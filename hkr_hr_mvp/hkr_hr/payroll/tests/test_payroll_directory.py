from datetime import date
from unittest import TestCase, mock

from tests.fixtures import PayrollTestCase
from hkr_hr.attendance.api import AttendanceMonthlySummary, AttendanceSegment
from hkr_hr.employees.api import Employee
from hkr_hr.leave.api import EmployeeWorkInjuryPeriod
from hkr_hr.payroll.api import PayrollRun
from hkr_hr.references.api import ReferenceList, ReferenceValue
from hkr_hr.platform.db import User, db
from hkr_hr.payroll.api import calculate_employee, snapshot_payroll


class PayrollDirectoryTests(PayrollTestCase):

    def test_browse_cards_without_calculating_payroll(self):
        eid, _ = self.employee()
        with mock.patch("hkr_hr.workbench.web.employees.directory.calculate_payroll", side_effect=AssertionError("paid roster requested")):
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

    def test_saved_payroll_runs_follow_entity_and_strict_group_with_hkt_header(self):
        e1 = self.ready(1)
        e2 = self.ready(2)
        with self.app.app_context():
            entity_list = ReferenceList.query.filter_by(code="payroll_entity").one()
            entity_a = ReferenceValue.query.filter_by(list_id=entity_list.id, code="HK_RIVER").one()
            entity_b = ReferenceValue(
                list_id=entity_list.id,
                code="ENTITY_B",
                display_name="Entity B Ltd",
                normalized_name="entity b ltd",
                active=True,
            )
            db.session.add(entity_b)
            db.session.flush()
            emp1 = db.session.get(Employee, e1)
            emp2 = db.session.get(Employee, e2)
            emp1.current_assignment.payroll_entity_id = entity_a.id
            emp2.current_assignment.payroll_entity_id = entity_b.id
            db.session.commit()

            uid = User.query.first().id
            row1 = calculate_employee(emp1, "2026-08")
            row2 = calculate_employee(emp2, "2026-08")
            run_a_mgmt = snapshot_payroll("2026-08", "management", [row1], uid)
            run_a_all = snapshot_payroll("2026-08", "all", [row1], uid)
            run_b_mgmt = snapshot_payroll("2026-08", "management", [row2], uid)
            ids = (entity_a.id, entity_b.id, run_a_mgmt.id, run_a_all.id, run_b_mgmt.id)

        entity_a_id, entity_b_id, run_a_mgmt_id, run_a_all_id, run_b_mgmt_id = ids
        page_a_mgmt = self.client.get(
            f"/attendance-payroll?year_month=2026-08&payroll_entity_id={entity_a_id}&payroll_group=management&lang=en"
        ).get_data(as_text=True)
        self.assertIn("Saved at (HKT)", page_a_mgmt)
        self.assertNotIn("(UTC)", page_a_mgmt)
        self.assertIn(f"/payroll/runs/{run_a_mgmt_id}/export", page_a_mgmt)
        self.assertNotIn(f"/payroll/runs/{run_a_all_id}/export", page_a_mgmt)
        self.assertNotIn(f"/payroll/runs/{run_b_mgmt_id}/export", page_a_mgmt)
        self.assertIn("1 saved all-groups payroll export(s) exist", page_a_mgmt)

        page_a_all = self.client.get(
            f"/attendance-payroll?year_month=2026-08&payroll_entity_id={entity_a_id}&payroll_group=all&lang=en"
        ).get_data(as_text=True)
        self.assertIn(f"/payroll/runs/{run_a_mgmt_id}/export", page_a_all)
        self.assertIn(f"/payroll/runs/{run_a_all_id}/export", page_a_all)
        self.assertNotIn(f"/payroll/runs/{run_b_mgmt_id}/export", page_a_all)

        page_b_daily = self.client.get(
            f"/attendance-payroll?year_month=2026-08&payroll_entity_id={entity_b_id}&payroll_group=site_daily&lang=en"
        ).get_data(as_text=True)
        self.assertNotIn(f"/payroll/runs/{run_b_mgmt_id}/export", page_b_daily)

    def test_department_directory_orders_by_corporate_hierarchy_and_custom_sort_order(self):
        created = {}
        for idx, code in enumerate(("HR", "SITE", "FINANCE", "COMMERCIAL", "ENGINEERING", "MANAGEMENT"), start=10):
            eid, _ = self.employee("management", idx)
            with self.app.app_context():
                dept_list = ReferenceList.query.filter_by(code="department").one()
                dept = ReferenceValue.query.filter_by(list_id=dept_list.id, code=code).one()
                db.session.get(Employee, eid).current_assignment.department_id = dept.id
                db.session.commit()
                created[code] = (dept.id, dept.display_name)
        unassigned_eid, _ = self.employee("management", 20)
        with self.app.app_context():
            db.session.get(Employee, unassigned_eid).current_assignment.department_id = None
            db.session.commit()

        directory = self.client.get("/employees?lang=zh-Hant").get_data(as_text=True)
        expected_labels = [
            "管理層",
            "工程管理部",
            "成本合約部",
            "財務部",
            "人事行政部",
            "地盤",
            "未填部門",
        ]
        positions = [directory.index(f"<h2>{label}") for label in expected_labels]
        self.assertEqual(positions, sorted(positions))

        hr_dept_id, hr_dept_name = created["HR"]
        updated = self.client.post(
            f"/references/values/{hr_dept_id}",
            data={"display_name": hr_dept_name, "sort_order": "5", "remarks": ""},
            follow_redirects=True,
        )
        self.assertEqual(updated.status_code, 200)
        reordered_dir = self.client.get("/employees?lang=zh-Hant").get_data(as_text=True)
        self.assertLess(reordered_dir.index("<h2>人事行政部"), reordered_dir.index("<h2>管理層"))
        ref_page = self.client.get("/references?list=department&lang=zh-Hant").get_data(as_text=True)
        self.assertLess(ref_page.index("人事行政部"), ref_page.index("管理層"))
