from datetime import date
from decimal import Decimal
from unittest.mock import patch
import unittest

from tests.fixtures import PayrollTestCase
from models import db, Employee, EmployeeAnnualLeaveBalance, EmployeeAnnualLeaveRecord, AuditLog
from tools.annual_leave_policy import annual_rate, entitlement, rollover
from tools.annual_leave_setup import token
from tools.hr_core import annual_leave_summary


class FormulaTests(unittest.TestCase):
    def test_company_calendar_progression(self):
        self.assertEqual([annual_rate(date(2026,7,1), 7, y) for y in range(2026,2036)],
                         list(map(Decimal, [7,7,8,9,10,11,12,13,14,14])))
        self.assertEqual([annual_rate(date(2026,7,1), 8, y) for y in range(2026,2035)],
                         list(map(Decimal, [8,9,10,11,12,13,14,14,14])))
        self.assertEqual(annual_rate(date(2020,1,1),7,2026),12)
        self.assertEqual(annual_rate(date(2025,7,1),7,2026),7)
        self.assertEqual(annual_rate(date(2025,7,1),8,2026),9)

    def test_first_year_and_leap_rounding(self):
        self.assertEqual(entitlement(date(2026,10,10),7,2026),Decimal('1.5'))
        self.assertEqual(entitlement(date(2026,3,4),7,2026),6)
        self.assertEqual(entitlement(date(2026,7,1),7,2026),Decimal('3.5'))
        self.assertEqual(entitlement(date(2026,7,1),8,2026),4)
        self.assertEqual(entitlement(date(2024,1,1),7,2024),7)
        self.assertEqual(entitlement(date(2026,12,31),7,2026),0)

    def test_settlement_uses_raw_earning(self):
        self.assertEqual(entitlement(date(2026,7,1),7,2027,date(2027,3,31)),Decimal(7)*90/365)
        self.assertEqual(entitlement(date(2026,3,4),7,2026,date(2026,3,31)),Decimal(7)*28/365)


