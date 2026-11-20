"""Employee workspace routes: employment."""
from hkr_hr.workbench.web.employees.common import *  # noqa: F401, F403


@employees_bp.route("/employees/<int:employee_id>/assignment", methods=["POST"])
@login_required
def add_assignment(employee_id):
    employee = db.get_or_404(Employee, employee_id)
    previous_current = current_assignment_on(employee, date.today())
    effective_from = parse_date(request.form.get("effective_from"))
    if not effective_from:
        flash("任職調整必須填寫生效日期。", "error")
        return employee_redirect(employee.id, "employment")
    if any(
        item.status == "active" and item.effective_from == effective_from
        for item in employee.assignments
    ):
        flash("此生效日期已有任職記錄；請修正原有記錄。", "error")
        return employee_redirect(employee.id, "employment")
    evidence = save_evidence(
        employee,
        request.files.get("evidence"),
        "change_evidence",
        "任職調整憑證",
    )
    payroll_group = request.form.get("payroll_group") or employee.payroll_group
    workweek_days = normalize_workweek_days(
        request.form.get("workweek_days"),
        payroll_group,
    )
    assignment = create_assignment(
        employee=employee,
        effective_from=effective_from,
        payroll_group=payroll_group,
        workweek_days=workweek_days,
        region_id=form_int("region_id"),
        project_id=form_int("project_id"),
        department_id=form_int("department_id"),
        employer_id=form_int("employer_id"),
        payroll_entity_id=form_int("payroll_entity_id"),
        social_insurance_entity_id=form_int("social_insurance_entity_id"),
        labour_dispatch_entity_id=form_int("labour_dispatch_entity_id"),
        position_ids=[
            int(item)
            for item in request.form.getlist("position_ids")
            if str(item).isdigit()
        ],
        evidence_document_id=evidence.id if evidence else None,
        remarks=request.form.get("remarks", "").strip() or None,
    )
    current_assignment = current_assignment_on(employee, date.today())
    if current_assignment:
        employee.payroll_group = current_assignment.payroll_group
    leave_period = ensure_current_employment_period(employee, effective_from)
    if not employee.annual_leave_balances and leave_period.contract_annual_leave_days is None and request.form.get("initial_leave_days"):
        from hkr_hr.leave.api import validate_leave_setup as validate
        from hkr_hr.leave.api import save_current_balance
        initial = parse_decimal(request.form.get("initial_leave_days"))
        try:
            validate(effective_from, initial)
        except ValueError:
            db.session.rollback()
            flash("leave.setup_invalid", "error")
            return employee_redirect(employee.id, "employment")
        leave_period.contract_annual_leave_days = initial
        leave_period.annual_leave_policy_year = date.today().year
        balance = save_current_balance(employee)
        write_audit("annual_leave_balance_updated", "EmployeeAnnualLeaveBalance", balance.id,
                    employee_id=employee.id, detail="初始任職建立本年度年假",
                    after={"year": date.today().year, "initial_days": str(initial),
                           "applied": str(balance.calculated_entitled_days)})
    write_audit(
        "assignment_changed",
        "EmployeeAssignment",
        assignment.id,
        employee_id=employee.id,
        detail=f"任職資料由 {effective_from:%Y-%m-%d} 生效",
        after={
            "project_id": assignment.project_id,
            "department_id": assignment.department_id,
            "payroll_group": assignment.payroll_group,
            "workweek_days": str(assignment.workweek_days),
            "evidence_missing": evidence is None,
        },
    )
    db.session.commit()
    if effective_from > date.today():
        flash(
            f"任職調整已保存，將於 {effective_from:%Y-%m-%d} 生效；目前任職暫不變。",
            "success",
        )
    elif previous_current:
        flash("任職調整已保存，當前任職已更新。", "success")
    else:
        flash("初始任職已保存，當前任職已建立。", "success")
    return employee_redirect(employee.id, "employment", saved=True)


