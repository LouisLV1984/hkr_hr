from hkr_hr.attendance.api import profile_revision
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
from hkr_hr.platform.db import AuditLog, User, db
from hkr_hr.attendance.api import AttendanceBatch, AttendanceBatchItem, AttendanceMonthlySummary, AttendanceSegment, AttendanceSpecialDay
from hkr_hr.employees.api import Employee, EmployeeAttendancePolicy, EmployeeAllowance, EmployeeBankAccount, EmployeeCertificate, EmployeeEmploymentPeriod, EmployeeIdentity, EmployeeAssignment, EmployeeQualification, EmployeeSalary, EmployeeMpfEnrollment, EmployeeVisa
from hkr_hr.leave.api import EmployeeAnnualLeaveBalance, EmployeeAnnualLeaveAllocation, EmployeeAnnualLeaveRecord, EmployeeCompLeaveAllocation, EmployeeCompLeaveCredit, EmployeeWorkInjuryPeriod, EmployeeWorkInjuryMonthlyExpense
from hkr_hr.documents.api import EmployeeDocument, GeneratedContract
from hkr_hr.payroll.api import EmployeeFinalPaymentCase, PayrollAdjustment, PayrollEmployeeResult, PayrollRun
from hkr_hr.references.api import MpfScheme, ReferenceList, ReferenceValue, WorkProject, WorkCalendarHoliday
from hkr_hr.leave.api import annual_leave_buckets, annual_leave_summary
from hkr_hr.platform.dates import annual_leave_days_between
from hkr_hr.employees.api import create_mpf_enrollment
from hkr_hr.references.api import employee_type_by_code, ensure_reference_seed, reference_by_code
from hkr_hr.platform.files import store_employee_file, uploaded_file_sha256
from hkr_hr.references.api import parse_hong_kong_public_holidays, parse_hong_kong_statutory_holidays
from hkr_hr.payroll.api import calculate_benefit, calculate_final_payment, service_portion_days
from hkr_hr.payroll.api import calculate_payroll, casual_daily_mpf, employee_warnings, forecast_tail
from hkr_hr.attendance.api import automatic_attendance_rows, is_legacy_inferred_special_day_summary, special_work_day_units
from hkr_hr.payroll.api import mpf_preview_rows, result_lines
from hkr_hr.workbench.api import validate_attendance_segment_totals, validate_sunday_holiday_entries
from hkr_hr.payroll.api import employee_data_items
from hkr_hr.workbench.api import CURRENT_VERSION, NEXT_VERSION, RELEASES
from hkr_hr.workbench.api import apply_additive_migrations, repair_legacy_inferred_special_day_attendance, retire_obsolete_audit_events, retire_legacy_tables, schema_compatibility_issues
from hkr_hr.platform.security import LoginRateLimiter, UploadValidationError, safe_next_url, validate_uploaded_file


from tests.fixtures import (
    APP_ROOT,
    HrAppTestCase,
    current_profile_revision,
    pdf_bytes,
)


