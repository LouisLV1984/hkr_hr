import io
import time
import zipfile
from datetime import date
from decimal import Decimal
from hkr_hr.platform.dates import parse_decimal
from hkr_hr.leave.api import annual_leave_summary
from pathlib import Path
from uuid import uuid4

from docxtpl import DocxTemplate
from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from flask_login import current_user, login_required
from itsdangerous import BadData, URLSafeTimedSerializer

from hkr_hr.attendance.api import AttendanceMonthlySummary
from hkr_hr.employees.api import Employee, EmployeeAssignment, EmployeeBankAccount, EmployeeCertificate, EmployeeEmploymentPeriod, EmployeeIdentity, EmployeeQualification, EmployeeSalary, EmployeeVisa
from hkr_hr.documents.api import EmployeeDocument, GeneratedContract
from hkr_hr.references.api import ReferenceList, ReferenceValue
from hkr_hr.platform.db import db
from hkr_hr.platform.dates import DOCUMENT_CATEGORIES, IDENTITY_TYPE_OPTIONS, REPLACEMENT_REASONS, format_money, masked_bank_account, parse_bool, parse_date
from hkr_hr.platform.files import copy_file_to_employee, file_sha256, store_employee_file, uploaded_file_sha256
from hkr_hr.employees.api import current_bank_account_on, current_assignment_on, current_salary_on, ensure_current_employment_period, rebuild_effective_ranges
from hkr_hr.documents.api import find_duplicate_employee_document
from hkr_hr.references.api import reference_map
from hkr_hr.platform.audit import write_audit
from hkr_hr.platform.security import UploadValidationError, validate_uploaded_file
from hkr_hr.employees.api import identity_conflict, validate_credential_dates
from hkr_hr.employees.api import employee_audit_snapshot
from hkr_hr.platform.dates import normalize_identity_number


documents_bp = Blueprint("documents", __name__)
PENDING_DUPLICATE_MAX_AGE = 60 * 60
DIRECT_UPLOAD_CATEGORIES = {
    code: DOCUMENT_CATEGORIES[code]
    for code in (
        "three_treasures",
        "staff_record",
        "signed_contract",
        "cv",
        "other",
    )
}
SPECIALIST_UPLOAD_CHOICES = (
    ("bank_record", "employee.current_bank", "personal"),
    ("credential_record", "employee.credentials", "credentials"),
    ("employment_record", "employee.employment", "employment"),
    ("probation_record", "employee.current_probation", "employment_status"),
    ("leave_record", "leave.title", "leave"),
    ("work_injury_record", "work_injury.title", "work_injury"),
    ("attendance_record", "attendance.title", "attendance"),
    ("termination_record", "employee.termination", "employment_status"),
    ("name_change_record", "employee.name_change_evidence", "personal"),
    ("salary_record_entry", "salary_record.title", "salary_records"),
)


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
    if file_path.stat().st_size == 0:
        abort(400, description="upload.empty_file")
    return send_file(
        file_path,
        as_attachment=as_attachment,
        download_name=download_name or file_path.name,
        mimetype=mimetype,
    )


def replace_one_document(old_document, new_document, reason):
    if (old_document.status != "active" or not reason or
            old_document.employee_id != new_document.employee_id or
            old_document.category != new_document.category or
            old_document.general_document_type_id != new_document.general_document_type_id):
        abort(400)
    old_document.status = "replaced"
    old_document.replaced_by_document_id = new_document.id
    old_document.replacement_reason = reason
    relink_document_references(old_document, new_document)
    write_audit("document_replaced", "EmployeeDocument", old_document.id,
                employee_id=old_document.employee_id, detail=reason,
                before={"status": "active"}, after={"status": "replaced", "replaced_by_document_id": new_document.id})


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


def validated_upload_or_flash(uploaded, allowed_extensions=None):
    try:
        return validate_uploaded_file(
            uploaded,
            allowed_extensions=allowed_extensions,
        )
    except UploadValidationError as exc:
        flash(str(exc), "error")
        return None


def general_document_types():
    return (
        ReferenceValue.query.join(ReferenceList)
        .filter(
            ReferenceList.code == "general_document_type",
            ReferenceValue.active.is_(True),
        )
        .order_by(ReferenceValue.display_name.asc())
        .all()
    )


