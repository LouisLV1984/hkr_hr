"""Employee workspace routes: leave_actions."""
from hkr_hr.workbench.web.employees.common import *  # noqa: F401, F403


@employees_bp.route("/annual-leave/<int:record_id>/evidence", methods=["POST"])
@login_required
def supplement_leave_evidence(record_id):
    record = db.get_or_404(EmployeeAnnualLeaveRecord, record_id)
    if record.status != "active":
        abort(400)
    uploaded = request.files.get("evidence")
    if not uploaded or not uploaded.filename:
        flash("profile.select_evidence", "error")
        return annual_leave_redirect(record.employee_id, record.entitlement_year)
    before = {"evidence_document_id": record.evidence_document_id}
    document = replace_record_evidence(record.employee, record.evidence_document,
                                       uploaded, "change_evidence", "假期憑證")
    if not document:
        return annual_leave_redirect(record.employee_id, record.entitlement_year)
    record.evidence_document_id = document.id
    # Payroll uses the leave revision time to decide whether attendance needs
    # another review. The document and audit carry the time of this upload.
    record.updated_at = EmployeeAnnualLeaveRecord.updated_at
    write_audit("leave_evidence_added", "EmployeeAnnualLeaveRecord", record.id,
                employee_id=record.employee_id, detail="補交假期憑證（不改動假期日期及日數）",
                before=before, after={"evidence_document_id": document.id})
    db.session.commit()
    flash("profile.evidence_saved", "success")
    return annual_leave_redirect(record.employee_id, record.entitlement_year)


@employees_bp.route("/employees/<int:employee_id>/annual-leave", methods=["POST"])
@login_required
def add_annual_leave(employee_id):
    from hkr_hr.attendance.api import leave_day_units
    employee = db.get_or_404(Employee, employee_id)
    leave_type = request.form.get("leave_type", "annual").strip()
    if leave_type not in {"annual", "sick", "unpaid"}:
        leave_type = "annual"
    leave_date = parse_date(
        request.form.get("start_date") or request.form.get("leave_date")
    )
    end_date = parse_date(request.form.get("end_date")) or leave_date
    start_session = request.form.get("start_session") or "am"
    end_session = request.form.get("end_session") or "pm"
    try:
        units = leave_day_units(employee, leave_date, end_date, start_session, end_session)
    except ValueError as exc:
        flash(str(exc), "error")
        return annual_leave_redirect(employee.id, request.form.get("entitlement_year", type=int))
    calculated_days = sum(units.values(), parse_decimal("0"))
    if not calculated_days:
        flash("leave.zero_days", "error")
        return annual_leave_redirect(employee.id, leave_date.year)
    manual_days = parse_decimal(request.form.get("days"))
    days = calculated_days
    if (
        (manual_days is not None and manual_days != calculated_days)
        or not leave_date
        or not calculated_days
        or not days
        or days < parse_decimal("0.5")
        or days % parse_decimal("0.5")
    ):
        flash("請填寫正確的請假起止日期；日數以 0.5 日為單位。", "error")
        return annual_leave_redirect(
            employee.id,
            request.form.get("entitlement_year", type=int),
        )
    if conflicting_absence(employee, leave_date, end_date, start_session, end_session):
        flash("leave.overlap", "error")
        return annual_leave_redirect(employee.id, leave_date.year)
    evidence = save_evidence(employee, request.files.get("evidence"), "change_evidence",
                             {"annual": "年假憑證", "sick": "病假憑證", "unpaid": "無薪假憑證"}[leave_type])
    record = EmployeeAnnualLeaveRecord(
        employee=employee,
        leave_date=leave_date,
        end_date=end_date,
        start_session=start_session,
        end_session=end_session,
        entitlement_year=request.form.get("entitlement_year", type=int)
        or leave_date.year,
        days=days,
        leave_units_json={day.isoformat(): str(value) for day, value in units.items()},
        leave_type=leave_type,
        evidence_document=evidence,
        status="active",
        remarks=request.form.get("remarks", "").strip() or None,
        created_by=current_user.id,
    )
    db.session.add(record)
    db.session.flush()
    entitlement_year = record.entitlement_year
    if leave_type == "annual":
        try:
            allocate_annual_leave_with_comp(record, as_of=leave_date)
        except ValueError:
            db.session.rollback()
            flash("假期結餘不足，請核對補休及年假可用日數。", "error")
            return annual_leave_redirect(employee.id, entitlement_year)
    write_audit(
        "leave_added",
        "EmployeeAnnualLeaveRecord",
        record.id,
        employee_id=employee.id,
        detail=(
            f"{leave_type}: {leave_date:%Y-%m-%d} 至 {end_date:%Y-%m-%d} "
            f"{days} 日"
        ),
    )
    db.session.commit()
    flash("請假記錄已新增。", "success")
    return annual_leave_redirect(employee.id, record.entitlement_year)


