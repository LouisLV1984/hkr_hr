"""Shared validation and derived credential state; no persisted workflow state."""
from datetime import date
from functools import wraps

from flask import flash, redirect, request, url_for
from models import EmployeeIdentity, EmployeeCertificate, EmployeeVisa, EmployeeQualification
from tools.hr_core import normalize_identity_number, parse_date


def document_reference_count(document):
    """Count typed references, excluding the document replacement chain itself."""
    from models import db, EmployeeDocument
    count = 0
    with db.session.no_autoflush:
        for mapper in db.Model.registry.mappers:
            if mapper.class_ is EmployeeDocument:
                continue
            for column in mapper.columns:
                if any(fk.target_fullname == "employee_documents.id" for fk in column.foreign_keys):
                    count += db.session.query(mapper.class_).filter(
                        getattr(mapper.class_, column.key) == document.id).count()
    return count


def identity_conflict(identity_type, identity_number, exclude_id=None):
    number = normalize_identity_number(identity_number)
    if not number:
        return None
    return next((item for item in EmployeeIdentity.query.filter_by(
        identity_type=identity_type, status="active").all()
        if item.id != exclude_id and normalize_identity_number(item.identity_number) == number), None)


def validate_credential_dates(start, end, long_term=False, require_expiry=False):
    for raw in (start, end):
        if raw and not parse_date(raw):
            raise ValueError("profile.invalid_date")
    first, last = parse_date(start), parse_date(end)
    if first and last and last < first:
        raise ValueError("profile.date_order")
    if long_term and last:
        raise ValueError("profile.expiry_conflict")
    if require_expiry and not long_term and not last:
        raise ValueError("profile.expiry_required")


def credential_form_validation(kind):
    """Validate before any record/file mutation on either create or correct."""
    def decorate(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            try:
                if kind in {"certificate", "visa"}:
                    from models import db, ReferenceValue
                    field = "certificate_type_id" if kind == "certificate" else "visa_category_id"
                    ref = db.session.get(ReferenceValue, int(request.form.get(field) or 0))
                    expected = "certificate_type" if kind == "certificate" else "visa_category"
                    if not ref or ref.reference_list.code != expected:
                        raise ValueError("profile.invalid_credential_type")
                    if kind == "certificate" and "employee_id" in kwargs and ref.code in {"DEGREE", "SKILL"}:
                        raise ValueError("profile.category_hint")
                validate_credential_dates(
                    request.form.get("valid_from" if kind == "certificate" else "issue_date"),
                    request.form.get("expiry_date"),
                    request.form.get("is_long_term") in {"on", "1", "true"},
                    require_expiry=kind == "certificate",
                )
            except ValueError as error:
                flash(str(error) if str(error).startswith("profile.") else "profile.invalid_credential_type", "error")
                employee_id = kwargs.get("employee_id")
                if not employee_id:
                    model = {"identity": EmployeeIdentity, "certificate": EmployeeCertificate,
                             "visa": EmployeeVisa, "qualification": EmployeeQualification}[kind]
                    from models import db
                    row = db.get_or_404(model, kwargs[f"{kind}_id"])
                    employee_id = row.employee_id
                return redirect(url_for("employees.view_employee", employee_id=employee_id, tab="credentials"))
            return fn(*args, **kwargs)
        return wrapped
    return decorate


def credential_state(item, today=None):
    today = today or date.today()
    if item.status != "active":
        return {"code": "voided", "tone": "muted"}
    start = getattr(item, "valid_from", None) or getattr(item, "issue_date", None)
    if start and start > today:
        return {"code": "future", "tone": "warn"}
    if getattr(item, "is_long_term", False):
        return {"code": "permanent", "tone": "ok"}
    expiry = item.expiry_date
    if not expiry:
        # Degrees are ordinarily permanent; undated work permissions are not.
        permanent = isinstance(item, EmployeeQualification) and item.category == "degree"
        return {"code": "permanent" if permanent else "unknown", "tone": "ok" if permanent else "warn"}
    remaining = (expiry - today).days
    return {"code": "expired" if remaining < 0 else "expiring" if remaining <= 60 else "valid",
            "tone": "danger" if remaining < 0 else "warn" if remaining <= 60 else "ok"}


def credential_alerts(today=None):
    today = today or date.today()
    alerts = []
    for model, kind in ((EmployeeIdentity, "identity"), (EmployeeCertificate, "certificate"),
                        (EmployeeVisa, "visa"), (EmployeeQualification, "qualification")):
        for item in model.query.filter_by(status="active").all():
            if not item.employee.employed_during(today, today):
                continue
            state = credential_state(item, today)
            if state["code"] not in {"expired", "expiring"}:
                continue
            label = (item.identity_type if kind == "identity" else
                     item.certificate_type.display_name if kind == "certificate" else
                     item.visa_category.display_name if kind == "visa" else item.qualification_name)
            alerts.append({"employee": item.employee, "label": label, "date": item.expiry_date,
                           "anchor": f"credential-{kind}-{item.id}"})
    return alerts