@employees_bp.route("/employees/<int:employee_id>/salary", methods=["POST"])
@login_required
def add_salary(employee_id):
    employee = db.get_or_404(Employee, employee_id)
    effective_from = parse_date(request.form.get("effective_from"))
    amount = parse_decimal(request.form.get("amount"))
    salary_basis = request.form.get("salary_basis")
    monthly_pay_method = request.form.get("monthly_pay_method") or "full_month"
    if not effective_from or not valid_salary_amount(amount) or salary_basis not in {"monthly", "daily"}:
        flash("請完整填寫薪酬類型、金額及生效日期。", "error")
        return employee_redirect(employee.id, "employment")
    if monthly_pay_method not in {"full_month", "attendance_days"}:
        flash("請選擇有效的月薪計薪方式。", "error")
        return employee_redirect(employee.id, "employment")
    if any(
        item.status == "active" and item.effective_from == effective_from
        for item in employee.salaries
    ):
        flash("此生效日期已有薪酬記錄；請修正原有記錄。", "error")
        return employee_redirect(employee.id, "employment")
    evidence = save_evidence(
        employee,
        request.files.get("evidence"),
        "change_evidence",
        "薪酬調整憑證",
    )
    salary = create_salary(
        employee,
        effective_from,
        salary_basis,
        request.form.get("currency") or "HKD",
        amount,
        monthly_pay_method=monthly_pay_method,
        evidence_document_id=evidence.id if evidence else None,
        remarks=request.form.get("remarks", "").strip() or None,
    )
    write_audit(
        "salary_changed",
        "EmployeeSalary",
        salary.id,
        employee_id=employee.id,
        detail=f"薪酬由 {effective_from:%Y-%m-%d} 生效",
        after={
            "basis": salary_basis,
            "monthly_pay_method": salary.monthly_pay_method,
            "currency": salary.currency,
            "amount": str(salary.amount),
            "evidence_missing": evidence is None,
        },
    )
    db.session.commit()
    flash("薪酬資料已保存。", "success")
    return employee_redirect(employee.id, "employment", saved=True)


def replace_linked_evidence(old_document, new_document, reason):
    if not old_document or old_document.id == new_document.id:
        return
    from hkr_hr.documents.api import document_reference_count
    if old_document.status != "active" or document_reference_count(old_document) > 1:
        return
    old_document.status = "replaced"
    old_document.replaced_by_document_id = new_document.id
    old_document.replacement_reason = reason


@employees_bp.route(
    "/assignments/<int:assignment_id>/evidence",
    methods=["POST"],
)
@login_required
def supplement_assignment_evidence(assignment_id):
    assignment = db.get_or_404(EmployeeAssignment, assignment_id)
    document = save_evidence(
        assignment.employee,
        request.files.get("evidence"),
        "change_evidence",
        "任職調整憑證",
    )
    if not document:
        flash("請選擇憑證文件。", "error")
        return employee_redirect(assignment.employee_id, "employment")
    replace_linked_evidence(
        assignment.evidence_document,
        document,
        "補充或更正任職調整憑證",
    )
    assignment.evidence_document_id = document.id
    write_audit(
        "assignment_evidence_added",
        "EmployeeAssignment",
        assignment.id,
        employee_id=assignment.employee_id,
        detail=document.original_filename,
    )
    db.session.commit()
    flash("任職調整憑證已保存。", "success")
    return employee_redirect(assignment.employee_id, "employment")


