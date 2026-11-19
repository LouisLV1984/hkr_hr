"""People away today and in the coming week, shared by the two HR overviews."""
from datetime import timedelta

from tools.attendance_policy import saved_leave_units


def leave_outlook(employees, today):
    end = today + timedelta(days=7)
    result = {"today": [], "week": [], "injury": [], "by_employee": {}}
    for employee in employees:
        if not employee.is_active_on(today):
            continue
        absences = []
        days_off = set()
        for record in employee.annual_leave_records:
            if record.status != "active" or record.leave_date > end or (record.end_date or record.leave_date) < today:
                continue
            days = {day for day, units in saved_leave_units(record).items() if today <= day <= end and units > 0}
            if days:
                absences.append((min(days), record.leave_type))
                days_off.update(days)
        if today in days_off:
            result["today"].append(employee)
        if any(day > today for day in days_off):
            result["week"].append(employee)
        if any(
            injury.status == "active" and injury.payroll_start_date <= today
            and (injury.payroll_end_date is None or injury.payroll_end_date >= today)
            for injury in employee.work_injury_periods
        ):
            result["injury"].append(employee)
            absences.append((today, "injury"))
        result["by_employee"][employee.id] = sorted(absences)
    return result
