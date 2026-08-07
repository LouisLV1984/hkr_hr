import io
import time
import zipfile
from datetime import date
from pathlib import Path
from uuid import uuid4

from docxtpl import DocxTemplate
from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from flask_login import current_user, login_required
from itsdangerous import BadData, URLSafeTimedSerializer

from models import (
    AttendanceMonthlySummary,
    Employee,
    EmployeeAssignment,
    EmployeeCertificate,
    EmployeeDocument,
    EmployeeEmploymentPeriod,
    EmployeeIdentity,
    EmployeeQualification,
    EmployeeSalary,
    EmployeeVisa,
    GeneratedContract,
    ReferenceValue,
    db,
)
from tools.hr_core import (
    DOCUMENT_CATEGORIES,
    IDENTITY_TYPE_OPTIONS,
    REPLACEMENT_REASONS,
    copy_file_to_employee,
    ensure_current_employment_period,
    file_sha256,
    find_duplicate_employee_document,
    format_money,
    parse_bool,
    parse_date,
    reference_map,
    store_employee_file,
    uploaded_file_sha256,
    write_audit,
)


documents_bp = Blueprint("documents", __name__)
PENDING_DUPLICATE_MAX_AGE = 60 * 60


def form_int(name):
    try:
        return int(request.form.get(name, "").strip())
    except (TypeError, ValueError):
        return None


def safe_send(
    path,
    as_attachment=False,
    download_name=None,
    mimetype=None,
):
    file_path = Path(path)
    if not file_path.exists() or not file_path.is_file():
        abort(404)
    return send_file(
        file_path,
        as_attachment=as_attachment,
        download_name=download_name or file_path.name,
        mimetype=mimetype,
    )


def replace_active_category(employee, category, new_document, reason):
    for document in EmployeeDocument.query.filter_by(
        employee_id=employee.id,
        category=category,
        status="active",
    ).filter(EmployeeDocument.id != new_document.id):
        document.status = "replaced"
        document.replaced_by_document_id = new_document.id
        document.replacement_reason = reason


def pending_duplicate_root():
    root = Path(current_app.config["HKR_HR_UPLOAD_ROOT"]) / "_pending_duplicates"
    root.mkdir(parents=True, exist_ok=True)
    cutoff = time.time() - (24 * 60 * 60)
    for path in root.iterdir():
        if path.is_file() and path.stat().st_mtime < cutoff:
            path.unlink(missing_ok=True)
    return root


def duplicate_serializer():
    return URLSafeTimedSerializer(
        current_app.secret_key,
        salt="hkr-hr-duplicate-document",
    )


def pending_path(payload):
    root = pending_duplicate_root().resolve()
    path = (root / str(payload.get("pending_name", ""))).resolve()
    if path.parent != root:
        abort(400)
    return path


@documents_bp.route("/employees/<int:employee_id>/documents/new", methods=["GET", "POST"])
@login_required
def new_document(employee_id):
    employee = db.get_or_404(Employee, employee_id)
    if request.method == "POST":
        uploaded = request.files.get("file")
        category = request.form.get("category")
        if not uploaded or not uploaded.filename or category not in DOCUMENT_CATEGORIES:
            flash("請選擇附件類別及文件。", "error")
        else:
            content_sha256 = uploaded_file_sha256(uploaded)
            duplicate = find_duplicate_employee_document(
                employee.id,
                category,
                content_sha256,
            )
            if duplicate:
                root = pending_duplicate_root()
                pending_name = (
                    f"{uuid4().hex}{Path(uploaded.filename).suffix.lower()}"
                )
                pending = root / pending_name
                uploaded.save(pending)
                payload = {
                    "employee_id": employee.id,
                    "category": category,
                    "title": request.form.get("title", "").strip(),
                    "original_filename": uploaded.filename,
                    "pending_name": pending_name,
                    "mime_type": uploaded.mimetype,
                    "file_ext": Path(uploaded.filename).suffix.lower(),
                    "file_size": pending.stat().st_size,
                    "content_sha256": content_sha256,
                    "document_date": request.form.get("document_date", ""),
                    "remarks": request.form.get("remarks", "").strip(),
                    "replace_existing": parse_bool(
                        request.form.get("replace_existing")
                    ),
                    "replacement_reason": (
                        request.form.get("replacement_reason")
                        or "資料更新"
                    ),
                    "duplicate_id": duplicate.id,
                }
                db.session.commit()
                return render_template(
                    "documents/new.html",
                    employee=employee,
                    categories=DOCUMENT_CATEGORIES,
                    replacement_reasons=REPLACEMENT_REASONS,
                    duplicate_pending={
                        "token": duplicate_serializer().dumps(payload),
                        "filename": uploaded.filename,
                        "existing": duplicate,
                    },
                )
            path = store_employee_file(employee, uploaded, category)
            document = EmployeeDocument(
                employee=employee,
                category=category,
                title=request.form.get("title", "").strip()
                or DOCUMENT_CATEGORIES[category],
                original_filename=uploaded.filename,
                stored_path=str(path),
                mime_type=uploaded.mimetype,
                file_ext=Path(uploaded.filename).suffix.lower(),
                file_size=path.stat().st_size,
                content_sha256=content_sha256,
                status="active",
                document_date=parse_date(request.form.get("document_date")),
                uploaded_by=current_user.id,
                remarks=request.form.get("remarks", "").strip() or None,
            )
            db.session.add(document)
            db.session.flush()
            if parse_bool(request.form.get("replace_existing")):
                reason = request.form.get("replacement_reason") or "資料更新"
                replace_active_category(employee, category, document, reason)
            write_audit(
                "document_uploaded",
                "EmployeeDocument",
                document.id,
                employee_id=employee.id,
                detail=f"{DOCUMENT_CATEGORIES[category]}：{uploaded.filename}",
            )
            db.session.commit()
            return redirect(
                url_for(
                    "documents.review_document",
                    document_id=document.id,
                )
            )
    return render_template(
        "documents/new.html",
        employee=employee,
        categories=DOCUMENT_CATEGORIES,
        replacement_reasons=REPLACEMENT_REASONS,
    )


