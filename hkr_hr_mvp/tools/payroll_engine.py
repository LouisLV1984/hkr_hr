import calendar
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from models import (
    AttendanceMonthlySummary,
    Employee,
    PayrollAdjustment,
    PayrollEmployeeResult,
    PayrollProjectLine,
    PayrollRun,
    WorkProject,
    db,
)
from tools.hr_core import (
    current_assignment_on,
    current_salary_on,
    parse_year_month,
    previous_month,
)


RULE_VERSION = "V1.3-2026-07-31"
PAYROLL_GROUP_CODES = ("site_daily", "site_monthly", "management")
ECALL_FLAT_AMOUNT = Decimal("400")


def decimal_value(value):
    return Decimal(str(value or 0))


def rounded(value):
    return decimal_value(value).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )


def date_range(start, end):
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def employed_during(employee, start, end):
    if not employee.employment_periods:
        return employee.status == "active"
    return any(
        period.start_date <= end
        and (period.end_date is None or period.end_date >= start)
        for period in employee.employment_periods
    )


def group_on(employee, on_date):
    assignment = current_assignment_on(employee, on_date)
    return assignment.payroll_group if assignment else employee.payroll_group


def employees_for_payroll(year_month, payroll_group="all"):
    month_start, month_end = parse_year_month(year_month)
    employees = Employee.query.order_by(Employee.employee_no.asc()).all()
    rows = [
        employee
        for employee in employees
        if employed_during(employee, month_start, month_end)
    ]
    if payroll_group != "all":
        rows = [
            employee
            for employee in rows
            if group_on(employee, month_end) == payroll_group
        ]
    return rows


def active_document(employee, category):
    return next(
        (
            document
            for document in employee.documents
            if document.category == category and document.status == "active"
        ),
        None,
    )


def salary_rate_for_date(employee, on_date, project=None):
    salary = current_salary_on(employee, on_date)
    if not salary:
        return None
    days_in_month = Decimal(
        calendar.monthrange(on_date.year, on_date.month)[1]
    )
    amount = decimal_value(salary.amount)
    divisor = Decimal("9")
    if salary.salary_basis == "daily":
        if project and project.daily_ot_divisor:
            divisor = decimal_value(project.daily_ot_divisor)
        base_rate = amount
        holiday_rate = amount
        ot_rate = amount / divisor * Decimal("1.5")
    else:
        base_rate = amount / days_in_month
        holiday_rate = base_rate
        ot_rate = base_rate / Decimal("9") * Decimal("1.5")
    return {
        "salary": salary,
        "base_rate": base_rate,
        "holiday_rate": holiday_rate,
        "ot_rate": ot_rate,
        "ot_divisor": divisor,
    }


def average_rates(employee, start, end, project=None):
    rates = []
    for day in date_range(start, end):
        item = salary_rate_for_date(employee, day, project)
        if item:
            rates.append(item)
    if not rates:
        return None
    count = Decimal(len(rates))
    first = rates[0]
    return {
        "salary": first["salary"],
        "base_rate": sum(
            item["base_rate"] for item in rates
        ) / count,
        "holiday_rate": sum(
            item["holiday_rate"] for item in rates
        ) / count,
        "ot_rate": sum(item["ot_rate"] for item in rates) / count,
        "ot_divisor": first["ot_divisor"],
    }


def empty_line(project):
    return {
        "project": project,
        "working_days": Decimal("0"),
        "holiday_days": Decimal("0"),
        "current_ot_hours": Decimal("0"),
        "previous_ot_hours": Decimal("0"),
        "previous_holiday_days": Decimal("0"),
        "current_large_ecall_count": Decimal("0"),
        "current_ecall_count": Decimal("0"),
        "previous_large_ecall_count": Decimal("0"),
        "previous_ecall_count": Decimal("0"),
        "base_amount": Decimal("0"),
        "holiday_amount": Decimal("0"),
        "ot_amount": Decimal("0"),
        "previous_ot_amount": Decimal("0"),
        "previous_holiday_amount": Decimal("0"),
        "large_ecall_amount": Decimal("0"),
        "ecall_amount": Decimal("0"),
        "previous_large_ecall_amount": Decimal("0"),
        "previous_ecall_amount": Decimal("0"),
        "allowance_amount": Decimal("0"),
        "adjustment_amount": Decimal("0"),
        "gross_amount": Decimal("0"),
        "base_rate": Decimal("0"),
        "holiday_rate": Decimal("0"),
        "ot_rate": Decimal("0"),
        "ot_divisor": Decimal("9"),
        "forecast_working_days": Decimal("0"),
        "forecast_holiday_days": Decimal("0"),
        "forecast_base_amount": Decimal("0"),
        "forecast_holiday_amount": Decimal("0"),
    }


