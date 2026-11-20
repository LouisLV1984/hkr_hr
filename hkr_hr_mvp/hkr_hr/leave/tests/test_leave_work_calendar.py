"""Company leave workday counting and preserved historical payroll regression."""
from datetime import date
from decimal import Decimal
import unittest

from tests.fixtures import PayrollTestCase
from models import db, Employee, EmployeeAssignment, EmployeeAnnualLeaveRecord, WorkCalendarHoliday, AuditLog
from tools.attendance_policy import (leave_day_units, saved_leave_units, scheduled_work_units,
                                    employee_nonattendance_units)
from tools.payroll_engine import monthly_salary_components, daily_leave_components
from tools.absence_integrity import absence_data_issues


class LeaveCalendarTests(PayrollTestCase):

    def test_five_five_half_six_and_half_day_endpoints(self):
        eid, _ = self.employee('management')
        with self.app.app_context():
            employee = db.session.get(Employee, eid)
            assignment = employee.assignments[0]
            for workweek, whole, half, attendance in [('5', 2, 1, 0), ('5.5', 2, 1, .5), ('6', 3, 2, 1)]:
                assignment.workweek_days = Decimal(workweek)
                units = leave_day_units(employee, date(2026,8,14), date(2026,8,17))
                self.assertEqual(sum(units.values()), whole)
                units = leave_day_units(employee, date(2026,8,14), date(2026,8,17), 'pm', 'am')
                self.assertEqual(sum(units.values()), half)
                self.assertEqual(scheduled_work_units(assignment, date(2026,8,15)), Decimal(str(attendance)))

    def test_public_vs_statutory_holiday_and_cross_month(self):
        eid, _ = self.employee('management')
        with self.app.app_context():
            employee = db.session.get(Employee, eid)
            assignment = employee.assignments[0]
            assignment.workweek_days = Decimal('6')
            holiday = WorkCalendarHoliday.query.filter_by(region_id=assignment.region_id, holiday_date=date(2026,7,1)).one()
            holiday.applies_to_public = True
            holiday.applies_to_statutory = False
            db.session.flush()
            self.assertEqual(sum(leave_day_units(employee, date(2026,6,30), date(2026,7,2)).values()), 2)
            assignment.payroll_group = 'site_monthly'
            self.assertEqual(sum(leave_day_units(employee, date(2026,6,30), date(2026,7,2)).values()), 3)
            self.assertEqual(sum(leave_day_units(employee, date(2028,2,28), date(2028,3,1)).values()), 3)

    def test_all_leave_types_save_same_distribution_and_no_weekend_deduction(self):
        eid, _ = self.employee('management')
        for kind, day in [('annual', 7), ('sick', 14), ('unpaid', 21)]:
            response = self.request_leave(eid, start=f'2026-08-{day:02}', end=f'2026-08-{day+3:02}', leave_type=kind)
            self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            employee = db.session.get(Employee, eid)
            rows = EmployeeAnnualLeaveRecord.query.order_by(EmployeeAnnualLeaveRecord.id).all()
            self.assertEqual(len(rows), 3)
            self.assertEqual([r.days for r in rows], [Decimal('2')]*3)
            for row in rows:
                self.assertIsNotNone(row.leave_units_json)
                self.assertEqual(sum(saved_leave_units(row).values()), 2)
            self.assertEqual(employee_nonattendance_units(employee, date(2026,8,1), date(2026,8,31))[date(2026,8,15)], 0)
            self.assertEqual(absence_data_issues(employee, date(2026,8,1), date(2026,8,31)), [])
            employee.current_period.confirmation_date = date(2026,1,1)
            result = monthly_salary_components(employee, date(2026,8,1), date(2026,8,31))
            self.assertEqual(result['annual_days'], 2)
            self.assertEqual(result['sick_days'], 2)
            self.assertEqual(result['unpaid_deduction'], 2000)
            self.assertEqual(result['sick'], 1800)
            self.assertEqual(result['base'] + result['sick'], 28800)
            # Changing future calendar configuration cannot silently reprice saved leave.
            employee.assignments[0].workweek_days = 6
            self.assertEqual(monthly_salary_components(employee, date(2026,8,1), date(2026,8,31))['sick_days'], 2)

    def test_daily_sick_pay_and_sunday_exclusion(self):
        eid, _ = self.employee('site_daily')
        self.request_leave(eid, start='2026-08-14', end='2026-08-17')
        with self.app.app_context():
            employee = db.session.get(Employee, eid)
            employee.current_period.confirmation_date = date(2026,1,1)
            result = daily_leave_components(employee, date(2026,8,1), date(2026,8,31))
            self.assertEqual(result['sick_days'], 3)
            self.assertEqual(result['sick'], 2600)

    def test_zero_invalid_missing_schedule_and_preview_endpoint(self):
        eid, _ = self.employee('management')
        query = 'start_date=2026-08-14&end_date=2026-08-17&start_session=pm&end_session=am'
        response = self.client.get(f'/employees/{eid}/leave-day-preview?{query}')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['days'], '1.0')
        self.assertEqual(response.json['excluded'], ['2026-08-15', '2026-08-16'])
        self.assertIn('管理人員及總部人員', response.json['context_text'])
        self.assertIn('合約 5 天工作制', response.json['context_text'])
        self.assertEqual(self.client.get(f'/employees/{eid}/leave-day-preview?start_date=wrong').status_code, 400)
        response = self.request_leave(eid, start='2026-08-15', end='2026-08-16')
        self.assertIn('計假 0 日', response.get_data(as_text=True))
        response = self.request_leave(eid, start='2025-08-14', end='2025-08-17')
        self.assertIn('缺少有效任職', response.get_data(as_text=True))
        with self.app.app_context():
            self.assertEqual(EmployeeAnnualLeaveRecord.query.count(), 0)

    def test_context_tracks_effective_schedule_and_editor_entry_points(self):
        eid, _ = self.employee('management')
        with self.app.app_context():
            employee = db.session.get(Employee, eid)
            old = employee.assignments[0]
            old.workweek_days = Decimal('5.5')
            old.effective_to = date(2026,8,15)
            db.session.add(EmployeeAssignment(employee=employee, effective_from=date(2026,8,16),
                           payroll_group='site_monthly', region_id=old.region_id, workweek_days=6))
            db.session.commit()
        endpoint = f'/employees/{eid}/leave-day-preview?start_date=2026-08-14&end_date=2026-08-17'
        response = self.client.get(endpoint)
        self.assertEqual(response.status_code, 200)
        text = response.json['context_text']
        self.assertIn('2026-08-14 – 2026-08-15', text)
        self.assertIn('合約 5.5 天工作制；請假按 5 天計日', text)
        self.assertIn('2026-08-16 – 2026-08-17', text)
        self.assertIn('合約 6 天工作制；請假按 6 天計日', text)
        self.assertIn('地盤工人（月工）', text)
        for url in [f'/annual-leave?employee_id={eid}', f'/employees/{eid}?tab=leave']:
            page = self.client.get(url)
            self.assertEqual(page.status_code, 200)
            self.assertIn('data-leave-employee-context', page.get_data(as_text=True))
            self.assertIn('data-leave-form-context', page.get_data(as_text=True))
        with self.client.session_transaction() as sess:
            sess['lang'] = 'en'
        response = self.client.get(endpoint)
        self.assertIn('Contract: 5.5-day week; leave: 5-day week', response.json['context_text'])

    def test_legacy_readonly_report_then_explicit_correction(self):
        eid, _ = self.employee('management')
        with self.app.app_context():
            employee = db.session.get(Employee, eid)
            employee.assignments[0].workweek_days = 6
            row = EmployeeAnnualLeaveRecord(employee=employee, leave_date=date(2026,8,3),
                     end_date=date(2026,8,21), days=19, entitlement_year=2026, leave_type='sick')
            db.session.add(row)
            db.session.commit()
            rid = row.id
        response = self.client.get('/annual-leave/day-review')
        self.assertEqual(response.status_code, 200)
        self.assertIn('17', response.get_data(as_text=True))
        with self.app.app_context():
            row = db.session.get(EmployeeAnnualLeaveRecord, rid)
            self.assertEqual(row.days, 19)
            self.assertIsNone(row.leave_units_json)
            self.assertEqual(sum(saved_leave_units(row).values()), 19)
        response = self.client.post(f'/annual-leave/{rid}/update', data=dict(start_date='2026-08-03',
                     end_date='2026-08-21', start_session='am', end_session='pm'), follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            row = db.session.get(EmployeeAnnualLeaveRecord, rid)
            self.assertEqual(row.days, 17)
            self.assertEqual(sum(saved_leave_units(row).values()), 17)
            audit = AuditLog.query.filter_by(action='leave_corrected', entity_id=rid).first()
            self.assertEqual(audit.before_json['days'], '19.0')
            self.assertEqual(audit.after_json['days'], '17')


if __name__ == '__main__':
    unittest.main()
