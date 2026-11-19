"""Attendance and monthly payroll use the same employee and period boundaries."""
from datetime import date, datetime, timedelta
from types import SimpleNamespace
from unittest import TestCase

from flask import template_rendered
import test_payroll_policy as fixtures
from models import (db, Employee, EmployeeWorkInjuryPeriod, EmployeeAnnualLeaveRecord, AttendanceBatch, AttendanceBatchItem,
                    AttendanceMonthlySummary, PayrollRun, PayrollAdjustment)
from tools.attendance_policy import attendance_required, automatic_attendance_rows
from tools.attendance_rates import allocation_issue, rate_windows
from tools.payroll_engine import calculate_employee


class WorkbenchConsistencyTests(TestCase):
    setUp = fixtures.PayrollPolicyTests.setUp
    tearDown = fixtures.PayrollPolicyTests.tearDown
    login = fixtures.PayrollPolicyTests.login
    create_employee = fixtures.PayrollPolicyTests.create_employee
    complete_employee = fixtures.PayrollPolicyTests.complete_employee
    employee = fixtures.PayrollPolicyTests.employee
    ready = fixtures.PayrollPolicyTests.ready

    def test_intake_resumes_unfinished_batch_after_work_month_changes(self):
        with self.app.app_context():
            for month, statuses in [("2026-07", ["saved", "pending"]), ("2026-08", ["saved"])]:
                batch = AttendanceBatch(batch_no=month, year_month=month)
                for index, status in enumerate(statuses):
                    batch.items.append(AttendanceBatchItem(original_filename=f"{month}-{index}.pdf",
                                                           stored_path="test.pdf", status=status))
                db.session.add(batch)
            db.session.commit()
        page = self.client.get("/attendance?month=2026-08&lang=en").get_data(as_text=True)
        resume = page.split('class="intake-resume"', 1)[1].split('</section>', 1)[0]
        self.assertIn("1 saved · 0 pending", resume)
        self.assertIn("All attendance files for", resume)
        self.assertNotIn("2026-07-1.pdf", resume)
        self.assertIn('class="intake-other-months"', resume)
        self.assertIn("month=2026-07", resume)
        self.assertIn("1 pending", resume)
        self.assertIn("status=missing&amp;month=2026-08", page)

    def test_review_exempt_attendance_returns_to_same_payroll_scope(self):
        eid = self.ready()
        with self.app.app_context():
            summary = AttendanceMonthlySummary(employee_id=eid, year_month="2026-08", status="not_required",
                                               no_attendance_reason="Test exemption")
            db.session.add(summary)
            db.session.commit()
            summary_id = summary.id
        response = self.client.post(f"/attendance/summaries/{summary_id}/correct", data={
            "employee_id": eid, "year_month": "2026-08", "from_payroll": "1",
            "pay_group": "management", "pay_status": "pending", "pay_employee": str(eid)})
        self.assertIn("/attendance-payroll?", response.location)
        self.assertIn("status=pending", response.location)
        self.assertIn("payroll_group=management", response.location)
        with self.app.app_context():
            summary = db.session.get(AttendanceMonthlySummary, summary_id)
            self.assertEqual((summary.status, summary.no_attendance_reason), ("not_required", "Test exemption"))

    def test_full_and_partial_injury_and_explicit_month_choice(self):
        eid, _ = self.employee()
        with self.app.app_context():
            e = db.session.get(Employee, eid)
            injury = EmployeeWorkInjuryPeriod(employee_id=eid, accident_date=date(2026,7,15),
                payroll_start_date=date(2026,7,15), confirmed_monthly_earnings=20000)
            db.session.add(injury)
            db.session.commit()
            self.assertTrue(attendance_required(e, "2026-07"))
            self.assertFalse(attendance_required(e, "2026-08"))
            self.assertFalse(calculate_employee(e, "2026-08")["blockers"])
            for status, expected in [("received", True), ("required", True), ("not_required", False)]:
                self.assertEqual(attendance_required(e, "2026-08", SimpleNamespace(status=status)), expected)
            injury.payroll_end_date = date(2026,8,30)
            self.assertTrue(attendance_required(e, "2026-08"))

    def test_hire_date_limits_prefill_rates_and_legacy_zero_band(self):
        eid, _ = self.employee()
        with self.app.app_context():
            e = db.session.get(Employee, eid)
            hire = date(2026,8,10)
            e.current_period.start_date = e.current_assignment.effective_from = e.salaries[0].effective_from = hire
            start,end = date(2026,8,1),date(2026,8,20)
            outside = automatic_attendance_rows(e, start, hire - timedelta(days=1))
            self.assertEqual(outside, [])
            windows = rate_windows(e,start,end)
            self.assertEqual([(w["start"],w["end"]) for w in windows], [("2026-08-10","2026-08-20")])
            s = SimpleNamespace(working_days=5,ot_hours=2)
            self.assertIsNone(allocation_issue(e,s,start,end))
            s.rate_allocations=[dict(start="2026-08-01",end="2026-08-09"),dict(start="2026-08-10",end="2026-08-20",working_days=5,ot_hours=2)]
            self.assertIsNone(allocation_issue(e,s,start,end))
            e.salaries[0].effective_from = date(2026,8,12)
            self.assertIn("缺少生效薪酬", allocation_issue(e,s,start,end))

    def test_rosters_month_and_repeat_download(self):
        ready, negative, stale = [self.ready(n) for n in (1,2,3)]
        month = "2026-08"
        with self.app.app_context():
            db.session.add_all([
                PayrollAdjustment(employee_id=negative,year_month=month,label="QA",amount=-100000,status="active"),
                AttendanceMonthlySummary(employee_id=stale,year_month=month,status="not_required",confirmed_at=datetime.utcnow()-timedelta(days=3)),
                EmployeeAnnualLeaveRecord(employee_id=stale,leave_date=date(2026,8,4),days=1,entitlement_year=2026,status="active")
            ])
            db.session.commit()
        captured = {}
        def capture(sender,template,context,**kwargs):
            if template.name == "dashboard.html":
                captured["dashboard"] = (context["year_month"],context["payroll_unready_count"],context["estimated_payroll"][0]["net"])
            if template.name == "payroll/index.html":
                captured["ready"] = [r["employee"].id for r in context["ready_rows"]]
                captured["pending"] = {r["employee"].id for r in context["blockers"]}
                captured["net"] = context["summary"]["currencies"][0]["net"]
            if template.name == "employees/list.html":
                captured["staff_pending"] = {r["employee"].id for r in context["readiness_rows"]}
        with template_rendered.connected_to(capture,self.app):
            for path in ["/attendance-payroll?year_month="+month, "/annual-leave","/employees?readiness=payroll","/dashboard"]:
                self.assertEqual(self.client.get(path).status_code,200)
        self.assertEqual(captured["ready"],[ready])
        self.assertEqual(captured["pending"],{negative,stale})
        self.assertEqual(captured["staff_pending"],captured["pending"])
        self.assertEqual(captured["dashboard"],(month,2,captured["net"]))
        for url in ["/export/monthly-payroll?year_month="+month, "/payroll/export-current?year_month="+month]:
            self.assertEqual(self.client.get(url,follow_redirects=True).request.path,"/attendance-payroll")
        with self.app.app_context():
            self.assertEqual(PayrollRun.query.count(),0)
        response = self.client.post("/payroll/export-current",data={"year_month":month,"scope":"ready"})
        self.assertEqual(response.status_code,303)
        for _ in range(10):
            self.assertIn("attachment",self.client.get(response.location).headers["Content-Disposition"])
        with self.app.app_context():
            run = PayrollRun.query.one()
            self.assertEqual([(r.employee_id,r.net_amount) for r in run.employee_results],[(ready,captured["net"])])
