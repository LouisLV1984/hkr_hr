"""Company calendar-year advance leave, activated by an explicit HR save."""
import calendar
from datetime import date
from decimal import Decimal, ROUND_HALF_UP


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
    return raw if end_date is not None else (raw * 2).quantize(Decimal(1), rounding=ROUND_HALF_UP) / 2


def active_for(period, year):
    return bool(period and period.annual_leave_policy_year is not None
                and year >= period.annual_leave_policy_year)


def freeze_balance(employee, balance):
    period = employee.current_period
    if not active_for(period, balance.year):
        return
    balance.calculated_entitled_days = entitlement(period.start_date, period.contract_annual_leave_days, balance.year) or Decimal(0)
    balance.calculated_annual_rate = annual_rate(period.start_date, period.contract_annual_leave_days, balance.year) or Decimal(0)
    balance.calculation_start_date = period.start_date


def save_current_balance(employee):
    from tools.hr_core import ensure_annual_leave_balance
    balance = ensure_annual_leave_balance(employee, date.today().year)
    freeze_balance(employee, balance)
    return balance


def rollover():
    """Catch up the current year on use, including after a January shutdown.

    Only HR-activated periods participate. Employee locks serialize workers;
    never overwrite an existing annual account or synthesize historic years.
    """
    from models import Employee, EmployeeEmploymentPeriod, EmployeeAnnualLeaveBalance, db
    from tools.hr_core import write_audit
    year = date.today().year
    periods = EmployeeEmploymentPeriod.query.filter(
        EmployeeEmploymentPeriod.annual_leave_policy_year.isnot(None),
        EmployeeEmploymentPeriod.annual_leave_policy_year < year,
        EmployeeEmploymentPeriod.start_date <= date.today(),
        db.or_(EmployeeEmploymentPeriod.end_date.is_(None), EmployeeEmploymentPeriod.end_date >= date.today()),
        ~db.exists().where(db.and_(EmployeeAnnualLeaveBalance.employee_id == EmployeeEmploymentPeriod.employee_id,
                                 EmployeeAnnualLeaveBalance.year == year)),
    ).all()
    for period in periods:
        employee = db.session.query(Employee).filter_by(id=period.employee_id).with_for_update().one()
        if EmployeeAnnualLeaveBalance.query.filter_by(employee_id=employee.id, year=year).first():
            continue
        balance = save_current_balance(employee)
        write_audit("annual_leave_balance_updated", "EmployeeAnnualLeaveBalance", balance.id,
                    employee_id=employee.id, detail=f"自動配置 {year} 年年假",
                    after={"year": year, "applied": str(balance.calculated_entitled_days), "automatic": True})
    if periods:
        db.session.commit()
