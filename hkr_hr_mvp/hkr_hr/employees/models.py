"""SQLAlchemy ORM models owned by the ``employees`` module."""
from __future__ import annotations

from datetime import date, datetime, timedelta

from hkr_hr.platform.db import TimestampMixin, db

class Employee(TimestampMixin, db.Model):
    __tablename__ = "employees"

    id = db.Column(db.Integer, primary_key=True)
    employee_no = db.Column(db.String(50), unique=True, nullable=False, index=True)
    status = db.Column(db.String(30), nullable=False, default="active", index=True)
    employee_type_id = db.Column(
        db.Integer,
        db.ForeignKey("reference_values.id"),
        nullable=False,
        index=True,
    )
    payroll_group = db.Column(db.String(30), nullable=False, index=True)
    mpf_mode = db.Column(
        db.String(20),
        nullable=False,
        default="regular",
        index=True,
    )
    chinese_name = db.Column(db.String(120), nullable=True, index=True)
    english_name = db.Column(db.String(160), nullable=True, index=True)
    gender = db.Column(db.String(20), nullable=True)
    date_of_birth = db.Column(db.Date, nullable=True)
    mobile_region_code = db.Column(db.String(20), nullable=True)
    mobile_number = db.Column(db.String(80), nullable=True, index=True)
    email = db.Column(db.String(160), nullable=True)
    residential_address = db.Column(db.Text, nullable=True)
    bank_name = db.Column(db.String(200), nullable=True)
    bank_account_no = db.Column(db.String(120), nullable=True)
    emergency_contact_name = db.Column(db.String(120), nullable=True)
    emergency_contact_region_code = db.Column(db.String(20), nullable=True)
    emergency_contact_phone = db.Column(db.String(80), nullable=True)
    emergency_contact_relation = db.Column(db.String(80), nullable=True)
    education_level = db.Column(db.String(120), nullable=True)
    major = db.Column(db.String(160), nullable=True)
    graduation_school = db.Column(db.String(200), nullable=True)
    visa_required = db.Column(db.Boolean, nullable=False, default=False)
    remarks = db.Column(db.Text, nullable=True)

    employee_type = db.relationship("ReferenceValue", foreign_keys=[employee_type_id])
    identities = db.relationship(
        "EmployeeIdentity",
        back_populates="employee",
        cascade="all, delete-orphan",
        order_by="EmployeeIdentity.created_at.desc()",
    )
    employment_periods = db.relationship(
        "EmployeeEmploymentPeriod",
        back_populates="employee",
        cascade="all, delete-orphan",
        order_by="EmployeeEmploymentPeriod.start_date.desc()",
    )
    assignments = db.relationship(
        "EmployeeAssignment",
        back_populates="employee",
        cascade="all, delete-orphan",
        order_by="EmployeeAssignment.effective_from.desc()",
    )
    salaries = db.relationship(
        "EmployeeSalary",
        back_populates="employee",
        cascade="all, delete-orphan",
        order_by="EmployeeSalary.effective_from.desc()",
    )
    mpf_enrollments = db.relationship(
        "EmployeeMpfEnrollment",
        back_populates="employee",
        cascade="all, delete-orphan",
        order_by="EmployeeMpfEnrollment.effective_from.desc()",
    )
    allowances = db.relationship(
        "EmployeeAllowance",
        back_populates="employee",
        cascade="all, delete-orphan",
        order_by="EmployeeAllowance.effective_from.desc()",
    )
    bank_accounts = db.relationship(
        "EmployeeBankAccount",
        back_populates="employee",
        cascade="all, delete-orphan",
        order_by="EmployeeBankAccount.effective_from.desc()",
    )
    comp_leave_credits = db.relationship(
        "EmployeeCompLeaveCredit",
        back_populates="employee",
        cascade="all, delete-orphan",
        order_by="EmployeeCompLeaveCredit.source_date.desc()",
    )
    work_injury_periods = db.relationship(
        "EmployeeWorkInjuryPeriod",
        back_populates="employee",
        cascade="all, delete-orphan",
        order_by="EmployeeWorkInjuryPeriod.payroll_start_date.desc()",
    )
    work_injury_expenses = db.relationship(
        "EmployeeWorkInjuryMonthlyExpense",
        back_populates="employee",
        cascade="all, delete-orphan",
        order_by="EmployeeWorkInjuryMonthlyExpense.year_month.desc()",
    )
    documents = db.relationship(
        "EmployeeDocument",
        back_populates="employee",
        cascade="all, delete-orphan",
        foreign_keys="EmployeeDocument.employee_id",
        order_by="EmployeeDocument.uploaded_at.desc()",
    )
    qualifications = db.relationship(
        "EmployeeQualification",
        back_populates="employee",
        cascade="all, delete-orphan",
    )
    certificates = db.relationship(
        "EmployeeCertificate",
        back_populates="employee",
        cascade="all, delete-orphan",
    )
    visas = db.relationship(
        "EmployeeVisa",
        back_populates="employee",
        cascade="all, delete-orphan",
    )
    generated_contracts = db.relationship(
        "GeneratedContract",
        cascade="all, delete-orphan",
        foreign_keys="GeneratedContract.employee_id",
    )
    attendance_summaries = db.relationship(
        "AttendanceMonthlySummary",
        cascade="all, delete-orphan",
        foreign_keys="AttendanceMonthlySummary.employee_id",
    )
    attendance_policies = db.relationship(
        "EmployeeAttendancePolicy",
        back_populates="employee",
        cascade="all, delete-orphan",
        order_by="EmployeeAttendancePolicy.effective_from_month.desc()",
    )
    attendance_corrections = db.relationship("AttendanceCorrection", cascade="all, delete-orphan")
    payroll_adjustments = db.relationship(
        "PayrollAdjustment",
        cascade="all, delete-orphan",
        foreign_keys="PayrollAdjustment.employee_id",
    )
    payroll_results = db.relationship(
        "PayrollEmployeeResult",
        cascade="all, delete-orphan",
        foreign_keys="PayrollEmployeeResult.employee_id",
    )
    annual_leave_balances = db.relationship(
        "EmployeeAnnualLeaveBalance",
        cascade="all, delete-orphan",
        foreign_keys="EmployeeAnnualLeaveBalance.employee_id",
    )
    annual_leave_records = db.relationship(
        "EmployeeAnnualLeaveRecord",
        cascade="all, delete-orphan",
        foreign_keys="EmployeeAnnualLeaveRecord.employee_id",
    )
    final_payment_cases = db.relationship(
        "EmployeeFinalPaymentCase",
        cascade="all, delete-orphan",
        foreign_keys="EmployeeFinalPaymentCase.employee_id",
    )
    @property
    def display_name(self):
        return self.chinese_name or self.english_name or self.employee_no

    @property
    def primary_identity(self):
        from hkr_hr.employees.rules.credentials import credential_state
        active = [item for item in self.identities if credential_state(item)["code"] not in {"voided", "renewed", "future"}]
        return next((item for item in active if item.is_primary), active[0] if active else None)

    def is_active_on(self, on_date):
        if not self.employment_periods:
            return self.status == "active"
        return any(
            period.start_date <= on_date
            and (period.end_date is None or period.end_date >= on_date)
            for period in self.employment_periods
        )

    def employed_during(self, start_date, end_date):
        if not self.employment_periods:
            return self.status == "active"
        return any(
            period.start_date <= end_date
            and (period.end_date is None or period.end_date >= start_date)
            for period in self.employment_periods
        )

    @property
    def derived_status(self):
        return "active" if self.is_active_on(date.today()) else "departed"

    @property
    def scheduled_departure_date(self):
        today = date.today()
        dates = [
            period.end_date
            for period in self.employment_periods
            if period.start_date <= today
            and period.end_date is not None
            and period.end_date >= today
        ]
        return min(dates) if dates else None

    @property
    def current_period(self):
        today = date.today()
        active = [
            item
            for item in self.employment_periods
            if item.start_date <= today
            and (item.end_date is None or item.end_date >= today)
        ]
        return active[0] if active else (self.employment_periods[0] if self.employment_periods else None)

    @property
    def current_assignment(self):
        today = date.today()
        active = [
            item
            for item in self.assignments
            if item.status == "active"
            if item.effective_from <= today
            and (item.effective_to is None or item.effective_to >= today)
        ]
        return active[0] if active else None

    @property
    def current_salary(self):
        today = date.today()
        active = [
            item
            for item in self.salaries
            if item.status == "active"
            if item.effective_from <= today
            and (item.effective_to is None or item.effective_to >= today)
        ]
        return active[0] if active else None

    @property
    def current_mpf(self):
        today = date.today()
        active = [
            item
            for item in self.mpf_enrollments
            if item.status == "active"
            if item.effective_from <= today
            and (item.effective_to is None or item.effective_to >= today)
        ]
        return active[0] if active else None

    @property
    def current_bank_account(self):
        today = date.today()
        active = [
            item
            for item in self.bank_accounts
            if item.status == "active"
            and item.effective_from <= today
            and (item.effective_to is None or item.effective_to >= today)
        ]
        return active[0] if active else None