@employees_bp.route(
    "/assignments/<int:assignment_id>/correct",
    methods=["POST"],
)
@login_required
def correct_assignment(assignment_id):
    assignment = db.get_or_404(EmployeeAssignment, assignment_id)
    if assignment.status != "active":
        abort(400)
    before = assignment_snapshot(assignment)
    effective_from = parse_date(request.form.get("effective_from"))
    payroll_group = request.form.get("payroll_group")
    if not effective_from or payroll_group not in {
        item[0] for item in PAYROLL_GROUPS
    }:
        flash("請完整填寫任職生效日期及薪酬組別。", "error")
        return employee_redirect(assignment.employee_id, "employment")
    duplicate = EmployeeAssignment.query.filter(
        EmployeeAssignment.employee_id == assignment.employee_id,
        EmployeeAssignment.effective_from == effective_from,
        EmployeeAssignment.status == "active",
        EmployeeAssignment.id != assignment.id,
    ).first()
    if duplicate:
        flash("同一生效日期已有一筆任職記錄，請修正原記錄。", "error")
        return employee_redirect(assignment.employee_id, "employment")
    assignment.effective_from = effective_from
    assignment.region_id = form_int("region_id")
    assignment.project_id = form_int("project_id")
    assignment.department_id = form_int("department_id")
    assignment.employer_id = form_int("employer_id")
    assignment.payroll_entity_id = form_int("payroll_entity_id")
    assignment.social_insurance_entity_id = form_int(
        "social_insurance_entity_id"
    )
    assignment.labour_dispatch_entity_id = form_int(
        "labour_dispatch_entity_id"
    )
    assignment.payroll_group = payroll_group
    assignment.workweek_days = normalize_workweek_days(
        request.form.get("workweek_days"),
        payroll_group,
    )
    assignment.remarks = request.form.get("remarks", "").strip() or None
    assignment.positions.clear()
    db.session.flush()
    for index, value in enumerate(request.form.getlist("position_ids")):
        if str(value).isdigit():
            assignment.positions.append(
                EmployeeAssignmentPosition(
                    position_id=int(value),
                    is_primary=index == 0,
                )
            )
    document = save_evidence(
        assignment.employee,
        request.files.get("evidence"),
        "change_evidence",
        "任職調整憑證",
    )
    if document:
        replace_linked_evidence(
            assignment.evidence_document,
            document,
            "更正任職調整憑證",
        )
        assignment.evidence_document_id = document.id
    rebuild_effective_ranges(assignment.employee.assignments)
    current = current_assignment_on(assignment.employee, date.today())
    if current:
        assignment.employee.payroll_group = current.payroll_group
    write_audit(
        "assignment_corrected",
        "EmployeeAssignment",
        assignment.id,
        employee_id=assignment.employee_id,
        detail=f"更正任職記錄，生效日 {effective_from:%Y-%m-%d}",
        before=before,
        after=assignment_snapshot(assignment),
    )
    db.session.commit()
    flash("任職記錄已更正。", "success")
    return employee_redirect(assignment.employee_id, "employment", saved=True)


@employees_bp.route(
    "/assignments/<int:assignment_id>/withdraw",
    methods=["POST"],
)
@login_required
def withdraw_assignment(assignment_id):
    assignment = db.get_or_404(EmployeeAssignment, assignment_id)
    before = assignment_snapshot(assignment)
    assignment.status = "voided"
    rebuild_effective_ranges(assignment.employee.assignments)
    current = current_assignment_on(assignment.employee, date.today())
    if current:
        assignment.employee.payroll_group = current.payroll_group
    write_audit(
        "assignment_withdrawn",
        "EmployeeAssignment",
        assignment.id,
        employee_id=assignment.employee_id,
        detail=request.form.get("reason", "").strip() or "撤回錯誤記錄",
        before=before,
        after=assignment_snapshot(assignment),
    )
    db.session.commit()
    flash("任職記錄已撤回，原記錄保留在歷史中。", "success")
    return employee_redirect(assignment.employee_id, "employment")


@employees_bp.route(
    "/salaries/<int:salary_id>/evidence",
    methods=["POST"],
)
@login_required
def supplement_salary_evidence(salary_id):
    salary = db.get_or_404(EmployeeSalary, salary_id)
    document = save_evidence(
        salary.employee,
        request.files.get("evidence"),
        "change_evidence",
        "薪酬調整憑證",
    )
    if not document:
        flash("請選擇憑證文件。", "error")
        return employee_redirect(salary.employee_id, "employment")
    replace_linked_evidence(
        salary.evidence_document,
        document,
        "補充或更正薪酬調整憑證",
    )
    salary.evidence_document_id = document.id
    write_audit(
        "salary_evidence_added",
        "EmployeeSalary",
        salary.id,
        employee_id=salary.employee_id,
        detail=document.original_filename,
    )
    db.session.commit()
    flash("薪酬調整憑證已保存。", "success")
    return employee_redirect(salary.employee_id, "employment")


