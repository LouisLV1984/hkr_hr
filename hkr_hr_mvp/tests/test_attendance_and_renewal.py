import io
import unittest
from datetime import date, timedelta

import test_audit_integrity as fixture
from test_v1_workflows import pdf_bytes
from models import db, AttendanceBatchItem, AttendanceMonthlySummary, EmployeeCertificate
from tools.hr_core import reference_by_code
from tools.profile_integrity import credential_alerts, credential_state


class AttendanceAndRenewalTests(unittest.TestCase):
    setUp = fixture.AuditIntegrityTests.setUp
    tearDown = fixture.AuditIntegrityTests.tearDown
    login = fixture.AuditIntegrityTests.login
    employee = fixture.AuditIntegrityTests.employee
    create_employee = fixture.AuditIntegrityTests.create_employee
    complete_employee = fixture.AuditIntegrityTests.complete_employee

    def test_new_pdf_needs_original_id_and_old_forms_cannot_change_replacement(self):
        employee, project = self.employee()
        items = []
        month = "2026-08"
        for filename in ("original.pdf", "revision.pdf"):
            self.client.post("/attendance/batches", data={
                "year_month": month, "files": (io.BytesIO(pdf_bytes(filename)), filename)})
            with self.app.app_context():
                items.append(AttendanceBatchItem.query.order_by(AttendanceBatchItem.id.desc()).first().id)
        form = dict(year_month=month, employee_id=employee, current_1_20_project_id=project,
                    current_1_20_working_days="1", current_1_20_ot_hours="2")
        self.client.post(f"/attendance/items/{items[0]}/save", data=form)
        with self.app.app_context():
            summary = AttendanceMonthlySummary.query.filter_by(employee_id=employee, year_month=month).one()
            original, summary_id = summary.document_id, summary.id
        form["current_1_20_ot_hours"] = "0"
        for stale_id in ("", "999999"):
            self.client.post(f"/attendance/items/{items[1]}/save", data={**form, "replace_document_id": stale_id})
            with self.app.app_context():
                self.assertEqual(db.session.get(AttendanceBatchItem, items[1]).status, "pending")
                self.assertEqual(db.session.get(AttendanceMonthlySummary, summary_id).document_id, original)
        self.client.post(f"/attendance/items/{items[1]}/save", data={**form, "replace_document_id": original})
        self.client.post(f"/attendance/summaries/{summary_id}/correct", data={
            **form, "editing_document_id": original, "current_1_20_ot_hours": "8"})
        with self.app.app_context():
            old = db.session.get(AttendanceBatchItem, items[0])
            self.assertEqual(old.status, "replaced")
            self.assertEqual(float(old.archived_summary["segments"][0]["ot_hours"]), 2)
            summary = db.session.get(AttendanceMonthlySummary, summary_id)
            self.assertNotEqual(summary.document_id, original)
            self.assertFalse(any(s.ot_hours for s in summary.segments))
            # Simulate a batch saved on the previous version. The old audit
            # snapshot can identify this file without borrowing current figures.
            old.archived_summary = None
            db.session.commit()
        history = self.client.get(f"/attendance?item_id={items[0]}").get_data(as_text=True)
        self.assertRegex(history, r"OT 2(?:\.0+)? h")

    def test_renewal_changes_only_named_reminder_on_its_effective_date(self):
        employee, _ = self.employee()
        today = date.today()
        tomorrow = today + timedelta(days=1)
        with self.app.app_context():
            kind = reference_by_code("certificate_type", "WORKER_REGISTRATION").id
        url = f"/employees/{employee}/certificates"
        for number in ("A", "B"):
            self.client.post(url, data=dict(certificate_type_id=kind, certificate_no=number,
                                            expiry_date=(today + timedelta(days=10)).isoformat()))
        with self.app.app_context():
            old, other = [row.id for row in EmployeeCertificate.query.filter_by(employee_id=employee).order_by(EmployeeCertificate.id)]
        self.client.post(url, data=dict(certificate_type_id=kind, certificate_no="A2",
                                       renews_id=old, valid_from=tomorrow.isoformat(),
                                       expiry_date=(tomorrow + timedelta(days=730)).isoformat()))
        with self.app.app_context():
            source = db.session.get(EmployeeCertificate, old)
            self.assertEqual(credential_state(source, today)["code"], "expiring")
            self.assertEqual(credential_state(source, tomorrow)["code"], "renewed")
            alerts = {row["anchor"] for row in credential_alerts(tomorrow)}
            self.assertNotIn(f"credential-certificate-{old}", alerts)
            self.assertIn(f"credential-certificate-{other}", alerts)
