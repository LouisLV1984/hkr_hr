"""SQLAlchemy ORM models owned by the ``references`` module."""
from __future__ import annotations

from datetime import date, datetime, timedelta

from hkr_hr.platform.db import TimestampMixin, db

class ReferenceList(TimestampMixin, db.Model):
    __tablename__ = "reference_lists"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(60), unique=True, nullable=False, index=True)
    label = db.Column(db.String(160), nullable=False)
    active = db.Column(db.Boolean, nullable=False, default=True)

    values = db.relationship(
        "ReferenceValue",
        back_populates="reference_list",
        cascade="all, delete-orphan",
        order_by="ReferenceValue.display_name",
    )


class ReferenceValue(TimestampMixin, db.Model):
    __tablename__ = "reference_values"
    __table_args__ = (
        db.UniqueConstraint("list_id", "code", name="uq_reference_value_code"),
        db.UniqueConstraint(
            "list_id",
            "normalized_name",
            name="uq_reference_value_normalized_name",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    list_id = db.Column(
        db.Integer,
        db.ForeignKey("reference_lists.id"),
        nullable=False,
        index=True,
    )
    code = db.Column(db.String(80), nullable=False, index=True)
    display_name = db.Column(db.String(200), nullable=False, index=True)
    normalized_name = db.Column(db.String(200), nullable=False, index=True)
    active = db.Column(db.Boolean, nullable=False, default=True)
    remarks = db.Column(db.Text, nullable=True)
    metadata_json = db.Column(db.JSON, nullable=True)

    reference_list = db.relationship("ReferenceList", back_populates="values")


class WorkCalendarHoliday(TimestampMixin, db.Model):
    __tablename__ = "work_calendar_holidays"
    __table_args__ = (
        db.UniqueConstraint(
            "region_id",
            "holiday_date",
            name="uq_work_calendar_region_date",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    region_id = db.Column(
        db.Integer,
        db.ForeignKey("reference_values.id"),
        nullable=False,
        index=True,
    )
    holiday_date = db.Column(db.Date, nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False)
    applies_to_statutory = db.Column(
        db.Boolean,
        nullable=False,
        default=True,
        index=True,
    )
    applies_to_public = db.Column(
        db.Boolean,
        nullable=False,
        default=False,
        index=True,
    )
    active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    remarks = db.Column(db.Text, nullable=True)

    region = db.relationship("ReferenceValue", foreign_keys=[region_id])


class WorkProject(TimestampMixin, db.Model):
    __tablename__ = "work_projects"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(80), unique=True, nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False, index=True)
    region_id = db.Column(
        db.Integer,
        db.ForeignKey("reference_values.id"),
        nullable=True,
        index=True,
    )
    work_location = db.Column(db.String(255), nullable=True)
    contact_name = db.Column(db.String(120), nullable=True)
    contact_phone_region = db.Column(db.String(20), nullable=True)
    contact_phone = db.Column(db.String(80), nullable=True)
    daily_ot_divisor = db.Column(db.Numeric(5, 2), nullable=False, default=9)
    active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    remarks = db.Column(db.Text, nullable=True)

    region = db.relationship("ReferenceValue", foreign_keys=[region_id])


class MpfScheme(TimestampMixin, db.Model):
    __tablename__ = "mpf_schemes"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(80), unique=True, nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False, index=True)
    employer_account_no = db.Column(db.String(80), nullable=False)
    payroll_group_no = db.Column(db.String(120), nullable=True)
    calculation_mode = db.Column(db.String(20), nullable=False, default="regular")
    active = db.Column(db.Boolean, nullable=False, default=True, index=True)

    enrollments = db.relationship(
        "EmployeeMpfEnrollment",
        back_populates="scheme",
    )


