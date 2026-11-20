"""Explicit monthly cost allocation, independent of employment history."""
from datetime import date, timedelta
from decimal import Decimal

from hkr_hr.platform.db import db
from hkr_hr.references.api import WorkProject
from hkr_hr.employees.api import current_assignment_on, current_salary_on
from hkr_hr.platform.dates import parse_year_month
from hkr_hr.attendance.service.policy import employee_payroll_holidays, scheduled_work_units

WORKDAY_BASIS = 'scheduled_workdays'


def uses_workday_allocation(rows):
    return bool(rows) and all(row.get('basis') == WORKDAY_BASIS for row in rows)


class ProjectAllocationError(ValueError):
    pass


def allocation_dates(employee, year_month, rows):
    if not rows:
        return {}
    start, end = parse_year_month(year_month)
    workdays_only = uses_workday_allocation(rows)
    if any(row.get('basis') == WORKDAY_BASIS for row in rows) and not workdays_only:
        raise ProjectAllocationError('allocation.invalid')
    result = {}
    for row in rows:
        try:
            first, last = date.fromisoformat(row['start']), date.fromisoformat(row['end'])
            project = db.session.get(WorkProject, int(row['project_id']))
        except (ValueError, TypeError, KeyError):
            raise ProjectAllocationError('allocation.invalid') from None
        if not project or project.code.upper() == 'UNASSIGNED' or first < start or last > end or last < first:
            raise ProjectAllocationError('allocation.invalid')
        day = first
        while day <= last:
            if day in result:
                raise ProjectAllocationError('allocation.overlap')
            salary = current_salary_on(employee, day)
            if salary and (salary.salary_basis != 'monthly' or salary.monthly_pay_method == 'attendance_days'):
                raise ProjectAllocationError('allocation.monthly_only')
            result[day] = project
            day += timedelta(days=1)
    if not workdays_only and len(result) != (end - start).days + 1:
        raise ProjectAllocationError('allocation.cover_month')
    return result


def allocation_weights(employee, year_month, rows):
    """Calendar-day pay shares; legacy ranges retain their saved rule until reconfirmed."""
    requested = allocation_dates(employee, year_month, rows)
    if not requested:
        return {}
    if not uses_workday_allocation(rows):
        return {day: [(project, Decimal('1'))] for day, project in requested.items()}
    start, end = parse_year_month(year_month)
    holidays = employee_payroll_holidays(employee, start, end)
    result = {}
    day = start
    while day <= end:
        salary = current_salary_on(employee, day)
        if not salary:
            # Dates before the first salary record produce no monthly pay share.
            result[day] = []
            day += timedelta(days=1)
            continue
        assignment = current_assignment_on(employee, day)
        if not assignment or not assignment.project or assignment.project.code.upper() == 'UNASSIGNED':
            raise ProjectAllocationError('allocation.missing_home')
        if salary and (salary.salary_basis != 'monthly' or salary.monthly_pay_method == 'attendance_days'):
            raise ProjectAllocationError('allocation.monthly_only')
        home, target = assignment.project, requested.get(day, assignment.project)
        units = Decimal('0') if day in holidays else scheduled_work_units(assignment, day)
        if target.id == home.id or not units:
            result[day] = [(home, Decimal('1'))]
        else:
            result[day] = [(target, units)]
            if units < 1:
                result[day].append((home, Decimal('1') - units))
        day += timedelta(days=1)
    return result


def update_allocation_from_form(summary, form):
    # Older clients keep existing explicit allocation; changed months are revalidated.
    if 'allocation_present' not in form:
        allocation_weights(summary.employee, summary.year_month, summary.monthly_project_allocation)
        return
    rows = []
    if form.get('allocation_enabled') == 'on':
        projects = form.getlist('allocation_project')
        starts, ends = form.getlist('allocation_start'), form.getlist('allocation_end')
        if not projects or len(projects) != len(starts) or len(projects) != len(ends):
            raise ProjectAllocationError('allocation.invalid')
        basis = (WORKDAY_BASIS if not summary.monthly_project_allocation
                 or uses_workday_allocation(summary.monthly_project_allocation)
                 or form.get('allocation_convert') == 'on' else 'calendar')
        rows = [dict(project_id=p, start=s, end=e, basis=basis) for p, s, e in zip(projects, starts, ends)]
        allocation_weights(summary.employee, summary.year_month, rows)
        for row in rows:
            row['project_id'] = int(row['project_id'])
            row['project_name'] = db.session.get(WorkProject, row['project_id']).name
    summary.monthly_project_allocation = rows or None
