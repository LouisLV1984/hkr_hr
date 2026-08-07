import calendar
from datetime import date, timedelta
from decimal import Decimal

from models import (
    AttendanceMonthlySummary,
    EmployeeFinalPaymentCase,
    EmployeeEmploymentPeriod,
)
from tools.hr_core import (
    annual_leave_buckets,
    average_wage_prefill,
    current_assignment_on,
    current_salary_on,
    parse_year_month,
)
from tools.payroll_engine import (
    ECALL_FLAT_AMOUNT,
    decimal_value,
    mpf_amounts,
    rounded,
    salary_rate_for_date,
)


TRANSITION_DATE = date(2025, 5, 1)
SP_LSP_ANNUAL_CAP = Decimal("15000")
SP_LSP_TOTAL_CAP = Decimal("390000")
FINAL_PAYMENT_RULE_VERSION = "V1.0-2026-08-07"


def periods_for_final_payment(year_month, payroll_group="all"):
    month_start, month_end = parse_year_month(year_month)
    rows = (
        EmployeeEmploymentPeriod.query.filter(
            EmployeeEmploymentPeriod.end_date >= month_start,
            EmployeeEmploymentPeriod.end_date <= month_end,
        )
        .order_by(EmployeeEmploymentPeriod.end_date.asc())
        .all()
    )
    if payroll_group == "all":
        return rows
    return [
        period
        for period in rows
        if group_for_period(period) == payroll_group
    ]


def group_for_period(period):
    assignment = current_assignment_on(period.employee, period.end_date)
    return assignment.payroll_group if assignment else period.employee.payroll_group


def final_payment_case(period):
    return EmployeeFinalPaymentCase.query.filter_by(
        employment_period_id=period.id,
        status="active",
    ).first()


def attendance_defaults(period):
    summary = AttendanceMonthlySummary.query.filter_by(
        employee_id=period.employee_id,
        year_month=period.end_date.strftime("%Y-%m"),
    ).first()
    segments = (
        [item for item in summary.segments if item.period_kind == "current_1_20"]
        if summary
        else []
    )
    return {
        "summary": summary,
        "working_days": sum(
            (decimal_value(item.working_days) for item in segments),
            Decimal("0"),
        ),
        "ot_hours": sum(
            (decimal_value(item.ot_hours) for item in segments),
            Decimal("0"),
        ),
        "holiday_days": sum(
            (decimal_value(item.sunday_holiday_days) for item in segments),
            Decimal("0"),
        ),
        "large_ecall_count": sum(item.large_ecall_count or 0 for item in segments),
        "ecall_count": sum(item.ecall_count or 0 for item in segments),
    }


def payroll_average(employee, end_date):
    details = average_wage_prefill(employee, end_date)
    return details["average"], details["count"], details["months"]


def last_full_month_salary(employee, reference_date):
    first = reference_date.replace(day=1)
    previous_end = first - timedelta(days=1)
    salary = current_salary_on(employee, previous_end)
    return decimal_value(salary.amount) if salary else Decimal("0")


def default_benefit_inputs(period):
    employee = period.employee
    group = group_for_period(period)
    if group == "site_daily":
        return {
            "pre_basis_last": None,
            "pre_basis_average": None,
            "post_basis_last": None,
            "post_basis_average": None,
        }
    pre_average = average_wage_prefill(employee, TRANSITION_DATE)
    post_average = average_wage_prefill(employee, period.end_date)
    return {
        "pre_basis_last": (
            last_full_month_salary(employee, TRANSITION_DATE)
            if period.start_date < TRANSITION_DATE
            else None
        ),
        "pre_basis_average": (
            pre_average["average"] if pre_average["count"] == 12 else None
        ),
        "post_basis_last": (
            last_full_month_salary(employee, period.end_date)
            if period.end_date >= TRANSITION_DATE
            else None
        ),
        "post_basis_average": (
            post_average["average"] if post_average["count"] == 12 else None
        ),
    }


def leave_defaults(period):
    buckets = annual_leave_buckets(
        period.employee,
        as_of=period.end_date,
        include_expired=False,
        prorate_current=True,
    )
    legacy = sum(
        (max(Decimal("0"), item["remaining"]) for item in buckets if item["is_legacy"]),
        Decimal("0"),
    )
    regular = sum(
        (max(Decimal("0"), item["remaining"]) for item in buckets if not item["is_legacy"]),
        Decimal("0"),
    )
    return legacy, regular, buckets


def selected_basis(case, defaults, prefix):
    last = decimal_value(
        getattr(case, f"{prefix}_basis_last")
        if case and getattr(case, f"{prefix}_basis_last") is not None
        else defaults.get(f"{prefix}_basis_last")
    )
    average = decimal_value(
        getattr(case, f"{prefix}_basis_average")
        if case and getattr(case, f"{prefix}_basis_average") is not None
        else defaults.get(f"{prefix}_basis_average")
    )
    choice = getattr(case, f"{prefix}_basis_choice") if case else None
    if choice not in {"last", "average"}:
        choice = "average" if average > last else "last"
    selected = average if choice == "average" else last
    return {
        "last": rounded(last),
        "average": rounded(average),
        "choice": choice,
        "selected": rounded(selected),
    }