def selected_general_document_type(field_name):
    item = db.session.get(ReferenceValue, form_int(field_name))
    if (
        not item
        or not item.active
        or item.reference_list.code != "general_document_type"
    ):
        return None
    return item


def specialist_upload_target(employee, upload_type):
    choice = next(
        (item for item in SPECIALIST_UPLOAD_CHOICES if item[0] == upload_type),
        None,
    )
    if not choice:
        return None
    destination = choice[2]
    if destination == 'salary_records':
        return url_for('salary_records.index', employee_id=employee.id,
                       entity_id=employee.current_assignment.payroll_entity_id if employee.current_assignment else None)
    if destination == "leave":
        return url_for("leave.leave_home", employee_id=employee.id)
    if destination == "work_injury":
        return url_for(
            "leave.leave_home",
            view="injury",
            employee_id=employee.id,
        )
    if destination == "attendance":
        return url_for("attendance.attendance_home", employee_id=employee.id)
    return url_for(
        "employees.view_employee",
        employee_id=employee.id,
        tab=destination,
    )


def render_new_document(employee, **context):
    return render_template(
        "documents/new.html",
        employee=employee,
        categories=DIRECT_UPLOAD_CATEGORIES,
        specialist_choices=SPECIALIST_UPLOAD_CHOICES,
        general_document_types=general_document_types(),
        replacement_reasons=REPLACEMENT_REASONS,
        **context,
    )


def review_source_snapshots(employee):
    snapshots = {}
    for relation in ("identities", "certificates", "visas", "qualifications", "employment_periods"):
        for item in getattr(employee, relation):
            values = {}
            for column in item.__table__.columns:
                value = getattr(item, column.name)
                if column.name not in {"created_at", "updated_at"}:
                    values[column.name] = value if isinstance(value, (str, int, float, bool, type(None))) else str(value)
            snapshots[(type(item).__name__, item.id)] = values
    return snapshots


def audit_review_sources(employee, before, document):
    after = review_source_snapshots(employee)
    for (kind, record_id), values in after.items():
        old = before.get((kind, record_id))
        if old != values:
            write_audit("document_source_updated", kind, record_id, employee_id=employee.id,
                        detail=f"文件人工核對更新（文件 #{document.id}）", before=old, after=values)


def render_document_review(document):
    employee = document.employee
    current_bank = current_bank_account_on(employee, date.today())
    bank_effective_default = (
        current_bank.effective_from
        if current_bank
        else employee.current_period.start_date
        if employee.current_period
        else document.document_date
        or date.today()
    )
    return render_template(
        "documents/review.html",
        employee=employee,
        document=document,
        refs=reference_map(),
        identity_types=IDENTITY_TYPE_OPTIONS,
        current_bank=current_bank,
        bank_effective_default=bank_effective_default,
    )


