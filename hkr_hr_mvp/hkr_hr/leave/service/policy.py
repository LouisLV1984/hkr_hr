"""Company calendar-year advance annual leave persistence and automatic rollover."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from hkr_hr.employees.api import Employee, EmployeeEmploymentPeriod
from hkr_hr.leave.models import EmployeeAnnualLeaveBalance
from hkr_hr.leave.rules.entitlement import active_for, annual_rate, entitlement
from hkr_hr.leave.service.buckets import ensure_annual_leave_balance
from hkr_hr.platform.audit import write_audit
from hkr_hr.platform.db import db


def freeze_balance(employee, balance):
    period = employee.current_period
    if not active_for(period, balance.year):
        return
    balance.calculated_entitled_days = entitlement(
        period.start_date, period.contract_annual_leave_days, balance.year
    ) or Decimal(0)
    balance.calculated_annual_rate = annual_rate(
        period.start_date, period.contract_annual_leave_days, balance.year
    ) or Decimal(0)
    balance.calculation_start_date = period.start_date


def save_current_balance(employee):
    balance = ensure_annual_leave_balance(employee, date.today().year)
    freeze_balance(employee, balance)
    return balance


def rollover():
    """Catch up the current year on use, including after a January shutdown."""
    year = date.today().year
    periods = EmployeeEmploymentPeriod.query.filter(
        EmployeeEmploymentPeriod.annual_leave_policy_year.isnot(None),
        EmployeeEmploymentPeriod.annual_leave_policy_year < year,
        EmployeeEmploymentPeriod.start_date <= date.today(),
        db.or_(
            EmployeeEmploymentPeriod.end_date.is_(None),
            EmployeeEmploymentPeriod.end_date >= date.today(),
        ),
        ~db.exists().where(
            db.and_(
                EmployeeAnnualLeaveBalance.employee_id == EmployeeEmploymentPeriod.employee_id,
                EmployeeAnnualLeaveBalance.year == year,
            )
        ),
    ).all()
    for period in periods:
        employee = db.session.query(Employee).filter_by(id=period.employee_id).with_for_update().one()
        if EmployeeAnnualLeaveBalance.query.filter_by(employee_id=employee.id, year=year).first():
            continue
        balance = save_current_balance(employee)
        write_audit(
            "annual_leave_balance_updated",
            "EmployeeAnnualLeaveBalance",
            balance.id,
            employee_id=employee.id,
            detail=f"自動配置 {year} 年年假",
            after={"year": year, "applied": str(balance.calculated_entitled_days), "automatic": True},
        )
    if periods:
        db.session.commit()
