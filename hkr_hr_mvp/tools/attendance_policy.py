from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from models import (
    AttendanceMonthlySummary,
    AttendanceSegment,
    EmployeeAttendancePolicy,
    WorkCalendarHoliday,
)
from tools.hr_core import (
    current_assignment_on,
    current_salary_on,
    default_workweek_days,
    parse_year_month,
    previous_month,
)


def assignment_workweek_days(assignment):
    if not assignment:
        return Decimal("6")
    value = Decimal(str(assignment.workweek_days or 0))
    return (
        value
        if value in {Decimal("5"), Decimal("5.5"), Decimal("6")}
        else default_workweek_days(assignment.payroll_group)
    )


def holiday_calendar_kind_for_payroll_group(payroll_group):
    return "public" if payroll_group == "management" else "statutory"


def holiday_calendar_kind_for_employee(employee, on_date):
    assignment = current_assignment_on(employee, on_date)
    payroll_group = assignment.payroll_group if assignment else employee.payroll_group
    return holiday_calendar_kind_for_payroll_group(payroll_group)


def _employee_holidays(employee, start_date, end_date, calendar_kind=None):
    rows = WorkCalendarHoliday.query.filter(
        WorkCalendarHoliday.holiday_date >= start_date,
        WorkCalendarHoliday.holiday_date <= end_date,
        WorkCalendarHoliday.active.is_(True),
    ).all()
    indexed = {
        (item.region_id, item.holiday_date): item for item in rows
    }
    result = {}
    day = start_date
    while day <= end_date:
        assignment = current_assignment_on(employee, day)
        if assignment and assignment.region_id:
            item = indexed.get((assignment.region_id, day))
            kind = calendar_kind or holiday_calendar_kind_for_payroll_group(
                assignment.payroll_group
            )
            applies = bool(
                item
                and (
                    item.applies_to_public
                    if kind == "public"
                    else item.applies_to_statutory
                )
            )
            if applies:
                result[day] = item
        day += timedelta(days=1)
    return result


def employee_statutory_holidays(employee, start_date, end_date):
    """Statutory holidays only, including daily-worker paid entitlement."""
    return _employee_holidays(
        employee,
        start_date,
        end_date,
        calendar_kind="statutory",
    )


def employee_payroll_holidays(employee, start_date, end_date):
    """Use statutory holidays on Site Payroll and public holidays for OFFICE."""
    return _employee_holidays(employee, start_date, end_date)


def scheduled_work_units(assignment, day):
    payroll_group = assignment.payroll_group if assignment else "site_daily"
    if payroll_group == "site_daily":
        # The review baseline assumes Monday-Saturday attendance only. Sunday
        # is unpaid unless HR confirms actual work from the signed PDF, while
        # statutory holidays are excluded later because entitlement and actual
        # holiday work are handled separately.
        return Decimal("0") if day.weekday() == 6 else Decimal("1")
    workweek = assignment_workweek_days(assignment)
    if day.weekday() <= 4:
        return Decimal("1")
    if day.weekday() == 5:
        if workweek == Decimal("6"):
            return Decimal("1")
        if workweek == Decimal("5.5"):
            return Decimal("0.5")
    return Decimal("0")


def special_work_day_units(employee, work_date, holiday_dates=None):
    holidays = holiday_dates
    if holidays is None:
        holidays = employee_payroll_holidays(employee, work_date, work_date)
    assignment = current_assignment_on(employee, work_date)
    if assignment and assignment.payroll_group == "site_daily":
        # A daily worker records Sunday in ordinary actual attendance. Only
        # actual statutory-holiday work uses the Payroll / Comp Leave picker.
        return Decimal("1") if work_date in holidays else None
    if work_date in holidays or work_date.weekday() == 6:
        return Decimal("1")
    if not assignment:
        return None
    if work_date.weekday() == 5:
        workweek = assignment_workweek_days(assignment)
        if workweek == Decimal("5"):
            return Decimal("1")
        if workweek == Decimal("5.5"):
            return Decimal("0.5")
    return None


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


