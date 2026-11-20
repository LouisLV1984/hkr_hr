"""SQLAlchemy ORM models owned by the ``attendance`` module."""
from __future__ import annotations

from datetime import date, datetime, timedelta

from hkr_hr.platform.db import TimestampMixin, db

class AttendanceBatch(TimestampMixin, db.Model):
    __tablename__ = "attendance_batches"

    id = db.Column(db.Integer, primary_key=True)
    batch_no = db.Column(db.String(80), unique=True, nullable=False, index=True)
    year_month = db.Column(db.String(7), nullable=False, index=True)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    status = db.Column(db.String(30), nullable=False, default="open", index=True)

    items = db.relationship(
        "AttendanceBatchItem",
        back_populates="batch",
        cascade="all, delete-orphan",
        order_by="AttendanceBatchItem.id",
    )


class AttendanceBatchItem(TimestampMixin, db.Model):
    __tablename__ = "attendance_batch_items"

    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(
        db.Integer,
        db.ForeignKey("attendance_batches.id"),
        nullable=False,
        index=True,
    )
    archived_summary = db.Column(db.JSON, nullable=True)
    original_filename = db.Column(db.String(255), nullable=False)
    stored_path = db.Column(db.Text, nullable=False)
    mime_type = db.Column(db.String(120), nullable=True)
    file_size = db.Column(db.Integer, nullable=True)
    content_sha256 = db.Column(db.String(64), nullable=True)
    year_month = db.Column(db.String(7), nullable=True, index=True)
    status = db.Column(db.String(30), nullable=False, default="pending", index=True)
    employee_id = db.Column(
        db.Integer,
        db.ForeignKey("employees.id"),
        nullable=True,
        index=True,
    )
    summary_id = db.Column(
        db.Integer,
        db.ForeignKey("attendance_monthly_summaries.id"),
        nullable=True,
    )
    remarks = db.Column(db.Text, nullable=True)

    batch = db.relationship("AttendanceBatch", back_populates="items")
    employee = db.relationship("Employee", foreign_keys=[employee_id])
    summary = db.relationship(
        "AttendanceMonthlySummary",
        foreign_keys=[summary_id],
    )

    @property
    def effective_year_month(self):
        if self.summary:
            return self.summary.year_month
        return self.year_month or (self.batch.year_month if self.batch else None)


