"""Synthetic isolated-data acceptance tests for the independent salary register."""
import html
import io
import re
import unittest
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import patch

import test_audit_integrity as fixture
from models import (db, Employee, ReferenceValue, SalaryRecord, AuditLog, EmployeeDocument,
                    PayrollRun, PayrollEmployeeResult, EmployeeAnnualLeaveRecord)
from tools.salary_records import annual_summary, money
from openpyxl import load_workbook


class SalaryRecordTests(unittest.TestCase):
    setUp=fixture.AuditIntegrityTests.setUp
    tearDown=fixture.AuditIntegrityTests.tearDown
    login=fixture.AuditIntegrityTests.login
    create_employee=fixture.AuditIntegrityTests.create_employee
    complete_employee=fixture.AuditIntegrityTests.complete_employee
    employee=fixture.AuditIntegrityTests.employee

    def entity(self):
        with self.app.app_context():
            from tools.hr_core import reference_by_code
            return reference_by_code('payroll_entity','HK_RIVER').id

    def form(self,eid,month='2026-04',entity=None):
        page=self.client.get('/salary-records',query_string=dict(month=month,entity_id=entity or self.entity(),employee_id=eid))
        self.assertEqual(page.status_code,200,page.get_data(as_text=True)[:500])
        token=html.unescape(re.search(r'name="editor_token" value="([^"]+)"',page.get_data(as_text=True))[1])
        from routes.salary_records import serializer
        with self.app.app_context(): data=serializer().loads(token)
        form={'editor_token':token}
        for key,row in data['rows'].items():
            form.update({f'{key}.{f}':v for f,v in row['values'].items()})
        return form

    def values(self,form,eid,gross='10000',mpf='1500',net='8400',currency='HKD',remarks='Manual adjustment'):
        form.update({f'{eid}.{f}':v for f,v in dict(gross_amount=gross,employee_mpf=mpf,net_amount=net,currency=currency,remarks=remarks).items()})
        return form

    def save(self,form):
        return self.client.post('/salary-records/save',data=form)

    def test_create_override_catchup_and_no_payroll_or_leave_side_effect(self):
        eid,_=self.employee()
        response=self.save(self.values(self.form(eid),eid))
        self.assertEqual(response.status_code,200,response.json)
        with self.app.app_context():
            row=SalaryRecord.query.one()
            self.assertEqual((row.gross_amount,row.employee_mpf,row.net_amount),(Decimal(10000),Decimal(1500),Decimal(8400)))
            self.assertEqual(PayrollRun.query.count(),0)
            self.assertEqual(EmployeeAnnualLeaveRecord.query.count(),0)
            self.assertEqual(AuditLog.query.filter_by(entity_type='SalaryRecord').count(),1)
        self.assertEqual(self.client.get(response.json['redirect']).status_code,200)
        self.assertIn('10,000.00',self.client.get(f'/employees/{eid}?tab=attendance').get_data(as_text=True))
        annual=self.client.get('/salary-records/annual?year=2026')
        self.assertEqual(annual.status_code,200)
        self.assertIn('8,400.00',annual.get_data(as_text=True))

    def test_configured_currency_dropdown_grouped_amounts_and_noop_save(self):
        eid,_=self.employee()
        with self.app.app_context():
            from models import ReferenceList
            db.session.add(ReferenceValue(list_id=ReferenceList.query.filter_by(code='currency').one().id,
                code='EUR',display_name='Euro QA',normalized_name='euro qa'))
            db.session.commit()
        page=self.client.get('/salary-records',query_string=dict(month='2026-04',entity_id=self.entity())).get_data(as_text=True)
        self.assertRegex(page,rf'<select[^>]+name="{eid}\.currency"')
        self.assertIn('value="EUR"',page)
        self.assertIn('Euro QA',page)
        self.assertEqual(self.save(self.values(self.form(eid),eid,currency='ZZZ')).status_code,422)
        response=self.save(self.values(self.form(eid),eid,currency='EUR',gross='15,000.00',mpf='1,500.00',net='13,500.00'))
        self.assertEqual(response.status_code,200,response.json)
        page=self.client.get(response.json['redirect']).get_data(as_text=True)
        self.assertIn('value="15,000.00"',page)
        self.assertIn('15,000.00',self.client.get('/salary-records/annual?year=2026').get_data(as_text=True))
        # Display commas must not manufacture an edit/revision when unchanged rows are submitted.
        form=self.form(eid)
        for field in ('gross_amount','employee_mpf','net_amount'):
            form[f'{eid}.{field}']=f'{Decimal(form[f"{eid}.{field}"]):,.2f}'
        self.assertEqual(self.save(form).status_code,200)
        with self.app.app_context():
            record=SalaryRecord.query.one()
            self.assertEqual(record.revision,1)
            self.assertEqual(record.gross_amount,Decimal('15000'))
            record.currency='ZZZ'  # Legacy free-text currency remains visible, never silently replaced.
            db.session.commit()
        page=self.client.get(response.json['redirect']).get_data(as_text=True)
        self.assertIn('value="ZZZ" selected',page)
        form=self.form(eid); form[f'{eid}.remarks']='Legacy currency retained'
        self.assertEqual(self.save(form).status_code,200)

    def test_blank_rows_not_zero_partial_invalid_money_transaction(self):
        eid,_=self.employee()
        form=self.form(eid)
        self.assertEqual(self.save(form).status_code,200)
        with self.app.app_context(): self.assertEqual(SalaryRecord.query.count(),0)
        for value in ('','NaN','Infinity','12.345','1000000000000'):
            response=self.save(self.values(self.form(eid),eid,net=value))
            self.assertEqual(response.status_code,422,response.json)
        self.assertEqual(self.save(self.values(self.form(eid),eid,gross='0',mpf='0',net='0')).status_code,200)
        with self.app.app_context(): self.assertEqual(SalaryRecord.query.one().net_amount,0)

    def test_stale_duplicate_withdraw_reactivate_preserve_audit(self):
        eid,_=self.employee()
        stale=self.values(self.form(eid),eid)
        self.assertEqual(self.save(stale).status_code,200)
        self.assertEqual(self.save(stale).status_code,422)
        form=self.form(eid)
        with self.app.app_context(): rid=SalaryRecord.query.one().id
        self.assertEqual(self.client.post(f'/salary-records/{rid}/withdraw',data={'revision':1,'reason':''}).status_code,422)
        self.assertEqual(self.client.post(f'/salary-records/{rid}/withdraw',data={'revision':1,'reason':'Wrong month'}).status_code,200)
        self.assertEqual(self.save(self.values(form,eid,net='8300')).status_code,422)
        self.assertEqual(self.client.post(f'/salary-records/{rid}/withdraw',data={'revision':1,'reason':'Repeated'}).status_code,409)
        self.assertEqual(self.save(self.values(self.form(eid),eid,net='8500')).status_code,200)
        with self.app.app_context():
            self.assertEqual(SalaryRecord.query.count(),1)
            self.assertEqual(SalaryRecord.query.one().revision,3)
            self.assertEqual(AuditLog.query.filter_by(entity_type='SalaryRecord').count(),3)

    def test_multiple_rows_atomic_and_tampered_token(self):
        eid,_=self.employee()
        eid2,_=self.employee(number=2)
        form=self.values(self.form(eid),eid)
        self.values(form,eid2,net='invalid')
        self.assertEqual(self.save(form).status_code,422)
        with self.app.app_context(): self.assertEqual(SalaryRecord.query.count(),0)
        form['editor_token']+='bad'
        self.assertEqual(self.save(form).status_code,422)

    def test_annual_april_start_departed_missing_currency_entity_separation(self):
        eid,_=self.employee()
        with self.app.app_context():
            employee=db.session.get(Employee,eid)
            employee.employment_periods[0].start_date=date(2026,4,15)
            employee.employment_periods[0].end_date=date(2026,6,5)
            employee.status='terminated'
            from models import ReferenceList
            entity=ReferenceValue(list_id=ReferenceList.query.filter_by(code='payroll_entity').one().id,code='QA_OTHER',display_name='QA Other',normalized_name='qa other')
            db.session.add(entity); db.session.commit(); other=entity.id
        self.save(self.values(self.form(eid),eid))
        self.save(self.values(self.form(eid,'2026-05'),eid,currency='CNY',net='8500'))
        self.save(self.values(self.form(eid,entity=other),eid,gross='500',mpf='0',net='500'))
        with self.app.app_context():
            rows,details,months=annual_summary(2026)
            self.assertEqual((months[0],months[-1]),('2026-04','2027-03'))
            mine=[r for r in rows if r['employee'].id==eid]
            self.assertEqual(len(mine),3)
            normal=[r for r in mine if r['entity_id']!=other]
            self.assertTrue(all(r['missing']==['2026-06'] for r in normal))
            self.assertEqual(len(details),3)
        self.assertEqual(self.client.get('/salary-records/annual?year=2025').status_code,400)
        self.assertEqual(self.client.get('/salary-records?month=2026-03').status_code,400)

    def test_attachment_history_retained_and_invalid_upload_preserves_record(self):
        eid,_=self.employee()
        form=self.values(self.form(eid),eid)
        form[f'{eid}.evidence']=(io.BytesIO(b'%PDF-1.4\nQA\n%%EOF'),'qa.pdf')
        self.assertEqual(self.save(form).status_code,200)
        with self.app.app_context():
            did=SalaryRecord.query.one().evidence_document_id
            self.assertEqual(EmployeeDocument.query.filter_by(id=did).one().category,'salary_record')
        form=self.values(self.form(eid),eid,net='8000')
        form[f'{eid}.evidence']=(io.BytesIO(b'bad'),'bad.pdf')
        self.assertEqual(self.save(form).status_code,422)
        with self.app.app_context():
            self.assertEqual(SalaryRecord.query.one().net_amount,8400)
            self.assertEqual(SalaryRecord.query.one().evidence_document_id,did)
        form=self.values(self.form(eid),eid,net='8500')
        form[f'{eid}.evidence']=(io.BytesIO(b'%PDF-1.4\nQA2\n%%EOF'),'qa2.pdf')
        self.assertEqual(self.save(form).status_code,200)
        page=self.client.get('/salary-records',query_string=dict(month='2026-04',entity_id=self.entity())).get_data(as_text=True)
        self.assertIn(f'/documents/{did}/open',page)

    def test_export_typed_numbers_dates_missing_and_formula_injection(self):
        eid,_=self.employee()
        self.save(self.values(self.form(eid),eid,remarks='=1+1'))
        response=self.client.get('/salary-records/annual/export?year=2026')
        self.assertEqual(response.status_code,200)
        workbook=load_workbook(io.BytesIO(response.data))
        self.assertEqual(len(workbook.worksheets),2)
        summary,detail=workbook.worksheets
        self.assertEqual(summary['E6'].value,10000)
        self.assertEqual(detail['D6'].value,datetime(2026,4,1))
        self.assertEqual(detail['D6'].number_format,'yyyy-mm')
        self.assertEqual(detail['I6'].value,100)
        self.assertEqual(detail['J6'].value,'=1+1')
        self.assertEqual(detail['J6'].data_type,'s')
        self.assertEqual(detail.freeze_panes,'C6')
        if __import__('os').environ.get('HR_QA_EXPORT_ROOT'):
            from pathlib import Path
            target=Path(__import__('os').environ['HR_QA_EXPORT_ROOT']); target.mkdir(parents=True,exist_ok=True)
            workbook.save(target/'salary_records_qa.xlsx')

    def test_login_csrf_languages_and_prefill_missing_no_writes(self):
        eid,_=self.employee()
        for lang in ('zh-Hant','zh-Hans','en'):
            page=self.client.get('/salary-records',query_string=dict(month='2026-04',entity_id=self.entity(),lang=lang))
            self.assertEqual(page.status_code,200)
            self.assertNotIn('salary_record.title',page.get_data(as_text=True))
        response=self.client.get('/salary-records/prefill',query_string=dict(month='2026-04',entity_id=self.entity(),employee_id=eid))
        self.assertEqual(response.status_code,404)
        self.app.config['CSRF_ENABLED']=True
        self.assertEqual(self.save({'editor_token':'no'}).status_code,400)
        self.client=self.app.test_client()
        self.assertEqual(self.client.get('/salary-records').status_code,302)

    def test_saved_payroll_prefill_is_scoped_read_only_and_keeps_register_independent(self):
        eid,_=self.employee()
        self.save(self.values(self.form(eid),eid))
        with self.app.app_context():
            for amount,entity_code in [(20000,'HK_RIVER'),(30000,'WRONG_ENTITY')]:
                run=PayrollRun(year_month='2026-04',payroll_group='site_daily',rule_version='QA')
                db.session.add(run); db.session.flush()
                db.session.add(PayrollEmployeeResult(run_id=run.id,employee_id=eid,currency='HKD',
                    gross_amount=amount,employee_mpf=1500,net_amount=amount-1500,
                    calculation_json={'payroll_entity_code':entity_code}))
            db.session.commit()
        response=self.client.get('/salary-records/prefill',query_string=dict(employee_id=eid,month='2026-04',entity_id=self.entity()))
        self.assertEqual(response.status_code,200,response.json)
        self.assertEqual(Decimal(response.json['values']['gross_amount']),20000)
        with self.app.app_context():
            self.assertEqual(SalaryRecord.query.one().gross_amount,10000)
            self.assertEqual(PayrollRun.query.count(),2)

    def test_reference_usage_and_evidence_single_owner(self):
        eid,_=self.employee()
        form=self.values(self.form(eid),eid)
        form[f'{eid}.evidence']=(io.BytesIO(b'%PDF-1.4\nQA\n%%EOF'),'owned.pdf')
        self.save(form)
        with self.app.app_context():
            from routes.references import usage_count, historical_reference_employee_ids
            record=SalaryRecord.query.one(); did=record.evidence_document_id
            entity=record.payroll_entity
            self.assertGreaterEqual(usage_count(entity),2)
            self.assertIn(eid,historical_reference_employee_ids(entity))
        response=self.client.post(f'/documents/{did}/status',data=dict(status='voided',reason='wrong entry'))
        self.assertEqual(response.status_code,302)
        with self.app.app_context():
            self.assertEqual(db.session.get(EmployeeDocument,did).status,'active')
            self.assertEqual(SalaryRecord.query.one().revision,1)

    def test_hr_access_and_new_hire_missing_months(self):
        eid,_=self.employee()
        with self.app.app_context():
            employee=db.session.get(Employee,eid)
            employee.employment_periods[0].start_date=date(2026,7,1)
            db.session.commit()
        self.login('hr_test','test-hr-password')
        self.assertEqual(self.save(self.values(self.form(eid,'2026-07'),eid)).status_code,200)
        with self.app.app_context():
            rows,_,_=annual_summary(2026)
            self.assertEqual(rows[0]['missing'],['2026-08','2026-09'])

    def test_commit_failure_cleans_new_attachment_and_no_partial_records(self):
        eid,_=self.employee()
        form=self.values(self.form(eid),eid)
        form[f'{eid}.evidence']=(io.BytesIO(b'%PDF-1.4\nQA\n%%EOF'),'rollback.pdf')
        with patch('routes.salary_records.write_audit',side_effect=ValueError('salary_record.stale')):
            self.assertEqual(self.save(form).status_code,422)
        with self.app.app_context():
            self.assertEqual(SalaryRecord.query.count(),0)
            self.assertEqual(EmployeeDocument.query.filter_by(category='salary_record').count(),0)
            root=self.app.config['HKR_HR_UPLOAD_ROOT']
            self.assertEqual(list(root.rglob('*rollback*')),[])


if __name__=='__main__': unittest.main()
