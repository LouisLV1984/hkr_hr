"""Core employee DB operations: numbering, audit snapshots, effective-dated records."""
from __future__ import annotations

from datetime import date
import re

from hkr_hr.employees.models import (
    Employee,
    EmployeeAssignment,
    EmployeeAssignmentPosition,
    EmployeeEmploymentPeriod,
    EmployeeMpfEnrollment,
    EmployeeSalary,
)
from hkr_hr.employees.rules.credentials import (
    current_mpf_on,
    rebuild_effective_ranges,
)
from hkr_hr.platform.dates import (
    money,
    normalize_workweek_days,
    valid_salary_amount,
)
from hkr_hr.platform.db import db


def next_employee_no(employee_type):
    prefix = (employee_type.code or "OTHER").upper()
    pattern = re.compile(rf"^{re.escape(prefix)}(\d+)$", re.I)
    maximum = 0
    for (number,) in db.session.query(Employee.employee_no).filter(
        Employee.employee_no.ilike(f"{prefix}%")
    ):
        match = pattern.match(number or "")
        if match:
            maximum = max(maximum, int(match.group(1)))
    return f"{prefix}{maximum + 1:04d}"


def employee_audit_snapshot(employee):
    assignment = employee.current_assignment
    salary = employee.current_salary
    identity = employee.primary_identity
    return {
        "employee_no": employee.employee_no,
        "status": employee.status,
        "employee_type": (
            employee.employee_type.display_name if employee.employee_type else ""
        ),
        "payroll_group": employee.payroll_group,
        "chinese_name": employee.chinese_name or "",
        "english_name": employee.english_name or "",
        "gender": employee.gender or "",
        "date_of_birth": str(employee.date_of_birth or ""),
        "mobile": " ".join(
            item
            for item in [employee.mobile_region_code, employee.mobile_number]
            if item
        ),
        "email": employee.email or "",
        "address": employee.residential_address or "",
        "emergency_contact_name": employee.emergency_contact_name or "",
        "emergency_contact_phone": " ".join(
            item
            for item in [
                employee.emergency_contact_region_code,
                employee.emergency_contact_phone,
            ]
            if item
        ),
        "emergency_contact_relation": employee.emergency_contact_relation or "",
        "education_level": employee.education_level or "",
        "major": employee.major or "",
        "graduation_school": employee.graduation_school or "",
        "visa_required": employee.visa_required,
        "remarks": employee.remarks or "",
        "bank_name": employee.bank_name or "",
        "bank_account": employee.bank_account_no or "",
        "primary_identity": identity.identity_number if identity else "",
        "project": assignment.project.name if assignment and assignment.project else "",
        "department": (
            assignment.department.display_name
            if assignment and assignment.department
            else ""
        ),
        "salary_basis": salary.salary_basis if salary else "",
        "salary_currency": salary.currency if salary else "",
        "salary_amount": str(salary.amount if salary else ""),
    }


def create_mpf_enrollment(
    employee,
    effective_from,
    scheme=None,
    member_account_no=None,
    contribution_mode=None,
    remarks=None,
):
    mode = contribution_mode or (scheme.calculation_mode if scheme else "exempt")
    enrollment = EmployeeMpfEnrollment(
        employee=employee,
        scheme=scheme,
        member_account_no=member_account_no or None,
        contribution_mode=mode,
        effective_from=effective_from,
        status="active",
        remarks=remarks,
    )
    db.session.add(enrollment)
    db.session.flush()
    rebuild_effective_ranges(employee.mpf_enrollments)
    current = current_mpf_on(employee, date.today())
    if current:
        employee.mpf_mode = current.contribution_mode
    return enrollment


def create_assignment(
    employee,
    effective_from,
    payroll_group,
    workweek_days=None,
    region_id=None,
    project_id=None,
    department_id=None,
    employer_id=None,
    payroll_entity_id=None,
    social_insurance_entity_id=None,
    labour_dispatch_entity_id=None,
    position_ids=None,
    evidence_document_id=None,
    remarks=None,
):
    assignment = EmployeeAssignment(
        employee=employee,
        effective_from=effective_from,
        payroll_group=payroll_group,
        workweek_days=normalize_workweek_days(workweek_days, payroll_group),
        region_id=region_id,
        project_id=project_id,
        department_id=department_id,
        employer_id=employer_id,
        payroll_entity_id=payroll_entity_id,
        social_insurance_entity_id=social_insurance_entity_id,
        labour_dispatch_entity_id=labour_dispatch_entity_id,
        evidence_document_id=evidence_document_id,
        remarks=remarks,
        status="active",
    )
    db.session.add(assignment)
    db.session.flush()
    rebuild_effective_ranges(employee.assignments)
    for index, position_id in enumerate(position_ids or []):
        db.session.add(
            EmployeeAssignmentPosition(
                assignment=assignment,
                position_id=position_id,
                is_primary=index == 0,
            )
        )
    return assignment


def create_salary(
    employee,
    effective_from,
    salary_basis,
    currency,
    amount,
    monthly_pay_method="full_month",
    evidence_document_id=None,
    remarks=None,
):
    if not valid_salary_amount(amount):
        raise ValueError("Invalid salary amount")
    salary = EmployeeSalary(
        employee=employee,
        effective_from=effective_from,
        salary_basis=salary_basis,
        monthly_pay_method=(
            monthly_pay_method if salary_basis == "monthly" else "full_month"
        ),
        currency=currency,
        amount=money(amount),
        evidence_document_id=evidence_document_id,
        remarks=remarks,
        status="active",
    )
    db.session.add(salary)
    db.session.flush()
    rebuild_effective_ranges(employee.salaries)
    return salary


def ensure_current_employment_period(employee, start_date=None):
    period = employee.current_period
    if period and period.end_date is None:
        return period
    period = EmployeeEmploymentPeriod(
        employee=employee,
        start_date=start_date or date.today(),
    )
    db.session.add(period)
    return period