@employees_bp.route(
    "/annual-leave/<int:record_id>/update",
    methods=["POST"],
)
@login_required
def update_annual_leave(record_id):
    from hkr_hr.attendance.api import leave_day_units
    record = db.get_or_404(EmployeeAnnualLeaveRecord, record_id)
    employee_id = record.employee_id
    before = {
        "leave_type": record.leave_type,
        "start_date": record.leave_date.isoformat(),
        "end_date": (
            (record.end_date or record.leave_date).isoformat()
        ),
        "start_session": record.start_session,
        "end_session": record.end_session,
        "days": str(record.days),
        "leave_units_json": record.leave_units_json,
        "entitlement_year": record.entitlement_year,
        "status": record.status,
    }
    start_date = parse_date(request.form.get("start_date"))
    leave_type = request.form.get("leave_type", record.leave_type).strip()
    if leave_type not in {"annual", "sick", "unpaid"}:
        leave_type = record.leave_type
    end_date = parse_date(request.form.get("end_date")) or start_date
    start_session = request.form.get("start_session") or "am"
    end_session = request.form.get("end_session") or "pm"
    try:
        units = leave_day_units(record.employee, start_date, end_date, start_session, end_session)
    except ValueError as exc:
        flash(str(exc), "error")
        return annual_leave_redirect(employee_id, request.form.get("entitlement_year", type=int))
    calculated = sum(units.values(), parse_decimal("0"))
    if not calculated:
        flash("leave.zero_days", "error")
        return annual_leave_redirect(employee_id, start_date.year)
    manual = parse_decimal(request.form.get("days"))
    days = calculated
    if (
        (manual is not None and manual != calculated)
        or not calculated
        or not days
        or days < parse_decimal("0.5")
        or days % parse_decimal("0.5")
    ):
        flash("請填寫正確的請假起止日期；日數以 0.5 日為單位。", "error")
        return annual_leave_redirect(
            record.employee_id,
            request.form.get("entitlement_year", type=int),
        )
    if conflicting_absence(record.employee, start_date, end_date, start_session, end_session,
                           exclude=("leave", record.id)):
        flash("leave.overlap", "error")
        return annual_leave_redirect(employee_id, start_date.year)
    record.leave_date = start_date
    record.end_date = end_date
    record.start_session = start_session
    record.end_session = end_session
    record.days = days
    record.leave_units_json = {day.isoformat(): str(value) for day, value in units.items()}
    record.leave_type = leave_type
    record.entitlement_year = (
        request.form.get("entitlement_year", type=int) or start_date.year
    )
    record.remarks = request.form.get("remarks", "").strip() or None
    record.status = "active"
    evidence = save_evidence(
        record.employee,
        request.files.get("evidence"),
        "change_evidence",
        "請假憑證",
    )
    if evidence:
        record.evidence_document = evidence
    clear_leave_allocations(record)
    if leave_type == "annual":
        try:
            allocate_annual_leave_with_comp(record, as_of=start_date)
        except ValueError:
            db.session.rollback()
            flash("假期結餘不足，請核對補休及年假可用日數。", "error")
            return annual_leave_redirect(
                employee_id,
                request.form.get("entitlement_year", type=int),
            )
    write_audit(
        "leave_corrected",
        "EmployeeAnnualLeaveRecord",
        record.id,
        employee_id=record.employee_id,
        detail=f"{start_date:%Y-%m-%d} 至 {end_date:%Y-%m-%d}，{days} 日",
        before=before,
        after={
            "leave_type": record.leave_type,
            "start_date": record.leave_date.isoformat(),
            "end_date": (record.end_date or record.leave_date).isoformat(),
            "start_session": record.start_session,
            "end_session": record.end_session,
            "days": str(record.days),
            "leave_units_json": record.leave_units_json,
            "entitlement_year": record.entitlement_year,
            "status": record.status,
        },
    )
    db.session.commit()
    flash("請假記錄已更正。", "success")
    return annual_leave_redirect(record.employee_id, record.entitlement_year)


