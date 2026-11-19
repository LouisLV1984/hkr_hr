"""Progressive employee editors: isolated synthetic records, no runtime data."""
from test_v1_workflows import current_profile_revision, pdf_bytes
import io
import unittest
import re
from datetime import date, timedelta
from decimal import Decimal

import test_profile_integrity as integrity
from models import (
    db,
    Employee,
    EmployeeAssignment,
    EmployeeCertificate,
    EmployeeSalary,
    PayrollEmployeeResult,
    PayrollRun,
)
from tools.hr_core import reference_by_code


class ProfileWorkspaceTests(unittest.TestCase):
    setUp = integrity.ProfileIntegrityTests.setUp
    tearDown = integrity.ProfileIntegrityTests.tearDown
    login = integrity.ProfileIntegrityTests.login
    create_employee = integrity.ProfileIntegrityTests.create_employee
    employee = integrity.ProfileIntegrityTests.employee
    document = integrity.ProfileIntegrityTests.document
    enhanced = {"X-HKR-Profile-Editor": "1"}

    def test_history_separates_effective_start_and_end_without_changing_records(self):
        eid = self.employee()
        with self.app.app_context():
            row = EmployeeSalary(employee_id=eid, effective_from=date(2022, 9, 19),
                effective_to=date(2025, 12, 31), salary_basis="monthly", currency="HKD", amount=15000)
            db.session.add(row); db.session.commit(); rid = row.id
        page = self.client.get(f"/employees/{eid}?tab=employment").get_data(as_text=True)
        history = page.split('<table class="dense-table change-history-table">', 1)[1].split('</table>', 1)[0]
        row = re.search(r'<tr class="" data-record-context>(.*?)</tr>', history, re.S).group(1)
        cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.S)
        self.assertIn('2022-09-19', cells[0])
        self.assertNotIn('2025-12-31', cells[0])
        self.assertIn('history-effective-end', cells[2])
        self.assertIn('2025-12-31', cells[2])
        self.assertNotIn('<td class="effective-period-cell">', history)
        self.assertNotIn('<td class="change-content-cell">', history)
        with self.app.app_context():
            self.assertEqual(db.session.get(EmployeeSalary, rid).effective_to, date(2025, 12, 31))

    def test_library_has_one_file_list_and_neutral_counts(self):
        eid = self.employee()
        self.document(eid)
        page = self.client.get(f"/employees/{eid}?tab=documents").get_data(as_text=True)
        library = page.split('data-document-library>', 1)[1].split('</section>', 1)[0]
        self.assertNotIn('document-card-grid', library)
        self.assertNotIn('doc-card missing', library)
        self.assertIn('data-document-filter="staff_record"', library)
        self.assertIn('data-document-category="staff_record"', library)
        self.assertEqual(library.count('>A.pdf</a>'), 1)
        self.assertIn('<details class="document-file-details">', library)
        self.assertIn('data-library-empty hidden', library)

    def test_script_scoped_to_employee_editors(self):
        eid = self.employee()
        for path in (f"/employees/{eid}", "/employees/new", f"/employees/{eid}/documents/new"):
            self.assertIn('data-profile-workspace', self.client.get(path).get_data(as_text=True))
        for path in ("/employees", "/attendance", "/payroll", "/login"):
            self.assertNotIn('data-profile-workspace', self.client.get(path).get_data(as_text=True))
        did = self.document(eid)
        self.assertIn('data-profile-workspace', self.client.get(f"/documents/{did}/review").get_data(as_text=True))

    def test_enhanced_validation_preserves_native_contract(self):
        eid = self.employee()
        path = f"/employees/{eid}/bank-accounts"
        # Resolve the actual action from the rendered owning form.
        page = self.client.get(f"/employees/{eid}").get_data(as_text=True)
        import re
        path = re.search(r'id="add-bank-dialog".*?action="([^"]+)"', page).group(1)
        response = self.client.post(path, data={}, headers=self.enhanced)
        self.assertEqual(response.status_code, 422)
        self.assertTrue(response.json["errors"])
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        native = self.client.post(path, data={})
        self.assertEqual(native.status_code, 302)

    def test_success_keeps_flash_for_destination_and_changes_once(self):
        eid = self.employee()
        path = f"/employees/{eid}/personal"
        response = self.client.post(path, data={"profile_revision": current_profile_revision(self.app, eid, "profile"), "form_scope": "profile", "residential_address": "QA address"}, headers=self.enhanced)
        self.assertEqual(response.status_code, 200)
        self.assertIn("redirect", response.json)
        page = self.client.get(response.json["redirect"]).get_data(as_text=True)
        self.assertIn('flash-success', page)
        with self.app.app_context():
            self.assertEqual(db.session.get(Employee, eid).residential_address, "QA address")

    def test_expired_session_returns_login_without_mutation(self):
        eid = self.employee()
        self.client.get('/logout')
        with self.client.session_transaction() as session:
            session.clear()
        response = self.client.post(f"/employees/{eid}/personal", data={"residential_address": "SHOULD NOT SAVE"}, headers=self.enhanced)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json["redirect"].startswith('/login'))
        with self.app.app_context():
            self.assertNotEqual(db.session.get(Employee, eid).residential_address, "SHOULD NOT SAVE")

    def test_v075_profile_layout_and_links_contract(self):
        eid = self.employee()
        did = self.document(eid, "staff_record")
        with self.app.app_context():
            assignment = EmployeeAssignment(
                employee_id=eid,
                effective_from=date(2026, 1, 1),
                payroll_group="management",
                workweek_days=Decimal("5.0"),
            )
            salary = EmployeeSalary(
                employee_id=eid,
                effective_from=date(2026, 1, 1),
                salary_basis="monthly",
                currency="HKD",
                amount=Decimal("20000"),
                evidence_document_id=did,
            )
            db.session.add_all([assignment, salary])
            run = PayrollRun(year_month="2026-08", payroll_group="management", rule_version="V0.7.5")
            db.session.add(run)
            db.session.flush()
            db.session.add(
                PayrollEmployeeResult(
                    run_id=run.id,
                    employee_id=eid,
                    currency="HKD",
                    gross_amount=Decimal("0"),
                    employee_mpf=Decimal("300"),
                    net_amount=Decimal("-300"),
                )
            )
            db.session.commit()
            aid = assignment.id

        page = self.client.get(f"/employees/{eid}?lang=zh-Hant").get_data(as_text=True)
        self.assertIn('class="hr-back"', page)
        self.assertIn('class="flag danger flag-link"', page)
        self.assertNotIn('class="panel initial-setup"', page)
        self.assertEqual(page.count('data-dialog-open="edit-personal-dialog"'), 1)
        self.assertIn('class="panel current-state-card span-wide"', page)
        self.assertNotIn("compact-upload", page)
        self.assertIn(f'data-dialog-open="supplement-employment-evidence-{aid}"', page)
        self.assertIn(f'id="supplement-employment-evidence-{aid}"', page)
        self.assertIn("data-document-empty-filters", page)
        self.assertIn("is-negative", page)
        self.assertIn("實發為負數，請核對", page)

        upload = self.client.post(
            f"/assignments/{aid}/evidence",
            data={"evidence": (io.BytesIO(pdf_bytes("A")), "ev.pdf")},
            follow_redirects=False,
        )
        self.assertEqual(upload.status_code, 302)
        with self.app.app_context():
            self.assertIsNotNone(db.session.get(EmployeeAssignment, aid).evidence_document_id)

    def test_v075_onboarding_setup_still_shows_before_assignment_and_salary(self):
        eid = self.employee()
        page = self.client.get(f"/employees/{eid}?lang=zh-Hant").get_data(as_text=True)
        self.assertIn('class="panel initial-setup"', page)

    def test_v076_unified_history_disclosures_across_tabs(self):
        eid = self.employee()
        self.document(eid, "staff_record")
        with self.app.app_context():
            db.session.add(
                EmployeeAssignment(
                    employee_id=eid,
                    effective_from=date(2026, 1, 1),
                    payroll_group="management",
                    workweek_days=Decimal("5.0"),
                )
            )
            db.session.add(
                EmployeeSalary(
                    employee_id=eid,
                    effective_from=date(2026, 1, 1),
                    salary_basis="monthly",
                    currency="HKD",
                    amount=Decimal("20000"),
                )
            )
            db.session.commit()

        page = self.client.get(f"/employees/{eid}?lang=zh-Hant").get_data(as_text=True)
        personal_panel = page.split('data-panel="personal">', 1)[1].split(
            'data-panel="employment"', 1
        )[0]
        employment_panel = page.split('data-panel="employment"', 1)[1].split(
            'data-panel="credentials"', 1
        )[0]
        credentials_panel = page.split('data-panel="credentials"', 1)[1].split(
            'data-panel="leave"', 1
        )[0]
        leave_panel = page.split('data-panel="leave"', 1)[1].split(
            'data-panel="attendance"', 1
        )[0]
        attendance_panel = page.split('data-panel="attendance"', 1)[1]

        self.assertEqual(personal_panel.count('class="panel history-disclosure" open'), 1)
        self.assertIn("<h2>變更歷史</h2>", personal_panel)

        self.assertEqual(employment_panel.count('class="panel history-disclosure" open'), 1)
        self.assertEqual(employment_panel.count("<table "), 1)
        self.assertLess(
            employment_panel.index('id="employment-status"'),
            employment_panel.index('class="panel history-disclosure" open'),
        )
        self.assertIn('class="flag change-kind employment_status"', employment_panel)

        self.assertNotIn("profile-credential-history", credentials_panel)
        self.assertEqual(credentials_panel.count('class="panel history-disclosure" open'), 1)
        self.assertLess(
            credentials_panel.index('id="file-library"'),
            credentials_panel.index('class="panel history-disclosure" open'),
        )
        self.assertIn("<h2>變更歷史</h2>", credentials_panel)

        self.assertEqual(leave_panel.count('class="panel history-disclosure" open'), 1)
        self.assertIn("<h2>假期與工傷紀錄</h2>", leave_panel)

        self.assertIn(
            'class="panel history-disclosure payroll-adjustment-panel" id="legacy-adjustments" open',
            attendance_panel,
        )

    def test_v077_cross_module_ui_fixes(self):
        eid = self.employee()
        expiring_on = date.today() + timedelta(days=15)
        with self.app.app_context():
            run = PayrollRun(year_month="2026-08", payroll_group="management", rule_version="V0.7.7")
            db.session.add(run)
            db.session.flush()
            db.session.add(
                PayrollEmployeeResult(
                    run_id=run.id,
                    employee_id=eid,
                    currency="HKD",
                    gross_amount=Decimal("20000"),
                    employee_mpf=Decimal("1000"),
                    net_amount=Decimal("19000"),
                )
            )
            db.session.add(
                EmployeeCertificate(
                    employee_id=eid,
                    certificate_type_id=reference_by_code("certificate_type", "SAFETY_CARD").id,
                    certificate_no="SC-077",
                    expiry_date=expiring_on,
                )
            )
            db.session.commit()

        attendance_page = self.client.get("/attendance?lang=zh-Hant").get_data(as_text=True)
        self.assertIn('input[type="file"]:not([data-attendance-file-input])', attendance_page)
        self.assertLess(attendance_page.index("<h1>考勤收集</h1>"), attendance_page.index('class="intake-desk"'))
        workbench_head = attendance_page.split('class="page-head compact workbench-head">', 1)[1].split(
            "</section>", 1
        )[0]
        self.assertIn("intake-missing", workbench_head)

        injury_list_en = self.client.get("/annual-leave?view=injury&lang=en").get_data(as_text=True)
        self.assertIn("Work injury management", injury_list_en)
        injury_detail_en = self.client.get(
            f"/annual-leave?view=injury&employee_id={eid}&lang=en"
        ).get_data(as_text=True)
        self.assertIn('class="app-dialog record-editor-dialog" id="new-work-injury"', injury_detail_en)
        self.assertIn("Medical claim history", injury_detail_en)
        self.assertIn('class="panel history-disclosure" open', injury_detail_en)

        detail_page = self.client.get(f"/employees/{eid}?lang=zh-Hant").get_data(as_text=True)
        attendance_panel = detail_page.split('data-panel="attendance"', 1)[1]
        self.assertIn("已保存工資表快照", attendance_panel)
        self.assertIn("尚無月度考勤單紀錄；下方為已保存工資表快照。", attendance_panel)
        self.assertNotIn("暫無考勤與工資紀錄。", attendance_panel)

        dashboard_page = self.client.get("/dashboard?lang=zh-Hant").get_data(as_text=True)
        self.assertIn("history-disclosure-chevron", dashboard_page)
        self.assertIn(expiring_on.strftime("%Y/%m/%d"), dashboard_page)


if __name__ == "__main__":
    unittest.main()