class AttendanceMonthlySummary(TimestampMixin, db.Model):
    __tablename__ = "attendance_monthly_summaries"
    __table_args__ = (
        db.UniqueConstraint(
            "employee_id",
            "year_month",
            name="uq_attendance_employee_month",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(
        db.Integer,
        db.ForeignKey("employees.id"),
        nullable=False,
        index=True,
    )
    year_month = db.Column(db.String(7), nullable=False, index=True)
    monthly_project_allocation = db.Column(db.JSON, nullable=True)
    document_id = db.Column(
        db.Integer,
        db.ForeignKey("employee_documents.id"),
        nullable=True,
    )
    status = db.Column(db.String(30), nullable=False, default="received", index=True)
    special_day_handling = db.Column(
        db.String(20),
        nullable=False,
        default="pay",
        index=True,
    )
    no_attendance_reason = db.Column(db.String(255), nullable=True)
    confirmed_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    confirmed_at = db.Column(db.DateTime, nullable=True)
    remarks = db.Column(db.Text, nullable=True)

    employee = db.relationship(
        "Employee",
        back_populates="attendance_summaries",
    )
    document = db.relationship("EmployeeDocument", foreign_keys=[document_id])
    segments = db.relationship(
        "AttendanceSegment",
        back_populates="summary",
        cascade="all, delete-orphan",
        order_by="AttendanceSegment.period_kind, AttendanceSegment.id",
    )
    special_days = db.relationship(
        "AttendanceSpecialDay",
        back_populates="summary",
        cascade="all, delete-orphan",
        order_by="AttendanceSpecialDay.work_date, AttendanceSpecialDay.id",
    )


class AttendanceSegment(TimestampMixin, db.Model):
    rate_allocations = db.Column(db.JSON)
    __tablename__ = "attendance_segments"
    __table_args__ = (
        db.UniqueConstraint(
            "summary_id",
            "period_kind",
            "project_id",
            name="uq_attendance_segment",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    summary_id = db.Column(
        db.Integer,
        db.ForeignKey("attendance_monthly_summaries.id"),
        nullable=False,
        index=True,
    )
    period_kind = db.Column(db.String(30), nullable=False, index=True)
    project_id = db.Column(
        db.Integer,
        db.ForeignKey("work_projects.id"),
        nullable=True,
        index=True,
    )
    working_days = db.Column(db.Numeric(8, 2), nullable=False, default=0)
    ot_hours = db.Column(db.Numeric(8, 2), nullable=False, default=0)
    sunday_holiday_days = db.Column(db.Numeric(8, 2), nullable=False, default=0)
    large_ecall_count = db.Column(db.Integer, nullable=False, default=0)
    ecall_count = db.Column(db.Integer, nullable=False, default=0)
    other_allowance_amount = db.Column(
        db.Numeric(14, 2), nullable=False, default=0
    )

    summary = db.relationship("AttendanceMonthlySummary", back_populates="segments")
    project = db.relationship("WorkProject", foreign_keys=[project_id])


class AttendanceSpecialDay(TimestampMixin, db.Model):
    __tablename__ = "attendance_special_days"
    __table_args__ = (
        db.UniqueConstraint(
            "summary_id",
            "work_date",
            name="uq_attendance_special_day_date",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    summary_id = db.Column(
        db.Integer,
        db.ForeignKey("attendance_monthly_summaries.id"),
        nullable=False,
        index=True,
    )
    segment_id = db.Column(
        db.Integer,
        db.ForeignKey("attendance_segments.id"),
        nullable=True,
        index=True,
    )
    period_kind = db.Column(db.String(30), nullable=False, index=True)
    project_id = db.Column(
        db.Integer,
        db.ForeignKey("work_projects.id"),
        nullable=True,
        index=True,
    )
    work_date = db.Column(db.Date, nullable=False, index=True)
    day_kind = db.Column(db.String(30), nullable=False, index=True)
    session = db.Column(
        db.String(20),
        nullable=False,
        default="full_day",
    )
    handling = db.Column(db.String(20), nullable=False, default="pay", index=True)
    days = db.Column(db.Numeric(4, 1), nullable=False, default=1)
    status = db.Column(db.String(30), nullable=False, default="active", index=True)

    summary = db.relationship("AttendanceMonthlySummary", back_populates="special_days")
    segment = db.relationship("AttendanceSegment", foreign_keys=[segment_id])
    project = db.relationship("WorkProject", foreign_keys=[project_id])
    comp_leave_credit = db.relationship(
        "EmployeeCompLeaveCredit",
        back_populates="source_special_day",
        uselist=False,
    )


correction_documents = db.Table(
    "attendance_correction_documents",
    db.Column("correction_id", db.ForeignKey("attendance_corrections.id"), primary_key=True),
    db.Column("document_id", db.ForeignKey("employee_documents.id"), primary_key=True),
)


class AttendanceCorrection(TimestampMixin, db.Model):
    __tablename__ = "attendance_corrections"
    __table_args__ = (db.UniqueConstraint("employee_id", "source_month", "pay_month"),)
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.ForeignKey("employees.id"), nullable=False, index=True)
    source_month = db.Column(db.String(7), nullable=False, index=True)
    pay_month = db.Column(db.String(7), nullable=False, index=True)
    lines = db.Column(db.JSON, nullable=False)
    currency = db.Column(db.String(8), nullable=False)
    amount = db.Column(db.Numeric(14, 2), nullable=False)
    edited_by = db.Column(db.ForeignKey("users.id"), nullable=False)
    editor = db.relationship("User")
    revision = db.Column(db.Integer, nullable=False, default=1)
    __mapper_args__ = {"version_id_col": revision}
    documents = db.relationship("EmployeeDocument", secondary=correction_documents,
                                order_by="EmployeeDocument.id")

    @property
    def edited_hk(self):
        return (self.updated_at + timedelta(hours=8)).strftime("%Y-%m-%d %H:%M")


