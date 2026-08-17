from collections import defaultdict
from datetime import timedelta

from models import (
    AttendanceMonthlySummary,
    AttendanceSegment,
    EmployeeAttendancePolicy,
)
from tools.hr_core import (
    current_assignment_on,
    parse_year_month,
    previous_month,
)


def policy_on(employee_id, year_month):
    return (
        EmployeeAttendancePolicy.query.filter(
            EmployeeAttendancePolicy.employee_id == employee_id,
            EmployeeAttendancePolicy.effective_from_month <= year_month,
        )
        .order_by(
            EmployeeAttendancePolicy.effective_from_month.desc(),
            EmployeeAttendancePolicy.id.desc(),
        )
        .first()
    )


def attendance_required(employee, year_month, summary=None):
    if summary is None:
        summary = AttendanceMonthlySummary.query.filter_by(
            employee_id=employee.id,
            year_month=year_month,
        ).first()
    if summary:
        if summary.status in {"received", "required"}:
            return True
        if summary.status == "not_required":
            return False
    policy = policy_on(employee.id, year_month)
    return policy.requires_attendance if policy else True


def set_long_term_attendance_policy(
    employee,
    effective_from_month,
    requires_attendance,
    created_by=None,
    remarks=None,
):
    policy = EmployeeAttendancePolicy.query.filter_by(
        employee_id=employee.id,
        effective_from_month=effective_from_month,
    ).first()
    if not policy:
        policy = EmployeeAttendancePolicy(
            employee=employee,
            effective_from_month=effective_from_month,
        )
    policy.requires_attendance = requires_attendance
    policy.created_by = created_by
    policy.remarks = remarks
    return policy


def automatic_attendance_rows(employee, start_date, end_date):
    day = start_date
    rows = defaultdict(
        lambda: {
            "project_id": None,
            "working_days": 0,
            "sunday_holiday_days": 0,
        }
    )
    while day <= end_date:
        assignment = current_assignment_on(employee, day)
        project_id = assignment.project_id if assignment else None
        row = rows[project_id]
        row["project_id"] = project_id
        # Automatic attendance may infer ordinary weekdays only. A Sunday or
        # statutory-holiday shift is exceptional work and must come from an
        # explicit attendance entry; otherwise monthly staff would receive an
        # extra 1x payment merely because the calendar contains Sundays.
        if day.weekday() != 6:
            row["working_days"] += 1
        day += timedelta(days=1)
    return [
        row
        for row in rows.values()
        if row["working_days"] or row["sunday_holiday_days"]
    ]


def _segments_from_rows(summary, period_kind, rows):
    for row in rows:
        summary.segments.append(
            AttendanceSegment(
                period_kind=period_kind,
                project_id=row.get("project_id"),
                working_days=row.get("working_days", 0),
                ot_hours=0,
                sunday_holiday_days=row.get("sunday_holiday_days", 0),
                large_ecall_count=0,
                ecall_count=0,
            )
        )


def default_attendance_summary(employee, year_month):
    """Build an unsaved full-attendance summary for payroll calculation."""
    month_start, month_end = parse_year_month(year_month)
    prior_month = previous_month(year_month)
    prior_start, prior_end = parse_year_month(prior_month)
    prior_start = prior_start.replace(day=21)

    summary = AttendanceMonthlySummary(
        employee_id=employee.id,
        year_month=year_month,
        status="not_required",
        no_attendance_reason="long_term_policy",
    )
    current_actual = automatic_attendance_rows(
        employee,
        month_start,
        min(month_end, month_start.replace(day=20)),
    )
    current_forecast = automatic_attendance_rows(
        employee,
        month_start.replace(day=21),
        month_end,
    )
    previous_summary = AttendanceMonthlySummary.query.filter_by(
        employee_id=employee.id,
        year_month=prior_month,
    ).first()
    previous_forecast_segments = [
        item
        for item in (previous_summary.segments if previous_summary else [])
        if item.period_kind == "current_21_end_forecast"
    ]
    previous_forecast = (
        [
            {
                "project_id": item.project_id,
                "working_days": item.working_days,
                "sunday_holiday_days": item.sunday_holiday_days,
            }
            for item in previous_forecast_segments
        ]
        if previous_forecast_segments
        else automatic_attendance_rows(employee, prior_start, prior_end)
    )

    _segments_from_rows(summary, "current_1_20", current_actual)
    _segments_from_rows(summary, "current_21_end_forecast", current_forecast)
    _segments_from_rows(summary, "previous_21_end", previous_forecast)
    _segments_from_rows(summary, "previous_21_end_forecast", previous_forecast)
    return summary
