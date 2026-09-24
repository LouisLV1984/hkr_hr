"""Explicit, transactional leave-day review; never edits attendance inputs."""
from decimal import Decimal
import hashlib
import json

from flask import current_app
from itsdangerous import URLSafeTimedSerializer, BadData

from models import (db, Employee, EmployeeAnnualLeaveRecord, PayrollRun,
                    PayrollEmployeeResult, EmployeeFinalPaymentCase)
from tools.attendance_policy import leave_day_units, saved_leave_units
from tools.hr_core import clear_leave_allocations, allocate_annual_leave_with_comp, write_audit


def review_rows(employee_id=None):
    query = EmployeeAnnualLeaveRecord.query.filter_by(status="active")
    if employee_id:
        query = query.filter_by(employee_id=employee_id)
    records = query.order_by(EmployeeAnnualLeaveRecord.employee_id,
                             EmployeeAnnualLeaveRecord.leave_date,
                             EmployeeAnnualLeaveRecord.id).all()
    rows = []
    for record in records:
        row = dict(record=record, new_days=None, delta=None, excluded=[], error=None, units=None)
        try:
            units = leave_day_units(record.employee, record.leave_date,
                                   record.end_date or record.leave_date,
                                   record.start_session, record.end_session)
            row.update(units={d.isoformat(): str(v) for d, v in units.items()},
                       new_days=sum(units.values(), Decimal("0")),
                       excluded=[d.isoformat() for d, v in units.items() if not v])
            row["delta"] = row["new_days"] - record.days
            if not row["delta"] and units == saved_leave_units(record):
                continue
        except ValueError as exc:
            row["error"] = str(exc)
        rows.append(row)
    return rows, len(records)


def leave_state(record):
    return dict(start_date=record.leave_date.isoformat(),
                end_date=(record.end_date or record.leave_date).isoformat(),
                start_session=record.start_session, end_session=record.end_session,
                days=str(record.days), leave_type=record.leave_type, status=record.status,
                entitlement_year=record.entitlement_year, leave_units_json=record.leave_units_json,
                evidence_document_id=record.evidence_document_id, remarks=record.remarks)


def fingerprint(row):
    payload = dict(record=leave_state(row["record"]), proposed=row["units"],
                   updated_at=str(row["record"].updated_at))
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def signer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="leave-day-review-v1")


def review_token(rows, user_id):
    return signer().dumps(dict(user_id=user_id, records={str(r["record"].id): fingerprint(r)
                          for r in rows if not r["error"] and r["new_days"] > 0}))


def payroll_targets(records):
    """Include later saved months: prior forecasts and wage averages can propagate."""
    first_month = {}
    for record in records:
        month = record.leave_date.strftime("%Y-%m")
        first_month[record.employee_id] = min(first_month.get(record.employee_id, month), month)
    if not first_month:
        return [], []
    results = (PayrollEmployeeResult.query.join(PayrollRun)
               .filter(PayrollEmployeeResult.employee_id.in_(first_month))
               .order_by(PayrollRun.year_month, PayrollRun.created_at, PayrollRun.id,
                         PayrollEmployeeResult.id).all())
    latest = {}
    for result in results:
        if result.run.year_month >= first_month[result.employee_id]:
            latest[result.employee_id, result.run.year_month] = result
    cases = (EmployeeFinalPaymentCase.query.filter(
        EmployeeFinalPaymentCase.employee_id.in_(first_month),
        EmployeeFinalPaymentCase.status == "active").order_by(EmployeeFinalPaymentCase.id).all())
    cases = [c for c in cases if c.employment_period.end_date
             and c.employment_period.end_date.strftime("%Y-%m") >= first_month[c.employee_id]]
    return sorted(latest.values(), key=lambda r: (r.run.year_month, r.employee_id)), cases


def payroll_values(row):
    keys = ("gross_amount", "net_amount", "employee_mpf", "employer_mpf", "sick_leave_amount",
            "unpaid_leave_deduction", "annual_leave_days", "sick_leave_days", "unpaid_leave_days",
            "annual_leave_pay", "annual_leave_overuse_deduction", "legacy_leave_days", "post_2024_leave_days")
    return {key: str(row[key]) for key in keys if key in row}