def employee_nonattendance_units(employee, start_date, end_date):
    """Known leave and work-injury units that must not be prefilled as work."""
    units = defaultdict(lambda: Decimal("0"))
    for record in employee.annual_leave_records:
        if record.status != "active":
            continue
        record_end = record.end_date or record.leave_date
        if record.leave_date > end_date or record_end < start_date:
            continue
        day = max(start_date, record.leave_date)
        last_day = min(end_date, record_end)
        while day <= last_day:
            value = Decimal("1")
            if day == record.leave_date and record.start_session == "pm":
                value -= Decimal("0.5")
            if day == record_end and record.end_session == "am":
                value -= Decimal("0.5")
            units[day] = min(Decimal("1"), units[day] + max(Decimal("0"), value))
            day += timedelta(days=1)
    for injury in employee.work_injury_periods:
        if injury.status != "active":
            continue
        injury_end = injury.payroll_end_date or end_date
        if injury.payroll_start_date > end_date or injury_end < start_date:
            continue
        day = max(start_date, injury.payroll_start_date)
        last_day = min(end_date, injury_end)
        while day <= last_day:
            units[day] = Decimal("1")
            day += timedelta(days=1)
    return units


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
    holiday_dates = employee_payroll_holidays(
        employee, start_date, end_date
    )
    nonattendance_units = employee_nonattendance_units(
        employee, start_date, end_date
    )
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
        salary = current_salary_on(employee, day)
        project_id = assignment.project_id if assignment else None
        row = rows[project_id]
        row["project_id"] = project_id
        # Automatic attendance may infer ordinary weekdays only. A Sunday or
        # statutory-holiday shift is exceptional work and must come from an
        # explicit attendance entry; otherwise monthly staff would receive an
        # extra 1x payment merely because the calendar contains Sundays.
        is_attendance_prorated = bool(
            salary
            and salary.salary_basis == "monthly"
            and salary.monthly_pay_method == "attendance_days"
        )
        work_units = scheduled_work_units(assignment, day)
        is_statutory_holiday = day in holiday_dates
        payroll_group = assignment.payroll_group if assignment else "site_daily"
        attendance_drives_pay = (
            payroll_group == "site_daily" or is_attendance_prorated
        )
        if work_units and not is_statutory_holiday:
            if attendance_drives_pay:
                work_units = max(
                    Decimal("0"),
                    work_units - nonattendance_units[day],
                )
            if not is_attendance_prorated:
                row["working_days"] += work_units
        day += timedelta(days=1)
    return [
        row
        for row in rows.values()
        if row["working_days"] or row["sunday_holiday_days"]
    ]


def attendance_period_ranges(year_month):
    month_start, month_end = parse_year_month(year_month)
    prior_month = previous_month(year_month)
    prior_start, prior_end = parse_year_month(prior_month)
    prior_start = prior_start.replace(day=21)
    prior_range = (prior_start, prior_end)
    return {
        "current_1_20": (
            month_start,
            min(month_end, month_start.replace(day=20)),
        ),
        "current_21_end_forecast": (
            month_start.replace(day=21),
            month_end,
        ),
        "previous_21_end": prior_range,
        "previous_21_end_forecast": prior_range,
    }


def _calendar_split(start_date, end_date):
    ordinary_days = Decimal("0")
    sunday_days = Decimal("0")
    day = start_date
    while day <= end_date:
        if day.weekday() == 6:
            sunday_days += Decimal("1")
        else:
            ordinary_days += Decimal("1")
        day += timedelta(days=1)
    return ordinary_days, sunday_days


def is_legacy_inferred_special_day_summary(summary):
    """Identify the retired calendar split that treated every Sunday as work.

    The check is deliberately narrow: it applies only to attendance-exempt
    Monthly/OFFICE summaries with no dated special-day evidence, no OT,
    E-CALL or substitute-shift allowance, and all four segments matching the
    old weekday-versus-Sunday calendar split exactly.
    """
    if (
        not summary
        or summary.status != "not_required"
        or not summary.employee
        or summary.employee.payroll_group not in {"site_monthly", "management"}
        or any(row.status == "active" for row in summary.special_days)
    ):
        return False

    period_ranges = attendance_period_ranges(summary.year_month)
    grouped = defaultdict(list)
    for segment in summary.segments:
        grouped[segment.period_kind].append(segment)
        if any(
            Decimal(str(value or 0)) != 0
            for value in (
                segment.ot_hours,
                segment.large_ecall_count,
                segment.ecall_count,
                segment.other_allowance_amount,
            )
        ):
            return False

    if not set(period_ranges).issubset(grouped):
        return False

    for period_kind, (start_date, end_date) in period_ranges.items():
        expected_ordinary, expected_sundays = _calendar_split(
            start_date,
            end_date,
        )
        ordinary_total = sum(
            (
                Decimal(str(segment.working_days or 0))
                for segment in grouped[period_kind]
            ),
            Decimal("0"),
        )
        special_total = sum(
            (
                Decimal(str(segment.sunday_holiday_days or 0))
                for segment in grouped[period_kind]
            ),
            Decimal("0"),
        )
        if (
            ordinary_total != expected_ordinary
            or special_total != expected_sundays
        ):
            return False
    return True


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
