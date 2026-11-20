"""Focused tests for V0.7.8 business rules and usability fixes."""
import unittest
from datetime import date
from decimal import Decimal

from hkr_hr.attendance.api import (
    AttendanceMonthlySummary,
    attendance_required,
    set_long_term_attendance_policy,
)
from hkr_hr.employees.api import (
    Employee,
    EmployeeEmploymentPeriod,
    EmployeeSalary,
)
from hkr_hr.leave.api import (
    EmployeeAnnualLeaveRecord,
    EmployeeWorkInjuryPeriod,
)
from hkr_hr.payroll.api import (
    PayrollAdjustment,
    calculate_employee,
    calculate_final_payment,
    leave_defaults,
)
from hkr_hr.platform.db import AuditLog, db
from hkr_hr.platform.i18n import TRANSLATIONS, translate_system_message
from hkr_hr.references.api import reference_by_code
from tests.fixtures import PayrollTestCase


class V078UsabilityFixesTests(PayrollTestCase):
    def test_final_payment_full_month_uses_calendar_days_and_rounds_leave(self):
        eid, _ = self.create_employee("HKR", "management", "周建華", "CHAU KIN WAH")
        self.complete_employee(
            eid, "management", "TMC046", "monthly", "26000", "BANK01", "90001111"
        )
        with self.app.app_context():
            emp = db.session.get(Employee, eid)
            emp.current_period.start_date = date(2025, 3, 10)
            emp.current_period.end_date = date(2026, 11, 30)
            emp.current_period.contract_annual_leave_days = Decimal("10")
            db.session.commit()

            # Full month Nov 2026 (30 calendar days) -> exact full salary HKD 26,000.00
            result = calculate_final_payment(emp.current_period)
            self.assertTrue(result["calendar_prorated_monthly"])
            self.assertEqual(result["calendar_active_days"], Decimal("30"))
            self.assertEqual(result["working_days"], Decimal("30"))
            self.assertEqual(result["base_amount"], Decimal("26000.00"))
            # Leave defaults quantized to 3 decimal places (compatible with step="0.001")
            legacy, regular, overused, _ = leave_defaults(emp.current_period)
            for val in (legacy, regular, overused):
                self.assertGreaterEqual(val.as_tuple().exponent, -3)

            # Mid-month exit Nov 15, 2026 (15/30 calendar days) -> HKD 13,000.00
            emp.current_period.end_date = date(2026, 11, 15)
            db.session.commit()
            mid = calculate_final_payment(emp.current_period)
            self.assertEqual(mid["calendar_active_days"], Decimal("15"))
            self.assertEqual(mid["base_amount"], Decimal("13000.00"))

            # Unpaid leave 1 day on Nov 10 -> deducts 1/30 of 26,000 = 866.67
            db.session.add(
                EmployeeAnnualLeaveRecord(
                    employee_id=eid,
                    leave_type="unpaid",
                    entitlement_year=2026,
                    leave_date=date(2026, 11, 10),
                    end_date=date(2026, 11, 10),
                    days=Decimal("1"),
                    leave_units_json={"2026-11-10": "1"},
                    status="active",
                )
            )
            db.session.commit()
            with_unpaid = calculate_final_payment(emp.current_period)
            self.assertEqual(with_unpaid["unpaid_leave_days"], Decimal("1"))
            self.assertEqual(with_unpaid["base_amount"], Decimal("12133.33"))

    def test_one_off_payroll_adjustment_bonus_deduction_and_withdraw(self):
        eid, _ = self.create_employee("HKRD", "site_daily", "陳日工", "CHAN DAILY")
        self.complete_employee(
            eid, "site_daily", "TMC046", "daily", "1000", "BANK02", "90002222"
        )
        # Positive bonus for daily worker
        resp = self.client.post(
            f"/employees/{eid}/payroll-adjustments",
            data={
                "year_month": "2026-11",
                "label": "項目獎金",
                "amount": "1500",
                "return_to": "employee",
            },
            follow_redirects=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("項目獎金", resp.get_data(as_text=True))

        # Negative deduction
        resp2 = self.client.post(
            f"/employees/{eid}/payroll-adjustments",
            data={
                "year_month": "2026-11",
                "label": "預支薪金扣回",
                "amount": "-500",
                "return_to": "payroll",
                "pay_month": "2026-11",
            },
        )
        self.assertEqual(resp2.status_code, 302)
        self.assertIn("/attendance-payroll", resp2.headers["Location"])

        with self.app.app_context():
            active = PayrollAdjustment.query.filter_by(
                employee_id=eid, year_month="2026-11", status="active"
            ).all()
            self.assertEqual(len(active), 2)
            self.assertEqual(sum(a.amount for a in active), Decimal("1000.00"))
            deduction_id = next(a.id for a in active if a.amount < 0)

        # Withdraw the negative deduction
        resp3 = self.client.post(
            f"/payroll-adjustments/{deduction_id}/withdraw",
            data={"return_to": "employee", "reason": "重複錄入"},
        )
        self.assertEqual(resp3.status_code, 302)
        with self.app.app_context():
            voided = db.session.get(PayrollAdjustment, deduction_id)
            self.assertEqual(voided.status, "voided")
            self.assertGreaterEqual(
                AuditLog.query.filter_by(action="payroll_adjustment_added").count(), 2
            )
            self.assertEqual(
                AuditLog.query.filter_by(action="payroll_adjustment_voided").count(), 1
            )

    def test_management_default_attendance_exempt_and_long_term_overrides_single_month(self):
        with self.app.app_context():
            emp_type = reference_by_code("employee_type", "HKR")
            type_id = emp_type.id
        # Create management employee without explicitly setting requires_attendance -> defaults to exempt
        resp = self.client.post(
            "/employees/new",
            data={
                "employee_type_id": str(type_id),
                "payroll_group": "management",
                "chinese_name": "林管理",
                "english_name": "LAM MGT",
            },
            follow_redirects=False,
        )
        self.assertEqual(resp.status_code, 302)
        with self.app.app_context():
            emp = Employee.query.filter_by(chinese_name="林管理").one()
            self.assertFalse(attendance_required(emp, "2026-11"))

            # Add a single-month 'required' override for 2026-11
            db.session.add(
                AttendanceMonthlySummary(
                    employee_id=emp.id,
                    year_month="2026-11",
                    status="required",
                )
            )
            db.session.commit()
            self.assertTrue(attendance_required(emp, "2026-11"))

            # Saving long-term exemption starting 2026-11 must clear the 2026-11 single-month override
            policy = set_long_term_attendance_policy(emp, "2026-11", False)
            db.session.add(policy)
            db.session.commit()
            self.assertFalse(attendance_required(emp, "2026-11"))

    def test_monthly_payroll_missing_mpf_warning_and_navigation_and_audit_i18n(self):
        eid, _ = self.create_employee("HKR", "management", "缺強積金", "NO MPF")
        self.complete_employee(
            eid, "management", "TMC046", "monthly", "20000", "BANK03", "90003333"
        )
        with self.app.app_context():
            emp = db.session.get(Employee, eid)
            for mpf in list(emp.mpf_enrollments):
                db.session.delete(mpf)
            db.session.add(set_long_term_attendance_policy(emp, "2026-01", False))
            db.session.commit()

        page = self.client.get(
            "/attendance-payroll?year_month=2026-11&status=ready"
        ).get_data(as_text=True)
        self.assertIn("MPF 申報資料未齊", page)
        self.assertIn("未設定 MPF 計劃", page)
        # Left rail order: Monthly Payroll before Actual Salary Records
        self.assertLess(page.index("每月工資表"), page.index("實際發薪紀錄"))
        # Admin topbar link is visible for admin user
        self.assertIn('href="/admin/users"', page)

        # Bank record specialist upload redirects with guidance flash and anchor
        bank_resp = self.client.get(
            f"/employees/{eid}/documents/new?upload_type=bank_record"
        )
        self.assertEqual(bank_resp.status_code, 302)
        self.assertIn("tab=personal", bank_resp.headers["Location"])
        self.assertIn("#bank-accounts", bank_resp.headers["Location"])

        # Exports heading is 匯出與歷史
        exports_html = self.client.get("/exports").get_data(as_text=True)
        self.assertIn("匯出與歷史", exports_html)

        # Audit i18n translates previously untranslated keys
        zh = TRANSLATIONS["zh-Hant"]
        translate = lambda k: zh.get(k, k)
        self.assertEqual(
            translate_system_message("work_calendar_created", translate),
            "新增工作日曆假日",
        )
        self.assertEqual(
            translate_system_message("salary_record_saved", translate),
            "保存實際發薪紀錄",
        )

    def test_work_injury_expense_flash_column_am_vs_an(self):
        eid, _ = self.create_employee("HKRD", "site_daily", "工傷日工", "INJURY DAILY")
        self.complete_employee(
            eid, "site_daily", "TMC046", "daily", "1000", "BANK04", "90004444"
        )
        with self.app.app_context():
            injury = EmployeeWorkInjuryPeriod(
                employee_id=eid,
                accident_date=date(2026, 11, 1),
                payroll_start_date=date(2026, 11, 1),
                confirmed_monthly_earnings=Decimal("24000"),
                incapacity_monthly_earnings=Decimal("0"),
                currency="HKD",
                status="active",
            )
            db.session.add(injury)
            db.session.commit()
            period_id = injury.id
        resp = self.client.post(
            f"/work-injuries/{period_id}/monthly-expenses",
            data={"year_month": "2026-11", "amount": "350", "currency": "HKD"},
            follow_redirects=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("AM 欄", resp.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