@documents_bp.route(
    "/employees/<int:employee_id>/documents/duplicate",
    methods=["POST"],
)
@login_required
def resolve_duplicate_document(employee_id):
    employee = db.get_or_404(Employee, employee_id)
    try:
        payload = duplicate_serializer().loads(
            request.form.get("duplicate_token", ""),
            max_age=PENDING_DUPLICATE_MAX_AGE,
        )
    except BadData:
        flash("重複文件確認已過期，請重新選擇文件。", "error")
        return redirect(
            url_for("documents.new_document", employee_id=employee.id)
        )
    if payload.get("employee_id") != employee.id:
        abort(400)
    path = pending_path(payload)
    if request.form.get("action") == "cancel":
        path.unlink(missing_ok=True)
        flash("已取消上傳，原有附件沒有變更。", "info")
        return redirect(
            url_for("documents.new_document", employee_id=employee.id)
        )
    if request.form.get("action") != "replace" or not path.is_file():
        abort(400)
    content_sha256 = file_sha256(path)
    if content_sha256 != payload.get("content_sha256"):
        path.unlink(missing_ok=True)
        abort(400)
    duplicate = db.session.get(
        EmployeeDocument,
        payload.get("duplicate_id"),
    )
    if (
        not duplicate
        or duplicate.employee_id != employee.id
        or duplicate.category != payload.get("category")
        or duplicate.status != "active"
        or (duplicate.content_sha256 or "") != content_sha256
    ):
        path.unlink(missing_ok=True)
        flash("原有附件狀態已變更，請重新上傳。", "error")
        return redirect(
            url_for("documents.new_document", employee_id=employee.id)
        )
    category = payload["category"]
    target = copy_file_to_employee(
        employee,
        path,
        payload["original_filename"],
        category,
    )
    path.unlink(missing_ok=True)
    document = EmployeeDocument(
        employee=employee,
        category=category,
        title=payload.get("title") or DOCUMENT_CATEGORIES[category],
        original_filename=payload["original_filename"],
        stored_path=str(target),
        mime_type=payload.get("mime_type"),
        file_ext=payload.get("file_ext"),
        file_size=target.stat().st_size,
        content_sha256=content_sha256,
        status="active",
        document_date=parse_date(payload.get("document_date")),
        uploaded_by=current_user.id,
        remarks=payload.get("remarks") or None,
    )
    db.session.add(document)
    db.session.flush()
    reason = payload.get("replacement_reason") or "資料更新"
    if payload.get("replace_existing"):
        replace_active_category(employee, category, document, reason)
    else:
        duplicate.status = "replaced"
        duplicate.replaced_by_document_id = document.id
        duplicate.replacement_reason = reason
    write_audit(
        "document_uploaded",
        "EmployeeDocument",
        document.id,
        employee_id=employee.id,
        detail=(
            f"{DOCUMENT_CATEGORIES[category]}："
            f"{payload['original_filename']}（確認替換相同文件）"
        ),
    )
    db.session.commit()
    return redirect(
        url_for("documents.review_document", document_id=document.id)
    )


