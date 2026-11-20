"""SQLAlchemy ORM models owned by the ``documents`` module."""
from __future__ import annotations

from datetime import date, datetime, timedelta

from hkr_hr.platform.db import TimestampMixin, db

class EmployeeDocument(TimestampMixin, db.Model):
    __tablename__ = "employee_documents"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(
        db.Integer,
        db.ForeignKey("employees.id"),
        nullable=False,
        index=True,
    )
    category = db.Column(db.String(60), nullable=False, index=True)
    general_document_type_id = db.Column(
        db.Integer,
        db.ForeignKey("reference_values.id"),
        nullable=True,
        index=True,
    )
    title = db.Column(db.String(200), nullable=True)
    original_filename = db.Column(db.String(255), nullable=False)
    stored_path = db.Column(db.Text, nullable=False)
    mime_type = db.Column(db.String(120), nullable=True)
    file_ext = db.Column(db.String(20), nullable=True)
    file_size = db.Column(db.Integer, nullable=True)
    content_sha256 = db.Column(db.String(64), nullable=True)
    status = db.Column(db.String(30), nullable=False, default="active", index=True)
    document_date = db.Column(db.Date, nullable=True)
    effective_month = db.Column(db.String(7), nullable=True, index=True)
    replacement_reason = db.Column(db.String(120), nullable=True)
    replaced_by_document_id = db.Column(
        db.Integer,
        db.ForeignKey("employee_documents.id"),
        nullable=True,
    )
    uploaded_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    uploaded_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    remarks = db.Column(db.Text, nullable=True)

    employee = db.relationship(
        "Employee",
        back_populates="documents",
        foreign_keys=[employee_id],
    )
    replaced_by = db.relationship(
        "EmployeeDocument",
        remote_side=[id],
        foreign_keys=[replaced_by_document_id],
    )
    general_document_type = db.relationship(
        "ReferenceValue",
        foreign_keys=[general_document_type_id],
    )


class GeneratedContract(TimestampMixin, db.Model):
    __tablename__ = "generated_contracts"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(
        db.Integer,
        db.ForeignKey("employees.id"),
        nullable=False,
        index=True,
    )
    template_code = db.Column(db.String(30), nullable=False)
    template_name = db.Column(db.String(255), nullable=False)
    output_filename = db.Column(db.String(255), nullable=False)
    output_path = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(30), nullable=False, default="draft", index=True)
    contract_date = db.Column(db.Date, nullable=False)
    effective_date = db.Column(db.Date, nullable=False)
    annual_leave_days = db.Column(db.Numeric(5, 1), nullable=False, default=7)
    probation_months = db.Column(db.Numeric(5, 1), nullable=True)
    generated_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    document_id = db.Column(
        db.Integer,
        db.ForeignKey("employee_documents.id"),
        nullable=True,
    )

    employee = db.relationship(
        "Employee",
        back_populates="generated_contracts",
    )
    document = db.relationship("EmployeeDocument", foreign_keys=[document_id])


