"""Employee-management audit H1-H5 / M1-M4, isolated synthetic fixtures only."""
import io
import json
import unittest
from datetime import date, timedelta
from decimal import Decimal

import test_v1_workflows as workflow
from models import (db, Employee, EmployeeDocument, EmployeeEmploymentPeriod,
                    EmployeeIdentity, EmployeeCertificate, EmployeeQualification,
                    EmployeeAnnualLeaveRecord, EmployeeAllowance, AuditLog)
from tools.hr_core import reference_by_code
from tools.profile_integrity import credential_state, credential_alerts, document_reference_count


class ProfileIntegrityTests(unittest.TestCase):
    setUp = workflow.V1WorkflowTests.setUp
    tearDown = workflow.V1WorkflowTests.tearDown
    login = workflow.V1WorkflowTests.login
    create_employee = workflow.V1WorkflowTests.create_employee

    def employee(self, suffix="A"):
        eid, _ = self.create_employee("HKR", "management", "測試" + suffix, "QA " + suffix)
        with self.app.app_context():
            db.session.add(EmployeeEmploymentPeriod(employee_id=eid, start_date=date(2026, 1, 1),
                contract_annual_leave_days=14, probation_end_date=date(2026, 3, 31)))
            db.session.commit()
        return eid

    def document(self, eid, category="staff_record", suffix="A"):
        response = self.client.post(f"/employees/{eid}/documents/new", data={
            "category": category, "file": (io.BytesIO(workflow.pdf_bytes(suffix)), suffix + ".pdf")})
        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            return EmployeeDocument.query.filter_by(employee_id=eid).order_by(EmployeeDocument.id.desc()).first().id

    def test_evidence_only_and_missing_entry(self):
        eid = self.employee()
        with self.app.app_context():
            row = EmployeeAnnualLeaveRecord(employee_id=eid, leave_date=date(2026, 8, 4),
                end_date=date(2026, 8, 4), days=1, entitlement_year=2026, leave_type="sick")
            db.session.add(row); db.session.commit(); rid = row.id
            leave_changed_at = row.updated_at
        page = self.client.get(f"/employees/{eid}?tab=leave&focus=sick_evidence").get_data(as_text=True)
        self.assertIn('id="missing-leave-evidence"', page)
        self.assertIn(f'/annual-leave/{rid}/evidence', page)
        response = self.client.post(f"/annual-leave/{rid}/evidence", data={
            "start_date": "2025-01-01", "days": "99", "leave_type": "annual",
            "evidence": (io.BytesIO(workflow.pdf_bytes("sick")), "sick.pdf")}, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            row = EmployeeAnnualLeaveRecord.query.one()
            self.assertEqual((row.leave_date, row.days, row.leave_type), (date(2026, 8, 4), Decimal(1), "sick"))
            self.assertIsNotNone(row.evidence_document_id)
            self.assertEqual(row.updated_at, leave_changed_at)
            self.assertEqual(AuditLog.query.filter_by(action="leave_evidence_added").count(), 1)
            row.status = "voided"; db.session.commit()
        self.assertEqual(self.client.post(f"/annual-leave/{rid}/evidence").status_code, 400)

    def test_contract_review_preserves_terms_and_explicit_changes_audited(self):
        eid = self.employee()
        did = self.document(eid, "signed_contract")
        page = self.client.get(f"/documents/{did}/review").get_data(as_text=True)
        self.assertIn('name="apply_contract_terms"', page)
        self.assertIn('2026-03-31', page)
        self.client.post(f"/documents/{did}/review", data={
            "contract_effective_date": "2026-02-01", "contract_annual_leave_days": "7"})
        with self.app.app_context():
            period = db.session.get(Employee, eid).current_period
            self.assertEqual(period.contract_annual_leave_days, Decimal(14))
            self.assertEqual(period.probation_end_date, date(2026, 3, 31))
        self.client.post(f"/documents/{did}/review", data={
            "apply_contract_terms": "on", "contract_effective_date": "2026-02-01",
            "contract_annual_leave_days": "16", "probation_end_date": ""})
        with self.app.app_context():
            period = db.session.get(Employee, eid).current_period
            self.assertEqual(period.contract_annual_leave_days, Decimal(16))
            self.assertEqual(period.probation_end_date, date(2026, 3, 31))
            audit = AuditLog.query.filter_by(action="document_source_updated", entity_type="EmployeeEmploymentPeriod").one()
            self.assertNotEqual(audit.before_json, audit.after_json)
        self.client.post(f"/documents/{did}/review", data={
            "apply_contract_terms": "on", "contract_effective_date": "2026-02-01",
            "contract_annual_leave_days": "-1"})
        with self.app.app_context():
            self.assertEqual(db.session.get(Employee, eid).current_period.contract_annual_leave_days, Decimal(16))

    def test_staff_record_updates_profile_hire_date_and_education_history(self):
        eid = self.employee()
        did = self.document(eid)
        response = self.client.post(f"/documents/{did}/review", data={
            "residential_address": "Synthetic address", "education_level": "Degree",
            "start_date": "2026-01-15"}, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            employee = db.session.get(Employee, eid)
            self.assertEqual(employee.residential_address, "Synthetic address")
            self.assertEqual(employee.current_period.start_date, date(2026, 1, 15))
            for action in ("personal_data_updated", "education_background_updated", "document_source_updated"):
                self.assertTrue(AuditLog.query.filter_by(action=action).count(), action)
            db.session.get(EmployeeDocument, did).status = "replaced"; db.session.commit()
        self.assertEqual(self.client.post(f"/documents/{did}/review", data={"residential_address": "bad"}).status_code, 400)
        with self.app.app_context():
            self.assertEqual(db.session.get(Employee, eid).residential_address, "Synthetic address")

    def test_identity_cross_entry_duplicate_and_existing_primary_dates(self):
        eid, other = self.employee(), self.employee("B")
        with self.app.app_context():
            db.session.add(EmployeeIdentity(employee_id=eid, identity_type="hkid",
                identity_number="A123456(7)", is_primary=True, issue_date=date(2020, 1, 1),
                expiry_date=date(2030, 1, 1)))
            db.session.commit()
        did = self.document(other, "three_treasures")
        self.client.post(f"/documents/{did}/review", data={"identity_type": "hkid", "identity_number": "A1234567", "identity_primary": "on"})
        with self.app.app_context():
            self.assertEqual(EmployeeIdentity.query.count(), 1)
        did = self.document(eid, "three_treasures", "own")
        self.client.post(f"/documents/{did}/review", data={"identity_type": "hkid", "identity_number": "A1234567", "identity_primary": "on"})
        with self.app.app_context():
            row = EmployeeIdentity.query.one()
            self.assertTrue(row.is_primary)
            self.assertEqual(row.expiry_date, date(2030, 1, 1))
            self.assertEqual(row.issue_date, date(2020, 1, 1))
        self.client.post(f"/documents/{did}/review", data={"identity_type": "hkid", "identity_number": "A1234567",
            "identity_issue_date": "2031-01-01"})
        with self.app.app_context():
            self.assertEqual(EmployeeIdentity.query.one().issue_date, date(2020, 1, 1))

    def test_credential_validation_all_entry_points(self):
        eid = self.employee()
        with self.app.app_context():
            tid = reference_by_code("certificate_type", "SAFETY_CARD").id
        base = {"certificate_type_id": tid, "certificate_no": "QA"}
        for extra in ({}, {"valid_from": "2026-03-01", "expiry_date": "2026-02-01"},
                      {"expiry_date": "2027-01-01", "is_long_term": "on"}):
            self.client.post(f"/employees/{eid}/certificates", data={**base, **extra})
        with self.app.app_context():
            self.assertEqual(EmployeeCertificate.query.count(), 0)
        did = self.document(eid, "three_treasures")
        self.client.post(f"/documents/{did}/review", data={"worker_registration_no": "bad",
            "worker_registration_valid_from": "2026-03-01", "worker_registration_expiry_date": "2026-02-01"})
        with self.app.app_context():
            self.assertEqual(EmployeeCertificate.query.count(), 0)
        self.client.post(f"/employees/{eid}/certificates", data={**base, "is_long_term": "on"})
        with self.app.app_context():
            self.assertEqual(EmployeeCertificate.query.count(), 1)

    def test_expiry_shared_state_alerts_and_legacy_category_projection(self):
        eid = self.employee()
        today = date.today()
        with self.app.app_context():
            cert = EmployeeCertificate(employee_id=eid,
                certificate_type_id=reference_by_code("certificate_type", "DEGREE").id,
                certificate_no="LEGACY-DEGREE", expiry_date=today-timedelta(days=3))
            qualification = EmployeeQualification(employee_id=eid, category="skill",
                qualification_name="QA qualification", expiry_date=today+timedelta(days=20))
            db.session.add_all([cert, qualification]); db.session.commit(); cid = cert.id
            self.assertEqual(credential_state(cert)["code"], "expired")
            alerts = credential_alerts()
            self.assertEqual(len([a for a in alerts if a["employee"].id == eid]), 2)
            self.assertIn(f"credential-certificate-{cid}", [a["anchor"] for a in alerts])
        page = self.client.get(f"/employees/{eid}?tab=credentials").get_data(as_text=True)
        self.assertIn("已到期", page)
        self.assertEqual(page.count(f'id="credential-certificate-{cid}"'), 1)
        self.assertGreater(page.index("LEGACY-DEGREE"), page.index("學歷與專業資歷"))
        with self.app.app_context():
            employee = db.session.get(Employee, eid)
            employee.current_period.end_date = today-timedelta(days=1)
            db.session.commit()
            self.assertFalse([a for a in credential_alerts() if a["employee"].id == eid])

    def test_replacement_is_one_target_and_relinks_all_typed_sources(self):
        eid = self.employee()
        first, second = self.document(eid, suffix="first"), self.document(eid, suffix="second")
        with self.app.app_context():
            db.session.add(EmployeeAllowance(employee_id=eid, allowance_type="meal", label="Meal", amount=10,
                effective_from=date(2026, 1, 1), evidence_document_id=first))
            db.session.add(EmployeeAnnualLeaveRecord(employee_id=eid, leave_date=date(2026, 8, 4),
                days=1, entitlement_year=2026, leave_type="sick", evidence_document_id=first))
            db.session.commit()
            self.assertEqual(document_reference_count(db.session.get(EmployeeDocument, first)), 2)
        response = self.client.post(f"/employees/{eid}/documents/new", data={
            "category": "staff_record", "replace_document_id": str(first), "replacement_reason": "QA correction",
            "file": (io.BytesIO(workflow.pdf_bytes("third")), "third.pdf")})
        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            old = db.session.get(EmployeeDocument, first)
            self.assertEqual(old.status, "replaced")
            self.assertEqual(db.session.get(EmployeeDocument, second).status, "active")
            self.assertEqual(EmployeeAllowance.query.one().evidence_document_id, old.replaced_by_document_id)
            self.assertEqual(EmployeeAnnualLeaveRecord.query.one().evidence_document_id, old.replaced_by_document_id)

    def test_specialist_evidence_does_not_retire_shared_source(self):
        eid = self.employee()
        did = self.document(eid)
        with self.app.app_context():
            leave = EmployeeAnnualLeaveRecord(employee_id=eid, leave_date=date(2026, 8, 4),
                days=1, entitlement_year=2026, leave_type="sick", evidence_document_id=did)
            db.session.add_all([leave, EmployeeAllowance(employee_id=eid, allowance_type="meal", label="Meal",
                amount=10, effective_from=date(2026, 1, 1), evidence_document_id=did)])
            db.session.commit(); rid = leave.id
        self.client.post(f"/annual-leave/{rid}/evidence", data={
            "evidence": (io.BytesIO(workflow.pdf_bytes("new evidence")), "new.pdf")})
        with self.app.app_context():
            self.assertEqual(db.session.get(EmployeeDocument, did).status, "active")
            self.assertEqual(EmployeeAllowance.query.one().evidence_document_id, did)
            self.assertNotEqual(EmployeeAnnualLeaveRecord.query.one().evidence_document_id, did)

    def test_new_employee_requires_choice_and_unknown_probation_copy(self):
        page = self.client.get("/employees/new").get_data(as_text=True)
        import re
        select = re.search(r'<select[^>]+name="payroll_group"[^>]*>(.*?)</select>', page, re.S).group(1)
        self.assertRegex(select, r'^\s*<option value="">')
        eid = self.employee()
        with self.app.app_context():
            db.session.get(Employee, eid).current_period.probation_end_date = None
            db.session.commit()
        page = self.client.get(f"/employees/{eid}?tab=employment_status").get_data(as_text=True)
        self.assertIn("轉正資料待核實", page)
        for tab in ("personal", "employment", "credentials", "documents", "leave"):
            self.assertEqual(self.client.get(f"/employees/{eid}?tab={tab}").status_code, 200)


if __name__ == "__main__":
    unittest.main()