@employees_bp.route(
    "/salaries/<int:salary_id>/correct",
    methods=["POST"],
)
@login_required
def correct_salary(salary_id):
    salary = db.get_or_404(EmployeeSalary, salary_id)
    if salary.status != "active":
        abort(400)
    before = salary_snapshot(salary)
    effective_from = parse_date(request.form.get("effective_from"))
    amount = parse_decimal(request.form.get("amount"))
    salary_basis = request.form.get("salary_basis")
    monthly_pay_method = request.form.get("monthly_pay_method") or "full_month"
    if (
        not effective_from
        or not valid_salary_amount(amount)
        or salary_basis not in {"monthly", "daily"}
        or monthly_pay_method not in {"full_month", "attendance_days"}
    ):
        flash("請完整填寫薪酬類型、金額及生效日期。", "error")
        return employee_redirect(salary.employee_id, "employment")
    duplicate = EmployeeSalary.query.filter(
        EmployeeSalary.employee_id == salary.employee_id,
        EmployeeSalary.effective_from == effective_from,
        EmployeeSalary.status == "active",
        EmployeeSalary.id != salary.id,
    ).first()
    if duplicate:
        flash("同一生效日期已有一筆薪酬記錄，請修正原記錄。", "error")
        return employee_redirect(salary.employee_id, "employment")
    salary.effective_from = effective_from
    salary.salary_basis = salary_basis
    salary.monthly_pay_method = (
        monthly_pay_method if salary_basis == "monthly" else "full_month"
    )
    salary.currency = request.form.get("currency") or "HKD"
    salary.amount = amount
    salary.remarks = request.form.get("remarks", "").strip() or None
    document = save_evidence(
        salary.employee,
        request.files.get("evidence"),
        "change_evidence",
        "薪酬調整憑證",
    )
    if document:
        replace_linked_evidence(
            salary.evidence_document,
            document,
            "更正薪酬調整憑證",
        )
        salary.evidence_document_id = document.id
    rebuild_effective_ranges(salary.employee.salaries)
    write_audit(
        "salary_corrected",
        "EmployeeSalary",
        salary.id,
        employee_id=salary.employee_id,
        detail=f"更正薪酬記錄，生效日 {effective_from:%Y-%m-%d}",
        before=before,
        after=salary_snapshot(salary),
    )
    db.session.commit()
    flash("薪酬記錄已更正。", "success")
    return employee_redirect(salary.employee_id, "employment")


@employees_bp.route(
    "/salaries/<int:salary_id>/withdraw",
    methods=["POST"],
)
@login_required
def withdraw_salary(salary_id):
    salary = db.get_or_404(EmployeeSalary, salary_id)
    before = salary_snapshot(salary)
    salary.status = "voided"
    rebuild_effective_ranges(salary.employee.salaries)
    write_audit(
        "salary_withdrawn",
        "EmployeeSalary",
        salary.id,
        employee_id=salary.employee_id,
        detail=request.form.get("reason", "").strip() or "撤回錯誤記錄",
        before=before,
        after=salary_snapshot(salary),
    )
    db.session.commit()
    flash("薪酬記錄已撤回，原記錄保留在歷史中。", "success")
    return employee_redirect(salary.employee_id, "employment")


def requested_mpf_values():
    effective_from = parse_date(request.form.get("effective_from"))
    selection = request.form.get("mpf_selection")
    if not effective_from:
        raise ValueError("MPF 記錄必須填寫生效日期。")
    exempt = request.form.get("mpf_exempt") == "on"
    if not selection and exempt:
        return effective_from, None, None, "exempt"
    if not str(selection or "").isdigit():
        raise ValueError("請選擇 MPF 計劃。")
    scheme = db.session.get(MpfScheme, int(selection))
    if not scheme or not scheme.active:
        raise ValueError("所選 MPF 計劃無效。")
    member_account_no = (
        request.form.get("member_account_no", "").strip() or None
    )
    contribution_mode = (
        "exempt"
        if request.form.get("mpf_exempt") == "on"
        else scheme.calculation_mode
    )
    return (
        effective_from,
        scheme,
        member_account_no,
        contribution_mode,
    )


@employees_bp.route("/employees/<int:employee_id>/mpf", methods=["POST"])
@login_required
def add_mpf_enrollment(employee_id):
    employee = db.get_or_404(Employee, employee_id)
    try:
        effective_from, scheme, member_no, mode = requested_mpf_values()
    except ValueError as exc:
        flash(str(exc), "error")
        return employee_redirect(employee.id, "employment")
    if any(
        item.status == "active" and item.effective_from == effective_from
        for item in employee.mpf_enrollments
    ):
        flash("此生效日期已有 MPF 記錄；請更正原有記錄。", "error")
        return employee_redirect(employee.id, "employment")
    enrollment = create_mpf_enrollment(
        employee,
        effective_from,
        scheme=scheme,
        member_account_no=member_no,
        contribution_mode=mode,
        remarks=request.form.get("remarks", "").strip() or None,
    )
    write_audit(
        "mpf_enrollment_added",
        "EmployeeMpfEnrollment",
        enrollment.id,
        employee_id=employee.id,
        detail=f"MPF 記錄由 {effective_from:%Y-%m-%d} 生效",
        after=mpf_snapshot(enrollment),
    )
    db.session.commit()
    flash("MPF 記錄已保存。", "success")
    return employee_redirect(employee.id, "employment")