class EmployeeBankAccount(TimestampMixin, db.Model):
    __tablename__ = "employee_bank_accounts"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(
        db.Integer,
        db.ForeignKey("employees.id"),
        nullable=False,
        index=True,
    )
    effective_from = db.Column(db.Date, nullable=False, index=True)
    effective_to = db.Column(db.Date, nullable=True, index=True)
    bank_name = db.Column(db.String(200), nullable=False)
    account_no = db.Column(db.String(120), nullable=False)
    currency = db.Column(db.String(10), nullable=False, default="HKD")
    status = db.Column(db.String(30), nullable=False, default="active", index=True)
    evidence_document_id = db.Column(
        db.Integer,
        db.ForeignKey("employee_documents.id"),
        nullable=True,
    )
    remarks = db.Column(db.Text, nullable=True)

    employee = db.relationship("Employee", back_populates="bank_accounts")
    evidence_document = db.relationship(
        "EmployeeDocument",
        foreign_keys=[evidence_document_id],
    )


class EmployeeIdentity(TimestampMixin, db.Model):
    __tablename__ = "employee_identities"

    renews_id = db.Column(db.Integer, db.ForeignKey("employee_identities.id"), nullable=True)

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(
        db.Integer,
        db.ForeignKey("employees.id"),
        nullable=False,
        index=True,
    )
    identity_type = db.Column(db.String(40), nullable=False, index=True)
    identity_number = db.Column(db.String(120), nullable=False, index=True)
    issue_date = db.Column(db.Date, nullable=True)
    expiry_date = db.Column(db.Date, nullable=True, index=True)
    is_long_term = db.Column(db.Boolean, nullable=False, default=False)
    is_primary = db.Column(db.Boolean, nullable=False, default=False, index=True)
    status = db.Column(db.String(30), nullable=False, default="active", index=True)
    document_id = db.Column(
        db.Integer,
        db.ForeignKey("employee_documents.id"),
        nullable=True,
    )
    remarks = db.Column(db.Text, nullable=True)

    employee = db.relationship("Employee", back_populates="identities")
    document = db.relationship("EmployeeDocument", foreign_keys=[document_id])