@documents_bp.route("/documents/<int:document_id>/review", methods=["GET", "POST"])
@login_required
def review_document(document_id):
    document = db.get_or_404(EmployeeDocument, document_id)
    employee = document.employee
    if request.method == "POST":
        document.title = request.form.get("title", "").strip() or document.title
        document.document_date = parse_date(request.form.get("document_date"))
        document.remarks = request.form.get("remarks", "").strip() or None
        category = document.category

        if category == "staff_record":
            for field in (
                "chinese_name",
                "english_name",
                "gender",
                "mobile_region_code",
                "mobile_number",
                "email",
                "residential_address",
                "bank_name",
                "bank_account_no",
                "emergency_contact_name",
                "emergency_contact_region_code",
                "emergency_contact_phone",
                "emergency_contact_relation",
                "education_level",
                "major",
                "graduation_school",
            ):
                value = request.form.get(field)
                if value is not None and str(value).strip():
                    setattr(employee, field, str(value).strip())
            start_date = parse_date(request.form.get("start_date"))
            if start_date:
                ensure_current_employment_period(employee, start_date)

        if category in {"three_treasures", "identity"}:
            identity_type = request.form.get("identity_type")
            identity_number = request.form.get("identity_number", "").strip()
            if identity_type and identity_number:
                for item in employee.identities:
                    if parse_bool(request.form.get("identity_primary")):
                        item.is_primary = False
                existing = EmployeeIdentity.query.filter_by(
                    employee_id=employee.id,
                    identity_type=identity_type,
                    identity_number=identity_number,
                    status="active",
                ).first()
                if not existing:
                    db.session.add(
                        EmployeeIdentity(
                            employee=employee,
                            identity_type=identity_type,
                            identity_number=identity_number,
                            issue_date=parse_date(request.form.get("identity_issue_date")),
                            expiry_date=parse_date(request.form.get("identity_expiry_date")),
                            is_long_term=parse_bool(
                                request.form.get("identity_long_term")
                            ),
                            is_primary=parse_bool(
                                request.form.get("identity_primary")
                            )
                            or not employee.identities,
                            document_id=document.id,
                        )
                    )

        if category == "three_treasures":
            certificate_specs = (
                (
                    "safety_card",
                    "SAFETY_CARD",
                ),
                (
                    "worker_registration",
                    "WORKER_REGISTRATION",
                ),
            )
            refs = reference_map()["certificate_type"]
            by_code = {item.code: item for item in refs}
            for prefix, code in certificate_specs:
                number = request.form.get(f"{prefix}_no", "").strip()
                if number and code in by_code:
                    db.session.add(
                        EmployeeCertificate(
                            employee=employee,
                            certificate_type=by_code[code],
                            certificate_no=number,
                            valid_from=parse_date(
                                request.form.get(f"{prefix}_valid_from")
                            ),
                            expiry_date=parse_date(
                                request.form.get(f"{prefix}_expiry_date")
                            ),
                            is_long_term=parse_bool(
                                request.form.get(f"{prefix}_long_term")
                            ),
                            document_id=document.id,
                        )
                    )

        if category == "bank_proof":
            employee.bank_name = request.form.get("bank_name", "").strip() or None
            employee.bank_account_no = (
                request.form.get("bank_account_no", "").strip() or None
            )

        if category == "visa":
            category_id = form_int("visa_category_id")
            if category_id:
                employee.visa_required = True
                db.session.add(
                    EmployeeVisa(
                        employee=employee,
                        visa_category_id=category_id,
                        visa_no=request.form.get("visa_no", "").strip() or None,
                        issue_date=parse_date(request.form.get("visa_issue_date")),
                        expiry_date=parse_date(request.form.get("visa_expiry_date")),
                        document_id=document.id,
                    )
                )

        if category == "qualification":
            name = request.form.get("qualification_name", "").strip()
            if name:
                db.session.add(
                    EmployeeQualification(
                        employee=employee,
                        category=request.form.get("qualification_category") or "skill",
                        qualification_name=name,
                        certificate_no=request.form.get(
                            "qualification_no",
                            "",
                        ).strip()
                        or None,
                        issue_date=parse_date(
                            request.form.get("qualification_issue_date")
                        ),
                        expiry_date=parse_date(
                            request.form.get("qualification_expiry_date")
                        ),
                        document_id=document.id,
                    )
                )

        if category == "signed_contract":
            effective_date = parse_date(request.form.get("contract_effective_date"))
            if effective_date:
                period = ensure_current_employment_period(employee, effective_date)
                period.contract_annual_leave_days = request.form.get(
                    "contract_annual_leave_days",
                    type=float,
                )
                if employee.payroll_group == "management":
                    period.probation_end_date = parse_date(
                        request.form.get("probation_end_date")
                    )

        write_audit(
            "document_review_saved",
            "EmployeeDocument",
            document.id,
            employee_id=employee.id,
            detail=f"完成 {document.title or document.category} 人工核對",
        )
        db.session.commit()
        flash("附件及資料已保存。", "success")
        return redirect(url_for("employees.view_employee", employee_id=employee.id))

    return render_template(
        "documents/review.html",
        employee=employee,
        document=document,
        refs=reference_map(),
        identity_types=IDENTITY_TYPE_OPTIONS,
    )