@employees_bp.route(
    "/annual-leave/<int:record_id>/void",
    methods=["POST"],
)
@login_required
def void_annual_leave(record_id):
    record = db.get_or_404(EmployeeAnnualLeaveRecord, record_id)
    before = {"status": record.status, "days": str(record.days)}
    record.status = "voided"
    write_audit(
        "leave_voided",
        "EmployeeAnnualLeaveRecord",
        record.id,
        employee_id=record.employee_id,
        detail=request.form.get("reason", "").strip() or "撤回錯誤記錄",
        before=before,
        after={"status": record.status, "days": str(record.days)},
    )
    db.session.commit()
    flash("請假記錄已撤回。", "success")
    return annual_leave_redirect(
        record.employee_id,
        request.form.get("entitlement_year", type=int)
        or record.entitlement_year,
    )


@employees_bp.route("/employees/<int:employee_id>/leave-balance", methods=["POST"])
@login_required
def update_leave_balance(employee_id):
    employee = db.get_or_404(Employee, employee_id)
    year = request.form.get("year", type=int) or date.today().year
    balance = EmployeeAnnualLeaveBalance.query.filter_by(
        employee_id=employee.id,
        year=year,
    ).first()
    if not balance:
        balance = EmployeeAnnualLeaveBalance(employee=employee, year=year)
        db.session.add(balance)
    balance.carried_from_previous_days = parse_decimal(
        request.form.get("carried"),
        parse_decimal("0"),
    )
    balance.manual_adjustment_days = parse_decimal(
        request.form.get("manual_adjustment"),
        parse_decimal("0"),
    )
    db.session.commit()
    flash("年假結餘已保存。", "success")
    return employee_redirect(employee.id, "leave")


@employees_bp.route("/employees/<int:employee_id>/work-injuries", methods=["POST"])
@login_required
def add_work_injury(employee_id):
    employee = db.get_or_404(Employee, employee_id)
    accident_date = parse_date(request.form.get("accident_date"))
    payroll_start = parse_date(request.form.get("payroll_start_date"))
    payroll_end = parse_date(request.form.get("payroll_end_date"))
    confirmed = parse_decimal(request.form.get("confirmed_monthly_earnings"))
    during = parse_decimal(
        request.form.get("incapacity_monthly_earnings"), parse_decimal("0")
    )
    pay_mode = request.form.get("pay_mode", "four_fifths")
    if (
        not accident_date
        or not payroll_start
        or confirmed is None
        or confirmed < 0
        or during < 0
        or during > confirmed
        or (payroll_end and payroll_end < payroll_start)
        or pay_mode not in {"four_fifths", "full_pay"}
    ):
        flash("請核對工傷日期及計薪基數。", "error")
        return redirect(url_for("leave.leave_home", view="injury", employee_id=employee.id))
    if conflicting_absence(employee, payroll_start, payroll_end):
        flash("leave.overlap", "error")
        return redirect(url_for("leave.leave_home", view="injury", employee_id=employee.id))
    evidence = save_evidence(
        employee,
        request.files.get("evidence"),
        "change_evidence",
        "工傷證明",
    )
    salary = current_salary_on(employee, payroll_start)
    row = EmployeeWorkInjuryPeriod(
        employee=employee,
        accident_date=accident_date,
        payroll_start_date=payroll_start,
        payroll_end_date=payroll_end,
        confirmed_monthly_earnings=confirmed,
        incapacity_monthly_earnings=during,
        currency=request.form.get("currency")
        or (salary.currency if salary else "HKD"),
        evidence_document=evidence,
        remarks=request.form.get("remarks", "").strip() or None,
        status="active",
        pay_mode=pay_mode,
    )
    db.session.add(row)
    db.session.flush()
    write_audit(
        "work_injury_added",
        "EmployeeWorkInjuryPeriod",
        row.id,
        employee_id=employee.id,
        detail=f"{payroll_start:%Y-%m-%d} 至 {payroll_end or '至今'}",
    )
    db.session.commit()
    flash("工傷記錄已新增。", "success")
    filters = {key: request.form["back_" + key] for key in ("q", "status", "action", "project_id", "payroll_group")
               if request.form.get("back_" + key)}
    return redirect(url_for("leave.leave_home", view="injury", employee_id=employee.id,
                            year=request.form.get("entitlement_year") or None, **filters))


