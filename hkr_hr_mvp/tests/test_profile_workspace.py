"""Progressive employee editors: isolated synthetic records, no runtime data."""
from test_v1_workflows import current_profile_revision, pdf_bytes
import io
import unittest
import re
from datetime import date
from decimal import Decimal

import test_profile_integrity as integrity
from models import (
    db,
    Employee,
    EmployeeAssignment,
    EmployeeSalary,
    PayrollEmployeeResult,
    PayrollRun,
)


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


if __name__ == "__main__":
    unittest.main()