def line_key(project):
    return project.id if project else 0


def attendance_segments(summary, kind):
    if not summary:
        return []
    return [item for item in summary.segments if item.period_kind == kind]


def apply_actual_segments(
    employee,
    segments,
    start,
    end,
    lines,
    previous=False,
    casual_components=None,
):
    total = Decimal("0")
    for segment in segments:
        project = segment.project
        rates = average_rates(employee, start, end, project)
        if not rates:
            continue
        key = line_key(project)
        line = lines.setdefault(key, empty_line(project))
        working_days = decimal_value(segment.working_days)
        holiday_days = decimal_value(segment.sunday_holiday_days)
        ot_hours = decimal_value(segment.ot_hours)
        large_ecall_count = decimal_value(segment.large_ecall_count)
        ecall_count = decimal_value(segment.ecall_count)
        base = rates["base_rate"] * working_days
        holiday = rates["holiday_rate"] * holiday_days
        overtime = rates["ot_rate"] * ot_hours
        large_ecall = rates["base_rate"] * large_ecall_count
        ecall = ECALL_FLAT_AMOUNT * ecall_count
        if previous:
            line["previous_ot_hours"] += ot_hours
            line["previous_holiday_days"] += holiday_days
            line["previous_ot_amount"] += overtime
            line["previous_holiday_amount"] += holiday
            line["previous_large_ecall_count"] += large_ecall_count
            line["previous_ecall_count"] += ecall_count
            line["previous_large_ecall_amount"] += large_ecall
            line["previous_ecall_amount"] += ecall
        else:
            line["working_days"] += working_days
            line["holiday_days"] += holiday_days
            line["current_ot_hours"] += ot_hours
            line["base_amount"] += base
            line["holiday_amount"] += holiday
            line["ot_amount"] += overtime
            line["current_large_ecall_count"] += large_ecall_count
            line["current_ecall_count"] += ecall_count
            line["large_ecall_amount"] += large_ecall
            line["ecall_amount"] += ecall
        line["base_rate"] = rates["base_rate"]
        line["holiday_rate"] = rates["holiday_rate"]
        line["ot_rate"] = rates["ot_rate"]
        line["ot_divisor"] = rates["ot_divisor"]
        total += base + holiday + overtime + large_ecall + ecall
        if casual_components is not None:
            casual_components.append(
                {
                    "income": base
                    + holiday
                    + overtime
                    + large_ecall
                    + ecall,
                    "days": working_days + holiday_days,
                    "sign": Decimal("1"),
                }
            )
    return total


def apply_forecast_segments(
    employee,
    segments,
    start,
    end,
    lines=None,
    apply_to_lines=False,
    casual_components=None,
    sign=Decimal("1"),
):
    lines = lines if lines is not None else {}
    total = Decimal("0")
    for segment in segments:
        project = segment.project
        rates = average_rates(employee, start, end, project)
        if not rates:
            continue
        working_days = decimal_value(segment.working_days)
        holiday_days = decimal_value(segment.sunday_holiday_days)
        base = rates["base_rate"] * working_days
        holiday = rates["holiday_rate"] * holiday_days
        if apply_to_lines:
            line = lines.setdefault(line_key(project), empty_line(project))
            line["forecast_working_days"] += working_days
            line["forecast_holiday_days"] += holiday_days
            line["forecast_base_amount"] += base
            line["forecast_holiday_amount"] += holiday
            line["working_days"] += working_days
            line["holiday_days"] += holiday_days
            line["base_amount"] += base
            line["holiday_amount"] += holiday
            line["base_rate"] = rates["base_rate"]
            line["holiday_rate"] = rates["holiday_rate"]
            line["ot_rate"] = rates["ot_rate"]
            line["ot_divisor"] = rates["ot_divisor"]
        if casual_components is not None:
            casual_components.append(
                {
                    "income": base + holiday,
                    "days": working_days + holiday_days,
                    "sign": sign,
                }
            )
        total += base + holiday
    return total