class EmployeeEmploymentPeriod(TimestampMixin, db.Model):
    __tablename__ = "employee_employment_periods"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(
        db.Integer,
        db.ForeignKey("employees.id"),
        nullable=False,
        index=True,
    )
    start_date = db.Column(db.Date, nullable=False, index=True)
    end_date = db.Column(db.Date, nullable=True, index=True)
    probation_end_date = db.Column(db.Date, nullable=True, index=True)
    confirmation_date = db.Column(db.Date, nullable=True)
    contract_annual_leave_days = db.Column(db.Numeric(5, 1), nullable=True)
    annual_leave_policy_year = db.Column(db.Integer, nullable=True)
    annual_leave_contract_verified = db.Column(db.Boolean, nullable=True)
    termination_reason = db.Column(db.String(40), nullable=True)
    notice_period_value = db.Column(db.Numeric(6, 2), nullable=True)
    notice_period_unit = db.Column(db.String(20), nullable=True)
    average_wage = db.Column(db.Numeric(12, 2), nullable=True)
    payment_in_lieu = db.Column(db.Numeric(12, 2), nullable=True)
    severance_payment = db.Column(db.Numeric(12, 2), nullable=True)
    long_service_payment = db.Column(db.Numeric(12, 2), nullable=True)
    confirmation_document_id = db.Column(
        db.Integer,
        db.ForeignKey("employee_documents.id"),
        nullable=True,
    )
    termination_document_id = db.Column(
        db.Integer,
        db.ForeignKey("employee_documents.id"),
        nullable=True,
    )
    remarks = db.Column(db.Text, nullable=True)

    employee = db.relationship("Employee", back_populates="employment_periods")
    confirmation_document = db.relationship(
        "EmployeeDocument",
        foreign_keys=[confirmation_document_id],
    )
    termination_document = db.relationship(
        "EmployeeDocument",
        foreign_keys=[termination_document_id],
    )


