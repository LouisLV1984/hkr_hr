from hkr_hr.leave.api import leave_outlook
from hkr_hr.employees.api import workbench_options
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for, jsonify, session
from flask_login import current_user, login_required
from sqlalchemy import or_

from hkr_hr.platform.db import AuditLog, db
from hkr_hr.employees.api import Employee
from hkr_hr.leave.api import EmployeeAnnualLeaveBalance, EmployeeAnnualLeaveRecord, EmployeeWorkInjuryPeriod, EmployeeWorkInjuryMonthlyExpense
from hkr_hr.references.api import WorkProject
from hkr_hr.platform.search import chinese_search_variants
from hkr_hr.platform.dates import PAYROLL_GROUPS, parse_date, parse_decimal
from hkr_hr.leave.api import annual_leave_buckets, annual_leave_summary, comp_leave_summary, ensure_annual_leave_balance
from hkr_hr.employees.api import current_assignment_on
from hkr_hr.platform.audit import write_audit
from hkr_hr.platform.dates import hong_kong_datetime


from hkr_hr.leave.api import leave_setup_token as annual_setup_token

leave_bp = Blueprint("leave", __name__)


@leave_bp.get("/annual-leave/day-review")
@login_required
def leave_day_review():
    from hkr_hr.payroll.api import review_rows, review_token, payroll_targets
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
    from hkr_hr.payroll.api import apply_review
    from hkr_hr.platform.i18n import TRANSLATIONS, normalize_language
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
    from hkr_hr.attendance.api import leave_day_units, leave_context_text
    from hkr_hr.platform.i18n import TRANSLATIONS, normalize_language
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
    availability = leave_availability(employee, min(units))
    remaining = days
    deductions = []
    for source in availability["sources"]:
        used = min(remaining, source["remaining"])
        if used > 0:
            deductions.append(f'{source["label"]}: {used}')
            remaining -= used
    return jsonify(available=str(availability["total"]), projected=str(availability["total"]-days), deductions=deductions, days=str(days), excluded=[day.isoformat() for day, value in units.items() if not value],
                   context_text=leave_context_text(employee, min(units), max(units), session.get("lang")))



def leave_availability(employee, as_of):
    """Available after all registered leave; no inferred or historical reallocation."""
    from hkr_hr.leave.api import comp_leave_credit_remaining
    buckets = [b for b in annual_leave_buckets(employee, as_of=as_of, include_expired=False)
               if b["year"] <= as_of.year and b["remaining"] > 0]
    comp = sum((comp_leave_credit_remaining(c) for c in employee.comp_leave_credits
                if c.status == "active" and c.source_date <= as_of), Decimal("0"))
    sources = ([{"label": "補休", "remaining": comp, "expiry": None}] if comp else [])
    for b in sorted(buckets, key=lambda b: (not b["is_legacy"], b["expiry_date"] or date.max)):
        sources.append({"label": "2023及以前" if b["is_legacy"] else str(b["year"]), "remaining": b["remaining"],
                        "expiry": b["expiry_date"]})
    expiring = sorted((s for s in sources if s["expiry"]), key=lambda s:s["expiry"])
    return {"total": sum((s["remaining"] for s in sources), Decimal("0")),
            "sources": sources, "next_expiry": expiring[0] if expiring else None}

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
    status = request.args.get("status", "all" if view == "injury" else "active")
    payroll_group = request.args.get("payroll_group", "").strip()
    project_id = request.args.get("project_id", type=int)
    search = request.args.get("q", "").strip()
    employees = Employee.query.options(*workbench_options()).order_by(Employee.employee_no.asc()).all()
    employees_by_id = {employee.id: employee for employee in employees}
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
            "annual": annual_leave_summary(employee, year, preloaded=True),
            "comp": comp_leave_summary(employee),
            "missing_evidence": sum(1 for record in employee.annual_leave_records
                                    if record.status == "active" and record.leave_type == "sick"
                                    and not record.evidence_document_id
                                    and record.leave_date.year <= year <= (record.end_date or record.leave_date).year),
        }
        for employee in employees
    }
    action_filter = request.args.get("action", "attention" if view == "injury" and not search else "")
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
                or summaries[employee.id]["missing_evidence"]
            ]
    selected_id = request.args.get("employee_id", type=int)
    # An explicit employee link must remain usable after a future hire-date
    # correction, even when the overview defaults to currently active staff.
    selected = employees_by_id.get(selected_id)
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
    as_of = parse_date(request.args.get("as_of")) or (date.today() if year == date.today().year else date(year, 12, 31))
    availability = leave_availability(selected, as_of) if selected else None
    return render_template(
        "leave/index.html",
        as_of=as_of, availability=availability,
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
        summaries=summaries, today=date.today(), leave_people=employees_by_id.values(),
        outlook=leave_outlook(employees_by_id.values(), date.today()) if not selected and view == "leave" else {},
        selected=selected,
        leave=selected_summary,
        comp_leave=comp_leave_summary(selected) if selected else None,
        records=records,
        balance=balance,
        setup_token=annual_setup_token(selected) if selected else None,
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
    legacy_balance = (ensure_annual_leave_balance(employee, 2023) if scope in {"all", "legacy"}
                      else EmployeeAnnualLeaveBalance.query.filter_by(employee_id=employee.id, year=2023).first())
    before = {
        "entitled": str(annual_leave_summary(employee, year)["entitled"]),
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
        "legacy_days": str(legacy_balance.entitled_days_override or 0) if legacy_balance else "0",
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
            "year": 2023 if scope == "legacy" else year,
            "scope": scope,
            "applied": str(legacy_balance.entitled_days_override or 0) if scope == "legacy" else str(annual_leave_summary(employee, year)["entitled"]),
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
            "legacy_days": str(legacy_balance.entitled_days_override or 0) if legacy_balance else "0",
        },
    )
    db.session.commit()
    flash("年假額度已保存。", "success")
    return leave_redirect(employee.id, year)