def service_portion_days(period):
    pre_end = min(period.end_date, TRANSITION_DATE - timedelta(days=1))
    pre_days = (
        max(0, (pre_end - period.start_date).days + 1)
        if period.start_date < TRANSITION_DATE
        else 0
    )
    post_start = max(period.start_date, TRANSITION_DATE)
    post_days = (
        max(0, (period.end_date - post_start).days + 1)
        if period.end_date >= TRANSITION_DATE
        else 0
    )
    return pre_days, post_days


def calculate_benefit(period, case, defaults, group):
    benefit_type = case.benefit_type if case else "none"
    pre = selected_basis(case, defaults, "pre")
    post = selected_basis(case, defaults, "post")
    pre_days, post_days = service_portion_days(period)
    blockers = []
    if benefit_type != "none":
        if pre_days and pre["selected"] <= 0:
            blockers.append("缺轉制前遣散／長服金工資基數")
        if post_days and post["selected"] <= 0:
            blockers.append("缺轉制後遣散／長服金工資基數")

    def annual_amount(selected):
        if group == "site_daily":
            return min(selected, SP_LSP_ANNUAL_CAP)
        return min(selected * Decimal("2") / Decimal("3"), SP_LSP_ANNUAL_CAP)

    pre_amount = (
        annual_amount(pre["selected"]) * Decimal(pre_days) / Decimal("365")
        if benefit_type != "none" and pre_days and pre["selected"] > 0
        else Decimal("0")
    )
    post_amount = (
        annual_amount(post["selected"]) * Decimal(post_days) / Decimal("365")
        if benefit_type != "none" and post_days and post["selected"] > 0
        else Decimal("0")
    )
    gross = pre_amount + post_amount
    if gross > SP_LSP_TOTAL_CAP:
        excess = gross - SP_LSP_TOTAL_CAP
        post_reduction = min(post_amount, excess)
        post_amount -= post_reduction
        excess -= post_reduction
        if excess > 0:
            pre_amount = max(Decimal("0"), pre_amount - excess)
    offset = min(
        max(Decimal("0"), decimal_value(case.mpf_offset_amount if case else 0)),
        pre_amount,
    )
    return {
        "type": benefit_type,
        "pre": pre,
        "post": post,
        "pre_days": pre_days,
        "post_days": post_days,
        "pre_years": Decimal(pre_days) / Decimal("365"),
        "post_years": Decimal(post_days) / Decimal("365"),
        "pre_amount": rounded(pre_amount),
        "post_amount": rounded(post_amount),
        "gross": rounded(pre_amount + post_amount),
        "mpf_offset": rounded(offset),
        "net": rounded(pre_amount + post_amount - offset),
        "blockers": blockers,
    }


