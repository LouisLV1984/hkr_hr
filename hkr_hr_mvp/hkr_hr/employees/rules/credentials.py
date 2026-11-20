"""Pure employee credential state and effective-date range rules (zero Flask/DB)."""
from __future__ import annotations

from datetime import date, timedelta

from hkr_hr.platform.dates import parse_date


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


def _credential_group_attr(item) -> str:
    cls_name = type(item).__name__
    return {
        "EmployeeIdentity": "identities",
        "EmployeeCertificate": "certificates",
        "EmployeeVisa": "visas",
        "EmployeeQualification": "qualifications",
    }[cls_name]


def active_successor(item):
    group = _credential_group_attr(item)
    return next(
        (
            row
            for row in getattr(item.employee, group)
            if row.renews_id == item.id and row.status == "active"
        ),
        None,
    )


def credential_state(item, today=None):
    today = today or date.today()
    if item.status != "active":
        return {"code": "voided", "tone": "muted"}
    successor = active_successor(item)
    if (
        successor
        and (
            getattr(successor, "valid_from", None)
            or getattr(successor, "issue_date", None)
            or today
        )
        <= today
    ):
        return {"code": "renewed", "tone": "muted"}
    start = getattr(item, "valid_from", None) or getattr(item, "issue_date", None)
    if start and start > today:
        return {"code": "future", "tone": "warn"}
    if getattr(item, "is_long_term", False):
        return {"code": "permanent", "tone": "ok"}
    expiry = item.expiry_date
    if not expiry:
        # Degrees are ordinarily permanent; undated work permissions are not.
        permanent = (
            type(item).__name__ == "EmployeeQualification"
            and getattr(item, "category", None) == "degree"
        )
        return {
            "code": "permanent" if permanent else "unknown",
            "tone": "ok" if permanent else "warn",
        }
    remaining = (expiry - today).days
    return {
        "code": "expired" if remaining < 0 else "expiring" if remaining <= 60 else "valid",
        "tone": "danger" if remaining < 0 else "warn" if remaining <= 60 else "ok",
    }


def current_bank_account_on(employee, on_date):
    rows = [
        row
        for row in employee.bank_accounts
        if row.status == "active"
        and row.effective_from <= on_date
        and (row.effective_to is None or row.effective_to >= on_date)
    ]
    return rows[0] if rows else None


def current_assignment_on(employee, on_date):
    rows = [
        row
        for row in employee.assignments
        if row.status == "active"
        and row.effective_from <= on_date
        and (row.effective_to is None or row.effective_to >= on_date)
    ]
    return rows[0] if rows else None


def current_salary_on(employee, on_date):
    rows = [
        row
        for row in employee.salaries
        if row.status == "active"
        and row.effective_from <= on_date
        and (row.effective_to is None or row.effective_to >= on_date)
    ]
    return rows[0] if rows else None


def current_mpf_on(employee, on_date):
    rows = [
        row
        for row in employee.mpf_enrollments
        if row.status == "active"
        and row.effective_from <= on_date
        and (row.effective_to is None or row.effective_to >= on_date)
    ]
    return rows[0] if rows else None


def close_previous_record(records, effective_from):
    for item in records:
        if getattr(item, "status", "active") != "active":
            continue
        if item.effective_from < effective_from and (
            item.effective_to is None or item.effective_to >= effective_from
        ):
            item.effective_to = effective_from - timedelta(days=1)


def rebuild_effective_ranges(records):
    active = sorted(
        (
            item
            for item in records
            if getattr(item, "status", "active") == "active"
        ),
        key=lambda item: (item.effective_from, item.id or 0),
    )
    for index, item in enumerate(active):
        item.effective_to = (
            active[index + 1].effective_from - timedelta(days=1)
            if index + 1 < len(active)
            else None
        )
    return active