class LeaveWorkflowTests(HrAppTestCase):
    def test_annual_leave_legacy_bucket_and_special_extension(self):
        employee_id, _ = self.create_employee(
            "ASMTP",
            "management",
            "年假桶測試",
            "LEAVE BUCKET TEST",
        )
        self.complete_employee(
            employee_id,
            "management",
            "TMC046",
            "monthly",
            "30000",
            "LEAVE1001",
            "65550001",
        )
        with self.app.app_context():
            employee = db.session.get(Employee, employee_id)
            employee.current_period.start_date = date(2020, 1, 1)
            employee.current_period.contract_annual_leave_days = Decimal("10")
            db.session.add(
                EmployeeCompLeaveCredit(
                    employee_id=employee_id,
                    source_date=date(2026, 7, 5),
                    source_kind="rest_day",
                    days=Decimal("1"),
                    status="active",
                )
            )
            db.session.commit()

        response = self.client.post(
            f"/annual-leave/{employee_id}/balance",
            data={
                "year": "2025",
                "entitled_days": "8",
                "legacy_days": "8",
                "extended_until": "2026-12-31",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        response = self.client.post(
            f"/employees/{employee_id}/annual-leave",
            data={
                "start_date": "2026-08-10",
                "start_session": "am",
                "end_date": "2026-08-14",
                "end_session": "pm",
                "entitlement_year": "2026",
                "days": "5",
                "legacy_days": "3",
                "regular_days": "2",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("請假記錄已新增", response.get_data(as_text=True))
        with self.app.app_context():
            record = EmployeeAnnualLeaveRecord.query.one()
            self.assertEqual(record.days, Decimal("5.0"))
            self.assertEqual(len(record.comp_leave_allocations), 1)
            self.assertEqual(
                record.comp_leave_allocations[0].days, Decimal("1.0")
            )
            self.assertEqual(
                EmployeeAnnualLeaveAllocation.query.filter_by(
                    record_id=record.id
                ).count(),
                1,
            )
            allocations = {
                item.balance.year: item.days for item in record.allocations
            }
            self.assertEqual(allocations[2023], Decimal("4.0"))
            employee = db.session.get(Employee, employee_id)
            buckets = annual_leave_buckets(
                employee,
                as_of=date(2026, 8, 14),
            )
            by_year = {item["year"]: item for item in buckets}
            self.assertEqual(by_year[2023]["remaining"], Decimal("4.0"))
            self.assertEqual(by_year[2025]["remaining"], Decimal("8.0"))
            self.assertEqual(by_year[2025]["expiry_date"], date(2026, 12, 31))

    def test_annual_leave_record_is_not_counted_against_two_buckets(self):
        employee_id, _ = self.create_employee(
            "ASMTP",
            "management",
            "年假跨帳戶測試",
            "LEAVE CROSS BUCKET TEST",
        )
        self.complete_employee(
            employee_id,
            "management",
            "TMC046",
            "monthly",
            "30000",
            "LEAVE1002",
            "65550002",
        )
        with self.app.app_context():
            employee = db.session.get(Employee, employee_id)
            employee.current_period.start_date = date(2020, 1, 1)
            employee.current_period.contract_annual_leave_days = Decimal("14")
            legacy_balance = EmployeeAnnualLeaveBalance(
                employee_id=employee_id,
                year=2023,
                entitled_days_override=Decimal("50.5"),
            )
            current_balance = EmployeeAnnualLeaveBalance(
                employee_id=employee_id,
                year=2026,
                entitled_days_override=Decimal("14"),
                expiry_date=date(2027, 3, 31),
            )
            db.session.add_all([legacy_balance, current_balance])
            db.session.flush()

            fallback_record = EmployeeAnnualLeaveRecord(
                employee_id=employee_id,
                leave_date=date(2026, 7, 1),
                end_date=date(2026, 7, 7),
                entitlement_year=2026,
                days=Decimal("7"),
                leave_type="annual",
                status="active",
            )
            legacy_record = EmployeeAnnualLeaveRecord(
                employee_id=employee_id,
                leave_date=date(2026, 8, 31),
                end_date=date(2026, 8, 31),
                start_session="am",
                end_session="am",
                entitlement_year=2026,
                days=Decimal("0.5"),
                leave_type="annual",
                status="active",
            )
            comp_record = EmployeeAnnualLeaveRecord(
                employee_id=employee_id,
                leave_date=date(2026, 9, 1),
                end_date=date(2026, 9, 1),
                entitlement_year=2026,
                days=Decimal("1"),
                leave_type="annual",
                status="active",
            )
            sick_record = EmployeeAnnualLeaveRecord(
                employee_id=employee_id,
                leave_date=date(2026, 9, 2),
                end_date=date(2026, 9, 3),
                entitlement_year=2026,
                days=Decimal("2"),
                leave_type="sick",
                status="active",
            )
            credit = EmployeeCompLeaveCredit(
                employee_id=employee_id,
                source_date=date(2026, 6, 1),
                source_kind="rest_day",
                days=Decimal("1"),
                status="active",
            )
            db.session.add_all(
                [
                    fallback_record,
                    legacy_record,
                    comp_record,
                    sick_record,
                    credit,
                ]
            )
            db.session.flush()
            fixed_utc = datetime(2026, 9, 1, 6, 30)
            legacy_record.created_at = fixed_utc
            legacy_record.updated_at = fixed_utc
            db.session.add_all(
                [
                    EmployeeAnnualLeaveAllocation(
                        record_id=legacy_record.id,
                        balance_id=legacy_balance.id,
                        days=Decimal("0.5"),
                    ),
                    EmployeeCompLeaveAllocation(
                        leave_record_id=comp_record.id,
                        credit_id=credit.id,
                        days=Decimal("1"),
                    ),
                ]
            )
            db.session.commit()

            buckets = annual_leave_buckets(
                employee,
                as_of=date(2026, 9, 1),
            )
            by_year = {item["year"]: item for item in buckets}
            self.assertEqual(by_year[2023]["used"], Decimal("0.5"))
            self.assertEqual(by_year[2023]["remaining"], Decimal("50.0"))
            self.assertEqual(by_year[2026]["used"], Decimal("7.0"))
            self.assertEqual(by_year[2026]["remaining"], Decimal("7.0"))

            summary = annual_leave_summary(employee, 2026)
            self.assertEqual(summary["used"], Decimal("8.5"))
            self.assertEqual(summary["bucket_used"], Decimal("7.0"))
            self.assertEqual(summary["remaining"], Decimal("7.0"))

        page = self.client.get(
            f"/annual-leave?year=2026&employee_id={employee_id}"
        ).get_data(as_text=True)
        self.assertIn("本年實際已放", page)
        self.assertIn("所有帳戶合計", page)
        self.assertIn("本年度帳戶剩餘", page)
        self.assertIn("已確認總額", page)
        self.assertIn("目前剩餘＝已確認總額－已扣除", page)
        self.assertIn("假期變更歷史", page)
        self.assertIn("變更時間（香港）", page)
        self.assertIn("2026-09-01 14:30", page)
        self.assertIn("假期日期：2026-08-31", page)
        self.assertNotIn("2026-08-31 至 2026-08-31", page)
        self.assertIn("假期日期：2026-09-02 上午 – 2026-09-03 下午", page)
        self.assertIn("補休只可由考勤錄入產生", page)
        self.assertIn("扣自：2023及以前 0.5 日", page)
        self.assertIn("扣自：補休 1.0 日", page)

        response = self.client.post(
            f"/annual-leave/{employee_id}/balance",
            data={
                "year": "2026",
                "scope": "current",
                "entitled_days": "15",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            self.assertEqual(
                EmployeeAnnualLeaveBalance.query.filter_by(
                    employee_id=employee_id,
                    year=2026,
                ).one().entitled_days_override,
                Decimal("15.0"),
            )
            self.assertEqual(
                EmployeeAnnualLeaveBalance.query.filter_by(
                    employee_id=employee_id,
                    year=2023,
                ).one().entitled_days_override,
                Decimal("50.5"),
            )

        response = self.client.post(
            f"/annual-leave/{employee_id}/balance",
            data={
                "year": "2026",
                "scope": "legacy",
                "legacy_days": "51",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        page = response.get_data(as_text=True)
        self.assertIn("年假額度調整", page)
        with self.app.app_context():
            self.assertEqual(
                EmployeeAnnualLeaveBalance.query.filter_by(
                    employee_id=employee_id,
                    year=2026,
                ).one().entitled_days_override,
                Decimal("15.0"),
            )
            self.assertEqual(
                EmployeeAnnualLeaveBalance.query.filter_by(
                    employee_id=employee_id,
                    year=2023,
                ).one().entitled_days_override,
                Decimal("51.0"),
            )

    def test_leave_work_injury_allowance_and_special_day_payroll_rules(self):
        sick_employee_id, _ = self.create_employee(
            "ASMTP",
            "site_monthly",
            "病假薪酬測試",
            "SICK PAY TEST",
        )
        project_id = self.complete_employee(
            sick_employee_id,
            "site_monthly",
            "TMC046",
            "monthly",
            "31000",
            "SP100001",
            "62223100",
        )
        injury_employee_id, _ = self.create_employee(
            "ASMTP",
            "site_monthly",
            "工傷薪酬測試",
            "INJURY PAY TEST",
        )
        self.complete_employee(
            injury_employee_id,
            "site_monthly",
            "TMC046",
            "monthly",
            "31000",
            "WI100001",
            "62224800",
        )

        with self.app.app_context():
            sick_employee = db.session.get(Employee, sick_employee_id)
            sick_employee.current_period.confirmation_date = date(2026, 6, 30)
            summary = AttendanceMonthlySummary(
                employee_id=sick_employee_id,
                year_month="2026-07",
                status="received",
                special_day_handling="pay",
            )
            db.session.add(summary)
            db.session.flush()
            segment = AttendanceSegment(
                summary=summary,
                period_kind="current_1_20",
                project_id=project_id,
                # Monthly ordinary-day input is intentionally ignored.
                working_days=Decimal("16"),
                other_allowance_amount=Decimal("250"),
            )
            db.session.add(segment)
            db.session.flush()
            special_day = AttendanceSpecialDay(
                summary=summary,
                segment=segment,
                period_kind="current_1_20",
                project_id=project_id,
                work_date=date(2026, 7, 5),
                day_kind="rest_day",
                handling="pay",
                days=Decimal("1"),
                status="active",
            )
            db.session.add_all(
                [
                    special_day,
                    EmployeeAnnualLeaveRecord(
                        employee_id=sick_employee_id,
                        leave_date=date(2026, 7, 10),
                        end_date=date(2026, 7, 12),
                        start_session="am",
                        end_session="pm",
                        entitlement_year=2026,
                        days=Decimal("3"),
                        leave_type="sick",
                        status="active",
                    ),
                    EmployeeAllowance(
                        employee_id=sick_employee_id,
                        label="餐補",
                        allowance_type="meal",
                        currency="HKD",
                        amount=Decimal("310"),
                        effective_from=date(2026, 7, 1),
                        status="active",
                    ),
                    EmployeeAllowance(
                        employee_id=sick_employee_id,
                        label="特殊津貼",
                        allowance_type="special",
                        currency="HKD",
                        amount=Decimal("620"),
                        effective_from=date(2026, 7, 1),
                        status="active",
                    ),
                    EmployeeWorkInjuryPeriod(
                        employee_id=injury_employee_id,
                        accident_date=date(2026, 7, 1),
                        payroll_start_date=date(2026, 7, 1),
                        payroll_end_date=date(2026, 7, 31),
                        confirmed_monthly_earnings=Decimal("31000"),
                        incapacity_monthly_earnings=Decimal("0"),
                        currency="HKD",
                        status="active",
                    ),
                ]
            )
            db.session.commit()

            rows = calculate_payroll("2026-07", "site_monthly")
            sick_row = next(
                row for row in rows if row["employee"].id == sick_employee_id
            )
            self.assertEqual(sick_row["sick_leave_days"], Decimal("3.0"))
            self.assertEqual(sick_row["sick_leave_amount"], Decimal("2600.00"))
            self.assertEqual(
                sick_row["traffic_meal_allowance_amount"], Decimal("8680.00")
            )
            self.assertEqual(
                sick_row["special_allowance_amount"], Decimal("620.00")
            )
            self.assertEqual(sick_row["gross_amount"], Decimal("41150.00"))
            self.assertEqual(
                sick_row["attendance_other_allowance_amount"], Decimal("250.00")
            )
            line = sick_row["lines"][0]
            self.assertEqual(line["working_days"], Decimal("28.00"))
            self.assertEqual(line["holiday_days"], Decimal("1.00"))
            self.assertIn("病假憑證待補", sick_row["warnings"])

            special_day.handling = "comp_leave"
            summary.special_day_handling = "comp_leave"
            db.session.commit()
            sick_row = next(
                row
                for row in calculate_payroll("2026-07", "site_monthly")
                if row["employee"].id == sick_employee_id
            )
            self.assertEqual(sick_row["gross_amount"], Decimal("40150.00"))
            self.assertEqual(sick_row["lines"][0]["holiday_days"], Decimal("0.00"))

            db.session.add(
                AttendanceSegment(
                    summary=summary,
                    period_kind="current_21_end_forecast",
                    project_id=project_id,
                    working_days=Decimal("0"),
                    sunday_holiday_days=Decimal("1"),
                )
            )
            db.session.commit()
            sick_row = next(
                row
                for row in calculate_payroll("2026-07", "site_monthly")
                if row["employee"].id == sick_employee_id
            )
            self.assertEqual(sick_row["gross_amount"], Decimal("41150.00"))
            self.assertEqual(
                sick_row["lines"][0]["forecast_holiday_days"],
                Decimal("1.00"),
            )

            injury_row = next(
                row
                for row in calculate_payroll("2026-07", "site_monthly")
                if row["employee"].id == injury_employee_id
            )
            self.assertFalse(injury_row["blockers"])
            self.assertEqual(injury_row["work_injury_days"], Decimal("31.0"))
            self.assertEqual(
                injury_row["work_injury_amount"], Decimal("24800.00")
            )
            self.assertEqual(injury_row["gross_amount"], Decimal("24800.00"))

            injury_period = EmployeeWorkInjuryPeriod.query.filter_by(
                employee_id=injury_employee_id
            ).one()
            injury_period.pay_mode = "full_pay"
            db.session.add(
                EmployeeWorkInjuryMonthlyExpense(
                    employee_id=injury_employee_id,
                    work_injury_period_id=injury_period.id,
                    year_month="2026-07",
                    amount=Decimal("800"),
                    currency="HKD",
                    status="active",
                )
            )
            db.session.commit()
            injury_row = next(
                row
                for row in calculate_payroll("2026-07", "site_monthly")
                if row["employee"].id == injury_employee_id
            )
            self.assertEqual(injury_row["work_injury_amount"], Decimal("31000.00"))
            self.assertEqual(injury_row["gross_amount"], Decimal("31000.00"))
            self.assertEqual(
                injury_row["work_injury_medical_reimbursement_amount"],
                Decimal("800.00"),
            )
            self.assertEqual(injury_row["net_amount"], Decimal("30300.00"))

        employment_page = self.client.get(
            f"/employees/{sick_employee_id}?tab=employment"
        ).get_data(as_text=True)
        self.assertIn("變更歷史", employment_page)
        self.assertIn("補貼", employment_page)
        self.assertIn('id="allowance-editor-', employment_page)
        self.assertIn("可不填；留空表示持續生效", employment_page)
        self.assertNotIn("補貼時間線", employment_page)

        injury_search_page = self.client.get(
            "/annual-leave",
            query_string={"view": "injury", "q": "工伤薪酬测试"},
        ).get_data(as_text=True)
        self.assertIn("假期與工傷", injury_search_page)
        self.assertIn("工傷管理", injury_search_page)
        self.assertIn("工傷薪酬測試", injury_search_page)
        injury_detail_page = self.client.get(
            "/annual-leave",
            query_string={
                "view": "injury",
                "employee_id": injury_employee_id,
            },
        ).get_data(as_text=True)
        self.assertIn("按〔核實每月收入－期間每月收入〕× 4/5", injury_detail_page)
        self.assertIn("日工 AM；月工／OFFICE AN", injury_detail_page)

        payroll_page = self.client.get(
            "/attendance-payroll",
            query_string={
                "year_month": "2026-07",
                "status": "all",
                "employee_id": sick_employee_id,
            },
        ).get_data(as_text=True)
        self.assertNotIn("工資更正與一次性調整", payroll_page)
        self.assertNotIn('action="/payroll/adjustments"', payroll_page)
        self.assertIn("離職當月的工資只由離職結算", payroll_page)

    def test_attendance_special_dates_generate_and_void_comp_leave(self):
        employee_id, _ = self.create_employee(
            "HKRD", "site_daily", "補休聯動測試", "COMP LEAVE TEST"
        )
        project_id = self.complete_employee(
            employee_id,
            "site_daily",
            "TMC046",
            "daily",
            "500",
            "CL100001",
            "62225000",
            mpf_mode="casual",
        )
        with self.app.app_context():
            employee = db.session.get(Employee, employee_id)
            db.session.add_all(
                [
                    WorkCalendarHoliday(
                        region_id=employee.current_assignment.region_id,
                        holiday_date=holiday_date,
                        name=f"補休測試法定假日 {holiday_date:%m-%d}",
                        active=True,
                    )
                    for holiday_date in (date(2026, 7, 5), date(2026, 7, 12))
                ]
            )
            db.session.commit()
        response = self.client.post(
            "/attendance/batches",
            data={
                "year_month": "2026-07",
                "files": [
                    (
                        io.BytesIO(pdf_bytes("comp-leave-attendance")),
                        "comp-leave-attendance.pdf",
                    )
                ],
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            item_id = AttendanceBatchItem.query.one().id

        entry_page = self.client.get(
            f"/attendance?month=2026-07&view=collection&item_id={item_id}&employee_id={employee_id}"
        ).get_data(as_text=True)
        self.assertIn("薪酬類別", entry_page)
        self.assertIn("填寫方式：非法定假日按真正實際出勤日數填寫", entry_page)
        self.assertIn("請選擇員工", entry_page)
        self.assertNotIn("文件名不作身份依據", entry_page)
        context_start = entry_page.index(
            '<section class="period-context-bar attendance-period-context'
        )
        context_end = entry_page.index("</section>", context_start)
        self.assertIn(
            'class="attendance-calendar-check"',
            entry_page[context_start:context_end],
        )
        self.assertNotIn(
            '<section class="attendance-calendar-check"',
            entry_page,
        )
        self.assertIn("非法定假日實際出勤日數（含星期日）", entry_page)
        self.assertIn("法定假日實際工作日數", entry_page)
        self.assertIn("法定假日預估工作日數", entry_page)
        self.assertIn('data-special-work-picker', entry_page)
        self.assertNotIn('data-special-work-session', entry_page)
        self.assertNotIn('class="icon-btn remove-segment"', entry_page)
        self.assertNotIn("休息日實際工作日期", entry_page)
        self.assertIn("指定法定假日實際工作日期", entry_page)
        self.assertNotIn("特殊日統一處理方式", entry_page)
        self.assertIn('class="attendance-period-table-head"', entry_page)
        self.assertIn('class="review-section attendance-period-row actual-period-row"', entry_page)
        self.assertIn("待按 PDF 核對的系統基準", entry_page)
        self.assertIn("目前未錄入額外考勤項目", entry_page)
        self.assertIn("ⓘ 計算規則", entry_page)
        self.assertNotIn("本次工資表核對", entry_page)
        self.assertRegex(
            entry_page,
            r'name="previous_21_end_forecast_working_days" value="8(?:\.0+)?"',
        )
        self.assertRegex(
            entry_page,
            r'name="previous_21_end_forecast_holiday_days" value="0"',
        )
        self.assertIn('disabled aria-disabled="true"', entry_page)
        self.assertIn("未找到 2026年6月考勤", entry_page)

        form = {
            "employee_id": str(employee_id),
            "special_day_handling": "comp_leave",
            "current_1_20_project_id": [str(project_id)],
            "current_1_20_working_days": ["16"],
            "current_1_20_ot_hours": ["0"],
            "current_1_20_holiday_days": ["2"],
            "current_1_20_special_work_entries": [json.dumps([
                {"date": "2026-07-05", "session": "full_day"},
                {"date": "2026-07-12", "session": "pm"},
            ])],
            "current_1_20_large_ecall_count": ["0"],
            "current_1_20_ecall_count": ["0"],
            "current_21_end_forecast_project_id": [str(project_id)],
            "current_21_end_forecast_working_days": ["6"],
            "current_21_end_forecast_holiday_days": ["1"],
            "current_21_end_forecast_special_work_entries": ["[]"],
        }
        invalid_form = dict(form)
        invalid_form["current_1_20_special_work_entries"] = [json.dumps([
            {"date": "2026-07-05", "session": "full_day"},
        ])]
        invalid_response = self.client.post(
            f"/attendance/items/{item_id}/save",
            data=invalid_form,
            follow_redirects=True,
        )
        self.assertIn(
            "日期數必須與出勤日數一致",
            invalid_response.get_data(as_text=True),
        )
        with self.app.app_context():
            self.assertEqual(AttendanceMonthlySummary.query.count(), 0)

        response = self.client.post(
            f"/attendance/items/{item_id}/save", data=form
        )
        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            credits = EmployeeCompLeaveCredit.query.order_by(
                EmployeeCompLeaveCredit.source_date
            ).all()
            self.assertEqual(len(credits), 2)
            self.assertTrue(all(item.status == "active" for item in credits))
            self.assertEqual(
                [item.source_date for item in credits],
                [date(2026, 7, 5), date(2026, 7, 12)],
            )
            self.assertEqual(
                [item.days for item in credits],
                [Decimal("1.0"), Decimal("1.0")],
            )
            special_days = AttendanceSpecialDay.query.order_by(
                AttendanceSpecialDay.work_date
            ).all()
            self.assertEqual(
                [item.session for item in special_days],
                ["full_day", "full_day"],
            )

        response = self.client.post(
            "/attendance/batches",
            data={
                "year_month": "2026-08",
                "files": [
                    (
                        io.BytesIO(pdf_bytes("august-attendance")),
                        "august-attendance.pdf",
                    )
                ],
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            august_item_id = AttendanceBatchItem.query.filter_by(
                original_filename="august-attendance.pdf"
            ).one().id
        august_page = self.client.get(
            f"/attendance?month=2026-08&view=collection&item_id={august_item_id}&employee_id={employee_id}"
        ).get_data(as_text=True)
        self.assertRegex(
            august_page,
            r'name="previous_21_end_forecast_working_days" value="6(?:\.00)?"',
        )
        self.assertRegex(
            august_page,
            r'name="previous_21_end_forecast_holiday_days" value="1(?:\.00)?"',
        )
        self.assertIn('target="_blank" rel="noopener"', august_page)
        self.assertIn("打開 2026年7月考勤表", august_page)
        self.assertNotIn("未找到 2026年7月考勤", august_page)

        form["special_day_handling"] = "pay"
        form["confirm_duplicate"] = "1"
        response = self.client.post(
            f"/attendance/items/{item_id}/save", data=form
        )
        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            credits = EmployeeCompLeaveCredit.query.all()
            self.assertEqual(len(credits), 2)
            self.assertTrue(all(item.status == "voided" for item in credits))
            special_days = AttendanceSpecialDay.query.all()
            self.assertEqual(len(special_days), 2)
            self.assertTrue(all(item.handling == "pay" for item in special_days))

    def test_work_injury_allowance_and_effective_bank_routes(self):
        employee_id, _ = self.create_employee(
            "ASMTP", "site_monthly", "記錄路由測試", "RECORD ROUTES"
        )
        self.complete_employee(
            employee_id,
            "site_monthly",
            "TMC046",
            "monthly",
            "31000",
            "ROUTES-01",
            "61119991",
        )
        general_upload = self.client.get(
            f"/employees/{employee_id}/documents/new"
        ).get_data(as_text=True)
        self.assertIn('value="staff_record"', general_upload)
        self.assertIn('value="three_treasures"', general_upload)
        self.assertIn('value="cv"', general_upload)
        self.assertIn('value="other"', general_upload)
        self.assertIn('value="signed_contract"', general_upload)
        self.assertIn('value="bank_record"', general_upload)
        specialist = self.client.get(
            f"/employees/{employee_id}/documents/new?upload_type=bank_record",
            follow_redirects=False,
        )
        self.assertEqual(specialist.status_code, 302)
        self.assertIn("tab=personal", specialist.headers["Location"])
        other_upload = self.client.get(
            f"/employees/{employee_id}/documents/new?upload_type=other"
        ).get_data(as_text=True)
        self.assertIn('name="general_document_type_id"', other_upload)
        with self.app.app_context():
            general_type = ReferenceValue.query.join(ReferenceList).filter(
                ReferenceList.code == "general_document_type",
                ReferenceValue.code == "GENERAL_OTHER",
            ).one()
            general_type_id = general_type.id
        response = self.client.post(
            f"/employees/{employee_id}/documents/new",
            data={
                "category": "other",
                "general_document_type_id": str(general_type_id),
                "title": "一般測試附件",
                "file": (
                    io.BytesIO(pdf_bytes("general attachment")),
                    "general-attachment.pdf",
                ),
            },
            content_type="multipart/form-data",
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            general_document = EmployeeDocument.query.filter_by(
                employee_id=employee_id,
                category="other",
            ).one()
            self.assertEqual(
                general_document.general_document_type_id,
                general_type_id,
            )
        response = self.client.post(
            f"/employees/{employee_id}/documents/new",
            data={
                "category": "change_evidence",
                "file": (
                    io.BytesIO(pdf_bytes("orphan evidence")),
                    "orphan-evidence.pdf",
                ),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 400)
        response = self.client.post(
            f"/employees/{employee_id}/work-injuries",
            data={
                "accident_date": "2026-07-01",
                "payroll_start_date": "2026-07-01",
                "payroll_end_date": "2026-07-31",
                "confirmed_monthly_earnings": "31000",
                "incapacity_monthly_earnings": "0",
                "currency": "HKD",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        response = self.client.post(
            f"/employees/{employee_id}/allowances",
            data={
                "allowance_type": "meal",
                "effective_from": "2026-07-01",
                "amount": "500",
                "currency": "HKD",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        response = self.client.post(
            f"/employees/{employee_id}/bank-accounts",
            data={
                "effective_from": "2026-08-01",
                "bank_name": "NEW BANK",
                "account_no": "99887766",
                "currency": "HKD",
                "evidence": (
                    io.BytesIO(pdf_bytes("bank evidence")),
                    "bank-evidence.pdf",
                ),
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("NEW BANK", response.get_data(as_text=True))
        with self.app.app_context():
            self.assertEqual(
                EmployeeWorkInjuryPeriod.query.filter_by(employee_id=employee_id).count(),
                1,
            )
            self.assertEqual(
                EmployeeAllowance.query.filter_by(employee_id=employee_id).count(),
                1,
            )
            bank = EmployeeBankAccount.query.filter_by(
                employee_id=employee_id,
                bank_name="NEW BANK",
            ).one()
            bank_id = bank.id
            bank_document_id = bank.evidence_document_id
        profile = self.client.get(
            f"/employees/{employee_id}?tab=documents&lang=en"
        ).get_data(as_text=True)
        self.assertIn("bank-evidence.pdf", profile)
        self.assertIn("Manage in module", profile)
        self.assertIn(
            f'/employees/{employee_id}?tab=personal',
            profile,
        )
        self.assertNotIn(
            f'data-dialog-open="document-replace-{bank_document_id}"',
            profile,
        )
        response = self.client.post(
            f"/bank-accounts/{bank_id}/correct",
            data={
                "effective_from": "2026-08-01",
                "bank_name": "CORRECT BANK",
                "account_no": "88776655",
                "currency": "HKD",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("CORRECT BANK", response.get_data(as_text=True))
        response = self.client.post(
            f"/bank-accounts/{bank_id}/withdraw",
            data={"reason": "wrong account"},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            bank = db.session.get(EmployeeBankAccount, bank_id)
            employee = db.session.get(Employee, employee_id)
            self.assertEqual(bank.status, "voided")
            self.assertEqual(
                employee.bank_name,
                "BANK OF CHINA (HONG KONG) LIMITED",
            )
            self.assertTrue(
                AuditLog.query.filter_by(
                    entity_type="EmployeeBankAccount",
                    entity_id=bank_id,
                ).count() >= 3
            )


if __name__ == "__main__":
    unittest.main()
