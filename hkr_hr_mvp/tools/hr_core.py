"""Transitional shim; L0-L3 helpers now live in hkr_hr.{platform,references,employees,documents}."""
from datetime import date, timedelta
from decimal import Decimal

from hkr_hr.app.models import (
    EmployeeAnnualLeaveAllocation,
    EmployeeAnnualLeaveBalance,
    EmployeeAnnualLeaveRecord,
    EmployeeCompLeaveAllocation,
    EmployeeCompLeaveCredit,
    PayrollEmployeeResult,
    PayrollRun,
    db,
)
from hkr_hr.documents.api import find_duplicate_employee_document
from hkr_hr.employees.api import (
    close_previous_record,
    create_assignment,
    create_mpf_enrollment,
    create_salary,
    current_assignment_on,
    current_bank_account_on,
    current_mpf_on,
    current_salary_on,
    employee_audit_snapshot,
    ensure_current_employment_period,
    next_employee_no,
    rebuild_effective_ranges,
)
from hkr_hr.platform.audit import write_audit
from hkr_hr.platform.dates import (
    DOCUMENT_CATEGORIES,
    IDENTITY_TYPE_OPTIONS,
    PAYROLL_GROUPS,
    REPLACEMENT_REASONS,
    TERMINATION_REASONS,
    WORKWEEK_DAY_OPTIONS,
    attendance_period_bounds,
    current_month,
    default_workweek_days,
    format_date,
    format_money,
    masked_bank_account,
    money,
    month_days,
    normalize_identity_number,
    normalize_workweek_days,
    parse_bool,
    parse_date,
    parse_decimal,
    parse_year_month,
    previous_month,
    valid_salary_amount,
)
from hkr_hr.platform.files import (
    copy_file_to_employee,
    delete_employee_files,
    employee_files_path,
    file_sha256,
    safe_employee_folder,
    store_employee_file,
    unique_filename,
    uploaded_file_sha256,
)
from hkr_hr.references.api import (
    DEFAULT_DEPARTMENT_ORDER,
    DEFAULT_MPF_SCHEMES,
    DEFAULT_PROJECTS,
    DEFAULT_REFERENCE_VALUES,
    EMPLOYEE_TYPES,
    REFERENCE_LISTS,
    employee_type_by_code,
    ensure_reference_seed,
    ensure_reference_value,
    normalize_reference_display,
    reference_by_code,
    reference_map,
    reference_options,
    reference_sort_key,
    reference_sort_order,
    slug_code,
)


def statutory_annual_leave_days(start_date, year):
    if not start_date:
        return Decimal("0")
    service_years = max(0, year - start_date.year)
    if date(year, 12, 31) < date(
        start_date.year + service_years,
        start_date.month,
        min(start_date.day, 28),
    ):
        service_years -= 1
    if service_years < 1:
        return Decimal("0")
    if service_years <= 2:
        return Decimal("7")
    return Decimal(str(min(14, service_years + 5)))


def annual_leave_expiry(balance):
    if balance.year <= 2023:
        return None
    return (
        balance.extended_until
        or balance.expiry_date
        or date(balance.year + 1, 3, 31)
    )


def ensure_annual_leave_balance(employee, year):
    balance = EmployeeAnnualLeaveBalance.query.filter_by(
        employee_id=employee.id,
        year=year,
    ).first()
    if not balance:
        balance = EmployeeAnnualLeaveBalance(employee=employee, year=year)
        if year >= 2024:
            balance.expiry_date = date(year + 1, 3, 31)
        db.session.add(balance)
        from tools.annual_leave_policy import freeze_balance
        freeze_balance(employee, balance)
        db.session.flush()
    return balance


def annual_leave_allocated_days(balance, records=None):
    allocations = [
        item
        for item in balance.allocations
        if item.record and item.record.status == "active"
    ]
    allocated = sum(
        (Decimal(str(item.days)) for item in allocations),
        Decimal("0"),
    )
    legacy_records = ([item for item in records if item.entitlement_year == balance.year
                       and item.leave_type == "annual" and item.status == "active"]
                      if records is not None else EmployeeAnnualLeaveRecord.query.filter_by(
                          employee_id=balance.employee_id, entitlement_year=balance.year,
                          leave_type="annual", status="active").all())
    fallback = sum(
        (
            max(
                Decimal("0"),
                Decimal(str(item.days))
                - sum(
                    (
                        Decimal(str(allocation.days))
                        for allocation in item.allocations
                    ),
                    Decimal("0"),
                )
                - sum(
                    (
                        Decimal(str(allocation.days))
                        for allocation in item.comp_leave_allocations
                    ),
                    Decimal("0"),
                ),
            )
            for item in legacy_records
        ),
        Decimal("0"),
    )
    return allocated + fallback


