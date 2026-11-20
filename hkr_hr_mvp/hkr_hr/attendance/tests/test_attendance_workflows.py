from tools.profile_revision import profile_revision
import io
import json
import re
import tempfile
import unittest
import zipfile
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from openpyxl import load_workbook
from sqlalchemy import inspect, text
from werkzeug.datastructures import FileStorage

from app import create_app
from models import (
    AuditLog,
    AttendanceBatch,
    AttendanceBatchItem,
    AttendanceMonthlySummary,
    AttendanceSegment,
    AttendanceSpecialDay,
    Employee,
    EmployeeAttendancePolicy,
    EmployeeAnnualLeaveBalance,
    EmployeeAnnualLeaveAllocation,
    EmployeeAnnualLeaveRecord,
    EmployeeAllowance,
    EmployeeBankAccount,
    EmployeeCertificate,
    EmployeeCompLeaveAllocation,
    EmployeeCompLeaveCredit,
    EmployeeDocument,
    EmployeeEmploymentPeriod,
    EmployeeFinalPaymentCase,
    EmployeeIdentity,
    EmployeeAssignment,
    EmployeeQualification,
    EmployeeSalary,
    EmployeeMpfEnrollment,
    EmployeeVisa,
    EmployeeWorkInjuryPeriod,
    EmployeeWorkInjuryMonthlyExpense,
    GeneratedContract,
    PayrollAdjustment,
    PayrollEmployeeResult,
    PayrollRun,
    MpfScheme,
    ReferenceList,
    ReferenceValue,
    User,
    WorkProject,
    WorkCalendarHoliday,
    db,
)
from tools.hr_core import (
    annual_leave_buckets,
    annual_leave_days_between,
    annual_leave_summary,
    create_mpf_enrollment,
    employee_type_by_code,
    ensure_reference_seed,
    reference_by_code,
    store_employee_file,
    uploaded_file_sha256,
)
from tools.hk_statutory_holidays import (
    parse_hong_kong_public_holidays,
    parse_hong_kong_statutory_holidays,
)
from tools.final_payment import (
    calculate_benefit,
    calculate_final_payment,
    service_portion_days,
)
from tools.payroll_engine import (
    calculate_payroll,
    casual_daily_mpf,
    employee_warnings,
    forecast_tail,
)
from tools.attendance_policy import (
    automatic_attendance_rows,
    is_legacy_inferred_special_day_summary,
    special_work_day_units,
)
from routes.payroll import mpf_preview_rows, result_lines
from routes.attendance import (
    validate_attendance_segment_totals,
    validate_sunday_holiday_entries,
)
from tools.completeness import employee_data_items
from tools.releases import CURRENT_VERSION, NEXT_VERSION, RELEASES
from tools.schema_migrations import (
    apply_additive_migrations,
    repair_legacy_inferred_special_day_attendance,
    retire_obsolete_audit_events,
    retire_legacy_tables,
    schema_compatibility_issues,
)
from tools.security import (
    LoginRateLimiter,
    UploadValidationError,
    safe_next_url,
    validate_uploaded_file,
)


from tests.fixtures import (
    APP_ROOT,
    HrAppTestCase,
    current_profile_revision,
    pdf_bytes,
)