@documents_bp.route("/documents/<int:document_id>/open")
@login_required
def open_document(document_id):
    document = db.get_or_404(EmployeeDocument, document_id)
    return safe_send(
        document.stored_path,
        download_name=document.original_filename,
        mimetype=document.mime_type,
    )


@documents_bp.route("/documents/<int:document_id>/download")
@login_required
def download_document(document_id):
    document = db.get_or_404(EmployeeDocument, document_id)
    return safe_send(
        document.stored_path,
        as_attachment=True,
        download_name=document.original_filename,
    )


def relink_document_references(old_document, new_document):
    for item in EmployeeIdentity.query.filter_by(
        document_id=old_document.id
    ):
        item.document_id = new_document.id
    for item in EmployeeCertificate.query.filter_by(
        document_id=old_document.id
    ):
        item.document_id = new_document.id
    for item in EmployeeVisa.query.filter_by(document_id=old_document.id):
        item.document_id = new_document.id
    for item in EmployeeQualification.query.filter_by(
        document_id=old_document.id
    ):
        item.document_id = new_document.id
    for item in EmployeeAssignment.query.filter_by(
        evidence_document_id=old_document.id
    ):
        item.evidence_document_id = new_document.id
    for item in EmployeeSalary.query.filter_by(
        evidence_document_id=old_document.id
    ):
        item.evidence_document_id = new_document.id
    for item in AttendanceMonthlySummary.query.filter_by(
        document_id=old_document.id
    ):
        item.document_id = new_document.id
    for item in GeneratedContract.query.filter_by(
        document_id=old_document.id
    ):
        item.document_id = new_document.id
    for item in EmployeeEmploymentPeriod.query.filter_by(
        confirmation_document_id=old_document.id
    ):
        item.confirmation_document_id = new_document.id
    for item in EmployeeEmploymentPeriod.query.filter_by(
        termination_document_id=old_document.id
    ):
        item.termination_document_id = new_document.id


@documents_bp.route(
    "/documents/<int:document_id>/replace",
    methods=["POST"],
)
@login_required
def replace_document(document_id):
    old_document = db.get_or_404(EmployeeDocument, document_id)
    uploaded = request.files.get("file")
    reason = request.form.get("reason", "").strip()
    if not uploaded or not uploaded.filename or not reason:
        flash("請選擇新文件並填寫替換原因。", "error")
        return redirect(
            url_for(
                "employees.view_employee",
                employee_id=old_document.employee_id,
                tab="documents",
            )
        )
    digest = uploaded_file_sha256(uploaded)
    if (
        digest == (old_document.content_sha256 or "")
        and not parse_bool(request.form.get("confirm_same"))
    ):
        flash("新文件與現有文件完全一致。如仍要替換，請勾選確認。", "info")
        return redirect(
            url_for(
                "employees.view_employee",
                employee_id=old_document.employee_id,
                tab="documents",
            )
        )
    path = store_employee_file(
        old_document.employee,
        uploaded,
        old_document.category,
    )
    document = EmployeeDocument(
        employee=old_document.employee,
        category=old_document.category,
        title=request.form.get("title", "").strip()
        or old_document.title,
        original_filename=uploaded.filename,
        stored_path=str(path),
        mime_type=uploaded.mimetype,
        file_ext=Path(uploaded.filename).suffix.lower(),
        file_size=path.stat().st_size,
        content_sha256=digest,
        status="active",
        document_date=parse_date(request.form.get("document_date"))
        or old_document.document_date,
        effective_month=old_document.effective_month,
        uploaded_by=current_user.id,
        remarks=request.form.get("remarks", "").strip()
        or old_document.remarks,
    )
    db.session.add(document)
    db.session.flush()
    old_document.status = "replaced"
    old_document.replaced_by_document_id = document.id
    old_document.replacement_reason = reason
    relink_document_references(old_document, document)
    write_audit(
        "document_replaced",
        "EmployeeDocument",
        document.id,
        employee_id=document.employee_id,
        detail=(
            f"{old_document.original_filename} → "
            f"{document.original_filename}：{reason}"
        ),
    )
    db.session.commit()
    flash("附件已替換，舊文件已保留為歷史。", "success")
    return redirect(
        url_for(
            "employees.view_employee",
            employee_id=document.employee_id,
            tab="documents",
        )
    )


