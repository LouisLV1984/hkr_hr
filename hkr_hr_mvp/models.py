from datetime import date, datetime

from flask_login import LoginManager, UserMixin
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash


db = SQLAlchemy()
login_manager = LoginManager()


class TimestampMixin:
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(30), nullable=False, default="hr", index=True)
    active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    last_login_at = db.Column(db.DateTime, nullable=True)
    last_seen_at = db.Column(db.DateTime, nullable=True, index=True)
    last_logout_at = db.Column(db.DateTime, nullable=True)

    @property
    def is_active(self):
        return self.active

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


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
        active = [item for item in self.identities if item.status == "active"]
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
    original_filename = db.Column(db.String(255), nullable=False)
    stored_path = db.Column(db.Text, nullable=False)
    mime_type = db.Column(db.String(120), nullable=True)
    file_size = db.Column(db.Integer, nullable=True)
    content_sha256 = db.Column(db.String(64), nullable=True)
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


class AttendanceSegment(TimestampMixin, db.Model):
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


class EmployeeFinalPaymentCase(TimestampMixin, db.Model):
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


class SystemSetting(TimestampMixin, db.Model):
    __tablename__ = "system_settings"

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(120), unique=True, nullable=False, index=True)
    value_json = db.Column(db.JSON, nullable=True)


class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    employee_id = db.Column(
        db.Integer,
        db.ForeignKey("employees.id"),
        nullable=True,
        index=True,
    )
    action = db.Column(db.String(80), nullable=False, index=True)
    entity_type = db.Column(db.String(80), nullable=False)
    entity_id = db.Column(db.Integer, nullable=True)
    before_json = db.Column(db.JSON, nullable=True)
    after_json = db.Column(db.JSON, nullable=True)
    detail = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    user = db.relationship("User")
    employee = db.relationship("Employee")
