"""Employee workspace routes: profile."""
from hkr_hr.workbench.web.employees.common import *  # noqa: F401, F403


@employees_bp.route("/employees/<int:employee_id>/personal", methods=["POST"])
@login_required
def update_personal(employee_id):
    employee = Employee.query.filter_by(id=employee_id).with_for_update().populate_existing().first_or_404()
    scope = request.form.get("form_scope", "all")
    if scope not in {"all", "profile", "education", "visa_requirement", "attendance_policy"}:
        abort(400)
    if not hmac.compare_digest(request.form.get("profile_revision", "").encode(), profile_revision(employee, scope).encode()):
        db.session.rollback()
        flash("review.profile_conflict", "error")
        return employee_redirect(employee_id, "personal")
    before = employee_audit_snapshot(employee)
    previous_attendance_required = attendance_required(
        employee,
        current_month(),
    )
    if scope in {"all", "profile"}:
        employee.gender = request.form.get("gender") or None
        employee.date_of_birth = parse_date(request.form.get("date_of_birth"))
        employee.mobile_region_code = request.form.get("mobile_region_code") or None
        employee.mobile_number = request.form.get("mobile_number", "").strip() or None
        employee.email = request.form.get("email", "").strip() or None
        employee.residential_address = (
            request.form.get("residential_address", "").strip() or None
        )
        employee.emergency_contact_name = (
            request.form.get("emergency_contact_name", "").strip() or None
        )
        employee.emergency_contact_region_code = (
            request.form.get("emergency_contact_region_code") or None
        )
        employee.emergency_contact_phone = (
            request.form.get("emergency_contact_phone", "").strip() or None
        )
        employee.emergency_contact_relation = (
            request.form.get("emergency_contact_relation", "").strip() or None
        )
        employee.remarks = request.form.get("remarks", "").strip() or None
    if scope == "all" and (
        "bank_name" in request.form or "bank_account_no" in request.form
    ):
        bank_name = request.form.get("bank_name", "").strip()
        account_no = request.form.get("bank_account_no", "").strip()
        if bank_name and account_no:
            current_bank = current_bank_account_on(employee, date.today())
            if not current_bank:
                current_bank = EmployeeBankAccount(
                    employee=employee,
                    effective_from=(
                        employee.current_period.start_date
                        if employee.current_period
                        else date.today()
                    ),
                    bank_name=bank_name,
                    account_no=account_no,
                    currency="HKD",
                    status="active",
                )
                db.session.add(current_bank)
                db.session.flush()
            else:
                current_bank.bank_name = bank_name
                current_bank.account_no = account_no
            rebuild_effective_ranges(employee.bank_accounts)
            sync_legacy_bank_fields(employee)
    if scope in {"all", "education"}:
        employee.education_level = request.form.get("education_level") or None
        employee.major = request.form.get("major", "").strip() or None
        employee.graduation_school = (
            request.form.get("graduation_school", "").strip() or None
        )
    if scope in {"all", "visa_requirement"}:
        employee.visa_required = parse_bool(request.form.get("visa_required"))
    requested_attendance_required = (
        request.form.get("requires_attendance") == "1"
        if "requires_attendance" in request.form
        else previous_attendance_required
    )
    if scope in {"all", "attendance_policy"} and (
        requested_attendance_required != previous_attendance_required
    ):
        db.session.add(
            set_long_term_attendance_policy(
                employee,
                current_month(),
                requested_attendance_required,
                created_by=current_user.id,
                remarks="由員工檔案更新每月考勤要求",
            )
        )
        write_audit(
            "attendance_policy_required"
            if requested_attendance_required
            else "attendance_policy_exempted",
            "EmployeeAttendancePolicy",
            employee_id=employee.id,
            detail=(
                f"自 {current_month()} 起需要每月考勤"
                if requested_attendance_required
                else f"自 {current_month()} 起長期免交考勤"
            ),
            before={"requires_attendance": previous_attendance_required},
            after={"requires_attendance": requested_attendance_required},
        )
    after = employee_audit_snapshot(employee)
    if before != after:
        action = {
            "education": "education_background_updated",
            "visa_requirement": "visa_requirement_updated",
        }.get(scope, "personal_data_updated")
        detail = {
            "profile": "更新個人資料",
            "education": "更新教育背景",
            "visa_requirement": "更新工作許可要求",
            "attendance_policy": "更新每月考勤要求",
        }.get(scope, "更新個人資料")
        write_audit(
            action,
            "Employee",
            employee.id,
            employee_id=employee.id,
            detail=detail,
            before=before,
            after=after,
        )
    db.session.commit()
    flash(
        {
            "education": "教育背景已保存。",
            "visa_requirement": "工作許可要求已保存。",
            "attendance_policy": "每月考勤要求已保存。",
        }.get(scope, "個人資料已保存。"),
        "success",
    )
    return employee_redirect(
        employee.id,
        "credentials"
        if scope in {"education", "visa_requirement"}
        else "employment"
        if scope == "attendance_policy"
        else "personal",
    )


