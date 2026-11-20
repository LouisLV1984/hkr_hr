"""Pure annual leave entitlement and statutory leave formulas (zero Flask/DB)."""
from __future__ import annotations

import calendar
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from hkr_hr.platform.dates import annual_leave_days_between


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
    return Decimal(str(min(14, 7 + (service_years - 2))))


def annual_leave_expiry(balance):
    if balance.year <= 2023:
        return None
    return (
        balance.extended_until
        or balance.expiry_date
        or date(balance.year + 1, 3, 31)
    )


def annual_rate(start_date, initial_days, year):
    if not start_date or initial_days is None or year < start_date.year:
        return None
    initial = Decimal(str(initial_days))
    elapsed = year - start_date.year
    if initial == 7:
        return min(Decimal(14), initial + max(0, elapsed - 1))
    return min(Decimal(14), initial + elapsed)


def entitlement(start_date, initial_days, year, end_date=None):
    rate = annual_rate(start_date, initial_days, year)
    if rate is None:
        return None
    first = max(start_date, date(year, 1, 1))
    last = min(end_date or date(year, 12, 31), date(year, 12, 31))
    days = max(0, (last - first).days + 1)
    raw = rate * Decimal(days) / Decimal(366 if calendar.isleap(year) else 365)
    # Settlement must use the unrounded earning, not a second fraction of
    # the already prorated/rounded first-year allocation.
    return (
        raw
        if end_date is not None
        else (raw * 2).quantize(Decimal(1), rounding=ROUND_HALF_UP) / 2
    )


def active_for(period, year):
    return bool(
        period
        and period.annual_leave_policy_year is not None
        and year >= period.annual_leave_policy_year
    )


def freeze_balance(employee, balance):
    period = employee.current_period
    if not active_for(period, balance.year):
        return
    balance.calculated_entitled_days = (
        entitlement(period.start_date, period.contract_annual_leave_days, balance.year)
        or Decimal(0)
    )
    balance.calculated_annual_rate = (
        annual_rate(period.start_date, period.contract_annual_leave_days, balance.year)
        or Decimal(0)
    )
    balance.calculation_start_date = period.start_date


__all__ = [
    "active_for",
    "annual_leave_days_between",
    "annual_leave_expiry",
    "annual_rate",
    "entitlement",
    "freeze_balance",
    "statutory_annual_leave_days",
]