def annual_leave_taken_days(employee, year):
    """Return annual leave recorded against a selected entitlement year."""
    records = EmployeeAnnualLeaveRecord.query.filter_by(
        employee_id=employee.id,
        entitlement_year=year,
        leave_type="annual",
        status="active",
    ).all()
    return sum(
        (Decimal(str(item.days or 0)) for item in records),
        Decimal("0"),
    )


def annual_leave_bucket(employee, balance, as_of=None, prorate_current=False, records=None):
    as_of = as_of or date.today()
    year = balance.year
    period = employee.current_period
    start_date = period.start_date if period else None
    statutory = statutory_annual_leave_days(start_date, year)
    contract = (
        Decimal(str(period.contract_annual_leave_days))
        if period and period.contract_annual_leave_days is not None
        else Decimal("0")
    )
    calculated = max(statutory, contract)
    from tools.annual_leave_policy import active_for, entitlement, annual_rate
    company_policy = active_for(period, year) and year >= 2026
    if balance.calculated_entitled_days is not None:
        calculated = Decimal(str(balance.calculated_entitled_days))
        company_policy = True
    elif company_policy:
        calculated = entitlement(start_date, period.contract_annual_leave_days, year) or Decimal("0")
    override = (
        Decimal(str(balance.entitled_days_override))
        if balance.entitled_days_override is not None
        else None
    )
    entitled = override if override is not None else calculated
    if year <= 2023:
        entitled = override or Decimal("0")
    if prorate_current and year == as_of.year and start_date:
        year_start = date(year, 1, 1)
        employed_from = max(start_date, year_start)
        employed_days = max(0, (as_of - employed_from).days + 1)
        days_in_year = Decimal("366" if calendar.isleap(year) else "365")
        if company_policy and override is None:
            rate = (Decimal(str(balance.calculated_annual_rate))
                    if balance.calculated_annual_rate is not None
                    else annual_rate(start_date, period.contract_annual_leave_days, year) or Decimal("0"))
            earning_start = max(balance.calculation_start_date or start_date, year_start)
            entitled = rate * Decimal(max(0, (as_of - earning_start).days + 1)) / days_in_year
        elif company_policy:
            scheduled_start = max(balance.calculation_start_date or start_date, year_start)
            scheduled_days = max(1, (date(year, 12, 31) - scheduled_start).days + 1)
            entitled = entitled * Decimal(max(0, (as_of - scheduled_start).days + 1)) / Decimal(scheduled_days)
        else:
            entitled = entitled * Decimal(employed_days) / days_in_year
    carried = Decimal(str(balance.carried_from_previous_days or 0))
    manual = Decimal(str(balance.manual_adjustment_days or 0))
    used = annual_leave_allocated_days(balance, records=records)
    expiry = annual_leave_expiry(balance)
    expired = bool(expiry and expiry < as_of)
    total = entitled + carried + manual
    return {
        "balance": balance,
        "year": year,
        "is_legacy": year <= 2023,
        "statutory": statutory,
        "contract": contract,
        "calculated_entitled": calculated,
        "company_policy": company_policy,
        "calculation_pending": bool(year >= 2026 and (not period or period.contract_annual_leave_days is None or not active_for(period, year)) and balance.calculated_entitled_days is None),
        "entitled_override": override,
        "entitled": entitled,
        "carried": carried,
        "manual": manual,
        "used": used,
        "total": total,
        "remaining": total - used,
        "expiry_date": expiry,
        "extended_until": balance.extended_until,
        "expired": expired,
    }


def annual_leave_buckets(
    employee,
    as_of=None,
    include_expired=True,
    prorate_current=False,
):
    as_of = as_of or date.today()
    balances = list(
        EmployeeAnnualLeaveBalance.query.filter_by(employee_id=employee.id)
        .order_by(EmployeeAnnualLeaveBalance.year.asc())
        .all()
    )
    if not any(item.year == as_of.year for item in balances):
        balance = EmployeeAnnualLeaveBalance(
            employee_id=employee.id,
            year=as_of.year,
        )
        balance.expiry_date = date(as_of.year + 1, 3, 31)
        balances.append(balance)
    rows = [
        annual_leave_bucket(
            employee,
            balance,
            as_of=as_of,
            prorate_current=prorate_current,
        )
        for balance in balances
    ]
    if not include_expired:
        rows = [item for item in rows if not item["expired"]]
    return rows