@employees_bp.route(
    "/mpf-enrollments/<int:enrollment_id>/correct",
    methods=["POST"],
)
@login_required
def correct_mpf_enrollment(enrollment_id):
    enrollment = db.get_or_404(EmployeeMpfEnrollment, enrollment_id)
    if enrollment.status != "active":
        abort(400)
    try:
        effective_from, scheme, member_no, mode = requested_mpf_values()
    except ValueError as exc:
        flash(str(exc), "error")
        return employee_redirect(enrollment.employee_id, "employment")
    duplicate = EmployeeMpfEnrollment.query.filter(
        EmployeeMpfEnrollment.employee_id == enrollment.employee_id,
        EmployeeMpfEnrollment.effective_from == effective_from,
        EmployeeMpfEnrollment.status == "active",
        EmployeeMpfEnrollment.id != enrollment.id,
    ).first()
    if duplicate:
        flash("同一生效日期已有一筆 MPF 記錄。", "error")
        return employee_redirect(enrollment.employee_id, "employment")
    before = mpf_snapshot(enrollment)
    enrollment.effective_from = effective_from
    enrollment.scheme = scheme
    enrollment.member_account_no = member_no
    enrollment.contribution_mode = mode
    enrollment.remarks = request.form.get("remarks", "").strip() or None
    rebuild_effective_ranges(enrollment.employee.mpf_enrollments)
    current = current_mpf_on(enrollment.employee, date.today())
    enrollment.employee.mpf_mode = (
        current.contribution_mode if current else "regular"
    )
    write_audit(
        "mpf_enrollment_corrected",
        "EmployeeMpfEnrollment",
        enrollment.id,
        employee_id=enrollment.employee_id,
        detail=f"更正 MPF 記錄，生效日 {effective_from:%Y-%m-%d}",
        before=before,
        after=mpf_snapshot(enrollment),
    )
    db.session.commit()
    flash("MPF 記錄已更正。", "success")
    return employee_redirect(enrollment.employee_id, "employment")


@employees_bp.route(
    "/mpf-enrollments/<int:enrollment_id>/withdraw",
    methods=["POST"],
)
@login_required
def withdraw_mpf_enrollment(enrollment_id):
    enrollment = db.get_or_404(EmployeeMpfEnrollment, enrollment_id)
    before = mpf_snapshot(enrollment)
    enrollment.status = "voided"
    rebuild_effective_ranges(enrollment.employee.mpf_enrollments)
    current = current_mpf_on(enrollment.employee, date.today())
    enrollment.employee.mpf_mode = (
        current.contribution_mode if current else "regular"
    )
    write_audit(
        "mpf_enrollment_withdrawn",
        "EmployeeMpfEnrollment",
        enrollment.id,
        employee_id=enrollment.employee_id,
        detail=request.form.get("reason", "").strip() or "撤回錯誤記錄",
        before=before,
        after=mpf_snapshot(enrollment),
    )
    db.session.commit()
    flash("MPF 記錄已撤回，原記錄保留在變更歷史。", "success")
    return employee_redirect(enrollment.employee_id, "employment")


@employees_bp.route("/employees/<int:employee_id>/probation", methods=["POST"])
@login_required
def update_probation(employee_id):
    employee = db.get_or_404(Employee, employee_id)
    period = ensure_current_employment_period(
        employee,
        parse_date(request.form.get("start_date")) or date.today(),
    )
    before = employment_period_snapshot(period)
    evidence = replace_record_evidence(
        employee,
        period.confirmation_document,
        request.files.get("evidence"),
        "probation_confirmation",
        "通過試用期申請表",
        "更正通過試用期申請表",
    )
    period.probation_end_date = parse_date(request.form.get("probation_end_date"))
    period.confirmation_date = parse_date(request.form.get("confirmation_date"))
    if evidence:
        period.confirmation_document_id = evidence.id
    write_audit(
        "probation_updated",
        "EmployeeEmploymentPeriod",
        period.id,
        employee_id=employee.id,
        detail="更新試用期 / 轉正資料",
        before=before,
        after=employment_period_snapshot(period),
    )
    db.session.commit()
    flash("試用期資料已保存。", "success")
    return employee_redirect(employee.id, "employment_status")


