from datetime import date
from unittest import TestCase, mock

import test_payroll_policy as fixtures
from models import AttendanceMonthlySummary, AttendanceSegment, Employee, EmployeeWorkInjuryPeriod, User, db
from tools.payroll_engine import calculate_employee, snapshot_payroll


class PayrollDirectoryTests(TestCase):
    setUp = fixtures.PayrollPolicyTests.setUp
    tearDown = fixtures.PayrollPolicyTests.tearDown
    login = fixtures.PayrollPolicyTests.login
    create_employee = fixtures.PayrollPolicyTests.create_employee
    complete_employee = fixtures.PayrollPolicyTests.complete_employee
    employee = fixtures.PayrollPolicyTests.employee
    ready = fixtures.PayrollPolicyTests.ready

    def test_browse_cards_without_calculating_payroll(self):
        eid, _ = self.employee()
        with mock.patch("routes.employees.calculate_payroll", side_effect=AssertionError("paid roster requested")):
            for grouping in ("department", "position"):
                page = self.client.get("/employees?group_by=" + grouping).get_data(as_text=True)
                self.assertIn(f'/employees/{eid}?origin=directory', page)
                self.assertIn('data-mpf-status=', page)
                self.assertEqual(page.count('class="directory-person-link"'), 1)

    def test_negative_reconciliation_points_to_the_actual_saved_forecast(self):
        eid, _ = self.employee("site_daily")
        with self.app.app_context():
            person = db.session.get(Employee, eid)
            july = AttendanceMonthlySummary(employee_id=eid, year_month="2026-07", status="received")
            july.segments.append(AttendanceSegment(period_kind="current_21_end_forecast", working_days=11))
            db.session.add(july)
            db.session.flush()
            run = snapshot_payroll("2026-07", "site_daily", [calculate_employee(person, "2026-07")], User.query.first().id)
            saved = run.employee_results[0].id
            db.session.add(EmployeeWorkInjuryPeriod(employee_id=eid, accident_date=date(2026,8,1),
                payroll_start_date=date(2026,8,1), confirmed_monthly_earnings=100))
            db.session.commit()
        page = self.client.get("/attendance-payroll?year_month=2026-08&status=pending").get_data(as_text=True)
        self.assertIn("11,000.00", page)
        self.assertIn("-1,920.00", page)
        self.assertIn(f"#pay-snapshot-{saved}", page)
        profile = self.client.get(f"/employees/{eid}?tab=attendance").get_data(as_text=True)
        self.assertIn(f'id="pay-snapshot-{saved}"', profile)

    def test_missing_entity_is_pending_even_when_pay_can_be_calculated(self):
        eid = self.ready()
        with self.app.app_context():
            db.session.get(Employee, eid).current_assignment.payroll_entity_id = None
            db.session.commit()
        pending = self.client.get("/attendance-payroll?year_month=2026-08&status=pending").get_data(as_text=True)
        self.assertIn('focus=pay_entity', pending)
        ready = self.client.get("/attendance-payroll?year_month=2026-08&status=ready").get_data(as_text=True)
        self.assertNotIn('focus=pay_entity', ready)
