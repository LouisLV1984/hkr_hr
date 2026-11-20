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


class PlatformWorkflowTests(HrAppTestCase):
    def test_security_boundaries_and_friendly_errors(self):
        self.assertEqual(
            safe_next_url("https://example.com/steal", "/dashboard"),
            "/dashboard",
        )
        self.assertEqual(
            safe_next_url("/employees?status=active", "/dashboard"),
            "/employees?status=active",
        )
        limiter = LoginRateLimiter(limit=2, window_seconds=60)
        limiter.record_failure("admin", "127.0.0.1")
        self.assertEqual(limiter.retry_after("admin", "127.0.0.1"), 0)
        limiter.record_failure("admin", "127.0.0.1")
        self.assertGreater(limiter.retry_after("admin", "127.0.0.1"), 0)
        limiter.clear("admin", "127.0.0.1")
        self.assertEqual(limiter.retry_after("admin", "127.0.0.1"), 0)

        valid_pdf = FileStorage(
            stream=io.BytesIO(pdf_bytes("VALID")),
            filename="attendance.pdf",
            content_type="text/plain",
        )
        metadata = validate_uploaded_file(valid_pdf, {".pdf"})
        self.assertEqual(metadata["mime_type"], "application/pdf")
        disguised_pdf = FileStorage(
            stream=io.BytesIO(b"not a pdf"),
            filename="attendance.pdf",
            content_type="application/pdf",
        )
        with self.assertRaises(UploadValidationError):
            validate_uploaded_file(disguised_pdf, {".pdf"})

        with self.assertRaises(RuntimeError):
            create_app(
                {
                    "HKR_HR_ENV": "production",
                    "SECRET_KEY": "dev-change-me",
                }
            )

        missing = self.client.get("/this-page-does-not-exist?lang=en")
        self.assertEqual(missing.status_code, 404)
        self.assertIn("Record not found", missing.get_data(as_text=True))

        self.app.config["CSRF_ENABLED"] = True
        login_page = self.client.get("/dashboard?lang=en")
        token_match = re.search(
            r'<meta name="csrf-token" content="([^"]+)"',
            login_page.get_data(as_text=True),
        )
        self.assertIsNotNone(token_match)
        self.client.post("/logout", data={"_csrf_token": token_match.group(1)})
        rejected = self.client.post(
            "/login?lang=en",
            data={"username": "admin", "password": "test-admin-password"},
        )
        self.assertEqual(rejected.status_code, 400)
        self.assertIn(
            "Page verification has expired",
            rejected.get_data(as_text=True),
        )
        self.app.config["CSRF_ENABLED"] = False
        self.login("admin", "test-admin-password")

        audit_page = self.client.get("/admin/audit?lang=en").get_data(
            as_text=True
        )
        self.assertIn("Login succeeded", audit_page)

    def test_schema_compatibility_detects_legacy_columns(self):
        legacy_dir = tempfile.TemporaryDirectory()
        self.addCleanup(legacy_dir.cleanup)
        legacy_path = Path(legacy_dir.name) / "legacy.db"
        legacy_app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "legacy-test",
                "SQLALCHEMY_DATABASE_URI": (
                    f"sqlite:///{legacy_path.as_posix()}"
                ),
            }
        )
        with legacy_app.app_context():
            db.session.execute(
                text(
                    "create table reference_lists ("
                    "id integer primary key, code varchar(64) not null)"
                )
            )
            db.session.execute(
                text(
                    "create table reference_values ("
                    "id integer primary key, list_id integer not null, "
                    "code varchar(64), display_name varchar(255) not null)"
                )
            )
            for table_name in (
                "employee_documents",
                "attendance_batch_items",
                "attendance_segments",
                "attendance_special_days",
                "payroll_employee_results",
                "payroll_project_lines",
            ):
                db.session.execute(
                    text(
                        f"create table {table_name} "
                        "(id integer primary key)"
                    )
                )
            db.session.commit()
            changed = apply_additive_migrations()
            self.assertIn(
                "attendance_segments.large_ecall_count",
                changed,
            )
            self.assertIn(
                "employee_documents.content_sha256",
                changed,
            )
            self.assertIn(
                "employee_documents.general_document_type_id",
                changed,
            )
            self.assertIn(
                "attendance_batch_items.content_sha256",
                changed,
            )
            self.assertIn(
                "attendance_batch_items.year_month",
                changed,
            )
            self.assertIn(
                "attendance_special_days.session",
                changed,
            )
            document_columns = {
                column["name"]
                for column in inspect(db.engine).get_columns(
                    "employee_documents"
                )
            }
            batch_item_columns = {
                column["name"]
                for column in inspect(db.engine).get_columns(
                    "attendance_batch_items"
                )
            }
            self.assertIn("content_sha256", document_columns)
            self.assertIn("general_document_type_id", document_columns)
            self.assertIn("content_sha256", batch_item_columns)
            self.assertIn("year_month", batch_item_columns)
            attendance_columns = {
                column["name"]
                for column in inspect(db.engine).get_columns(
                    "attendance_segments"
                )
            }
            self.assertTrue(
                {"large_ecall_count", "ecall_count"}.issubset(
                    attendance_columns
                )
            )
            result_columns = {
                column["name"]
                for column in inspect(db.engine).get_columns(
                    "payroll_employee_results"
                )
            }
            line_columns = {
                column["name"]
                for column in inspect(db.engine).get_columns(
                    "payroll_project_lines"
                )
            }
            self.assertTrue(
                {"large_ecall_amount", "ecall_amount"}.issubset(
                    result_columns
                )
            )
            self.assertTrue(
                {
                    "large_ecall_count",
                    "ecall_count",
                    "large_ecall_amount",
                    "ecall_amount",
                }.issubset(line_columns)
            )
            issues = schema_compatibility_issues()
            self.assertIn("reference_values", issues)
            self.assertIn("normalized_name", issues["reference_values"])
            db.session.remove()
            db.engine.dispose()

    def test_retired_workflow_tables_are_dropped_without_employee_loss(self):
        employee_id, employee_no = self.create_employee(
            "HKR",
            "management",
            "保留員工測試",
            "KEEP EMPLOYEE TEST",
        )
        with self.app.app_context():
            db.session.execute(
                text(
                    "create table import_batches ("
                    "id integer primary key, batch_no varchar(80))"
                )
            )
            db.session.execute(
                text(
                    "insert into import_batches (id, batch_no) "
                    "values (1, 'LEGACY')"
                )
            )
            db.session.execute(
                text(
                    "create table employee_task_notes ("
                    "id integer primary key, employee_id integer, "
                    "task_code varchar(80), note text)"
                )
            )
            db.session.execute(
                text(
                    "insert into employee_task_notes "
                    "(id, employee_id, task_code, note) "
                    "values (1, :employee_id, 'legacy', 'retired')"
                ),
                {"employee_id": employee_id},
            )
            db.session.commit()
            retired_audit = AuditLog(
                user_id=User.query.filter_by(username="admin").one().id,
                employee_id=employee_id,
                action="bank_confirmed_for_payroll",
                entity_type="Employee",
                entity_id=employee_id,
                detail="retired bank confirmation",
            )
            db.session.add(retired_audit)
            db.session.commit()
            retired_audit_id = retired_audit.id
            self.assertIn("import_batches", inspect(db.engine).get_table_names())
            self.assertIn(
                "employee_task_notes",
                inspect(db.engine).get_table_names(),
            )

            removed = retire_legacy_tables()

            self.assertEqual(
                removed,
                ["import_batches", "employee_task_notes"],
            )
            self.assertNotIn(
                "import_batches",
                inspect(db.engine).get_table_names(),
            )
            self.assertNotIn(
                "employee_task_notes",
                inspect(db.engine).get_table_names(),
            )
            employee = db.session.get(Employee, employee_id)
            self.assertIsNotNone(employee)
            self.assertEqual(employee.employee_no, employee_no)
            self.assertEqual(retire_obsolete_audit_events(), 1)
            self.assertIsNone(db.session.get(AuditLog, retired_audit_id))
            self.assertIsNotNone(db.session.get(Employee, employee_id))

    def test_search_fields_disable_browser_history_without_breaking_password_manager_tokens(self):
        def read_tpl(name):
            return self.app.jinja_loader.get_source(self.app.jinja_env, name)[0]

        base_source = read_tpl("base.html")
        self.assertNotIn("hkr-disabled-", base_source)
        self.assertIn('input[type="search"], [data-no-browser-history]', base_source)

        for template_name in [
            "attendance/index.html",
            "employees/list.html",
            "leave/index.html",
            "payroll/index.html",
        ]:
            source = read_tpl(template_name)
            search_controls = re.findall(r'<input type="search"[^>]*>', source)
            self.assertTrue(search_controls, template_name)
            for control in search_controls:
                self.assertIn('autocomplete="off"', control, template_name)
                self.assertIn('autocapitalize="off"', control, template_name)
                self.assertIn('spellcheck="false"', control, template_name)

        login_source = read_tpl("auth/login.html")
        self.assertIn('autocomplete="username"', login_source)
        self.assertIn('autocomplete="current-password"', login_source)

    def test_language_switch_and_page_smoke(self):
        routes = (
            "/dashboard",
            "/employees",
            "/employees/new",
            "/annual-leave",
            "/attendance",
            "/attendance-payroll?year_month=2026-07",
            "/exports",
            "/references",
            "/admin/users",
            "/admin/audit",
            "/updates",
            "/guide",
        )
        for route in routes:
            response = self.client.get(route)
            self.assertEqual(response.status_code, 200, route)
        dashboard = self.client.get("/dashboard").get_data(as_text=True)
        self.assertIn('class="app-layout no-sidebar"', dashboard)
        self.assertIn('class="system-tabs"', dashboard)
        self.assertNotIn('class="app-shell"', dashboard)
        self.assertNotIn('class="context-nav"', dashboard)
        self.assertIn("考勤錄入", dashboard)
        self.assertIn("出糧", dashboard)
        self.assertIn('aria-current="page"', dashboard)
        attendance = self.client.get("/attendance").get_data(as_text=True)
        self.assertIn('class="app-layout"', attendance)
        self.assertIn('class="app-shell"', attendance)
        self.assertIn('class="context-nav"', attendance)
        self.assertIn("考勤詳情", attendance)
        self.assertIn("拖放 PDF 到此或點擊選擇", attendance)
        attendance_collection = self.client.get(
            "/attendance?view=collection"
        ).get_data(as_text=True)
        self.assertIn('data-attendance-upload-form', attendance_collection)
        self.assertIn("拖放 PDF 到此或點擊選擇", attendance_collection)
        self.assertIn(
            "批次只管理已上傳 PDF",
            attendance_collection,
        )
        payroll = self.client.get(
            "/attendance-payroll?year_month=2026-07"
        ).get_data(as_text=True)
        self.assertIn('class="app-shell"', payroll)
        self.assertIn("payroll-controls", payroll)
        self.assertIn("data-payroll-filter", payroll)
        self.assertNotIn("確認並保存本次計算", payroll)
        self.assertNotIn('class="payroll-layout"', payroll)
        english = self.client.get(
            "/employees/new?lang=en"
        ).get_data(as_text=True)
        self.assertIn("Create employee file", english)
        self.assertIn("Site workers (daily)", english)
        self.assertIn("HR workbench", english)
        self.assertNotIn("建立員工檔案", english)
        english_references = self.client.get(
            "/references?list=education_level&lang=en"
        ).get_data(as_text=True)
        self.assertIn("Education level", english_references)
        self.assertIn("Archive option", english_references)
        self.assertNotIn("學歷", english_references)
        self.assertIn("Renaming updates existing displays and history", english_references)
        self.assertNotIn("System codes are hidden", english_references)
        project_references = self.client.get(
            "/references?list=projects&lang=en"
        ).get_data(as_text=True)
        self.assertNotIn("<th>Code</th>", project_references)
        self.assertNotIn('name="code"', project_references)
        english_payroll = self.client.get(
            "/attendance-payroll?year_month=2026-07&lang=en"
        ).get_data(as_text=True)
        self.assertIn("Payroll period:", english_payroll)
        self.assertIn("each ordinary E-CALL adds HKD 400", english_payroll)
        self.assertIn("XLSX exports retain calculation formulas", english_payroll)
        self.assertIn(
            "Contractually explicit exceptions use monthly salary / calendar days",
            english_payroll,
        )
        self.assertNotIn("出糧週期", english_payroll)
        english_attendance = self.client.get(
            "/attendance?view=collection&lang=en"
        ).get_data(as_text=True)
        self.assertIn("Drop PDFs here or click to choose", english_attendance)
        self.assertIn("A batch only groups uploaded PDFs", english_attendance)
        simplified = self.client.get(
            "/employees?lang=zh-Hans"
        ).get_data(as_text=True)
        self.assertIn("员工档案", simplified)
        self.assertIn("考勤录入", simplified)
        self.assertIn("每月工资表", simplified)
        self.assertNotIn("員工總覽", simplified)
        self.assertIn("退出登录", simplified)


if __name__ == "__main__":
    unittest.main()