def calculate_final_payment(period):
    employee = period.employee
    case = final_payment_case(period)
    group = group_for_period(period)
    attendance = attendance_defaults(period)
    benefit_defaults = default_benefit_inputs(period)
    legacy_default, regular_default, leave_buckets = leave_defaults(period)
    _, month_end = parse_year_month(period.end_date.strftime("%Y-%m"))
    assignment = current_assignment_on(employee, period.end_date)
    project = assignment.project if assignment else None
    rates = salary_rate_for_date(employee, period.end_date, project)
    salary = rates["salary"] if rates else None
    blockers = []
    if not salary or not rates:
        blockers.append("缺離職日適用薪酬")

    confirmed = bool(case)
    working_days = decimal_value(
        case.actual_working_days if case and case.actual_working_days is not None else attendance["working_days"]
    )
    ot_hours = decimal_value(
        case.actual_ot_hours if case and case.actual_ot_hours is not None else attendance["ot_hours"]
    )
    holiday_days = decimal_value(
        case.actual_holiday_days if case and case.actual_holiday_days is not None else attendance["holiday_days"]
    )
    large_ecall_count = decimal_value(
        case.large_ecall_count if case else attendance["large_ecall_count"]
    )
    ecall_count = decimal_value(case.ecall_count if case else attendance["ecall_count"])
    if not confirmed:
        blockers.append("尚未確認離職月實際考勤及結算資料")

    base_rate = rates["base_rate"] if rates else Decimal("0")
    ot_rate = rates["ot_rate"] if rates else Decimal("0")
    holiday_rate = (
        decimal_value(case.holiday_daily_rate_override)
        if case and case.holiday_daily_rate_override is not None
        else rates["holiday_rate"] if rates else Decimal("0")
    )
    base_amount = base_rate * working_days
    ot_amount = ot_rate * ot_hours
    holiday_amount = holiday_rate * holiday_days
    ecall_amount = base_rate * large_ecall_count + ECALL_FLAT_AMOUNT * ecall_count

    allowance = decimal_value(case.allowance_amount if case else 0)
    other_payment = decimal_value(case.other_payment if case else 0)
    overpay = decimal_value(case.overpay_amount if case else 0)
    underpay = decimal_value(case.underpay_amount if case else 0)
    special = decimal_value(case.special_compensation if case else 0)
    legacy_days = decimal_value(
        case.legacy_leave_days if case and case.legacy_leave_days is not None else legacy_default
    )
    regular_days = decimal_value(
        case.post_2024_leave_days if case and case.post_2024_leave_days is not None else regular_default
    )
    statutory_days = decimal_value(
        case.statutory_holiday_days if case and case.statutory_holiday_days is not None else 0
    )

    service_days = max(0, (period.end_date - period.start_date).days + 1)
    average_wage, average_count, average_months = payroll_average(employee, period.end_date)
    leave_average = decimal_value(
        case.leave_average_wage
        if case and case.leave_average_wage is not None
        else average_wage if average_count == 12 else 0
    )
    if case and case.leave_daily_rate_override is not None:
        leave_rate = decimal_value(case.leave_daily_rate_override)
        leave_rate_source = "manual"
    elif salary and salary.salary_basis == "daily":
        leave_rate = decimal_value(salary.amount)
        leave_rate_source = "daily_salary"
    elif service_days < 365 and salary:
        leave_rate = decimal_value(salary.amount) / Decimal(
            calendar.monthrange(period.end_date.year, period.end_date.month)[1]
        )
        leave_rate_source = "current_monthly_salary"
    elif leave_average > 0:
        leave_rate = leave_average / Decimal(
            calendar.monthrange(period.end_date.year, period.end_date.month)[1]
        )
        leave_rate_source = "twelve_month_average"
    else:
        leave_rate = Decimal("0")
        leave_rate_source = "missing"
        if legacy_days + regular_days > 0:
            blockers.append("缺年假補薪平均工資或日薪率")

    annual_leave_pay = (legacy_days + regular_days) * leave_rate
    statutory_holiday_pay = statutory_days * holiday_rate
    benefit = calculate_benefit(period, case, benefit_defaults, group)
    blockers.extend(benefit["blockers"])
    payment_in_lieu = decimal_value(period.payment_in_lieu)
    wage_income = (
        base_amount
        + ot_amount
        + holiday_amount
        + ecall_amount
        + allowance
        + other_payment
        - overpay
        + underpay
        + annual_leave_pay
        + statutory_holiday_pay
    )
    casual_components = None
    if employee.mpf_mode == "casual":
        casual_components = [
            {
                "income": wage_income,
                "days": max(Decimal("0"), working_days + holiday_days + statutory_days),
                "sign": Decimal("1"),
            }
        ]
    employee_mpf, employer_mpf, mpf_warnings = mpf_amounts(
        employee,
        wage_income,
        working_days + holiday_days + statutory_days,
        month_end,
        casual_components=casual_components,
    )
    net = (
        wage_income
        - employee_mpf
        + payment_in_lieu
        + benefit["net"]
        + special
    )
    return {
        "employee": employee,
        "period": period,
        "case": case,
        "group": group,
        "assignment": assignment,
        "project": project,
        "salary": salary,
        "attendance": attendance,
        "confirmed": confirmed,
        "working_days": working_days,
        "ot_hours": ot_hours,
        "holiday_days": holiday_days,
        "large_ecall_count": large_ecall_count,
        "ecall_count": ecall_count,
        "base_rate": rounded(base_rate),
        "ot_rate": rounded(ot_rate),
        "holiday_rate": rounded(holiday_rate),
        "base_amount": rounded(base_amount),
        "ot_amount": rounded(ot_amount),
        "holiday_amount": rounded(holiday_amount),
        "ecall_amount": rounded(ecall_amount),
        "allowance_amount": rounded(allowance),
        "other_payment": rounded(other_payment),
        "overpay_amount": rounded(overpay),
        "underpay_amount": rounded(underpay),
        "legacy_leave_days": legacy_days,
        "post_2024_leave_days": regular_days,
        "statutory_holiday_days": statutory_days,
        "leave_buckets": leave_buckets,
        "leave_average_wage": rounded(leave_average),
        "leave_average_count": average_count,
        "leave_average_months": average_months,
        "leave_rate": leave_rate.quantize(Decimal("0.0001")),
        "leave_rate_source": leave_rate_source,
        "annual_leave_pay": rounded(annual_leave_pay),
        "statutory_holiday_pay": rounded(statutory_holiday_pay),
        "payment_in_lieu": rounded(payment_in_lieu),
        "benefit": benefit,
        "special_compensation": rounded(special),
        "wage_income": rounded(wage_income),
        "employee_mpf": rounded(employee_mpf),
        "employer_mpf": rounded(employer_mpf),
        "net_amount": rounded(net),
        "benefit_defaults": benefit_defaults,
        "blockers": list(dict.fromkeys(blockers)),
        "warnings": list(dict.fromkeys(mpf_warnings + ["離職法定權益為系統估算，必須由 HR 核對。"])),
    }


def calculate_final_payments(year_month, payroll_group="all"):
    return [
        calculate_final_payment(period)
        for period in periods_for_final_payment(year_month, payroll_group)
    ]