def set_annual_leave_allocations(
    record,
    legacy_days,
    regular_days,
    as_of=None,
):
    as_of = as_of or record.leave_date
    legacy_days = Decimal(str(legacy_days or 0))
    regular_days = Decimal(str(regular_days or 0))
    if legacy_days < 0 or regular_days < 0:
        raise ValueError("Annual leave allocation cannot be negative.")

    if legacy_days:
        legacy_balance = ensure_annual_leave_balance(record.employee, 2023)
        legacy = annual_leave_bucket(record.employee, legacy_balance, as_of=as_of)
        if legacy["remaining"] < legacy_days:
            raise ValueError("Insufficient 2023-and-earlier annual leave.")
        db.session.add(
            EmployeeAnnualLeaveAllocation(
                record=record,
                balance=legacy_balance,
                days=legacy_days,
            )
        )

    if regular_days:
        ensure_annual_leave_balance(record.employee, as_of.year)
        buckets = [
            item
            for item in annual_leave_buckets(
                record.employee,
                as_of=as_of,
                include_expired=False,
            )
            if not item["is_legacy"] and item["remaining"] > 0
        ]
        buckets.sort(
            key=lambda item: (
                item["expiry_date"] or date.max,
                item["year"],
            )
        )
        remaining = regular_days
        for bucket in buckets:
            if remaining <= 0:
                break
            allocated = min(remaining, bucket["remaining"])
            if allocated <= 0:
                continue
            db.session.add(
                EmployeeAnnualLeaveAllocation(
                    record=record,
                    balance=bucket["balance"],
                    days=allocated,
                )
            )
            remaining -= allocated
        if remaining > 0:
            current_balance = ensure_annual_leave_balance(
                record.employee,
                as_of.year,
            )
            db.session.add(
                EmployeeAnnualLeaveAllocation(
                    record=record,
                    balance=current_balance,
                    days=remaining,
                )
            )


def comp_leave_credit_remaining(credit, excluding_record_id=None):
    used = sum(
        (
            Decimal(str(allocation.days or 0))
            for allocation in credit.allocations
            if allocation.leave_record
            and allocation.leave_record.status == "active"
            and allocation.leave_record_id != excluding_record_id
        ),
        Decimal("0"),
    )
    return max(Decimal("0"), Decimal(str(credit.days or 0)) - used)


def comp_leave_summary(employee):
    total = Decimal("0")
    used = Decimal("0")
    for credit in employee.comp_leave_credits:
        if credit.status != "active":
            continue
        total += Decimal(str(credit.days or 0))
        used += Decimal(str(credit.days or 0)) - comp_leave_credit_remaining(
            credit
        )
    return {
        "total": total,
        "used": used,
        "remaining": max(Decimal("0"), total - used),
    }


def clear_leave_allocations(record):
    record.allocations.clear()
    record.comp_leave_allocations.clear()
    db.session.flush()


def allocate_annual_leave_with_comp(record, as_of=None):
    """Allocate annual leave: comp leave, legacy 2023, then oldest valid year."""
    as_of = as_of or record.leave_date
    remaining = Decimal(str(record.days or 0))
    credits = sorted(
        (
            credit
            for credit in record.employee.comp_leave_credits
            if credit.status == "active"
            and credit.source_date <= as_of
            and comp_leave_credit_remaining(
                credit, excluding_record_id=record.id
            )
            > 0
        ),
        key=lambda credit: (credit.source_date, credit.id),
    )
    for credit in credits:
        if remaining <= 0:
            break
        allocated = min(
            remaining,
            comp_leave_credit_remaining(
                credit, excluding_record_id=record.id
            ),
        )
        db.session.add(
            EmployeeCompLeaveAllocation(
                leave_record=record,
                credit=credit,
                days=allocated,
            )
        )
        remaining -= allocated

    if remaining <= 0:
        return

    legacy_balance = ensure_annual_leave_balance(record.employee, 2023)
    legacy = annual_leave_bucket(record.employee, legacy_balance, as_of=as_of)
    legacy_days = min(remaining, legacy["remaining"])
    if legacy_days > 0:
        db.session.add(
            EmployeeAnnualLeaveAllocation(
                record=record,
                balance=legacy_balance,
                days=legacy_days,
            )
        )
        remaining -= legacy_days

    if remaining > 0:
        set_annual_leave_allocations(
            record,
            Decimal("0"),
            remaining,
            as_of=as_of,
        )