@leave_bp.get("/annual-leave/entitlement-review")
@login_required
def entitlement_review():
    from hkr_hr.leave.api import preview_leave_setup as preview
    year = date.today().year
    rows = []
    for employee in Employee.query.options(*workbench_options()).order_by(Employee.employee_no).all():
        period = employee.current_period
        old = annual_leave_summary(employee, year, preloaded=True)
        ready = bool(period and period.contract_annual_leave_days is not None)
        proposed = None
        if ready:
            try:
                proposed = preview(employee, period.start_date, Decimal(str(period.contract_annual_leave_days)))
            except ValueError:
                ready = False
        audit = (AuditLog.query.filter_by(employee_id=employee.id, action="annual_leave_balance_updated")
                 .filter(AuditLog.after_json["year"].as_integer() == year)
                 .order_by(AuditLog.id.desc()).first())
        rows.append(dict(employee=employee, period=period, old=old, proposed=proposed, ready=ready,
                         audit=audit if audit and audit.after_json and audit.after_json.get("year") == year else None))
    return render_template("leave/entitlement_review.html", rows=rows, year=year)


@leave_bp.get("/employees/<int:employee_id>/annual-leave-setup-preview")
@login_required
def annual_leave_setup_preview(employee_id):
    from hkr_hr.leave.api import preview_leave_setup as preview
    employee = db.get_or_404(Employee, employee_id)
    try:
        result = preview(employee, parse_date(request.args.get("start_date")),
                         parse_decimal(request.args.get("initial_days")), request.args.get("preserve") != "0",
                         request.args.get("date_change_action"))
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    return jsonify(result)


@leave_bp.post("/employees/<int:employee_id>/annual-leave-setup")
@login_required
def annual_leave_setup(employee_id):
    from hkr_hr.leave.api import apply_leave_setup as apply
    from hkr_hr.platform.i18n import TRANSLATIONS, normalize_language
    messages = TRANSLATIONS[normalize_language(session.get("lang"))]
    employee = db.get_or_404(Employee, employee_id)
    try:
        result = apply(employee, parse_date(request.form.get("start_date")),
                       parse_decimal(request.form.get("initial_days")), request.form.get("preserve") != "0",
                       request.form.get("setup_token", ""), request.form.get("date_change_action"))
        db.session.commit()
    except ValueError as exc:
        db.session.rollback()
        flash(messages.get(str(exc), str(exc)), "error")
    else:
        flash(messages["leave.setup_saved"], "success")
    return leave_redirect(employee.id, date.today().year)


@leave_bp.get("/employees/<int:employee_id>/termination-leave-preview")
@login_required
def termination_leave_preview(employee_id):
    from hkr_hr.payroll.api import leave_defaults, payroll_average
    from hkr_hr.payroll.api import EmployeeFinalPaymentCase
    from hkr_hr.leave.api import annual_leave_buckets
    employee = db.get_or_404(Employee, employee_id)
    period = employee.current_period
    end = parse_date(request.args.get("end_date"))
    if not period or not end or end < period.start_date:
        return jsonify(error="leave.setup_invalid"), 400
    original_end = period.end_date
    try:
        with db.session.no_autoflush:
            period.end_date = end
            summary = annual_leave_summary(employee, end.year)
            legacy, regular, overused, buckets = leave_defaults(period)
            case = EmployeeFinalPaymentCase.query.filter_by(employment_period_id=period.id).first()
            rate = case.leave_daily_rate_override if case else None
            total = case.leave_wage_total if case else None
            if rate is None:
                if total is None:
                    _, candidate, count, _ = payroll_average(employee, end)
                    total = candidate if count == 12 else None
                rate = Decimal(str(total)) / 365 if total and total > 0 else None
            return jsonify(entitled=str(summary["entitled"]), used=str(summary["bucket_used"]),
                           overused=str(overused), offset=str(max(Decimal(0), summary["bucket_used"] - summary["entitled"] - overused)),
                           rate=str(rate) if rate is not None else None,
                           deduction=str((overused * Decimal(str(rate))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)) if rate is not None and rate > 0 else None,
                           pending=summary["calculation_pending"])
    finally:
        period.end_date = original_end
