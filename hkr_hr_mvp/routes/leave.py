from datetime import date, datetime
from decimal import Decimal

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for, jsonify, session
from flask_login import current_user, login_required
from sqlalchemy import or_

from models import (
    AuditLog,
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
from tools.datetime_utils import hong_kong_datetime


leave_bp = Blueprint("leave", __name__)


@leave_bp.get("/annual-leave/day-review")
@login_required
def leave_day_review():
    from tools.leave_review import review_rows, review_token, payroll_targets
    employee_id = request.args.get("employee_id", type=int)
    employee = db.get_or_404(Employee, employee_id) if employee_id else None
    rows, total = review_rows(employee_id)
    for row in rows:
        targets, cases = payroll_targets([row["record"]])
        row["snapshots"] = sorted({r.run.year_month for r in targets})
        row["final_months"] = sorted({c.settlement_month for c in cases})
    return render_template("leave/day_review.html", rows=rows, total=total, employee=employee,
                           review_token=review_token(rows, current_user.id))


@leave_bp.post("/annual-leave/day-review/apply")
@login_required
def apply_leave_day_review():
    from tools.leave_review import apply_review
    from tools.i18n import TRANSLATIONS, normalize_language
    messages = TRANSLATIONS[normalize_language(session.get("lang"))]
    translate = lambda key: messages.get(key, key)
    employee_id = request.form.get("employee_id", type=int)
    try:
        if request.form.get("acknowledge") != "on":
            raise ValueError("leave.review_invalid")
        result = apply_review(request.form.getlist("record_ids"), request.form.get("review_token", ""),
                              current_user.id, employee_id)
        db.session.commit()
    except ValueError as exc:
        db.session.rollback()
        flash(translate("leave.review_failed") + " " + translate(str(exc)), "error")
    else:
        flash(translate("leave.review_done").format(**result), "success")
    return redirect(url_for("leave.leave_day_review", employee_id=employee_id))


@leave_bp.get("/employees/<int:employee_id>/leave-day-preview")
@login_required
def leave_day_preview(employee_id):
    from tools.attendance_policy import leave_day_units, leave_context_text
    from tools.i18n import TRANSLATIONS, normalize_language
    employee = db.get_or_404(Employee, employee_id)
    try:
        units = leave_day_units(employee, parse_date(request.args.get("start_date")),
                               parse_date(request.args.get("end_date")),
                               request.args.get("start_session", "am"),
                               request.args.get("end_session", "pm"))
    except ValueError as exc:
        messages = TRANSLATIONS[normalize_language(session.get("lang"))]
        return jsonify(error=messages.get(str(exc), str(exc))), 400
    days = sum(units.values(), Decimal("0"))
    return jsonify(days=str(days), excluded=[day.isoformat() for day, value in units.items() if not value],
                   context_text=leave_context_text(employee, min(units), max(units), session.get("lang")))


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
    allocation_sources = {}
    for record in records:
        if record.leave_type != "annual" or record.status != "active":
            continue
        sources = []
        comp_days = sum(
            (
                Decimal(str(item.days or 0))
                for item in record.comp_leave_allocations
            ),
            Decimal("0"),
        )
        if comp_days > 0:
            sources.append({"label": "補休", "days": comp_days})
        annual_by_year = {}
        for allocation in record.allocations:
            if not allocation.balance:
                continue
            bucket_year = allocation.balance.year
            annual_by_year[bucket_year] = annual_by_year.get(
                bucket_year,
                Decimal("0"),
            ) + Decimal(str(allocation.days or 0))
        for bucket_year in sorted(annual_by_year):
            sources.append(
                {
                    "label": (
                        "2023及以前"
                        if bucket_year <= 2023
                        else f"{bucket_year}年年假"
                    ),
                    "days": annual_by_year[bucket_year],
                }
            )
        explicitly_allocated = comp_days + sum(
            annual_by_year.values(),
            Decimal("0"),
        )
        fallback_days = max(
            Decimal("0"),
            Decimal(str(record.days or 0)) - explicitly_allocated,
        )
        if fallback_days > 0:
            sources.append(
                {
                    "label": (
                        "2023及以前"
                        if record.entitlement_year <= 2023
                        else f"{record.entitlement_year}年年假"
                    ),
                    "days": fallback_days,
                }
            )
        allocation_sources[record.id] = sources
    leave_history = []
    for record in records:
        changed_at = record.updated_at or record.created_at
        leave_history.append(
            {
                "kind": "leave",
                "sort_at": changed_at,
                "display_at": hong_kong_datetime(changed_at),
                "record": record,
            }
        )
    if selected:
        for credit in selected.comp_leave_credits:
            changed_at = credit.updated_at or credit.created_at
            leave_history.append(
                {
                    "kind": "comp_credit",
                    "sort_at": changed_at,
                    "display_at": hong_kong_datetime(changed_at),
                    "credit": credit,
                }
            )
        balance_audits = AuditLog.query.filter_by(
            employee_id=selected.id,
            action="annual_leave_balance_updated",
        ).order_by(AuditLog.created_at.desc()).all()
        for audit in balance_audits:
            leave_history.append(
                {
                    "kind": "balance",
                    "sort_at": audit.created_at,
                    "display_at": hong_kong_datetime(audit.created_at),
                    "audit": audit,
                }
            )
    leave_history.sort(
        key=lambda item: item["sort_at"] or datetime.min,
        reverse=True,
    )
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
        allocation_sources=allocation_sources,
        leave_history=leave_history,
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
    scope = request.form.get("scope", "all")
    if scope not in {"all", "current", "legacy"}:
        abort(400)
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
    if scope in {"all", "current"}:
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
        if year >= 2024:
            default_expiry = date(year + 1, 3, 31)
            extension = parse_date(request.form.get("extended_until"))
            if extension and extension < default_expiry:
                flash("順延到期日不可早於原到期日。", "error")
                return leave_redirect(employee.id, year)
            balance.expiry_date = default_expiry
            balance.extended_until = extension
        balance.remarks = request.form.get("remarks", "").strip() or None
    if scope in {"all", "legacy"}:
        legacy_days = parse_decimal(request.form.get("legacy_days"))
        if (
            legacy_days is None
            or legacy_days < 0
            or legacy_days % parse_decimal("0.5")
        ):
            flash("2023 年及以前的年假總額必須以 0.5 日為單位。", "error")
            return leave_redirect(employee.id, year)
        legacy_balance.entitled_days_override = legacy_days
    db.session.flush()
    write_audit(
        "annual_leave_balance_updated",
        "EmployeeAnnualLeaveBalance",
        balance.id,
        employee_id=employee.id,
        detail=(
            "更新 2023 年及以前年假總額"
            if scope == "legacy"
            else f"更新 {year} 年年假額度"
        ),
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
