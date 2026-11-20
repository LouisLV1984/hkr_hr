"""Regression cases from the authenticated review, using synthetic records only."""
import io
import unittest
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

from openpyxl import load_workbook
from werkzeug.datastructures import FileStorage
from tests.fixtures import ProfileTestCase, current_profile_revision, pdf_bytes
from hkr_hr.platform.db import db, User
from hkr_hr.employees.api import Employee, EmployeeSalary
from hkr_hr.documents.api import EmployeeDocument
from hkr_hr.attendance.api import AttendanceBatchItem, AttendanceMonthlySummary
from hkr_hr.payroll.api import currency_summary, project_summary
from hkr_hr.platform.security import validate_uploaded_file, UploadValidationError


class ReviewHardeningTests(ProfileTestCase):

    def test_stale_profile_cannot_erase_new_values_and_scopes_are_independent(self):
        eid = self.employee()
        token = current_profile_revision(self.app, eid, "profile")
        education = current_profile_revision(self.app, eid, "education")
        url = f"/employees/{eid}/personal"
        data = {"form_scope": "profile", "profile_revision": token, "residential_address": "New address"}
        self.assertEqual(self.client.post(url, data=data).status_code, 302)
        data["residential_address"] = ""
        result = self.client.post(url, data=data, headers={"X-HKR-Profile-Editor": "1"})
        self.assertEqual(result.status_code, 422)
        self.assertTrue(result.json["errors"])
        self.client.post(url, data={"form_scope": "education", "profile_revision": education, "major": "Engineering"})
        with self.app.app_context():
            employee = db.session.get(Employee, eid)
            self.assertEqual(employee.residential_address, "New address")
            self.assertEqual(employee.major, "Engineering")
        self.assertEqual(self.client.post(url, data={"form_scope": "profile"},
                         headers={"X-HKR-Profile-Editor": "1"}).status_code, 422)

    def test_salary_rejects_negative_nonfinite_and_database_overflow(self):
        eid = self.employee()
        for amount in ("-100", "NaN", "Infinity", "-Infinity", "1e100", "10000000000"):
            response = self.client.post(f"/employees/{eid}/salary", data={
                "amount": amount, "salary_basis": "monthly", "effective_from": "2026-01-01"},
                headers={"X-HKR-Profile-Editor": "1"})
            self.assertEqual(response.status_code, 422, amount)
        with self.app.app_context():
            self.assertEqual(EmployeeSalary.query.filter_by(employee_id=eid).count(), 0)
        self.client.post(f"/employees/{eid}/salary", data={"amount": "0", "salary_basis": "monthly", "effective_from": "2026-01-01"})
        with self.app.app_context():
            salary = EmployeeSalary.query.filter_by(employee_id=eid).one()
            sid = salary.id
        self.client.post(f"/salaries/{sid}/correct", data={"amount": "-1", "salary_basis": "monthly", "effective_from": "2026-01-01"})
        with self.app.app_context():
            self.assertEqual(db.session.get(EmployeeSalary, sid).amount, 0)

    def test_export_preserves_formula_like_user_text_without_execution(self):
        eid = self.employee()
        with self.app.app_context():
            employee = db.session.get(Employee, eid)
            employee.residential_address = '=HYPERLINK("https://example.invalid","QA")'
            employee.remarks = "=1+1"
            db.session.commit()
        response = self.client.get("/export/employees")
        self.assertEqual(response.status_code, 200)
        workbook = load_workbook(io.BytesIO(response.data), data_only=False)
        cells = [c for sheet in workbook for row in sheet for c in row]
        self.assertFalse(any(c.data_type == "f" for c in cells))
        self.assertTrue(any(c.value == "=1+1" and c.data_type == "s" for c in cells))

    def test_password_reset_revokes_existing_login_and_malformed_ids(self):
        other = self.app.test_client()
        other.post("/login", data={"username": "admin", "password": "test-admin-password"})
        with self.app.app_context():
            user = User.query.filter_by(username="admin").one()
            user.set_password("new-synthetic-password")
            db.session.commit()
        for client in (self.client, other):
            response = client.get("/employees")
            self.assertEqual(response.status_code, 302)
            self.assertIn("/login", response.location)
        self.login("admin", "new-synthetic-password")
        self.assertEqual(self.client.get("/employees").status_code, 200)
        with self.client.session_transaction() as session:
            session["_user_id"] = "not-an-integer"
        self.assertEqual(self.client.get("/employees").status_code, 302)

    def test_pdf_requires_pages_and_retains_original_bytes_and_position(self):
        for content in (b"%PDF-1.4\nQA\n%%EOF", b"%PDF-1.4\n%%EOF"):
            with self.assertRaises(UploadValidationError):
                validate_uploaded_file(FileStorage(stream=io.BytesIO(content), filename="bad.pdf"))
        data = pdf_bytes("QA original")
        stream = io.BytesIO(data)
        stream.seek(7)
        validate_uploaded_file(FileStorage(stream=stream, filename="good.pdf"))
        self.assertEqual(stream.tell(), 7)
        self.assertEqual(stream.getvalue(), data)
        did = self.document(self.employee())
        with self.app.app_context():
            path = Path(db.session.get(EmployeeDocument, did).stored_path)
        path.write_bytes(b"")
        viewer = self.client.get(f"/documents/{did}/open")
        source_url = f"/documents/{did}/open?raw=1"
        self.assertIn(source_url, viewer.get_data(as_text=True))
        self.assertEqual(self.client.get(source_url).status_code, 400)

    def test_invalid_calendar_parameters_return_400_instead_of_500(self):
        for path in ("/payroll?year_month=0001-01", "/dashboard?month=2026-13",
                     "/employees?month=abc", "/annual-leave?year=10000", "/annual-leave?year=-1"):
            self.assertEqual(self.client.get(path).status_code, 400, path)

    def test_currency_totals_and_project_lines_remain_separate(self):
        rows = []
        for currency, value in (("HKD", "1000"), ("CNY", "2000")):
            amount = Decimal(value)
            rows.append(dict(currency=currency, blockers=[], employee=SimpleNamespace(id=len(rows)+1),
                gross_amount=amount, net_amount=amount + 10, employee_mpf=0, employer_mpf=0,
                work_injury_medical_reimbursement_amount=10,
                lines=[dict(project=None, base_amount=amount, gross_amount=amount,
                            ot_amount=0, large_ecall_amount=0, ecall_amount=0, allowance_amount=0)]))
        self.assertEqual({r["currency"]: r["gross"] for r in currency_summary(rows)},
                         {"HKD": Decimal("1000"), "CNY": Decimal("2000")})
        self.assertEqual(len(project_summary(rows)), 2)
        self.assertTrue(all(r["net"] == r["gross"] - r["employee_mpf"] + r["medical"]
                            for r in currency_summary(rows)))

    def test_preloaded_leave_summary_matches_query_path(self):
        from datetime import date
        from hkr_hr.leave.api import EmployeeAnnualLeaveBalance, EmployeeAnnualLeaveRecord
        from hkr_hr.leave.api import annual_leave_summary
        from hkr_hr.employees.api import workbench_options
        eid = self.employee()
        with self.app.app_context():
            db.session.add(EmployeeAnnualLeaveBalance(employee_id=eid, year=2026,
                entitled_days_override=14, manual_adjustment_days=1))
            db.session.add(EmployeeAnnualLeaveRecord(employee_id=eid, leave_date=date(2026, 8, 4),
                days=2, entitlement_year=2026, leave_type="annual", status="active"))
            db.session.commit()
            employee = Employee.query.options(*workbench_options()).filter_by(id=eid).one()
            original = annual_leave_summary(employee, 2026)
            preloaded = annual_leave_summary(employee, 2026, preloaded=True)
            for key in ("used", "remaining", "entitled", "legacy_used", "bucket_used"):
                self.assertEqual(preloaded[key], original[key], key)
            self.assertEqual(preloaded["remaining"], Decimal("13"))

    def test_postgres_simultaneous_profile_writes_have_one_winner(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        with self.app.app_context():
            if db.engine.dialect.name != "postgresql":
                self.skipTest("Row locking requires the isolated PostgreSQL runner")
        eid = self.employee()
        token = current_profile_revision(self.app, eid, "profile")
        clients = [self.app.test_client(), self.app.test_client()]
        for client in clients:
            client.post("/login", data={"username": "admin", "password": "test-admin-password"})
        barrier = Barrier(2)

        def save(index):
            barrier.wait(timeout=10)
            return clients[index].post(f"/employees/{eid}/personal", data={
                "form_scope": "profile", "profile_revision": token,
                "residential_address": f"Concurrent draft {index}",
            }, headers={"X-HKR-Profile-Editor": "1"}).status_code

        with ThreadPoolExecutor(max_workers=2) as executor:
            statuses = list(executor.map(save, range(2)))
        self.assertEqual(sorted(statuses), [200, 422])
        with self.app.app_context():
            self.assertEqual(db.session.get(Employee, eid).residential_address,
                             f"Concurrent draft {statuses.index(200)}")

    def test_postgres_simultaneous_attendance_item_writes_have_one_winner(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        with self.app.app_context():
            if db.engine.dialect.name != "postgresql":
                self.skipTest("Row locking requires the isolated PostgreSQL runner")
        eid = self.employee()
        self.client.post("/attendance/batches", data={
            "year_month": "2026-08",
            "files": (io.BytesIO(pdf_bytes("concurrent.pdf")), "concurrent.pdf"),
        })
        with self.app.app_context():
            item_id = AttendanceBatchItem.query.order_by(AttendanceBatchItem.id.desc()).first().id
        clients = [self.app.test_client(), self.app.test_client()]
        clients[0].post("/login", data={"username": "admin", "password": "test-admin-password"})
        clients[1].post("/login", data={"username": "hr_test", "password": "test-hr-password"})
        barrier = Barrier(2)

        def save(index):
            barrier.wait(timeout=10)
            return clients[index].post(f"/attendance/items/{item_id}/save", data={
                "employee_id": eid,
                "year_month": "2026-08",
                "expected_item_status": "pending",
                "current_1_20_project_id": "",
                "current_1_20_working_days": "10",
                "current_1_20_ot_hours": str(index + 1),
            }, headers={"X-HKR-Profile-Editor": "1"}).status_code

        with ThreadPoolExecutor(max_workers=2) as executor:
            statuses = list(executor.map(save, range(2)))
        self.assertEqual(sorted(statuses), [200, 422])
        winner = statuses.index(200)
        with self.app.app_context():
            item = db.session.get(AttendanceBatchItem, item_id)
            self.assertEqual(item.status, "saved")
            summary = AttendanceMonthlySummary.query.filter_by(employee_id=eid, year_month="2026-08").one()
            self.assertEqual(item.summary_id, summary.id)
            self.assertEqual(summary.segments[0].ot_hours, Decimal(winner + 1))

    def test_postgres_simultaneous_attendance_correction_writes_have_one_winner(self):
        import re
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        with self.app.app_context():
            if db.engine.dialect.name != "postgresql":
                self.skipTest("Row locking requires the isolated PostgreSQL runner")
        eid = self.employee()
        self.client.post("/attendance/batches", data={
            "year_month": "2026-08",
            "files": (io.BytesIO(pdf_bytes("correct.pdf")), "correct.pdf"),
        })
        with self.app.app_context():
            item_id = AttendanceBatchItem.query.order_by(AttendanceBatchItem.id.desc()).first().id
        self.client.post(f"/attendance/items/{item_id}/save", data={
            "employee_id": eid,
            "year_month": "2026-08",
            "expected_item_status": "pending",
            "current_1_20_project_id": "",
            "current_1_20_working_days": "10",
            "current_1_20_ot_hours": "1",
        })
        with self.app.app_context():
            summary = AttendanceMonthlySummary.query.filter_by(employee_id=eid, year_month="2026-08").one()
            summary_id = summary.id
            doc_id = summary.document_id
        html = self.client.get(f"/attendance?summary_id={summary_id}").get_data(as_text=True)
        revision = re.search(r'name="summary_revision" value="([^"]+)"', html).group(1)

        clients = [self.app.test_client(), self.app.test_client()]
        clients[0].post("/login", data={"username": "admin", "password": "test-admin-password"})
        clients[1].post("/login", data={"username": "hr_test", "password": "test-hr-password"})
        barrier = Barrier(2)

        def correct(index):
            barrier.wait(timeout=10)
            return clients[index].post(f"/attendance/summaries/{summary_id}/correct", data={
                "employee_id": eid,
                "year_month": "2026-08",
                "editing_document_id": doc_id,
                "summary_revision": revision,
                "current_1_20_project_id": "",
                "current_1_20_working_days": "10",
                "current_1_20_ot_hours": str(index + 5),
            }, headers={"X-HKR-Profile-Editor": "1"}).status_code

        with ThreadPoolExecutor(max_workers=2) as executor:
            statuses = list(executor.map(correct, range(2)))
        self.assertEqual(sorted(statuses), [200, 422])
        winner = statuses.index(200)
        with self.app.app_context():
            summary = db.session.get(AttendanceMonthlySummary, summary_id)
            self.assertEqual(summary.segments[0].ot_hours, Decimal(winner + 5))