def apply_review(raw_ids, token, user_id, employee_id=None):
    """Caller owns commit/rollback. Validate entire selection before any writes."""
    from tools.absence_integrity import conflicting_absence
    from tools.final_payment import calculate_final_payment, leave_defaults
    from tools.payroll_engine import calculate_employee, snapshot_payroll

    try:
        signed = signer().loads(token, max_age=3600)
        ids = {int(value) for value in raw_ids}
        if not ids or len(ids) != len(raw_ids) or signed["user_id"] != user_id:
            raise ValueError
    except (BadData, ValueError, TypeError, KeyError):
        raise ValueError("leave.review_invalid") from None
    records = EmployeeAnnualLeaveRecord.query.filter(EmployeeAnnualLeaveRecord.id.in_(ids)).all()
    if len(records) != len(ids) or (employee_id and any(r.employee_id != employee_id for r in records)):
        raise ValueError("leave.review_invalid")
    # Coordinate with normal absence writes and competing review submissions.
    employee_ids = sorted({r.employee_id for r in records})
    db.session.execute(db.select(Employee.id).where(Employee.id.in_(employee_ids))
                       .order_by(Employee.id).with_for_update()).all()
    db.session.expire_all()
    rows = []
    for eid in employee_ids:
        candidates, _ = review_rows(eid)
        rows.extend(r for r in candidates if r["record"].id in ids)
    if len(rows) != len(ids):
        raise ValueError("leave.review_stale")
    for row in rows:
        record = row["record"]
        if (row["error"] or not row["new_days"] or
                signed["records"].get(str(record.id)) != fingerprint(row)):
            raise ValueError("leave.review_stale")
        if conflicting_absence(record.employee, record.leave_date, record.end_date or record.leave_date,
                               record.start_session, record.end_session, exclude=("leave", record.id)):
            raise ValueError("leave.overlap")

    records = [r["record"] for r in rows]
    targets, cases = payroll_targets(records)
    final_before = {c.id: (leave_defaults(c.employment_period)[:2],
                           payroll_values(calculate_final_payment(c.employment_period))) for c in cases}
    old = {r.id: leave_state(r) for r in records}
    # Release all selected allocations before allocating again in date order.
    for record in records:
        clear_leave_allocations(record)
    for row in sorted(rows, key=lambda r: (r["record"].leave_date, r["record"].id)):
        record = row["record"]
        record.days = row["new_days"]
        record.leave_units_json = row["units"]
        if record.leave_type == "annual":
            try:
                allocate_annual_leave_with_comp(record, as_of=record.leave_date)
            except ValueError:
                raise ValueError("假期結餘不足，請核對補休及年假可用日數。") from None
        write_audit("leave_corrected", "EmployeeAnnualLeaveRecord", record.id,
                    employee_id=record.employee_id, detail="按工作制確認更新假期日數（保留日期、憑證及備註）",
                    before=old[record.id], after=leave_state(record))
    db.session.flush()

    runs = []
    for previous in targets:
        employee = previous.employee
        month = previous.run.year_month
        # Departure wages belong to Final Payment; never create an ordinary duplicate.
        if any(p.end_date and p.end_date.strftime("%Y-%m") == month
               for p in employee.employment_periods):
            continue
        calculated = calculate_employee(employee, month)
        if calculated["blockers"]:
            raise ValueError(f'{employee.employee_no} · {month}: ' + "、".join(calculated["blockers"]))
        run = snapshot_payroll(month, calculated["group"], [calculated], user_id, commit=False)
        db.session.flush()
        write_audit("payroll_leave_recalculated", "PayrollRun", run.id,
                    employee_id=employee.id, detail=f"{month} / 假期日數確認更新",
                    before=dict(run_id=previous.run_id, result_id=previous.id,
                                **{k: str(getattr(previous, k)) for k in ("gross_amount", "net_amount", "employee_mpf", "employer_mpf")}),
                    after=dict(run_id=run.id, leave_record_ids=sorted(ids), **payroll_values(calculated)))
        runs.append(run)

    for case in cases:
        defaults_before, values_before = final_before[case.id]
        defaults_after = leave_defaults(case.employment_period)[:2]
        # Preserve a manual adjustment relative to the old balance, not a stale absolute balance.
        for field, before, after in zip(("legacy_leave_days", "post_2024_leave_days"), defaults_before, defaults_after):
            value = getattr(case, field)
            if value is not None:
                updated = value + after - before
                if updated < 0:
                    raise ValueError("leave.review_final_negative")
                setattr(case, field, updated)
        case.updated_by = user_id
        result = calculate_final_payment(case.employment_period)
        if result["blockers"]:
            raise ValueError(f'{case.employee.employee_no} · {case.settlement_month}: ' + "、".join(result["blockers"]))
        write_audit("final_payment_leave_recalculated", "EmployeeFinalPaymentCase", case.id,
                    employee_id=case.employee_id, detail="假期更新：同步年假補薪日數及離職 Payroll／MPF",
                    before=values_before, after=dict(leave_record_ids=sorted(ids), **payroll_values(result)))
    db.session.flush()
    return dict(leaves=len(records), payroll=len(runs), final=len(cases))