@employees_bp.route("/work-injuries/<int:period_id>/correct", methods=["POST"])
@login_required
def correct_work_injury(period_id):
    row = db.get_or_404(EmployeeWorkInjuryPeriod, period_id)
    accident_date = parse_date(request.form.get("accident_date"))
    payroll_start = parse_date(request.form.get("payroll_start_date"))
    payroll_end = parse_date(request.form.get("payroll_end_date"))
    confirmed = parse_decimal(request.form.get("confirmed_monthly_earnings"))
    during = parse_decimal(
        request.form.get("incapacity_monthly_earnings"), parse_decimal("0")
    )
    pay_mode = request.form.get("pay_mode", "four_fifths")
    if (
        not accident_date
        or not payroll_start
        or confirmed is None
        or confirmed < 0
        or during < 0
        or during > confirmed
        or (payroll_end and payroll_end < payroll_start)
        or pay_mode not in {"four_fifths", "full_pay"}
    ):
        flash("請核對工傷日期及計薪基數。", "error")
        return redirect(url_for("leave.leave_home", view="injury", employee_id=row.employee_id))
    if conflicting_absence(row.employee, payroll_start, payroll_end, exclude=("injury", row.id)):
        flash("leave.overlap", "error")
        return redirect(url_for("leave.leave_home", view="injury", employee_id=row.employee_id))
    before = {
        "payroll_start_date": row.payroll_start_date.isoformat(),
        "payroll_end_date": (
            row.payroll_end_date.isoformat() if row.payroll_end_date else None
        ),
        "confirmed_monthly_earnings": str(row.confirmed_monthly_earnings),
        "incapacity_monthly_earnings": str(row.incapacity_monthly_earnings),
        "pay_mode": row.pay_mode,
    }
    row.accident_date = accident_date
    row.payroll_start_date = payroll_start
    row.payroll_end_date = payroll_end
    row.confirmed_monthly_earnings = confirmed
    row.incapacity_monthly_earnings = during
    row.pay_mode = pay_mode
    row.currency = request.form.get("currency") or row.currency
    row.remarks = request.form.get("remarks", "").strip() or None
    row.status = "active"
    evidence = save_evidence(
        row.employee,
        request.files.get("evidence"),
        "change_evidence",
        "工傷證明",
    )
    if evidence:
        row.evidence_document = evidence
    write_audit(
        "work_injury_corrected",
        "EmployeeWorkInjuryPeriod",
        row.id,
        employee_id=row.employee_id,
        before=before,
        after={
            "payroll_start_date": row.payroll_start_date.isoformat(),
            "payroll_end_date": (
                row.payroll_end_date.isoformat() if row.payroll_end_date else None
            ),
            "confirmed_monthly_earnings": str(row.confirmed_monthly_earnings),
            "incapacity_monthly_earnings": str(row.incapacity_monthly_earnings),
            "pay_mode": row.pay_mode,
        },
    )
    db.session.commit()
    flash("工傷記錄已更正。", "success")
    return redirect(url_for("leave.leave_home", view="injury", employee_id=row.employee_id))


@employees_bp.route("/work-injuries/<int:period_id>/withdraw", methods=["POST"])
@login_required
def withdraw_work_injury(period_id):
    row = db.get_or_404(EmployeeWorkInjuryPeriod, period_id)
    row.status = "voided"
    write_audit(
        "work_injury_withdrawn",
        "EmployeeWorkInjuryPeriod",
        row.id,
        employee_id=row.employee_id,
        detail=request.form.get("reason", "").strip() or "撤回工傷記錄",
    )
    db.session.commit()
    flash("工傷記錄已撤回。", "success")
    return redirect(url_for("leave.leave_home", view="injury", employee_id=row.employee_id))