@employees_bp.route("/employees/<int:employee_id>/allowances", methods=["POST"])
@login_required
def add_allowance(employee_id):
    employee = db.get_or_404(Employee, employee_id)
    if employee.payroll_group == "site_daily":
        flash("固定補貼目前只支持月工及 OFFICE，不支持日工。", "error")
        return employee_redirect(employee.id, "employment")
    allowance_type = request.form.get("allowance_type", "").strip()
    effective_from = parse_date(request.form.get("effective_from"))
    effective_to = parse_date(request.form.get("effective_to"))
    amount = parse_decimal(request.form.get("amount"))
    currency = request.form.get("currency", "HKD").strip().upper()
    exchange_rate = parse_decimal(request.form.get("exchange_rate"))
    salary = current_salary_on(employee, effective_from or date.today())
    if allowance_type not in {"meal", "transport", "special"}:
        flash("請選擇餐補、交通補貼或特殊津貼。", "error")
        return employee_redirect(employee.id, "employment")
    if not effective_from or amount is None or amount < 0:
        flash("請填寫有效的補貼生效日期及金額。", "error")
        return employee_redirect(employee.id, "employment")
    if effective_to and effective_to < effective_from:
        flash("補貼結束日期不可早於生效日期。", "error")
        return employee_redirect(employee.id, "employment")
    if salary and currency != salary.currency and (
        exchange_rate is None or exchange_rate <= 0
    ):
        flash("補貼幣種與發薪幣種不同，必須填寫匯率。", "error")
        return employee_redirect(employee.id, "employment")
    evidence = save_evidence(
        employee,
        request.files.get("evidence"),
        "change_evidence",
        "補貼憑證",
    )
    labels = {"meal": "餐補", "transport": "交通補貼", "special": "特殊津貼"}
    allowance = EmployeeAllowance(
        employee=employee,
        allowance_type=allowance_type,
        label=labels[allowance_type],
        currency=currency,
        amount=amount,
        exchange_rate=(
            exchange_rate if salary and currency != salary.currency else None
        ),
        effective_from=effective_from,
        effective_to=effective_to,
        status="active",
        evidence_document=evidence,
        remarks=request.form.get("remarks", "").strip() or None,
    )
    db.session.add(allowance)
    db.session.flush()
    write_audit(
        "allowance_added",
        "EmployeeAllowance",
        allowance.id,
        employee_id=employee.id,
        detail=f"{labels[allowance_type]} {currency} {amount}",
    )
    db.session.commit()
    flash("補貼記錄已新增。", "success")
    return employee_redirect(employee.id, "employment")


@employees_bp.route("/allowances/<int:allowance_id>/correct", methods=["POST"])
@login_required
def correct_allowance(allowance_id):
    allowance = db.get_or_404(EmployeeAllowance, allowance_id)
    if allowance.employee.payroll_group == "site_daily":
        flash("固定補貼目前只支持月工及 OFFICE，不支持日工。", "error")
        return employee_redirect(allowance.employee_id, "employment")
    before = {
        "allowance_type": allowance.allowance_type,
        "currency": allowance.currency,
        "amount": str(allowance.amount),
        "exchange_rate": (
            str(allowance.exchange_rate) if allowance.exchange_rate else None
        ),
        "effective_from": allowance.effective_from.isoformat(),
        "effective_to": (
            allowance.effective_to.isoformat() if allowance.effective_to else None
        ),
    }
    allowance_type = request.form.get(
        "allowance_type", allowance.allowance_type
    ).strip()
    effective_from = parse_date(request.form.get("effective_from"))
    effective_to = parse_date(request.form.get("effective_to"))
    amount = parse_decimal(request.form.get("amount"))
    currency = request.form.get("currency", allowance.currency).strip().upper()
    exchange_rate = parse_decimal(request.form.get("exchange_rate"))
    salary = current_salary_on(allowance.employee, effective_from or date.today())
    if (
        allowance_type not in {"meal", "transport", "special"}
        or not effective_from
        or amount is None
        or amount < 0
        or (effective_to and effective_to < effective_from)
        or (
            salary
            and currency != salary.currency
            and (exchange_rate is None or exchange_rate <= 0)
        )
    ):
        flash("請核對補貼類型、日期、金額、幣種及匯率。", "error")
        return employee_redirect(allowance.employee_id, "employment")
    labels = {"meal": "餐補", "transport": "交通補貼", "special": "特殊津貼"}
    allowance.allowance_type = allowance_type
    allowance.label = labels[allowance_type]
    allowance.effective_from = effective_from
    allowance.effective_to = effective_to
    allowance.amount = amount
    allowance.currency = currency
    allowance.exchange_rate = (
        exchange_rate if salary and currency != salary.currency else None
    )
    allowance.remarks = request.form.get("remarks", "").strip() or None
    evidence = save_evidence(
        allowance.employee,
        request.files.get("evidence"),
        "change_evidence",
        "補貼憑證",
    )
    if evidence:
        allowance.evidence_document = evidence
    allowance.status = "active"
    write_audit(
        "allowance_corrected",
        "EmployeeAllowance",
        allowance.id,
        employee_id=allowance.employee_id,
        before=before,
        after={
            "allowance_type": allowance.allowance_type,
            "currency": allowance.currency,
            "amount": str(allowance.amount),
            "exchange_rate": (
                str(allowance.exchange_rate) if allowance.exchange_rate else None
            ),
            "effective_from": allowance.effective_from.isoformat(),
            "effective_to": (
                allowance.effective_to.isoformat() if allowance.effective_to else None
            ),
        },
    )
    db.session.commit()
    flash("補貼記錄已更正。", "success")
    return employee_redirect(allowance.employee_id, "employment")