def annual_leave_summary(employee, year=None, preloaded=False):
    year = year or date.today().year
    records = employee.annual_leave_records if preloaded else None
    balance = (next((item for item in employee.annual_leave_balances if item.year == year), None)
               if preloaded else EmployeeAnnualLeaveBalance.query.filter_by(employee_id=employee.id, year=year).first())
    if not balance:
        balance = EmployeeAnnualLeaveBalance(employee_id=employee.id, year=year)
        if year >= 2024:
            balance.expiry_date = date(year + 1, 3, 31)
    period = employee.current_period
    termination_date = (
        period.end_date
        if period and period.end_date and period.end_date.year == year
        else None
    )
    as_of = termination_date or date(year, 12, 31)
    current = annual_leave_bucket(
        employee,
        balance,
        as_of=as_of,
        prorate_current=bool(termination_date),
        records=records,
    )
    current["bucket_used"] = current["used"]
    current["used"] = (sum((Decimal(str(item.days or 0)) for item in records
                            if item.entitlement_year == year and item.leave_type == "annual"
                            and item.status == "active"), Decimal("0"))
                       if preloaded else annual_leave_taken_days(employee, year))
    current["termination_prorated"] = bool(termination_date)
    current["termination_date"] = termination_date
    legacy_balance = (next((item for item in employee.annual_leave_balances if item.year == 2023), None)
                      if preloaded else EmployeeAnnualLeaveBalance.query.filter_by(employee_id=employee.id, year=2023).first())
    legacy = (
        annual_leave_bucket(employee, legacy_balance, as_of=date.today(), records=records)
        if legacy_balance
        else None
    )
    current.update(
        {
            "legacy_remaining": (
                legacy["remaining"] if legacy else Decimal("0")
            ),
            "legacy_used": legacy["used"] if legacy else Decimal("0"),
            "carry_deadline": annual_leave_expiry(balance),
        }
    )
    return current


def annual_leave_days_between(
    start_date,
    end_date,
    start_session="am",
    end_session="pm",
):
    if (not start_date or not end_date or end_date < start_date
            or start_session not in {"am", "pm"}
            or end_session not in {"am", "pm"}
            or (start_date == end_date and start_session == "pm" and end_session == "am")):
        return None
    days = Decimal((end_date - start_date).days + 1)
    if start_session == "pm":
        days -= Decimal("0.5")
    if end_session == "am":
        days -= Decimal("0.5")
    return days


def average_wage_prefill(employee, end_date=None):
    reference_date = end_date or date.today()
    month = previous_month(reference_date.strftime("%Y-%m"))
    results = []
    for _ in range(12):
        row = (
            PayrollEmployeeResult.query.join(PayrollRun)
            .filter(
                PayrollRun.year_month == month,
                PayrollEmployeeResult.employee_id == employee.id,
            )
            .order_by(PayrollRun.created_at.desc())
            .first()
        )
        if row:
            results.append(
                {
                    "month": month,
                    "amount": money(row.gross_amount),
                }
            )
        month = previous_month(month)
    average = (
        money(sum((item["amount"] for item in results), Decimal("0")) / len(results))
        if results
        else Decimal("0")
    )
    total = money(
        sum((item["amount"] for item in results), Decimal("0"))
    )
    return {
        "average": average,
        "total": total,
        "months": [item["month"] for item in reversed(results)],
        "count": len(results),
    }


def termination_estimate(employee, end_date, reason, average_wage=None):
    period = employee.current_period
    if not period or not end_date:
        return {
            "payment_in_lieu": Decimal("0"),
            "severance": Decimal("0"),
            "long_service": Decimal("0"),
            "note": "資料不足，須由 HR 核對。",
        }
    if average_wage in {None, ""}:
        average_wage = average_wage_prefill(employee, end_date)["average"]
    average_wage = money(average_wage or 0)
    service_days = max(0, (end_date - period.start_date).days + 1)
    service_years = Decimal(service_days) / Decimal("365")
    capped_year_amount = min(average_wage * Decimal("0.6666666667"), Decimal("15000"))
    payment_in_lieu = Decimal("0")
    if reason in {"company_termination", "redundancy", "failed_probation"}:
        notice_value = parse_decimal(
            period.notice_period_value,
            Decimal("0"),
        )
        notice_unit = (period.notice_period_unit or "day").strip().lower()
        if reason != "failed_probation" or service_days > 31:
            if notice_unit in {"month", "months"}:
                payment_in_lieu = average_wage * notice_value
            else:
                notice_days = (
                    notice_value * Decimal("7")
                    if notice_unit in {"week", "weeks"}
                    else notice_value
                )
                average_daily_wage = (
                    average_wage * Decimal("12") / Decimal("365")
                )
                payment_in_lieu = average_daily_wage * notice_days
    severance = (
        capped_year_amount * service_years
        if reason == "redundancy" and service_days >= 365 * 2
        else Decimal("0")
    )
    long_service = (
        capped_year_amount * service_years
        if reason
        in {
            "company_termination",
            "contract_expiry",
            "failed_probation",
        }
        and service_days >= 365 * 5
        else Decimal("0")
    )
    return {
        "payment_in_lieu": money(payment_in_lieu),
        "severance": min(money(severance), Decimal("390000")),
        "long_service": min(money(long_service), Decimal("390000")),
        "note": (
            "只作參考估算；代通知金假設公司沒有安排員工完成通知期。"
            "平均工資、跨越 2025-05-01 的個案及實際合資格情況，"
            "必須由 HR 按合同及勞工處計算機再核對。"
        ),
    }

