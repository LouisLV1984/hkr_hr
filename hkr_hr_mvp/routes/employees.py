from datetime import date, datetime
from pathlib import Path

from flask import (
    Blueprint,
    abort,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required
from sqlalchemy import or_

from models import (
    AuditLog,
    AttendanceBatch,
    AttendanceMonthlySummary,
    AttendanceBatchItem,
    Employee,
    EmployeeAnnualLeaveBalance,
    EmployeeAnnualLeaveRecord,
    EmployeeAssignment,
    EmployeeAssignmentPosition,
    EmployeeCertificate,
    EmployeeDocument,
    EmployeeEmploymentPeriod,
    EmployeeIdentity,
    EmployeeQualification,
    EmployeeSalary,
    EmployeeVisa,
    GeneratedContract,
    PayrollAdjustment,
    PayrollEmployeeResult,
    PayrollRun,
    ReferenceValue,
    WorkProject,
    db,
)
from tools.hr_core import (
    DOCUMENT_CATEGORIES,
    IDENTITY_TYPE_OPTIONS,
    PAYROLL_GROUPS,
    TERMINATION_REASONS,
    annual_leave_summary,
    annual_leave_days_between,
    average_wage_prefill,
    create_assignment,
    create_salary,
    current_assignment_on,
    current_month,
    delete_employee_files,
    employee_files_path,
    employee_audit_snapshot,
    ensure_current_employment_period,
    file_sha256,
    format_money,
    masked_bank_account,
    next_employee_no,
    normalize_identity_number,
    parse_bool,
    parse_date,
    parse_decimal,
    reference_map,
    reference_options,
    rebuild_effective_ranges,
    REPLACEMENT_REASONS,
    set_annual_leave_allocations,
    store_employee_file,
    termination_estimate,
    uploaded_file_sha256,
    write_audit,
)


employees_bp = Blueprint("employees", __name__)


def form_int(name):
    try:
        return int(request.form.get(name, "").strip())
    except (TypeError, ValueError):
        return None


def identity_conflict(identity_type, identity_number, exclude_id=None):
    normalized = normalize_identity_number(identity_number)
    if not normalized:
        return None
    query = EmployeeIdentity.query.filter_by(
        identity_type=identity_type,
        status="active",
    )
    if exclude_id:
        query = query.filter(EmployeeIdentity.id != exclude_id)
    return next(
        (
            item
            for item in query.all()
            if normalize_identity_number(item.identity_number) == normalized
        ),
        None,
    )


def employee_redirect(employee_id, tab="overview"):
    return redirect(
        url_for(
            "employees.view_employee",
            employee_id=employee_id,
            tab=tab,
        )
    )


def annual_leave_redirect(employee_id, year=None):
    if request.form.get("return_to") == "annual_leave":
        return redirect(
            url_for(
                "leave.leave_home",
                employee_id=employee_id,
                year=year or date.today().year,
            )
            + "#employee-leave"
        )
    return employee_redirect(employee_id, "leave")


def save_evidence(employee, uploaded, category, title):
    if not uploaded or not uploaded.filename:
        return None
    path = store_employee_file(employee, uploaded, category)
    document = EmployeeDocument(
        employee=employee,
        category=category,
        title=title,
        original_filename=uploaded.filename,
        stored_path=str(path),
        mime_type=uploaded.mimetype,
        file_ext=Path(uploaded.filename).suffix.lower(),
        file_size=path.stat().st_size,
        content_sha256=file_sha256(path),
        status="active",
        uploaded_by=current_user.id,
    )
    db.session.add(document)
    db.session.flush()
    return document


def replace_record_evidence(
    employee,
    current_document,
    uploaded,
    category,
    title,
    replacement_reason="證件資料更新",
):
    if not uploaded or not uploaded.filename:
        return current_document
    digest = uploaded_file_sha256(uploaded)
    if (
        current_document
        and digest
        and digest == (current_document.content_sha256 or "")
    ):
        return current_document
    document = save_evidence(employee, uploaded, category, title)
    if not document or not current_document:
        return document
    linked_rows = sum(
        model.query.filter_by(document_id=current_document.id).count()
        for model in (
            EmployeeIdentity,
            EmployeeCertificate,
            EmployeeVisa,
            EmployeeQualification,
        )
    )
    if linked_rows <= 1 and current_document.status == "active":
        current_document.status = "replaced"
        current_document.replaced_by_document_id = document.id
        current_document.replacement_reason = replacement_reason
    return document


def credential_snapshot(item, fields):
    return {
        field: (
            value.isoformat()
            if isinstance((value := getattr(item, field, None)), date)
            else value
        )
        for field in fields
    }


def assignment_snapshot(assignment):
    return {
        "effective_from": assignment.effective_from.isoformat(),
        "effective_to": (
            assignment.effective_to.isoformat()
            if assignment.effective_to
            else None
        ),
        "region_id": assignment.region_id,
        "project_id": assignment.project_id,
        "department_id": assignment.department_id,
        "payroll_group": assignment.payroll_group,
        "position_ids": [
            item.position_id for item in assignment.positions
        ],
        "status": assignment.status,
        "evidence_document_id": assignment.evidence_document_id,
    }


def salary_snapshot(salary):
    return {
        "effective_from": salary.effective_from.isoformat(),
        "effective_to": (
            salary.effective_to.isoformat() if salary.effective_to else None
        ),
        "salary_basis": salary.salary_basis,
        "currency": salary.currency,
        "amount": str(salary.amount),
        "status": salary.status,
        "evidence_document_id": salary.evidence_document_id,
    }


def employment_period_snapshot(period):
    return {
        "start_date": period.start_date.isoformat(),
        "end_date": period.end_date.isoformat() if period.end_date else None,
        "termination_reason": period.termination_reason,
        "average_wage": (
            str(period.average_wage)
            if period.average_wage is not None
            else None
        ),
        "payment_in_lieu": (
            str(period.payment_in_lieu)
            if period.payment_in_lieu is not None
            else None
        ),
        "severance_payment": (
            str(period.severance_payment)
            if period.severance_payment is not None
            else None
        ),
        "long_service_payment": (
            str(period.long_service_payment)
            if period.long_service_payment is not None
            else None
        ),
        "termination_document_id": period.termination_document_id,
    }


AUDIT_FIELD_LABELS = {
    "effective_from": "audit.field.effective_from",
    "effective_to": "audit.field.effective_to",
    "start_date": "audit.field.start_date",
    "end_date": "audit.field.end_date",
    "year_month": "audit.field.year_month",
    "region_id": "audit.field.region",
    "project_id": "audit.field.project",
    "department_id": "audit.field.department",
    "position_ids": "audit.field.positions",
    "payroll_group": "audit.field.payroll_group",
    "salary_basis": "audit.field.salary_basis",
    "currency": "audit.field.currency",
    "amount": "audit.field.amount",
    "label": "audit.field.label",
    "identity_type": "audit.field.identity_type",
    "identity_number": "audit.field.identity_number",
    "certificate_type_id": "audit.field.certificate_type",
    "certificate_no": "audit.field.certificate_no",
    "visa_category_id": "audit.field.visa_category",
    "visa_no": "audit.field.visa_no",
    "qualification_name": "audit.field.qualification_name",
    "issue_date": "audit.field.issue_date",
    "expiry_date": "audit.field.expiry_date",
    "is_long_term": "audit.field.is_long_term",
    "is_primary": "audit.field.is_primary",
    "status": "audit.field.status",
    "termination_reason": "audit.field.termination_reason",
    "average_wage": "audit.field.average_wage",
    "payment_in_lieu": "audit.field.payment_in_lieu",
    "severance_payment": "audit.field.severance_payment",
    "long_service_payment": "audit.field.long_service_payment",
}

AUDIT_OPTION_CATEGORIES = {
    "identity_type": "identity_type",
    "payroll_group": "payroll_group",
    "salary_basis": "salary_basis",
    "status": "document_status",
    "termination_reason": "termination_reason",
}

AUDIT_REFERENCE_FIELDS = {
    "region_id",
    "department_id",
    "certificate_type_id",
    "visa_category_id",
}


def audit_value(field, value):
    if value in (None, ""):
        return None
    if field == "project_id":
        project = db.session.get(WorkProject, int(value))
        return project.name if project else str(value)
    if field in AUDIT_REFERENCE_FIELDS:
        reference = db.session.get(ReferenceValue, int(value))
        return reference.display_name if reference else str(value)
    if field == "position_ids":
        values = value if isinstance(value, list) else [value]
        names = []
        for item in values:
            reference = db.session.get(ReferenceValue, int(item))
            names.append(reference.display_name if reference else str(item))
        return "、".join(names)
    if field.endswith("_document_id") or field == "document_id":
        document = db.session.get(EmployeeDocument, int(value))
        return document.original_filename if document else str(value)
    if isinstance(value, bool):
        return value
    return str(value)


def audit_change_rows(log):
    before = log.before_json or {}
    after = log.after_json or {}
    rows = []
    for field, label_key in AUDIT_FIELD_LABELS.items():
        if field not in before and field not in after:
            continue
        old_value = before.get(field)
        new_value = after.get(field)
        if old_value == new_value:
            continue
        rows.append(
            {
                "label_key": label_key,
                "before": audit_value(field, old_value),
                "after": audit_value(field, new_value),
                "option_category": AUDIT_OPTION_CATEGORIES.get(field),
                "is_boolean": isinstance(old_value, bool)
                or isinstance(new_value, bool),
            }
        )
    return rows


def audit_timeline_kind(log):
    action = log.action or ""
    entity = log.entity_type or ""
    if action.startswith("assignment_") or entity == "EmployeeAssignment":
        return "employment"
    if action.startswith("salary_") or entity == "EmployeeSalary":
        return "salary"
    if (
        action.startswith(("identity_", "certificate_", "visa_", "qualification_"))
        or entity
        in {
            "EmployeeIdentity",
            "EmployeeCertificate",
            "EmployeeVisa",
            "EmployeeQualification",
        }
    ):
        return "credentials"
    if action.startswith("document_") or entity == "EmployeeDocument":
        return "document"
    if action.startswith("annual_leave_"):
        return "leave"
    if action.startswith("attendance_") or entity == "AttendanceMonthlySummary":
        return "attendance"
    if action.startswith("payroll_"):
        return "payroll"
    if action.startswith(("employment_", "employee_rehired", "probation_")):
        return "termination"
    if action.startswith(("personal_", "employee_name_", "bank_")):
        return "personal"
    return "audit"


def build_timeline(employee):
    rows = []
    for log in AuditLog.query.filter_by(employee_id=employee.id).order_by(
        AuditLog.created_at.desc()
    ):
        rows.append(
            {
                "date": log.created_at,
                "title": log.action,
                "detail": log.detail or "",
                "kind": audit_timeline_kind(log),
                "changes": audit_change_rows(log),
                "author": log.user.username if log.user else "system",
            }
        )
    for document in employee.documents:
        rows.append(
            {
                "date": document.uploaded_at,
                "title": f"附件：{document.title or document.category}",
                "detail": document.original_filename,
                "kind": "document",
                "changes": [],
                "author": None,
            }
        )
    for assignment in employee.assignments:
        rows.append(
            {
                "date": datetime.combine(
                    assignment.effective_from,
                    datetime.min.time(),
                ),
                "title": (
                    "assignment_withdrawn"
                    if assignment.status == "voided"
                    else "任職資料生效"
                ),
                "detail": " / ".join(
                    item
                    for item in [
                        assignment.region.display_name if assignment.region else "",
                        assignment.project.name if assignment.project else "",
                        assignment.department.display_name
                        if assignment.department
                        else "",
                    ]
                    if item
                ),
                "kind": "employment",
                "changes": [],
                "author": None,
            }
        )
    for salary in employee.salaries:
        rows.append(
            {
                "date": datetime.combine(
                    salary.effective_from,
                    datetime.min.time(),
                ),
                "title": (
                    "salary_withdrawn"
                    if salary.status == "voided"
                    else "薪酬資料生效"
                ),
                "detail": (
                    f"{salary.currency} {format_money(salary.amount)} "
                    f"({salary.salary_basis})"
                ),
                "kind": "salary",
                "changes": [],
                "author": None,
            }
        )
    rows.sort(key=lambda item: item["date"], reverse=True)
    return rows


def missing_items(employee):
    missing = []
    categories = {
        item.category
        for item in employee.documents
        if item.status == "active"
    }
    if not employee.current_period:
        missing.append("缺入職日期")
    if not employee.current_assignment:
        missing.append("缺任職資料")
    if not employee.current_salary:
        missing.append("缺薪酬資料")
    if (
        not employee.bank_name
        or not employee.bank_account_no
        or "bank_proof" not in categories
    ):
        missing.append("銀行資料未完成")
    if "staff_record" not in categories:
        missing.append("缺 Staff Record")
    if "signed_contract" not in categories:
        missing.append("缺已簽署合同")
    if employee.payroll_group in {"site_daily", "site_monthly"}:
        if "three_treasures" not in categories:
            missing.append("缺三寶")
    if employee.visa_required and not any(
        item.status == "active" for item in employee.visas
    ):
        missing.append("缺 VISA 資料")
    return missing


def employee_query():
    query = Employee.query
    search = request.args.get("q", "").strip()
    if search:
        like = f"%{search}%"
        query = query.filter(
            or_(
                Employee.employee_no.ilike(like),
                Employee.chinese_name.ilike(like),
                Employee.english_name.ilike(like),
                Employee.mobile_number.ilike(like),
                Employee.email.ilike(like),
            )
        )
    payroll_group = request.args.get("payroll_group", "")
    if payroll_group:
        query = query.filter(Employee.payroll_group == payroll_group)
    employee_type_id = request.args.get("employee_type_id", type=int)
    if employee_type_id:
        query = query.filter(Employee.employee_type_id == employee_type_id)
    project_id = request.args.get("project_id", type=int)
    if project_id:
        query = query.filter(
            Employee.assignments.any(
                EmployeeAssignment.project_id == project_id
            )
        )
    return query.order_by(Employee.employee_no.asc())


@employees_bp.route("/api/employees/next-no")
@login_required
def api_next_employee_no():
    employee_type = db.session.get(ReferenceValue, request.args.get("employee_type_id", type=int))
    if not employee_type:
        return {"employee_no": ""}
    return {"employee_no": next_employee_no(employee_type)}


@employees_bp.route("/employees")
@login_required
def list_employees():
    employees = employee_query().all()
    status = request.args.get("status", "active")
    if status in {"active", "departed"}:
        employees = [
            employee
            for employee in employees
            if employee.derived_status == status
        ]
    return render_template(
        "employees/list.html",
        employees=employees,
        employee_types=reference_options("employee_type"),
        projects=WorkProject.query.filter_by(active=True).order_by(
            WorkProject.name
        ).all(),
        payroll_groups=PAYROLL_GROUPS,
    )


@employees_bp.route("/employees/new", methods=["GET", "POST"])
@login_required
def new_employee():
    employee_types = reference_options("employee_type")
    if request.method == "POST":
        chinese_name = request.form.get("chinese_name", "").strip() or None
        english_name = request.form.get("english_name", "").strip() or None
        employee_type = db.session.get(
            ReferenceValue,
            form_int("employee_type_id"),
        )
        payroll_group = request.form.get("payroll_group", "").strip()
        if not (chinese_name or english_name):
            flash("中文名或英文名至少填寫一項。", "error")
        elif not employee_type:
            flash("請選擇員工編號類別。", "error")
        elif payroll_group not in {item[0] for item in PAYROLL_GROUPS}:
            flash("請選擇 Payroll 組別。", "error")
        else:
            employee = Employee(
                employee_no=next_employee_no(employee_type),
                employee_type=employee_type,
                payroll_group=payroll_group,
                chinese_name=chinese_name,
                english_name=english_name,
                status="active",
            )
            db.session.add(employee)
            db.session.flush()
            write_audit(
                "employee_created",
                "Employee",
                employee.id,
                employee_id=employee.id,
                detail=f"建立員工檔案 {employee.employee_no}",
                after=employee_audit_snapshot(employee),
            )
            db.session.commit()
            flash("員工檔案已建立。", "success")
            return redirect(url_for("employees.view_employee", employee_id=employee.id))
    return render_template(
        "employees/new.html",
        employee_types=employee_types,
        payroll_groups=PAYROLL_GROUPS,
    )


@employees_bp.route("/employees/<int:employee_id>")
@login_required
def view_employee(employee_id):
    employee = db.get_or_404(Employee, employee_id)
    refs = reference_map()
    attendance_rows = AttendanceMonthlySummary.query.filter_by(
        employee_id=employee.id
    ).order_by(AttendanceMonthlySummary.year_month.desc()).all()
    payroll_by_month = {}
    payroll_results = (
        PayrollEmployeeResult.query.join(PayrollRun)
        .filter(PayrollEmployeeResult.employee_id == employee.id)
        .order_by(
            PayrollRun.year_month.desc(),
            PayrollRun.created_at.desc(),
            PayrollEmployeeResult.id.desc(),
        )
        .all()
    )
    for result in payroll_results:
        payroll_by_month.setdefault(result.run.year_month, result)
    return render_template(
        "employees/detail.html",
        employee=employee,
        refs=refs,
        projects=WorkProject.query.filter_by(active=True).order_by(
            WorkProject.name
        ).all(),
        payroll_groups=PAYROLL_GROUPS,
        identity_types=IDENTITY_TYPE_OPTIONS,
        termination_reasons=TERMINATION_REASONS,
        timeline=build_timeline(employee),
        missing=missing_items(employee),
        leave=annual_leave_summary(employee),
        leave_records=EmployeeAnnualLeaveRecord.query.filter_by(
            employee_id=employee.id
        ).order_by(
            EmployeeAnnualLeaveRecord.leave_date.desc(),
            EmployeeAnnualLeaveRecord.id.desc(),
        ).all(),
        average_wage=average_wage_prefill(employee),
        masked_bank=masked_bank_account(employee.bank_account_no),
        contracts=GeneratedContract.query.filter_by(employee_id=employee.id)
        .order_by(GeneratedContract.created_at.desc())
        .all(),
        attendance=attendance_rows,
        payroll_by_month=payroll_by_month,
        payroll_adjustments=PayrollAdjustment.query.filter_by(
            employee_id=employee.id
        ).order_by(
            PayrollAdjustment.year_month.desc(),
            PayrollAdjustment.id.desc(),
        ).all(),
        default_payroll_month=current_month(),
        document_categories=DOCUMENT_CATEGORIES,
        replacement_reasons=REPLACEMENT_REASONS,
    )


@employees_bp.route("/employees/<int:employee_id>/personal", methods=["POST"])
@login_required
def update_personal(employee_id):
    employee = db.get_or_404(Employee, employee_id)
    before = employee_audit_snapshot(employee)
    old_bank = (employee.bank_name, employee.bank_account_no)
    employee.gender = request.form.get("gender") or None
    employee.date_of_birth = parse_date(request.form.get("date_of_birth"))
    employee.mobile_region_code = request.form.get("mobile_region_code") or None
    employee.mobile_number = request.form.get("mobile_number", "").strip() or None
    employee.email = request.form.get("email", "").strip() or None
    employee.residential_address = (
        request.form.get("residential_address", "").strip() or None
    )
    employee.bank_name = request.form.get("bank_name", "").strip() or None
    employee.bank_account_no = (
        request.form.get("bank_account_no", "").strip() or None
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
    employee.education_level = request.form.get("education_level") or None
    employee.major = request.form.get("major", "").strip() or None
    employee.graduation_school = (
        request.form.get("graduation_school", "").strip() or None
    )
    employee.visa_required = parse_bool(request.form.get("visa_required"))
    mpf_mode = request.form.get("mpf_mode")
    if mpf_mode in {"regular", "casual", "exempt"}:
        employee.mpf_mode = mpf_mode
    employee.remarks = request.form.get("remarks", "").strip() or None
    if old_bank != (employee.bank_name, employee.bank_account_no):
        employee.bank_changed_at = datetime.utcnow()
        employee.bank_payroll_confirmed_at = None
    write_audit(
        "personal_data_updated",
        "Employee",
        employee.id,
        employee_id=employee.id,
        detail="更新個人與聯絡資料",
        before=before,
        after=employee_audit_snapshot(employee),
    )
    db.session.commit()
    flash("個人資料已保存。", "success")
    return employee_redirect(employee.id, "personal")


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
    assignment = create_assignment(
        employee=employee,
        effective_from=effective_from,
        payroll_group=request.form.get("payroll_group") or employee.payroll_group,
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
    ensure_current_employment_period(employee, effective_from)
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
    return employee_redirect(employee.id, "employment")


@employees_bp.route("/employees/<int:employee_id>/salary", methods=["POST"])
@login_required
def add_salary(employee_id):
    employee = db.get_or_404(Employee, employee_id)
    effective_from = parse_date(request.form.get("effective_from"))
    amount = parse_decimal(request.form.get("amount"))
    salary_basis = request.form.get("salary_basis")
    if not effective_from or amount is None or salary_basis not in {"monthly", "daily"}:
        flash("請完整填寫薪酬類型、金額及生效日期。", "error")
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
        evidence_document_id=evidence.id if evidence else None,
        remarks=request.form.get("remarks", "").strip() or None,
    )
    write_audit(
        "salary_changed",
        "EmployeeSalary",
        employee_id=employee.id,
        detail=f"薪酬由 {effective_from:%Y-%m-%d} 生效",
        after={
            "basis": salary_basis,
            "currency": salary.currency,
            "amount": str(salary.amount),
            "evidence_missing": evidence is None,
        },
    )
    db.session.commit()
    flash("薪酬資料已保存。", "success")
    return employee_redirect(employee.id, "employment")


def replace_linked_evidence(old_document, new_document, reason):
    if not old_document or old_document.id == new_document.id:
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
        flash("請完整填寫任職生效日期及 Payroll 組別。", "error")
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
    return employee_redirect(assignment.employee_id, "employment")


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
    if (
        not effective_from
        or amount is None
        or salary_basis not in {"monthly", "daily"}
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


@employees_bp.route("/employees/<int:employee_id>/identities", methods=["POST"])
@login_required
def add_identity(employee_id):
    employee = db.get_or_404(Employee, employee_id)
    identity_type = request.form.get("identity_type")
    identity_number = request.form.get("identity_number", "").strip()
    if not identity_type or not identity_number:
        flash("請填寫身份證件類型和號碼。", "error")
        return employee_redirect(employee.id, "credentials")
    conflict = identity_conflict(identity_type, identity_number)
    if conflict:
        flash(
            f"此證件號碼已屬於 {conflict.employee.employee_no} "
            f"{conflict.employee.display_name}，請先核對。",
            "error",
        )
        return employee_redirect(employee.id, "credentials")
    primary = parse_bool(request.form.get("is_primary")) or not employee.identities
    if primary:
        for item in employee.identities:
            item.is_primary = False
    evidence = save_evidence(
        employee,
        request.files.get("evidence"),
        "identity",
        "身份證明",
    )
    identity = EmployeeIdentity(
        employee=employee,
        identity_type=identity_type,
        identity_number=identity_number,
        issue_date=parse_date(request.form.get("issue_date")),
        expiry_date=parse_date(request.form.get("expiry_date")),
        is_long_term=parse_bool(request.form.get("is_long_term")),
        is_primary=primary,
        document_id=evidence.id if evidence else None,
    )
    db.session.add(identity)
    db.session.flush()
    write_audit(
        "identity_added",
        "EmployeeIdentity",
        identity.id,
        employee_id=employee.id,
        detail=f"新增 {identity_type}",
    )
    db.session.commit()
    flash("身份證件已新增。", "success")
    return employee_redirect(employee.id, "credentials")


@employees_bp.route("/identities/<int:identity_id>/update", methods=["POST"])
@login_required
def update_identity(identity_id):
    identity = db.get_or_404(EmployeeIdentity, identity_id)
    if identity.status != "active":
        abort(400)
    identity_type = request.form.get("identity_type", "").strip()
    identity_number = request.form.get("identity_number", "").strip()
    if identity_type not in dict(IDENTITY_TYPE_OPTIONS) or not identity_number:
        flash("請填寫身份證件類型和號碼。", "error")
        return employee_redirect(identity.employee_id, "credentials")
    conflict = identity_conflict(
        identity_type,
        identity_number,
        exclude_id=identity.id,
    )
    if conflict:
        flash(
            f"此證件號碼已屬於 {conflict.employee.employee_no} "
            f"{conflict.employee.display_name}，請先核對。",
            "error",
        )
        return employee_redirect(identity.employee_id, "credentials")
    fields = (
        "identity_type",
        "identity_number",
        "issue_date",
        "expiry_date",
        "is_long_term",
        "is_primary",
        "document_id",
        "remarks",
    )
    before = credential_snapshot(identity, fields)
    identity.identity_type = identity_type
    identity.identity_number = identity_number
    identity.issue_date = parse_date(request.form.get("issue_date"))
    identity.is_long_term = parse_bool(request.form.get("is_long_term"))
    identity.expiry_date = (
        None
        if identity.is_long_term
        else parse_date(request.form.get("expiry_date"))
    )
    identity.remarks = request.form.get("remarks", "").strip() or None
    wants_primary = parse_bool(request.form.get("is_primary"))
    active_others = [
        item
        for item in identity.employee.identities
        if item.id != identity.id and item.status == "active"
    ]
    if wants_primary:
        for item in active_others:
            item.is_primary = False
        identity.is_primary = True
    elif identity.is_primary and active_others:
        identity.is_primary = False
        active_others[0].is_primary = True
    elif not active_others:
        identity.is_primary = True
    evidence = replace_record_evidence(
        identity.employee,
        identity.document,
        request.files.get("evidence"),
        "identity",
        "身份證明",
    )
    if evidence:
        identity.document_id = evidence.id
    write_audit(
        "identity_corrected",
        "EmployeeIdentity",
        identity.id,
        employee_id=identity.employee_id,
        detail=f"更正 {identity_type} 資料",
        before=before,
        after=credential_snapshot(identity, fields),
    )
    db.session.commit()
    flash("身份證件資料已更正。", "success")
    return employee_redirect(identity.employee_id, "credentials")


@employees_bp.route("/identities/<int:identity_id>/void", methods=["POST"])
@login_required
def void_identity(identity_id):
    identity = db.get_or_404(EmployeeIdentity, identity_id)
    fields = (
        "identity_type",
        "identity_number",
        "issue_date",
        "expiry_date",
        "is_long_term",
        "is_primary",
        "document_id",
        "status",
    )
    before = credential_snapshot(identity, fields)
    identity.status = "voided"
    identity.is_primary = False
    replacement = next(
        (
            item
            for item in identity.employee.identities
            if item.id != identity.id and item.status == "active"
        ),
        None,
    )
    if replacement and not any(
        item.is_primary
        for item in identity.employee.identities
        if item.id != identity.id and item.status == "active"
    ):
        replacement.is_primary = True
    write_audit(
        "identity_voided",
        "EmployeeIdentity",
        identity.id,
        employee_id=identity.employee_id,
        detail=request.form.get("reason", "").strip() or "作廢身份證件記錄",
        before=before,
        after=credential_snapshot(identity, fields),
    )
    db.session.commit()
    flash("身份證件已標記作廢，歷史記錄仍然保留。", "success")
    return employee_redirect(identity.employee_id, "credentials")


@employees_bp.route("/identities/<int:identity_id>/replace", methods=["POST"])
@login_required
def replace_identity(identity_id):
    old = db.get_or_404(EmployeeIdentity, identity_id)
    old.status = "replaced"
    if old.is_primary:
        old.is_primary = False
    request.form = request.form.copy()
    return add_identity(old.employee_id)


@employees_bp.route("/employees/<int:employee_id>/certificates", methods=["POST"])
@login_required
def add_certificate(employee_id):
    employee = db.get_or_404(Employee, employee_id)
    certificate_type_id = form_int("certificate_type_id")
    if not certificate_type_id:
        abort(400)
    evidence = save_evidence(
        employee,
        request.files.get("evidence"),
        "qualification",
        "證件附件",
    )
    certificate = EmployeeCertificate(
        employee=employee,
        certificate_type_id=certificate_type_id,
        certificate_no=request.form.get("certificate_no", "").strip() or None,
        valid_from=parse_date(request.form.get("valid_from")),
        expiry_date=parse_date(request.form.get("expiry_date")),
        is_long_term=parse_bool(request.form.get("is_long_term")),
        document_id=evidence.id if evidence else None,
        remarks=request.form.get("remarks", "").strip() or None,
    )
    db.session.add(certificate)
    db.session.flush()
    write_audit(
        "certificate_added",
        "EmployeeCertificate",
        certificate.id,
        employee_id=employee.id,
        detail="新增證件",
    )
    db.session.commit()
    flash("證件已新增。", "success")
    return employee_redirect(employee.id, "credentials")


@employees_bp.route(
    "/certificates/<int:certificate_id>/update",
    methods=["POST"],
)
@login_required
def update_certificate(certificate_id):
    certificate = db.get_or_404(EmployeeCertificate, certificate_id)
    if certificate.status != "active":
        abort(400)
    certificate_type_id = form_int("certificate_type_id")
    if not certificate_type_id:
        flash("請選擇證件類型。", "error")
        return employee_redirect(certificate.employee_id, "credentials")
    fields = (
        "certificate_type_id",
        "certificate_no",
        "valid_from",
        "expiry_date",
        "is_long_term",
        "document_id",
        "remarks",
    )
    before = credential_snapshot(certificate, fields)
    certificate.certificate_type_id = certificate_type_id
    certificate.certificate_no = (
        request.form.get("certificate_no", "").strip() or None
    )
    certificate.valid_from = parse_date(request.form.get("valid_from"))
    certificate.is_long_term = parse_bool(request.form.get("is_long_term"))
    certificate.expiry_date = (
        None
        if certificate.is_long_term
        else parse_date(request.form.get("expiry_date"))
    )
    certificate.remarks = request.form.get("remarks", "").strip() or None
    evidence = replace_record_evidence(
        certificate.employee,
        certificate.document,
        request.files.get("evidence"),
        "qualification",
        "證件附件",
    )
    if evidence:
        certificate.document_id = evidence.id
    write_audit(
        "certificate_corrected",
        "EmployeeCertificate",
        certificate.id,
        employee_id=certificate.employee_id,
        detail="更正證件資料",
        before=before,
        after=credential_snapshot(certificate, fields),
    )
    db.session.commit()
    flash("證件資料已更正。", "success")
    return employee_redirect(certificate.employee_id, "credentials")


@employees_bp.route(
    "/certificates/<int:certificate_id>/void",
    methods=["POST"],
)
@login_required
def void_certificate(certificate_id):
    certificate = db.get_or_404(EmployeeCertificate, certificate_id)
    fields = (
        "certificate_type_id",
        "certificate_no",
        "valid_from",
        "expiry_date",
        "is_long_term",
        "document_id",
        "status",
    )
    before = credential_snapshot(certificate, fields)
    certificate.status = "voided"
    write_audit(
        "certificate_voided",
        "EmployeeCertificate",
        certificate.id,
        employee_id=certificate.employee_id,
        detail=request.form.get("reason", "").strip() or "作廢證件記錄",
        before=before,
        after=credential_snapshot(certificate, fields),
    )
    db.session.commit()
    flash("證件已標記作廢，歷史記錄仍然保留。", "success")
    return employee_redirect(certificate.employee_id, "credentials")


@employees_bp.route("/employees/<int:employee_id>/visas", methods=["POST"])
@login_required
def add_visa(employee_id):
    employee = db.get_or_404(Employee, employee_id)
    visa_category_id = form_int("visa_category_id")
    if not visa_category_id:
        abort(400)
    evidence = save_evidence(
        employee,
        request.files.get("evidence"),
        "visa",
        "VISA 附件",
    )
    visa = EmployeeVisa(
        employee=employee,
        visa_category_id=visa_category_id,
        visa_no=request.form.get("visa_no", "").strip() or None,
        issue_date=parse_date(request.form.get("issue_date")),
        expiry_date=parse_date(request.form.get("expiry_date")),
        document_id=evidence.id if evidence else None,
        remarks=request.form.get("remarks", "").strip() or None,
    )
    db.session.add(visa)
    employee.visa_required = True
    db.session.flush()
    write_audit(
        "visa_added",
        "EmployeeVisa",
        visa.id,
        employee_id=employee.id,
        detail="新增 VISA",
    )
    db.session.commit()
    flash("VISA 已新增。", "success")
    return employee_redirect(employee.id, "credentials")


@employees_bp.route("/visas/<int:visa_id>/update", methods=["POST"])
@login_required
def update_visa(visa_id):
    visa = db.get_or_404(EmployeeVisa, visa_id)
    if visa.status != "active":
        abort(400)
    visa_category_id = form_int("visa_category_id")
    if not visa_category_id:
        flash("請選擇 VISA 類別。", "error")
        return employee_redirect(visa.employee_id, "credentials")
    fields = (
        "visa_category_id",
        "visa_no",
        "issue_date",
        "expiry_date",
        "document_id",
        "remarks",
    )
    before = credential_snapshot(visa, fields)
    visa.visa_category_id = visa_category_id
    visa.visa_no = request.form.get("visa_no", "").strip() or None
    visa.issue_date = parse_date(request.form.get("issue_date"))
    visa.expiry_date = parse_date(request.form.get("expiry_date"))
    visa.remarks = request.form.get("remarks", "").strip() or None
    evidence = replace_record_evidence(
        visa.employee,
        visa.document,
        request.files.get("evidence"),
        "visa",
        "VISA 附件",
    )
    if evidence:
        visa.document_id = evidence.id
    write_audit(
        "visa_corrected",
        "EmployeeVisa",
        visa.id,
        employee_id=visa.employee_id,
        detail="更正 VISA 資料",
        before=before,
        after=credential_snapshot(visa, fields),
    )
    db.session.commit()
    flash("VISA 資料已更正。", "success")
    return employee_redirect(visa.employee_id, "credentials")


@employees_bp.route("/visas/<int:visa_id>/void", methods=["POST"])
@login_required
def void_visa(visa_id):
    visa = db.get_or_404(EmployeeVisa, visa_id)
    fields = (
        "visa_category_id",
        "visa_no",
        "issue_date",
        "expiry_date",
        "document_id",
        "status",
    )
    before = credential_snapshot(visa, fields)
    visa.status = "voided"
    write_audit(
        "visa_voided",
        "EmployeeVisa",
        visa.id,
        employee_id=visa.employee_id,
        detail=request.form.get("reason", "").strip() or "作廢 VISA 記錄",
        before=before,
        after=credential_snapshot(visa, fields),
    )
    db.session.commit()
    flash("VISA 已標記作廢，歷史記錄仍然保留。", "success")
    return employee_redirect(visa.employee_id, "credentials")


@employees_bp.route(
    "/employees/<int:employee_id>/qualifications",
    methods=["POST"],
)
@login_required
def add_qualification(employee_id):
    employee = db.get_or_404(Employee, employee_id)
    category = request.form.get("category", "skill").strip()
    name = request.form.get("qualification_name", "").strip()
    if category not in {"degree", "skill"} or not name:
        flash("請選擇學歷或技能類別並填寫名稱。", "error")
        return employee_redirect(employee.id, "credentials")
    evidence = save_evidence(
        employee,
        request.files.get("evidence"),
        "qualification",
        "學歷 / 技能證書",
    )
    qualification = EmployeeQualification(
        employee=employee,
        category=category,
        qualification_name=name,
        certificate_no=(
            request.form.get("certificate_no", "").strip() or None
        ),
        issue_date=parse_date(request.form.get("issue_date")),
        expiry_date=parse_date(request.form.get("expiry_date")),
        document_id=evidence.id if evidence else None,
        remarks=request.form.get("remarks", "").strip() or None,
        status="active",
    )
    db.session.add(qualification)
    db.session.flush()
    write_audit(
        "qualification_added",
        "EmployeeQualification",
        qualification.id,
        employee_id=employee.id,
        detail=f"新增 {name}",
    )
    db.session.commit()
    flash("學歷 / 技能證書已新增。", "success")
    return employee_redirect(employee.id, "credentials")


@employees_bp.route(
    "/qualifications/<int:qualification_id>/update",
    methods=["POST"],
)
@login_required
def update_qualification(qualification_id):
    qualification = db.get_or_404(EmployeeQualification, qualification_id)
    if qualification.status != "active":
        abort(400)
    category = request.form.get("category", "").strip()
    name = request.form.get("qualification_name", "").strip()
    if category not in {"degree", "skill"} or not name:
        flash("請選擇學歷或技能類別並填寫名稱。", "error")
        return employee_redirect(qualification.employee_id, "credentials")
    fields = (
        "category",
        "qualification_name",
        "certificate_no",
        "issue_date",
        "expiry_date",
        "document_id",
        "remarks",
    )
    before = credential_snapshot(qualification, fields)
    qualification.category = category
    qualification.qualification_name = name
    qualification.certificate_no = (
        request.form.get("certificate_no", "").strip() or None
    )
    qualification.issue_date = parse_date(request.form.get("issue_date"))
    qualification.expiry_date = parse_date(request.form.get("expiry_date"))
    qualification.remarks = request.form.get("remarks", "").strip() or None
    evidence = replace_record_evidence(
        qualification.employee,
        qualification.document,
        request.files.get("evidence"),
        "qualification",
        "學歷 / 技能證書",
    )
    if evidence:
        qualification.document_id = evidence.id
    write_audit(
        "qualification_corrected",
        "EmployeeQualification",
        qualification.id,
        employee_id=qualification.employee_id,
        detail=f"更正 {name}",
        before=before,
        after=credential_snapshot(qualification, fields),
    )
    db.session.commit()
    flash("學歷 / 技能證書資料已更正。", "success")
    return employee_redirect(qualification.employee_id, "credentials")


@employees_bp.route(
    "/qualifications/<int:qualification_id>/void",
    methods=["POST"],
)
@login_required
def void_qualification(qualification_id):
    qualification = db.get_or_404(EmployeeQualification, qualification_id)
    fields = (
        "category",
        "qualification_name",
        "certificate_no",
        "issue_date",
        "expiry_date",
        "document_id",
        "status",
    )
    before = credential_snapshot(qualification, fields)
    qualification.status = "voided"
    write_audit(
        "qualification_voided",
        "EmployeeQualification",
        qualification.id,
        employee_id=qualification.employee_id,
        detail=request.form.get("reason", "").strip() or "作廢學歷 / 技能證書記錄",
        before=before,
        after=credential_snapshot(qualification, fields),
    )
    db.session.commit()
    flash("學歷 / 技能證書已標記作廢，歷史記錄仍然保留。", "success")
    return employee_redirect(qualification.employee_id, "credentials")


@employees_bp.route("/employees/<int:employee_id>/probation", methods=["POST"])
@login_required
def update_probation(employee_id):
    employee = db.get_or_404(Employee, employee_id)
    period = ensure_current_employment_period(
        employee,
        parse_date(request.form.get("start_date")) or date.today(),
    )
    evidence = save_evidence(
        employee,
        request.files.get("evidence"),
        "probation_confirmation",
        "通過試用期申請表",
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
    )
    db.session.commit()
    flash("試用期資料已保存。", "success")
    return employee_redirect(employee.id, "leave")


@employees_bp.route("/employees/<int:employee_id>/annual-leave", methods=["POST"])
@login_required
def add_annual_leave(employee_id):
    employee = db.get_or_404(Employee, employee_id)
    leave_date = parse_date(
        request.form.get("start_date") or request.form.get("leave_date")
    )
    end_date = parse_date(request.form.get("end_date")) or leave_date
    start_session = request.form.get("start_session") or "am"
    end_session = request.form.get("end_session") or "pm"
    calculated_days = annual_leave_days_between(
        leave_date,
        end_date,
        start_session,
        end_session,
    )
    manual_days = parse_decimal(request.form.get("days"))
    days = manual_days if manual_days is not None else calculated_days
    legacy_days = parse_decimal(request.form.get("legacy_days"), parse_decimal("0"))
    regular_days = parse_decimal(request.form.get("regular_days"))
    if regular_days is None and days is not None:
        regular_days = days - legacy_days
    if (
        not leave_date
        or not calculated_days
        or not days
        or days < parse_decimal("0.5")
        or days % parse_decimal("0.5")
        or legacy_days < 0
        or regular_days < 0
        or legacy_days % parse_decimal("0.5")
        or regular_days % parse_decimal("0.5")
        or legacy_days + regular_days != days
    ):
        flash("請填寫正確的年假起止日期；日數以 0.5 日為單位。", "error")
        return annual_leave_redirect(
            employee.id,
            request.form.get("entitlement_year", type=int),
        )
    record = EmployeeAnnualLeaveRecord(
        employee=employee,
        leave_date=leave_date,
        end_date=end_date,
        start_session=start_session,
        end_session=end_session,
        entitlement_year=request.form.get("entitlement_year", type=int)
        or leave_date.year,
        days=days,
        status="active",
        remarks=request.form.get("remarks", "").strip() or None,
        created_by=current_user.id,
    )
    db.session.add(record)
    db.session.flush()
    entitlement_year = record.entitlement_year
    try:
        set_annual_leave_allocations(
            record,
            legacy_days,
            regular_days,
            as_of=leave_date,
        )
    except ValueError:
        db.session.rollback()
        flash("年假結餘不足，請核對 2023 年及以前與 2024 年起的可用日數。", "error")
        return annual_leave_redirect(employee.id, entitlement_year)
    write_audit(
        "annual_leave_added",
        "EmployeeAnnualLeaveRecord",
        employee_id=employee.id,
        detail=(
            f"{leave_date:%Y-%m-%d} 至 {end_date:%Y-%m-%d} "
            f"{days} 日"
        ),
    )
    db.session.commit()
    flash("年假記錄已新增。", "success")
    return annual_leave_redirect(employee.id, record.entitlement_year)


@employees_bp.route(
    "/annual-leave/<int:record_id>/update",
    methods=["POST"],
)
@login_required
def update_annual_leave(record_id):
    record = db.get_or_404(EmployeeAnnualLeaveRecord, record_id)
    employee_id = record.employee_id
    before = {
        "start_date": record.leave_date.isoformat(),
        "end_date": (
            (record.end_date or record.leave_date).isoformat()
        ),
        "start_session": record.start_session,
        "end_session": record.end_session,
        "days": str(record.days),
        "entitlement_year": record.entitlement_year,
        "status": record.status,
    }
    start_date = parse_date(request.form.get("start_date"))
    end_date = parse_date(request.form.get("end_date")) or start_date
    start_session = request.form.get("start_session") or "am"
    end_session = request.form.get("end_session") or "pm"
    calculated = annual_leave_days_between(
        start_date,
        end_date,
        start_session,
        end_session,
    )
    manual = parse_decimal(request.form.get("days"))
    days = manual if manual is not None else calculated
    legacy_days = parse_decimal(request.form.get("legacy_days"), parse_decimal("0"))
    regular_days = parse_decimal(request.form.get("regular_days"))
    if regular_days is None and days is not None:
        regular_days = days - legacy_days
    if (
        not calculated
        or not days
        or days < parse_decimal("0.5")
        or days % parse_decimal("0.5")
        or legacy_days < 0
        or regular_days < 0
        or legacy_days % parse_decimal("0.5")
        or regular_days % parse_decimal("0.5")
        or legacy_days + regular_days != days
    ):
        flash("請填寫正確的年假起止日期；日數以 0.5 日為單位。", "error")
        return annual_leave_redirect(
            record.employee_id,
            request.form.get("entitlement_year", type=int),
        )
    record.leave_date = start_date
    record.end_date = end_date
    record.start_session = start_session
    record.end_session = end_session
    record.days = days
    record.entitlement_year = (
        request.form.get("entitlement_year", type=int) or start_date.year
    )
    record.remarks = request.form.get("remarks", "").strip() or None
    record.status = "active"
    record.allocations.clear()
    db.session.flush()
    try:
        set_annual_leave_allocations(
            record,
            legacy_days,
            regular_days,
            as_of=start_date,
        )
    except ValueError:
        db.session.rollback()
        flash("年假結餘不足，請核對 2023 年及以前與 2024 年起的可用日數。", "error")
        return annual_leave_redirect(
            employee_id,
            request.form.get("entitlement_year", type=int),
        )
    write_audit(
        "annual_leave_corrected",
        "EmployeeAnnualLeaveRecord",
        record.id,
        employee_id=record.employee_id,
        detail=f"{start_date:%Y-%m-%d} 至 {end_date:%Y-%m-%d}，{days} 日",
        before=before,
        after={
            "start_date": record.leave_date.isoformat(),
            "end_date": (record.end_date or record.leave_date).isoformat(),
            "start_session": record.start_session,
            "end_session": record.end_session,
            "days": str(record.days),
            "entitlement_year": record.entitlement_year,
            "status": record.status,
        },
    )
    db.session.commit()
    flash("年假記錄已更正。", "success")
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
        "annual_leave_voided",
        "EmployeeAnnualLeaveRecord",
        record.id,
        employee_id=record.employee_id,
        detail=request.form.get("reason", "").strip() or "撤回錯誤記錄",
        before=before,
        after={"status": record.status, "days": str(record.days)},
    )
    db.session.commit()
    flash("年假記錄已撤回。", "success")
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


@employees_bp.route("/employees/<int:employee_id>/terminate", methods=["POST"])
@login_required
def terminate_employee(employee_id):
    employee = db.get_or_404(Employee, employee_id)
    end_date = parse_date(request.form.get("end_date"))
    reason = request.form.get("reason")
    if not end_date or reason not in {item[0] for item in TERMINATION_REASONS}:
        flash("請填寫最後工作日及離職原因。", "error")
        return employee_redirect(employee.id, "leave")
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
    return employee_redirect(employee.id, "leave")


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
        return employee_redirect(employee.id, "leave")
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
    return employee_redirect(employee.id, "leave")


@employees_bp.route("/employees/<int:employee_id>/rehire", methods=["POST"])
@login_required
def rehire_employee(employee_id):
    employee = db.get_or_404(Employee, employee_id)
    start_date = parse_date(request.form.get("start_date"))
    if not start_date:
        flash("請填寫重新入職日期。", "error")
        return employee_redirect(employee.id, "leave")
    period = EmployeeEmploymentPeriod(employee=employee, start_date=start_date)
    db.session.add(period)
    employee.status = "active"
    write_audit(
        "employee_rehired",
        "EmployeeEmploymentPeriod",
        employee_id=employee.id,
        detail=f"重新入職 {start_date:%Y-%m-%d}",
    )
    db.session.commit()
    flash("已使用原員工編號建立新的任職期間。", "success")
    return employee_redirect(employee.id, "leave")


@employees_bp.route("/employees/<int:employee_id>/bank-confirm", methods=["POST"])
@login_required
def confirm_bank(employee_id):
    employee = db.get_or_404(Employee, employee_id)
    employee.bank_payroll_confirmed_at = datetime.utcnow()
    write_audit(
        "bank_confirmed_for_payroll",
        "Employee",
        employee.id,
        employee_id=employee.id,
        detail="已核對新銀行戶口",
    )
    db.session.commit()
    flash("新銀行戶口已核對，Payroll 阻塞已解除。", "success")
    return employee_redirect(employee.id, "personal")


@employees_bp.route("/employees/<int:employee_id>/delete", methods=["POST"])
@login_required
def delete_employee(employee_id):
    if current_user.role != "admin":
        abort(403)
    employee = db.get_or_404(Employee, employee_id)
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
    flash(f"員工 {employee_no}、考勤及 Payroll 資料已全部刪除。", "success")
    return redirect(url_for("employees.list_employees"))
