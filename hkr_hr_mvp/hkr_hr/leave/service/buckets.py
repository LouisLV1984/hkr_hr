"""Annual leave and comp leave bucket calculations and allocation persistence."""
from __future__ import annotations

import calendar
from datetime import date, timedelta
from decimal import Decimal

from hkr_hr.leave.models import (
    EmployeeAnnualLeaveAllocation,
    EmployeeAnnualLeaveBalance,
    EmployeeAnnualLeaveRecord,
    EmployeeCompLeaveAllocation,
    EmployeeCompLeaveCredit,
)
from hkr_hr.leave.rules.entitlement import (
    annual_leave_expiry,
    statutory_annual_leave_days,
)
from hkr_hr.platform.db import db


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
        from hkr_hr.leave.rules.entitlement import freeze_balance
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
    from hkr_hr.leave.rules.entitlement import active_for, entitlement, annual_rate
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


