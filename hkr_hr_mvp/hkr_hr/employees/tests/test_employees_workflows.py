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


class EmployeesWorkflowTests(HrAppTestCase):
    def test_employee_search_matches_traditional_and_simplified_names(self):
        traditional_id, traditional_no = self.create_employee(
            "HKR",
            "site_monthly",
            "黃志強",
            "WONG CHI KEUNG",
        )
        simplified_id, simplified_no = self.create_employee(
            "HKR",
            "site_monthly",
            "黄美玲",
            "WONG MEI LING",
        )

        simplified_search = self.client.get(
            "/employees",
            query_string={"q": "黄", "status": "active"},
        ).get_data(as_text=True)
        self.assertIn(traditional_no, simplified_search)
        self.assertIn(simplified_no, simplified_search)

        traditional_search = self.client.get(
            "/employees",
            query_string={"q": "黃", "status": "active"},
        ).get_data(as_text=True)
        self.assertIn(traditional_no, traditional_search)
        self.assertIn(simplified_no, traditional_search)

        self.assertNotEqual(traditional_id, simplified_id)

    def test_employee_quick_reference_creation_and_return_context(self):
        employee_id, _ = self.create_employee(
            "HKR",
            "site_monthly",
            "快速選項驗收",
            "QUICK REFERENCE QA",
        )
        self.client.post("/logout")
        self.login("hr_test", "test-hr-password")

        created = self.client.post(
            "/references/quick-create",
            json={"list_code": "bank", "display_name": "驗收快速銀行"},
        )
        self.assertEqual(created.status_code, 200)
        created_payload = created.get_json()
        self.assertTrue(created_payload["created"])
        bank_id = created_payload["item"]["id"]

        duplicate = self.client.post(
            "/references/quick-create",
            json={"list_code": "bank", "display_name": "驗收快速銀行"},
        )
        self.assertEqual(duplicate.status_code, 200)
        self.assertFalse(duplicate.get_json()["created"])
        self.assertEqual(duplicate.get_json()["item"]["id"], bank_id)

        code_conflict = self.client.post(
            "/references/quick-create",
            json={"list_code": "position", "display_name": "Project Manager"},
        )
        self.assertEqual(code_conflict.status_code, 409)
        conflict_payload = code_conflict.get_json()
        self.assertFalse(conflict_payload["ok"])
        self.assertEqual(
            conflict_payload["error_code"],
            "reference_code_exists",
        )
        self.assertEqual(
            conflict_payload["existing_item"]["code"],
            "PROJECT_MANAGER",
        )
        with self.app.app_context():
            position_list = ReferenceList.query.filter_by(code="position").one()
            self.assertEqual(
                ReferenceValue.query.filter_by(
                    list_id=position_list.id,
                    code="PROJECT_MANAGER",
                ).count(),
                1,
            )

        bank_options = self.client.get(
            "/references/quick-options/bank"
        ).get_json()["items"]
        self.assertIn("驗收快速銀行", {
            item["display_name"] for item in bank_options
        })
        self.assertEqual(
            self.client.post(
                "/references/quick-create",
                json={
                    "list_code": "employee_type",
                    "display_name": "不應快速新增",
                },
            ).status_code,
            400,
        )

        with self.app.app_context():
            region_id = reference_by_code("work_region", "HK").id
        project = self.client.post(
            "/references/projects/quick-create",
            json={
                "name": "驗收快速項目",
                "region_id": region_id,
                "daily_ot_divisor": "10",
            },
        )
        self.assertEqual(project.status_code, 200)
        self.assertTrue(project.get_json()["created"])
        self.assertEqual(
            project.get_json()["item"]["daily_ot_divisor"], "10.00"
        )

        profile = self.client.get(
            f"/employees/{employee_id}?tab=personal"
        ).get_data(as_text=True)
        self.assertIn('data-ref-code="bank"', profile)
        self.assertIn('data-ref-code="projects"', profile)
        self.assertIn('class="quick-add-reference" type="button" hidden', profile)
        self.assertIn('data-add-label="新增銀行名稱"', profile)
        self.assertNotIn('aria-label="快速新增 銀行名稱">+</button>', profile)
        self.assertIn('id="quick-reference-dialog"', profile)

        return_to = f"/employees/{employee_id}?tab=personal"
        references = self.client.get(
            "/references",
            query_string={"list": "bank", "return_to": return_to},
        ).get_data(as_text=True)
        self.assertIn(f'href="{return_to.replace("&", "&amp;")}"', references)
        with self.app.app_context():
            education = ReferenceList.query.filter_by(
                code="education_level"
            ).one()
            education_id = education.id
        response = self.client.post(
            f"/references/{education_id}/values",
            data={
                "display_name": "返回路徑驗收",
                "return_to": return_to,
            },
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("return_to=", response.headers["Location"])

    def test_current_assignment_uses_position_and_prefills_adjustment(self):
        employee_id, _ = self.create_employee(
            "ASMTP",
            "management",
            "當前任職驗收",
            "CURRENT ASSIGNMENT QA",
        )
        empty_page = self.client.get(
            f"/employees/{employee_id}?tab=employment"
        ).get_data(as_text=True)
        self.assertIn("尚未建立任職資料", empty_page)
        self.assertIn("新增任職紀錄", empty_page)

        with self.app.app_context():
            region = reference_by_code("work_region", "HK")
            department = reference_by_code("department", "ENGINEERING")
            position = reference_by_code("position", "PROJECT_MANAGER")
            employer = reference_by_code("employer", "HK_RIVER")
            payroll_entity = reference_by_code("payroll_entity", "HK_RIVER")
            social = reference_by_code("social_insurance_entity", "NONE")
            dispatch = reference_by_code("labour_dispatch_entity", "NONE")
            ids = {
                "region": region.id,
                "department": department.id,
                "position": position.id,
                "employer": employer.id,
                "payroll": payroll_entity.id,
                "social": social.id,
                "dispatch": dispatch.id,
            }

        saved = self.client.post(
            f"/employees/{employee_id}/assignment",
            data={
                "effective_from": "2015-04-13",
                "region_id": ids["region"],
                "project_id": "",
                "department_id": ids["department"],
                "position_ids": [str(ids["position"])],
                "employer_id": ids["employer"],
                "payroll_entity_id": ids["payroll"],
                "social_insurance_entity_id": ids["social"],
                "labour_dispatch_entity_id": ids["dispatch"],
                "payroll_group": "management",
            },
            follow_redirects=True,
        )
        html = saved.get_data(as_text=True)
        self.assertIn("初始任職已保存，當前任職已建立。", html)
        self.assertIn("當前任職</span><h2>項目經理</h2>", html)
        self.assertIn("項目：未分配", html)
        self.assertIn("未分配", html)
        self.assertIn("5 天工作制", html)
        self.assertIn('data-dialog-open="add-assignment-dialog"', html)
        self.assertIn('id="add-assignment-dialog"', html)
        self.assertRegex(
            html,
            rf'(?s)name="region_id">.*?<option value="{ids["region"]}" selected>',
        )
        self.assertRegex(
            html,
            rf'(?s)<select class="multi-select-source" name="position_ids" multiple hidden.*?<option value="{ids["position"]}" selected>',
        )
        self.assertNotIn('name="position_ids" multiple size="4"', html)
        self.assertGreaterEqual(html.count('name="employer_id"'), 2)
        self.assertNotIn('type="hidden" name="employer_id"', html)

        future = self.client.post(
            f"/employees/{employee_id}/assignment",
            data={
                "effective_from": "2099-01-01",
                "region_id": ids["region"],
                "department_id": ids["department"],
                "position_ids": [str(ids["position"])],
                "employer_id": ids["employer"],
                "payroll_entity_id": ids["payroll"],
                "social_insurance_entity_id": ids["social"],
                "labour_dispatch_entity_id": ids["dispatch"],
                "payroll_group": "management",
                "workweek_days": "5.5",
            },
            follow_redirects=True,
        )
        future_html = future.get_data(as_text=True)
        self.assertIn("將於 2099-01-01 生效；目前任職暫不變", future_html)
        self.assertIn("當前任職</span><h2>項目經理</h2>", future_html)
        self.assertIn("5.5 天工作制", future_html)
        with self.app.app_context():
            future_assignment = EmployeeAssignment.query.filter_by(
                employee_id=employee_id,
                effective_from=date(2099, 1, 1),
            ).one()
            self.assertEqual(
                future_assignment.workweek_days,
                Decimal("5.5"),
            )

    def test_effective_ranges_identity_uniqueness_and_reference_protection(self):
        first_id, _ = self.create_employee(
            "HKR",
            "site_monthly",
            "資料可信測試一",
            "DATA TRUST ONE",
        )
        second_id, _ = self.create_employee(
            "HKR",
            "site_monthly",
            "資料可信測試二",
            "DATA TRUST TWO",
        )
        today = date.today()
        earlier = today - timedelta(days=20)
        later = today - timedelta(days=10)
        future = today + timedelta(days=30)

        for effective_from, group in (
            (later, "site_monthly"),
            (earlier, "site_daily"),
            (future, "management"),
        ):
            response = self.client.post(
                f"/employees/{first_id}/assignment",
                data={
                    "effective_from": effective_from.isoformat(),
                    "payroll_group": group,
                },
                follow_redirects=True,
            )
            self.assertEqual(response.status_code, 200)

        for effective_from, amount in (
            (later, "30000"),
            (earlier, "900"),
            (future, "33000"),
        ):
            response = self.client.post(
                f"/employees/{first_id}/salary",
                data={
                    "effective_from": effective_from.isoformat(),
                    "salary_basis": (
                        "daily" if effective_from == earlier else "monthly"
                    ),
                    "currency": "HKD",
                    "amount": amount,
                },
                follow_redirects=True,
            )
            self.assertEqual(response.status_code, 200)

        duplicate = self.client.post(
            f"/employees/{first_id}/assignment",
            data={
                "effective_from": later.isoformat(),
                "payroll_group": "management",
            },
            follow_redirects=True,
        )
        self.assertIn("已有任職記錄", duplicate.get_data(as_text=True))

        with self.app.app_context():
            employee = db.session.get(Employee, first_id)
            assignments = sorted(
                EmployeeAssignment.query.filter_by(
                    employee_id=first_id,
                    status="active",
                ).all(),
                key=lambda item: item.effective_from,
            )
            salaries = sorted(
                EmployeeSalary.query.filter_by(
                    employee_id=first_id,
                    status="active",
                ).all(),
                key=lambda item: item.effective_from,
            )
            self.assertEqual(len(assignments), 3)
            self.assertEqual(
                assignments[0].effective_to,
                later - timedelta(days=1),
            )
            self.assertEqual(
                assignments[1].effective_to,
                future - timedelta(days=1),
            )
            self.assertIsNone(assignments[2].effective_to)
            self.assertEqual(employee.current_assignment.payroll_group, "site_monthly")
            self.assertEqual(employee.payroll_group, "site_monthly")
            self.assertEqual(salaries[0].effective_to, later - timedelta(days=1))
            self.assertEqual(salaries[1].effective_to, future - timedelta(days=1))
            self.assertEqual(employee.current_salary.amount, Decimal("30000.00"))
            employee_type_id = employee.employee_type_id

        added = self.client.post(
            f"/employees/{first_id}/identities",
            data={
                "identity_type": "hkid",
                "identity_number": "A123456(7)",
                "is_primary": "on",
            },
            follow_redirects=True,
        )
        self.assertEqual(added.status_code, 200)
        conflict = self.client.post(
            f"/employees/{second_id}/identities",
            data={
                "identity_type": "hkid",
                "identity_number": "a 123456-7",
                "is_primary": "on",
            },
            follow_redirects=True,
        )
        self.assertIn("已屬於", conflict.get_data(as_text=True))
        with self.app.app_context():
            self.assertEqual(
                EmployeeIdentity.query.filter_by(
                    identity_type="hkid",
                    status="active",
                ).count(),
                1,
            )

        blocked_delete = self.client.post(
            f"/references/values/{employee_type_id}/delete",
            follow_redirects=True,
        )
        self.assertIn("不能刪除", blocked_delete.get_data(as_text=True))
        with self.app.app_context():
            self.assertIsNotNone(
                db.session.get(ReferenceValue, employee_type_id)
            )

    def test_payroll_bank_details_are_separate_from_optional_document(self):
        employee_id, _ = self.create_employee(
            "HKR",
            "site_monthly",
            "銀行提示測試",
            "BANK WARNING TEST",
        )
        with self.app.app_context():
            employee = db.session.get(Employee, employee_id)
            warnings = employee_warnings(employee)
            self.assertFalse(any("銀行" in warning for warning in warnings))
            bank_item = next(
                item
                for item in employee_data_items(employee)
                if item["code"] == "bank"
            )
            self.assertFalse(bank_item["ok"])
            payroll_row = calculate_payroll("2026-07", "site_monthly")[0]
            self.assertIn("出糧銀行資料未填寫", payroll_row["blockers"])

        page = self.client.get(
            f"/employees?month=2026-07&readiness=employee_data&status=all&lang=en"
        ).get_data(as_text=True)
        self.assertIn("Payroll bank details not entered", page)
        self.assertNotIn("bank proof", page.lower())

    def test_employee_register_shows_month_effective_mpf_status_only_in_scope(self):
        employee_id, _ = self.create_employee(
            "HKR",
            "management",
            "MPF 狀態測試",
            "MPF STATUS TEST",
        )
        with self.app.app_context():
            employee = db.session.get(Employee, employee_id)
            employee.employment_periods.append(
                EmployeeEmploymentPeriod(start_date=date(2026, 1, 1))
            )
            db.session.commit()

        missing_page = self.client.get(
            "/employees?month=2026-08&status=all"
        ).get_data(as_text=True)
        self.assertIn('data-mpf-status="missing"', missing_page)
        self.assertIn("MPF 資料未填寫", missing_page)

        with self.app.app_context():
            employee = db.session.get(Employee, employee_id)
            scheme = MpfScheme.query.filter_by(code="BCOM_MONTHLY").one()
            create_mpf_enrollment(
                employee,
                date(2026, 8, 1),
                scheme=scheme,
                member_account_no="MPF-STATUS-001",
            )
            db.session.commit()

        complete_page = self.client.get(
            "/employees?month=2026-08&status=all"
        ).get_data(as_text=True)
        self.assertIn('data-mpf-status="complete"', complete_page)
        self.assertIn("MPF 資料已填寫", complete_page)
        simplified_page = self.client.get(
            "/employees?month=2026-08&status=all&lang=zh-Hans"
        ).get_data(as_text=True)
        self.assertIn("MPF 资料已填写", simplified_page)
        english_page = self.client.get(
            "/employees?month=2026-08&status=all&lang=en"
        ).get_data(as_text=True)
        self.assertIn("MPF details entered", english_page)

        with self.app.app_context():
            employee = db.session.get(Employee, employee_id)
            employee.employment_periods[0].end_date = date(2026, 7, 31)
            db.session.commit()

        departed_page = self.client.get(
            "/employees?month=2026-08&status=all"
        ).get_data(as_text=True)
        self.assertNotIn("data-mpf-status=", departed_page)
        self.assertNotIn("MPF 資料已填寫", departed_page)
        self.assertNotIn("MPF 資料未填寫", departed_page)

    def test_record_editors_use_shared_dialogs(self):
        def read_tpl(name):
            return self.app.jinja_loader.get_source(self.app.jinja_env, name)[0]

        employee_template = read_tpl("employees/detail.html")
        leave_template = read_tpl("leave/index.html")
        change_history_template = read_tpl("employees/_change_history.html")
        combined = employee_template + change_history_template + leave_template

        self.assertNotIn("floating-editor", combined)
        self.assertNotIn("details class=\"row-editor\"", combined)
        self.assertGreaterEqual(combined.count("record-editor-form"), 20)
        self.assertIn("data-record-editor-trigger", combined)

    def test_employee_change_history_is_unified_without_duplicate_timeline(self):
        employee_id, _ = self.create_employee(
            "ASMTP",
            "management",
            "變更歷史測試",
            "CHANGE HISTORY TEST",
        )
        self.complete_employee(
            employee_id,
            "management",
            "TMC046",
            "monthly",
            "20000",
            "A1234567",
            "61234567",
        )

        page = self.client.get(
            f"/employees/{employee_id}?tab=employment"
        ).get_data(as_text=True)

        employment_panel = page.split(
            'data-panel="employment"', 1
        )[1].split('data-panel="credentials"', 1)[0]
        self.assertIn('class="dense-table change-history-table"', employment_panel)
        self.assertEqual(employment_panel.count('class="flag change-kind '), 4)
        self.assertEqual(employment_panel.count('class="record-audit-summary"'), 2)
        self.assertIn("2026-01-01", employment_panel)
        self.assertIn("HKD 20,000.00", employment_panel)
        self.assertIn("管理人員及總部人員", employment_panel)
        self.assertNotIn('class="panel profile-timeline"', employment_panel)
        self.assertNotIn('class="panel domain-timeline"', employment_panel)

    def test_profile_tabs_use_current_cards_scoped_editing_and_histories(self):
        employee_id, _ = self.create_employee(
            "ASMTP",
            "management",
            "統一介面測試",
            "UNIFIED PROFILE TEST",
        )
        with self.app.app_context():
            employee = db.session.get(Employee, employee_id)
            employee.education_level = "Bachelor"
            employee.major = "Engineering"
            employee.graduation_school = "Original School"
            employee.visa_required = True
            db.session.commit()

        response = self.client.post(
            f"/employees/{employee_id}/personal",
            data={
                "profile_revision": current_profile_revision(self.app, employee_id, "profile"),
                "form_scope": "profile",
                "gender": "male",
                "mobile_region_code": "+852",
                "mobile_number": "61230000",
                "email": "profile@example.com",
                "residential_address": "Updated address",
                "emergency_contact_name": "Emergency Person",
                "emergency_contact_region_code": "+852",
                "emergency_contact_phone": "61239999",
                "emergency_contact_relation": "Family",
                "remarks": "Current profile",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            employee = db.session.get(Employee, employee_id)
            self.assertEqual(employee.education_level, "Bachelor")
            self.assertEqual(employee.graduation_school, "Original School")
            self.assertTrue(employee.visa_required)
            self.assertEqual(employee.mobile_number, "61230000")

        response = self.client.post(
            f"/employees/{employee_id}/personal",
            data={
                "profile_revision": current_profile_revision(self.app, employee_id, "education"),
                "form_scope": "education",
                "education_level": "Master",
                "major": "Construction",
                "graduation_school": "Updated School",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            employee = db.session.get(Employee, employee_id)
            self.assertEqual(employee.mobile_number, "61230000")
            self.assertEqual(employee.education_level, "Master")
            self.assertTrue(
                AuditLog.query.filter_by(
                    employee_id=employee_id,
                    action="education_background_updated",
                ).first()
            )

        page = self.client.get(
            f"/employees/{employee_id}?tab=personal"
        ).get_data(as_text=True)
        self.assertIn("個人資料", page)
        self.assertIn('data-dialog-open="edit-personal-dialog"', page)
        self.assertIn('class="panel history-disclosure" open', page)
        self.assertIn("<h2>變更歷史</h2>", page)
        self.assertIn('class="dense-table profile-history-table"', page)

        credentials = self.client.get(
            f"/employees/{employee_id}?tab=credentials"
        ).get_data(as_text=True)
        self.assertIn("<h2>變更歷史</h2>", credentials)
        self.assertNotIn("profile-credential-history", credentials)
        self.assertIn("Updated School", credentials)
        self.assertIn('data-dialog-open="education-editor-dialog"', credentials)

        status = self.client.get(
            f"/employees/{employee_id}?tab=employment_status"
        ).get_data(as_text=True)
        self.assertIn('class="dense-table change-history-table"', status)
        self.assertIn('data-dialog-open="termination-editor-dialog"', status)
        self.assertNotIn('details class="action-panel"', status)

        documents = self.client.get(
            f"/employees/{employee_id}?tab=documents"
        ).get_data(as_text=True)
        self.assertIn('class="dense-table document-library-table"', documents)

    def test_record_corrections_and_withdrawals(self):
        employee_id, employee_no = self.create_employee(
            "HKR",
            "site_monthly",
            "修正流程測試",
            "CORRECTION TEST",
        )
        self.complete_employee(
            employee_id,
            "site_monthly",
            "TMC046",
            "monthly",
            "30000",
            "WRONG-HKID",
            "63330001",
        )
        with self.app.app_context():
            identity = EmployeeIdentity.query.filter_by(
                employee_id=employee_id,
                status="active",
            ).one()
            identity_id = identity.id
            certificate_type_id = reference_by_code(
                "certificate_type",
                "SAFETY_CARD",
            ).id
            visa_category_id = reference_by_code(
                "visa_category",
                "ASMTP",
            ).id

        response = self.client.post(
            f"/identities/{identity_id}/update",
            data={
                "identity_type": "hkid",
                "identity_number": "A1234567",
                "is_primary": "on",
                "is_long_term": "on",
                "remarks": "更正測試",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("身份證件資料已更正", response.get_data(as_text=True))

        response = self.client.post(
            f"/employees/{employee_id}/certificates",
            data={
                "certificate_type_id": certificate_type_id,
                "certificate_no": "GREEN-WRONG",
                "valid_from": "2026-01-01",
                "expiry_date": "2027-01-01",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            certificate_id = EmployeeCertificate.query.filter_by(
                employee_id=employee_id
            ).one().id
        response = self.client.post(
            f"/certificates/{certificate_id}/update",
            data={
                "certificate_type_id": certificate_type_id,
                "certificate_no": "GREEN-CORRECT",
                "valid_from": "2026-02-01",
                "expiry_date": "2027-02-01",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        response = self.client.post(
            f"/certificates/{certificate_id}/void",
            data={"reason": "整筆測試資料錯誤"},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)

        response = self.client.post(
            f"/employees/{employee_id}/visas",
            data={
                "visa_category_id": visa_category_id,
                "visa_no": "VISA-QA",
                "issue_date": "2026-01-01",
                "expiry_date": "2027-01-01",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        response = self.client.post(
            f"/employees/{employee_id}/qualifications",
            data={
                "category": "skill",
                "qualification_name": "測試技能證書",
                "certificate_no": "SKILL-QA",
                "issue_date": "2026-01-01",
                "expiry_date": "2028-01-01",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)

        response = self.client.post(
            f"/annual-leave/{employee_id}/balance",
            data={
                "year": "2026",
                "entitled_days": "8.5",
                "legacy_days": "1.5",
                "remarks": "HR 確認",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            balance = EmployeeAnnualLeaveBalance.query.filter_by(
                employee_id=employee_id,
                year=2026,
            ).one()
            self.assertEqual(balance.entitled_days_override, Decimal("8.5"))
            legacy = EmployeeAnnualLeaveBalance.query.filter_by(
                employee_id=employee_id,
                year=2023,
            ).one()
            self.assertEqual(legacy.entitled_days_override, Decimal("1.5"))

        with self.app.app_context():
            audit = AuditLog.query.filter_by(
                action="identity_corrected"
            ).one()
            self.assertEqual(
                audit.before_json["identity_number"],
                "WRONG-HKID",
            )
            self.assertEqual(
                audit.after_json["identity_number"],
                "A1234567",
            )
            self.assertEqual(
                db.session.get(EmployeeCertificate, certificate_id).status,
                "voided",
            )

        page = self.client.get(
            f"/employees/{employee_id}?tab=credentials"
        ).get_data(as_text=True)
        self.assertIn("A1234567", page)
        self.assertIn("WRONG-HKID", page)
        self.assertIn("GREEN-CORRECT", page)
        self.assertIn("修正", page)
        self.assertIn("作廢", page)
        leave_page = self.client.get(
            f"/annual-leave?year=2026&employee_id={employee_id}"
        ).get_data(as_text=True)
        self.assertIn(employee_no, leave_page)
        self.assertIn('value="8.5"', leave_page)

    def test_effective_records_can_be_corrected_or_withdrawn(
        self,
    ):
        employee_id, _ = self.create_employee(
            "HKR",
            "site_monthly",
            "任職薪酬修正測試",
            "EMPLOYMENT CORRECTION",
        )
        self.complete_employee(
            employee_id,
            "site_monthly",
            "TMC046",
            "monthly",
            "30000",
            "CORRECT1001",
            "63330002",
        )
        with self.app.app_context():
            employee = db.session.get(Employee, employee_id)
            assignment = employee.current_assignment
            salary = employee.current_salary
            assignment_id = assignment.id
            salary_id = salary.id
            alternate_project_id = WorkProject.query.filter_by(
                code="PC_AD014"
            ).one().id
            original_project_id = assignment.project_id
            assignment_form = {
                "effective_from": "2026-02-15",
                "region_id": assignment.region_id,
                "project_id": alternate_project_id,
                "department_id": assignment.department_id,
                "position_ids": [
                    str(item.position_id) for item in assignment.positions
                ],
                "employer_id": assignment.employer_id,
                "payroll_entity_id": assignment.payroll_entity_id,
                "social_insurance_entity_id": (
                    assignment.social_insurance_entity_id
                ),
                "labour_dispatch_entity_id": (
                    assignment.labour_dispatch_entity_id
                ),
                "payroll_group": assignment.payroll_group,
                "remarks": "修正錯誤項目及生效日期",
            }

        response = self.client.post(
            f"/assignments/{assignment_id}/correct",
            data=assignment_form,
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("任職記錄已更正", response.get_data(as_text=True))
        response = self.client.post(
            f"/salaries/{salary_id}/correct",
            data={
                "effective_from": "2026-02-15",
                "salary_basis": "monthly",
                "currency": "HKD",
                "amount": "32,000.00",
                "remarks": "修正錯誤薪酬及生效日期",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("薪酬記錄已更正", response.get_data(as_text=True))

        with self.app.app_context():
            employee = db.session.get(Employee, employee_id)
            assignment = db.session.get(
                type(employee.assignments[0]),
                assignment_id,
            )
            salary = db.session.get(type(employee.salaries[0]), salary_id)
            self.assertEqual(assignment.effective_from, date(2026, 2, 15))
            self.assertEqual(assignment.project_id, alternate_project_id)
            self.assertEqual(salary.effective_from, date(2026, 2, 15))
            self.assertEqual(salary.amount, Decimal("32000.00"))
            assignment_audit = AuditLog.query.filter_by(
                action="assignment_corrected"
            ).one()
            salary_audit = AuditLog.query.filter_by(
                action="salary_corrected"
            ).one()
            self.assertEqual(
                assignment_audit.before_json["project_id"],
                original_project_id,
            )
            self.assertEqual(
                assignment_audit.after_json["project_id"],
                alternate_project_id,
            )
            self.assertEqual(
                salary_audit.before_json["amount"],
                "30000.00",
            )
            self.assertEqual(
                salary_audit.after_json["amount"],
                "32000.00",
            )
        employment_page = self.client.get(
            f"/employees/{employee_id}?tab=employment"
        ).get_data(as_text=True)
        self.assertIn("更正任職記錄", employment_page)
        self.assertIn("TMC046 醫管局項目", employment_page)
        self.assertIn("PC AD014", employment_page)
        self.assertIn("更正薪酬記錄", employment_page)
        self.assertIn("30000.00", employment_page)
        self.assertIn("32000.00", employment_page)

        response = self.client.post(
            f"/salaries/{salary_id}/withdraw",
            data={"reason": "整筆薪酬記錄不應存在"},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        response = self.client.post(
            f"/assignments/{assignment_id}/withdraw",
            data={"reason": "整筆任職記錄不應存在"},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            employee = db.session.get(Employee, employee_id)
            self.assertIsNone(employee.current_assignment)
            self.assertIsNone(employee.current_salary)
            self.assertEqual(
                AuditLog.query.filter_by(
                    action="assignment_withdrawn"
                ).count(),
                1,
            )
            self.assertEqual(
                AuditLog.query.filter_by(action="salary_withdrawn").count(),
                1,
            )

    def test_hard_delete_removes_attendance_and_payroll_orphans(self):
        employee_id, employee_no = self.create_employee(
            "HKRD",
            "site_daily",
            "刪除關聯測試",
            "DELETE RELATIONS",
        )
        project_id = self.complete_employee(
            employee_id,
            "site_daily",
            "TMC046",
            "daily",
            "800",
            "DEL10001",
            "64440001",
            mpf_mode="casual",
        )
        self.add_attendance([(employee_id, project_id)])
        response = self.client.post(
            "/payroll/export-current",
            data={
                "year_month": "2026-07",
                "payroll_group": "site_daily",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            batch_id = AttendanceBatch.query.one().id
            summary_id = AttendanceMonthlySummary.query.one().id
            run_id = PayrollRun.query.one().id
            upload_folder = (
                Path(self.app.config["HKR_HR_UPLOAD_ROOT"])
                / employee_no
            )
            self.assertTrue(upload_folder.exists())

        self.client.post("/logout")
        self.login("hr_test", "test-hr-password")
        denied = self.client.post(
            f"/employees/{employee_id}/delete",
            data={"confirm_employee_no": employee_no},
        )
        self.assertEqual(denied.status_code, 403)
        with self.app.app_context():
            self.assertIsNotNone(db.session.get(Employee, employee_id))
        self.client.post("/logout")
        self.login("admin", "test-admin-password")

        response = self.client.post(
            f"/employees/{employee_id}/delete",
            data={"confirm_employee_no": employee_no},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("考勤及工資表資料已全部刪除", response.get_data(as_text=True))
        with self.app.app_context():
            self.assertIsNone(db.session.get(Employee, employee_id))
            self.assertIsNone(
                db.session.get(AttendanceMonthlySummary, summary_id)
            )
            self.assertIsNone(db.session.get(AttendanceBatch, batch_id))
            self.assertIsNone(db.session.get(PayrollRun, run_id))
            self.assertEqual(
                AttendanceBatchItem.query.filter_by(
                    employee_id=employee_id
                ).count(),
                0,
            )
            self.assertEqual(
                PayrollEmployeeResult.query.filter_by(
                    employee_id=employee_id
                ).count(),
                0,
            )
            self.assertFalse(upload_folder.exists())
        attendance_page = self.client.get(
            "/attendance?month=2026-07"
        ).get_data(as_text=True)
        payroll_page = self.client.get(
            "/attendance-payroll"
            "?year_month=2026-07&payroll_group=site_daily"
        ).get_data(as_text=True)
        self.assertNotIn(employee_no, attendance_page)
        self.assertNotIn(employee_no, payroll_page)

    def test_fixed_allowances_reject_daily_workers_and_show_daily_rate_rule(self):
        daily_id, _ = self.create_employee(
            "HKRD",
            "site_daily",
            "日工補貼限制",
            "DAILY ALLOWANCE BLOCK",
        )
        monthly_id, _ = self.create_employee(
            "HKR",
            "site_monthly",
            "月工補貼提示",
            "MONTHLY ALLOWANCE NOTE",
        )
        self.complete_employee(
            daily_id,
            "site_daily",
            "TMC046",
            "daily",
            "500",
            "QA-DAILY-ALLOWANCE",
            "61110103",
            mpf_mode="casual",
        )
        self.complete_employee(
            monthly_id,
            "site_monthly",
            "TMC046",
            "monthly",
            "30000",
            "QA-MONTHLY-ALLOWANCE",
            "61110104",
        )
        response = self.client.post(
            f"/employees/{daily_id}/allowances",
            data={
                "allowance_type": "meal",
                "effective_from": "2026-08-01",
                "amount": "60",
                "currency": "HKD",
            },
            follow_redirects=True,
        )
        self.assertIn(
            "固定補貼目前只支持月工及 OFFICE，不支持日工",
            response.get_data(as_text=True),
        )
        with self.app.app_context():
            self.assertEqual(
                EmployeeAllowance.query.filter_by(employee_id=daily_id).count(),
                0,
            )

        daily_profile = self.client.get(
            f"/employees/{daily_id}?tab=employment&lang=zh-Hant"
        ).get_data(as_text=True)
        self.assertIn("固定補貼目前只支持月工及 OFFICE", daily_profile)
        self.assertNotIn('data-dialog-open="add-allowance-dialog"', daily_profile)
        monthly_profile = self.client.get(
            f"/employees/{monthly_id}?tab=employment&lang=zh-Hant"
        ).get_data(as_text=True)
        self.assertIn("每日金額 × 計薪曆日", monthly_profile)
        self.assertIn('data-dialog-open="add-allowance-dialog"', monthly_profile)
        self.assertIn("餐補／交通補貼為每日金額", monthly_profile)

    def test_new_employee_can_start_with_long_term_attendance_exemption(self):
        with self.app.app_context():
            employee_type_id = employee_type_by_code("HKR").id
        new_page = self.client.get("/employees/new?lang=en").get_data(
            as_text=True
        )
        self.assertIn("Monthly attendance record required", new_page)
        self.assertIn("Attendance is required by default", new_page)

        response = self.client.post(
            "/employees/new?lang=en",
            data={
                "employee_type_id": employee_type_id,
                "payroll_group": "management",
                "chinese_name": "長期免交新員工",
                "english_name": "NEW LONG TERM EXEMPT",
                "requires_attendance": "0",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        page = response.get_data(as_text=True)
        self.assertIn("Long-term exempt", page)
        with self.app.app_context():
            employee = Employee.query.filter_by(
                english_name="NEW LONG TERM EXEMPT"
            ).one()
            policy = EmployeeAttendancePolicy.query.filter_by(
                employee_id=employee.id
            ).one()
            self.assertFalse(policy.requires_attendance)


if __name__ == "__main__":
    unittest.main()
