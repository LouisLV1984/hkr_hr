"""Approved zero-base, export-blocking and manual-rate regression cases."""
from datetime import date, datetime, timedelta
from decimal import Decimal
import unittest

from tests.fixtures import PayrollTestCase
from hkr_hr.platform.db import db, User, AuditLog
from hkr_hr.employees.api import Employee
from hkr_hr.attendance.api import AttendanceMonthlySummary
from hkr_hr.leave.api import EmployeeAnnualLeaveRecord
from hkr_hr.payroll.api import PayrollAdjustment, PayrollRun
from hkr_hr.attendance.api import set_long_term_attendance_policy
from hkr_hr.references.api import reference_by_code
from hkr_hr.payroll.api import calculate_employee, snapshot_payroll
from hkr_hr.payroll.api import hkd_summary


class PayrollPolicyTests(PayrollTestCase):

    def export(self, eid=None):
        data = {"year_month": "2026-08", "payroll_group": "management"}
        if eid:
            data.update(scope="selected", employee_ids=str(eid))
        response = self.client.post("/payroll/export-current", data=data)
        return self.client.get(response.location) if response.status_code == 303 else response

    def test_negative_blocks_new_export_but_preserves_original_snapshot(self):
        eid, other = self.ready(), self.ready(2)
        with self.app.app_context():
            employee = db.session.get(Employee, eid)
            run = snapshot_payroll("2026-08", "management", [calculate_employee(employee, "2026-08")], User.query.first().id)
            runid = run.id
            db.session.add(PayrollAdjustment(employee_id=eid, year_month="2026-08", label="Synthetic deduction", amount=-100000, status="active"))
            db.session.commit()
        for response in (self.export(eid),):
            self.assertEqual(response.status_code, 302)
            self.assertNotIn("attachment", response.headers.get("Content-Disposition", ""))
        with self.client.session_transaction() as session:
            text = str(session.get("_flashes"))
            self.assertIn("驗收1", text)
            self.assertIn("實發為負數", text)
        with self.app.app_context():
            self.assertEqual(PayrollRun.query.count(), 1)
            self.assertEqual(AuditLog.query.filter_by(action="payroll_exported").count(), 0)
        for url in (f"/payroll/runs/{runid}/export", f"/export/payroll-summary?run_id={runid}", f"/export/salary-certificate?employee_id={eid}&year_month=2026-08"):
            self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.export().status_code, 200)
        self.assertEqual(self.export(other).status_code, 200)

    def test_stale_attendance_blocks_until_reconfirmed_and_old_flag_remains_blocked(self):
        eid = self.ready()
        with self.app.app_context():
            employee = db.session.get(Employee, eid)
            summary = AttendanceMonthlySummary(employee_id=eid, year_month="2026-08", status="not_required", confirmed_at=datetime.utcnow()-timedelta(days=1))
            db.session.add_all([summary, EmployeeAnnualLeaveRecord(employee_id=eid, leave_date=date(2026,8,4), end_date=date(2026,8,4), days=1, entitlement_year=2026, leave_type="annual", status="active")])
            db.session.commit()
            row = calculate_employee(employee, "2026-08")
            self.assertIn("leave.attendance_recheck", row["warnings"])
            run = snapshot_payroll("2026-08", "management", [row], User.query.first().id)
            runid = run.id
        self.assertEqual(self.export(eid).status_code, 302)
        with self.app.app_context():
            AttendanceMonthlySummary.query.one().confirmed_at = datetime.utcnow()+timedelta(seconds=1)
            db.session.commit()
        self.assertEqual(self.export(eid).status_code, 200)
        self.assertEqual(self.client.get(f"/payroll/runs/{runid}/export").status_code, 302)
        self.assertEqual(self.client.get(f"/export/payroll-summary?run_id={runid}").status_code, 302)

    def test_manual_rates_persist_atomically_and_display_converted_totals(self):
        self.ready()
        self.login("hr_test", "test-hr-password")
        url = "/payroll/exchange-rates"
        self.assertEqual(self.client.post(url, data={"year_month":"2026-08", "rate_CNY":"1.1", "rate_USD":"7.8"}).status_code, 302)
        for invalid in ("0", "-1", "NaN", "Infinity", "1e100", "invalid"):
            self.client.post(url, data={"year_month":"2026-08", "rate_CNY":"2", "rate_USD":invalid})
            with self.app.app_context():
                self.assertEqual(reference_by_code("currency", "CNY").metadata_json["payroll_hkd_rate"], "1.1")
        with self.app.app_context():
            totals = hkd_summary([{"currency":"HKD", "net":Decimal("100")}, {"currency":"CNY", "net":Decimal("100")}])
            self.assertEqual(totals["totals"]["net"], Decimal("210"))
            self.assertEqual(hkd_summary([{"currency":"MOP", "net":Decimal("1")}])["missing"], ["MOP"])
            self.assertEqual(AuditLog.query.filter_by(action="payroll_exchange_rate_updated").count(), 2)
        for page in ("/attendance-payroll?year_month=2026-08", "/final-payment?year_month=2026-08", "/dashboard?year_month=2026-08"):
            response = self.client.get(page)
            self.assertEqual(response.status_code, 200, page)
        self.client.post(url, data={"rate_CNY":""})
        with self.app.app_context():
            self.assertNotIn("payroll_hkd_rate", reference_by_code("currency", "CNY").metadata_json)

    def test_mpf_and_final_exports_block_negative_employee_with_name(self):
        from hkr_hr.payroll.api import calculate_final_payment
        eid = self.ready()
        with self.app.app_context():
            employee = db.session.get(Employee, eid)
            entity = employee.current_assignment.payroll_entity_id
            db.session.add(PayrollAdjustment(employee_id=eid, year_month="2026-08", label="Synthetic deduction", amount=-100000, status="active"))
            db.session.commit()
        response = self.client.post("/mpf-contributions/export", data={"year_month":"2026-08", "scheme_code":"all"})
        self.assertEqual(response.status_code, 302)
        with self.client.session_transaction() as session:
            self.assertIn("驗收1", str(session.get("_flashes")))
            self.assertIn("禁止匯出", str(session.get("_flashes")))
        with self.app.app_context():
            employee = db.session.get(Employee, eid)
            employee.current_period.end_date = date(2026,8,20)
            db.session.commit()
            self.assertLess(calculate_final_payment(employee.current_period)["net_amount"], 0)
        response = self.client.post("/final-payment/export", data={"year_month":"2026-08", "payroll_entity_id":str(entity)})
        self.assertEqual(response.status_code, 302)
        with self.client.session_transaction() as session:
            self.assertIn("驗收1", str(session.get("_flashes")))
        with self.app.app_context():
            self.assertEqual(PayrollRun.query.count(), 0)
            self.assertEqual(AuditLog.query.filter_by(action="final_payment_exported").count(), 0)
