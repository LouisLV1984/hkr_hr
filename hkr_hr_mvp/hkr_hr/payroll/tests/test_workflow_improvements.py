"""Synthetic regression tests for the November small-team workflow changes."""
import hashlib
import io
import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from openpyxl import load_workbook
from sqlalchemy import text, inspect
import unittest
from tests.fixtures import PayrollTestCase, pdf_bytes
from hkr_hr.platform.db import db, User
from hkr_hr.employees.api import Employee, EmployeeSalary
from hkr_hr.documents.api import GeneratedContract
from hkr_hr.payroll.api import PayrollRun, EmployeeFinalPaymentCase
from hkr_hr.attendance.api import AttendanceBatch, AttendanceBatchItem, AttendanceMonthlySummary, AttendanceSegment
from hkr_hr.references.api import WorkCalendarHoliday
from hkr_hr.payroll.api import calculate_employee, snapshot_payroll, apply_actual_segments
from hkr_hr.attendance.api import allocation_issue
from hkr_hr.payroll.api import payroll_items
from hkr_hr.payroll.api import build_group_workbook, mpf_preview_rows
from hkr_hr.documents.api import contract_context

class WorkflowImprovementsTests(PayrollTestCase):

    def test_contract_drafts_keep_zero_effective_salary_and_original_files(self):
        eid = self.ready()
        with self.app.app_context():
            employee = db.session.get(Employee, eid)
            employee.current_period.notice_period_value = 30
            employee.current_period.notice_period_unit = "day"
            employee.current_salary.effective_to = date(2026,11,30)
            db.session.add(EmployeeSalary(employee_id=eid, effective_from=date(2026,12,1),
                salary_basis="monthly", currency="HKD", amount=40000, status="active"))
            db.session.commit(); db.session.expire_all()
            ctx = contract_context(db.session.get(Employee,eid), date(2026,11,4),date(2026,12,1),7,0,0)
            self.assertIn("40,000", ctx["salary_text"])
        form=dict(template_code="OFFICE", contract_date="2026-11-04", effective_date="2026-12-01",
                  annual_leave_days="7", notice_period_days="0", probation_months="0")
        self.assertEqual(self.client.post(f"/employees/{eid}/contracts/generate",data=form).status_code,302)
        with self.app.app_context():
            first=GeneratedContract.query.one()
            path=Path(first.output_path); digest=hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertEqual(first.probation_months,0)
        form.update(notice_period_days="60",probation_months="6")
        self.client.post(f"/employees/{eid}/contracts/generate",data=form)
        with self.app.app_context():
            rows=GeneratedContract.query.order_by(GeneratedContract.id).all()
            self.assertNotEqual(rows[0].output_path,rows[1].output_path)
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),digest)
            self.assertEqual(db.session.get(Employee,eid).current_period.notice_period_value,30)
        facts=self.client.get(f"/employees/{eid}/contracts/facts?effective_date=2026-12-01").get_json()
        self.assertIn("40,000",facts["salary"])

    def test_snapshot_keeps_identity_and_project_and_negative_is_not_ready(self):
        eid=self.ready()
        with self.app.app_context():
            employee=db.session.get(Employee,eid)
            row=calculate_employee(employee,"2026-08")
            run=snapshot_payroll("2026-08","management",[row],User.query.first().id)
            before=build_group_workbook(run,"management")["OFFICE"]
            runid = run.id
            expected=[before.cell(7,c).value for c in (2,5,6,7,8,9)]
            employee.english_name="Changed later"
            employee.employee_no="NEW-NUMBER"
            employee.current_assignment.project.name="Changed project"
            employee.current_period.start_date=date(2026,2,1)
            db.session.commit()
            after=build_group_workbook(run,"management")["OFFICE"]
            self.assertEqual(expected,[after.cell(7,c).value for c in (2,5,6,7,8,9)])
            self.assertFalse(payroll_items(dict(blockers=[],net_amount=-1,warnings=[]))[0]["ok"])
            self.assertFalse(payroll_items(None)[0]["ok"])
        summary=load_workbook(io.BytesIO(self.client.get(f"/export/payroll-summary?run_id={runid}").data)).active
        self.assertNotEqual(summary.cell(2,3).value,"NEW-NUMBER")
        certificate=load_workbook(io.BytesIO(self.client.get(f"/export/salary-certificate?employee_id={eid}&year_month=2026-08").data)).active
        self.assertNotEqual(certificate.cell(9,2).value,"Changed later")

    def test_rate_change_needs_date_allocation_and_pays_the_right_rate(self):
        eid,project=self.employee("site_daily")
        with self.app.app_context():
            employee=db.session.get(Employee,eid)
            employee.current_salary.effective_to=date(2026,8,10)
            db.session.add(EmployeeSalary(employee_id=eid,effective_from=date(2026,8,11),
                salary_basis="daily",currency="HKD",amount=2000,status="active"))
            db.session.commit();db.session.expire_all();employee=db.session.get(Employee,eid)
            segment=AttendanceSegment(period_kind="current_1_20", project_id=project,
                working_days=5, ot_hours=0,sunday_holiday_days=0,large_ecall_count=0,ecall_count=0,other_allowance_amount=0)
            self.assertIsNotNone(allocation_issue(employee,segment,date(2026,8,1),date(2026,8,20)))
            with self.assertRaises(ValueError):
                apply_actual_segments(employee,[segment],date(2026,8,1),date(2026,8,20),{})
            def parts(first,last):
                return [dict(start="2026-08-01",end="2026-08-10",working_days=first),
                        dict(start="2026-08-11",end="2026-08-20",working_days=last)]
            segment.rate_allocations=parts(5,0)
            self.assertEqual(apply_actual_segments(employee,[segment],date(2026,8,1),date(2026,8,20),{}),5000)
            segment.rate_allocations=parts(0,5)
            self.assertEqual(apply_actual_segments(employee,[segment],date(2026,8,1),date(2026,8,20),{}),10000)
            self.assertEqual(self.client.get(f"/attendance?month=2026-08&employee_id={eid}").status_code,200)

    def test_departure_mpf_export_and_retired_manual_editor(self):
        eid=self.ready()
        with self.app.app_context():
            employee=db.session.get(Employee,eid);period=employee.current_period;period.end_date=date(2026,8,20)
            db.session.add(EmployeeFinalPaymentCase(employee_id=eid, employment_period_id=period.id,settlement_month="2026-08",
                actual_working_days=14,legacy_leave_days=0,post_2024_leave_days=0,statutory_holiday_days=0,benefit_type="none"))
            db.session.commit()
            row=mpf_preview_rows("2026-08")[0]
            self.assertTrue(all(k in row for k in ("monthly_pay_method","workweek_days","statutory_holiday_paid_days")))
        response=self.client.post("/mpf-contributions/export",data={"year_month":"2026-08","scheme_code":"all"})
        self.assertEqual(response.status_code,200)
        html=self.client.get("/final-payment?year_month=2026-08").get_data(as_text=True)
        self.assertIn("rate_allocations", self.app.jinja_loader.get_source(self.app.jinja_env,"payroll/final_payment.html")[0])
        response=self.client.post(f"/employees/{eid}/payroll-adjustments",data={"year_month":"2026-08","label":"Correction","amount":"100","return_to":"final_payment"})
        self.assertEqual(response.status_code,302)
        self.assertIn("/final-payment",response.headers["Location"])

    def test_queue_and_duplicate_keep_same_batch_and_form(self):
        eid=self.ready()
        headers={"X-HKR-Profile-Editor":"1","X-HKR-Upload-Queue":"1"}
        def upload(batch=None):
            data={"year_month":"2026-08","files":(io.BytesIO(pdf_bytes("same")),"same.pdf")}
            if batch:data["batch_id"]=batch
            return self.client.post("/attendance/batches",data=data,headers=headers).get_json()
        first=upload();second=upload(first["batch_id"])
        self.assertEqual(first["batch_id"],second["batch_id"])
        with self.app.app_context():
            self.assertEqual(AttendanceBatch.query.count(),1)
            items=AttendanceBatchItem.query.order_by(AttendanceBatchItem.id).all()
            ids=[i.id for i in items];paths=[i.stored_path for i in items]
            self.assertEqual(len(set(paths)),2)
        data={"employee_id":eid,"year_month":"2026-08","current_1_20_ot_hours":"2","remarks":"first"}
        self.client.post(f"/attendance/items/{ids[0]}/save",data=data)
        data.update(current_1_20_ot_hours="7",remarks="retain this")
        response=self.client.post(f"/attendance/items/{ids[1]}/save",data=data,headers={"X-HKR-Profile-Editor":"1"})
        self.assertTrue(response.get_json()["confirm_duplicate"])
        data["confirm_duplicate"]="1"
        self.client.post(f"/attendance/items/{ids[1]}/save",data=data)
        with self.app.app_context():
            summary=AttendanceMonthlySummary.query.filter_by(employee_id=eid,year_month="2026-08").one()
            self.assertEqual(summary.remarks,"retain this")
            db.session.get(Employee,eid).current_period.end_date=date(2026,8,20);db.session.commit()
        html=self.client.get(f"/attendance?month=2026-08&item_id={ids[1]}&correct_identity=1").get_data(as_text=True)
        self.assertIn(f'data-employee-id="{eid}"',html)

    def test_initial_setup_month_context_and_offline_calendar(self):
        eid,_=self.create_employee("HKR","management","Initial","Initial")
        form=dict(effective_from="2026-01-01",salary_basis="monthly",amount="30000",
                  currency="HKD",bank_name="Bank",account_no="123",mpf_exempt="on")
        self.assertEqual(self.client.post(f"/employees/{eid}/initial-setup",data=form).status_code,302)
        with self.app.app_context():
            e=db.session.get(Employee,eid)
            self.assertEqual(len(e.employment_periods),1);self.assertEqual(len(e.assignments),1)
            self.assertEqual(len(e.salaries),1);self.assertEqual(len(e.bank_accounts),1);self.assertEqual(len(e.mpf_enrollments),1)
        self.client.post(f"/employees/{eid}/initial-setup",data=form)
        with self.app.app_context():self.assertEqual(len(db.session.get(Employee,eid).salaries),1)
        for url in ("/employees?month=2026-08",f"/employees/{eid}","/attendance?month=2026-08","/attendance-payroll?year_month=2026-08","/salary-records?month=2026-08","/annual-leave?view=injury",f"/annual-leave?employee_id={eid}","/references?list=work_calendar"):
            with self.subTest(url=url):self.assertEqual(self.client.get(url).status_code,200)
        csv=b"date,name,scope,region_code\n2027-01-02,Synthetic holiday,both,HK\n"
        response=self.client.post("/references/work-calendar/csv",data={"calendar_csv":(io.BytesIO(csv),"calendar.csv")})
        self.assertEqual(response.status_code,302)
        with self.app.app_context():
            holiday=WorkCalendarHoliday.query.filter_by(holiday_date=date(2027,1,2)).one()
            self.assertTrue(holiday.applies_to_statutory and holiday.applies_to_public)
        self.assertIn(b"Synthetic holiday",self.client.get("/references/work-calendar/csv?calendar_year=2027").data)

    def test_additive_rate_columns_preserve_existing_rows(self):
        from hkr_hr.workbench.api import apply_additive_migrations
        with self.app.app_context():
            for table in ("attendance_segments", "employee_final_payment_cases"):
                db.session.execute(text(f'ALTER TABLE "{table}" DROP COLUMN rate_allocations'))
            db.session.commit()
            employees_before=Employee.query.count()
            changed=apply_additive_migrations()
            self.assertIn("attendance_segments.rate_allocations",changed)
            self.assertIn("employee_final_payment_cases.rate_allocations",changed)
            self.assertEqual(Employee.query.count(),employees_before)
            self.assertEqual(apply_additive_migrations(),[])

if __name__=="__main__":unittest.main()