class AttendanceWorkflowTests(HrAppTestCase):
    def test_attendance_rejects_period_day_totals_above_calendar_span(self):
        employee_id, _ = self.create_employee(
            "HKR", "site_daily", "考勤校驗測試", "ATTENDANCE VALIDATION"
        )
        created = self.client.post(
            "/attendance/batches",
            data={
                "files": [(
                    io.BytesIO(pdf_bytes("attendance-validation")),
                    "attendance-validation.pdf",
                )]
            },
            content_type="multipart/form-data",
            follow_redirects=False,
        )
        self.assertEqual(created.status_code, 302)
        with self.app.app_context():
            item_id = AttendanceBatchItem.query.one().id
        response = self.client.post(
            f"/attendance/items/{item_id}/save",
            data={
                "year_month": "2026-07",
                "employee_id": employee_id,
                "current_1_20_project_id": [""],
                "current_1_20_working_days": ["20"],
                "current_1_20_holiday_days": ["1"],
            },
            follow_redirects=True,
        )
        self.assertIn("出勤合計不可超過 20 日", response.get_data(as_text=True))
        with self.app.app_context():
            self.assertIsNone(db.session.get(AttendanceBatchItem, item_id).summary_id)

    def test_attendance_pdf_month_can_be_corrected_by_repreview(self):
        employee_id, _ = self.create_employee(
            "HKR", "site_monthly", "月份更正測試", "MONTH CORRECTION"
        )
        project_id = self.complete_employee(
            employee_id,
            "site_monthly",
            "TMC046",
            "monthly",
            "30000",
            "QA-MONTH-001",
            "60000991",
        )
        created = self.client.post(
            "/attendance/batches",
            data={
                "files": [(
                    io.BytesIO(pdf_bytes("attendance-month-correction")),
                    "attendance-month-correction.pdf",
                )]
            },
            content_type="multipart/form-data",
            follow_redirects=False,
        )
        self.assertEqual(created.status_code, 302)
        with self.app.app_context():
            item = AttendanceBatchItem.query.one()
            item_id = item.id
            batch_id = item.batch_id
            self.assertRegex(item.year_month, r"^\d{4}-\d{2}$")

        form = {
            "year_month": "2026-07",
            "employee_id": employee_id,
            "current_1_20_project_id": [str(project_id)],
            "current_1_20_working_days": ["10"],
            "current_1_20_ot_hours": ["0"],
            "current_1_20_holiday_days": ["0"],
            "current_1_20_large_ecall_count": ["0"],
            "current_1_20_ecall_count": ["0"],
        }
        saved = self.client.post(
            f"/attendance/items/{item_id}/save",
            data=form,
            follow_redirects=False,
        )
        self.assertEqual(saved.status_code, 302)
        with self.app.app_context():
            item = db.session.get(AttendanceBatchItem, item_id)
            summary_id = item.summary_id
            self.assertEqual(item.year_month, "2026-07")
            self.assertEqual(item.summary.year_month, "2026-07")
            self.assertEqual(item.summary.document.effective_month, "2026-07")
            run = PayrollRun(
                year_month="2026-07",
                payroll_group="site_monthly",
                rule_version="test",
            )
            db.session.add(run)
            db.session.flush()
            db.session.add(PayrollEmployeeResult(
                run=run,
                employee_id=employee_id,
                currency="HKD",
            ))
            db.session.commit()

        overview = self.client.get(
            f"/attendance?view=collection&batch_id={batch_id}"
        ).get_data(as_text=True)
        self.assertIn("重新預覽", overview)
        self.assertNotIn('name="year_month" value="2026-07"', overview)
        repreview = self.client.get(
            f"/attendance?view=collection&batch_id={batch_id}&item_id={item_id}"
        ).get_data(as_text=True)
        self.assertIn("已保存的考勤歸屬", repreview)
        self.assertIn("更正員工／月份", repreview)
        self.assertIn('name="year_month" value="2026-07"', repreview)
        self.assertIn("保存更正", repreview)
        correction_page = self.client.get(
            f"/attendance?view=collection&batch_id={batch_id}"
            f"&item_id={item_id}&correct_identity=1"
        ).get_data(as_text=True)
        self.assertIn("這份考勤所屬月份", correction_page)
        self.assertIn("正在更正考勤歸屬", correction_page)

        form["year_month"] = "2026-08"
        corrected = self.client.post(
            f"/attendance/summaries/{summary_id}/correct",
            data=form,
            follow_redirects=True,
        )
        self.assertEqual(corrected.status_code, 200)
        self.assertIn(
            "請重新核對及匯出工資表",
            corrected.get_data(as_text=True),
        )
        with self.app.app_context():
            item = db.session.get(AttendanceBatchItem, item_id)
            summary = db.session.get(AttendanceMonthlySummary, summary_id)
            self.assertEqual(item.year_month, "2026-08")
            self.assertEqual(summary.year_month, "2026-08")
            self.assertEqual(summary.document.effective_month, "2026-08")
            audit = AuditLog.query.filter_by(
                action="attendance_corrected",
                entity_id=summary_id,
            ).order_by(AuditLog.id.desc()).first()
            self.assertEqual(audit.before_json["year_month"], "2026-07")
            self.assertEqual(audit.after_json["year_month"], "2026-08")
            db.session.add(AttendanceMonthlySummary(
                employee_id=employee_id,
                year_month="2026-09",
                status="received",
            ))
            db.session.commit()

        form["year_month"] = "2026-09"
        conflict = self.client.post(
            f"/attendance/summaries/{summary_id}/correct",
            data=form,
            follow_redirects=True,
        )
        self.assertIn(
            "該員工在 2026-09 已有考勤",
            conflict.get_data(as_text=True),
        )
        with self.app.app_context():
            self.assertEqual(
                db.session.get(AttendanceMonthlySummary, summary_id).year_month,
                "2026-08",
            )

    def test_attendance_not_required_uses_default_full_attendance_and_is_reversible(self):
        employee_id, employee_no = self.create_employee(
            "HKR",
            "site_monthly",
            "無需考勤測試",
            "NO ATTENDANCE REQUIRED",
        )
        project_id = self.complete_employee(
            employee_id,
            "site_monthly",
            "TMC046",
            "monthly",
            "30000",
            "QA-NO-ATTENDANCE",
            "61110001",
        )

        landing = self.client.get("/attendance?month=2026-07&lang=en").get_data(as_text=True)
        self.assertIn('class="intake-resume"', landing)
        self.assertIn('data-attendance-upload-form>', landing)
        page = self.client.get("/attendance?month=2026-07&view=details&lang=en").get_data(
            as_text=True
        )
        self.assertIn(employee_no, page)
        self.assertNotIn('data-attendance-requirement="not_required"', page)
        self.assertIn('href="/attendance?month=2026-07&amp;view=details&amp;status=expected"', page)
        self.assertIn('href="/attendance?month=2026-07&amp;view=details&amp;status=missing"', page)
        self.assertIn('href="/attendance?month=2026-07&amp;view=details&amp;status=received"', page)
        self.assertNotIn('id="expected"', page)
        self.assertIn('id="missing"', page)
        self.assertNotIn('id="received"', page)
        self.assertIn("Current attendance month", page)
        self.assertIn("2026-07", page)
        self.assertIn(
            'href="/attendance-payroll?year_month=2026-07"',
            page,
        )

        missing_page = self.client.get(
            "/attendance?month=2026-07&view=details&status=missing&lang=en"
        ).get_data(as_text=True)
        self.assertIn('id="missing"', missing_page)
        self.assertIn(employee_no, missing_page)
        self.assertIn("Site workers (monthly)", missing_page)
        self.assertIn("TMC046", missing_page)

        expected_page = self.client.get(
            "/attendance?month=2026-07&view=details&status=expected&lang=en"
        ).get_data(as_text=True)
        self.assertIn('id="expected"', expected_page)
        self.assertIn(employee_no, expected_page)

        monthly_page = self.client.get(
            "/attendance?month=2026-07&view=monthly_exemptions&lang=en"
        ).get_data(as_text=True)
        self.assertIn(employee_no, monthly_page)
        self.assertIn("Specific-month attendance exemption", monthly_page)
        self.assertIn('id="attendance-policy-dialog"', monthly_page)
        self.assertIn('data-policy-action="exempt"', monthly_page)
        self.assertIn('data-policy-action="require"', monthly_page)

        response = self.client.post(
            "/attendance/monthly-exemptions/batch",
            data={
                "employee_ids": [str(employee_id)],
                "year_month": "2026-07",
                "action": "exempt",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        response_html = response.get_data(as_text=True)
        self.assertIn("Exempt this month", response_html)
        received_tab = self.client.get(
            "/attendance?month=2026-07&view=details&status=received&lang=en"
        ).get_data(as_text=True)
        self.assertIn('id="received"', received_tab)
        self.assertNotIn('id="missing"', received_tab)
        payroll_page = self.client.get(
            "/attendance-payroll?year_month=2026-07&payroll_group=site_monthly"
        ).get_data(as_text=True)
        self.assertIn("Attendance exemptions: attendance is required by default", payroll_page)
        self.assertIn("No attendance PDF is required this month; payroll uses default full attendance with zero OT and E-CALL", payroll_page)
        dashboard_page = self.client.get(
            "/dashboard?month=2026-07"
        ).get_data(as_text=True)
        self.assertRegex(dashboard_page, r"0(?:<small>)? / 0")
        english_payroll = self.client.get(
            "/attendance-payroll?year_month=2026-07&payroll_group=site_monthly&lang=en"
        ).get_data(as_text=True)
        self.assertIn("Attendance exemptions: attendance is required by default", english_payroll)
        self.client.get("/attendance?month=2026-07&lang=zh-Hant")

        with self.app.app_context():
            summary = AttendanceMonthlySummary.query.filter_by(
                employee_id=employee_id,
                year_month="2026-07",
            ).one()
            self.assertEqual(summary.status, "not_required")
            self.assertIsNone(summary.document_id)
            self.assertEqual(
                {segment.period_kind for segment in summary.segments},
                {
                    "current_1_20",
                    "current_21_end_forecast",
                    "previous_21_end",
                    "previous_21_end_forecast",
                },
            )
            self.assertGreater(
                sum(
                    segment.working_days + segment.sunday_holiday_days
                    for segment in summary.segments
                    if segment.period_kind == "current_1_20"
                ),
                Decimal("0"),
            )
            self.assertTrue(
                all(
                    segment.ot_hours == 0
                    and segment.large_ecall_count == 0
                    and segment.ecall_count == 0
                    and segment.sunday_holiday_days == 0
                    for segment in summary.segments
                )
            )
            previous_actual = sorted(
                (
                    segment.project_id or 0,
                    segment.working_days,
                    segment.sunday_holiday_days,
                )
                for segment in summary.segments
                if segment.period_kind == "previous_21_end"
            )
            previous_forecast = sorted(
                (
                    segment.project_id or 0,
                    segment.working_days,
                    segment.sunday_holiday_days,
                )
                for segment in summary.segments
                if segment.period_kind == "previous_21_end_forecast"
            )
            self.assertEqual(previous_actual, previous_forecast)
            payroll_row = calculate_payroll("2026-07", "site_monthly")[0]
            self.assertFalse(payroll_row["blockers"])
            self.assertEqual(payroll_row["ot_amount"], Decimal("0.00"))
            self.assertEqual(payroll_row["large_ecall_amount"], Decimal("0.00"))
            self.assertEqual(payroll_row["ecall_amount"], Decimal("0.00"))
            self.assertEqual(payroll_row["overpay_amount"], Decimal("0.00"))
            self.assertEqual(payroll_row["underpay_amount"], Decimal("0.00"))
            self.assertIn(
                "本月無需考勤表，按預設全勤及零 OT／E-CALL 計算",
                payroll_row["warnings"],
            )
            self.assertEqual(
                AuditLog.query.filter_by(
                    employee_id=employee_id,
                    action="attendance_not_required",
                ).count(),
                1,
            )

        response = self.client.post(
            "/attendance/monthly-exemptions/batch",
            data={
                "employee_ids": [str(employee_id)],
                "year_month": "2026-07",
                "action": "require",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("本月仍需考勤", response.get_data(as_text=True))
        with self.app.app_context():
            summary = AttendanceMonthlySummary.query.filter_by(
                employee_id=employee_id,
                year_month="2026-07",
            ).one()
            self.assertEqual(summary.status, "required")
            self.assertEqual(len(summary.segments), 0)
            payroll_row = calculate_payroll("2026-07", "site_monthly")[0]
            self.assertIn("考勤未收", payroll_row["blockers"])
            self.assertEqual(
                AuditLog.query.filter_by(
                    employee_id=employee_id,
                    action="attendance_required",
                ).count(),
                1,
            )

        self.add_attendance([(employee_id, project_id)])
        with self.app.app_context():
            summary = AttendanceMonthlySummary.query.filter_by(
                employee_id=employee_id,
                year_month="2026-07",
            ).one()
            self.assertEqual(summary.status, "received")
            self.assertIsNotNone(summary.document_id)
            payroll_row = calculate_payroll("2026-07", "site_monthly")[0]
            self.assertFalse(payroll_row["blockers"])
            self.assertNotIn(
                "本月無需考勤表，按預設全勤及零 OT／E-CALL 計算",
                payroll_row["warnings"],
            )

    def test_legacy_calendar_sundays_are_not_paid_as_real_extra_work(self):
        employee_id, _employee_no = self.create_employee(
            "HKR",
            "management",
            "舊版日曆星期日測試",
            "LEGACY CALENDAR SUNDAY",
        )
        project_id = self.complete_employee(
            employee_id,
            "management",
            "TMC046",
            "monthly",
            "65000",
            "QA-LEGACY-SUNDAY",
            "61110009",
        )
        with self.app.app_context():
            summary = AttendanceMonthlySummary(
                employee_id=employee_id,
                year_month="2026-08",
                status="not_required",
                no_attendance_reason="舊版免交考勤",
            )
            db.session.add(summary)
            db.session.flush()
            for period_kind, ordinary_days, sunday_days in (
                ("current_1_20", "17", "3"),
                ("current_21_end_forecast", "9", "2"),
                ("previous_21_end", "10", "1"),
                ("previous_21_end_forecast", "10", "1"),
            ):
                db.session.add(
                    AttendanceSegment(
                        summary_id=summary.id,
                        period_kind=period_kind,
                        project_id=project_id,
                        working_days=Decimal(ordinary_days),
                        sunday_holiday_days=Decimal(sunday_days),
                    )
                )
            db.session.commit()
            self.assertTrue(is_legacy_inferred_special_day_summary(summary))

            payroll_row = calculate_payroll("2026-08", "management")[0]
            self.assertFalse(payroll_row["blockers"])
            self.assertEqual(payroll_row["holiday_amount"], Decimal("0.00"))
            self.assertEqual(payroll_row["overpay_amount"], Decimal("0.00"))
            self.assertEqual(payroll_row["underpay_amount"], Decimal("0.00"))
            self.assertEqual(payroll_row["gross_amount"], Decimal("65000.00"))
            self.assertTrue(
                any(
                    "真正額外工作" in warning
                    for warning in payroll_row["warnings"]
                )
            )

            self.assertEqual(
                repair_legacy_inferred_special_day_attendance(),
                1,
            )
            db.session.refresh(summary)
            self.assertTrue(
                all(
                    segment.sunday_holiday_days == 0
                    for segment in summary.segments
                )
            )
            self.assertFalse(is_legacy_inferred_special_day_summary(summary))
            self.assertEqual(
                AuditLog.query.filter_by(
                    employee_id=employee_id,
                    action="attendance_legacy_special_days_repaired",
                ).count(),
                1,
            )
            self.assertEqual(
                repair_legacy_inferred_special_day_attendance(),
                0,
            )

            repaired_payroll_row = calculate_payroll(
                "2026-08",
                "management",
            )[0]
            self.assertEqual(
                repaired_payroll_row["gross_amount"],
                Decimal("65000.00"),
            )
            self.assertFalse(
                any(
                    "真正額外工作" in warning
                    for warning in repaired_payroll_row["warnings"]
                )
            )

            actual_segment = next(
                segment
                for segment in summary.segments
                if segment.period_kind == "current_1_20"
            )
            actual_segment.sunday_holiday_days = Decimal("1")
            db.session.add(
                AttendanceSpecialDay(
                    summary_id=summary.id,
                    segment_id=actual_segment.id,
                    period_kind="current_1_20",
                    project_id=project_id,
                    work_date=date(2026, 8, 2),
                    day_kind="sunday",
                    session="full_day",
                    handling="pay",
                    days=Decimal("1"),
                    status="active",
                )
            )
            db.session.commit()
            self.assertFalse(is_legacy_inferred_special_day_summary(summary))
            self.assertEqual(
                repair_legacy_inferred_special_day_attendance(),
                0,
            )
            real_work_payroll_row = calculate_payroll(
                "2026-08",
                "management",
            )[0]
            self.assertGreater(
                real_work_payroll_row["holiday_amount"],
                Decimal("0"),
            )
            self.assertGreater(
                real_work_payroll_row["gross_amount"],
                Decimal("65000"),
            )
            saved_summary_id = summary.id

        profile_page = self.client.get(
            f"/employees/{employee_id}?lang=zh-Hant"
        ).get_data(as_text=True)
        self.assertIn("月薪無需填寫", profile_page)
        self.assertIn("只記錄真正額外工作", profile_page)

        entry_page = self.client.get(
            f"/attendance?month=2026-08&summary_id={saved_summary_id}&lang=zh-Hant"
        ).get_data(as_text=True)
        self.assertIn("選擇真正有工作的日期", entry_page)
        self.assertIn("系統自動合計日數", entry_page)

    def test_attendance_employee_search_excludes_departed_and_blocks_wheel_changes(self):
        active_id, active_no = self.create_employee(
            "HKR",
            "site_monthly",
            "黃搜尋",
            "SEARCH ACTIVE",
        )
        departed_id, departed_no = self.create_employee(
            "HKR",
            "site_monthly",
            "黃離職",
            "SEARCH DEPARTED",
        )
        self.complete_employee(
            active_id,
            "site_monthly",
            "TMC046",
            "monthly",
            "30000",
            "QA-SEARCH-ACTIVE",
            "61110101",
        )
        self.complete_employee(
            departed_id,
            "site_monthly",
            "TMC046",
            "monthly",
            "30000",
            "QA-SEARCH-DEPARTED",
            "61110102",
        )
        with self.app.app_context():
            active = db.session.get(Employee, active_id)
            active.current_assignment.effective_from = date(2026, 6, 1)
            departed = db.session.get(Employee, departed_id)
            departed.current_period.end_date = date(2026, 7, 31)
            departed.status = "departed"
            summary = AttendanceMonthlySummary(
                employee_id=active_id,
                year_month="2026-08",
                status="received",
            )
            db.session.add(summary)
            db.session.commit()
            summary_id = summary.id

        locked_page = self.client.get(
            f"/attendance?month=2026-08&summary_id={summary_id}&lang=zh-Hant"
        ).get_data(as_text=True)
        self.assertNotRegex(locked_page, r'<input[^>]+type="search"')
        self.assertIn("已保存的考勤歸屬", locked_page)
        page = self.client.get(
            f"/attendance?month=2026-08&summary_id={summary_id}"
            "&correct_identity=1&lang=zh-Hant"
        ).get_data(as_text=True)
        self.assertRegex(page, r'<input[^>]+type="search"')
        self.assertNotIn("支持員工編號、英文姓名及繁簡體中文混合搜尋", page)
        self.assertIn("input.showPicker()", page)
        self.assertIn(active_no, page)
        self.assertIn("SEARCH ACTIVE", page)
        self.assertIn("黃搜尋", page)
        self.assertIn("黄搜寻", page)
        self.assertNotIn(departed_no, page)
        self.assertNotIn("SEARCH DEPARTED", page)
        self.assertIn("input[type='number']", page)
        self.assertIn("document.activeElement === input", page)

        profile = self.client.get(
            f"/employees/{active_id}?tab=employment&lang=zh-Hant"
        ).get_data(as_text=True)
        current_card = re.search(
            r'<article class="panel current-state-card">.*?當前任職.*?</article>',
            profile,
            re.S,
        )
        self.assertIsNotNone(current_card)
        self.assertIn("入職日期", current_card.group(0))
        self.assertIn("2026-01-01", current_card.group(0))
        self.assertNotIn("2026-06-01", current_card.group(0))

    def test_attendance_linked_leave_is_compact_actionable_and_type_specific(self):
        employee_id, _ = self.create_employee(
            "HKR",
            "management",
            "假期聯動提示",
            "LEAVE LINK ALERT",
        )
        self.complete_employee(
            employee_id,
            "management",
            "TMC046",
            "monthly",
            "31000",
            "QA-LEAVE-LINK",
            "61110109",
        )
        with self.app.app_context():
            summary = AttendanceMonthlySummary(
                employee_id=employee_id,
                year_month="2026-08",
                status="received",
            )
            db.session.add_all(
                [
                    summary,
                    EmployeeAnnualLeaveRecord(
                    employee_id=employee_id,
                    leave_date=date(2026, 7, 14),
                    end_date=date(2026, 7, 21),
                    entitlement_year=2026,
                    days=Decimal("6.5"),
                    leave_type="annual",
                    status="active",
                    ),
                ]
            )
            db.session.commit()
            summary_id = summary.id

        page = self.client.get(
            f"/attendance?month=2026-08&summary_id={summary_id}"
            "&lang=zh-Hant"
        ).get_data(as_text=True)
        self.assertIn("本次考勤有 1 筆年假", page)
        self.assertIn("上月尾段", page)
        self.assertIn("需核對 2026-07-21–2026-07-21", page)
        self.assertIn("原記錄 2026-07-14–2026-07-21 · 6.5 日", page)
        self.assertIn("全薪 · 不計實際出勤，由系統另計年假薪酬", page)
        self.assertIn("請從實際出勤扣除相應 1 日／0.5 日", page)
        self.assertIn("HR 操作：", page)
        self.assertIn("前往假期與工傷", page)
        self.assertNotIn("病假憑證必須補交", page)

        with self.app.app_context():
            db.session.add(
                EmployeeAnnualLeaveRecord(
                    employee_id=employee_id,
                    leave_date=date(2026, 8, 5),
                    end_date=date(2026, 8, 5),
                    entitlement_year=2026,
                    days=Decimal("1"),
                    leave_type="sick",
                    status="active",
                )
            )
            db.session.commit()

        page = self.client.get(
            f"/attendance?month=2026-08&summary_id={summary_id}"
            "&lang=zh-Hant"
        ).get_data(as_text=True)
        self.assertIn("本次考勤有 1 筆年假、1 筆病假", page)
        self.assertIn("依病假規則計薪", page)
        self.assertIn("病假憑證待補", page)

    def test_long_term_attendance_policy_is_effective_dated_and_batch_reversible(self):
        employee_id, employee_no = self.create_employee(
            "HKR",
            "site_monthly",
            "長期免交測試",
            "LONG TERM EXEMPT",
        )
        self.complete_employee(
            employee_id,
            "site_monthly",
            "TMC046",
            "monthly",
            "30000",
            "QA-LONG-TERM",
            "61110002",
        )
        response = self.client.post(
            "/attendance/policies/batch",
            data={
                "employee_ids": [str(employee_id)],
                "effective_from_month": "2026-07",
                "action": "exempt",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        page = response.get_data(as_text=True)
        self.assertIn(employee_no, page)
        self.assertIn("長期免交", page)
        with self.app.app_context():
            policy = EmployeeAttendancePolicy.query.filter_by(
                employee_id=employee_id,
                effective_from_month="2026-07",
            ).one()
            self.assertFalse(policy.requires_attendance)
            july = calculate_payroll("2026-07", "site_monthly")[0]
            self.assertFalse(july["blockers"])
            self.assertTrue(
                any("永久無需考勤表" in item for item in july["warnings"])
            )
            self.assertEqual(july["ot_amount"], Decimal("0.00"))
        payroll_page = self.client.get(
            "/attendance-payroll",
            query_string={
                "year_month": "2026-07",
                "payroll_group": "site_monthly",
                "status": "ready",
            },
        ).get_data(as_text=True)
        self.assertIn("payroll-summary-card active", payroll_page)
        self.assertIn(employee_no, payroll_page)
        self.assertIn("匯出此員工工資表", payroll_page)
        self.assertIn("30,000.00", payroll_page)
        self.assertNotIn("payroll-person-preview", payroll_page)

        response = self.client.post(
            "/attendance/policies/batch",
            data={
                "employee_ids": [str(employee_id)],
                "effective_from_month": "2026-08",
                "action": "require",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            self.assertFalse(
                calculate_payroll("2026-07", "site_monthly")[0]["blockers"]
            )
            self.assertIn(
                "考勤未收",
                calculate_payroll("2026-08", "site_monthly")[0]["blockers"],
            )
            self.assertEqual(
                AuditLog.query.filter(
                    AuditLog.employee_id == employee_id,
                    AuditLog.action.in_(
                        [
                            "attendance_policy_exempted",
                            "attendance_policy_required",
                        ]
                    ),
                ).count(),
                2,
            )

    def test_attendance_policy_list_sorts_by_payroll_group(self):
        management_id, management_no = self.create_employee(
            "HKR",
            "management",
            "管理排序測試",
            "POLICY MANAGEMENT",
        )
        daily_id, daily_no = self.create_employee(
            "HKRD",
            "site_daily",
            "日工排序測試",
            "POLICY DAILY",
        )
        monthly_id, monthly_no = self.create_employee(
            "HKR",
            "site_monthly",
            "月工排序測試",
            "POLICY MONTHLY",
        )
        self.complete_employee(
            management_id,
            "management",
            "TMC046",
            "monthly",
            "30000",
            "QA-POLICY-MGMT",
            "61231001",
        )
        self.complete_employee(
            daily_id,
            "site_daily",
            "TMC046",
            "daily",
            "1000",
            "QA-POLICY-DAILY",
            "61231002",
        )
        self.complete_employee(
            monthly_id,
            "site_monthly",
            "TMC046",
            "monthly",
            "20000",
            "QA-POLICY-MONTHLY",
            "61231003",
        )

        ascending = self.client.get(
            "/attendance",
            query_string={
                "month": "2026-08",
                "view": "policies",
                "sort": "payroll_group",
                "direction": "asc",
            },
        ).get_data(as_text=True)
        self.assertLess(
            ascending.index(daily_no),
            ascending.index(monthly_no),
        )
        self.assertLess(
            ascending.index(monthly_no),
            ascending.index(management_no),
        )
        self.assertIn("薪酬組別 ↑", ascending)
        self.assertIn("policy-actions-head", ascending)

        descending = self.client.get(
            "/attendance",
            query_string={
                "month": "2026-08",
                "view": "policies",
                "sort": "payroll_group",
                "direction": "desc",
            },
        ).get_data(as_text=True)
        self.assertLess(
            descending.index(management_no),
            descending.index(monthly_no),
        )
        self.assertLess(
            descending.index(monthly_no),
            descending.index(daily_no),
        )

    def test_departed_employee_is_missing_only_through_departure_month(self):
        employee_id, employee_no = self.create_employee(
            "HKR",
            "site_monthly",
            "離職考勤測試",
            "DEPARTED ATTENDANCE TEST",
        )
        self.complete_employee(
            employee_id,
            "site_monthly",
            "TMC046",
            "monthly",
            "30000",
            "QA-DEPARTED-ATTENDANCE",
            "61110002",
        )
        with self.app.app_context():
            employee = db.session.get(Employee, employee_id)
            employee.current_period.end_date = date(2026, 7, 15)
            employee.status = "departed"
            db.session.commit()

        departure_month = self.client.get(
            "/attendance?month=2026-07&view=details&status=missing"
        ).get_data(as_text=True)
        self.assertIn(employee_no, departure_month)

        after_departure = self.client.get(
            "/attendance?month=2026-08&view=details&status=missing"
        ).get_data(as_text=True)
        self.assertNotIn(employee_no, after_departure)

    def test_attendance_prorated_monthly_salary_and_work_calendar_forecast(self):
        employee_id, _ = self.create_employee(
            "HKR",
            "site_monthly",
            "例外月薪測試",
            "ATTENDANCE PRORATED",
        )
        project_id = self.complete_employee(
            employee_id,
            "site_monthly",
            "TMC046",
            "monthly",
            "31000",
            "QA-PRORATED-001",
            "62220001",
        )
        with self.app.app_context():
            employee = db.session.get(Employee, employee_id)
            employee.current_salary.monthly_pay_method = "attendance_days"
            employee.allowances.append(
                EmployeeAllowance(
                    label="Daily meal",
                    allowance_type="meal",
                    currency="HKD",
                    amount=Decimal("50"),
                    effective_from=date(2026, 1, 1),
                    status="active",
                )
            )
            summary = AttendanceMonthlySummary(
                employee_id=employee_id,
                year_month="2026-07",
                status="received",
            )
            for kind, days in (
                ("current_1_20", Decimal("10")),
                ("current_21_end_forecast", Decimal("0")),
                ("previous_21_end", Decimal("0")),
                ("previous_21_end_forecast", Decimal("0")),
            ):
                summary.segments.append(
                    AttendanceSegment(
                        period_kind=kind,
                        project_id=project_id,
                        working_days=days,
                        sunday_holiday_days=Decimal("0"),
                        ot_hours=Decimal("0"),
                    )
                )
            db.session.add(summary)
            db.session.commit()

            row = calculate_payroll("2026-07", "site_monthly")[0]
            self.assertEqual(row["base_amount"], Decimal("10000.00"))
            self.assertEqual(
                row["traffic_meal_allowance_amount"],
                Decimal("500.00"),
            )
            self.assertEqual(row["holiday_amount"], Decimal("0.00"))

            region_id = employee.current_assignment.region_id
            db.session.add(
                WorkCalendarHoliday(
                    region_id=region_id,
                    holiday_date=date(2026, 7, 24),
                    name="Test statutory holiday",
                    applies_to_statutory=True,
                    applies_to_public=True,
                    active=True,
                )
            )
            employee.current_salary.monthly_pay_method = "full_month"
            db.session.commit()
            monthly_rows = automatic_attendance_rows(
                employee,
                date(2026, 7, 21),
                date(2026, 7, 31),
            )
            self.assertEqual(
                sum(Decimal(str(item["working_days"])) for item in monthly_rows),
                Decimal("9"),
            )
            employee.current_assignment.payroll_group = "management"
            employee.current_assignment.workweek_days = Decimal("5")
            employee.payroll_group = "management"
            db.session.commit()
            management_rows = automatic_attendance_rows(
                employee,
                date(2026, 7, 21),
                date(2026, 7, 31),
            )
            self.assertEqual(
                sum(Decimal(str(item["working_days"])) for item in management_rows),
                Decimal("8"),
            )
            holiday = WorkCalendarHoliday.query.filter_by(
                region_id=region_id,
                holiday_date=date(2026, 7, 24),
            ).one()
            holiday.applies_to_public = False
            db.session.commit()
            statutory_only_management_rows = automatic_attendance_rows(
                employee,
                date(2026, 7, 21),
                date(2026, 7, 31),
            )
            self.assertEqual(
                sum(
                    Decimal(str(item["working_days"]))
                    for item in statutory_only_management_rows
                ),
                Decimal("9"),
            )
            holiday.applies_to_public = True
            employee.current_salary.monthly_pay_method = "attendance_days"
            db.session.commit()
            self.assertEqual(
                automatic_attendance_rows(
                    employee,
                    date(2026, 7, 21),
                    date(2026, 7, 31),
                ),
                [],
            )


if __name__ == "__main__":
    unittest.main()
