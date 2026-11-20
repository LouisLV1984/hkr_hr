"""DB-backed employee credential integrity, renewal, and expiry alert services."""
from __future__ import annotations

from datetime import date
from functools import wraps

from flask import flash, redirect, request, url_for

from hkr_hr.employees.models import (
    EmployeeCertificate,
    EmployeeIdentity,
    EmployeeQualification,
    EmployeeVisa,
)
from hkr_hr.employees.rules.credentials import (
    active_successor,
    credential_state,
    validate_credential_dates,
)
from hkr_hr.platform.dates import normalize_identity_number, parse_date
from hkr_hr.platform.db import db
from hkr_hr.references.api import ReferenceValue


CREDENTIAL_GROUPS = {
    EmployeeIdentity: ("identities", "identity_type"),
    EmployeeCertificate: ("certificates", "certificate_type_id"),
    EmployeeVisa: ("visas", "visa_category_id"),
    EmployeeQualification: ("qualifications", "category"),
}


def identity_conflict(identity_type, identity_number, exclude_id=None, renewal=None):
    number = normalize_identity_number(identity_number)
    if not number:
        return None
    related = set()
    if renewal:
        family = {row.id: row for row in renewal.employee.identities}
        while renewal and renewal.id not in related:
            related.add(renewal.id)
            renewal = family.get(renewal.renews_id)
        for row in sorted(family.values(), key=lambda row: row.id):
            if row.renews_id in related:
                related.add(row.id)
    return next(
        (
            item
            for item in EmployeeIdentity.query.filter_by(
                identity_type=identity_type, status="active"
            ).all()
            if item.id != exclude_id
            and item.id not in related
            and normalize_identity_number(item.identity_number) == number
        ),
        None,
    )


def credential_form_validation(kind):
    """Validate before any record/file mutation on either create or correct."""

    def decorate(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            try:
                if kind in {"certificate", "visa"}:
                    field = (
                        "certificate_type_id"
                        if kind == "certificate"
                        else "visa_category_id"
                    )
                    ref = db.session.get(
                        ReferenceValue, int(request.form.get(field) or 0)
                    )
                    expected = (
                        "certificate_type"
                        if kind == "certificate"
                        else "visa_category"
                    )
                    if not ref or ref.reference_list.code != expected:
                        raise ValueError("profile.invalid_credential_type")
                    if (
                        kind == "certificate"
                        and "employee_id" in kwargs
                        and ref.code in {"DEGREE", "SKILL"}
                    ):
                        raise ValueError("profile.category_hint")
                validate_credential_dates(
                    request.form.get(
                        "valid_from" if kind == "certificate" else "issue_date"
                    ),
                    request.form.get("expiry_date"),
                    request.form.get("is_long_term") in {"on", "1", "true"},
                    require_expiry=kind == "certificate",
                )
            except ValueError as error:
                flash(
                    str(error)
                    if str(error).startswith("profile.")
                    else "profile.invalid_credential_type",
                    "error",
                )
                employee_id = kwargs.get("employee_id")
                if not employee_id:
                    model = {
                        "identity": EmployeeIdentity,
                        "certificate": EmployeeCertificate,
                        "visa": EmployeeVisa,
                        "qualification": EmployeeQualification,
                    }[kind]
                    row = db.get_or_404(model, kwargs[f"{kind}_id"])
                    employee_id = row.employee_id
                return redirect(
                    url_for(
                        "employees.view_employee",
                        employee_id=employee_id,
                        tab="credentials",
                    )
                )
            return fn(*args, **kwargs)

        return wrapped

    return decorate


def renewal_source(model, employee):
    source_id = request.form.get("renews_id", type=int)
    if not source_id:
        return None
    _, type_field = CREDENTIAL_GROUPS[model]
    old = (
        model.query.filter_by(id=source_id, employee_id=employee.id, status="active")
        .with_for_update()
        .first()
    )
    date_field = "valid_from" if model is EmployeeCertificate else "issue_date"
    effective = parse_date(request.form.get(date_field))
    if (
        not old
        or active_successor(old)
        or not effective
        or str(getattr(old, type_field)) != request.form.get(type_field)
        or (getattr(old, date_field) and effective < getattr(old, date_field))
    ):
        raise ValueError("hr.renewal_invalid")
    return old


def credential_alerts(today=None):
    today = today or date.today()
    alerts = []
    for model, kind in (
        (EmployeeIdentity, "identity"),
        (EmployeeCertificate, "certificate"),
        (EmployeeVisa, "visa"),
        (EmployeeQualification, "qualification"),
    ):
        for item in model.query.filter_by(status="active").all():
            if not item.employee.employed_during(today, today):
                continue
            state = credential_state(item, today)
            if state["code"] not in {"expired", "expiring"}:
                continue
            label = (
                item.identity_type
                if kind == "identity"
                else item.certificate_type.display_name
                if kind == "certificate"
                else item.visa_category.display_name
                if kind == "visa"
                else item.qualification_name
            )
            alerts.append(
                {
                    "employee": item.employee,
                    "label": label,
                    "date": item.expiry_date,
                    "anchor": f"credential-{kind}-{item.id}",
                }
            )
    return alerts
