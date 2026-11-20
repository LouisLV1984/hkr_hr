"""Transitional compatibility shim; profile integrity lives in ``hkr_hr.employees`` & ``hkr_hr.documents``."""
from hkr_hr.documents.api import document_reference_count
from hkr_hr.employees.api import (
    CREDENTIAL_GROUPS,
    active_successor,
    credential_alerts,
    credential_form_validation,
    credential_state,
    identity_conflict,
    renewal_source,
    validate_credential_dates,
)

__all__ = [
    "CREDENTIAL_GROUPS",
    "active_successor",
    "credential_alerts",
    "credential_form_validation",
    "credential_state",
    "document_reference_count",
    "identity_conflict",
    "renewal_source",
    "validate_credential_dates",
]