class SetupTests(PayrollTestCase):

    def test_date_change_requires_choice_and_keep_is_current_year_only(self):
        from tools.annual_leave_setup import apply
        eid,_=self.employee('management')
        self.setup(eid,preserve='0')
        with self.app.test_request_context():
            e=db.session.get(Employee,eid)
            with self.assertRaisesRegex(ValueError,'leave.date_choice_required'):
                apply(e,date(2026,7,1),Decimal(7),False,token(e))
            self.assertEqual(e.current_period.start_date,date(2026,3,4))
            result=apply(e,date(2026,7,1),Decimal(7),False,token(e),'keep_current')
            db.session.commit()
            self.assertEqual(Decimal(result['calculated']),Decimal('3.5'))
            self.assertEqual(annual_leave_summary(e,2026)['entitled'],6)
            self.assertEqual(annual_rate(e.current_period.start_date,7,2027),7)
            self.assertEqual(e.current_period.start_date,date(2026,7,1))
            apply(e,date(2026,10,10),Decimal(7),True,token(e),'recalculate')
            db.session.commit()
            self.assertEqual(annual_leave_summary(e,2026)['entitled'],Decimal('1.5'))
            self.assertIsNone(EmployeeAnnualLeaveBalance.query.filter_by(employee_id=eid,year=2026).one().entitled_days_override)
        page=self.client.get(f'/annual-leave?employee_id={eid}&year=2026').get_data(as_text=True)
        self.assertIn('id="annual-leave-setup-dialog"',page)
        self.assertIn('2026-10-10',page)

    def test_staff_record_date_choice_preserves_then_recalculates(self):
        eid,_=self.employee('management')
        self.setup(eid,preserve='0')
        staff=self.document(eid,'staff_record','C')
        url=f'/documents/{staff}/review'
        self.client.post(url,data=dict(start_date='2026-07-01'))
        with self.app.app_context():
            self.assertEqual(db.session.get(Employee,eid).current_period.start_date,date(2026,3,4))
        response=self.client.post(url,data=dict(start_date='2026-07-01',date_change_action='keep_current'))
        self.assertEqual(response.status_code,302)
        with self.app.app_context():
            e=db.session.get(Employee,eid)
            self.assertEqual(e.current_period.start_date,date(2026,7,1))
            self.assertEqual(annual_leave_summary(e,2026)['entitled'],6)
        self.client.post(url,data=dict(start_date='2026-10-10',date_change_action='recalculate'))
        with self.app.app_context():
            self.assertEqual(annual_leave_summary(db.session.get(Employee,eid),2026)['entitled'],Decimal('1.5'))

    def signed(self, eid):
        with self.app.app_context():
            return token(db.session.get(Employee,eid))

    def test_real_get_form_save_existing_balance_and_period(self):
        import re
        from html import unescape
        eid,_=self.employee('management')
        with self.app.app_context():
            e=db.session.get(Employee,eid)
            e.current_period.start_date=date(2026,3,4)
            e.current_period.contract_annual_leave_days=7
            db.session.add(EmployeeAnnualLeaveBalance(employee=e,year=2026,entitled_days_override=7))
            db.session.commit()
        page=self.client.get(f'/annual-leave?employee_id={eid}&year=2026').get_data(as_text=True)
        signed=unescape(re.search(r'name="setup_token" value="([^"]+)"',page).group(1))
        response=self.client.post(f'/employees/{eid}/annual-leave-setup',data=dict(
            start_date='2026-03-04',initial_days='7.0',preserve='0',setup_token=signed),
            headers={'X-HKR-Profile-Editor':'1'})
        self.assertEqual(response.status_code,200,response.get_data(as_text=True))
        self.assertIn('redirect',response.json)
        with self.app.app_context():
            self.assertEqual(annual_leave_summary(db.session.get(Employee,eid),2026)['entitled'],6)

    def test_row_read_order_is_not_a_business_change(self):
        from itsdangerous import URLSafeSerializer
        from tools.annual_leave_setup import state,apply
        eid,_=self.employee('management')
        with self.app.test_request_context():
            e=db.session.get(Employee,eid)
            db.session.add_all([EmployeeAnnualLeaveBalance(employee=e,year=2023,entitled_days_override=0),
                                EmployeeAnnualLeaveBalance(employee=e,year=2026,entitled_days_override=7)])
            db.session.commit()
            original=state(e)
            # A workbench batch load and a single-employee reload may return
            # unordered relationships in different row order.
            original['balances'].reverse()
            for row in original['balances']:
                if row[2] == '7':
                    row[2] = '7.000'
            signed=URLSafeSerializer(self.app.secret_key,salt='annual-leave-setup').dumps(original)
            apply(e,date(2026,3,4),Decimal(7),False,signed)
            db.session.commit()
            self.assertEqual(annual_leave_summary(e,2026)['entitled'],6)

    def test_initial_assignment_creates_current_year_leave(self):
        eid,_=self.create_employee('HKR','management','新同事測試','NEW QA')
        post=self.client.post
        def submit(url, **kwargs):
            if url.endswith('/assignment'):
                kwargs['data']={**kwargs['data'],'effective_from':'2026-07-01','initial_leave_days':'7'}
            return post(url,**kwargs)
        with patch.object(self.client,'post',side_effect=submit):
            self.complete_employee(eid,'management','TMC046','monthly','31000','NEW00001','61230001')
        with self.app.app_context():
            e=db.session.get(Employee,eid)
            self.assertEqual(e.current_period.annual_leave_policy_year,2026)
            self.assertEqual(annual_leave_summary(e,2026)['entitled'],Decimal('3.5'))
            self.assertEqual(EmployeeAnnualLeaveBalance.query.filter_by(employee_id=eid,year=2026).count(),1)

    def setup(self, eid, start='2026-03-04', initial='7', preserve='1', signed=None):
        return self.client.post(f'/employees/{eid}/annual-leave-setup', data=dict(
            start_date=start, initial_days=initial, preserve=preserve, setup_token=signed or self.signed(eid)), follow_redirects=True)

    def test_setup_saves_six_days_and_retains_legacy_card(self):
        eid,_=self.employee()
        response=self.setup(eid)
        self.assertEqual(response.status_code,200)
        self.assertIn('2023及以前年假',response.get_data(as_text=True))
        self.assertIn('設定年假計算',response.get_data(as_text=True))
        self.assertIn('待合約核實',response.get_data(as_text=True))
        with self.app.app_context():
            e=db.session.get(Employee,eid)
            self.assertEqual(e.current_period.start_date,date(2026,3,4))
            self.assertEqual(annual_leave_summary(e,2026)['entitled'],6)
            self.assertEqual(annual_leave_summary(e,2027)['entitled'],7)
            self.assertEqual(EmployeeAnnualLeaveBalance.query.count(),1)
            a=AuditLog.query.filter_by(employee_id=eid,action='annual_leave_balance_updated').one()
            self.assertEqual(a.after_json['applied'],'6')
        response=self.client.get('/annual-leave/entitlement-review')
        self.assertEqual(response.status_code,200)
        self.assertIn('最近修正',response.get_data(as_text=True))

    def test_manual_override_remains_and_can_restore_calculated(self):
        eid,_=self.employee()
        with self.app.app_context():
            db.session.add(EmployeeAnnualLeaveBalance(employee_id=eid,year=2026,entitled_days_override=10))
            db.session.commit()
        self.setup(eid)
        with self.app.app_context():
            e=db.session.get(Employee,eid)
            self.assertEqual(annual_leave_summary(e,2026)['entitled'],10)
            self.assertEqual(annual_leave_summary(e,2027)['entitled'],7)
        self.setup(eid,preserve='0')
        with self.app.app_context():
            self.assertEqual(annual_leave_summary(db.session.get(Employee,eid),2026)['entitled'],6)

    def test_stale_and_invalid_save_do_not_write(self):
        eid,_=self.employee()
        signed=self.signed(eid)
        self.setup(eid)
        response=self.setup(eid,initial='8',signed=signed)
        self.assertIn('年假資料已變更',response.get_data(as_text=True))
        response=self.setup(eid,initial='NaN')
        self.assertIn('有效入職日期',response.get_data(as_text=True))
        with self.app.app_context():
            self.assertEqual(db.session.get(Employee,eid).current_period.contract_annual_leave_days,7)

    def test_previous_accounts_not_recreated_or_changed(self):
        eid,_=self.employee()
        with self.app.app_context():
            db.session.add(EmployeeAnnualLeaveBalance(employee_id=eid,year=2023,entitled_days_override=5))
            db.session.add(EmployeeAnnualLeaveBalance(employee_id=eid,year=2025,entitled_days_override=9))
            db.session.commit()
        self.setup(eid,start='2020-01-01')
        with self.app.app_context():
            e=db.session.get(Employee,eid)
            self.assertEqual(annual_leave_summary(e,2026)['entitled'],12)
            self.assertEqual(annual_leave_summary(e,2027)['entitled'],13)
            self.assertEqual({b.year for b in e.annual_leave_balances},{2023,2025,2026})
            self.assertEqual(annual_leave_summary(e,2025)['entitled'],9)

    def test_current_override_save_does_not_create_legacy_account(self):
        eid,_=self.employee()
        self.client.post(f'/annual-leave/{eid}/balance',data=dict(year=2026,scope='current',entitled_days='7'))
        with self.app.app_context():
            self.assertIsNone(EmployeeAnnualLeaveBalance.query.filter_by(employee_id=eid,year=2023).first())

    def test_legacy_edit_does_not_hide_current_year_correction(self):
        eid,_=self.employee()
        self.setup(eid)
        self.client.post(f'/annual-leave/{eid}/balance',data=dict(year=2026,scope='legacy',legacy_days='3'))
        response=self.client.get('/annual-leave/entitlement-review')
        self.assertEqual(response.status_code,200)
        self.assertIn('→ 6',response.get_data(as_text=True))
        with self.app.app_context():
            self.assertEqual(annual_leave_summary(db.session.get(Employee,eid),2026)['entitled'],6)
            self.assertEqual(EmployeeAnnualLeaveBalance.query.filter_by(employee_id=eid,year=2023).one().entitled_days_override,3)

    def test_rollover_persists_once_and_retains_prior_account(self):
        eid,_=self.employee()
        self.setup(eid,start='2026-07-01',initial='8')
        class NewYear(date):
            @classmethod
            def today(cls): return date(2027,1,1)
        with self.app.test_request_context(),patch('tools.annual_leave_policy.date',NewYear):
            rollover();rollover()
            e=db.session.get(Employee,eid)
            self.assertEqual(annual_leave_summary(e,2027)['entitled'],9)
            self.assertEqual(annual_leave_summary(e,2026)['entitled'],4)
            self.assertEqual(EmployeeAnnualLeaveBalance.query.filter_by(employee_id=eid,year=2027).count(),1)

    def test_first_use_after_new_year_updates_default_screen_and_account(self):
        eid,_=self.employee()
        self.setup(eid,start='2026-07-01',initial='8')
        class NewYear(date):
            @classmethod
            def today(cls): return date(2027,1,5)
        with patch('tools.annual_leave_policy.date',NewYear),patch('routes.leave.date',NewYear),\
             patch('tools.annual_leave_setup.date',NewYear),patch('tools.hr_core.date',NewYear),patch('models.date',NewYear):
            response=self.client.get(f'/annual-leave?employee_id={eid}')
            self.assertEqual(response.status_code,200)
            self.assertIn('2027年度年假',response.get_data(as_text=True))
            self.assertIn('9.0 日',response.get_data(as_text=True))
            with self.app.app_context():
                self.assertEqual(EmployeeAnnualLeaveBalance.query.filter_by(employee_id=eid,year=2027).one().calculated_entitled_days,9)
                self.assertEqual(EmployeeAnnualLeaveBalance.query.filter_by(employee_id=eid,year=2026).one().calculated_entitled_days,4)

    def test_departure_preview_is_read_only_and_raw(self):
        eid,_=self.employee()
        self.setup(eid,start='2026-07-01')
        response=self.client.get(f'/employees/{eid}/termination-leave-preview?end_date=2027-03-31')
        self.assertEqual(response.status_code,200)
        self.assertEqual(Decimal(response.json['entitled']),Decimal(7)*90/365)
        with self.app.app_context():
            self.assertIsNone(db.session.get(Employee,eid).current_period.end_date)

    def test_overuse_deduction_missing_rate_and_net(self):
        from models import EmployeeFinalPaymentCase
        from tools.final_payment import calculate_final_payment
        from tools.hr_core import ensure_annual_leave_balance, set_annual_leave_allocations
        eid,_=self.employee()
        self.setup(eid,start='2026-07-01')
        with self.app.app_context():
            e=db.session.get(Employee,eid)
            e.current_period.end_date=date(2026,8,31)
            row=EmployeeAnnualLeaveRecord(employee=e,leave_date=date(2026,8,3),days=3,
                                          entitlement_year=2026,leave_type='annual',status='active')
            db.session.add(row);db.session.flush()
            balance=ensure_annual_leave_balance(e,2026)
            set_annual_leave_allocations(row,0,3)
            case=EmployeeFinalPaymentCase(employee=e,employment_period=e.current_period,
                settlement_month='2026-08',status='active',actual_working_days=20,
                benefit_type='none',legacy_leave_days=0,post_2024_leave_days=0)
            db.session.add(case);db.session.commit()
            missing=calculate_final_payment(e.current_period)
            self.assertTrue(any('日薪' in message for message in missing['blockers']))
            case.leave_daily_rate_override=1000
            db.session.commit()
            calculated=calculate_final_payment(e.current_period)
            excess=Decimal(3)-Decimal(7)*62/365
            self.assertAlmostEqual(calculated['annual_leave_overused_days'],excess,places=10)
            self.assertEqual(calculated['annual_leave_overuse_deduction'],(excess*1000).quantize(Decimal('.01')))
            self.assertEqual(calculated['net_amount'],missing['net_amount']-calculated['annual_leave_overuse_deduction']
                             + missing['employee_mpf'] - calculated['employee_mpf'])

    def test_confirmed_contract_and_staff_record_recalculate_current_year(self):
        eid,_=self.employee()
        self.setup(eid,start='2026-07-01')
        did=self.document(eid,'signed_contract')
        self.client.post(f'/documents/{did}/review',data=dict(contract_effective_date='2026-07-01',
                          contract_annual_leave_days='8'))
        with self.app.app_context():
            self.assertEqual(annual_leave_summary(db.session.get(Employee,eid),2026)['entitled'],Decimal('3.5'))
        response=self.client.post(f'/documents/{did}/review',data=dict(apply_contract_terms='on',
                         contract_effective_date='2026-07-01',contract_annual_leave_days='8'))
        self.assertEqual(response.status_code,302)
        with self.app.app_context():
            self.assertEqual(annual_leave_summary(db.session.get(Employee,eid),2026)['entitled'],4)
            self.assertTrue(db.session.get(Employee,eid).current_period.annual_leave_contract_verified)
        staff=self.document(eid,'staff_record','B')
        self.client.post(f'/documents/{staff}/review',data=dict(start_date='2026-01-01',date_change_action='recalculate'))
        with self.app.app_context():
            self.assertEqual(annual_leave_summary(db.session.get(Employee,eid),2026)['entitled'],8)
