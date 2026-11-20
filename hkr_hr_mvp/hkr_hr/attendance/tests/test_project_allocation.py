"""No production data: calendar allocation and scheme-less exemption regressions."""
from datetime import date
import calendar
import io
from decimal import Decimal
import unittest

from tests.fixtures import PayrollTestCase, pdf_bytes
from hkr_hr.platform.db import db, User
from hkr_hr.employees.api import Employee, EmployeeAllowance, EmployeeMpfEnrollment, EmployeeAssignment
from hkr_hr.references.api import WorkProject, WorkCalendarHoliday
from hkr_hr.attendance.api import AttendanceMonthlySummary, AttendanceSegment, AttendanceBatchItem, AttendanceSpecialDay
from hkr_hr.leave.api import EmployeeAnnualLeaveRecord
from hkr_hr.documents.api import EmployeeDocument
from hkr_hr.payroll.api import calculate_employee, snapshot_payroll
from hkr_hr.attendance.api import allocation_dates, allocation_weights, WORKDAY_BASIS, ProjectAllocationError
from hkr_hr.payroll.api import mpf_data_item
from hkr_hr.payroll.api import build_group_workbook, mpf_export_issues, monthly_values, result_lines


class ProjectAllocationTests(PayrollTestCase):
    def setup_monthly(self, group='management'):
        eid, pid = self.employee(group)
        employee = db.session.get(Employee, eid)
        a = db.session.get(WorkProject, pid)
        b = WorkProject(code='QA-B', name='QA Project B', region_id=a.region_id)
        summary = AttendanceMonthlySummary(employee=employee, year_month='2026-08', status='received')
        db.session.add_all([b, summary]); db.session.flush()
        db.session.add(AttendanceSegment(summary=summary, period_kind='current_1_20', project=b, working_days=17, ot_hours=4))
        db.session.flush()
        return employee, a, b, summary

    def ranges(self, a, b):
        return [dict(project_id=a.id, start='2026-08-01', end='2026-08-10'),
                dict(project_id=b.id, start='2026-08-11', end='2026-08-31')]

    def test_workday_rule_rest_holidays_half_saturday_and_totals(self):
        with self.app.app_context():
            employee,a,b,summary=self.setup_monthly()
            db.session.add(WorkCalendarHoliday(region_id=a.region_id, holiday_date=date(2026,8,7),
                name='QA paid holiday', applies_to_public=True, applies_to_statutory=True))
            db.session.add(EmployeeAllowance(employee=employee, allowance_type='meal', amount=60,
                currency='HKD', effective_from=date(2026,8,1), status='active', label='meal'))
            db.session.flush()
            baseline=calculate_employee(employee,'2026-08')
            # Requested Fri-Mon: holiday Fri and rest Sun stay home. No need to list remaining month.
            rows=[dict(project_id=b.id,start='2026-08-07',end='2026-08-10',basis=WORKDAY_BASIS)]
            summary.monthly_project_allocation=rows
            for week,saturday in [('5',Decimal('0')),('5.5',Decimal('.5')),('6',Decimal('1'))]:
                employee.current_assignment.workweek_days=Decimal(week)
                db.session.flush()
                weights=allocation_weights(employee,'2026-08',rows)
                self.assertEqual(weights[date(2026,8,7)],[(a,Decimal(1))])
                self.assertEqual(weights[date(2026,8,9)],[(a,Decimal(1))])
                self.assertEqual(sum(w for p,w in weights[date(2026,8,8)] if p==b),saturday)
                self.assertTrue(all(sum(w for _,w in shares)==1 for shares in weights.values()))
                result=calculate_employee(employee,'2026-08')
                self.assertFalse(result['blockers'],result['blockers'])
                self.assertEqual(result['gross_amount'],baseline['gross_amount'])
                self.assertEqual(result['employee_mpf'],baseline['employee_mpf'])
                target=next(line for line in result['lines'] if line['project']==b)
                self.assertEqual(target['working_days'],1+saturday)
                self.assertEqual(target['base_amount'],1000*(1+saturday))
                self.assertEqual(target['traffic_meal_allowance_amount'],60*(1+saturday))
                self.assertGreater(target['ot_amount'],0)
                run=snapshot_payroll('2026-08','management',[result],User.query.first().id)
                sheet=build_group_workbook(run,'management').active
                self.assertEqual(sum(sheet.cell(r,12).value for r in (7,8)),31)
                saved=run.employee_results[0]
                values=[monthly_values(saved,line,i==0,7+i) for i,line in enumerate(result_lines(saved))]
                self.assertEqual(sum(row[37] for row in values),1500)

    def test_midmonth_joiner_has_no_allocation_before_salary_starts(self):
        with self.app.app_context():
            employee,a,b,summary=self.setup_monthly()
            employee.current_assignment.effective_from=date(2026,8,10)
            employee.salaries[0].effective_from=date(2026,8,10)
            employee.current_period.start_date=date(2026,8,10)
            db.session.flush()
            baseline=calculate_employee(employee,'2026-08')
            summary.monthly_project_allocation=[dict(project_id=b.id,start='2026-08-10',end='2026-08-14',basis=WORKDAY_BASIS)]
            result=calculate_employee(employee,'2026-08')
            self.assertFalse(result['blockers'],result['blockers'])
            self.assertEqual(result['gross_amount'],baseline['gross_amount'])
            weights=allocation_weights(employee,'2026-08',summary.monthly_project_allocation)
            self.assertEqual(weights[date(2026,8,9)],[])
            self.assertEqual(weights[date(2026,8,10)],[(b,Decimal(1))])

    def test_one_pdf_multiple_projects_save_and_reopen(self):
        eid,pid=self.employee('management')
        with self.app.app_context():
            a=db.session.get(WorkProject,pid)
            b=WorkProject(code='QA-B',name='QA B',region_id=a.region_id)
            db.session.add(b); db.session.commit(); bid=b.id
        upload=self.client.post('/attendance/batches',data={'files':(io.BytesIO(pdf_bytes('QA one PDF')), 'qa.pdf')},
                                content_type='multipart/form-data')
        self.assertEqual(upload.status_code,302)
        with self.app.app_context():
            item=AttendanceBatchItem.query.one(); itemid=item.id
        form=dict(employee_id=str(eid),year_month='2026-08',allocation_present='1',allocation_enabled='on',
            allocation_project=str(bid),allocation_start='2026-08-03',allocation_end='2026-08-07',
            current_1_20_project_id=[str(pid),str(bid)],current_1_20_ot_hours=['2','3'],
            current_1_20_working_days=['0','0'],current_1_20_holiday_days=['0','0'])
        response=self.client.post(f'/attendance/items/{itemid}/save',data=form,follow_redirects=True)
        self.assertEqual(response.status_code,200)
        with self.app.app_context():
            item=db.session.get(AttendanceBatchItem,itemid)
            self.assertEqual(item.status,'saved')
            row=db.session.get(AttendanceMonthlySummary,item.summary_id); sid=row.id
            document_id=row.document_id
            self.assertEqual(row.monthly_project_allocation[0]['basis'],WORKDAY_BASIS)
            self.assertEqual([(s.project_id,s.ot_hours) for s in row.segments],[(pid,Decimal(2)),(bid,Decimal(3))])
            self.assertEqual(EmployeeDocument.query.filter_by(category='attendance_pdf').count(),1)
        form['current_1_20_ot_hours']=['2','4']
        response=self.client.post(f'/attendance/summaries/{sid}/correct',data=form,follow_redirects=True)
        self.assertEqual(response.status_code,200)
        with self.app.app_context():
            row=db.session.get(AttendanceMonthlySummary,sid)
            self.assertEqual(row.document_id,document_id)
            self.assertEqual(sum(s.ot_hours for s in row.segments),6)
            self.assertEqual(AttendanceBatchItem.query.count(),1)
            self.assertEqual(EmployeeDocument.query.filter_by(category='attendance_pdf').count(),1)

    def test_effective_workweek_and_public_versus_statutory(self):
        with self.app.app_context():
            employee,a,b,summary=self.setup_monthly()
            row=employee.current_assignment
            row.workweek_days=Decimal('5'); row.effective_to=date(2026,8,14)
            later=EmployeeAssignment(employee=employee,project=a,payroll_group='site_monthly',
                workweek_days=Decimal('6'),effective_from=date(2026,8,15),status='active')
            db.session.add(later)
            for day in (7,21):
                db.session.add(WorkCalendarHoliday(region_id=a.region_id,holiday_date=date(2026,8,day),
                    name=f'QA public only {day}',applies_to_public=True,applies_to_statutory=False))
            db.session.flush()
            rows=[dict(project_id=b.id,start='2026-08-01',end='2026-08-31',basis=WORKDAY_BASIS)]
            weights=allocation_weights(employee,'2026-08',rows)
            self.assertEqual(weights[date(2026,8,7)],[(a,Decimal(1))])
            self.assertEqual(weights[date(2026,8,8)],[(a,Decimal(1))])
            self.assertEqual(weights[date(2026,8,15)],[(b,Decimal(1))])
            self.assertEqual(weights[date(2026,8,21)],[(b,Decimal(1))])

    def test_sunday_extra_project_independent_from_basic_salary(self):
        with self.app.app_context():
            employee,a,b,summary=self.setup_monthly('site_monthly')
            segment=summary.segments[0]
            segment.sunday_holiday_days=1; segment.ecall_count=1
            db.session.add(AttendanceSpecialDay(summary=summary,segment=segment,project=b,
                period_kind='current_1_20',work_date=date(2026,8,9),day_kind='rest_day',days=1,handling='pay'))
            db.session.flush()
            baseline=calculate_employee(employee,'2026-08')
            summary.monthly_project_allocation=[dict(project_id=b.id,start='2026-08-09',end='2026-08-09',basis=WORKDAY_BASIS)]
            result=calculate_employee(employee,'2026-08')
            self.assertFalse(result['blockers'],result['blockers'])
            self.assertEqual(result['gross_amount'],baseline['gross_amount'])
            home=next(x for x in result['lines'] if x['project']==a)
            extra=next(x for x in result['lines'] if x['project']==b)
            self.assertEqual(home['base_amount'],31000)
            self.assertEqual(extra['base_amount'],0)
            self.assertEqual(extra['holiday_amount'],1000)
            self.assertEqual(extra['ecall_amount'],400)

    def test_legacy_save_preserves_rule_until_explicit_conversion(self):
        from werkzeug.datastructures import MultiDict
        from hkr_hr.attendance.api import update_allocation_from_form
        with self.app.app_context():
            employee,a,b,summary=self.setup_monthly()
            summary.monthly_project_allocation=[dict(project_id=b.id,start='2026-08-01',end='2026-08-31')]
            form=MultiDict(dict(allocation_present='1',allocation_enabled='on',allocation_project=str(b.id),
                allocation_start='2026-08-01',allocation_end='2026-08-31'))
            update_allocation_from_form(summary,form)
            self.assertEqual(summary.monthly_project_allocation[0]['basis'],'calendar')
            self.assertEqual(allocation_weights(employee,'2026-08',summary.monthly_project_allocation)[date(2026,8,9)][0][0],b)
            form['allocation_convert']='on'
            update_allocation_from_form(summary,form)
            self.assertEqual(summary.monthly_project_allocation[0]['basis'],WORKDAY_BASIS)
            self.assertEqual(allocation_weights(employee,'2026-08',summary.monthly_project_allocation)[date(2026,8,9)][0][0],a)
    def test_full_transfer_split_calendar_allowances_and_mpf_once(self):
        with self.app.app_context():
            employee, a, b, summary = self.setup_monthly()
            for kind, amount in [('meal',60), ('transport',40), ('special',3100)]:
                db.session.add(EmployeeAllowance(employee=employee, allowance_type=kind, amount=amount,
                    currency='HKD', effective_from=date(2026,8,1), status='active', label=kind))
            db.session.flush()
            baseline = calculate_employee(employee,'2026-08')
            self.assertEqual(next(x for x in baseline['lines'] if x['project']==a)['working_days'],31)
            for ranges, expected in [([dict(project_id=b.id,start='2026-08-01',end='2026-08-31')],{b.id:31}),
                                     (self.ranges(a,b),{a.id:10,b.id:21})]:
                summary.monthly_project_allocation = ranges
                db.session.flush()
                result = calculate_employee(employee,'2026-08')
                self.assertFalse(result['blockers'])
                self.assertEqual(result['gross_amount'],baseline['gross_amount'])
                self.assertEqual(result['employee_mpf'],baseline['employee_mpf'])
                for line in result['lines']:
                    days = Decimal(expected[line['project'].id])
                    self.assertEqual(line['working_days'],days)
                    self.assertEqual(line['base_amount'],days*1000)
                    self.assertEqual(line['traffic_meal_allowance_amount'],days*100)
                    self.assertEqual(line['special_allowance_amount'],days*100)
                run = snapshot_payroll('2026-08','management',[result],User.query.first().id)
                sheet = build_group_workbook(run,'management').active
                self.assertEqual(sum(sheet.cell(r,12).value for r in range(7,7+len(result['lines']))),31)
                saved=run.employee_results[0]
                values=[monthly_values(saved,line,i==0,7+i) for i,line in enumerate(result_lines(saved))]
                self.assertEqual(sum(row[37] for row in values),1500)
                self.assertTrue(all(sheet.cell(r,37).value in (0,'=0') for r in range(8,7+len(result['lines']))))

    def test_leave_days_rounding_and_snapshot_export_per_project(self):
        with self.app.app_context():
            employee,a,b,summary = self.setup_monthly('site_monthly')
            employee.salaries[0].amount=Decimal('15400')
            employee.current_period.confirmation_date=date(2026,1,1)
            # 6-day schedule: Mon/Tue and Thu are working leave days.
            for start,end,kind,days in [(3,4,'sick',2),(13,13,'sick',1),(14,14,'unpaid',1),(17,17,'annual',1)]:
                db.session.add(EmployeeAnnualLeaveRecord(employee=employee,leave_date=date(2026,8,start),
                    end_date=date(2026,8,end), days=days, entitlement_year=2026,leave_type=kind,status='active'))
            db.session.flush()
            baseline=calculate_employee(employee,'2026-08')
            self.assertFalse(baseline['blockers'],baseline['blockers'])
            summary.monthly_project_allocation=self.ranges(a,b)
            db.session.flush()
            result=calculate_employee(employee,'2026-08')
            self.assertEqual(result['gross_amount'],baseline['gross_amount'])
            self.assertEqual(result['sick_leave_amount'],baseline['sick_leave_amount'])
            self.assertEqual(sum(x['working_days'] for x in result['lines']),27)
            run=snapshot_payroll('2026-08','site_monthly',[result],User.query.first().id)
            sheet=build_group_workbook(run,'site_monthly').active
            self.assertEqual(sum(sheet.cell(r,29).value for r in (7,8)),3)
            sick=sum(Decimal(str(sheet.cell(r,29).value))*Decimal(str(sheet.cell(r,30).value)) for r in (7,8))
            self.assertEqual(sick.quantize(Decimal('.01')),result['sick_leave_amount'])

    def test_invalid_ranges_and_save_correction_audit(self):
        with self.app.app_context():
            employee,a,b,summary=self.setup_monthly()
            eid,sid=employee.id,summary.id
            good=self.ranges(a,b)
            for bad in ([good[0]], [good[0],{**good[1],'start':'2026-08-10'}],
                        [{**good[0],'start':'2026-07-31'},good[1]],
                        [{**good[0],'project_id':999999},good[1]]):
                with self.assertRaises(ProjectAllocationError): allocation_dates(employee,'2026-08',bad)
            db.session.commit()
            form=dict(employee_id=str(eid),year_month='2026-08',allocation_present='1',allocation_enabled='on',
                      allocation_project=[str(a.id),str(b.id)],allocation_start=['2026-08-01','2026-08-11'],
                      allocation_end=['2026-08-10','2026-08-31'],current_1_20_project_id=str(b.id),current_1_20_ot_hours='4')
        response=self.client.post(f'/attendance/summaries/{sid}/correct',data=form,follow_redirects=True)
        self.assertEqual(response.status_code,200)
        with self.app.app_context():
            row=db.session.get(AttendanceMonthlySummary,sid)
            self.assertEqual(len(row.monthly_project_allocation),2)
            self.assertEqual(row.monthly_project_allocation[1]['project_name'],'QA Project B')
        form['allocation_start']=['2026-08-01','2026-08-10']
        self.client.post(f'/attendance/summaries/{sid}/correct',data=form)
        with self.app.app_context():
            self.assertEqual(db.session.get(AttendanceMonthlySummary,sid).monthly_project_allocation[1]['start'],'2026-08-11')
        form.pop('allocation_enabled')
        self.client.post(f'/attendance/summaries/{sid}/correct',data=form)
        with self.app.app_context():
            self.assertIsNone(db.session.get(AttendanceMonthlySummary,sid).monthly_project_allocation)

    def test_calendar_lengths_and_nonstandard_salary_rejected(self):
        with self.app.app_context():
            employee,a,b,summary=self.setup_monthly()
            for year,month in [(2026,2),(2028,2),(2026,4),(2026,8)]:
                last=calendar.monthrange(year,month)[1]
                ym=f'{year}-{month:02d}'
                days=allocation_dates(employee,ym,[dict(project_id=b.id,start=f'{ym}-01',end=f'{ym}-{last}')])
                self.assertEqual(len(days),last)
            employee.salaries[0].monthly_pay_method='attendance_days'
            db.session.flush()
            with self.assertRaises(ProjectAllocationError):
                allocation_dates(employee,'2026-08',self.ranges(a,b))

    def test_exempt_without_scheme_and_clear_exemption_validation(self):
        with self.app.app_context():
            employee,a,b,summary=self.setup_monthly()
            eid=employee.id
            db.session.commit()
        response=self.client.post(f'/employees/{eid}/mpf',data=dict(effective_from='2026-08-01',mpf_exempt='on'),follow_redirects=True)
        self.assertIn('MPF 記錄已保存',response.get_data(as_text=True))
        with self.app.app_context():
            employee=db.session.get(Employee,eid)
            record=EmployeeMpfEnrollment.query.filter_by(employee_id=eid,effective_from=date(2026,8,1)).one()
            rid=record.id
            self.assertIsNone(record.scheme_id)
            self.assertTrue(mpf_data_item(employee,date(2026,8,31))['ok'])
            result=calculate_employee(employee,'2026-08')
            self.assertEqual(result['employee_mpf'],0)
            self.assertEqual(result['employer_mpf'],0)
            self.assertEqual(mpf_export_issues(result),[])
            # A scheme-less exemption must not block all-scheme export for others.
            other_id,_=self.employee('management',number=2)
            other=db.session.get(Employee,other_id)
            db.session.add(AttendanceMonthlySummary(employee=other,year_month='2026-08',status='received'))
            db.session.commit()
        archive=self.client.post('/mpf-contributions/export',data=dict(year_month='2026-08',scheme_code='all'))
        self.assertEqual(archive.status_code,200)
        # With only one non-exempt scheme the export returns its XLSX directly.
        self.assertEqual(archive.content_type,'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        self.client.post(f'/mpf-enrollments/{rid}/correct',data=dict(effective_from='2026-08-01'))
        with self.app.app_context():
            self.assertTrue(db.session.get(EmployeeMpfEnrollment,rid).is_exempt)


if __name__=='__main__': unittest.main()