def forecast_tail(
    employee,
    start,
    end,
    lines=None,
    casual_components=None,
    sign=Decimal("1"),
):
    lines = lines if lines is not None else {}
    total = Decimal("0")
    for day in date_range(start, end):
        assignment = current_assignment_on(employee, day)
        project = assignment.project if assignment else None
        rates = salary_rate_for_date(employee, day, project)
        if not rates:
            continue
        if (
            rates["salary"].salary_basis == "daily"
            and day.weekday() == 6
        ):
            continue
        key = line_key(project)
        line = lines.setdefault(key, empty_line(project))
        if day.weekday() == 6:
            line["forecast_holiday_days"] += Decimal("1")
            line["forecast_holiday_amount"] += rates["holiday_rate"]
            line["holiday_days"] += Decimal("1")
            line["holiday_amount"] += rates["holiday_rate"]
            total += rates["holiday_rate"]
        else:
            line["forecast_working_days"] += Decimal("1")
            line["forecast_base_amount"] += rates["base_rate"]
            line["working_days"] += Decimal("1")
            line["base_amount"] += rates["base_rate"]
            total += rates["base_rate"]
        line["base_rate"] = rates["base_rate"]
        line["holiday_rate"] = rates["holiday_rate"]
        line["ot_rate"] = rates["ot_rate"]
        line["ot_divisor"] = rates["ot_divisor"]
        if casual_components is not None:
            casual_components.append(
                {
                    "income": rates["holiday_rate"]
                    if day.weekday() == 6
                    else rates["base_rate"],
                    "days": Decimal("1"),
                    "sign": sign,
                }
            )
    return total


def active_allowances(employee, month_start, month_end):
    rows = []
    days_in_month = Decimal((month_end - month_start).days + 1)
    for allowance in employee.allowances:
        start = max(month_start, allowance.effective_from)
        end = min(month_end, allowance.effective_to or month_end)
        if end < start:
            continue
        ratio = Decimal((end - start).days + 1) / days_in_month
        rows.append((allowance, decimal_value(allowance.amount) * ratio))
    return rows


def casual_daily_mpf(daily_income):
    income = decimal_value(daily_income)
    if income < Decimal("280"):
        return Decimal("0"), Decimal("10")
    if income < Decimal("350"):
        return Decimal("15"), Decimal("15")
    if income < Decimal("450"):
        return Decimal("20"), Decimal("20")
    if income < Decimal("550"):
        return Decimal("25"), Decimal("25")
    if income < Decimal("650"):
        return Decimal("30"), Decimal("30")
    if income < Decimal("750"):
        return Decimal("35"), Decimal("35")
    if income < Decimal("850"):
        return Decimal("40"), Decimal("40")
    if income < Decimal("950"):
        return Decimal("45"), Decimal("45")
    return Decimal("50"), Decimal("50")


def casual_mpf_from_components(components):
    employee_amount = Decimal("0")
    employer_amount = Decimal("0")
    for component in components:
        days = max(Decimal("0"), decimal_value(component.get("days")))
        if not days:
            continue
        income = max(Decimal("0"), decimal_value(component.get("income")))
        employee_daily, employer_daily = casual_daily_mpf(income / days)
        sign = decimal_value(component.get("sign") or 1)
        employee_amount += employee_daily * days * sign
        employer_amount += employer_daily * days * sign
    return (
        rounded(max(Decimal("0"), employee_amount)),
        rounded(max(Decimal("0"), employer_amount)),
    )


