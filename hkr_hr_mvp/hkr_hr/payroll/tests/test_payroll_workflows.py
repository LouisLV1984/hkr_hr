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


class PayrollWorkflowTests(HrAppTestCase):
    def test_complete_employee_document_attendance_payroll_flow(self):
        monthly_id, monthly_no = self.create_employee(
            "HKR",
            "site_monthly",
            "驗收月工",
            "QA MONTHLY",
        )
        daily_id, daily_no = self.create_employee(
            "HKRD",
            "site_daily",
            "驗收日工",
            "QA DAILY",
        )
        management_id, management_no = self.create_employee(
            "ASMTP",
            "management",
            "驗收管理",
            "QA MANAGEMENT",
        )
        monthly_project = self.complete_employee(
            monthly_id,
            "site_monthly",
            "TMC046",
            "monthly",
            "30000",
            "QA100001",
            "60000001",
        )
        daily_project = self.complete_employee(
            daily_id,
            "site_daily",
            "TMC046",
            "daily",
            "1600",
            "QA100002",
            "60000002",
            mpf_mode="casual",
        )
        management_project = self.complete_employee(
            management_id,
            "management",
            "UNASSIGNED",
            "monthly",
            "36000",
            "QA100003",
            "60000003",
        )

        staff_document_id = self.upload_document(
            monthly_id,
            "staff_record",
            "qa-staff-record.pdf",
        )
        response = self.client.post(
            f"/documents/{staff_document_id}/review",
            data={
                "title": "QA Staff Record",
                "email": "updated.monthly@example.test",
                "mobile_region_code": "+852",
                "mobile_number": "68810001",
                "start_date": "2026-01-01",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        for employee_id, suffix in (
            (monthly_id, "monthly"),
            (daily_id, "daily"),
            (management_id, "management"),
        ):
            self.upload_document(
                employee_id,
                "signed_contract",
                f"qa-{suffix}-signed-contract.pdf",
            )
            self.upload_document(
                employee_id,
                "bank_proof",
                f"qa-{suffix}-bank-proof.pdf",
            )

        self.add_attendance(
            [
                (monthly_id, monthly_project),
                (daily_id, daily_project),
                (management_id, management_project),
            ]
        )

        with self.app.app_context():
            self.assertEqual(
                AttendanceMonthlySummary.query.filter_by(
                    year_month="2026-07",
                    status="received",
                ).count(),
                3,
            )
            for summary in AttendanceMonthlySummary.query.filter_by(
                year_month="2026-07",
                status="received",
            ):
                self.assertEqual(
                    {
                        segment.period_kind
                        for segment in AttendanceSegment.query.filter_by(
                            summary_id=summary.id
                        )
                    },
                    {
                        "current_1_20",
                        "current_21_end_forecast",
                        "previous_21_end",
                        "previous_21_end_forecast",
                    },
                )
            rows = calculate_payroll("2026-07", "all")
            self.assertEqual(len(rows), 3)
            self.assertFalse(any(row["blockers"] for row in rows))
            daily = next(row for row in rows if row["group"] == "site_daily")
            self.assertTrue(
                any(line["ot_divisor"] == 10 for line in daily["lines"])
            )
            self.assertEqual(
                daily["large_ecall_amount"],
                Decimal("3200.00"),
            )
            self.assertEqual(daily["ecall_amount"], Decimal("1200.00"))
            self.assertEqual(
                daily["actual_previous_tail"],
                Decimal("18240.00"),
            )
            daily_forecast_days = sum(
                line["forecast_working_days"] + line["forecast_holiday_days"]
                for line in daily["lines"]
            )
            self.assertEqual(daily_forecast_days, 10)
            self.assertTrue(
                all(
                    line["forecast_holiday_days"] == 0
                    for line in daily["lines"]
                )
            )

        response = self.client.post(
            "/payroll/preview",
            data={"year_month": "2026-07", "payroll_group": "all"},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            run = PayrollRun.query.order_by(PayrollRun.id.desc()).first()
            self.assertIsNotNone(run)
            run_id = run.id
            self.assertEqual(len(run.employee_results), 3)
            expected_payroll = {
                result.employee.employee_no: {
                    "group": (result.calculation_json or {}).get("group"),
                    "overpay": float(result.overpay_amount),
                    "underpay": float(result.underpay_amount),
                    "employee_mpf": float(result.employee_mpf),
                    "net": float(result.net_amount),
                    "ecall": float(
                        result.large_ecall_amount + result.ecall_amount
                    ),
                    "attendance_remarks": (
                        result.calculation_json or {}
                    ).get("attendance_remarks"),
                }
                for result in run.employee_results
            }
            self.assertEqual(
                expected_payroll[monthly_no]["attendance_remarks"],
                "考勤核對備註 1",
            )
        monthly_attendance_page = self.client.get(
            f"/employees/{monthly_id}?tab=attendance&lang=zh-Hant"
        ).get_data(as_text=True)
        self.assertIn("考勤備註", monthly_attendance_page)
        self.assertIn("考勤核對備註 1", monthly_attendance_page)
        response = self.client.get(
            f"/payroll/runs/{run_id}/export?payroll_group=all"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "application/zip")
        with zipfile.ZipFile(io.BytesIO(response.data)) as archive:
            names = sorted(archive.namelist())
            self.assertEqual(len(names), 3)
            sheets = set()
            employee_numbers = set()
            for name in names:
                workbook = load_workbook(
                    io.BytesIO(archive.read(name)),
                    data_only=False,
                )
                self.assertEqual(len(workbook.sheetnames), 1)
                self.assertEqual(workbook.calculation.calcMode, "auto")
                self.assertTrue(workbook.calculation.fullCalcOnLoad)
                self.assertTrue(workbook.calculation.forceFullCalc)
                sheets.add(workbook.sheetnames[0])
                sheet = workbook.active
                self.assertEqual(sheet["F4"].value, "2026-07")
                self.assertEqual(sheet["F4"].number_format, "@")
                self.assertEqual(
                    sheet["M4"].value if sheet.title == "日工" else sheet["N4"].value,
                    "01/07/2026 - 20/07/2026",
                )
                employee_numbers.update(
                    sheet.cell(row, 5).value
                    for row in range(7, sheet.max_row + 1)
                    if sheet.cell(row, 5).value
                )
                for row in range(7, sheet.max_row + 1):
                    employee_no = sheet.cell(row, 5).value
                    if employee_no not in expected_payroll:
                        continue
                    expected = expected_payroll[employee_no]
                    if sheet.title == "日工":
                        columns = {
                            "ecall": 19,
                            "overpay": 31,
                            "underpay": 32,
                            "employee_mpf": 36,
                            "employer_mpf": 37,
                            "total": 35,
                            "net": 42,
                        }
                        formula_columns = (12, 15, 18, 19, 22, 25, 26, 30, 35, 36, 37, 42)
                    else:
                        columns = {
                            "ecall": 20,
                            "overpay": 32,
                            "underpay": 33,
                            "employee_mpf": 37,
                            "employer_mpf": 38,
                            "total": 36,
                            "net": 43,
                        }
                        formula_columns = (13, 16, 19, 20, 23, 26, 27, 31, 36, 37, 38, 43)
                    for key in ("overpay", "underpay"):
                        column = columns[key]
                        self.assertAlmostEqual(
                            float(sheet.cell(row, column).value or 0),
                            expected[key],
                            places=2,
                        )
                    for column in formula_columns:
                        self.assertTrue(
                            str(sheet.cell(row, column).value).startswith("="),
                            f"{sheet.title}!{sheet.cell(row, column).coordinate}",
                        )
                    self.assertIn(
                        "400",
                        str(sheet.cell(row, columns["ecall"]).value),
                    )
                    self.assertIn(
                        "SUMIF",
                        str(sheet.cell(row, columns["employee_mpf"]).value),
                    )
                    total_formula = str(
                        sheet.cell(row, columns["total"]).value
                    )
                    if sheet.title == "日工":
                        self.assertEqual(
                            total_formula,
                            (
                                f"=ROUND(L{row}+O{row}+R{row}+S{row}"
                                f"+V{row}+Y{row}+Z{row}+AA{row}+AD{row}"
                                f"-AE{row}+AF{row}+AG{row}+AL{row},2)"
                            ),
                        )
                    else:
                        self.assertEqual(
                            total_formula,
                            (
                                f"=ROUND(M{row}+P{row}+S{row}+T{row}"
                                f"+W{row}+Z{row}+AA{row}+AB{row}+AE{row}"
                                f"-AF{row}+AG{row}+AH{row}+AM{row},2)"
                            ),
                        )
                    if expected["group"] == "site_daily":
                        self.assertIn(
                            "/10*1.5",
                            str(sheet.cell(row, 14).value),
                        )
                        daily_mpf_formula = str(
                            sheet.cell(row, columns["employee_mpf"]).value
                        )
                        self.assertIn("<280", daily_mpf_formula)
                        self.assertIn("<950", daily_mpf_formula)
                        self.assertIn("50", daily_mpf_formula)
                    ecall_header_column = (
                        19 if sheet.title == "日工" else 20
                    )
                    self.assertEqual(
                        sheet.cell(5, ecall_header_column).value,
                        "E-CALL",
                    )
                    self.assertIn(
                        "大 E-CALL",
                        sheet.cell(
                            row,
                            43 if sheet.title == "日工" else 44,
                        ).value,
                    )
                    if expected["attendance_remarks"]:
                        self.assertIn(
                            f"考勤備註：{expected['attendance_remarks']}",
                            sheet.cell(
                                row,
                                43 if sheet.title == "日工" else 44,
                            ).value,
                        )
            self.assertEqual(sheets, {"月工", "OFFICE", "日工"})
            self.assertTrue(
                {monthly_no, daily_no, management_no}.issubset(
                    employee_numbers
                )
            )

        attendance_export = self.client.get(
            "/export/attendance-summary?year_month=2026-07"
        )
        self.assertEqual(attendance_export.status_code, 200)
        attendance_book = load_workbook(io.BytesIO(attendance_export.data))
        attendance_sheet = attendance_book.active
        attendance_headers = [
            cell.value for cell in attendance_sheet[1]
        ]
        self.assertIn("大 E-CALL 次數", attendance_headers)
        self.assertIn("普通 E-CALL 次數", attendance_headers)
        daily_current = next(
            row
            for row in attendance_sheet.iter_rows(
                min_row=2,
                values_only=True,
            )
            if row[1] == daily_no and row[3] == "current_1_20"
        )
        self.assertEqual(daily_current[8:10], (2, 3))

        payroll_summary = self.client.get(
            f"/export/payroll-summary?run_id={run_id}"
        )
        self.assertEqual(payroll_summary.status_code, 200)
        payroll_book = load_workbook(io.BytesIO(payroll_summary.data))
        payroll_sheet = payroll_book.active
        payroll_headers = [cell.value for cell in payroll_sheet[1]]
        self.assertIn("大 E-CALL", payroll_headers)
        self.assertIn("普通 E-CALL", payroll_headers)
        daily_summary = next(
            row
            for row in payroll_sheet.iter_rows(
                min_row=2,
                values_only=True,
            )
            if row[2] == daily_no
        )
        self.assertAlmostEqual(float(daily_summary[8]), 3200.0, places=2)
        self.assertAlmostEqual(float(daily_summary[9]), 1200.0, places=2)

        salary_certificate = self.client.get(
            "/export/salary-certificate"
            f"?employee_id={monthly_id}"
            "&year_month=2026-07"
            "&issue_date=2026-07-31"
        )
        self.assertEqual(salary_certificate.status_code, 200)
        self.assertEqual(
            salary_certificate.mimetype,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        certificate_book = load_workbook(
            io.BytesIO(salary_certificate.data),
            data_only=False,
        )
        certificate_sheet = certificate_book.active
        self.assertIn(
            "Employee Salary Certificate",
            certificate_sheet["A6"].value,
        )
        self.assertEqual(certificate_sheet["B9"].value, "QA MONTHLY")
        self.assertTrue(
            str(certificate_sheet["J9"].value).startswith("=")
        )
        self.assertIn(
            "31 July 2026",
            certificate_sheet["H19"].value,
        )

        with self.app.app_context():
            period = db.session.get(Employee, monthly_id).current_period
            signed_notice = (period.notice_period_value, period.notice_period_unit)
        response = self.client.post(
            f"/employees/{monthly_id}/contracts/generate",
            data={
                "template_code": "SITE",
                "contract_date": "2026-07-01",
                "effective_date": "2026-07-01",
                "annual_leave_days": "10",
                "notice_period_days": "7",
                "probation_months": "0",
            },
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)
        contract_response = self.client.get(response.headers["Location"])
        self.assertEqual(contract_response.status_code, 200)
        with zipfile.ZipFile(io.BytesIO(contract_response.data)) as archive:
            self.assertIn("README.txt", archive.namelist())
            docx_name = next(
                name for name in archive.namelist() if name.endswith(".docx")
            )
            with zipfile.ZipFile(
                io.BytesIO(archive.read(docx_name))
            ) as document:
                xml = document.read("word/document.xml").decode("utf-8")
                self.assertIn("驗收月工", xml)
                self.assertIn("享有10天", xml)
                self.assertIn("提前7天", xml)
                self.assertNotIn("{{ notice_period_text }}", xml)
        with self.app.app_context():
            self.assertEqual(GeneratedContract.query.count(), 1)
            contract = GeneratedContract.query.one()
            self.assertEqual(float(contract.annual_leave_days), 10.0)
            employee = db.session.get(Employee, monthly_id)
            self.assertEqual((employee.current_period.notice_period_value, employee.current_period.notice_period_unit), signed_notice)
        for template_name, annual_count, notice_count in (
            ("HKR_SITE_Employment_Contract_Template.docx", 1, 2),
            ("HKR_OFFICE_Employment_Contract_Template.docx", 1, 1),
        ):
            with zipfile.ZipFile(APP_ROOT / "contract_templates" / template_name) as template_zip:
                template_xml = template_zip.read(
                    "word/document.xml"
                ).decode("utf-8")
            self.assertEqual(
                template_xml.count("contract_annual_leave_text"),
                annual_count,
            )
            self.assertEqual(
                template_xml.count("notice_period_text"),
                notice_count,
            )

        employee_export = self.client.get("/export/employees")
        self.assertEqual(employee_export.status_code, 200)
        workbook = load_workbook(io.BytesIO(employee_export.data))
        self.assertEqual(
            workbook.sheetnames,
            [
                "員工資料總表",
                "證件及資歷",
                "任職及薪酬歷史",
                "附件索引",
            ],
        )
        exported_numbers = {
            workbook.active.cell(row, 1).value
            for row in range(2, workbook.active.max_row + 1)
        }
        self.assertTrue(
            {monthly_no, daily_no, management_no}.issubset(exported_numbers)
        )
        attachment_bundle = self.client.get(
            f"/employees/{monthly_id}/documents/bundle"
        )
        self.assertEqual(attachment_bundle.status_code, 200)
        with zipfile.ZipFile(io.BytesIO(attachment_bundle.data)) as archive:
            self.assertGreaterEqual(len(archive.namelist()), 3)

        attendance_bundle = self.client.get(
            "/export/attachments"
            "?bundle_group=attendance&year_month=2026-07"
        )
        self.assertEqual(attendance_bundle.status_code, 200)
        with zipfile.ZipFile(io.BytesIO(attendance_bundle.data)) as archive:
            attendance_names = archive.namelist()
            self.assertEqual(len(attendance_names), 3)
            self.assertTrue(
                all("/attendance_pdf/" in name for name in attendance_names)
            )

        report_payroll = self.client.get(
            "/export/monthly-payroll"
            "?year_month=2026-07&payroll_group=all",
            follow_redirects=True,
        )
        self.assertEqual(report_payroll.status_code, 200)
        self.assertEqual(report_payroll.request.path, "/attendance-payroll")
        self.assertEqual(report_payroll.mimetype, "text/html")

        delete_id, delete_no = self.create_employee(
            "TE",
            "site_daily",
            "只供刪除測試",
            "DELETE ME",
        )
        response = self.client.post(
            f"/employees/{delete_id}/delete",
            data={"confirm_employee_no": delete_no},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            self.assertIsNone(db.session.get(Employee, delete_id))
            self.assertEqual(Employee.query.count(), 3)

    def test_empty_project_lines_never_create_mpf_only_payroll_rows(self):
        employee_id, _ = self.create_employee(
            "HKR",
            "management",
            "MPF 分行測試",
            "MPF LINE TEST",
        )
        project_id = self.complete_employee(
            employee_id,
            "management",
            "TMC046",
            "monthly",
            "60000",
            "QA-MPF-LINE",
            "61110105",
        )
        with self.app.app_context():
            summary = AttendanceMonthlySummary(
                employee_id=employee_id,
                year_month="2026-08",
                status="received",
            )
            db.session.add(summary)
            db.session.flush()
            for period_kind in (
                "current_1_20",
                "current_21_end_forecast",
                "previous_21_end",
                "previous_21_end_forecast",
            ):
                db.session.add(
                    AttendanceSegment(
                        summary_id=summary.id,
                        period_kind=period_kind,
                        project_id=None,
                    )
                )
            db.session.commit()
            row = calculate_payroll("2026-08", "management")[0]
            self.assertEqual(row["employee_mpf"], Decimal("1500.00"))
            self.assertEqual(len(row["lines"]), 1)
            self.assertEqual(row["lines"][0]["project"].id, project_id)
            self.assertEqual(row["lines"][0]["base_amount"], Decimal("60000.00"))

            legacy_result = PayrollEmployeeResult(
                calculation_json={
                    "lines": [
                        {
                            "project": None,
                            "working_days": "31",
                            "holiday_days": "5",
                            "base_amount": "0",
                            "gross_amount": "0",
                        },
                        {
                            "project": project_id,
                            "working_days": "31",
                            "base_amount": "60000",
                            "gross_amount": "60000",
                        },
                    ]
                }
            )
            exported_lines = result_lines(legacy_result)
            self.assertEqual(len(exported_lines), 1)
            self.assertEqual(exported_lines[0]["project"], project_id)

    def test_v009_effective_status_leave_documents_and_mpf_scale(self):
        employee_id, employee_no = self.create_employee(
            "HKRD",
            "site_daily",
            "V009 驗收工人",
            "V009 ACCEPTANCE",
        )
        self.complete_employee(
            employee_id,
            "site_daily",
            "TMC046",
            "daily",
            "500",
            "V0090001",
            "61110001",
            mpf_mode="casual",
        )
        with self.app.app_context():
            employee = db.session.get(Employee, employee_id)
            employee.current_period.notice_period_value = Decimal("7")
            employee.current_period.notice_period_unit = "day"
            db.session.commit()

        response = self.client.post(
            f"/employees/{employee_id}/terminate",
            data={
                "end_date": "2099-08-30",
                "reason": "company_termination",
                "average_wage": "30,000.00",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            employee = db.session.get(Employee, employee_id)
            self.assertEqual(employee.derived_status, "active")
            self.assertEqual(employee.status, "active")
            self.assertEqual(
                employee.scheduled_departure_date,
                date(2099, 8, 30),
            )
            self.assertGreater(
                employee.current_period.payment_in_lieu,
                Decimal("0"),
            )
        attendance_page = self.client.get(
            "/attendance?month=2099-08&view=details&status=missing"
        ).get_data(as_text=True)
        self.assertIn(employee_no, attendance_page)

        response = self.client.post(
            f"/employees/{employee_id}/termination/cancel",
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            employee = db.session.get(Employee, employee_id)
            self.assertIsNone(employee.current_period.end_date)
            self.assertEqual(employee.derived_status, "active")

        self.assertEqual(
            annual_leave_days_between(
                date(2026, 8, 1),
                date(2026, 8, 2),
                "pm",
                "am",
            ),
            Decimal("1.0"),
        )
        response = self.client.post(
            f"/employees/{employee_id}/annual-leave",
            data={
                "start_date": "2026-08-01",
                "start_session": "pm",
                "end_date": "2026-08-02",
                "end_session": "am",
                "entitlement_year": "2026",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            leave = EmployeeAnnualLeaveRecord.query.one()
            leave_id = leave.id
            # Employee-aware leave excludes Sunday; Saturday PM on a 6-day
            # contract is half a day. The date-only helper above is unchanged.
            self.assertEqual(leave.days, Decimal("0.5"))
            self.assertEqual(leave.status, "active")

        response = self.client.post(
            f"/annual-leave/{leave_id}/update",
            data={
                "start_date": "2026-08-03",
                "start_session": "pm",
                "end_date": "2026-08-03",
                "end_session": "pm",
                "entitlement_year": "2026",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            self.assertEqual(
                db.session.get(EmployeeAnnualLeaveRecord, leave_id).days,
                Decimal("0.5"),
            )

        response = self.client.post(
            f"/annual-leave/{leave_id}/void",
            data={"reason": "驗收撤回"},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            self.assertEqual(
                db.session.get(EmployeeAnnualLeaveRecord, leave_id).status,
                "voided",
            )

        old_document_id = self.upload_document(
            employee_id,
            "identity",
            "v009-old-identity.pdf",
        )
        with self.app.app_context():
            employee = db.session.get(Employee, employee_id)
            employee.primary_identity.document_id = old_document_id
            db.session.commit()
        replacement = self.client.post(
            f"/documents/{old_document_id}/replace",
            data={
                "reason": "舊文件錯誤",
                "file": (
                    io.BytesIO(pdf_bytes("v009-replacement")),
                    "v009-new-identity.pdf",
                ),
            },
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        self.assertEqual(replacement.status_code, 200)
        with self.app.app_context():
            old_document = db.session.get(
                EmployeeDocument,
                old_document_id,
            )
            employee = db.session.get(Employee, employee_id)
            self.assertEqual(old_document.status, "replaced")
            self.assertIsNotNone(old_document.replaced_by_document_id)
            self.assertEqual(
                employee.primary_identity.document_id,
                old_document.replaced_by_document_id,
            )
            self.assertEqual(
                employee.primary_identity.document.status,
                "active",
            )

        expected_scale = (
            ("279.99", "0", "10"),
            ("280", "15", "15"),
            ("349.99", "15", "15"),
            ("350", "20", "20"),
            ("449.99", "20", "20"),
            ("450", "25", "25"),
            ("549.99", "25", "25"),
            ("550", "30", "30"),
            ("649.99", "30", "30"),
            ("650", "35", "35"),
            ("749.99", "35", "35"),
            ("750", "40", "40"),
            ("849.99", "40", "40"),
            ("850", "45", "45"),
            ("949.99", "45", "45"),
            ("950", "50", "50"),
            ("1200", "50", "50"),
        )
        for income, employee_mpf, employer_mpf in expected_scale:
            self.assertEqual(
                casual_daily_mpf(Decimal(income)),
                (Decimal(employee_mpf), Decimal(employer_mpf)),
            )

    def test_live_four_part_payroll_and_daily_mpf(self):
        employee_id, employee_no = self.create_employee(
            "HKRD",
            "site_daily",
            "四段計算測試",
            "FOUR PART TEST",
        )
        project_id = self.complete_employee(
            employee_id,
            "site_daily",
            "TMC046",
            "daily",
            "500",
            "FP100001",
            "62220001",
            mpf_mode="casual",
        )
        with self.app.app_context():
            summary = AttendanceMonthlySummary(
                employee_id=employee_id,
                year_month="2026-07",
                status="received",
            )
            db.session.add(summary)
            db.session.flush()
            for kind, days in (
                ("current_1_20", "10"),
                ("current_21_end_forecast", "5"),
                ("previous_21_end", "4"),
                ("previous_21_end_forecast", "6"),
            ):
                db.session.add(
                    AttendanceSegment(
                        summary_id=summary.id,
                        period_kind=kind,
                        project_id=project_id,
                        working_days=Decimal(days),
                    )
                )
            db.session.commit()
            row = calculate_payroll("2026-07", "site_daily")[0]
            self.assertEqual(row["employee"].employee_no, employee_no)
            self.assertEqual(row["current_actual_total"], Decimal("5500.00"))
            self.assertEqual(row["forecast_tail_total"], Decimal("2500.00"))
            self.assertEqual(row["actual_previous_tail"], Decimal("2000.00"))
            self.assertEqual(row["expected_previous_tail"], Decimal("3000.00"))
            self.assertEqual(row["gross_amount"], Decimal("7000.00"))
            self.assertEqual(row["overpay_amount"], Decimal("1000.00"))
            self.assertEqual(row["underpay_amount"], Decimal("0.00"))
            self.assertEqual(row["employee_mpf"], Decimal("350.00"))
            self.assertEqual(row["employer_mpf"], Decimal("350.00"))

        dashboard = self.client.get(
            "/dashboard?month=2026-07"
        ).get_data(as_text=True)
        self.assertIn("HKD 6,650.00", dashboard)

        page = self.client.get(
            "/attendance-payroll"
            "?year_month=2026-07&payroll_group=site_daily"
        ).get_data(as_text=True)
        self.assertIn("data-payroll-filter", page)
        self.assertIn("2026年7月1–20日（實際）", page)
        self.assertIn("2026年6月21–30日（原預估）", page)
        self.assertIn(
            'href="/attendance?month=2026-07"',
            page,
        )
        self.assertIn(
            'href="/mpf-contributions?year_month=2026-07"',
            page,
        )
        self.assertIn("請先選擇發薪單位", page)
        self.assertIn("/payroll/export-current", page)
        self.assertNotIn("確認並保存本次計算", page)
        self.assertNotIn("計算預覽", page)

        response = self.client.post(
            "/payroll/export-current",
            data={
                "year_month": "2026-07",
                "payroll_group": "site_daily",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.mimetype,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        with self.app.app_context():
            run = PayrollRun.query.one()
            result = PayrollEmployeeResult.query.one()
            self.assertEqual(run.year_month, "2026-07")
            self.assertEqual(result.employee_id, employee_id)
            self.assertEqual(result.gross_amount, Decimal("7000.00"))

    def test_mpf_effective_records_preview_and_exports(self):
        with self.app.app_context():
            schemes = {
                item.code: item for item in MpfScheme.query.order_by(MpfScheme.code)
            }
            self.assertEqual(
                set(schemes),
                {
                    "BCT_SERIES_800",
                    "BCOM_MONTHLY",
                    "BCT_MONTHLY",
                    "BCT_DAILY",
                },
            )
            self.assertIsNone(schemes["BCT_SERIES_800"].payroll_group_no)
            self.assertEqual(schemes["BCT_DAILY"].calculation_mode, "casual")

        monthly_id, monthly_no = self.create_employee(
            "ASMTP",
            "management",
            "MPF 月工驗收",
            "MPF MONTHLY QA",
        )
        monthly_project = self.complete_employee(
            monthly_id,
            "management",
            "TMC046",
            "monthly",
            "30000",
            "M1234567",
            "63330001",
        )
        daily_id, daily_no = self.create_employee(
            "HKRD",
            "site_daily",
            "MPF 日工驗收",
            "MPF DAILY QA",
        )
        daily_project = self.complete_employee(
            daily_id,
            "site_daily",
            "TMC046",
            "daily",
            "500",
            "D7654321",
            "63330002",
            mpf_mode="casual",
        )
        with self.app.app_context():
            new_scheme = MpfScheme.query.filter_by(code="BCT_MONTHLY").one()
            new_scheme_id = new_scheme.id
        response = self.client.post(
            f"/employees/{monthly_id}/mpf",
            data={
                "effective_from": "2026-05-01",
                "mpf_selection": str(new_scheme_id),
                "member_account_no": "MONTHLY-NEW-001",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("MPF 記錄已保存", response.get_data(as_text=True))

        with self.app.app_context():
            monthly = db.session.get(Employee, monthly_id)
            active_records = [
                item for item in monthly.mpf_enrollments if item.status == "active"
            ]
            self.assertEqual(len(active_records), 2)
            old_record = next(
                item for item in active_records if item.scheme.code == "BCOM_MONTHLY"
            )
            new_record = next(
                item for item in active_records if item.scheme.code == "BCT_MONTHLY"
            )
            self.assertEqual(old_record.effective_to, date(2026, 4, 30))
            self.assertIsNone(new_record.effective_to)
            new_record_id = new_record.id
            for employee_id, project_id in (
                (monthly_id, monthly_project),
                (daily_id, daily_project),
            ):
                summary = AttendanceMonthlySummary(
                    employee_id=employee_id,
                    year_month="2026-08",
                    status="received",
                )
                db.session.add(summary)
                db.session.flush()
                db.session.add_all(
                    [
                        AttendanceSegment(
                            summary_id=summary.id,
                            period_kind="current_1_20",
                            project_id=project_id,
                            working_days=Decimal("18"),
                        ),
                        AttendanceSegment(
                            summary_id=summary.id,
                            period_kind="current_21_end_forecast",
                            project_id=project_id,
                            working_days=Decimal("8"),
                        ),
                    ]
                )
            db.session.commit()

        profile = self.client.get(
            f"/employees/{monthly_id}?tab=employment"
        ).get_data(as_text=True)
        self.assertIn("當前薪酬及 MPF", profile)
        self.assertIn("變更歷史", profile)
        self.assertIn("銀聯（BCT）月工", profile)
        self.assertIn("MONTHLY-NEW-001", profile)

        page = self.client.get(
            "/mpf-contributions?year_month=2026-08"
        ).get_data(as_text=True)
        self.assertIn("MPF 供款表", page)
        self.assertIn(monthly_no, page)
        self.assertIn(daily_no, page)
        self.assertIn("下載全部 MPF ZIP", page)

        single = self.client.post(
            "/mpf-contributions/export",
            data={"year_month": "2026-08", "scheme_code": "BCT_MONTHLY"},
        )
        self.assertEqual(single.status_code, 200)
        self.assertIn(
            "application/vnd.openxmlformats-officedocument",
            single.content_type,
        )
        workbook = load_workbook(io.BytesIO(single.data), data_only=False)
        sheet = workbook["BILL_Submitted Employee(s)"]
        self.assertEqual(
            sheet["B2"].value,
            "HONG KONG RIVER ENGINEERING COMPANY LIMITED",
        )
        self.assertEqual(str(sheet["H2"].value), "53419540")
        self.assertEqual(sheet["J2"].value, "MONTHLY (CALENDAR MONTH)")
        self.assertEqual(sheet["A8"].value, "MPF MONTHLY QA")
        self.assertEqual(sheet["C8"].value, "MONTHLY-NEW-001")
        self.assertEqual(sheet["E8"].value, "APPROVED")
        self.assertIsNone(sheet["I8"].value)
        self.assertGreater(Decimal(str(sheet["H8"].value)), Decimal("0"))
        self.assertEqual(
            Decimal(str(sheet["J8"].value)),
            Decimal(str(sheet["K8"].value))
            + Decimal(str(sheet["L8"].value)),
        )

        archive_response = self.client.post(
            "/mpf-contributions/export",
            data={"year_month": "2026-08", "scheme_code": "all"},
        )
        self.assertEqual(archive_response.status_code, 200)
        self.assertEqual(archive_response.content_type, "application/zip")
        with zipfile.ZipFile(io.BytesIO(archive_response.data)) as archive:
            self.assertEqual(
                set(archive.namelist()),
                {
                    "HKR_MPF_2026-08_BCT_DAILY.xlsx",
                    "HKR_MPF_2026-08_BCT_MONTHLY.xlsx",
                },
            )

        response = self.client.post(
            f"/mpf-enrollments/{new_record_id}/withdraw",
            data={"reason": "驗收撤回"},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            monthly = db.session.get(Employee, monthly_id)
            active = [
                item for item in monthly.mpf_enrollments if item.status == "active"
            ]
            self.assertEqual(len(active), 1)
            self.assertEqual(active[0].scheme.code, "BCOM_MONTHLY")
            self.assertIsNone(active[0].effective_to)
            self.assertEqual(monthly.mpf_mode, "regular")

    def test_payroll_exports_ready_and_selected_employees_only(self):
        daily_id, daily_no = self.create_employee(
            "HKRD",
            "site_daily",
            "可出糧日工",
            "READY DAILY",
        )
        monthly_id, monthly_no = self.create_employee(
            "HKR",
            "site_monthly",
            "可出糧月工",
            "READY MONTHLY",
        )
        blocked_id, blocked_no = self.create_employee(
            "ASMTP",
            "management",
            "待補資料員工",
            "BLOCKED EMPLOYEE",
        )
        daily_project_id = self.complete_employee(
            daily_id,
            "site_daily",
            "TMC046",
            "daily",
            "500",
            "READY-D-01",
            "61110001",
            mpf_mode="casual",
        )
        monthly_project_id = self.complete_employee(
            monthly_id,
            "site_monthly",
            "TMC046",
            "monthly",
            "30000",
            "READY-M-01",
            "61110002",
        )
        with self.app.app_context():
            for employee_id, project_id in (
                (daily_id, daily_project_id),
                (monthly_id, monthly_project_id),
            ):
                summary = AttendanceMonthlySummary(
                    employee_id=employee_id,
                    year_month="2026-07",
                    status="received",
                )
                db.session.add(summary)
                db.session.flush()
                for kind, days in (
                    ("current_1_20", "15"),
                    ("current_21_end_forecast", "8"),
                    ("previous_21_end", "8"),
                    ("previous_21_end_forecast", "8"),
                ):
                    db.session.add(
                        AttendanceSegment(
                            summary_id=summary.id,
                            period_kind=kind,
                            project_id=project_id,
                            working_days=Decimal(days),
                        )
                    )
            db.session.commit()

        page = self.client.get(
            "/attendance-payroll?year_month=2026-07&payroll_group=all&status=all"
        ).get_data(as_text=True)
        self.assertIn("匯出全部可出糧員工（2 人）", page)
        self.assertIn("匯出此員工工資表", page)
        self.assertEqual(
            len(
                re.findall(
                    r"<input[^>]+data-payroll-employee-checkbox",
                    page,
                )
            ),
            2,
        )
        self.assertNotIn("payroll-person-preview", page)

        response = self.client.post(
            "/payroll/export-current",
            data={
                "year_month": "2026-07",
                "payroll_group": "all",
                "scope": "ready",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "application/zip")
        with self.app.app_context():
            run = PayrollRun.query.order_by(PayrollRun.id.desc()).first()
            self.assertEqual(
                {result.employee_id for result in run.employee_results},
                {daily_id, monthly_id},
            )

        response = self.client.post(
            "/payroll/export-current",
            data={
                "year_month": "2026-07",
                "payroll_group": "all",
                "scope": "selected",
                "employee_ids": [daily_id],
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.mimetype,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        with self.app.app_context():
            run = PayrollRun.query.order_by(PayrollRun.id.desc()).first()
            self.assertEqual(
                [result.employee_id for result in run.employee_results],
                [daily_id],
            )

        response = self.client.post(
            "/payroll/export-current",
            data={
                "year_month": "2026-07",
                "payroll_group": "all",
                "scope": "selected",
                "employee_ids": [daily_id, monthly_id],
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "application/zip")

        response = self.client.post(
            "/payroll/export-current",
            data={
                "year_month": "2026-07",
                "payroll_group": "all",
                "scope": "selected",
                "employee_ids": [blocked_id],
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(blocked_no, response.get_data(as_text=True))
        with self.app.app_context():
            latest = PayrollRun.query.order_by(PayrollRun.id.desc()).first()
            self.assertEqual(
                {result.employee_id for result in latest.employee_results},
                {daily_id, monthly_id},
            )
            self.assertNotIn(
                blocked_id,
                {result.employee_id for result in latest.employee_results},
            )
            self.assertEqual({daily_no, monthly_no}, {
                result.employee.employee_no
                for result in latest.employee_results
            })

    def test_final_payment_review_calculation_and_formula_export(self):
        employee_id, employee_no = self.create_employee(
            "ASMTP",
            "management",
            "離職結算測試",
            "FINAL PAYMENT TEST",
        )
        self.complete_employee(
            employee_id,
            "management",
            "TMC046",
            "monthly",
            "30000",
            "FINAL1001",
            "65550002",
        )
        with self.app.app_context():
            employee = db.session.get(Employee, employee_id)
            employee.current_period.start_date = date(2020, 1, 1)
            employee.current_period.contract_annual_leave_days = Decimal("10")
            assignment = employee.current_assignment
            payroll_entity_id = assignment.payroll_entity_id
            payroll_entity_code = assignment.payroll_entity.code
            summary = AttendanceMonthlySummary(
                employee_id=employee_id,
                year_month="2026-08",
                status="received",
                special_day_handling="pay",
            )
            db.session.add(summary)
            db.session.flush()
            db.session.add(
                AttendanceSegment(
                    summary=summary,
                    period_kind="current_1_20",
                    working_days=Decimal("14"),
                    ot_hours=Decimal("2"),
                    other_allowance_amount=Decimal("250"),
                )
            )
            injury = EmployeeWorkInjuryPeriod(
                employee_id=employee_id,
                accident_date=date(2026, 7, 1),
                payroll_start_date=date(2026, 7, 1),
                payroll_end_date=date(2026, 7, 31),
                confirmed_monthly_earnings=Decimal("30000"),
                incapacity_monthly_earnings=Decimal("0"),
                currency="HKD",
                status="active",
            )
            db.session.add(injury)
            db.session.flush()
            db.session.add_all(
                [
                    EmployeeAllowance(
                        employee_id=employee_id,
                        label="交通補貼",
                        allowance_type="transport",
                        currency="HKD",
                        amount=Decimal("60"),
                        effective_from=date(2026, 8, 1),
                        status="active",
                    ),
                    EmployeeAllowance(
                        employee_id=employee_id,
                        label="特殊津貼",
                        allowance_type="special",
                        currency="HKD",
                        amount=Decimal("310"),
                        effective_from=date(2026, 8, 1),
                        status="active",
                    ),
                    PayrollAdjustment(
                        employee_id=employee_id,
                        year_month="2026-08",
                        label="離職月補發",
                        amount=Decimal("300"),
                        status="active",
                    ),
                    EmployeeWorkInjuryMonthlyExpense(
                        employee_id=employee_id,
                        work_injury_period_id=injury.id,
                        year_month="2026-08",
                        amount=Decimal("400"),
                        currency="HKD",
                        status="active",
                    ),
                ]
            )
            db.session.commit()
        response = self.client.post(
            f"/employees/{employee_id}/terminate",
            data={
                "end_date": "2026-08-20",
                "reason": "company_termination",
                "average_wage": "30000",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            period = EmployeeEmploymentPeriod.query.filter_by(
                employee_id=employee_id
            ).one()
            period_id = period.id

        response = self.client.post(
            f"/final-payment/{period_id}/save",
            data={
                "year_month": "2026-08",
                "payroll_group": "management",
                "payroll_entity_id": str(payroll_entity_id),
                "actual_working_days": "14",
                "actual_ot_hours": "2",
                "actual_holiday_days": "0",
                "large_ecall_count": "0",
                "ecall_count": "0",
                "allowance_amount": "1000",
                "other_payment": "500",
                "overpay_amount": "0",
                "underpay_amount": "0",
                "legacy_leave_days": "3",
                "post_2024_leave_days": "2",
                "statutory_holiday_days": "1",
                "leave_average_wage": "30000",
                "leave_wage_total": "360000",
                "benefit_type": "long_service",
                "pre_basis_last": "18000",
                "pre_basis_average": "20000",
                "pre_basis_choice": "average",
                "post_basis_last": "30000",
                "post_basis_average": "28000",
                "post_basis_choice": "last",
                "mpf_offset_amount": "500",
                "special_compensation": "1000",
                "payment_in_lieu": "30000",
                "remarks": "HR 已核對測試資料",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        page = response.get_data(as_text=True)
        self.assertIn("離職結算資料已保存", page)
        self.assertIn("當前離職結算月份", page)
        self.assertIn("交通／餐補（自動）", page)
        self.assertIn("工傷醫療實銷（不計 MPF）", page)
        self.assertIn(employee_no, page)
        self.assertIn("2025-05-01", page)
        self.assertIn("勞工處規則摘要", page)
        self.assertIn("最後 30 個正常工作日", page)
        self.assertIn("不少於 24 個月", page)
        self.assertIn("前 12 個月工資合計 ÷ 365", page)
        self.assertIn("離職當月以 Final Payment 作唯一工資來源", page)
        with self.app.app_context():
            db.session.expire_all()
            period = db.session.get(EmployeeEmploymentPeriod, period_id)
            result = calculate_final_payment(period)
            expected_base_amount = result["base_amount"]
            expected_ot_amount = result["ot_amount"]
            expected_holiday_amount = result["holiday_amount"]
            expected_net_amount = result["net_amount"]
            self.assertFalse(result["blockers"])
            self.assertEqual(
                result["traffic_meal_allowance_amount"], Decimal("1200.00")
            )
            self.assertEqual(
                result["special_allowance_amount"], Decimal("200.00")
            )
            self.assertEqual(
                result["manual_allowance_amount"], Decimal("1000.00")
            )
            self.assertEqual(
                result["attendance_other_allowance_amount"], Decimal("250.00")
            )
            self.assertEqual(
                result["month_adjustment_amount"], Decimal("300.00")
            )
            self.assertEqual(
                result["manual_other_payment"], Decimal("500.00")
            )
            self.assertEqual(
                result["work_injury_medical_reimbursement_amount"],
                Decimal("400.00"),
            )
            self.assertEqual(result["leave_wage_total"], Decimal("360000.00"))
            self.assertEqual(result["leave_rate"], Decimal("986.3014"))
            leave_summary = annual_leave_summary(result["employee"], 2026)
            expected_prorated = (
                leave_summary["calculated_entitled"]
                * Decimal("232")
                / Decimal("365")
            )
            self.assertTrue(leave_summary["termination_prorated"])
            self.assertEqual(leave_summary["termination_date"], date(2026, 8, 20))
            self.assertEqual(leave_summary["entitled"], expected_prorated)
            self.assertEqual(result["benefit"]["type"], "long_service")
            self.assertEqual(result["benefit"]["mpf_offset"], Decimal("500.00"))
            self.assertGreater(result["benefit"]["pre_amount"], Decimal("0"))
            self.assertGreater(result["benefit"]["post_amount"], Decimal("0"))
            daily_benefit = calculate_benefit(
                period,
                result["case"],
                {},
                "site_daily",
            )
            pre_days, post_days = service_portion_days(period)
            self.assertEqual(
                daily_benefit["pre_amount"],
                (Decimal("15000") * Decimal(pre_days) / Decimal("365")).quantize(
                    Decimal("0.01")
                ),
            )
            self.assertEqual(
                daily_benefit["post_amount"],
                (Decimal("15000") * Decimal(post_days) / Decimal("365")).quantize(
                    Decimal("0.01")
                ),
            )
            self.assertEqual(
                EmployeeFinalPaymentCase.query.filter_by(
                    employment_period_id=period_id
                ).count(),
                1,
            )
            ordinary_rows = [
                row
                for row in calculate_payroll("2026-08", "all")
                if row["employee"].id == employee_id
            ]
            self.assertEqual(ordinary_rows, [])
            final_mpf_rows = [
                row
                for row in mpf_preview_rows("2026-08")
                if row["employee"].id == employee_id
            ]
            self.assertEqual(len(final_mpf_rows), 1)
            self.assertTrue(final_mpf_rows[0]["is_final_payment"])

        mpf_page = self.client.get(
            "/mpf-contributions",
            query_string={"year_month": "2026-08"},
        ).get_data(as_text=True)
        self.assertIn("離職員工 MPF 規則", mpf_page)
        self.assertIn("只採用已確認的 Final Payment 結果", mpf_page)

        response = self.client.post(
            "/final-payment/export",
            data={
                "year_month": "2026-08",
                "payroll_group": "management",
                "payroll_entity_id": str(payroll_entity_id),
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "application/vnd.openxmlformats-officedocument",
            response.content_type,
        )
        workbook = load_workbook(io.BytesIO(response.data), data_only=False)
        self.assertEqual(workbook.sheetnames, ["OFFICE", "計算說明"])
        sheet = workbook["OFFICE"]
        self.assertEqual(sheet["A1"].value, "Hong Kong River Engineering Co. Ltd.")
        self.assertEqual(sheet["A2"].value, "Final Payment")
        self.assertEqual(sheet["A3"].value, "Payroll of Local Staff")
        merged_ranges = {str(item) for item in sheet.merged_cells.ranges}
        self.assertTrue({"A1:Z1", "A2:Z2", "A3:Z3"}.issubset(merged_ranges))
        self.assertEqual(sheet["D8"].value, employee_no)
        self.assertIsNone(sheet["D9"].value)
        self.assertLess(Decimal(str(sheet["W8"].value)), Decimal("0"))
        self.assertEqual(sheet["J8"].value, "=ROUND(H8*I8,2)")
        self.assertEqual(sheet["M8"].value, "=ROUND(K8*L8,2)")
        self.assertTrue(str(sheet["V8"].value).startswith("=ROUND("))
        self.assertEqual(sheet["X8"].value, "=ROUND(V8+W8,2)")
        self.assertEqual(sheet["Y8"].value, "=X8")
        exported_base = (
            Decimal(str(sheet["H8"].value))
            * Decimal(str(sheet["I8"].value))
        ).quantize(Decimal("0.01"))
        exported_ot = (
            Decimal(str(sheet["K8"].value))
            * Decimal(str(sheet["L8"].value))
        ).quantize(Decimal("0.01"))
        exported_holiday = (
            Decimal(str(sheet["N8"].value))
            * Decimal(str(sheet["O8"].value))
        ).quantize(Decimal("0.01"))
        exported_gross = sum(
            (
                exported_base,
                exported_ot,
                exported_holiday,
                *(Decimal(str(sheet.cell(8, column).value or 0)) for column in range(17, 22)),
            ),
            Decimal("0"),
        ).quantize(Decimal("0.01"))
        exported_net = (
            exported_gross + Decimal(str(sheet["W8"].value))
        ).quantize(Decimal("0.01"))
        self.assertEqual(exported_base, expected_base_amount)
        self.assertEqual(exported_ot, expected_ot_amount)
        self.assertEqual(exported_holiday, expected_holiday_amount)
        self.assertEqual(exported_net, expected_net_amount)
        notes = workbook["計算說明"]
        self.assertIn("勞工處規則摘要", notes["A1"].value)
        self.assertTrue(
            any(
                "最後 30 個正常工作日" in str(cell.value or "")
                for cell in notes["B"]
            )
        )
        self.assertEqual(
            notes["C5"].hyperlink.target,
            "https://www.labour.gov.hk/tc/faq/cap57l_whole.htm",
        )

        response = self.client.post(
            "/final-payment/export",
            data={
                "year_month": "2026-08",
                "payroll_group": "all",
                "payroll_entity_id": str(payroll_entity_id),
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content_type, "application/zip")
        with zipfile.ZipFile(io.BytesIO(response.data)) as archive:
            self.assertEqual(
                set(archive.namelist()),
                {
                    f"HKR_Final_Payment_2026-08_{payroll_entity_code}_site_daily.xlsx",
                    f"HKR_Final_Payment_2026-08_{payroll_entity_code}_site_monthly.xlsx",
                    f"HKR_Final_Payment_2026-08_{payroll_entity_code}_management.xlsx",
                },
            )
            daily_workbook = load_workbook(
                io.BytesIO(
                    archive.read(
                        f"HKR_Final_Payment_2026-08_{payroll_entity_code}_site_daily.xlsx"
                    )
                ),
                data_only=False,
            )
        self.assertIn("計算說明", daily_workbook.sheetnames)

    def test_payroll_regression_matrix_for_leave_ot_ecall_and_export(self):
        post_id, _ = self.create_employee(
            "ASMTP", "site_monthly", "綜合薪酬測試", "PAYROLL MATRIX"
        )
        project_id = self.complete_employee(
            post_id,
            "site_monthly",
            "TMC046",
            "monthly",
            "31000",
            "MATRIX-01",
            "61118881",
        )
        pre_id, _ = self.create_employee(
            "ASMTP", "site_monthly", "試用期病假測試", "PROBATION SICK"
        )
        self.complete_employee(
            pre_id,
            "site_monthly",
            "TMC046",
            "monthly",
            "31000",
            "MATRIX-02",
            "61118882",
        )
        with self.app.app_context():
            post = db.session.get(Employee, post_id)
            post.current_period.confirmation_date = date(2026, 6, 30)
            summary = AttendanceMonthlySummary(
                employee_id=post_id,
                year_month="2026-07",
                status="received",
                special_day_handling="pay",
            )
            pre_summary = AttendanceMonthlySummary(
                employee_id=pre_id,
                year_month="2026-07",
                status="received",
            )
            db.session.add_all([summary, pre_summary])
            db.session.flush()
            current = AttendanceSegment(
                summary=summary,
                period_kind="current_1_20",
                project_id=project_id,
                working_days=Decimal("16"),
                ot_hours=Decimal("9"),
                large_ecall_count=1,
                ecall_count=1,
            )
            previous = AttendanceSegment(
                summary=summary,
                period_kind="previous_21_end",
                project_id=project_id,
                ot_hours=Decimal("9"),
                ecall_count=1,
            )
            previous_forecast = AttendanceSegment(
                summary=summary,
                period_kind="previous_21_end_forecast",
                project_id=project_id,
            )
            db.session.add_all([current, previous, previous_forecast])
            db.session.flush()
            db.session.add_all(
                [
                    AttendanceSpecialDay(
                        summary=summary,
                        segment=current,
                        period_kind="current_1_20",
                        project_id=project_id,
                        work_date=date(2026, 7, 5),
                        day_kind="rest_day",
                        handling="pay",
                        days=Decimal("1"),
                        status="active",
                    ),
                    EmployeeAnnualLeaveRecord(
                        employee_id=post_id,
                        leave_date=date(2026, 7, 6),
                        end_date=date(2026, 7, 7),
                        entitlement_year=2026,
                        days=Decimal("2"),
                        leave_type="annual",
                        status="active",
                    ),
                    EmployeeAnnualLeaveRecord(
                        employee_id=post_id,
                        leave_date=date(2026, 7, 8),
                        end_date=date(2026, 7, 10),
                        entitlement_year=2026,
                        days=Decimal("3"),
                        leave_type="sick",
                        status="active",
                    ),
                    EmployeeAnnualLeaveRecord(
                        employee_id=post_id,
                        leave_date=date(2026, 7, 11),
                        end_date=date(2026, 7, 12),
                        entitlement_year=2026,
                        days=Decimal("2"),
                        leave_type="unpaid",
                        status="active",
                    ),
                    EmployeeAnnualLeaveRecord(
                        employee_id=pre_id,
                        leave_date=date(2026, 7, 8),
                        end_date=date(2026, 7, 8),
                        entitlement_year=2026,
                        days=Decimal("1"),
                        leave_type="sick",
                        status="active",
                    ),
                ]
            )
            db.session.commit()
            rows = calculate_payroll("2026-07", "site_monthly")
            matrix = next(row for row in rows if row["employee"].id == post_id)
            probation = next(row for row in rows if row["employee"].id == pre_id)
            self.assertEqual(matrix["annual_leave_days"], Decimal("2.00"))
            self.assertEqual(matrix["sick_leave_days"], Decimal("3.00"))
            self.assertEqual(matrix["sick_leave_amount"], Decimal("2600.00"))
            self.assertEqual(matrix["unpaid_leave_days"], Decimal("2.00"))
            self.assertEqual(matrix["unpaid_leave_deduction"], Decimal("2000.00"))
            self.assertEqual(matrix["ot_amount"], Decimal("1500.00"))
            self.assertEqual(matrix["large_ecall_amount"], Decimal("1000.00"))
            self.assertEqual(matrix["ecall_amount"], Decimal("400.00"))
            self.assertEqual(matrix["underpay_amount"], Decimal("0.00"))
            self.assertEqual(matrix["overpay_amount"], Decimal("0.00"))
            self.assertEqual(probation["sick_leave_amount"], Decimal("800.00"))
            payroll_entity_id = post.current_assignment.payroll_entity_id

        response = self.client.post(
            "/payroll/export-current",
            data={
                "year_month": "2026-07",
                "payroll_group": "site_monthly",
                "payroll_entity_id": payroll_entity_id,
                "scope": "selected",
                "employee_ids": [post_id],
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        workbook = load_workbook(io.BytesIO(response.data), data_only=False)
        sheet = workbook["月工"]
        self.assertEqual(sheet["K7"].value, "=J7/$G$5")
        self.assertEqual(Decimal(str(sheet["L7"].value)), Decimal("26"))
        self.assertEqual(Decimal(str(sheet["AF7"].value)), Decimal("0"))
        self.assertEqual(Decimal(str(sheet["AG7"].value)), Decimal("0"))
        self.assertTrue(str(sheet["M7"].value).startswith("=ROUND"))

    def test_daily_statutory_holiday_pay_and_workweek_units(self):
        daily_id, _ = self.create_employee(
            "HKR",
            "site_daily",
            "日工法定假日測試",
            "DAILY STATUTORY HOLIDAY",
        )
        project_id = self.complete_employee(
            daily_id,
            "site_daily",
            "TMC046",
            "daily",
            "1000",
            "Y1234567",
            "61110001",
        )
        with self.app.app_context():
            employee = db.session.get(Employee, daily_id)
            region_id = employee.current_assignment.region_id
            sunday_rows = automatic_attendance_rows(
                employee,
                date(2026, 7, 5),
                date(2026, 7, 5),
            )
            self.assertEqual(
                sum(Decimal(str(item["working_days"])) for item in sunday_rows),
                Decimal("0"),
            )
            self.assertIsNone(
                special_work_day_units(employee, date(2026, 7, 5))
            )
            self.assertEqual(
                special_work_day_units(employee, date(2026, 7, 1)),
                Decimal("1"),
            )
            employee.annual_leave_records.append(
                EmployeeAnnualLeaveRecord(
                    leave_date=date(2026, 8, 15),
                    end_date=date(2026, 8, 15),
                    entitlement_year=2026,
                    days=Decimal("1"),
                    leave_type="annual",
                    status="active",
                )
            )
            august_summary = AttendanceMonthlySummary(
                employee_id=daily_id,
                year_month="2026-08",
                status="received",
            )
            for kind in (
                "current_1_20",
                "current_21_end_forecast",
                "previous_21_end",
                "previous_21_end_forecast",
            ):
                august_summary.segments.append(
                    AttendanceSegment(
                        period_kind=kind,
                        project_id=project_id,
                        working_days=Decimal("0"),
                        sunday_holiday_days=Decimal("0"),
                        ot_hours=Decimal("0"),
                    )
                )
            db.session.add(august_summary)
            db.session.commit()
            august_prefill = automatic_attendance_rows(
                employee,
                date(2026, 8, 15),
                date(2026, 8, 15),
            )
            self.assertEqual(
                sum(Decimal(str(item["working_days"])) for item in august_prefill),
                Decimal("0"),
            )
            august_payroll = calculate_payroll("2026-08", "site_daily")[0]
            self.assertEqual(august_payroll["annual_leave_days"], Decimal("1.00"))
            self.assertEqual(august_payroll["base_amount"], Decimal("1000.00"))
            with self.app.test_request_context(
                method="POST",
                data={
                    "employee_id": str(daily_id),
                    "current_1_20_project_id": [str(project_id)],
                    "current_1_20_working_days": ["1"],
                    "current_1_20_holiday_days": ["1"],
                    "current_1_20_special_work_entries": [json.dumps([
                        {"date": "2026-07-05"},
                    ])],
                },
            ):
                self.assertIn(
                    "日工的星期日工作應計入一般實際出勤日數",
                    validate_sunday_holiday_entries("2026-07"),
                )
            summary = AttendanceMonthlySummary(
                employee_id=daily_id,
                year_month="2026-07",
                status="received",
                special_day_handling="pay",
            )
            actual = AttendanceSegment(
                summary=summary,
                period_kind="current_1_20",
                project_id=project_id,
                working_days=Decimal("10"),
                sunday_holiday_days=Decimal("0"),
                ot_hours=Decimal("0"),
            )
            summary.segments.extend(
                [
                    actual,
                    AttendanceSegment(
                        period_kind="current_21_end_forecast",
                        project_id=project_id,
                        working_days=Decimal("8"),
                        sunday_holiday_days=Decimal("0"),
                        ot_hours=Decimal("0"),
                    ),
                    AttendanceSegment(
                        period_kind="previous_21_end",
                        project_id=project_id,
                        working_days=Decimal("8"),
                        sunday_holiday_days=Decimal("0"),
                        ot_hours=Decimal("0"),
                    ),
                    AttendanceSegment(
                        period_kind="previous_21_end_forecast",
                        project_id=project_id,
                        working_days=Decimal("8"),
                        sunday_holiday_days=Decimal("0"),
                        ot_hours=Decimal("0"),
                    ),
                ]
            )
            db.session.add(summary)
            db.session.commit()

            fallback_lines = {}
            fallback_amount = forecast_tail(
                employee,
                date(2026, 7, 1),
                date(2026, 7, 2),
                fallback_lines,
            )
            self.assertEqual(fallback_amount, Decimal("1000"))
            self.assertEqual(
                sum(
                    Decimal(str(line["forecast_working_days"]))
                    for line in fallback_lines.values()
                ),
                Decimal("1"),
            )

            holiday_only = calculate_payroll("2026-07", "site_daily")[0]
            self.assertEqual(holiday_only["holiday_amount"], Decimal("1000.00"))
            self.assertEqual(
                holiday_only["statutory_holiday_paid_days"],
                Decimal("1.00"),
            )

            actual.sunday_holiday_days = Decimal("1")
            actual.summary.special_days.append(
                AttendanceSpecialDay(
                    segment=actual,
                    period_kind="current_1_20",
                    project_id=project_id,
                    work_date=date(2026, 7, 1),
                    day_kind="sunday_statutory_holiday",
                    session="full_day",
                    handling="pay",
                    days=Decimal("1"),
                    status="active",
                )
            )
            db.session.commit()
            worked_and_paid = calculate_payroll("2026-07", "site_daily")[0]
            self.assertEqual(
                worked_and_paid["holiday_amount"],
                Decimal("2000.00"),
            )

            actual.summary.special_days[0].handling = "comp_leave"
            db.session.commit()
            worked_for_comp = calculate_payroll("2026-07", "site_daily")[0]
            self.assertEqual(
                worked_for_comp["holiday_amount"],
                Decimal("1000.00"),
            )

            db.session.add_all(
                [
                    WorkCalendarHoliday(
                        region_id=region_id,
                        holiday_date=holiday_date,
                        name=f"五月法定假日 {holiday_date:%m-%d}",
                        active=True,
                    )
                    for holiday_date in (date(2026, 5, 1), date(2026, 5, 25))
                ]
            )
            may_summary = AttendanceMonthlySummary(
                employee_id=daily_id,
                year_month="2026-05",
                status="received",
                special_day_handling="pay",
            )
            may_actual = AttendanceSegment(
                summary=may_summary,
                period_kind="current_1_20",
                project_id=project_id,
                working_days=Decimal("16"),
                sunday_holiday_days=Decimal("1"),
            )
            may_summary.segments.extend(
                [
                    may_actual,
                    AttendanceSegment(
                        period_kind="current_21_end_forecast",
                        project_id=project_id,
                        working_days=Decimal("10"),
                        sunday_holiday_days=Decimal("1"),
                    ),
                    AttendanceSegment(
                        period_kind="previous_21_end",
                        project_id=project_id,
                        working_days=Decimal("0"),
                        sunday_holiday_days=Decimal("0"),
                    ),
                    AttendanceSegment(
                        period_kind="previous_21_end_forecast",
                        project_id=project_id,
                        working_days=Decimal("0"),
                        sunday_holiday_days=Decimal("0"),
                    ),
                ]
            )
            may_summary.special_days.append(
                AttendanceSpecialDay(
                    segment=may_actual,
                    period_kind="current_1_20",
                    project_id=project_id,
                    work_date=date(2026, 5, 1),
                    day_kind="statutory_holiday",
                    session="full_day",
                    handling="pay",
                    days=Decimal("1"),
                    status="active",
                )
            )
            db.session.add(may_summary)
            db.session.commit()
            may_payroll = calculate_payroll("2026-05", "site_daily")[0]
            self.assertEqual(
                sum(line["working_days"] for line in may_payroll["lines"]),
                Decimal("26.00"),
            )
            self.assertEqual(
                sum(line["holiday_days"] for line in may_payroll["lines"]),
                Decimal("4.00"),
            )
            self.assertEqual(
                may_payroll["statutory_holiday_paid_days"], Decimal("2.00")
            )
            self.assertEqual(may_payroll["base_amount"], Decimal("26000.00"))
            self.assertEqual(may_payroll["holiday_amount"], Decimal("4000.00"))
            self.assertEqual(may_payroll["gross_amount"], Decimal("30000.00"))

        management_id, _ = self.create_employee(
            "HKR",
            "management",
            "五點五天測試",
            "FIVE HALF WORKWEEK",
        )
        management_project_id = self.complete_employee(
            management_id,
            "management",
            "TMC046",
            "monthly",
            "31000",
            "Y7654321",
            "61110002",
        )
        with self.app.app_context():
            employee = db.session.get(Employee, management_id)
            employee.current_assignment.workweek_days = Decimal("5.5")
            db.session.add(
                WorkCalendarHoliday(
                    region_id=employee.current_assignment.region_id,
                    holiday_date=date(2026, 7, 24),
                    name="工作日曆測試假日",
                    applies_to_statutory=False,
                    applies_to_public=True,
                    active=True,
                )
            )
            db.session.commit()
            rows = automatic_attendance_rows(
                employee,
                date(2026, 7, 21),
                date(2026, 7, 31),
            )
            self.assertEqual(
                sum(Decimal(str(item["working_days"])) for item in rows),
                Decimal("8.5"),
            )
            self.assertEqual(
                special_work_day_units(employee, date(2026, 7, 25)),
                Decimal("0.5"),
            )
            self.assertEqual(
                special_work_day_units(employee, date(2026, 7, 26)),
                Decimal("1"),
            )
            self.assertIsNone(
                special_work_day_units(employee, date(2026, 7, 27))
            )
            with self.app.test_request_context(
                method="POST",
                data={
                    "employee_id": str(management_id),
                    "current_1_20_project_id": [str(management_project_id)],
                    "current_1_20_working_days": ["0"],
                    "current_1_20_holiday_days": ["0.5"],
                    "current_1_20_special_work_entries": [json.dumps([
                        {"date": "2026-07-18"},
                    ])],
                },
            ):
                self.assertIsNone(
                    validate_attendance_segment_totals("2026-07")
                )
                self.assertIsNone(
                    validate_sunday_holiday_entries("2026-07")
                )


if __name__ == "__main__":
    unittest.main()
