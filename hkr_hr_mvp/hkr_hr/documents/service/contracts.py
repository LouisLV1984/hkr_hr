"""Contract template context builder."""
from __future__ import annotations

from hkr_hr.employees.api import current_assignment_on, current_salary_on
from hkr_hr.platform.dates import format_money


def contract_context(
    employee,
    contract_date,
    effective_date,
    annual_leave,
    probation,
    notice_period,
):
    assignment = current_assignment_on(employee, effective_date)
    salary = current_salary_on(employee, effective_date)
    identity = employee.primary_identity
    positions = (
        "、".join(item.position.display_name for item in assignment.positions)
        if assignment
        else ""
    )
    salary_basis = "每月" if salary and salary.salary_basis == "monthly" else "每日"
    salary_text = (
        f"{salary_basis} {salary.currency} {format_money(salary.amount)}"
        if salary
        else ""
    )
    return {
        "contract_date": (
            f"{contract_date.year:04d}年"
            f"{contract_date.month:02d}月"
            f"{contract_date.day:02d}日"
        ),
        "employee_name": employee.display_name,
        "salutation_name": employee.display_name,
        "salutation": "先生" if employee.gender == "male" else "女士",
        "start_year": effective_date.year,
        "start_month": effective_date.month,
        "start_day": effective_date.day,
        "department_text": (
            f"{assignment.department.display_name} "
            if assignment and assignment.department
            else ""
        ),
        "position_text": positions,
        "work_location": (
            assignment.project.work_location or assignment.project.name
            if assignment and assignment.project
            else ""
        ),
        "salary_text": salary_text,
        "probation_months_text": f"{probation:g}個月",
        "contract_annual_leave_text": f"{annual_leave:g}天",
        "notice_period_text": f"{notice_period:g}天",
        "primary_identity_no": identity.identity_number if identity else "",
    }