@documents_bp.route("/documents/<int:document_id>/status", methods=["POST"])
@login_required
def update_document_status(document_id):
    document = db.get_or_404(EmployeeDocument, document_id)
    before = {
        "status": document.status,
        "replacement_reason": document.replacement_reason,
    }
    status = request.form.get("status")
    reason = request.form.get("reason", "").strip()
    if status not in {"active", "replaced", "voided"}:
        abort(400)
    if status != "active" and not reason:
        flash("替換或作廢必須填寫原因。", "error")
    else:
        document.status = status
        document.replacement_reason = reason or None
        write_audit(
            "document_status_changed",
            "EmployeeDocument",
            document.id,
            employee_id=document.employee_id,
            detail=f"{status}: {reason}",
            before=before,
            after={
                "status": document.status,
                "replacement_reason": document.replacement_reason,
            },
        )
        db.session.commit()
        flash("附件狀態已更新。", "success")
    return redirect(url_for("employees.view_employee", employee_id=document.employee_id))


@documents_bp.route("/employees/<int:employee_id>/documents/bundle")
@login_required
def employee_document_bundle(employee_id):
    employee = db.get_or_404(Employee, employee_id)
    memory = io.BytesIO()
    with zipfile.ZipFile(memory, "w", zipfile.ZIP_DEFLATED) as archive:
        for document in EmployeeDocument.query.filter_by(
            employee_id=employee.id,
            status="active",
        ).order_by(EmployeeDocument.category, EmployeeDocument.uploaded_at):
            path = Path(document.stored_path)
            if path.exists():
                archive.write(
                    path,
                    arcname=f"{document.category}/{document.original_filename}",
                )
    memory.seek(0)
    return send_file(
        memory,
        as_attachment=True,
        download_name=f"{employee.employee_no}_{employee.display_name}_attachments.zip",
        mimetype="application/zip",
    )


def contract_context(
    employee,
    contract_date,
    effective_date,
    annual_leave,
    probation,
    notice_period,
):
    assignment = employee.current_assignment
    salary = employee.current_salary
    identity = employee.primary_identity
    positions = (
        "、".join(item.position.display_name for item in assignment.positions)
        if assignment
        else ""
    )
    salary_basis = "每月" if salary.salary_basis == "monthly" else "每日"
    salary_text = (
        f"{salary_basis} {salary.currency} {format_money(salary.amount)}"
        if salary
        else ""
    )
    return {
        "contract_date": (
            f"{contract_date.year:04d}年"
            f"{contract_date.month:02d}月"
            f"{contract_date.day:02d}日"
        ),
        "employee_name": employee.display_name,
        "salutation_name": employee.display_name,
        "salutation": "先生" if employee.gender == "male" else "女士",
        "start_year": effective_date.year,
        "start_month": effective_date.month,
        "start_day": effective_date.day,
        "department_text": (
            f"{assignment.department.display_name} "
            if assignment and assignment.department
            else ""
        ),
        "position_text": positions,
        "work_location": (
            assignment.project.work_location
            or assignment.project.name
            if assignment and assignment.project
            else ""
        ),
        "salary_text": salary_text,
        "probation_months_text": f"{probation:g}個月",
        "contract_annual_leave_text": f"{annual_leave:g}天",
        "notice_period_text": f"{notice_period:g}天",
        "primary_identity_no": identity.identity_number if identity else "",
    }


