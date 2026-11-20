"""Employee workspace routes: credentials."""
from hkr_hr.workbench.web.employees.common import *  # noqa: F401, F403


@employees_bp.route("/employees/<int:employee_id>/identities", methods=["POST"])
@login_required
@credential_form_validation("identity")
def add_identity(employee_id):
    employee = db.get_or_404(Employee, employee_id)
    try:
        old = renewal_source(EmployeeIdentity, employee)
    except ValueError as error:
        flash(str(error), "error")
        return employee_redirect(employee.id, "credentials")
    identity_type = request.form.get("identity_type")
    identity_number = request.form.get("identity_number", "").strip()
    if not identity_type or not identity_number:
        flash("請填寫身份證件類型和號碼。", "error")
        return employee_redirect(employee.id, "credentials")
    conflict = identity_conflict(identity_type, identity_number, renewal=old)
    if conflict:
        flash(
            f"此證件號碼已屬於 {conflict.employee.employee_no} "
            f"{conflict.employee.display_name}，請先核對。",
            "error",
        )
        return employee_redirect(employee.id, "credentials")
    primary = (old.is_primary if old else False) or parse_bool(request.form.get("is_primary")) or not employee.identities
    if primary and not (old and old.is_primary):
        for item in employee.identities:
            item.is_primary = False
    evidence = save_evidence(
        employee,
        request.files.get("evidence"),
        "identity",
        "身份證明",
    )
    identity = EmployeeIdentity(
        renews_id=old.id if old else None,
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
@credential_form_validation("identity")
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
        exclude_id=identity.id, renewal=identity,
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
@credential_form_validation("certificate")
def add_certificate(employee_id):
    employee = db.get_or_404(Employee, employee_id)
    try:
        old = renewal_source(EmployeeCertificate, employee)
    except ValueError as error:
        flash(str(error), "error")
        return employee_redirect(employee.id, "credentials")
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
        renews_id=old.id if old else None,
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
@credential_form_validation("certificate")
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
@credential_form_validation("visa")
def add_visa(employee_id):
    employee = db.get_or_404(Employee, employee_id)
    try:
        old = renewal_source(EmployeeVisa, employee)
    except ValueError as error:
        flash(str(error), "error")
        return employee_redirect(employee.id, "credentials")
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
        renews_id=old.id if old else None,
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
@credential_form_validation("visa")
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
@credential_form_validation("qualification")
def add_qualification(employee_id):
    employee = db.get_or_404(Employee, employee_id)
    try:
        old = renewal_source(EmployeeQualification, employee)
    except ValueError as error:
        flash(str(error), "error")
        return employee_redirect(employee.id, "credentials")
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
        renews_id=old.id if old else None,
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
@credential_form_validation("qualification")
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