class EmployeeAssignment(TimestampMixin, db.Model):
    __tablename__ = "employee_assignments"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(
        db.Integer,
        db.ForeignKey("employees.id"),
        nullable=False,
        index=True,
    )
    effective_from = db.Column(db.Date, nullable=False, index=True)
    effective_to = db.Column(db.Date, nullable=True, index=True)
    region_id = db.Column(
        db.Integer,
        db.ForeignKey("reference_values.id"),
        nullable=True,
        index=True,
    )
    project_id = db.Column(
        db.Integer,
        db.ForeignKey("work_projects.id"),
        nullable=True,
        index=True,
    )
    department_id = db.Column(
        db.Integer,
        db.ForeignKey("reference_values.id"),
        nullable=True,
        index=True,
    )
    employer_id = db.Column(
        db.Integer,
        db.ForeignKey("reference_values.id"),
        nullable=True,
    )
    payroll_entity_id = db.Column(
        db.Integer,
        db.ForeignKey("reference_values.id"),
        nullable=True,
    )
    social_insurance_entity_id = db.Column(
        db.Integer,
        db.ForeignKey("reference_values.id"),
        nullable=True,
    )
    labour_dispatch_entity_id = db.Column(
        db.Integer,
        db.ForeignKey("reference_values.id"),
        nullable=True,
    )
    payroll_group = db.Column(db.String(30), nullable=False, index=True)
    workweek_days = db.Column(
        db.Numeric(3, 1),
        nullable=False,
        default=6,
    )
    status = db.Column(
        db.String(30),
        nullable=False,
        default="active",
        index=True,
    )
    evidence_document_id = db.Column(
        db.Integer,
        db.ForeignKey("employee_documents.id"),
        nullable=True,
    )
    remarks = db.Column(db.Text, nullable=True)

    employee = db.relationship("Employee", back_populates="assignments")
    region = db.relationship("ReferenceValue", foreign_keys=[region_id])
    project = db.relationship("WorkProject", foreign_keys=[project_id])
    department = db.relationship("ReferenceValue", foreign_keys=[department_id])
    employer = db.relationship("ReferenceValue", foreign_keys=[employer_id])
    payroll_entity = db.relationship(
        "ReferenceValue",
        foreign_keys=[payroll_entity_id],
    )
    social_insurance_entity = db.relationship(
        "ReferenceValue",
        foreign_keys=[social_insurance_entity_id],
    )
    labour_dispatch_entity = db.relationship(
        "ReferenceValue",
        foreign_keys=[labour_dispatch_entity_id],
    )
    evidence_document = db.relationship(
        "EmployeeDocument",
        foreign_keys=[evidence_document_id],
    )
    positions = db.relationship(
        "EmployeeAssignmentPosition",
        back_populates="assignment",
        cascade="all, delete-orphan",
    )

    @property
    def primary_position(self):
        return next(
            (item.position for item in self.positions if item.is_primary),
            self.positions[0].position if self.positions else None,
        )


