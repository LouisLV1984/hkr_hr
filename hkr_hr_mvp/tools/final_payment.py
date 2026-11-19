import calendar
from datetime import date, timedelta
from decimal import Decimal

from models import (
    AttendanceCorrection,
    AttendanceMonthlySummary,
    EmployeeFinalPaymentCase,
    EmployeeEmploymentPeriod,
    EmployeeWorkInjuryMonthlyExpense,
    PayrollAdjustment,
)
from tools.hr_core import (
    annual_leave_buckets,
    average_wage_prefill,
    current_assignment_on,
    current_mpf_on,
    current_salary_on,
    parse_year_month,
)
from tools.payroll_engine import (
    ECALL_FLAT_AMOUNT,
    active_allowances,
    decimal_value,
    mpf_amounts,
    rounded,
    salary_rate_for_date,
)


TRANSITION_DATE = date(2025, 5, 1)
SP_LSP_ANNUAL_CAP = Decimal("15000")
SP_LSP_TOTAL_CAP = Decimal("390000")
FINAL_PAYMENT_RULE_VERSION = "V1.4-2026-11-17"


def periods_for_final_payment(
    year_month,
    payroll_group="all",
    payroll_entity_id=None,
):
    month_start, month_end = parse_year_month(year_month)
    rows = (
        EmployeeEmploymentPeriod.query.filter(
            EmployeeEmploymentPeriod.end_date >= month_start,
            EmployeeEmploymentPeriod.end_date <= month_end,
        )
        .order_by(EmployeeEmploymentPeriod.end_date.asc())
        .all()
    )
    selected = rows
    if payroll_group != "all":
        selected = [
            period
            for period in selected
            if group_for_period(period) == payroll_group
        ]
    if payroll_entity_id is not None:
        entity_selected = []
        for period in selected:
            assignment = current_assignment_on(
                period.employee,
                period.end_date,
            )
            if assignment and assignment.payroll_entity_id == payroll_entity_id:
                entity_selected.append(period)
        selected = entity_selected
    return selected


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
        "other_allowance_amount": sum(
            (
                decimal_value(item.other_allowance_amount)
                for item in segments
            ),
            Decimal("0"),
        ),
    }


