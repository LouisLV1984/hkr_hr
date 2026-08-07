from datetime import date

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from models import (
    Employee,
    EmployeeAnnualLeaveBalance,
    EmployeeAnnualLeaveRecord,
    db,
)
from tools.hr_core import (
    annual_leave_buckets,
    annual_leave_summary,
    ensure_annual_leave_balance,
    parse_date,
    parse_decimal,
    write_audit,
)


leave_bp = Blueprint("leave", __name__)


def leave_redirect(employee_id, year):
    return redirect(
        url_for(
            "leave.leave_home",
            employee_id=employee_id,
            year=year,
        )
        + "#employee-leave"
    )


@leave_bp.route("/annual-leave")
@login_required
def leave_home():
    year = request.args.get("year", type=int) or date.today().year
    status = request.args.get("status", "active")
    search = request.args.get("q", "").strip().casefold()
    employees = Employee.query.order_by(Employee.employee_no.asc()).all()
    if status in {"active", "departed"}:
        employees = [
            employee
            for employee in employees
            if employee.derived_status == status
        ]
    if search:
        employees = [
            employee
            for employee in employees
            if search
            in " ".join(
                filter(
                    None,
                    (
                        employee.employee_no,
                        employee.chinese_name,
                        employee.english_name,
                    ),
                )
            ).casefold()
        ]
    summaries = {
        employee.id: annual_leave_summary(employee, year)
        for employee in employees
    }
    selected_id = request.args.get("employee_id", type=int)
    selected = next(
        (employee for employee in employees if employee.id == selected_id),
        employees[0] if employees else None,
    )
    selected_summary = (
        annual_leave_summary(selected, year) if selected else None
    )
    records = (
        EmployeeAnnualLeaveRecord.query.filter_by(
            employee_id=selected.id,
            entitlement_year=year,
        )
        .order_by(
            EmployeeAnnualLeaveRecord.leave_date.desc(),
            EmployeeAnnualLeaveRecord.id.desc(),
        )
        .all()
        if selected
        else []
    )
    balance = (
        EmployeeAnnualLeaveBalance.query.filter_by(
            employee_id=selected.id,
            year=year,
        ).first()
        if selected
        else None
    )
    buckets = (
        annual_leave_buckets(selected, as_of=date(year, 12, 31))
        if selected
        else []
    )
    allocation_splits = {}
    for record in records:
        legacy = sum(
            (
                item.days
                for item in record.allocations
                if item.balance and item.balance.year <= 2023
            ),
            0,
        )
        allocation_splits[record.id] = {
            "legacy": legacy,
            "regular": record.days - legacy,
        }
    return render_template(
        "leave/index.html",
        year=year,
        status=status,
        search=request.args.get("q", "").strip(),
        employees=employees,
        summaries=summaries,
        selected=selected,
        leave=selected_summary,
        records=records,
        balance=balance,
        buckets=buckets,
        allocation_splits=allocation_splits,
        default_expiry=date(year + 1, 3, 31) if year >= 2024 else None,
    )


@leave_bp.route(
    "/annual-leave/<int:employee_id>/balance",
    methods=["POST"],
)
@login_required
def update_balance(employee_id):
    employee = db.get_or_404(Employee, employee_id)
    year = request.form.get("year", type=int) or date.today().year
    balance = ensure_annual_leave_balance(employee, year)
    legacy_balance = ensure_annual_leave_balance(employee, 2023)
    before = {
        "entitled_days_override": (
            str(balance.entitled_days_override)
            if balance.entitled_days_override is not None
            else None
        ),
        "extended_until": (
            balance.extended_until.isoformat()
            if balance.extended_until
            else None
        ),
        "legacy_days": str(legacy_balance.entitled_days_override or 0),
    }
    if request.form.get("clear_override") == "1":
        balance.entitled_days_override = None
    else:
        entitled = parse_decimal(request.form.get("entitled_days"))
        if (
            entitled is None
            or entitled < 0
            or entitled % parse_decimal("0.5")
        ):
            flash("本年應享年假必須以 0.5 日為單位。", "error")
            return leave_redirect(employee.id, year)
        balance.entitled_days_override = entitled
    legacy_days = parse_decimal(
        request.form.get("legacy_days"),
        parse_decimal("0"),
    )
    if legacy_days < 0 or legacy_days % parse_decimal("0.5"):
        flash("2023 年及以前的年假結餘必須以 0.5 日為單位。", "error")
        return leave_redirect(employee.id, year)
    legacy_balance.entitled_days_override = legacy_days
    if year >= 2024:
        default_expiry = date(year + 1, 3, 31)
        extension = parse_date(request.form.get("extended_until"))
        if extension and extension < default_expiry:
            flash("順延到期日不可早於原到期日。", "error")
            return leave_redirect(employee.id, year)
        balance.expiry_date = default_expiry
        balance.extended_until = extension
    balance.remarks = request.form.get("remarks", "").strip() or None
    db.session.flush()
    write_audit(
        "annual_leave_balance_updated",
        "EmployeeAnnualLeaveBalance",
        balance.id,
        employee_id=employee.id,
        detail=f"更新 {year} 年年假額度",
        before=before,
        after={
            "entitled_days_override": (
                str(balance.entitled_days_override)
                if balance.entitled_days_override is not None
                else None
            ),
            "extended_until": (
                balance.extended_until.isoformat()
                if balance.extended_until
                else None
            ),
            "legacy_days": str(legacy_balance.entitled_days_override or 0),
        },
    )
    db.session.commit()
    flash("年假額度已保存。", "success")
    return leave_redirect(employee.id, year)
