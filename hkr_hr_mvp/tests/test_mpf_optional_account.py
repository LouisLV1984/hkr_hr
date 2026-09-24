"""Isolated fixtures: optional member account must not affect contributions."""
import io
import re
import unittest
from datetime import date
from openpyxl import load_workbook
import test_v1_workflows as workflow
from models import db, Employee, MpfScheme, EmployeeMpfEnrollment, AuditLog, AttendanceMonthlySummary
from tools.completeness import mpf_data_item
from routes.payroll import mpf_export_issues


class OptionalMpfAccountTests(unittest.TestCase):
    setUp = workflow.V1WorkflowTests.setUp
    tearDown = workflow.V1WorkflowTests.tearDown
    login = workflow.V1WorkflowTests.login
    create_employee = workflow.V1WorkflowTests.create_employee
    complete_employee = workflow.V1WorkflowTests.complete_employee

    def test_blank_create_correct_export_and_required_scheme(self):
        eid,_ = self.create_employee('ASMTP', 'management', '測試員工', 'OPTIONAL MPF QA')
        self.complete_employee(eid,'management','TMC046','monthly','30000','Q1234567','61234567')
        with self.app.app_context():
            scheme_id = MpfScheme.query.filter_by(code='BCT_MONTHLY').one().id
            db.session.add(AttendanceMonthlySummary(employee_id=eid,year_month='2026-08',status='received'))
            db.session.commit()
        values = dict(effective_from='2026-05-01',mpf_selection=str(scheme_id))
        response = self.client.post(f'/employees/{eid}/mpf',data=values,follow_redirects=True)
        self.assertIn('MPF 記錄已保存',response.get_data(as_text=True))
        with self.app.app_context():
            record = EmployeeMpfEnrollment.query.filter_by(employee_id=eid,effective_from=date(2026,5,1)).one()
            rid = record.id
            self.assertIsNone(record.member_account_no)
            self.assertTrue(mpf_data_item(db.session.get(Employee,eid),date(2026,8,1))['ok'])
        html = response.get_data(as_text=True)
        inputs = re.findall(r'<input\b[^>]*name="member_account_no"[^>]*>', html)
        self.assertGreaterEqual(len(inputs),2)
        self.assertTrue(all('required' not in tag for tag in inputs))
        self.assertIn('Member Account No.（可不填）', html)
        def export():
            response = self.client.post('/mpf-contributions/export',data=dict(year_month='2026-08',scheme_code='BCT_MONTHLY'))
            self.assertEqual(response.status_code,200)
            return load_workbook(io.BytesIO(response.data))['BILL_Submitted Employee(s)']
        blank = export()
        self.assertEqual(blank['A8'].value, 'OPTIONAL MPF QA')
        self.assertIsNone(blank['C8'].value)
        for account in ('QA-MEMBER-1', '   '):
            result = self.client.post(f'/mpf-enrollments/{rid}/correct',data={**values,'member_account_no':account},follow_redirects=True)
            self.assertEqual(result.status_code,200)
            sheet = export()
            self.assertEqual(sheet['C8'].value,account.strip() or None)
            for cell in ('H8','J8','K8','L8'):
                self.assertEqual(sheet[cell].value,blank[cell].value)
        with self.app.app_context():
            self.assertIsNone(db.session.get(EmployeeMpfEnrollment,rid).member_account_no)
            self.assertEqual(AuditLog.query.filter_by(action='mpf_enrollment_corrected',entity_id=rid).count(),2)
            count = EmployeeMpfEnrollment.query.filter_by(employee_id=eid).count()
            employee = db.session.get(Employee,eid)
            self.assertIn('未設定 MPF 計劃',mpf_export_issues(dict(employee=employee,blockers=[],mpf_enrollment=None)))
        for invalid in ({'effective_from':'2026-06-01'}, {'mpf_selection':str(scheme_id)}):
            self.client.post(f'/employees/{eid}/mpf',data=invalid)
        with self.app.app_context():
            self.assertEqual(EmployeeMpfEnrollment.query.filter_by(employee_id=eid).count(),count)
