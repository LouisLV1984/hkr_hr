"""SQLAlchemy ORM models owned by the ``leave`` module."""
from __future__ import annotations

from datetime import date, datetime, timedelta

from hkr_hr.platform.db import TimestampMixin, db

class EmployeeAnnualLeaveBalance(TimestampMixin, db.Model):
    __tablename__ = "employee_annual_leave_balances"
    __table_args__ = (
        db.UniqueConstraint(
            "employee_id",
            "year",
            name="uq_employee_leave_balance_year",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(
        db.Integer,
        db.ForeignKey("employees.id"),
        nullable=False,
        index=True,
    )
    year = db.Column(db.Integer, nullable=False, index=True)
    entitled_days_override = db.Column(db.Numeric(5, 1), nullable=True)
    calculated_entitled_days = db.Column(db.Numeric(5, 1), nullable=True)
    calculated_annual_rate = db.Column(db.Numeric(5, 1), nullable=True)
    calculation_start_date = db.Column(db.Date, nullable=True)
    carried_from_previous_days = db.Column(
        db.Numeric(5, 1),
        nullable=False,
        default=0,
    )
    manual_adjustment_days = db.Column(db.Numeric(5, 1), nullable=False, default=0)
    expiry_date = db.Column(db.Date, nullable=True, index=True)
    extended_until = db.Column(db.Date, nullable=True, index=True)
    remarks = db.Column(db.Text, nullable=True)

    employee = db.relationship(
        "Employee",
        back_populates="annual_leave_balances",
    )
    allocations = db.relationship(
        "EmployeeAnnualLeaveAllocation",
        back_populates="balance",
        cascade="all, delete-orphan",
    )


class EmployeeAnnualLeaveRecord(TimestampMixin, db.Model):
    __tablename__ = "employee_annual_leave_records"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(
        db.Integer,
        db.ForeignKey("employees.id"),
        nullable=False,
        index=True,
    )
    leave_date = db.Column(db.Date, nullable=False, index=True)
    end_date = db.Column(db.Date, nullable=True, index=True)
    start_session = db.Column(
        db.String(20),
        nullable=False,
        default="am",
    )
    end_session = db.Column(
        db.String(20),
        nullable=False,
        default="pm",
    )
    entitlement_year = db.Column(db.Integer, nullable=False, index=True)
    days = db.Column(db.Numeric(4, 1), nullable=False)
    # NULL preserves legacy calendar-day records until HR explicitly corrects them.
    leave_units_json = db.Column(db.JSON, nullable=True)
    leave_type = db.Column(
        db.String(30),
        nullable=False,
        default="annual",
        index=True,
    )
    evidence_document_id = db.Column(
        db.Integer,
        db.ForeignKey("employee_documents.id"),
        nullable=True,
    )
    status = db.Column(
        db.String(30),
        nullable=False,
        default="active",
        index=True,
    )
    remarks = db.Column(db.Text, nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    employee = db.relationship(
        "Employee",
        back_populates="annual_leave_records",
    )
    allocations = db.relationship(
        "EmployeeAnnualLeaveAllocation",
        back_populates="record",
        cascade="all, delete-orphan",
    )
    comp_leave_allocations = db.relationship(
        "EmployeeCompLeaveAllocation",
        back_populates="leave_record",
        cascade="all, delete-orphan",
    )
    evidence_document = db.relationship(
        "EmployeeDocument",
        foreign_keys=[evidence_document_id],
    )


class EmployeeAnnualLeaveAllocation(TimestampMixin, db.Model):
    __tablename__ = "employee_annual_leave_allocations"

    id = db.Column(db.Integer, primary_key=True)
    record_id = db.Column(
        db.Integer,
        db.ForeignKey("employee_annual_leave_records.id"),
        nullable=False,
        index=True,
    )
    balance_id = db.Column(
        db.Integer,
        db.ForeignKey("employee_annual_leave_balances.id"),
        nullable=False,
        index=True,
    )
    days = db.Column(db.Numeric(6, 1), nullable=False)

    record = db.relationship(
        "EmployeeAnnualLeaveRecord",
        back_populates="allocations",
    )
    balance = db.relationship(
        "EmployeeAnnualLeaveBalance",
        back_populates="allocations",
    )


class EmployeeCompLeaveCredit(TimestampMixin, db.Model):
    __tablename__ = "employee_comp_leave_credits"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(
        db.Integer,
        db.ForeignKey("employees.id"),
        nullable=False,
        index=True,
    )
    source_special_day_id = db.Column(
        db.Integer,
        db.ForeignKey("attendance_special_days.id"),
        # A corrected attendance record keeps its voided compensation-leave
        # audit entry even after the superseded special-day row is removed.
        nullable=True,
        unique=True,
        index=True,
    )
    source_date = db.Column(db.Date, nullable=False, index=True)
    source_kind = db.Column(db.String(30), nullable=False, index=True)
    days = db.Column(db.Numeric(6, 1), nullable=False, default=1)
    status = db.Column(db.String(30), nullable=False, default="active", index=True)
    remarks = db.Column(db.Text, nullable=True)

    employee = db.relationship("Employee", back_populates="comp_leave_credits")
    source_special_day = db.relationship(
        "AttendanceSpecialDay",
        back_populates="comp_leave_credit",
    )
    allocations = db.relationship(
        "EmployeeCompLeaveAllocation",
        back_populates="credit",
        cascade="all, delete-orphan",
    )


class EmployeeCompLeaveAllocation(TimestampMixin, db.Model):
    __tablename__ = "employee_comp_leave_allocations"

    id = db.Column(db.Integer, primary_key=True)
    leave_record_id = db.Column(
        db.Integer,
        db.ForeignKey("employee_annual_leave_records.id"),
        nullable=False,
        index=True,
    )
    credit_id = db.Column(
        db.Integer,
        db.ForeignKey("employee_comp_leave_credits.id"),
        nullable=False,
        index=True,
    )
    days = db.Column(db.Numeric(6, 1), nullable=False)

    leave_record = db.relationship(
        "EmployeeAnnualLeaveRecord",
        back_populates="comp_leave_allocations",
    )
    credit = db.relationship(
        "EmployeeCompLeaveCredit",
        back_populates="allocations",
    )


class EmployeeWorkInjuryPeriod(TimestampMixin, db.Model):
    __tablename__ = "employee_work_injury_periods"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(
        db.Integer,
        db.ForeignKey("employees.id"),
        nullable=False,
        index=True,
    )
    accident_date = db.Column(db.Date, nullable=False, index=True)
    payroll_start_date = db.Column(db.Date, nullable=False, index=True)
    payroll_end_date = db.Column(db.Date, nullable=True, index=True)
    confirmed_monthly_earnings = db.Column(db.Numeric(14, 2), nullable=False)
    incapacity_monthly_earnings = db.Column(
        db.Numeric(14, 2), nullable=False, default=0
    )
    currency = db.Column(db.String(20), nullable=False, default="HKD")
    pay_mode = db.Column(
        db.String(30), nullable=False, default="four_fifths", index=True
    )
    evidence_document_id = db.Column(
        db.Integer,
        db.ForeignKey("employee_documents.id"),
        nullable=True,
    )
    status = db.Column(db.String(30), nullable=False, default="active", index=True)
    remarks = db.Column(db.Text, nullable=True)

    employee = db.relationship("Employee", back_populates="work_injury_periods")
    evidence_document = db.relationship(
        "EmployeeDocument",
        foreign_keys=[evidence_document_id],
    )
    monthly_expenses = db.relationship(
        "EmployeeWorkInjuryMonthlyExpense",
        back_populates="work_injury_period",
        cascade="all, delete-orphan",
        order_by="EmployeeWorkInjuryMonthlyExpense.year_month.desc()",
    )


class EmployeeWorkInjuryMonthlyExpense(TimestampMixin, db.Model):
    __tablename__ = "employee_work_injury_monthly_expenses"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(
        db.Integer,
        db.ForeignKey("employees.id"),
        nullable=False,
        index=True,
    )
    work_injury_period_id = db.Column(
        db.Integer,
        db.ForeignKey("employee_work_injury_periods.id"),
        nullable=False,
        index=True,
    )
    year_month = db.Column(db.String(7), nullable=False, index=True)
    amount = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    currency = db.Column(db.String(20), nullable=False, default="HKD")
    evidence_document_id = db.Column(
        db.Integer,
        db.ForeignKey("employee_documents.id"),
        nullable=True,
    )
    status = db.Column(db.String(30), nullable=False, default="active", index=True)
    remarks = db.Column(db.Text, nullable=True)

    employee = db.relationship("Employee", back_populates="work_injury_expenses")
    work_injury_period = db.relationship(
        "EmployeeWorkInjuryPeriod", back_populates="monthly_expenses"
    )
    evidence_document = db.relationship(
        "EmployeeDocument", foreign_keys=[evidence_document_id]
    )