@documents_bp.route("/employees/<int:employee_id>/contracts/generate", methods=["GET", "POST"])
@login_required
def generate_contract(employee_id):
    employee = db.get_or_404(Employee, employee_id)
    automatic_template = (
        "OFFICE" if employee.payroll_group == "management" else "SITE"
    )
    if request.method == "POST":
        template_code = request.form.get("template_code") or automatic_template
        contract_date = parse_date(request.form.get("contract_date")) or date.today()
        effective_date = parse_date(request.form.get("effective_date"))
        annual_leave = request.form.get("annual_leave_days", type=float) or 7
        notice_period = request.form.get("notice_period_days", type=float) or 7
        probation = (
            request.form.get("probation_months", type=float) or 3
            if template_code == "OFFICE"
            else 0
        )
        missing = []
        if not effective_date:
            missing.append("合同生效日")
        if not employee.current_assignment:
            missing.append("任職資料")
        if not employee.current_salary:
            missing.append("薪酬資料")
        if not employee.primary_identity:
            missing.append("主要身份證件")
        if missing:
            flash("不能生成合同，缺少：" + "、".join(missing), "error")
        elif template_code not in {"SITE", "OFFICE"}:
            abort(400)
        else:
            template_name = f"HKR_{template_code}_Employment_Contract_Template.docx"
            template_path = (
                Path(current_app.config["CONTRACT_TEMPLATE_ROOT"]) / template_name
            )
            if not template_path.exists():
                flash("找不到合同範本。", "error")
            else:
                output_root = Path(current_app.config["GENERATED_CONTRACT_ROOT"])
                output_root.mkdir(parents=True, exist_ok=True)
                output_name = (
                    f"{employee.employee_no}_{employee.display_name}_"
                    f"{effective_date:%Y%m%d}_{template_code}.docx"
                )
                output_path = output_root / output_name
                template = DocxTemplate(template_path)
                template.render(
                    contract_context(
                        employee,
                        contract_date,
                        effective_date,
                        annual_leave,
                        probation,
                        notice_period,
                    )
                )
                template.save(output_path)
                period = employee.current_period
                if period:
                    period.contract_annual_leave_days = annual_leave
                    period.notice_period_value = notice_period
                    period.notice_period_unit = "day"
                document = EmployeeDocument(
                    employee=employee,
                    category="contract_draft",
                    title=f"{template_code} 合同草稿",
                    original_filename=output_name,
                    stored_path=str(output_path),
                    mime_type=(
                        "application/vnd.openxmlformats-officedocument."
                        "wordprocessingml.document"
                    ),
                    file_ext=".docx",
                    file_size=output_path.stat().st_size,
                    content_sha256=file_sha256(output_path),
                    status="active",
                    document_date=contract_date,
                    uploaded_by=current_user.id,
                )
                db.session.add(document)
                db.session.flush()
                generated = GeneratedContract(
                    employee=employee,
                    template_code=template_code,
                    template_name=template_name,
                    output_filename=output_name,
                    output_path=str(output_path),
                    status="draft",
                    contract_date=contract_date,
                    effective_date=effective_date,
                    annual_leave_days=annual_leave,
                    probation_months=probation if probation else None,
                    generated_by=current_user.id,
                    document_id=document.id,
                )
                db.session.add(generated)
                db.session.flush()
                write_audit(
                    "contract_generated",
                    "GeneratedContract",
                    generated.id,
                    employee_id=employee.id,
                    detail=f"生成 {template_code} 合同草稿",
                )
                db.session.commit()
                flash("合同草稿已生成並保存到員工檔案。", "success")
                return redirect(
                    url_for(
                        "documents.download_contract",
                        contract_id=generated.id,
                    )
                )
    return render_template(
        "documents/generate_contract.html",
        employee=employee,
        automatic_template=automatic_template,
        now_date=date.today().isoformat(),
    )


@documents_bp.route("/contracts/<int:contract_id>/download")
@login_required
def download_contract(contract_id):
    contract = db.get_or_404(GeneratedContract, contract_id)
    path = Path(contract.output_path)
    if not path.is_file():
        abort(404)
    package = io.BytesIO()
    with zipfile.ZipFile(package, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.write(path, arcname=contract.output_filename)
        archive.writestr(
            "README.txt",
            (
                "HKR HR contract draft package\n"
                f"Employee: {contract.employee.employee_no} "
                f"{contract.employee.display_name}\n"
                f"Template: {contract.template_name}\n"
                "The DOCX is an editable draft. HR must review it before signing.\n"
            ),
        )
    package.seek(0)
    return send_file(
        package,
        as_attachment=True,
        download_name=f"{Path(contract.output_filename).stem}_package.zip",
        mimetype="application/zip",
    )