def payroll_average(employee, end_date):
    details = average_wage_prefill(employee, end_date)
    return (
        details["average"],
        details["total"],
        details["count"],
        details["months"],
    )


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
    legacy_raw = sum(
        (item["remaining"] for item in buckets if item["is_legacy"]),
        Decimal("0"),
    )
    regular_raw = sum(
        (item["remaining"] for item in buckets if not item["is_legacy"]),
        Decimal("0"),
    )
    total = legacy_raw + regular_raw
    payable_total = max(Decimal("0"), total)
    legacy = min(max(Decimal("0"), legacy_raw), payable_total)
    regular = max(Decimal("0"), payable_total - legacy)
    overused = max(Decimal("0"), -total)
    return legacy, regular, overused, buckets


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
    legacy_default, regular_default, leave_overused_days, leave_buckets = leave_defaults(period)
    year_month = period.end_date.strftime("%Y-%m")
    month_start, month_end = parse_year_month(year_month)
    assignment = current_assignment_on(employee, period.end_date)
    project = assignment.project if assignment else None
    rates = salary_rate_for_date(employee, period.end_date, project)
    salary = rates["salary"] if rates else None
    blockers = []
    if not salary or not rates:
        blockers.append("缺離職日適用薪酬")
    if not assignment or not assignment.payroll_entity_id:
        blockers.append("發薪單位未設定")

    attendance_prorated_monthly = bool(
        salary
        and salary.salary_basis == "monthly"
        and salary.monthly_pay_method == "attendance_days"
    )
    allowance_attendance_days = (
        decimal_value(
            case.actual_working_days
            if case and case.actual_working_days is not None
            else attendance["working_days"]
        )
        if attendance_prorated_monthly
        else None
    )
    fixed_allowance_rows = active_allowances(
        employee,
        month_start,
        month_end,
        payable_end=period.end_date,
        attendance_working_days=allowance_attendance_days,
    )
    if group == "site_daily" and fixed_allowance_rows:
        blockers.append("日工暫不支持固定補貼，請先撤回補貼記錄")
    traffic_meal_allowance = sum(
        (
            amount
            for allowance, amount in fixed_allowance_rows
            if allowance.allowance_type in {"meal", "transport"}
        ),
        Decimal("0"),
    )
    special_allowance = sum(
        (
            amount
            for allowance, amount in fixed_allowance_rows
            if allowance.allowance_type not in {"meal", "transport"}
        ),
        Decimal("0"),
    )
    fixed_allowance = traffic_meal_allowance + special_allowance

    month_adjustments = PayrollAdjustment.query.filter_by(
        employee_id=employee.id,
        year_month=year_month,
        status="active",
    ).all()
    corrections = AttendanceCorrection.query.filter_by(employee_id=employee.id, pay_month=year_month).all()
    month_adjustment = sum((c.amount for c in corrections), Decimal(0)) + sum(
        (decimal_value(item.amount) for item in month_adjustments),
        Decimal("0"),
    )
    medical_expenses = EmployeeWorkInjuryMonthlyExpense.query.filter_by(
        employee_id=employee.id,
        year_month=year_month,
        status="active",
    ).all()
    medical_reimbursement = sum(
        (decimal_value(item.amount) for item in medical_expenses),
        Decimal("0"),
    )

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
    if attendance_prorated_monthly:
        holiday_days = Decimal("0")
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
    rate_start = max(month_start, period.start_date)
    from tools.attendance_rates import active_allocations, allocation_issue, rate_windows
    from types import SimpleNamespace
    rate_windows_for_month = rate_windows(employee, rate_start, period.end_date)
    rate_totals = SimpleNamespace(working_days=working_days, ot_hours=ot_hours, sunday_holiday_days=holiday_days, large_ecall_count=large_ecall_count, rate_allocations=case.rate_allocations if case else None)
    rate_issue = allocation_issue(employee, rate_totals, rate_start, period.end_date)
    if rate_issue:
        blockers.append(rate_issue)
    base_amount = base_rate * working_days
    ot_amount = ot_rate * ot_hours
    holiday_amount = holiday_rate * holiday_days
    ecall_amount = base_rate * large_ecall_count + ECALL_FLAT_AMOUNT * ecall_count

    if len(rate_windows_for_month) > 1 and not rate_issue and case and case.rate_allocations:
        base_amount = ot_amount = holiday_amount = Decimal("0")
        ecall_amount = ECALL_FLAT_AMOUNT * ecall_count
        for part in active_allocations(case.rate_allocations, rate_windows_for_month):
            applicable = salary_rate_for_date(employee, date.fromisoformat(part["start"]), project)
            if not applicable:
                continue
            base_amount += applicable["base_rate"] * decimal_value(part.get("working_days"))
            ot_amount += applicable["ot_rate"] * decimal_value(part.get("ot_hours"))
            part_holiday_rate = holiday_rate if case.holiday_daily_rate_override is not None else applicable["holiday_rate"]
            holiday_amount += part_holiday_rate * decimal_value(part.get("sunday_holiday_days"))
            ecall_amount += applicable["base_rate"] * decimal_value(part.get("large_ecall_count"))
    manual_allowance = decimal_value(case.allowance_amount if case else 0)
    manual_other_payment = decimal_value(case.other_payment if case else 0)
    attendance_other_allowance = decimal_value(
        attendance["other_allowance_amount"]
    )
    allowance = fixed_allowance + manual_allowance
    other_payment = (
        manual_other_payment
        + month_adjustment
        + attendance_other_allowance
    )
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
    average_wage, wage_total, average_count, average_months = payroll_average(employee, period.end_date)
    leave_average = decimal_value(
        case.leave_average_wage
        if case and case.leave_average_wage is not None
        else average_wage if average_count == 12 else 0
    )
    leave_wage_total = decimal_value(
        case.leave_wage_total
        if case and case.leave_wage_total is not None
        else wage_total if average_count == 12 else 0
    )
    if case and case.leave_daily_rate_override is not None:
        leave_rate = decimal_value(case.leave_daily_rate_override)
        leave_rate_source = "manual"
    elif leave_wage_total > 0:
        leave_rate = leave_wage_total / Decimal("365")
        leave_rate_source = "twelve_month_wage_total"
    else:
        leave_rate = Decimal("0")
        leave_rate_source = "missing"
        if legacy_days + regular_days > 0 or leave_overused_days > 0:
            blockers.append("缺前 12 個月工資合計或年假補薪日薪率")

    annual_leave_pay = (legacy_days + regular_days) * leave_rate
    if leave_overused_days > 0 and leave_rate <= 0:
        blockers.append("超用年假追扣缺有效日薪基準，請 HR 核實")
    annual_leave_overuse_deduction = leave_overused_days * leave_rate
    statutory_holiday_pay = statutory_days * holiday_rate
    benefit = calculate_benefit(period, case, benefit_defaults, group)
    blockers.extend(benefit["blockers"])
    from tools.absence_integrity import absences_changed_since_attendance
    warnings = []
    if absences_changed_since_attendance(employee, attendance["summary"], month_start, period.end_date):
        warnings.append("leave.attendance_recheck")
    if any(not item.evidence_document_id for item in month_adjustments):
        warnings.append("指定月份調整憑證待補")
    if any(not item.evidence_document_id for item in medical_expenses):
        warnings.append("工傷復診／醫療實銷憑證待補")
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
        - annual_leave_overuse_deduction
    )
    mpf_enrollment = current_mpf_on(employee, month_end)
    mpf_mode = (
        mpf_enrollment.contribution_mode
        if mpf_enrollment
        else employee.mpf_mode
    )
    casual_components = None
    if mpf_mode == "casual":
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
        contribution_mode=mpf_mode,
    )
    net = (
        wage_income
        - employee_mpf
        + payment_in_lieu
        + benefit["net"]
        + special
        + medical_reimbursement
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
        "rate_windows": rate_windows_for_month,
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
        "fixed_allowance_amount": rounded(fixed_allowance),
        "traffic_meal_allowance_amount": rounded(
            traffic_meal_allowance
        ),
        "special_allowance_amount": rounded(special_allowance),
        "manual_allowance_amount": rounded(manual_allowance),
        "other_payment": rounded(other_payment),
        "manual_other_payment": rounded(manual_other_payment),
        "attendance_corrections": [entry for c in corrections for entry in c.lines],
        "month_adjustment_amount": rounded(month_adjustment),
        "attendance_other_allowance_amount": rounded(
            attendance_other_allowance
        ),
        "work_injury_medical_reimbursement_amount": rounded(
            medical_reimbursement
        ),
        "overpay_amount": rounded(overpay),
        "underpay_amount": rounded(underpay),
        "legacy_leave_days": legacy_days,
        "post_2024_leave_days": regular_days,
        "statutory_holiday_days": statutory_days,
        "leave_buckets": leave_buckets,
        "leave_average_wage": rounded(leave_average),
        "leave_wage_total": rounded(leave_wage_total),
        "leave_average_count": average_count,
        "leave_average_months": average_months,
        "leave_rate": leave_rate.quantize(Decimal("0.0001")),
        "leave_rate_source": leave_rate_source,
        "annual_leave_pay": rounded(annual_leave_pay),
        "annual_leave_overused_days": leave_overused_days,
        "annual_leave_overuse_deduction": rounded(
            annual_leave_overuse_deduction
        ),
        "statutory_holiday_pay": rounded(statutory_holiday_pay),
        "payment_in_lieu": rounded(payment_in_lieu),
        "benefit": benefit,
        "special_compensation": rounded(special),
        "wage_income": rounded(wage_income),
        "employee_mpf": rounded(employee_mpf),
        "employer_mpf": rounded(employer_mpf),
        "mpf_enrollment": mpf_enrollment,
        "mpf_calculation_mode": mpf_mode,
        "net_amount": rounded(net),
        "benefit_defaults": benefit_defaults,
        "blockers": list(dict.fromkeys(blockers)),
        "warnings": list(
            dict.fromkeys(
                warnings
                + mpf_warnings
                + ["離職法定權益為系統估算，必須由 HR 核對。"]
            )
        ),
    }


def calculate_final_payments(
    year_month,
    payroll_group="all",
    payroll_entity_id=None,
):
    return [
        calculate_final_payment(period)
        for period in periods_for_final_payment(
            year_month,
            payroll_group,
            payroll_entity_id,
        )
    ]