@employees_bp.route("/employees/<int:employee_id>/bank-accounts", methods=["POST"])
@login_required
def add_bank_account(employee_id):
    employee = db.get_or_404(Employee, employee_id)
    effective_from = parse_date(request.form.get("effective_from"))
    bank_name = request.form.get("bank_name", "").strip()
    account_no = request.form.get("account_no", "").strip()
    if not effective_from or not bank_name or not account_no:
        flash("請填寫生效日期、銀行及賬戶號碼。", "error")
        return employee_redirect(employee.id, "personal")
    evidence = save_evidence(
        employee,
        request.files.get("evidence"),
        "bank_proof",
        "銀行賬戶證明",
    )
    account = EmployeeBankAccount(
        employee=employee,
        effective_from=effective_from,
        bank_name=bank_name,
        account_no=account_no,
        currency=(request.form.get("currency", "HKD").strip() or "HKD").upper(),
        evidence_document=evidence,
        status="active",
        remarks=request.form.get("remarks", "").strip() or None,
    )
    db.session.add(account)
    db.session.flush()
    rebuild_effective_ranges(employee.bank_accounts)
    sync_legacy_bank_fields(employee)
    write_audit(
        "bank_account_added",
        "EmployeeBankAccount",
        account.id,
        employee_id=employee.id,
        detail=f"銀行賬戶由 {effective_from:%Y-%m-%d} 生效",
        after=bank_account_snapshot(account),
    )
    db.session.commit()
    flash("銀行賬戶記錄已新增。", "success")
    return employee_redirect(employee.id, "personal", saved=True)


@employees_bp.route("/bank-accounts/<int:account_id>/correct", methods=["POST"])
@login_required
def correct_bank_account(account_id):
    account = db.get_or_404(EmployeeBankAccount, account_id)
    before = bank_account_snapshot(account)
    effective_from = parse_date(request.form.get("effective_from"))
    bank_name = request.form.get("bank_name", "").strip()
    account_no = request.form.get("account_no", "").strip()
    if not effective_from or not bank_name or not account_no:
        flash("請填寫生效日期、銀行及賬戶號碼。", "error")
        return employee_redirect(account.employee_id, "personal")
    account.effective_from = effective_from
    account.bank_name = bank_name
    account.account_no = account_no
    account.currency = (request.form.get("currency", "HKD").strip() or "HKD").upper()
    account.remarks = request.form.get("remarks", "").strip() or None
    account.evidence_document = replace_record_evidence(
        account.employee,
        account.evidence_document,
        request.files.get("evidence"),
        "bank_proof",
        "銀行賬戶證明",
        "更正銀行賬戶證明",
    )
    rebuild_effective_ranges(account.employee.bank_accounts)
    sync_legacy_bank_fields(account.employee)
    write_audit(
        "bank_account_corrected",
        "EmployeeBankAccount",
        account.id,
        employee_id=account.employee_id,
        detail="更正銀行賬戶記錄",
        before=before,
        after=bank_account_snapshot(account),
    )
    db.session.commit()
    flash("銀行賬戶記錄已更正；舊附件仍保留在附件歷史。", "success")
    return employee_redirect(account.employee_id, "personal")


@employees_bp.route("/bank-accounts/<int:account_id>/withdraw", methods=["POST"])
@login_required
def withdraw_bank_account(account_id):
    account = db.get_or_404(EmployeeBankAccount, account_id)
    if account.status != "active":
        return employee_redirect(account.employee_id, "personal")
    before = bank_account_snapshot(account)
    account.status = "voided"
    account.remarks = request.form.get("reason", "").strip() or account.remarks
    rebuild_effective_ranges(account.employee.bank_accounts)
    sync_legacy_bank_fields(account.employee)
    write_audit(
        "bank_account_withdrawn",
        "EmployeeBankAccount",
        account.id,
        employee_id=account.employee_id,
        detail=account.remarks or "撤回銀行賬戶記錄",
        before=before,
        after=bank_account_snapshot(account),
    )
    db.session.commit()
    flash("銀行賬戶記錄已撤回並保留於變更歷史。", "success")
    return employee_redirect(account.employee_id, "personal")


@employees_bp.route("/employees/<int:employee_id>/name", methods=["POST"])
@login_required
def update_name(employee_id):
    employee = db.get_or_404(Employee, employee_id)
    reason = request.form.get("reason")
    if reason not in {"correction", "legal_change"}:
        abort(400)
    evidence = save_evidence(
        employee,
        request.files.get("evidence"),
        "name_change_evidence",
        "改名證明",
    )
    if reason == "legal_change" and not evidence:
        flash("正式改名必須上傳證明。", "error")
        return employee_redirect(employee.id, "personal")
    before = employee_audit_snapshot(employee)
    employee.chinese_name = request.form.get("chinese_name", "").strip() or None
    employee.english_name = request.form.get("english_name", "").strip() or None
    write_audit(
        "employee_name_updated",
        "Employee",
        employee.id,
        employee_id=employee.id,
        detail=(
            "修正系統錄入錯誤"
            if reason == "correction"
            else "員工正式改名"
        ),
        before=before,
        after=employee_audit_snapshot(employee),
    )
    db.session.commit()
    flash("姓名已更新。", "success")
    return employee_redirect(employee.id, "personal")