@employees_bp.route(
    "/work-injuries/<int:period_id>/monthly-expenses", methods=["POST"]
)
@login_required
def add_work_injury_expense(period_id):
    period = db.get_or_404(EmployeeWorkInjuryPeriod, period_id)
    year_month = request.form.get("year_month", "").strip()
    amount = parse_decimal(request.form.get("amount"))
    try:
        parse_year_month(year_month)
    except (TypeError, ValueError):
        year_month = ""
    if not year_month or amount is None or amount < 0:
        flash("請核對復診／醫療開支月份及金額。", "error")
        return redirect(url_for("leave.leave_home", view="injury", employee_id=period.employee_id))
    evidence = save_evidence(
        period.employee,
        request.files.get("evidence"),
        "change_evidence",
        f"{year_month} 工傷醫療開支",
    )
    expense = EmployeeWorkInjuryMonthlyExpense(
        employee=period.employee,
        work_injury_period=period,
        year_month=year_month,
        amount=amount,
        currency=request.form.get("currency") or period.currency or "HKD",
        evidence_document=evidence,
        remarks=request.form.get("remarks", "").strip() or None,
        status="active",
    )
    db.session.add(expense)
    db.session.flush()
    write_audit(
        "work_injury_expense_added",
        "EmployeeWorkInjuryMonthlyExpense",
        expense.id,
        employee_id=period.employee_id,
        detail=f"{year_month}: {amount}",
    )
    db.session.commit()
    flash("工傷復診／醫療開支已保存，將匯入該月工資表的 AN 欄。", "success")
    return redirect(url_for("leave.leave_home", view="injury", employee_id=period.employee_id))


@employees_bp.route(
    "/work-injury-expenses/<int:expense_id>/correct", methods=["POST"]
)
@login_required
def correct_work_injury_expense(expense_id):
    expense = db.get_or_404(EmployeeWorkInjuryMonthlyExpense, expense_id)
    year_month = request.form.get("year_month", "").strip()
    amount = parse_decimal(request.form.get("amount"))
    try:
        parse_year_month(year_month)
    except (TypeError, ValueError):
        year_month = ""
    if not year_month or amount is None or amount < 0:
        flash("請核對復診／醫療開支月份及金額。", "error")
        return redirect(url_for("leave.leave_home", view="injury", employee_id=expense.employee_id))
    before = {"year_month": expense.year_month, "amount": str(expense.amount)}
    expense.year_month = year_month
    expense.amount = amount
    expense.currency = request.form.get("currency") or expense.currency
    expense.remarks = request.form.get("remarks", "").strip() or None
    evidence = save_evidence(
        expense.employee,
        request.files.get("evidence"),
        "change_evidence",
        f"{year_month} 工傷醫療開支",
    )
    if evidence:
        expense.evidence_document = evidence
    write_audit(
        "work_injury_expense_corrected",
        "EmployeeWorkInjuryMonthlyExpense",
        expense.id,
        employee_id=expense.employee_id,
        before=before,
        after={"year_month": expense.year_month, "amount": str(expense.amount)},
    )
    db.session.commit()
    flash("工傷復診／醫療開支已更正。", "success")
    return redirect(url_for("leave.leave_home", view="injury", employee_id=expense.employee_id))


@employees_bp.route(
    "/work-injury-expenses/<int:expense_id>/withdraw", methods=["POST"]
)
@login_required
def withdraw_work_injury_expense(expense_id):
    expense = db.get_or_404(EmployeeWorkInjuryMonthlyExpense, expense_id)
    expense.status = "voided"
    write_audit(
        "work_injury_expense_withdrawn",
        "EmployeeWorkInjuryMonthlyExpense",
        expense.id,
        employee_id=expense.employee_id,
        detail=request.form.get("reason", "").strip() or "撤回工傷醫療開支",
    )
    db.session.commit()
    flash("工傷復診／醫療開支已撤回。", "success")
    return redirect(url_for("leave.leave_home", view="injury", employee_id=expense.employee_id))