@employees_bp.route("/allowances/<int:allowance_id>/withdraw", methods=["POST"])
@login_required
def withdraw_allowance(allowance_id):
    allowance = db.get_or_404(EmployeeAllowance, allowance_id)
    allowance.status = "voided"
    write_audit(
        "allowance_withdrawn",
        "EmployeeAllowance",
        allowance.id,
        employee_id=allowance.employee_id,
        detail=request.form.get("reason", "").strip() or "撤回補貼記錄",
    )
    db.session.commit()
    flash("補貼記錄已撤回。", "success")
    return employee_redirect(allowance.employee_id, "employment")


@employees_bp.route("/employees/<int:employee_id>/terminate", methods=["POST"])
@login_required
def terminate_employee(employee_id):
    employee = db.get_or_404(Employee, employee_id)
    end_date = parse_date(request.form.get("end_date"))
    reason = request.form.get("reason")
    if not end_date or reason not in {item[0] for item in TERMINATION_REASONS}:
        flash("請填寫最後工作日及離職原因。", "error")
        return employee_redirect(employee.id, "employment_status")
    period = employee.current_period or ensure_current_employment_period(employee)
    before = employment_period_snapshot(period)
    evidence = replace_record_evidence(
        employee,
        period.termination_document,
        request.files.get("evidence"),
        "termination_letter",
        "離職 / 終止通知",
        "更正離職 / 終止通知",
    )
    average_wage = parse_decimal(request.form.get("average_wage"))
    if average_wage is None:
        average_wage = average_wage_prefill(employee, end_date)["average"]
    estimate = termination_estimate(
        employee,
        end_date,
        reason,
        average_wage,
    )
    period.end_date = end_date
    period.termination_reason = reason
    period.average_wage = average_wage
    period.payment_in_lieu = parse_decimal(
        request.form.get("payment_in_lieu"),
        estimate["payment_in_lieu"],
    )
    period.severance_payment = parse_decimal(
        request.form.get("severance_payment"),
        estimate["severance"],
    )
    period.long_service_payment = parse_decimal(
        request.form.get("long_service_payment"),
        estimate["long_service"],
    )
    if evidence:
        period.termination_document_id = evidence.id
    employee.status = "active" if end_date >= date.today() else "departed"
    write_audit(
        "employment_terminated",
        "EmployeeEmploymentPeriod",
        period.id,
        employee_id=employee.id,
        detail=(
            f"{'更正' if before['end_date'] else '建立'}離職資料，"
            f"最後工作日 {end_date:%Y-%m-%d}"
        ),
        before=before,
        after=employment_period_snapshot(period),
    )
    db.session.commit()
    flash("離職資料已保存。估算金額仍須由 HR 核對。", "success")
    return employee_redirect(employee.id, "employment_status")


