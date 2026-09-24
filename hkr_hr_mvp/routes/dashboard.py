from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from flask import (
    Blueprint,
    abort,
    current_app,
    render_template,
    request,
)
from flask_login import login_required
from markdown import Markdown
from markupsafe import Markup
from models import (
    AttendanceMonthlySummary,
    Employee,
    EmployeeCertificate,
    EmployeeIdentity,
    EmployeeVisa,
)
from tools.completeness import employee_readiness
from tools.profile_integrity import credential_alerts
from tools.hr_core import current_month, parse_year_month
from tools.payroll_engine import calculate_payroll
from tools.releases import RELEASES


dashboard_bp = Blueprint("dashboard", __name__)
GUIDE_FILENAME = "操作指南.md"


def guide_path():
    return Path(current_app.root_path) / GUIDE_FILENAME


@dashboard_bp.route("/updates")
@login_required
def updates():
    return render_template("updates.html", releases=RELEASES)


@dashboard_bp.route("/guide")
@login_required
def guide():
    path = guide_path()
    if not path.is_file():
        abort(404)
    source = path.read_text(encoding="utf-8")
    renderer = Markdown(extensions=["extra", "toc"], output_format="html5")
    guide_html = Markup(renderer.convert(source))
    return render_template("guide.html", guide_html=guide_html)


@dashboard_bp.route("/dashboard")
@login_required
def dashboard():
    year_month = request.args.get("month") or current_month()
    month_start, month_end = parse_year_month(year_month)
    active_employees = [
        employee
        for employee in Employee.query.all()
        if employee.is_active_on(date.today())
    ]

    payroll_rows = calculate_payroll(year_month, "all")
    estimated_payroll = sum(
        (
            Decimal(str(row.get("net_amount", 0)))
            for row in payroll_rows
            if not row.get("blockers")
        ),
        Decimal("0"),
    )
    payroll_unready_count = sum(
        1 for row in payroll_rows if row.get("blockers")
    )
    month_employees = [
        employee
        for employee in Employee.query.all()
        if employee.employed_during(month_start, month_end)
    ]
    summaries = AttendanceMonthlySummary.query.filter_by(
        year_month=year_month,
    ).all()
    summaries_by_employee = {row.employee_id: row for row in summaries}
    payroll_by_employee = {
        row["employee"].id: row
        for row in payroll_rows
    }
    all_readiness_rows = [
        employee_readiness(
            employee,
            year_month,
            payroll_row=payroll_by_employee.get(employee.id),
            summary=summaries_by_employee.get(employee.id),
        )
        for employee in month_employees
    ]
    readiness_rows = [row for row in all_readiness_rows if row["has_issue"]]
    readiness_total_count = len(readiness_rows)
    employee_data_issue_count = sum(
        1
        for row in all_readiness_rows
        if any(not item["ok"] for item in row["employee_data"])
    )
    attendance_issue_count = sum(
        1 for row in all_readiness_rows if not row["attendance"]["ok"]
    )
    payroll_issue_count = sum(
        1
        for row in all_readiness_rows
        if any(not item["ok"] for item in row["payroll"])
    )

    expected = [
        row["employee"]
        for row in all_readiness_rows
        if row["attendance"]["code"] != "not_required"
    ]
    received_ids = {
        row.employee_id
        for row in AttendanceMonthlySummary.query.filter_by(
            year_month=year_month,
            status="received",
        ).all()
    }

    threshold = date.today() + timedelta(days=60)
    expiry_alerts = credential_alerts()
    today = date.today()
    for alert in expiry_alerts:
        alert["days_remaining"] = (alert["date"] - today).days
        alert["severity"] = (
            "expired"
            if alert["days_remaining"] < 0
            else "urgent"
            if alert["days_remaining"] <= 30
            else "warning"
        )
    expiry_alerts.sort(key=lambda item: item["date"] or date.max)

    confirmation_threshold = today + timedelta(days=30)
    confirmation_alerts = []
    for employee in active_employees:
        period = employee.current_period
        if (
            employee.payroll_group != "management"
            or not period
            or not period.probation_end_date
            or period.confirmation_date
            or period.probation_end_date > confirmation_threshold
        ):
            continue
        days_remaining = (period.probation_end_date - today).days
        confirmation_alerts.append(
            {
                "employee": employee,
                "date": period.probation_end_date,
                "days_remaining": days_remaining,
                "severity": (
                    "expired"
                    if days_remaining < 0
                    else "urgent"
                    if days_remaining <= 7
                    else "warning"
                ),
            }
        )
    confirmation_alerts.sort(key=lambda item: item["date"])

    return render_template(
        "dashboard.html",
        year_month=year_month,
        active_count=len(active_employees),
        estimated_payroll=estimated_payroll,
        payroll_unready_count=payroll_unready_count,
        attendance_expected=len(expected),
        attendance_received=len(received_ids.intersection({item.id for item in expected})),
        readiness_total_count=readiness_total_count,
        employee_data_issue_count=employee_data_issue_count,
        attendance_issue_count=attendance_issue_count,
        payroll_issue_count=payroll_issue_count,
        expiry_alerts=expiry_alerts,
        confirmation_alerts=confirmation_alerts,
        open_panel=request.args.get("panel", ""),
    )
