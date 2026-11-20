"""Audit log helper shared by all modules."""
from __future__ import annotations

from hkr_hr.platform.db import AuditLog, db


def write_audit(
    action,
    entity_type,
    entity_id=None,
    employee_id=None,
    detail=None,
    before=None,
    after=None,
    user_id=None,
):
    if user_id is None:
        try:
            from flask_login import current_user

            user_id = current_user.id if current_user.is_authenticated else None
        except RuntimeError:
            user_id = None
    db.session.add(
        AuditLog(
            user_id=user_id,
            employee_id=employee_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            before_json=before,
            after_json=after,
            detail=detail,
        )
    )
