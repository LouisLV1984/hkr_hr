"""SQLAlchemy ORM models owned by the ``payroll`` module."""
from __future__ import annotations

from datetime import date, datetime, timedelta

from hkr_hr.platform.db import TimestampMixin, db

class PayrollAdjustment(TimestampMixin, db.Model):
    __tablename__ = "payroll_adjustments"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(
        db.Integer,
        db.ForeignKey("employees.id"),
        nullable=False,
        index=True,
    )
    year_month = db.Column(db.String(7), nullable=False, index=True)
    label = db.Column(db.String(160), nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    status = db.Column(
        db.String(30),
        nullable=False,
        default="active",
        index=True,
    )
    project_id = db.Column(
        db.Integer,
        db.ForeignKey("work_projects.id"),
        nullable=True,
    )
    evidence_document_id = db.Column(
        db.Integer,
        db.ForeignKey("employee_documents.id"),
        nullable=True,
    )
    remarks = db.Column(db.Text, nullable=True)

    employee = db.relationship(
        "Employee",
        back_populates="payroll_adjustments",
    )
    project = db.relationship("WorkProject", foreign_keys=[project_id])
    evidence_document = db.relationship(
        "EmployeeDocument",
        foreign_keys=[evidence_document_id],
    )


class SalaryRecord(TimestampMixin, db.Model):
    """HR-confirmed payment history. Never a Payroll calculation input."""
    __tablename__ = "employee_salary_records"
    __table_args__ = (db.UniqueConstraint("employee_id", "year_month", "payroll_entity_id",
                                        name="uq_salary_record_employee_month_entity"),)
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=False, index=True)
    year_month = db.Column(db.String(7), nullable=False, index=True)
    payroll_entity_id = db.Column(db.Integer, db.ForeignKey("reference_values.id"), nullable=False)
    currency = db.Column(db.String(3), nullable=False)
    gross_amount = db.Column(db.Numeric(14, 2), nullable=False)
    employee_mpf = db.Column(db.Numeric(14, 2), nullable=False)
    net_amount = db.Column(db.Numeric(14, 2), nullable=False)
    remarks = db.Column(db.Text)
    evidence_document_id = db.Column(db.Integer, db.ForeignKey("employee_documents.id"))
    status = db.Column(db.String(20), nullable=False, default="active")
    revision = db.Column(db.Integer, nullable=False, default=1)
    updated_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    employee = db.relationship("Employee", backref=db.backref("salary_records", cascade="all, delete-orphan"))
    payroll_entity = db.relationship("ReferenceValue")
    evidence_document = db.relationship("EmployeeDocument")


