"""Tests for the Admin-only read-only historical review page."""
import io
import unittest
from datetime import date, timedelta
from decimal import Decimal

from tests.fixtures import PayrollTestCase, pdf_bytes
from models import (
    AttendanceBatchItem,
    AttendanceMonthlySummary,
    AuditLog,
    Employee,
    EmployeeCertificate,
    EmployeeIdentity,
    EmployeeWorkInjuryPeriod,
    PayrollRun,
    User,
    db,
)
from tools.hr_core import reference_by_code
from tools.payroll_engine import calculate_employee, snapshot_payroll


class HistoricalReviewTests(PayrollTestCase):

    def test_admin_only_access_and_read_only_historical_checks(self):
        # 1. Replaced attendance sheet + saved payroll snapshot
        emp_att, proj_att = self.employee("management", 1)
        month = "2026-08"
        for filename in ("old_sheet.pdf", "new_sheet.pdf"):
            self.client.post(
                "/attendance/batches",
                data={"year_month": month, "files": (io.BytesIO(pdf_bytes(filename)), filename)},
            )
        with self.app.app_context():
            items = [
                row.id
                for row in AttendanceBatchItem.query.order_by(AttendanceBatchItem.id).all()
            ]
        form = dict(
            year_month=month,
            employee_id=emp_att,
            current_1_20_project_id=proj_att,
            current_1_20_working_days="10",
            current_1_20_ot_hours="2",
        )
        self.client.post(f"/attendance/items/{items[0]}/save", data=form)
        with self.app.app_context():
            summary = AttendanceMonthlySummary.query.filter_by(
                employee_id=emp_att, year_month=month
            ).one()
            old_doc_id = summary.document_id
        self.client.post(
            f"/attendance/items/{items[1]}/save",
            data={**form, "current_1_20_ot_hours": "0", "replace_document_id": old_doc_id},
        )
        with self.app.app_context():
            person_att = db.session.get(Employee, emp_att)
            snapshot_payroll(
                month,
                "management",
                [calculate_employee(person_att, month)],
                User.query.first().id,
            )

        # 2. Daily worker injury: one suspect (daily rate entered as monthly earnings) + one normal
        emp_inj, _ = self.employee("site_daily", 2)
        with self.app.app_context():
            person_inj = db.session.get(Employee, emp_inj)
            # Default daily rate in fixture is 1000
            db.session.add_all(
                [
                    EmployeeWorkInjuryPeriod(
                        employee_id=emp_inj,
                        accident_date=date(2026, 8, 2),
                        payroll_start_date=date(2026, 8, 2),
                        payroll_end_date=date(2026, 8, 10),
                        confirmed_monthly_earnings=Decimal("1000.00"),
                    ),
                    EmployeeWorkInjuryPeriod(
                        employee_id=emp_inj,
                        accident_date=date(2026, 9, 2),
                        payroll_start_date=date(2026, 9, 2),
                        payroll_end_date=date(2026, 9, 10),
                        confirmed_monthly_earnings=Decimal("25000.00"),
                    ),
                ]
            )
            db.session.commit()
            snapshot_payroll(
                "2026-08",
                "site_daily",
                [calculate_employee(person_inj, "2026-08")],
                User.query.first().id,
            )

            # 3. Unlinked credential renewal + identity masking check
            today = date.today()
            cert_type = reference_by_code("certificate_type", "WORKER_REGISTRATION").id
            db.session.add_all(
                [
                    EmployeeCertificate(
                        employee_id=emp_inj,
                        certificate_type_id=cert_type,
                        certificate_no="OLD-CERT-999",
                        expiry_date=today + timedelta(days=10),
                        status="active",
                    ),
                    EmployeeCertificate(
                        employee_id=emp_inj,
                        certificate_type_id=cert_type,
                        certificate_no="NEW-CERT-888",
                        valid_from=today,
                        expiry_date=today + timedelta(days=730),
                        renews_id=None,
                        status="active",
                    ),
                    EmployeeIdentity(
                        employee_id=emp_inj,
                        identity_type="hkid",
                        identity_number="Z9876543",
                        expiry_date=today + timedelta(days=5),
                        status="active",
                    ),
                    EmployeeIdentity(
                        employee_id=emp_inj,
                        identity_type="hkid",
                        identity_number="Z9876543-NEW",
                        expiry_date=today + timedelta(days=1000),
                        renews_id=None,
                        status="active",
                    ),
                ]
            )
            db.session.commit()

        # HR role cannot open admin historical review
        hr_client = self.app.test_client()
        hr_client.post("/login", data={"username": "hr_test", "password": "test-hr-password"})
        self.assertEqual(hr_client.get("/admin/historical-review").status_code, 403)

        with self.app.app_context():
            audit_before = AuditLog.query.count()
            runs_before = PayrollRun.query.count()

        # Admin can inspect all three sections without mutating DB
        response = self.client.get("/admin/historical-review?lang=en")
        self.assertEqual(response.status_code, 200)
        page = response.get_data(as_text=True)

        self.assertIn("old_sheet.pdf", page)
        self.assertIn("new_sheet.pdf", page)
        self.assertIn("Different filename", page)
        self.assertIn("Figures changed", page)
        self.assertIn("1,000.00", page)
        self.assertIn("25,000.00", page)
        self.assertIn("Suspect daily-rate value", page)
        self.assertIn("OLD-CERT-999", page)
        self.assertIn("NEW-CERT-888", page)
        self.assertIn("Z987****", page)
        self.assertNotIn("Z9876543", page)

        with self.app.app_context():
            self.assertEqual(AuditLog.query.count(), audit_before)
            self.assertEqual(PayrollRun.query.count(), runs_before)
