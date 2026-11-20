"""Transactional leave review and latest Payroll/Final Payment regression."""
from datetime import date
from decimal import Decimal
import unittest

from tests.fixtures import PayrollTestCase
from hkr_hr.platform.db import db, AuditLog, User
from hkr_hr.employees.api import Employee
from hkr_hr.leave.api import EmployeeAnnualLeaveRecord
from hkr_hr.payroll.api import PayrollRun, PayrollEmployeeResult, EmployeeFinalPaymentCase
from hkr_hr.attendance.api import AttendanceMonthlySummary, AttendanceSegment
from hkr_hr.payroll.api import calculate_employee, snapshot_payroll
from hkr_hr.payroll.api import review_rows, review_token


class LeaveReviewTests(PayrollTestCase):

    def legacy(self, eid, start=14, end=17, kind="sick"):
        with self.app.app_context():
            row = EmployeeAnnualLeaveRecord(employee_id=eid, leave_date=date(2026,8,start),
                end_date=date(2026,8,end), days=end-start+1, start_session="am", end_session="pm",
                leave_type=kind, status="active", entitlement_year=2026, remarks="preserve me")
            db.session.add(row)
            db.session.commit()
            return row.id

    def token(self, eid=None):
        with self.app.app_context():
            return review_token(review_rows(eid)[0], User.query.filter_by(username="admin").one().id)

    def submit(self, ids, token=None, eid=None, **extra):
        form = dict(record_ids=[str(i) for i in ids], review_token=token or self.token(eid), acknowledge="on")
        if eid:
            form["employee_id"] = str(eid)
        form.update(extra)
        return self.client.post("/annual-leave/day-review/apply", data=form, follow_redirects=True)

    def saved_payroll(self, eid, project, month):
        with self.app.app_context():
            employee = db.session.get(Employee,eid)
            employee.current_period.confirmation_date = date(2026,1,1)
            summary = AttendanceMonthlySummary(employee=employee, year_month=month, status="received")
            db.session.add(summary)
            db.session.flush()
            db.session.add(AttendanceSegment(summary=summary, period_kind="current_1_20", project_id=project, working_days=10))
            db.session.flush()
            result = calculate_employee(employee,month)
            self.assertFalse(result["blockers"], result["blockers"])
            run = snapshot_payroll(month,"management",[result],User.query.filter_by(username="admin").one().id)
            return run.id

    def test_selected_only_preserves_fields_repeat_and_stale_rejected(self):
        eid,_=self.employee("management")
        a=self.legacy(eid)
        b=self.legacy(eid,21,24,"unpaid")
        token=self.token(eid)
        response=self.submit([a],token,eid)
        self.assertIn("已更新 1 筆假期",response.get_data(as_text=True))
        with self.app.app_context():
            row=db.session.get(EmployeeAnnualLeaveRecord,a)
            self.assertEqual(row.days,2)
            self.assertEqual(row.remarks,"preserve me")
            self.assertEqual(row.leave_date,date(2026,8,14))
            self.assertEqual(db.session.get(EmployeeAnnualLeaveRecord,b).days,4)
            self.assertEqual(AuditLog.query.filter_by(action="leave_corrected").count(),1)
        self.assertIn("未保存任何更新",self.submit([a],token,eid).get_data(as_text=True))
        token=self.token(eid)
        with self.app.app_context():
            db.session.get(Employee,eid).assignments[0].workweek_days=6
            db.session.commit()
        self.assertIn("計日依據已改動",self.submit([b],token,eid).get_data(as_text=True))

    def test_employee_scope_tamper_zero_and_missing_acknowledgement(self):
        eid,_=self.employee("management")
        other,_=self.employee("management",2)
        a=self.legacy(eid)
        b=self.legacy(other)
        z=self.legacy(eid,15,16)
        token=self.token(eid)
        for ids,kw in [([b],{}),([a],dict(acknowledge="")),([z],{})]:
            self.assertIn("未保存任何更新",self.submit(ids,token,eid,**kw).get_data(as_text=True))
        page=self.client.get(f"/annual-leave/day-review?employee_id={eid}").get_data(as_text=True)
        self.assertRegex(page,fr'name="record_ids" value="{z}"[^>]*disabled')
        self.assertNotRegex(page,fr'name="record_ids" value="{b}"')
        profile=self.client.get(f"/employees/{eid}?tab=employment").get_data(as_text=True)
        self.assertIn("核對後可一次更新",profile)

    def test_payroll_latest_snapshot_and_next_month_recalculated_no_attendance_edit(self):
        from hkr_hr.payroll.api import build_group_workbook
        eid,project=self.employee("management")
        a=self.legacy(eid)
        old=self.saved_payroll(eid,project,"2026-08")
        later=self.saved_payroll(eid,project,"2026-09")
        response=self.submit([a],eid=eid)
        self.assertIn("重新計算 2 個員工月份",response.get_data(as_text=True))
        with self.app.app_context():
            self.assertEqual(PayrollRun.query.count(),4)
            before=PayrollEmployeeResult.query.filter_by(run_id=old).one()
            after=(PayrollEmployeeResult.query.join(PayrollRun).filter(PayrollRun.year_month=="2026-08")
                   .order_by(PayrollRun.id.desc()).first())
            self.assertEqual(before.sick_leave_days,4)
            self.assertEqual(after.sick_leave_days,2)
            self.assertEqual(after.net_amount-before.net_amount,400)
            exported=build_group_workbook(after.run,"management").active
            self.assertEqual(exported.cell(7,29).value,2)
            self.assertEqual(Decimal(str(exported.cell(7,30).value))*2,after.sick_leave_amount)
            self.assertTrue(db.session.get(PayrollRun,later))
            self.assertEqual(AuditLog.query.filter_by(action="payroll_leave_recalculated").count(),2)
            self.assertTrue(all(s.working_days==10 for s in AttendanceSegment.query.all()))

    def test_payroll_failure_rolls_back_earlier_run_and_all_selected_leave(self):
        eid,project=self.employee("management")
        a=self.legacy(eid)
        b=self.legacy(eid,21,24,"unpaid")
        self.saved_payroll(eid,project,"2026-08")
        self.saved_payroll(eid,project,"2026-09")
        with self.app.app_context():
            AttendanceMonthlySummary.query.filter_by(year_month="2026-09").one().status="pending"
            db.session.commit()
        response=self.submit([a,b],eid=eid)
        self.assertIn("未保存任何更新",response.get_data(as_text=True))
        with self.app.app_context():
            self.assertEqual(PayrollRun.query.count(),2)
            self.assertEqual([r.days for r in EmployeeAnnualLeaveRecord.query.all()],[4,4])
            self.assertEqual(AuditLog.query.filter_by(action="leave_corrected").count(),0)

    def test_annual_allocations_and_final_pay_preserve_manual_delta(self):
        from hkr_hr.payroll.api import leave_defaults, calculate_final_payment
        eid,_=self.employee("management")
        self.request_leave(eid,start="2026-08-14",end="2026-08-17",leave_type="annual")
        with self.app.app_context():
            employee=db.session.get(Employee,eid)
            period=employee.current_period
            period.end_date=date(2026,8,31)
            period.contract_annual_leave_days=14
            row=EmployeeAnnualLeaveRecord.query.one()
            # Stored 5-day leave becomes 6-day; Sat now counts one additional day.
            employee.assignments[0].workweek_days=6
            db.session.flush()
            legacy,regular,*_=leave_defaults(period)
            case=EmployeeFinalPaymentCase(employee=employee,employment_period=period,
                settlement_month="2026-08",status="active",actual_working_days=23,
                legacy_leave_days=legacy,post_2024_leave_days=regular+Decimal('1'),
                leave_daily_rate_override=1000,benefit_type="none",other_payment=123)
            db.session.add(case)
            db.session.commit()
            rid=row.id
            old_regular=case.post_2024_leave_days
            old_pay=calculate_final_payment(period)["annual_leave_pay"]
        response=self.submit([rid],eid=eid)
        self.assertIn("1 筆離職結算",response.get_data(as_text=True))
        with self.app.app_context():
            row=db.session.get(EmployeeAnnualLeaveRecord,rid)
            self.assertEqual(row.days,3)
            self.assertEqual(sum(a.days for a in row.allocations),3)
            case=EmployeeFinalPaymentCase.query.one()
            self.assertAlmostEqual(case.post_2024_leave_days,old_regular-1,places=3)
            self.assertEqual(case.other_payment,123)
            self.assertEqual(case.actual_working_days,23)
            self.assertEqual(calculate_final_payment(case.employment_period)["annual_leave_pay"],old_pay-1000)
            self.assertEqual(AuditLog.query.filter_by(action="final_payment_leave_recalculated").count(),1)

    def test_cross_month_saved_units_and_daily_payroll(self):
        from hkr_hr.attendance.api import saved_leave_units
        eid,project=self.employee("site_daily")
        with self.app.app_context():
            row=EmployeeAnnualLeaveRecord(employee_id=eid, leave_date=date(2026,7,31),
                end_date=date(2026,8,3), days=4, start_session="am", end_session="pm",
                leave_type="sick",status="active",entitlement_year=2026)
            db.session.add(row)
            db.session.commit()
            rid=row.id
        old=self.saved_payroll(eid,project,"2026-08")
        response=self.submit([rid],eid=eid)
        self.assertIn("已更新 1 筆假期",response.get_data(as_text=True))
        with self.app.app_context():
            row=db.session.get(EmployeeAnnualLeaveRecord,rid)
            self.assertEqual(row.days,3)
            units=saved_leave_units(row)
            self.assertEqual(units[date(2026,8,2)],0)
            self.assertEqual(units[date(2026,8,1)],1)
            self.assertEqual(PayrollRun.query.count(),2)
            latest=PayrollEmployeeResult.query.order_by(PayrollEmployeeResult.id.desc()).first()
            self.assertEqual(latest.sick_leave_days,2)
            self.assertEqual(latest.sick_leave_amount,1800)

    def test_annual_overuse_keeps_existing_balance_and_recovery_policy(self):
        eid,_=self.employee("management")
        first=self.legacy(eid)
        with self.app.app_context():
            # More than the fixture's available annual entitlement.
            row=EmployeeAnnualLeaveRecord(employee_id=eid,leave_date=date(2026,1,1),
                end_date=date(2026,2,28),days=59,start_session="am",end_session="pm",
                leave_type="annual",status="active",entitlement_year=2026)
            db.session.add(row)
            db.session.commit()
            annual=row.id
        response=self.submit([first,annual],eid=eid)
        self.assertIn("已更新 2 筆假期",response.get_data(as_text=True))
        with self.app.app_context():
            from hkr_hr.leave.api import annual_leave_buckets
            self.assertEqual(db.session.get(EmployeeAnnualLeaveRecord,first).days,2)
            row=db.session.get(EmployeeAnnualLeaveRecord,annual)
            self.assertLess(row.days,59)
            self.assertEqual(sum(a.days for a in row.allocations),row.days)
            self.assertTrue(any(b['remaining']<0 for b in annual_leave_buckets(row.employee,as_of=date(2026,2,28))))
            self.assertEqual(AuditLog.query.filter_by(action="leave_corrected").count(),2)


if __name__ == "__main__":
    unittest.main()