class PayrollRun(TimestampMixin, db.Model):
    __tablename__ = "payroll_runs"

    id = db.Column(db.Integer, primary_key=True)
    year_month = db.Column(db.String(7), nullable=False, index=True)
    payroll_group = db.Column(db.String(30), nullable=False, index=True)
    rule_version = db.Column(db.String(30), nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    source_json = db.Column(db.JSON, nullable=True)

    employee_results = db.relationship(
        "PayrollEmployeeResult",
        back_populates="run",
        cascade="all, delete-orphan",
    )


class PayrollEmployeeResult(TimestampMixin, db.Model):
    __tablename__ = "payroll_employee_results"
    __table_args__ = (
        db.UniqueConstraint(
            "run_id",
            "employee_id",
            name="uq_payroll_run_employee",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    run_id = db.Column(
        db.Integer,
        db.ForeignKey("payroll_runs.id"),
        nullable=False,
        index=True,
    )
    employee_id = db.Column(
        db.Integer,
        db.ForeignKey("employees.id"),
        nullable=False,
        index=True,
    )
    currency = db.Column(db.String(20), nullable=False, default="HKD")
    base_amount = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    ot_amount = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    holiday_amount = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    large_ecall_amount = db.Column(
        db.Numeric(14, 2),
        nullable=False,
        default=0,
    )
    ecall_amount = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    allowance_amount = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    traffic_meal_allowance_amount = db.Column(
        db.Numeric(14, 2), nullable=False, default=0
    )
    special_allowance_amount = db.Column(
        db.Numeric(14, 2), nullable=False, default=0
    )
    sick_leave_amount = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    work_injury_amount = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    work_injury_medical_reimbursement_amount = db.Column(
        db.Numeric(14, 2), nullable=False, default=0
    )
    attendance_other_allowance_amount = db.Column(
        db.Numeric(14, 2), nullable=False, default=0
    )
    unpaid_leave_deduction = db.Column(
        db.Numeric(14, 2), nullable=False, default=0
    )
    annual_leave_days = db.Column(db.Numeric(8, 2), nullable=False, default=0)
    sick_leave_days = db.Column(db.Numeric(8, 2), nullable=False, default=0)
    unpaid_leave_days = db.Column(db.Numeric(8, 2), nullable=False, default=0)
    work_injury_days = db.Column(db.Numeric(8, 2), nullable=False, default=0)
    overpay_amount = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    underpay_amount = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    adjustment_amount = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    gross_amount = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    employee_mpf = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    employer_mpf = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    mpf_relevant_income = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    mpf_scheme_name = db.Column(db.String(200), nullable=True)
    mpf_scheme_code = db.Column(db.String(80), nullable=True)
    mpf_employer_account_no = db.Column(db.String(80), nullable=True)
    mpf_payroll_group_no = db.Column(db.String(120), nullable=True)
    mpf_member_account_no = db.Column(db.String(120), nullable=True)
    mpf_member_name = db.Column(db.String(200), nullable=True)
    mpf_calculation_mode = db.Column(db.String(20), nullable=True)
    payment_in_lieu = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    severance_long_service = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    net_amount = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    warnings_json = db.Column(db.JSON, nullable=True)
    calculation_json = db.Column(db.JSON, nullable=True)

    run = db.relationship("PayrollRun", back_populates="employee_results")
    employee = db.relationship(
        "Employee",
        back_populates="payroll_results",
    )
    project_lines = db.relationship(
        "PayrollProjectLine",
        back_populates="employee_result",
        cascade="all, delete-orphan",
    )


class PayrollProjectLine(TimestampMixin, db.Model):
    __tablename__ = "payroll_project_lines"

    id = db.Column(db.Integer, primary_key=True)
    employee_result_id = db.Column(
        db.Integer,
        db.ForeignKey("payroll_employee_results.id"),
        nullable=False,
        index=True,
    )
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
    base_amount = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    ot_amount = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    holiday_amount = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    large_ecall_amount = db.Column(
        db.Numeric(14, 2),
        nullable=False,
        default=0,
    )
    ecall_amount = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    allowance_amount = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    traffic_meal_allowance_amount = db.Column(
        db.Numeric(14, 2), nullable=False, default=0
    )
    special_allowance_amount = db.Column(
        db.Numeric(14, 2), nullable=False, default=0
    )
    attendance_other_allowance_amount = db.Column(
        db.Numeric(14, 2), nullable=False, default=0
    )
    adjustment_amount = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    gross_amount = db.Column(db.Numeric(14, 2), nullable=False, default=0)

    employee_result = db.relationship(
        "PayrollEmployeeResult",
        back_populates="project_lines",
    )
    project = db.relationship("WorkProject", foreign_keys=[project_id])


class EmployeeFinalPaymentCase(TimestampMixin, db.Model):
    rate_allocations = db.Column(db.JSON)
    __tablename__ = "employee_final_payment_cases"
    __table_args__ = (
        db.UniqueConstraint(
            "employment_period_id",
            name="uq_final_payment_employment_period",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(
        db.Integer,
        db.ForeignKey("employees.id"),
        nullable=False,
        index=True,
    )
    employment_period_id = db.Column(
        db.Integer,
        db.ForeignKey("employee_employment_periods.id"),
        nullable=False,
        index=True,
    )
    settlement_month = db.Column(db.String(7), nullable=False, index=True)
    status = db.Column(
        db.String(30),
        nullable=False,
        default="active",
        index=True,
    )
    actual_working_days = db.Column(db.Numeric(8, 2), nullable=True)
    actual_ot_hours = db.Column(db.Numeric(8, 2), nullable=True)
    actual_holiday_days = db.Column(db.Numeric(8, 2), nullable=True)
    large_ecall_count = db.Column(db.Integer, nullable=False, default=0)
    ecall_count = db.Column(db.Integer, nullable=False, default=0)
    allowance_amount = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    other_payment = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    overpay_amount = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    underpay_amount = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    legacy_leave_days = db.Column(db.Numeric(8, 3), nullable=True)
    post_2024_leave_days = db.Column(db.Numeric(8, 3), nullable=True)
    statutory_holiday_days = db.Column(db.Numeric(8, 3), nullable=True)
    leave_average_wage = db.Column(db.Numeric(14, 2), nullable=True)
    leave_wage_total = db.Column(db.Numeric(14, 2), nullable=True)
    leave_daily_rate_override = db.Column(db.Numeric(14, 4), nullable=True)
    holiday_daily_rate_override = db.Column(db.Numeric(14, 4), nullable=True)
    benefit_type = db.Column(
        db.String(30),
        nullable=False,
        default="none",
        index=True,
    )
    pre_basis_last = db.Column(db.Numeric(14, 2), nullable=True)
    pre_basis_average = db.Column(db.Numeric(14, 2), nullable=True)
    pre_basis_choice = db.Column(db.String(30), nullable=True)
    post_basis_last = db.Column(db.Numeric(14, 2), nullable=True)
    post_basis_average = db.Column(db.Numeric(14, 2), nullable=True)
    post_basis_choice = db.Column(db.String(30), nullable=True)
    mpf_offset_amount = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    special_compensation = db.Column(
        db.Numeric(14, 2),
        nullable=False,
        default=0,
    )
    remarks = db.Column(db.Text, nullable=True)
    updated_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    employee = db.relationship(
        "Employee",
        back_populates="final_payment_cases",
    )
    employment_period = db.relationship(
        "EmployeeEmploymentPeriod",
        foreign_keys=[employment_period_id],
    )


