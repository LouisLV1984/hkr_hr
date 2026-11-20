"""Batch eager-loading options for employee workbenches."""
from __future__ import annotations

from sqlalchemy.orm import selectinload

from hkr_hr.employees.models import Employee


def workbench_options():
    return tuple(
        selectinload(getattr(Employee, name))
        for name in (
            "employee_type",
            "employment_periods",
            "assignments",
            "salaries",
            "identities",
            "documents",
            "certificates",
            "visas",
            "mpf_enrollments",
            "bank_accounts",
            "annual_leave_records",
            "annual_leave_balances",
            "work_injury_periods",
            "attendance_policies",
            "comp_leave_credits",
        )
    )
