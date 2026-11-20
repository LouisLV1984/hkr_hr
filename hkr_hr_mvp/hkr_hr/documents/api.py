"""Public API for the ``documents`` module (L3)."""
from hkr_hr.documents.models import EmployeeDocument, GeneratedContract
from hkr_hr.documents.service.contracts import contract_context
from hkr_hr.documents.service.registry import (
    document_reference_count,
    find_duplicate_employee_document,
    relink_document_references,
)

__all__ = [
    "EmployeeDocument",
    "GeneratedContract",
    "contract_context",
    "document_reference_count",
    "find_duplicate_employee_document",
    "relink_document_references",
]
