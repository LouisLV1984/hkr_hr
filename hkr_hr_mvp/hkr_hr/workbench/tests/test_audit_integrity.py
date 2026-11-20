"""Regression evidence for the H1-H4 / M1-M4 acceptance findings."""
import json
import os
from pathlib import Path
import unittest
from datetime import date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

from tests.fixtures import APP_ROOT, PayrollTestCase
from hkr_hr.platform.db import db, User, AuditLog
from hkr_hr.employees.api import Employee
from hkr_hr.leave.api import EmployeeAnnualLeaveRecord, EmployeeAnnualLeaveBalance, EmployeeCompLeaveCredit, EmployeeWorkInjuryPeriod
from hkr_hr.attendance.api import AttendanceMonthlySummary, AttendanceSegment
from hkr_hr.leave.api import absence_data_issues, absences_changed_since_attendance, leave_date_label
from hkr_hr.platform.dates import annual_leave_days_between
from hkr_hr.leave.api import allocate_annual_leave_with_comp
from hkr_hr.payroll.api import calculate_employee, snapshot_payroll, project_summary
from hkr_hr.payroll.api import build_group_workbook
from hkr_hr.workbench.api import replace_summary_segments


class AuditIntegrityTests(PayrollTestCase):

    def test_dates_are_only_days_source_and_overlap_uses_half_days(self):
        eid, _ = self.employee()
        self.request_leave(eid, end="2026-08-07", days="2")
        with self.app.app_context():
            self.assertEqual(EmployeeAnnualLeaveRecord.query.count(), 0)
        self.request_leave(eid, end_session="am")
        self.request_leave(eid, leave_type="unpaid", start_session="pm")
        response = self.request_leave(eid)
        self.assertIn("重疊", response.get_data(as_text=True))
        with self.app.app_context():
            rows = EmployeeAnnualLeaveRecord.query.order_by(EmployeeAnnualLeaveRecord.id).all()
            self.assertEqual([r.days for r in rows], [Decimal('.5'), Decimal('.5')])
            rid = rows[1].id
            self.assertIn("上午", leave_date_label(rows[0], lambda k: {'employee.morning':'上午','employee.afternoon':'下午'}[k]))
        response = self.client.post(f"/annual-leave/{rid}/update", data=dict(start_date="2026-08-04", end_date="2026-08-04", start_session="am", end_session="pm"), follow_redirects=True)
        self.assertIn("重疊", response.get_data(as_text=True))
        response = self.client.post(f"/employees/{eid}/work-injuries", data=dict(accident_date="2026-08-01", payroll_start_date="2026-08-04", confirmed_monthly_earnings="31000"), follow_redirects=True)
        self.assertIn("重疊", response.get_data(as_text=True))
        self.assertIsNone(annual_leave_days_between(date(2026,8,4), date(2026,8,4), "pm", "am"))
        self.assertIsNone(annual_leave_days_between(date(2026,8,4), date(2026,8,4), "invalid", "am"))
        self.request_leave(eid, start="2026-08-10", end="2026-08-13")
        with self.app.app_context():
            self.assertEqual(EmployeeAnnualLeaveRecord.query.order_by(EmployeeAnnualLeaveRecord.id.desc()).first().days, Decimal('4'))

    def test_injury_overlap_both_directions_and_correcting_itself(self):
        eid, _ = self.employee()
        form = dict(accident_date="2026-08-01", payroll_start_date="2026-08-10", payroll_end_date="2026-08-20", confirmed_monthly_earnings="31000")
        self.client.post(f"/employees/{eid}/work-injuries", data=form)
        response = self.request_leave(eid, start="2026-08-11", end="2026-08-11")
        self.assertIn("重疊", response.get_data(as_text=True))
        self.client.post(f"/employees/{eid}/work-injuries", data=form)
        with self.app.app_context():
            row = EmployeeWorkInjuryPeriod.query.one()
            rid = row.id
        response = self.client.post(f"/work-injuries/{rid}/correct", data=form, follow_redirects=True)
        self.assertIn("已更正", response.get_data(as_text=True))

    def test_export_sick_injury_rate_keeps_engine_amount_all_groups(self):
        evidence = []
        for i, group in enumerate(("site_daily", "site_monthly", "management"), 1):
            eid, project = self.employee(group, i)
            with self.app.app_context():
                employee = db.session.get(Employee, eid)
                summary = AttendanceMonthlySummary(employee=employee, year_month="2026-08", status="received")
                db.session.add(summary)
                db.session.flush()
                db.session.add(AttendanceSegment(summary=summary, period_kind="current_1_20", project_id=project, working_days=10))
                sick = EmployeeAnnualLeaveRecord(employee=employee, leave_date=date(2026,8,11), end_date=date(2026,8,13), days=3, entitlement_year=2026, leave_type="sick", status="active")
                injury = EmployeeWorkInjuryPeriod(employee=employee, accident_date=date(2026,8,14), payroll_start_date=date(2026,8,14), payroll_end_date=date(2026,8,15), confirmed_monthly_earnings=31000, incapacity_monthly_earnings=0, pay_mode="four_fifths", status="active")
                db.session.add_all([sick, injury])
                db.session.commit()
                for confirmed in (False, True):
                    employee.current_period.confirmation_date = date(2026,1,1) if confirmed else None
                    employee.current_period.probation_end_date = None
                    for mode in ("four_fifths", "full_pay"):
                        injury.pay_mode = mode
                        db.session.flush()
                        result = calculate_employee(employee, "2026-08")
                        self.assertFalse(result["blockers"], result["blockers"])
                        run = snapshot_payroll("2026-08", group, [result], User.query.first().id)
                        db.session.flush()
                        workbook = build_group_workbook(run, group)
                        sheet = workbook.active
                        days_col, rate_col, amount_col = (28,29,30) if group == "site_daily" else (29,30,31)
                        rate = sheet.cell(7,rate_col).value
                        self.assertIsInstance(rate, (float,int))
                        calculated = (Decimal(str(rate))*Decimal(str(sheet.cell(7,days_col).value))).quantize(Decimal('.01'))
                        self.assertEqual(calculated, result['sick_leave_amount']+result['work_injury_amount'])
                        self.assertTrue(sheet.cell(7,amount_col).value.startswith('=ROUND('))
                        self.assertEqual(result['sick_leave_amount'],Decimal('2600' if confirmed else '2400'))
                        self.assertEqual(result['work_injury_amount'],Decimal('2000' if mode=='full_pay' else '1600'))
                        if os.environ.get('HR_QA_EXPORT_ROOT'):
                            target=Path(os.environ['HR_QA_EXPORT_ROOT'])
                            target.mkdir(parents=True,exist_ok=True)
                            filename=f'{group}_{confirmed}_{mode}.xlsx'
                            workbook.save(target/filename)
                            evidence.append(dict(file=filename, group=group, gross=str(result['gross_amount']), net=str(result['net_amount']), sick=str(result['sick_leave_amount']+result['work_injury_amount'])))
        if evidence:
            (target/'expected.json').write_text(json.dumps(evidence,indent=2),encoding='utf-8')

    def test_comp_unchanged_save_preserves_credit_and_consumption(self):
        eid, project = self.employee("site_monthly")
        form = {"current_1_20_project_id":str(project), "current_1_20_working_days":"0", "current_1_20_holiday_days":"1",
                "current_1_20_special_work_entries": json.dumps([{"date":"2026-08-09", "session":"full_day"}])}
        with self.app.app_context():
            employee = db.session.get(Employee,eid)
            summary = AttendanceMonthlySummary(employee=employee, year_month="2026-08", status="received", special_day_handling="comp_leave")
            db.session.add(summary)
            db.session.flush()
            with self.app.test_request_context(method="POST", data=form):
                replace_summary_segments(summary)
            db.session.flush()
            credit = EmployeeCompLeaveCredit.query.one()
            cid = credit.id
            record = EmployeeAnnualLeaveRecord(employee=employee, leave_date=date(2026,8,10), end_date=date(2026,8,10), days=1, entitlement_year=2026, leave_type="annual", status="active")
            db.session.add(record)
            db.session.flush()
            allocate_annual_leave_with_comp(record, as_of=record.leave_date)
            db.session.commit()
            for _ in range(2):
                with self.app.test_request_context(method="POST", data=form):
                    replace_summary_segments(summary)
                db.session.commit()
                self.assertEqual(EmployeeCompLeaveCredit.query.count(),1)
                self.assertEqual(record.comp_leave_allocations[0].credit_id,cid)
                self.assertEqual(record.comp_leave_allocations[0].days,Decimal('1'))
                self.assertEqual(len(record.allocations),0)
            # Real replacement exists before consumption is reallocated.
            form['current_1_20_special_work_entries']=json.dumps([{"date":"2026-08-02","session":"full_day"}])
            with self.app.test_request_context(method="POST",data=form):
                replace_summary_segments(summary)
            db.session.commit()
            self.assertNotEqual(record.comp_leave_allocations[0].credit_id,cid)
            self.assertEqual(len(record.allocations),0)
            sid, active_credit_id = summary.id, record.comp_leave_allocations[0].credit_id
            balance=EmployeeAnnualLeaveBalance.query.filter_by(employee_id=eid,year=2026).first()
            if not balance:
                balance=EmployeeAnnualLeaveBalance(employee_id=eid,year=2026,entitled_days_override=0)
                db.session.add(balance)
            balance.entitled_days_override=0
            db.session.commit()
        form.update(employee_id=str(eid),year_month='2026-08',special_day_handling='pay')
        response=self.client.post(f'/attendance/summaries/{sid}/correct',data=form,follow_redirects=True)
        self.assertEqual(response.status_code,200)
        self.assertIn('本次變更未保存',response.get_data(as_text=True))
        with self.app.app_context():
            self.assertEqual(db.session.get(AttendanceMonthlySummary,sid).special_day_handling,'comp_leave')
            self.assertEqual(db.session.get(EmployeeCompLeaveCredit,active_credit_id).status,'active')
            self.assertEqual(EmployeeAnnualLeaveRecord.query.one().comp_leave_allocations[0].credit_id,active_credit_id)

    def test_legacy_conflicts_and_post_save_changes_are_detected(self):
        eid, _ = self.employee()
        with self.app.app_context():
            employee=db.session.get(Employee,eid)
            summary=AttendanceMonthlySummary(employee=employee,year_month="2026-08",status="received",confirmed_at=datetime.utcnow()-timedelta(days=1))
            row=EmployeeAnnualLeaveRecord(employee=employee,leave_date=date(2026,8,4),end_date=date(2026,8,5),days=1,entitlement_year=2026,leave_type="sick",status="active")
            db.session.add_all([summary,row]); db.session.commit()
            self.assertIn('leave.inconsistent_days',absence_data_issues(employee,date(2026,7,21),date(2026,8,31)))
            self.assertTrue(absences_changed_since_attendance(employee,summary,date(2026,7,21),date(2026,8,31)))
            self.assertIn('leave.inconsistent_days',calculate_employee(employee,'2026-08')['blockers'])
            row.days=2; db.session.commit()
            summary.confirmed_at=datetime.utcnow(); db.session.commit()
            self.assertFalse(absences_changed_since_attendance(employee,summary,date(2026,7,21),date(2026,8,31)))
            row.status='voided'; db.session.commit()
            self.assertTrue(absences_changed_since_attendance(employee,summary,date(2026,7,21),date(2026,8,31)))
            row.leave_date=date(2026,9,4); row.end_date=date(2026,9,5)
            db.session.add(AuditLog(employee_id=eid,action='leave_corrected',entity_type='EmployeeAnnualLeaveRecord',entity_id=row.id,before_json={'start_date':'2026-08-04','end_date':'2026-08-05'})); db.session.commit()
            self.assertTrue(absences_changed_since_attendance(employee,summary,date(2026,7,21),date(2026,8,31)))

    def test_project_summary_components_reconcile(self):
        lines=[dict(project=None,base_amount=1000,ot_amount=100,previous_ot_amount=50,
                    large_ecall_amount=1000,ecall_amount=400,previous_ecall_amount=400,
                    allowance_amount=20,gross_amount=3470)]
        result=project_summary([dict(blockers=[],employee=SimpleNamespace(id=1),lines=lines)])[0]
        self.assertEqual(result['ot'],150)
        self.assertEqual(result['ecall'],1800)
        self.assertEqual(result['other'],500)
        self.assertEqual(sum(result[k] for k in ('base','ot','ecall','allowance','other')),result['total'])

    def test_unsaved_prefill_does_not_claim_saved(self):
        from pathlib import Path
        source = self.app.jinja_loader.get_source(self.app.jinja_env, "attendance/index.html")[0]
        self.assertNotIn("prefill_source or 'saved'",source)
        self.assertIn('hasSavedComparison',source)
        self.assertIn('attendance.tail_pending_review',source)


if __name__ == '__main__':
    unittest.main()