@documents_bp.route("/employees/<int:employee_id>/documents/new", methods=["GET", "POST"])
@login_required
def new_document(employee_id):
    employee = db.get_or_404(Employee, employee_id)
    upload_type = (
        request.args.get("upload_type")
        or request.args.get("category")
        or ""
    ).strip()
    target = specialist_upload_target(employee, upload_type)
    if target and request.method == "GET":
        return redirect(target)
    selected_category = (
        upload_type if upload_type in DIRECT_UPLOAD_CATEGORIES else ""
    )
    selected_general_type_id = None
    if request.method == "POST":
        uploaded = request.files.get("file")
        category = request.form.get("category")
        selected_category = category if category in DIRECT_UPLOAD_CATEGORIES else ""
        selected_general_type_id = form_int("general_document_type_id")
        general_type = (
            selected_general_document_type("general_document_type_id")
            if category == "other"
            else None
        )
        if category not in DIRECT_UPLOAD_CATEGORIES:
            abort(400)
        replacement = None
        if request.form.get("replace_existing") and not request.form.get("replace_document_id"):
            flash("profile.replace_select", "error")
            return render_new_document(employee, selected_category=category)
        if request.form.get("replace_document_id"):
            replacement = db.get_or_404(EmployeeDocument, form_int("replace_document_id"))
            if (replacement.employee_id != employee.id or replacement.status != "active" or
                    replacement.category != category or
                    replacement.general_document_type_id != (general_type.id if general_type else None) or
                    not request.form.get("replacement_reason", "").strip()):
                abort(400)
        if category == "other" and not general_type:
            flash("請選擇一般附件類型。", "error")
        elif not uploaded or not uploaded.filename:
            flash("請選擇附件類別及文件。", "error")
        elif not (upload_meta := validated_upload_or_flash(uploaded)):
            pass
        else:
            content_sha256 = uploaded_file_sha256(uploaded)
            duplicate = find_duplicate_employee_document(
                employee.id,
                category,
                content_sha256,
            )
            if duplicate:
                if replacement and replacement.id != duplicate.id:
                    flash("profile.replace_duplicate_target", "error")
                    return render_new_document(employee, selected_category=category)
                root = pending_duplicate_root()
                pending_name = (
                    f"{uuid4().hex}{Path(uploaded.filename).suffix.lower()}"
                )
                pending = root / pending_name
                uploaded.save(pending)
                payload = {
                    "employee_id": employee.id,
                    "category": category,
                    "general_document_type_id": (
                        general_type.id if general_type else None
                    ),
                    "title": request.form.get("title", "").strip(),
                    "original_filename": uploaded.filename,
                    "pending_name": pending_name,
                    "mime_type": upload_meta["mime_type"],
                    "file_ext": upload_meta["extension"],
                    "file_size": pending.stat().st_size,
                    "content_sha256": content_sha256,
                    "document_date": request.form.get("document_date", ""),
                    "remarks": request.form.get("remarks", "").strip(),
                    "replace_document_id": replacement.id if replacement else duplicate.id,
                    "replacement_reason": (
                        request.form.get("replacement_reason")
                        or "資料更新"
                    ),
                    "duplicate_id": duplicate.id,
                }
                db.session.commit()
                return render_new_document(
                    employee,
                    selected_category=category,
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
                general_document_type=general_type,
                title=request.form.get("title", "").strip()
                or (
                    general_type.display_name
                    if general_type
                    else DOCUMENT_CATEGORIES[category]
                ),
                original_filename=uploaded.filename,
                stored_path=str(path),
                mime_type=upload_meta["mime_type"],
                file_ext=upload_meta["extension"],
                file_size=path.stat().st_size,
                content_sha256=content_sha256,
                status="active",
                document_date=parse_date(request.form.get("document_date")),
                uploaded_by=current_user.id,
                remarks=request.form.get("remarks", "").strip() or None,
            )
            db.session.add(document)
            db.session.flush()
            if replacement:
                reason = request.form.get("replacement_reason") or "資料更新"
                replace_one_document(replacement, document, reason)
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
    return render_new_document(
        employee,
        selected_category=selected_category,
        selected_general_type_id=selected_general_type_id,
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
    general_type = None
    if category == "other" and payload.get("general_document_type_id"):
        general_type = db.session.get(
            ReferenceValue,
            payload["general_document_type_id"],
        )
        if (
            not general_type
            or general_type.reference_list.code != "general_document_type"
        ):
            path.unlink(missing_ok=True)
            abort(400)
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
        general_document_type=general_type,
        title=payload.get("title")
        or (
            general_type.display_name
            if general_type
            else DOCUMENT_CATEGORIES[category]
        ),
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
    replace_one_document(duplicate, document, reason)
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
    if document.category == 'salary_record':
        flash('salary_record.profile_hint', 'info')
        return redirect(url_for('employees.view_employee',employee_id=document.employee_id,tab='attendance'))
    employee = document.employee
    if request.method == "POST":
        if document.status != "active":
            abort(400)
        try:
            if document.category in {"identity", "three_treasures"}:
                identity_type = request.form.get("identity_type")
                number = request.form.get("identity_number", "").strip()
                if bool(identity_type) != bool(number):
                    raise ValueError("profile.identity_required")
                duplicate_identity = identity_conflict(identity_type, number)
                if duplicate_identity and duplicate_identity.employee_id != employee.id:
                    raise ValueError("profile.identity_duplicate")
                prior = duplicate_identity
                issue = request.form.get("identity_issue_date") or (prior.issue_date.isoformat() if prior and prior.issue_date else None)
                expiry = request.form.get("identity_expiry_date") or (prior.expiry_date.isoformat() if prior and prior.expiry_date else None)
                permanent = parse_bool(request.form.get("identity_long_term")) or bool(prior and prior.is_long_term and not request.form.get("identity_expiry_date"))
                if permanent and not request.form.get("identity_expiry_date"):
                    expiry = None
                validate_credential_dates(issue, expiry, permanent)
                for prefix in ("safety_card", "worker_registration"):
                    if request.form.get(prefix + "_no", "").strip():
                        validate_credential_dates(request.form.get(prefix + "_valid_from"), request.form.get(prefix + "_expiry_date"), parse_bool(request.form.get(prefix + "_long_term")), True)
            if document.category in {"visa", "qualification"}:
                prefix = document.category
                validate_credential_dates(request.form.get(prefix + "_issue_date"), request.form.get(prefix + "_expiry_date"))
            if document.category == "signed_contract" and parse_bool(request.form.get("apply_contract_terms")):
                if not parse_date(request.form.get("contract_effective_date")):
                    raise ValueError("profile.invalid_date")
                value = request.form.get("contract_annual_leave_days", "").strip()
                if value and employee.current_period and employee.current_period.annual_leave_policy_year is not None:
                    from hkr_hr.leave.api import validate_leave_setup as validate
                    validate(employee.current_period.start_date, parse_decimal(value), employee.current_period.end_date)
                if value and (not float(value) >= 0 or float(value) > 366 or float(value) * 2 % 1):
                    raise ValueError("profile.invalid_entitlement")
                if request.form.get("probation_end_date") and not parse_date(request.form.get("probation_end_date")):
                    raise ValueError("profile.invalid_date")
            if document.category == "staff_record" and request.form.get("start_date"):
                start = parse_date(request.form.get("start_date"))
                if not start:
                    raise ValueError("profile.invalid_date")
                current = employee.current_period
                from hkr_hr.leave.api import validate_leave_date_choice as validate_date_choice
                validate_date_choice(employee, start, request.form.get("date_change_action"))
                if current and any(p.id != current.id and (p.end_date is None or p.end_date >= start) for p in employee.employment_periods):
                    raise ValueError("profile.employment_overlap")
                if current and current.end_date and start > current.end_date:
                    raise ValueError("profile.date_order")
        except (ValueError, TypeError) as error:
            key = str(error) if str(error).startswith(("profile.", "leave.")) else "profile.invalid_entitlement"
            flash(key, "error")
            return render_document_review(document)
        before_employee = employee_audit_snapshot(employee)
        before_sources = review_source_snapshots(employee)
        category = document.category
        staff_bank_name = request.form.get("bank_name", "").strip()
        staff_bank_account_no = request.form.get(
            "bank_account_no",
            "",
        ).strip()
        staff_bank_effective_from = parse_date(
            request.form.get("bank_effective_from")
        )
        if category == "staff_record" and bool(staff_bank_name) != bool(
            staff_bank_account_no
        ):
            flash("銀行名稱及賬戶號碼必須同時填寫。", "error")
            return render_document_review(document)
        if (
            category == "staff_record"
            and staff_bank_name
            and not staff_bank_effective_from
        ):
            flash("Staff Record 的銀行資料必須填寫生效日期。", "error")
            return render_document_review(document)
        document.title = request.form.get("title", "").strip() or document.title
        document.document_date = parse_date(request.form.get("document_date"))
        document.remarks = request.form.get("remarks", "").strip() or None

        if category == "staff_record":
            for field in (
                "chinese_name",
                "english_name",
                "gender",
                "mobile_region_code",
                "mobile_number",
                "email",
                "residential_address",
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
                period = ensure_current_employment_period(employee, start_date)
                old_leave = annual_leave_summary(employee, date.today().year)["entitled"]
                changed_start = period.start_date != start_date
                period.start_date = start_date
                if period.annual_leave_policy_year is not None:
                    from hkr_hr.leave.api import save_current_balance
                    balance = save_current_balance(employee)
                    if changed_start:
                        balance.entitled_days_override = (old_leave if request.form.get("date_change_action") == "keep_current" else None)
                    write_audit("annual_leave_balance_updated", "EmployeeAnnualLeaveBalance", balance.id,
                                employee_id=employee.id, detail="員工資料表修正入職日期及本年度年假計算",
                                before={"entitled": str(old_leave)},
                                after={"year": date.today().year, "start_date": str(start_date),
                                       "date_change_action": request.form.get("date_change_action"),
                                       "applied": str(balance.entitled_days_override if balance.entitled_days_override is not None else balance.calculated_entitled_days)})
            if staff_bank_name and staff_bank_effective_from:
                bank_currency = (
                    request.form.get("bank_currency", "HKD").strip()
                    or "HKD"
                ).upper()
                same_effective_date = next(
                    (
                        item
                        for item in employee.bank_accounts
                        if item.status == "active"
                        and item.effective_from == staff_bank_effective_from
                    ),
                    None,
                )
                account_at_date = current_bank_account_on(
                    employee,
                    staff_bank_effective_from,
                )
                if same_effective_date:
                    details_changed = any(
                        (
                            same_effective_date.bank_name != staff_bank_name,
                            same_effective_date.account_no
                            != staff_bank_account_no,
                            same_effective_date.currency != bank_currency,
                        )
                    )
                    before = {
                        "effective_from": same_effective_date.effective_from.isoformat(),
                        "bank_name": same_effective_date.bank_name,
                        "account_no": masked_bank_account(
                            same_effective_date.account_no
                        ),
                        "currency": same_effective_date.currency,
                        "evidence_document_id": (
                            same_effective_date.evidence_document_id
                        ),
                    }
                    same_effective_date.bank_name = staff_bank_name
                    same_effective_date.account_no = staff_bank_account_no
                    same_effective_date.currency = bank_currency
                    if details_changed:
                        same_effective_date.evidence_document = document
                        write_audit(
                            "bank_account_corrected",
                            "EmployeeBankAccount",
                            same_effective_date.id,
                            employee_id=employee.id,
                            detail="按 Staff Record 核對銀行賬戶記錄",
                            before=before,
                            after={
                                "effective_from": (
                                    staff_bank_effective_from.isoformat()
                                ),
                                "bank_name": staff_bank_name,
                                "account_no": masked_bank_account(
                                    staff_bank_account_no
                                ),
                                "currency": bank_currency,
                                "evidence_document_id": document.id,
                            },
                        )
                    elif not same_effective_date.evidence_document_id:
                        same_effective_date.evidence_document = document
                        write_audit(
                            "bank_account_evidence_linked",
                            "EmployeeBankAccount",
                            same_effective_date.id,
                            employee_id=employee.id,
                            detail="以 Staff Record 補充銀行賬戶憑證",
                        )
                elif (
                    account_at_date
                    and account_at_date.bank_name == staff_bank_name
                    and account_at_date.account_no == staff_bank_account_no
                    and account_at_date.currency == bank_currency
                ):
                    if not account_at_date.evidence_document_id:
                        account_at_date.evidence_document = document
                else:
                    account = EmployeeBankAccount(
                        employee=employee,
                        effective_from=staff_bank_effective_from,
                        bank_name=staff_bank_name,
                        account_no=staff_bank_account_no,
                        currency=bank_currency,
                        evidence_document=document,
                        status="active",
                        remarks="由 Staff Record 人工核對建立",
                    )
                    db.session.add(account)
                    db.session.flush()
                    write_audit(
                        "bank_account_added",
                        "EmployeeBankAccount",
                        account.id,
                        employee_id=employee.id,
                        detail=(
                            "按 Staff Record 建立銀行賬戶；"
                            f"由 {staff_bank_effective_from:%Y-%m-%d} 生效"
                        ),
                        after={
                            "effective_from": staff_bank_effective_from.isoformat(),
                            "bank_name": staff_bank_name,
                            "account_no": masked_bank_account(
                                staff_bank_account_no
                            ),
                            "currency": bank_currency,
                            "evidence_document_id": document.id,
                        },
                    )
                rebuild_effective_ranges(employee.bank_accounts)
                current_bank = current_bank_account_on(employee, date.today())
                employee.bank_name = (
                    current_bank.bank_name if current_bank else None
                )
                employee.bank_account_no = (
                    current_bank.account_no if current_bank else None
                )

        if category in {"three_treasures", "identity"}:
            identity_type = request.form.get("identity_type")
            identity_number = request.form.get("identity_number", "").strip()
            if identity_type and identity_number:
                for item in employee.identities:
                    if parse_bool(request.form.get("identity_primary")):
                        item.is_primary = False
                existing = identity_conflict(identity_type, identity_number)
                if existing:
                    existing.is_primary = parse_bool(request.form.get("identity_primary")) or existing.is_primary
                    # Blank review fields do not erase a previously verified date.
                    if request.form.get("identity_issue_date"):
                        existing.issue_date = parse_date(request.form["identity_issue_date"])
                    if parse_bool(request.form.get("identity_long_term")):
                        existing.is_long_term, existing.expiry_date = True, None
                    elif request.form.get("identity_expiry_date"):
                        existing.is_long_term = False
                        existing.expiry_date = parse_date(request.form["identity_expiry_date"])
                    existing.document_id = document.id
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
                    is_long_term = parse_bool(
                        request.form.get(f"{prefix}_long_term")
                    )
                    expiry_date = parse_date(
                        request.form.get(f"{prefix}_expiry_date")
                    )
                    if not is_long_term and not expiry_date:
                        flash("平安卡及工人註冊證必須填寫到期日，或勾選長期有效。", "error")
                        return render_document_review(document)
                    certificate = EmployeeCertificate.query.filter_by(
                        employee_id=employee.id,
                        certificate_type_id=by_code[code].id,
                        certificate_no=number,
                        status="active",
                    ).first()
                    if not certificate:
                        certificate = EmployeeCertificate(
                            employee=employee,
                            certificate_type=by_code[code],
                            certificate_no=number,
                        )
                        db.session.add(certificate)
                    certificate.valid_from = parse_date(
                        request.form.get(f"{prefix}_valid_from")
                    )
                    certificate.expiry_date = expiry_date
                    certificate.is_long_term = is_long_term
                    certificate.document_id = document.id

        if category == "bank_proof":
            bank_name = request.form.get("bank_name", "").strip()
            account_no = request.form.get("bank_account_no", "").strip()
            effective_from = (
                parse_date(request.form.get("bank_effective_from"))
                or document.document_date
                or date.today()
            )
            if bank_name and account_no:
                current = current_bank_account_on(employee, effective_from)
                if current and current.bank_name == bank_name and current.account_no == account_no:
                    current.evidence_document_id = document.id
                else:
                    db.session.add(
                        EmployeeBankAccount(
                            employee=employee,
                            effective_from=effective_from,
                            bank_name=bank_name,
                            account_no=account_no,
                            currency="HKD",
                            status="active",
                            evidence_document_id=document.id,
                        )
                    )
                    db.session.flush()
                    rebuild_effective_ranges(employee.bank_accounts)
                current = current_bank_account_on(employee, date.today())
                employee.bank_name = current.bank_name if current else bank_name
                employee.bank_account_no = current.account_no if current else account_no

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

        if category == "signed_contract" and parse_bool(request.form.get("apply_contract_terms")):
            effective_date = parse_date(request.form.get("contract_effective_date"))
            if effective_date:
                period = ensure_current_employment_period(employee, effective_date)
                if request.form.get("contract_annual_leave_days", "").strip():
                    old_leave = annual_leave_summary(employee, date.today().year)["entitled"]
                    period.contract_annual_leave_days = float(request.form["contract_annual_leave_days"])
                    period.annual_leave_contract_verified = True
                    if period.annual_leave_policy_year is not None:
                        from hkr_hr.leave.api import save_current_balance
                        from hkr_hr.leave.api import validate_leave_setup as validate
                        validate(period.start_date, Decimal(str(period.contract_annual_leave_days)), period.end_date)
                        balance = save_current_balance(employee)
                        write_audit("annual_leave_balance_updated", "EmployeeAnnualLeaveBalance", balance.id,
                                    employee_id=employee.id, detail="合約核對更新初始年假及本年度計算",
                                    before={"entitled": str(old_leave)},
                                    after={"initial_days": str(period.contract_annual_leave_days), "year": date.today().year,
                                           "applied": str(balance.entitled_days_override if balance.entitled_days_override is not None else balance.calculated_entitled_days)})
                if employee.payroll_group == "management" and request.form.get("probation_end_date"):
                    period.probation_end_date = parse_date(
                        request.form.get("probation_end_date")
                    )

        db.session.flush()
        after_employee = employee_audit_snapshot(employee)
        if before_employee != after_employee:
            write_audit("personal_data_updated", "Employee", employee.id,
                        employee_id=employee.id, detail="從文件人工核對更新個人資料",
                        before=before_employee, after=after_employee)
        education_keys = ("education_level", "graduation_school", "major", "graduation_date")
        if any(before_employee.get(key) != after_employee.get(key) for key in education_keys):
            write_audit("education_background_updated", "Employee", employee.id,
                        employee_id=employee.id, detail="從 Staff Record 核對更新學歷",
                        before=before_employee, after=after_employee)
        audit_review_sources(employee, before_sources, document)
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

    return render_document_review(document)


@documents_bp.route("/documents/<int:document_id>/open")
@login_required
def open_document(document_id):
    document = db.get_or_404(EmployeeDocument, document_id)
    if Path(document.original_filename).suffix.lower() == '.pdf' and request.args.get('raw') != '1':
        if not Path(document.stored_path).is_file():
            abort(404)
        return render_template('documents/pdf.html', title=document.original_filename,
            source_url=url_for('documents.open_document', document_id=document.id, raw=1),
            download_url=url_for('documents.download_document', document_id=document.id))
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
    # Include every typed document FK (leave, allowances, MPF and injury too).
    # Replacement-chain pointers are deliberately not relinked.
    for mapper in db.Model.registry.mappers:
        model = mapper.class_
        if model is EmployeeDocument:
            continue
        for column in mapper.columns:
            if any(fk.target_fullname == "employee_documents.id" for fk in column.foreign_keys):
                for row in db.session.query(model).filter(getattr(model, column.key) == old_document.id):
                    setattr(row, column.key, new_document.id)


@documents_bp.route(
    "/documents/<int:document_id>/replace",
    methods=["POST"],
)
@login_required
def replace_document(document_id):
    old_document = db.get_or_404(EmployeeDocument, document_id)
    if old_document.category == 'salary_record':
        flash('salary_record.profile_hint', 'info')
        return redirect(url_for('employees.view_employee',employee_id=old_document.employee_id,tab='attendance'))
    if old_document.status != "active":
        abort(400)
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
    upload_meta = validated_upload_or_flash(uploaded)
    if not upload_meta:
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
        general_document_type_id=old_document.general_document_type_id,
        title=request.form.get("title", "").strip()
        or old_document.title,
        original_filename=uploaded.filename,
        stored_path=str(path),
        mime_type=upload_meta["mime_type"],
        file_ext=upload_meta["extension"],
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
    replace_one_document(old_document, document, reason)
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
    if document.category == 'salary_record':
        flash('salary_record.profile_hint', 'info')
        return redirect(url_for('employees.view_employee',employee_id=document.employee_id,tab='attendance'))
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
    assignment = current_assignment_on(employee, effective_date)
    salary = current_salary_on(employee, effective_date)
    identity = employee.primary_identity
    positions = (
        "、".join(item.position.display_name for item in assignment.positions)
        if assignment
        else ""
    )
    salary_basis = "每月" if salary and salary.salary_basis == "monthly" else "每日"
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
        annual_leave = float(request.form.get("annual_leave_days") or 7)
        notice_period = float(request.form.get("notice_period_days") or 7)
        probation = (
            float(request.form.get("probation_months") or 3)
            if template_code == "OFFICE"
            else 0
        )
        missing = []
        if not effective_date:
            missing.append("合同生效日")
        if not effective_date or not current_assignment_on(employee, effective_date):
            missing.append("任職資料")
        if not effective_date or not current_salary_on(employee, effective_date):
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
                    f"{effective_date:%Y%m%d}_{template_code}_{uuid4().hex[:12]}.docx"
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
                # Draft terms never update the signed employment facts.
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
                    probation_months=probation,
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
        contract_effective_date=parse_date(request.values.get("effective_date")) or (employee.current_period.start_date if employee.current_period else date.today()),
        now_date=date.today().isoformat(),
    )



@documents_bp.get("/employees/<int:employee_id>/contracts/facts")
@login_required
def contract_facts(employee_id):
    employee = db.get_or_404(Employee, employee_id)
    on_date = parse_date(request.args.get("effective_date")) or date.today()
    assignment = current_assignment_on(employee, on_date)
    salary = current_salary_on(employee, on_date)
    return jsonify(project=assignment.project.name if assignment and assignment.project else "—",
                   position="、".join(item.position.display_name for item in assignment.positions) if assignment else "—",
                   salary=f"{salary.currency} {salary.amount:,.2f}" if salary else "—")

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