class EmployeeAssignmentPosition(db.Model):
    __tablename__ = "employee_assignment_positions"
    __table_args__ = (
        db.UniqueConstraint(
            "assignment_id",
            "position_id",
            name="uq_assignment_position",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    assignment_id = db.Column(
        db.Integer,
        db.ForeignKey("employee_assignments.id"),
        nullable=False,
        index=True,
    )
    position_id = db.Column(
        db.Integer,
        db.ForeignKey("reference_values.id"),
        nullable=False,
        index=True,
    )
    is_primary = db.Column(db.Boolean, nullable=False, default=False)

    assignment = db.relationship("EmployeeAssignment", back_populates="positions")
    position = db.relationship("ReferenceValue", foreign_keys=[position_id])


class EmployeeSalary(TimestampMixin, db.Model):
    __tablename__ = "employee_salaries"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(
        db.Integer,
        db.ForeignKey("employees.id"),
        nullable=False,
        index=True,
    )
    effective_from = db.Column(db.Date, nullable=False, index=True)
    effective_to = db.Column(db.Date, nullable=True, index=True)
    salary_basis = db.Column(db.String(30), nullable=False, index=True)
    monthly_pay_method = db.Column(
        db.String(30),
        nullable=False,
        default="full_month",
        index=True,
    )
    currency = db.Column(db.String(20), nullable=False, default="HKD")
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    status = db.Column(
        db.String(30),
        nullable=False,
        default="active",
        index=True,
    )
    evidence_document_id = db.Column(
        db.Integer,
        db.ForeignKey("employee_documents.id"),
        nullable=True,
    )
    remarks = db.Column(db.Text, nullable=True)

    employee = db.relationship("Employee", back_populates="salaries")
    evidence_document = db.relationship(
        "EmployeeDocument",
        foreign_keys=[evidence_document_id],
    )


class EmployeeMpfEnrollment(TimestampMixin, db.Model):
    __tablename__ = "employee_mpf_enrollments"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(
        db.Integer,
        db.ForeignKey("employees.id"),
        nullable=False,
        index=True,
    )
    scheme_id = db.Column(
        db.Integer,
        db.ForeignKey("mpf_schemes.id"),
        nullable=True,
        index=True,
    )
    member_account_no = db.Column(db.String(120), nullable=True)
    contribution_mode = db.Column(
        db.String(20),
        nullable=False,
        default="regular",
        index=True,
    )
    effective_from = db.Column(db.Date, nullable=False, index=True)
    effective_to = db.Column(db.Date, nullable=True, index=True)
    status = db.Column(
        db.String(30),
        nullable=False,
        default="active",
        index=True,
    )
    remarks = db.Column(db.Text, nullable=True)

    employee = db.relationship("Employee", back_populates="mpf_enrollments")
    scheme = db.relationship("MpfScheme", back_populates="enrollments")

    @property
    def is_exempt(self):
        return self.contribution_mode == "exempt"


class EmployeeAllowance(TimestampMixin, db.Model):
    __tablename__ = "employee_allowances"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(
        db.Integer,
        db.ForeignKey("employees.id"),
        nullable=False,
        index=True,
    )
    label = db.Column(db.String(160), nullable=False)
    allowance_type = db.Column(
        db.String(30),
        nullable=False,
        default="special",
        index=True,
    )
    currency = db.Column(db.String(20), nullable=False, default="HKD")
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    exchange_rate = db.Column(db.Numeric(14, 6), nullable=True)
    effective_from = db.Column(db.Date, nullable=False, index=True)
    effective_to = db.Column(db.Date, nullable=True, index=True)
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

    employee = db.relationship("Employee", back_populates="allowances")
    project = db.relationship("WorkProject", foreign_keys=[project_id])
    evidence_document = db.relationship(
        "EmployeeDocument",
        foreign_keys=[evidence_document_id],
    )


class EmployeeQualification(TimestampMixin, db.Model):
    __tablename__ = "employee_qualifications"

    renews_id = db.Column(db.Integer, db.ForeignKey("employee_qualifications.id"), nullable=True)

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(
        db.Integer,
        db.ForeignKey("employees.id"),
        nullable=False,
        index=True,
    )
    category = db.Column(db.String(40), nullable=False, default="skill")
    qualification_name = db.Column(db.String(200), nullable=False)
    certificate_no = db.Column(db.String(120), nullable=True)
    issue_date = db.Column(db.Date, nullable=True)
    expiry_date = db.Column(db.Date, nullable=True, index=True)
    status = db.Column(
        db.String(30),
        nullable=False,
        default="active",
        index=True,
    )
    document_id = db.Column(
        db.Integer,
        db.ForeignKey("employee_documents.id"),
        nullable=True,
    )
    remarks = db.Column(db.Text, nullable=True)

    employee = db.relationship("Employee", back_populates="qualifications")
    document = db.relationship("EmployeeDocument", foreign_keys=[document_id])


class EmployeeCertificate(TimestampMixin, db.Model):
    __tablename__ = "employee_certificates"

    renews_id = db.Column(db.Integer, db.ForeignKey("employee_certificates.id"), nullable=True)

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(
        db.Integer,
        db.ForeignKey("employees.id"),
        nullable=False,
        index=True,
    )
    certificate_type_id = db.Column(
        db.Integer,
        db.ForeignKey("reference_values.id"),
        nullable=False,
        index=True,
    )
    certificate_no = db.Column(db.String(120), nullable=True)
    valid_from = db.Column(db.Date, nullable=True)
    expiry_date = db.Column(db.Date, nullable=True, index=True)
    is_long_term = db.Column(db.Boolean, nullable=False, default=False)
    status = db.Column(
        db.String(30),
        nullable=False,
        default="active",
        index=True,
    )
    document_id = db.Column(
        db.Integer,
        db.ForeignKey("employee_documents.id"),
        nullable=True,
    )
    remarks = db.Column(db.Text, nullable=True)

    employee = db.relationship("Employee", back_populates="certificates")
    certificate_type = db.relationship(
        "ReferenceValue",
        foreign_keys=[certificate_type_id],
    )
    document = db.relationship("EmployeeDocument", foreign_keys=[document_id])


class EmployeeVisa(TimestampMixin, db.Model):
    __tablename__ = "employee_visas"

    renews_id = db.Column(db.Integer, db.ForeignKey("employee_visas.id"), nullable=True)

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(
        db.Integer,
        db.ForeignKey("employees.id"),
        nullable=False,
        index=True,
    )
    visa_category_id = db.Column(
        db.Integer,
        db.ForeignKey("reference_values.id"),
        nullable=False,
    )
    visa_no = db.Column(db.String(120), nullable=True)
    issue_date = db.Column(db.Date, nullable=True)
    expiry_date = db.Column(db.Date, nullable=True, index=True)
    status = db.Column(
        db.String(30),
        nullable=False,
        default="active",
        index=True,
    )
    document_id = db.Column(
        db.Integer,
        db.ForeignKey("employee_documents.id"),
        nullable=True,
    )
    remarks = db.Column(db.Text, nullable=True)

    employee = db.relationship("Employee", back_populates="visas")
    visa_category = db.relationship(
        "ReferenceValue",
        foreign_keys=[visa_category_id],
    )
    document = db.relationship("EmployeeDocument", foreign_keys=[document_id])


class EmployeeAttendancePolicy(TimestampMixin, db.Model):
    __tablename__ = "employee_attendance_policies"
    __table_args__ = (
        db.UniqueConstraint(
            "employee_id",
            "effective_from_month",
            name="uq_employee_attendance_policy_month",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(
        db.Integer,
        db.ForeignKey("employees.id"),
        nullable=False,
        index=True,
    )
    effective_from_month = db.Column(db.String(7), nullable=False, index=True)
    requires_attendance = db.Column(db.Boolean, nullable=False, default=True)
    remarks = db.Column(db.Text, nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    employee = db.relationship("Employee", back_populates="attendance_policies")
    creator = db.relationship("User", foreign_keys=[created_by])


