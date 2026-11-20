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


class WorkbenchWorkflowTests(HrAppTestCase):
    def test_admin_system_status_is_read_only_and_versioned(self):
        page = self.client.get("/admin/system")
        self.assertEqual(page.status_code, 200)
        source = page.get_data(as_text=True)
        self.assertIn("系統運行狀態", source)
        self.assertIn(CURRENT_VERSION, source)
        self.assertIn("此頁不執行備份、還原或資料庫升級", source)
        self.assertNotIn("立即備份", source)
        self.assertNotIn("立即還原", source)

    def test_user_guide_page_and_release_alignment(self):
        self.assertEqual(CURRENT_VERSION, "V0.7.7")
        self.assertEqual(NEXT_VERSION, "V0.7.8")
        self.assertEqual(
            [(release["version"], release["date"]) for release in RELEASES],
            [
                ("V0.7.7", "2026-11-19"),
                ("V0.7.6", "2026-11-19"),
                ("V0.7.5", "2026-11-19"),
                ("V0.7.4", "2026-11-19"),
                ("V0.7.3", "2026-11-18"),
                ("V0.7.2", "2026-11-18"),
                ("V0.7.1", "2026-11-18"),
                ("V0.7.0", "2026-11-18"),
                ("V0.6.0", "2026-11-04"),
                ("V0.5.10", "2026-10-09"),
                ("V0.5.9", "2026-10-09"),
                ("V0.5.8", "2026-10-09"),
                ("V0.5.7", "2026-09-24"),
                ("V0.5.6", "2026-09-16"),
                ("V0.5.5", "2026-09-10"),
                ("V0.5.4", "2026-09-09"),
                ("V0.5.3", "2026-09-09"),
                ("V0.5.2", "2026-09-09"),
                ("V0.5.1", "2026-09-09"),
                ("V0.5.0", "2026-09-07"),
                ("V0.4.0", "2026-09-07"),
                ("V0.3.11", "2026-09-06"),
                ("V0.3.10", "2026-09-01"),
                ("V0.3.9", "2026-08-28"),
                ("V0.3.8", "2026-08-21"),
                ("V0.3.7", "2026-08-21"),
                ("V0.3.6", "2026-08-21"),
                ("V0.3.5", "2026-08-21"),
                ("V0.3.4", "2026-08-20"),
                ("V0.3.3", "2026-08-20"),
                ("V0.3.2", "2026-08-19"),
                ("V0.3.1", "2026-08-19"),
                ("V0.3.0", "2026-08-18"),
                ("V0.2.9", "2026-08-17"),
                ("V0.2.8", "2026-08-17"),
                ("V0.2.7", "2026-08-14"),
                ("V0.2.6", "2026-08-13"),
                ("V0.2.5", "2026-08-12"),
                ("V0.2.4", "2026-08-12"),
                ("V0.2.3", "2026-08-12"),
                ("V0.2.2", "2026-08-11"),
                ("V0.2.1", "2026-08-11"),
                ("V0.2.0", "2026-08-10"),
                ("V0.1.9", "2026-08-10"),
                ("V0.1.8", "2026-08-10"),
                ("V0.1.7", "2026-08-10"),
                ("V0.1.6", "2026-08-10"),
                ("V0.1.5", "2026-08-07"),
                ("V0.1.4", "2026-08-07"),
                ("V0.1.3", "2026-08-06"),
                ("V0.1.2", "2026-08-06"),
                ("V0.1.1", "2026-08-04"),
                ("V0.1.0", "2026-07-31"),
                ("V0.0.9", "2026-07-30"),
                ("V0.0.8", "2026-07-30"),
                ("V0.0.7", "2026-07-29"),
                ("V0.0.6", "2026-07-27"),
                ("V0.0.5", "2026-07-26"),
                ("V0.0.4", "2026-07-25"),
                ("V0.0.3", "2026-07-21"),
                ("V0.0.2", "2026-07-16"),
                ("V0.0.1", "2026-07-13"),
            ],
        )

        source = (APP_ROOT / "操作指南.md").read_text(encoding="utf-8")
        css_source = (APP_ROOT / "static" / "css" / "app.css").read_text(
            encoding="utf-8"
        )
        self.assertIn(".employee-readiness-wrap {", css_source)
        self.assertIn("max-height: calc(100vh - var(--header-height) - 205px);", css_source)
        self.assertIn(
            ".employee-readiness-wrap .employee-readiness-table thead th {",
            css_source,
        )
        self.assertIn(f"> 適用版本：{CURRENT_VERSION}", source)
        self.assertIn("本月無需考勤", source)
        self.assertIn("繁體或簡體搜尋", source)
        self.assertIn("離職後月份不再顯示", source)
        self.assertIn(f"> 更新日期：{RELEASES[0]['date']}", source)
        self.assertNotIn("適用對象：", source)
        self.assertIn("2026年8月1–20日（實際）", source)
        self.assertIn("2026年7月21–31日（原預估）", source)
        self.assertIn("上傳文件", source)
        self.assertIn("一般附件類型", source)
        self.assertIn("前往專項管理", source)
        self.assertIn("最小單位為 0.5 日", source)
        self.assertIn("撤回離職資料", source)
        self.assertIn("匯出薪金證明書", source)
        self.assertIn("頁面會自動計算", source)
        self.assertIn("修正／撤回／替換／補件", source)
        self.assertIn("### 10.6 每月 MPF 供款表", source)
        self.assertIn("Member Account No.", source)
        self.assertIn("變更歷史", source)
        self.assertIn("離職結算", source)
        self.assertIn("發薪單位", source)
        self.assertIn("手動例外補貼", source)

        response = self.client.get("/guide")
        self.assertEqual(response.status_code, 200)
        page = response.get_data(as_text=True)
        self.assertIn("HKR HR 操作指南", page)
        self.assertIn('href="/guide"', page)
        self.assertNotIn('href="/guide/download"', page)
        self.assertNotIn("下載 Markdown", page)
        self.assertNotIn("返回 Dashboard", page)
        self.assertIn("目前版本不使用 OCR", page)
        self.assertIn("Excel 會自動完整重算", page)

        english = self.client.get("/guide?lang=en").get_data(as_text=True)
        self.assertIn("<title>User Guide - HKR HR</title>", english)
        self.assertNotIn("Download Markdown", english)
        self.assertNotIn("Back to Dashboard", english)
        self.assertIn("HKR HR 操作指南", english)

        download = self.client.get("/guide/download")
        self.assertEqual(download.status_code, 404)

        self.client.post("/logout")
        protected = self.client.get("/guide")
        self.assertEqual(protected.status_code, 302)
        self.assertIn("/login", protected.headers["Location"])

    def test_acceptance_fixes_for_admin_and_employee_defaults(self):
        users_page = self.client.get("/admin/users?lang=en")
        self.assertEqual(users_page.status_code, 200)
        users_html = users_page.get_data(as_text=True)
        self.assertIn("Existing users", users_html)
        self.assertIn("Add user", users_html)
        self.assertIn("Current account", users_html)
        self.assertIn('data-dialog-open="manage-user-', users_html)
        self.assertIn("Delete account", users_html)
        self.assertNotIn("/admin/import", users_html)
        self.assertEqual(self.client.get("/admin/import").status_code, 404)
        self.assertEqual(
            self.client.get("/admin/import/template").status_code,
            404,
        )

        with self.app.app_context():
            admin_id = User.query.filter_by(username="admin").one().id
        demotion = self.client.post(
            "/admin/users",
            data={
                "action": "update",
                "user_id": admin_id,
                "role": "hr",
                "active": "on",
            },
            follow_redirects=True,
        )
        self.assertIn(
            "不能移除目前登入帳戶的 Admin 權限",
            demotion.get_data(as_text=True),
        )
        with self.app.app_context():
            self.assertEqual(db.session.get(User, admin_id).role, "admin")

        self_delete = self.client.post(
            "/admin/users",
            data={"action": "delete", "user_id": admin_id},
            follow_redirects=True,
        )
        self.assertIn(
            "The signed-in account cannot be deleted.",
            self_delete.get_data(as_text=True),
        )

        with self.app.app_context():
            disposable = User(
                username="delete_me",
                role="hr",
                active=True,
            )
            disposable.set_password("temporary-password")
            db.session.add(disposable)
            db.session.flush()
            disposable_id = disposable.id
            historical_log = AuditLog(
                user_id=disposable_id,
                action="auth_login_success",
                entity_type="User",
                entity_id=disposable_id,
                detail="delete_me",
            )
            db.session.add(historical_log)
            db.session.commit()
            historical_log_id = historical_log.id
        deleted = self.client.post(
            "/admin/users",
            data={"action": "delete", "user_id": disposable_id},
            follow_redirects=True,
        )
        self.assertIn("User deleted.", deleted.get_data(as_text=True))
        with self.app.app_context():
            self.assertIsNone(db.session.get(User, disposable_id))
            self.assertIsNotNone(db.session.get(AuditLog, historical_log_id))
            self.assertIsNone(
                db.session.get(AuditLog, historical_log_id).user_id
            )
            deletion_log = AuditLog.query.filter_by(
                action="user_deleted",
                entity_id=disposable_id,
            ).one()
            self.assertEqual(deletion_log.detail, "delete_me")

        employee_id, _ = self.create_employee(
            "HKRD",
            "site_daily",
            "預設值驗收",
            "DEFAULT TEST",
        )
        profile = self.client.get(
            f"/employees/{employee_id}?tab=employment&lang=zh-Hant"
        )
        profile_html = profile.get_data(as_text=True)
        self.assertIn('value="+852" selected', profile_html)
        self.assertIn('value="daily" selected', profile_html)
        self.assertIn('value="HKD" selected', profile_html)
        self.assertIn("緊急聯絡電話", profile_html)

        saved = self.client.post(
            f"/employees/{employee_id}/personal",
            data={
                "profile_revision": current_profile_revision(self.app, employee_id, "all"),
                "mobile_region_code": "+852",
                "mobile_number": "61234567",
                "bank_name": "BANK OF CHINA (HONG KONG) LIMITED",
                "bank_account_no": "TEST-001",
                "mpf_mode": "regular",
            },
            follow_redirects=False,
        )
        self.assertEqual(saved.status_code, 302)
        self.assertIn("tab=personal", saved.headers["Location"])
        with self.app.app_context():
            saved_employee = db.session.get(Employee, employee_id)
            self.assertEqual(
                saved_employee.bank_name,
                "BANK OF CHINA (HONG KONG) LIMITED",
            )
            self.assertEqual(saved_employee.bank_account_no, "TEST-001")

        exports_page = self.client.get(
            "/exports?section=employees&lang=en"
        ).get_data(as_text=True)
        self.assertIn("Employee records workbook", exports_page)
        self.assertIn("Employment and Salary History", exports_page)
        self.assertNotIn('name="warning"', exports_page)
        self.assertNotIn('name="expiry"', exports_page)
        self.assertNotIn("Management Overview", exports_page)

    def test_dashboard_readiness_and_user_activity(self):
        employee_id, employee_no = self.create_employee(
            "HKR",
            "site_monthly",
            "待辦彙整測試",
            "GROUPED TASK TEST",
        )
        dashboard = self.client.get(
            "/dashboard?month=2026-08&lang=en"
        ).get_data(as_text=True)
        self.assertNotIn('class="readiness-employee"', dashboard)
        self.assertIn("Needs attention", dashboard)
        self.assertIn("Employee files", dashboard)
        self.assertIn("Attendance and payroll", dashboard)
        self.assertIn("Payroll status", dashboard)
        self.assertIn(employee_no, dashboard)

        register = self.client.get(
            "/employees?month=2026-08&readiness=needs_action&status=all&lang=en"
        ).get_data(as_text=True)
        self.assertIn(employee_no, register)
        self.assertIn("Employee file", register)
        self.assertIn(
            "Monthly attendance and payroll status (2026-08)",
            register,
        )
        self.assertEqual(register.count("Attendance not received"), 1)
        self.assertIn("Salary not set", register)
        self.assertIn("Staff Record not filed", register)
        self.assertIn("Employment Contract not filed", register)
        self.assertIn("Attendance not received", register)

        self.client.post("/logout", follow_redirects=True)
        with self.app.app_context():
            signed_out_admin = User.query.filter_by(username="admin").one()
            self.assertIsNotNone(signed_out_admin.last_logout_at)
            self.assertGreaterEqual(
                signed_out_admin.last_logout_at,
                signed_out_admin.last_login_at,
            )
        failed = self.login("admin", "wrong-password")
        self.assertIn("登入資料不正確", failed.get_data(as_text=True))
        self.login("admin", "test-admin-password")

        with self.app.app_context():
            failed_login = AuditLog.query.filter_by(
                action="auth_login_failed"
            ).one()
            failed_login.created_at = datetime(2026, 8, 11, 1, 2, 3)
            active_admin = User.query.filter_by(username="admin").one()
            active_admin.last_login_at = datetime.utcnow() - timedelta(hours=1)
            active_admin.last_logout_at = datetime.utcnow() - timedelta(minutes=30)
            active_admin.last_seen_at = datetime.utcnow()
            db.session.commit()

        users_page = self.client.get("/admin/users?lang=en").get_data(
            as_text=True
        )
        self.assertIn("Account status", users_page)
        self.assertIn("Recent activity", users_page)
        self.assertIn("Online", users_page)

        login_activity = self.client.get(
            "/admin/audit?view=logins&lang=en"
        ).get_data(as_text=True)

        self.assertIn("Login succeeded", login_activity)
        self.assertIn("Login failed", login_activity)
        self.assertIn("Logged out", login_activity)
        self.assertIn("2026-08-11 09:02:03", login_activity)
        self.assertNotIn("HKT", login_activity)
        with self.app.app_context():
            actions = {
                row.action
                for row in AuditLog.query.filter(
                    AuditLog.action.in_(
                        {
                            "auth_login_success",
                            "auth_login_failed",
                            "auth_logout",
                        }
                    )
                )
            }
            self.assertEqual(
                actions,
                {"auth_login_success", "auth_login_failed", "auth_logout"},
            )

        payroll_template = load_workbook(
            APP_ROOT
            / "payroll_templates"
            / "Payroll_PC_AD014_V1_Template.xlsx",
            data_only=False,
        )
        self.assertEqual(payroll_template["月工"]["C6"].value, "Monthly Site Worker\n地盤月工")
        self.assertEqual(
            payroll_template["OFFICE"]["C6"].value,
            "Management / Office Staff\n管理及總部人員",
        )
        self.assertEqual(payroll_template["日工"]["C6"].value, "Daily Site Worker\n地盤日工")
        self.assertEqual(payroll_template["日工"]["J6"].value, "Daily salary standard\n日薪標準")
        self.assertTrue(str(payroll_template["日工"]["AP7"].value).startswith("="))
        payroll_template.close()

    def test_dashboard_confirmation_reminders_link_to_confirmation_editor(self):
        due_id, due_no = self.create_employee(
            "HKR",
            "management",
            "即將轉正",
            "CONFIRMATION DUE",
        )
        overdue_id, overdue_no = self.create_employee(
            "HKR",
            "management",
            "逾期轉正",
            "CONFIRMATION OVERDUE",
        )
        future_id, future_no = self.create_employee(
            "HKR",
            "management",
            "未到提醒期",
            "CONFIRMATION FUTURE",
        )
        confirmed_id, confirmed_no = self.create_employee(
            "HKR",
            "management",
            "已經轉正",
            "ALREADY CONFIRMED",
        )
        monthly_id, monthly_no = self.create_employee(
            "HKR",
            "site_monthly",
            "月工試用期",
            "MONTHLY PROBATION",
        )
        today = date.today()
        with self.app.app_context():
            periods = {
                employee_id: EmployeeEmploymentPeriod(
                    employee_id=employee_id,
                    start_date=today - timedelta(days=100),
                )
                for employee_id in (
                    due_id,
                    overdue_id,
                    future_id,
                    confirmed_id,
                    monthly_id,
                )
            }
            periods[due_id].probation_end_date = today + timedelta(days=10)
            periods[overdue_id].probation_end_date = today - timedelta(days=2)
            periods[future_id].probation_end_date = today + timedelta(days=31)
            periods[confirmed_id].probation_end_date = today
            periods[confirmed_id].confirmation_date = today
            periods[monthly_id].probation_end_date = today
            db.session.add_all(periods.values())
            db.session.commit()

        dashboard = self.client.get(
            "/dashboard?month=2026-08&panel=confirmation&lang=en"
        ).get_data(as_text=True)
        dashboard = dashboard.split('id="confirmation-alerts"', 1)[1].split('</details>', 1)[0]
        self.assertIn("open", dashboard.split(">", 1)[0])
        self.assertIn("Employee confirmation reminders (2)", dashboard)
        self.assertIn(due_no, dashboard)
        self.assertIn(overdue_no, dashboard)
        self.assertNotIn(future_no, dashboard)
        self.assertNotIn(confirmed_no, dashboard)
        self.assertNotIn(monthly_no, dashboard)
        self.assertIn("Due in 10 day(s)", dashboard)
        self.assertIn("Overdue by 2 day(s)", dashboard)
        self.assertIn(
            f'/employees/{due_id}?tab=employment_status&amp;focus=probation',
            dashboard,
        )

        profile = self.client.get(
            f"/employees/{due_id}?tab=employment_status&focus=probation&lang=en"
        ).get_data(as_text=True)
        self.assertIn('id="probation-editor-dialog"', profile)
        self.assertIn('employeeDetailParams.get("focus") === "probation"', profile)
        self.assertIn("probation-editor-dialog", profile)


if __name__ == "__main__":
    unittest.main()
