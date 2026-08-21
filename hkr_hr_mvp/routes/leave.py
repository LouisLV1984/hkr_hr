from datetime import date

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import or_

from models import (
    Employee,
    EmployeeAnnualLeaveBalance,
    EmployeeAnnualLeaveRecord,
    EmployeeWorkInjuryPeriod,
    EmployeeWorkInjuryMonthlyExpense,
    WorkProject,
    db,
)
from tools.text_search import chinese_search_variants
from tools.hr_core import (
    PAYROLL_GROUPS,
    annual_leave_buckets,
    annual_leave_summary,
    comp_leave_summary,
    current_assignment_on,
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
    view = request.args.get("view", "leave")
    if view not in {"leave", "injury"}:
        view = "leave"
    year = request.args.get("year", type=int) or date.today().year
    status = request.args.get("status", "active")
    payroll_group = request.args.get("payroll_group", "").strip()
    project_id = request.args.get("project_id", type=int)
    search = request.args.get("q", "").strip()
    employees = Employee.query.order_by(Employee.employee_no.asc()).all()
    if status in {"active", "departed"}:
        employees = [
            employee
            for employee in employees
            if employee.derived_status == status
        ]
    if payroll_group:
        employees = [
            employee
            for employee in employees
            if employee.payroll_group == payroll_group
        ]
    if project_id:
        employees = [
            employee
            for employee in employees
            if (
                current_assignment_on(employee, date(year, 12, 31))
                and current_assignment_on(
                    employee, date(year, 12, 31)
                ).project_id
                == project_id
            )
        ]
    if search:
        variants = [item.casefold() for item in chinese_search_variants(search)]
        employees = [
            employee
            for employee in employees
            if any(
                variant in (value or "").casefold()
                for variant in variants
                for value in (
                    employee.employee_no,
                    employee.chinese_name,
                    employee.english_name,
                )
            )
        ]
    summaries = {
        employee.id: {
            "annual": annual_leave_summary(employee, year),
            "comp": comp_leave_summary(employee),
        }
        for employee in employees
    }
    action_filter = request.args.get("action", "")
    if action_filter == "attention":
        if view == "injury":
            employees = [
                employee
                for employee in employees
                if any(
                    item.status == "active"
                    for item in employee.work_injury_periods
                )
            ]
        else:
            employees = [
                employee
                for employee in employees
                if summaries[employee.id]["annual"]["remaining"] < 0
                or any(
                    record.status == "active"
                    and record.leave_type == "sick"
                    and not record.evidence_document_id
                    for record in employee.annual_leave_records
                )
            ]
    selected_id = request.args.get("employee_id", type=int)
    selected = next(
        (employee for employee in employees if employee.id == selected_id),
        None,
    )
    selected_summary = (
        annual_leave_summary(selected, year) if selected else None
    )
    records = (
        EmployeeAnnualLeaveRecord.query.filter(
            EmployeeAnnualLeaveRecord.employee_id == selected.id,
            EmployeeAnnualLeaveRecord.leave_date <= date(year, 12, 31),
            or_(
                EmployeeAnnualLeaveRecord.end_date.is_(None),
                EmployeeAnnualLeaveRecord.end_date >= date(year, 1, 1),
            ),
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
        annual_leave_buckets(
            selected,
            as_of=(
                selected_summary.get("termination_date")
                if selected_summary and selected_summary.get("termination_date")
                else date(year, 12, 31)
            ),
            prorate_current=bool(
                selected_summary and selected_summary.get("termination_date")
            ),
        )
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
    work_injury_periods = (
        EmployeeWorkInjuryPeriod.query.filter_by(employee_id=selected.id)
        .order_by(
            EmployeeWorkInjuryPeriod.payroll_start_date.desc(),
            EmployeeWorkInjuryPeriod.id.desc(),
        )
        .all()
        if selected
        else []
    )
    work_injury_expenses = (
        EmployeeWorkInjuryMonthlyExpense.query.filter_by(employee_id=selected.id)
        .order_by(
            EmployeeWorkInjuryMonthlyExpense.year_month.desc(),
            EmployeeWorkInjuryMonthlyExpense.id.desc(),
        )
        .all()
        if selected
        else []
    )
    return render_template(
        "leave/index.html",
        year=year,
        view=view,
        search=search,
        status=status,
        payroll_group=payroll_group,
        project_id=project_id,
        action_filter=action_filter,
        projects=WorkProject.query.filter_by(active=True).order_by(
            WorkProject.name
        ).all(),
        payroll_groups=PAYROLL_GROUPS,
        employees=employees,
        summaries=summaries,
        selected=selected,
        leave=selected_summary,
        comp_leave=comp_leave_summary(selected) if selected else None,
        records=records,
        balance=balance,
        buckets=buckets,
        allocation_splits=allocation_splits,
        work_injury_periods=work_injury_periods,
        work_injury_expenses=work_injury_expenses,
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
