"""Document registry, duplicate detection, and cross-table reference counting."""
from __future__ import annotations

from pathlib import Path

from hkr_hr.documents.models import EmployeeDocument
from hkr_hr.platform.db import db
from hkr_hr.platform.files import file_sha256


def find_duplicate_employee_document(
    employee_id,
    category,
    content_sha256,
    effective_month=None,
):
    digest = str(content_sha256 or "").strip().lower()
    if len(digest) != 64:
        return None
    query = EmployeeDocument.query.filter_by(
        employee_id=employee_id,
        category=category,
        status="active",
    )
    if effective_month is not None:
        query = query.filter_by(effective_month=effective_month)
    for document in query.order_by(EmployeeDocument.id.desc()):
        if not document.content_sha256:
            path = Path(document.stored_path)
            if path.is_file():
                document.content_sha256 = file_sha256(path)
        if (document.content_sha256 or "").lower() == digest:
            return document
    return None


def document_reference_count(document):
    """Count typed references, excluding the document replacement chain itself."""
    count = 0
    with db.session.no_autoflush:
        for mapper in db.Model.registry.mappers:
            if mapper.class_ is EmployeeDocument:
                continue
            for column in mapper.columns:
                if any(
                    fk.target_fullname == "employee_documents.id"
                    for fk in column.foreign_keys
                ):
                    count += (
                        db.session.query(mapper.class_)
                        .filter(getattr(mapper.class_, column.key) == document.id)
                        .count()
                    )
    return count


def relink_document_references(old_document, new_document):
    """Re-point every typed foreign key from old_document to new_document."""
    with db.session.no_autoflush:
        for mapper in db.Model.registry.mappers:
            if mapper.class_ is EmployeeDocument:
                continue
            for column in mapper.columns:
                if any(
                    fk.target_fullname == "employee_documents.id"
                    for fk in column.foreign_keys
                ):
                    (
                        db.session.query(mapper.class_)
                        .filter(getattr(mapper.class_, column.key) == old_document.id)
                        .update({column.key: new_document.id})
                    )
