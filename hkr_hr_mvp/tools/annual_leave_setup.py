"""Transactional setup/recalculation previews with stale-state protection."""
from datetime import date
from decimal import Decimal
from itsdangerous import URLSafeSerializer, BadSignature
from flask import current_app
from models import db, EmployeeEmploymentPeriod
from tools.annual_leave_policy import entitlement, save_current_balance
from tools.hr_core import annual_leave_summary, write_audit


def canonical_state(value):
    """Relationship loading order and numeric display scale are not HR edits."""
    result = dict(value)
    numeric_fields = {"periods": (3,), "balances": (2, 3, 4, 6, 8), "records": (3,)}
    for name, indexes in numeric_fields.items():
        rows = []
        for item in value.get(name, []):
            row = list(item)
            for index in indexes:
                if index >= len(row):
                    continue
                number = row[index]
                row[index] = None if number is None or number == "None" else format(Decimal(str(number)).normalize(), "f")
            rows.append(row)
        result[name] = sorted(rows, key=lambda row: row[0])
    return result


def state(employee):
    period = employee.current_period
    return canonical_state({
        "employee": employee.id,
        "period": period.id if period else None,
        "periods": [(p.id, str(p.start_date), str(p.end_date), str(p.contract_annual_leave_days),
                     p.annual_leave_policy_year, p.annual_leave_contract_verified) for p in employee.employment_periods],
        "balances": [(b.id, b.year, str(b.entitled_days_override), str(b.calculated_entitled_days),
                       str(b.manual_adjustment_days), str(b.extended_until), str(b.carried_from_previous_days),
                       str(b.expiry_date), str(b.calculated_annual_rate), str(b.calculation_start_date)) for b in employee.annual_leave_balances],
        "records": [(r.id, str(r.updated_at), r.status, str(r.days)) for r in employee.annual_leave_records],
        "year": date.today().year,
    })


def token(employee):
    return URLSafeSerializer(current_app.secret_key, salt="annual-leave-setup").dumps(state(employee))


def validate(start, initial, end=None):
    if not start or initial is None or not initial.is_finite() or not 7 <= initial <= 14 or initial % Decimal("0.5"):
        raise ValueError("leave.setup_invalid")
    if end and start > end:
        raise ValueError("leave.setup_invalid")


def date_change_required(employee, start):
    period = employee.current_period
    return bool(period and period.annual_leave_policy_year is not None and period.start_date != start)


def validate_date_choice(employee, start, action):
    if date_change_required(employee, start) and action not in {"recalculate", "keep_current"}:
        raise ValueError("leave.date_choice_required")


def preview(employee, start, initial, preserve=True, date_action=None):
    period = employee.current_period
    validate(start, initial, period.end_date if period else None)
    year = date.today().year
    if period and period.end_date and period.end_date < date(year, 1, 1):
        raise ValueError("leave.setup_invalid")
    old = annual_leave_summary(employee, year)
    new = entitlement(start, initial, year) or Decimal(0)
    if period and period.end_date:
        new = entitlement(start, initial, year, period.end_date)
    changed = date_change_required(employee, start)
    kept = (date_action == "keep_current" if changed and date_action else
            preserve and old["entitled_override"] is not None)
    if changed and date_action == "recalculate":
        kept = False
    applied = old["entitled"] if kept else new
    return {"year": year, "old": str(old["entitled"]), "calculated": str(new),
            "applied": str(applied), "used": str(old["bucket_used"]),
            "remaining": str(applied + old["carried"] + old["manual"] - old["bucket_used"]),
            "preserved": kept, "date_changed": changed}


def apply(employee, start, initial, preserve, signed_token, date_action=None):
    try:
        expected = URLSafeSerializer(current_app.secret_key, salt="annual-leave-setup").loads(signed_token)
    except BadSignature:
        raise ValueError("leave.setup_stale")
    # Lock the employee anchor so concurrent setup saves cannot both pass.
    from models import Employee
    db.session.query(Employee).filter_by(id=employee.id).with_for_update().one()
    db.session.expire_all()
    if canonical_state(expected) != state(employee):
        raise ValueError("leave.setup_stale")
    validate_date_choice(employee, start, date_action)
    result = preview(employee, start, initial, preserve, date_action)
    period = employee.current_period
    if any(p != period and (p.end_date is None or p.end_date >= start)
           for p in employee.employment_periods):
        raise ValueError("leave.setup_overlap")
    before = {"start_date": str(period.start_date) if period else None,
              "initial_days": str(period.contract_annual_leave_days) if period else None,
              "entitled": result["old"]}
    if not period:
        period = EmployeeEmploymentPeriod(employee=employee, start_date=start)
        db.session.add(period)
        db.session.flush()
    period.start_date = start
    if period.contract_annual_leave_days != initial:
        period.annual_leave_contract_verified = False
    period.contract_annual_leave_days = initial
    period.annual_leave_policy_year = period.annual_leave_policy_year or date.today().year
    balance = save_current_balance(employee)
    if result["date_changed"] and date_action == "keep_current":
        balance.entitled_days_override = Decimal(result["old"])
    elif not preserve or (result["date_changed"] and date_action == "recalculate"):
        balance.entitled_days_override = None
    db.session.flush()
    after = {"start_date": str(start), "initial_days": str(initial), "date_change_action": date_action, **result}
    write_audit("annual_leave_balance_updated", "EmployeeAnnualLeaveBalance", balance.id,
                employee_id=employee.id, detail=f"{date.today().year} 年年假計算設定及重算",
                before=before, after=after)
    # Departure results are live; exported snapshots remain evidence requiring re-export.
    return result