def mpf_amounts(
    employee,
    relevant_income,
    working_days,
    month_end,
    casual_components=None,
):
    warnings = []
    if employee.mpf_mode == "exempt":
        return Decimal("0"), Decimal("0"), ["MPF：員工標記為豁免"]
    if not employee.date_of_birth:
        warnings.append("缺出生日期，請人工核對 MPF 年齡豁免")
    else:
        age = month_end.year - employee.date_of_birth.year - (
            (month_end.month, month_end.day)
            < (employee.date_of_birth.month, employee.date_of_birth.day)
        )
        if age < 18 or age >= 65:
            return Decimal("0"), Decimal("0"), [
                f"MPF：{age} 歲，按年齡不供款"
            ]

    income = max(Decimal("0"), decimal_value(relevant_income))
    if employee.mpf_mode == "casual":
        if casual_components:
            employee_amount, employer_amount = casual_mpf_from_components(
                casual_components
            )
            warnings.append("MPF：建造業臨時僱員按每日入息級距計算")
            return employee_amount, employer_amount, warnings
        days = max(Decimal("0"), decimal_value(working_days))
        if not days:
            return Decimal("0"), Decimal("0"), warnings
        employee_daily, employer_daily = casual_daily_mpf(income / days)
        employee_amount = employee_daily * days
        employer_amount = employer_daily * days
        warnings.append("MPF：建造業臨時僱員按每日入息級距計算")
        return rounded(employee_amount), rounded(employer_amount), warnings

    employee_amount = (
        Decimal("0")
        if income < Decimal("7100")
        else min(income * Decimal("0.05"), Decimal("1500"))
    )
    employer_amount = min(income * Decimal("0.05"), Decimal("1500"))
    return rounded(employee_amount), rounded(employer_amount), warnings


def prior_forecast_total(employee, year_month):
    previous = previous_month(year_month)
    row = (
        PayrollEmployeeResult.query.join(PayrollRun)
        .filter(
            PayrollRun.year_month == previous,
            PayrollEmployeeResult.employee_id == employee.id,
        )
        .order_by(PayrollRun.created_at.desc())
        .first()
    )
    if row and row.calculation_json:
        value = row.calculation_json.get("forecast_tail_total")
        if value is not None:
            return decimal_value(value)
    previous_start, previous_end = parse_year_month(previous)
    return forecast_tail(
        employee,
        previous_start.replace(day=21),
        previous_end,
        {},
    )


def segment_day_total(segments):
    return sum(
        (
            decimal_value(item.working_days)
            + decimal_value(item.sunday_holiday_days)
        )
        for item in segments
    )


def termination_amounts(employee, month_start, month_end):
    period = next(
        (
            item
            for item in employee.employment_periods
            if item.end_date and month_start <= item.end_date <= month_end
        ),
        None,
    )
    if not period:
        return Decimal("0"), Decimal("0")
    payment_in_lieu = decimal_value(period.payment_in_lieu)
    severance = decimal_value(period.severance_payment)
    long_service = decimal_value(period.long_service_payment)
    return payment_in_lieu, severance + long_service


def employee_warnings(employee):
    warnings = []
    if not active_document(employee, "signed_contract"):
        warnings.append("缺已簽署合同")
    if (
        not employee.bank_name
        or not employee.bank_account_no
        or not active_document(employee, "bank_proof")
    ):
        warnings.append("銀行資料未完成")
    active_assignments = sorted(
        (
            assignment
            for assignment in employee.assignments
            if assignment.status == "active"
            and assignment.effective_from <= date.today()
        ),
        key=lambda assignment: assignment.effective_from,
    )
    if any(
        not assignment.evidence_document
        or assignment.evidence_document.status != "active"
        for assignment in active_assignments[1:]
    ):
        warnings.append("有任職調整缺憑證")
    active_salaries = sorted(
        (
            salary
            for salary in employee.salaries
            if salary.status == "active"
            and salary.effective_from <= date.today()
        ),
        key=lambda salary: salary.effective_from,
    )
    if any(
        not salary.evidence_document
        or salary.evidence_document.status != "active"
        for salary in active_salaries[1:]
    ):
        warnings.append("有薪酬調整缺憑證")
    return warnings