@employees_bp.route(
    "/employees/<int:employee_id>/termination/cancel",
    methods=["POST"],
)
@login_required
def cancel_termination(employee_id):
    employee = db.get_or_404(Employee, employee_id)
    period = employee.current_period
    if not period or not period.end_date:
        flash("目前沒有可撤回的離職記錄。", "info")
        return employee_redirect(employee.id, "employment_status")
    old_end_date = period.end_date
    before = employment_period_snapshot(period)
    period.end_date = None
    period.termination_reason = None
    period.average_wage = None
    period.payment_in_lieu = None
    period.severance_payment = None
    period.long_service_payment = None
    period.termination_document_id = None
    employee.status = "active"
    write_audit(
        "employment_termination_cancelled",
        "EmployeeEmploymentPeriod",
        period.id,
        employee_id=employee.id,
        detail=f"撤回原定 {old_end_date:%Y-%m-%d} 的離職資料",
        before=before,
        after=employment_period_snapshot(period),
    )
    db.session.commit()
    flash("離職資料已撤回，員工保持在職。", "success")
    return employee_redirect(employee.id, "employment_status")


@employees_bp.route("/employees/<int:employee_id>/rehire", methods=["POST"])
@login_required
def rehire_employee(employee_id):
    employee = db.get_or_404(Employee, employee_id)
    start_date = parse_date(request.form.get("start_date"))
    if not start_date:
        flash("請填寫重新入職日期。", "error")
        return employee_redirect(employee.id, "employment_status")
    period = EmployeeEmploymentPeriod(employee=employee, start_date=start_date)
    db.session.add(period)
    db.session.flush()
    employee.status = "active"
    write_audit(
        "employee_rehired",
        "EmployeeEmploymentPeriod",
        period.id,
        employee_id=employee.id,
        detail=f"重新入職 {start_date:%Y-%m-%d}",
        after=employment_period_snapshot(period),
    )
    db.session.commit()
    flash("已使用原員工編號建立新的任職期間。", "success")
    return employee_redirect(employee.id, "employment_status")


@employees_bp.route("/employees/<int:employee_id>/delete", methods=["POST"])
@login_required
def delete_employee(employee_id):
    if current_user.role != "admin":
        abort(403)
    employee = db.get_or_404(Employee, employee_id)
    if request.form.get("confirm_employee_no", "").strip() != employee.employee_no:
        flash("employee.delete_confirmation_failed", "error")
        return employee_redirect(employee.id, "employment")
    employee_no = employee.employee_no
    upload_folder = employee_files_path(employee)
    summary_ids = [item.id for item in employee.attendance_summaries]
    batch_items = AttendanceBatchItem.query.filter(
        (AttendanceBatchItem.employee_id == employee.id)
        | (AttendanceBatchItem.summary_id.in_(summary_ids))
    ).all()
    batch_ids = {item.batch_id for item in batch_items}
    batch_paths = [Path(item.stored_path) for item in batch_items]
    batch_folders = {path.parent for path in batch_paths}
    payroll_run_ids = {item.run_id for item in employee.payroll_results}
    generated_paths = [
        Path(contract.output_path) for contract in employee.generated_contracts
    ]
    for item in batch_items:
        db.session.delete(item)
    AuditLog.query.filter_by(employee_id=employee.id).delete(
        synchronize_session=False
    )
    db.session.delete(employee)
    db.session.flush()
    for batch_id in batch_ids:
        if not AttendanceBatchItem.query.filter_by(batch_id=batch_id).first():
            batch = db.session.get(AttendanceBatch, batch_id)
            if batch:
                db.session.delete(batch)
    for run_id in payroll_run_ids:
        run = db.session.get(PayrollRun, run_id)
        if run and not PayrollEmployeeResult.query.filter_by(
            run_id=run_id
        ).first():
            db.session.delete(run)
    write_audit(
        "employee_deleted",
        "Employee",
        employee.id,
        detail=f"刪除員工檔案 {employee_no}",
    )
    db.session.commit()
    for path in generated_paths + batch_paths:
        if path.is_file():
            path.unlink()
    for folder in batch_folders:
        if folder.is_dir() and not any(folder.iterdir()):
            folder.rmdir()
    delete_employee_files(folder=upload_folder)
    flash(f"員工 {employee_no}、考勤及工資表資料已全部刪除。", "success")
    return redirect(url_for("employees.list_employees"))

