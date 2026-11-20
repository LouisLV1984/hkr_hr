"""Paid-month attendance corrections must remain reproducible after later edits."""
import unittest
from datetime import date
from decimal import Decimal
from io import BytesIO

from tests.fixtures import PayrollTestCase, pdf_bytes
from hkr_hr.attendance.api import AttendanceCorrection
from hkr_hr.employees.api import Employee
from hkr_hr.payroll.api import PayrollAdjustment
from hkr_hr.platform.db import User, db
from hkr_hr.payroll.api import build_final_payment_workbook, build_group_workbook
from hkr_hr.payroll.api import calculate_final_payment
from hkr_hr.payroll.api import calculate_employee, snapshot_payroll


class AttendanceCorrectionTests(PayrollTestCase):

    def test_correction_replaces_only_this_batch_and_freezes_export(self):
        eid, project = self.employee("site_daily", 1)
        self.client.post("/attendance/batches", data={
            "year_month": "2026-11", "files": (BytesIO(pdf_bytes("November")), "November.pdf")})
        from hkr_hr.attendance.api import AttendanceBatchItem
        with self.app.app_context():
            item_id = AttendanceBatchItem.query.one().id
        self.client.post(f"/attendance/items/{item_id}/save", data={
            "employee_id": eid, "year_month": "2026-11", "current_1_20_working_days": "10"})
        url = f"/attendance/{eid}/corrections/2026-11/2026-10"
        form = dict(work_date=["2026-10-08", "2026-10-12", "2026-10-13", "2026-10-14"],
                    kind=["ot", "ot", "day", "day"], direction=["add", "deduct", "add", "deduct"],
                    quantity=["2", "4", "1", "1"], project=[""] * 4, tail=[""] * 4, revision="0")
        preview = self.client.post(url, data={**form, "action": "preview"}).get_json()
        self.assertEqual(Decimal(preview["total"]), -300)
        receipts = [(BytesIO(pdf_bytes(name)), name + ".pdf") for name in ("First", "Second")]
        saved = self.client.post(url, data={**form, "evidence": receipts}).get_json()
        self.assertIn("First.pdf", saved["history"])
        self.assertIn("Second.pdf", saved["history"])
        with self.app.app_context():
            record = AttendanceCorrection.query.one()
            self.assertEqual(len(record.documents), 2)
            self.assertEqual(len(record.lines), 4)
            employee = db.session.get(Employee, eid)
            db.session.add(PayrollAdjustment(employee_id=eid, project_id=project,
                year_month="2026-11", label="Earlier payment", amount=125, status="active"))
            db.session.commit()
            row = calculate_employee(employee, "2026-11")
            self.assertFalse(row["blockers"], row["blockers"])
            run = snapshot_payroll("2026-11", "site_daily", [row], User.query.first().id)
            original = build_group_workbook(run, "site_daily").active["AG7"]
            self.assertEqual(original.value, -175)
            self.assertIn("2026-10-12", original.comment.text)
            self.assertIn("125.00", original.comment.text)
            revision = record.revision
            run_id = run.id
        form["quantity"][1] = "3"
        stale = self.client.post(url, data=form)
        self.assertIn(stale.status_code, (400, 409))
        saved = self.client.post(url, data={**form, "revision": str(revision)})
        self.assertEqual(Decimal(saved.get_json()["total"]), -150)
        with self.app.app_context():
            from hkr_hr.payroll.api import PayrollRun
            record = AttendanceCorrection.query.one()
            self.assertEqual(len(record.documents), 2)
            self.assertEqual(build_group_workbook(db.session.get(PayrollRun, run_id), "site_daily").active["AG7"].value, -175)
            employee = db.session.get(Employee, eid)
            employee.current_period.end_date = date(2026, 11, 20)
            db.session.commit()
            settlement = calculate_final_payment(employee.current_period)
            self.assertEqual(settlement["other_payment"], -25)
            self.assertEqual(len(settlement["attendance_corrections"]), 4)
            payment = build_final_payment_workbook("2026-11", "site_daily", [settlement]).active["R8"]
            self.assertEqual(payment.value, -25)
            self.assertIn("2026-10-12 -3 OT", payment.comment.text)

    def test_adjacent_tail_is_only_paid_separately_when_excluded_from_actuals(self):
        eid, _ = self.employee("site_daily", 1)
        url = f"/attendance/{eid}/corrections/2026-11/2026-10"
        form = dict(work_date="2026-10-25", kind="ot", direction="add", quantity="2",
                    project="", tail="", action="preview")
        self.assertEqual(self.client.post(url, data=form).status_code, 400)
        for choice, amount in (("included", 0), ("extra", 300)):
            response = self.client.post(url, data={**form, "tail": choice}).get_json()
            self.assertEqual(Decimal(response["total"]), amount)
            self.assertEqual(response["lines"][0]["included"], choice == "included")
        with self.app.app_context():
            self.assertEqual(AttendanceCorrection.query.count(), 0)