def calculate_employee(employee, year_month):
    month_start, month_end = parse_year_month(year_month)
    summary = AttendanceMonthlySummary.query.filter_by(
        employee_id=employee.id,
        year_month=year_month,
    ).first()
    blockers = []
    warnings = employee_warnings(employee)
    if not summary or summary.status not in {"received", "not_required"}:
        blockers.append("缺考勤")
    if not current_salary_on(employee, month_end):
        blockers.append("缺薪酬")
    if (
        employee.bank_changed_at
        and (
            not employee.bank_payroll_confirmed_at
            or employee.bank_payroll_confirmed_at < employee.bank_changed_at
        )
    ):
        blockers.append("新銀行資料尚未核對")

    group = group_on(employee, month_end)
    if blockers:
        return {
            "employee": employee,
            "group": group,
            "blockers": blockers,
            "warnings": warnings,
            "lines": [],
        }

    lines = {}
    current_start = month_start
    current_end = min(month_end, month_start.replace(day=20))
    previous_start, previous_end = parse_year_month(previous_month(year_month))
    previous_start = previous_start.replace(day=21)
    casual_components = []

    current_actual_segments = attendance_segments(summary, "current_1_20")
    current_actual_total = apply_actual_segments(
        employee,
        current_actual_segments,
        current_start,
        current_end,
        lines,
        casual_components=casual_components,
    )
    previous_actual_segments = attendance_segments(
        summary,
        "previous_21_end",
    )
    actual_previous_tail = apply_actual_segments(
        employee,
        previous_actual_segments,
        previous_start,
        previous_end,
        lines,
        previous=True,
        casual_components=casual_components,
    )
    current_forecast_segments = attendance_segments(
        summary,
        "current_21_end_forecast",
    )
    if current_forecast_segments:
        forecast_tail_total = apply_forecast_segments(
            employee,
            current_forecast_segments,
            month_start.replace(day=21),
            month_end,
            lines,
            apply_to_lines=True,
            casual_components=casual_components,
        )
    else:
        forecast_tail_total = forecast_tail(
            employee,
            month_start.replace(day=21),
            month_end,
            lines,
            casual_components=casual_components,
        )

    previous_forecast_segments = attendance_segments(
        summary,
        "previous_21_end_forecast",
    )
    if previous_forecast_segments:
        expected_previous_tail = apply_forecast_segments(
            employee,
            previous_forecast_segments,
            previous_start,
            previous_end,
            casual_components=casual_components,
            sign=Decimal("-1"),
        )
    else:
        expected_previous_tail = prior_forecast_total(employee, year_month)
        previous_summary = AttendanceMonthlySummary.query.filter_by(
            employee_id=employee.id,
            year_month=previous_month(year_month),
        ).first()
        previous_forecast_days = segment_day_total(
            attendance_segments(
                previous_summary,
                "current_21_end_forecast",
            )
        )
        if not previous_forecast_days:
            legacy_lines = {}
            forecast_tail(
                employee,
                previous_start,
                previous_end,
                legacy_lines,
            )
            previous_forecast_days = sum(
                decimal_value(line["forecast_working_days"])
                + decimal_value(line["forecast_holiday_days"])
                for line in legacy_lines.values()
            )
        if previous_forecast_days:
            casual_components.append(
                {
                    "income": expected_previous_tail,
                    "days": previous_forecast_days,
                    "sign": Decimal("-1"),
                }
            )
    overpay = max(Decimal("0"), expected_previous_tail - actual_previous_tail)
    underpay = max(Decimal("0"), actual_previous_tail - expected_previous_tail)

    for allowance, amount in active_allowances(
        employee,
        month_start,
        month_end,
    ):
        project = allowance.project
        if not project:
            assignment = current_assignment_on(employee, month_end)
            project = assignment.project if assignment else None
        line = lines.setdefault(line_key(project), empty_line(project))
        line["allowance_amount"] += amount

    adjustments = PayrollAdjustment.query.filter_by(
        employee_id=employee.id,
        year_month=year_month,
        status="active",
    ).all()
    for adjustment in adjustments:
        project = adjustment.project
        line = lines.setdefault(line_key(project), empty_line(project))
        line["adjustment_amount"] += decimal_value(adjustment.amount)
        if not adjustment.evidence_document_id:
            warnings.append(f"調整「{adjustment.label}」缺憑證")

    line_rows = list(lines.values())
    for line in line_rows:
        line["gross_amount"] = (
            line["base_amount"]
            + line["holiday_amount"]
            + line["ot_amount"]
            + line["large_ecall_amount"]
            + line["ecall_amount"]
            + line["allowance_amount"]
            + line["adjustment_amount"]
        )
        for key in list(line):
            if isinstance(line[key], Decimal):
                line[key] = rounded(line[key])

    base = sum(
        decimal_value(line["base_amount"]) for line in line_rows
    )
    holiday = sum(
        decimal_value(line["holiday_amount"]) for line in line_rows
    )
    overtime = sum(
        decimal_value(line["ot_amount"]) for line in line_rows
    )
    large_ecall = sum(
        decimal_value(line["large_ecall_amount"]) for line in line_rows
    )
    ecall = sum(
        decimal_value(line["ecall_amount"]) for line in line_rows
    )
    allowances = sum(
        decimal_value(line["allowance_amount"]) for line in line_rows
    )
    adjustments_total = sum(
        decimal_value(line["adjustment_amount"]) for line in line_rows
    )
    working_days = sum(
        decimal_value(line["working_days"]) for line in line_rows
    )
    relevant_income = (
        base
        + holiday
        + overtime
        + large_ecall
        + ecall
        + allowances
        + adjustments_total
        - overpay
        + underpay
    )
    employee_mpf, employer_mpf, mpf_warnings = mpf_amounts(
        employee,
        relevant_income,
        working_days,
        month_end,
        casual_components=casual_components,
    )
    warnings.extend(mpf_warnings)
    payment_in_lieu, severance_long_service = termination_amounts(
        employee,
        month_start,
        month_end,
    )
    net = (
        relevant_income
        - employee_mpf
        + payment_in_lieu
        + severance_long_service
    )
    salary = current_salary_on(employee, month_end)
    assignment = current_assignment_on(employee, month_end)
    return {
        "employee": employee,
        "group": group,
        "currency": salary.currency,
        "salary_basis": salary.salary_basis,
        "salary_amount": rounded(salary.amount),
        "assignment": assignment,
        "attendance": summary,
        "base_amount": rounded(base),
        "holiday_amount": rounded(holiday),
        "ot_amount": rounded(overtime),
        "large_ecall_amount": rounded(large_ecall),
        "ecall_amount": rounded(ecall),
        "allowance_amount": rounded(allowances),
        "adjustment_amount": rounded(adjustments_total),
        "overpay_amount": rounded(overpay),
        "underpay_amount": rounded(underpay),
        "gross_amount": rounded(relevant_income),
        "employee_mpf": rounded(employee_mpf),
        "employer_mpf": rounded(employer_mpf),
        "payment_in_lieu": rounded(payment_in_lieu),
        "severance_long_service": rounded(severance_long_service),
        "net_amount": rounded(net),
        "forecast_tail_total": rounded(forecast_tail_total),
        "current_actual_total": rounded(current_actual_total),
        "current_pay_total": rounded(
            current_actual_total + forecast_tail_total
        ),
        "actual_previous_tail": rounded(actual_previous_tail),
        "expected_previous_tail": rounded(expected_previous_tail),
        "reconciliation_amount": rounded(
            actual_previous_tail - expected_previous_tail
        ),
        "current_actual_days": rounded(
            segment_day_total(current_actual_segments)
        ),
        "current_forecast_days": rounded(
            segment_day_total(current_forecast_segments)
            if current_forecast_segments
            else sum(
                decimal_value(line["forecast_working_days"])
                + decimal_value(line["forecast_holiday_days"])
                for line in line_rows
            )
        ),
        "previous_actual_days": rounded(
            segment_day_total(previous_actual_segments)
        ),
        "previous_forecast_days": rounded(
            segment_day_total(previous_forecast_segments)
            if previous_forecast_segments
            else previous_forecast_days
        ),
        "warnings": list(dict.fromkeys(warnings)),
        "blockers": [],
        "lines": line_rows,
    }


def calculate_payroll(year_month, payroll_group="all"):
    return [
        calculate_employee(employee, year_month)
        for employee in employees_for_payroll(year_month, payroll_group)
    ]


def serialize_line(line):
    return {
        key: (
            str(value)
            if isinstance(value, Decimal)
            else value.id
            if key == "project" and value
            else None
            if key == "project"
            else value
        )
        for key, value in line.items()
    }


def snapshot_payroll(year_month, payroll_group, rows, user_id):
    run = PayrollRun(
        year_month=year_month,
        payroll_group=payroll_group,
        rule_version=RULE_VERSION,
        created_by=user_id,
        source_json={
            "period": {
                "current_actual": f"{year_month}-01..20",
                "previous_actual": f"{previous_month(year_month)}-21..end",
                "current_forecast": f"{year_month}-21..end",
                "previous_forecast": (
                    f"{previous_month(year_month)}-21..end"
                ),
            },
            "ecall": {
                "large": "one applicable daily rate per occurrence",
                "ordinary": "HKD 400 per occurrence",
                "forecast": "zero until actual attendance is received",
            },
            "groups": list(PAYROLL_GROUP_CODES),
        },
    )
    db.session.add(run)
    db.session.flush()
    for row in rows:
        if row["blockers"]:
            continue
        result = PayrollEmployeeResult(
            run=run,
            employee_id=row["employee"].id,
            currency=row["currency"],
            base_amount=row["base_amount"],
            ot_amount=row["ot_amount"],
            holiday_amount=row["holiday_amount"],
            large_ecall_amount=row["large_ecall_amount"],
            ecall_amount=row["ecall_amount"],
            allowance_amount=row["allowance_amount"],
            overpay_amount=row["overpay_amount"],
            underpay_amount=row["underpay_amount"],
            adjustment_amount=row["adjustment_amount"],
            gross_amount=row["gross_amount"],
            employee_mpf=row["employee_mpf"],
            employer_mpf=row["employer_mpf"],
            payment_in_lieu=row["payment_in_lieu"],
            severance_long_service=row["severance_long_service"],
            net_amount=row["net_amount"],
            warnings_json=row["warnings"],
            calculation_json={
                "group": row["group"],
                "salary_basis": row["salary_basis"],
                "salary_amount": str(row["salary_amount"]),
                "forecast_tail_total": str(row["forecast_tail_total"]),
                "current_actual_total": str(row["current_actual_total"]),
                "current_pay_total": str(row["current_pay_total"]),
                "actual_previous_tail": str(row["actual_previous_tail"]),
                "expected_previous_tail": str(
                    row["expected_previous_tail"]
                ),
                "current_actual_days": str(row["current_actual_days"]),
                "current_forecast_days": str(row["current_forecast_days"]),
                "previous_actual_days": str(row["previous_actual_days"]),
                "previous_forecast_days": str(
                    row["previous_forecast_days"]
                ),
                "reconciliation_amount": str(
                    row["reconciliation_amount"]
                ),
                "lines": [serialize_line(line) for line in row["lines"]],
            },
        )
        db.session.add(result)
        db.session.flush()
        for line in row["lines"]:
            db.session.add(
                PayrollProjectLine(
                    employee_result=result,
                    project_id=(
                        line["project"].id if line["project"] else None
                    ),
                    working_days=line["working_days"],
                    ot_hours=line["current_ot_hours"],
                    sunday_holiday_days=line["holiday_days"],
                    large_ecall_count=int(
                        decimal_value(line["current_large_ecall_count"])
                    ),
                    ecall_count=int(
                        decimal_value(line["current_ecall_count"])
                    ),
                    base_amount=line["base_amount"],
                    ot_amount=line["ot_amount"],
                    holiday_amount=line["holiday_amount"],
                    large_ecall_amount=line["large_ecall_amount"],
                    ecall_amount=line["ecall_amount"],
                    allowance_amount=line["allowance_amount"],
                    adjustment_amount=line["adjustment_amount"],
                    gross_amount=line["gross_amount"],
                )
            )
    db.session.commit()
    return run


def project_summary(rows):
    summary = defaultdict(
        lambda: {
            "project": None,
            "headcount": set(),
            "base": Decimal("0"),
            "ot": Decimal("0"),
            "ecall": Decimal("0"),
            "allowance": Decimal("0"),
            "total": Decimal("0"),
        }
    )
    for row in rows:
        if row["blockers"]:
            continue
        for line in row["lines"]:
            project = line["project"]
            key = project.id if project else 0
            item = summary[key]
            item["project"] = project
            item["headcount"].add(row["employee"].id)
            item["base"] += decimal_value(line["base_amount"])
            item["ot"] += decimal_value(line["ot_amount"])
            item["ecall"] += (
                decimal_value(line["large_ecall_amount"])
                + decimal_value(line["ecall_amount"])
            )
            item["allowance"] += decimal_value(line["allowance_amount"])
            item["total"] += decimal_value(line["gross_amount"])
    return [
        {
            **item,
            "headcount": len(item["headcount"]),
            "base": rounded(item["base"]),
            "ot": rounded(item["ot"]),
            "ecall": rounded(item["ecall"]),
            "allowance": rounded(item["allowance"]),
            "total": rounded(item["total"]),
        }
        for item in summary.values()
    ]
