"""Shared half-day validation and derived review warnings; never edits attendance."""
from datetime import date

from models import AuditLog, Employee, db


def half_day_span(start, end, start_session="am", end_session="pm"):
    return (start.toordinal() * 2 + (start_session == "pm"),
            end.toordinal() * 2 + 1 + (end_session == "pm"))


def absence_spans(employee):
    for row in employee.annual_leave_records:
        if row.status == "active":
            yield "leave", row, half_day_span(row.leave_date, row.end_date or row.leave_date,
                                               row.start_session, row.end_session)
    for row in employee.work_injury_periods:
        if row.status == "active":
            yield "injury", row, half_day_span(row.payroll_start_date, row.payroll_end_date or date.max)


def overlaps(left, right):
    return max(left[0], right[0]) < min(left[1], right[1])


def conflicting_absence(employee, start, end, start_session="am", end_session="pm", exclude=None):
    # Serialize source writes for this employee on PostgreSQL; no new workflow state.
    db.session.execute(db.select(Employee.id).where(Employee.id == employee.id).with_for_update())
    span = half_day_span(start, end or date.max, start_session, end_session)
    for kind, row, existing in absence_spans(employee):
        if (kind, row.id) != exclude and overlaps(span, existing):
            return kind, row
    return None


def absence_data_issues(employee, start, end):
    """Legacy records stay untouched, but contradictory payroll inputs are blocked."""
    from tools.attendance_policy import saved_leave_days
    target = half_day_span(start, end)
    records = [(kind, row, span) for kind, row, span in absence_spans(employee)
               if overlaps(target, span)]
    issues = []
    for index, (kind, row, span) in enumerate(records):
        if kind == "leave" and row.days != saved_leave_days(row):
            if "leave.inconsistent_days" not in issues:
                issues.append("leave.inconsistent_days")
        if any(overlaps(span, other[2]) for other in records[index + 1:]):
            if "leave.overlap" not in issues:
                issues.append("leave.overlap")
    return issues


def absences_changed_since_attendance(employee, summary, start, end):
    if not summary or not summary.confirmed_at:
        return False
    saved_at = summary.confirmed_at
    target = half_day_span(start, end)
    # Include withdrawn records: withdrawing an absence must also prompt review.
    for row in employee.annual_leave_records:
        if row.updated_at and row.updated_at > saved_at and overlaps(target, half_day_span(
                row.leave_date, row.end_date or row.leave_date, row.start_session, row.end_session)):
            return True
    for row in employee.work_injury_periods:
        if row.updated_at and row.updated_at > saved_at and overlaps(target, half_day_span(
                row.payroll_start_date, row.payroll_end_date or date.max)):
            return True
    # A correction can move the entire date range OUT of this attendance window.
    audits = AuditLog.query.filter(AuditLog.employee_id == employee.id,
                                  AuditLog.created_at > saved_at,
                                  AuditLog.action.in_(["leave_corrected", "work_injury_corrected"]))
    for audit in audits:
        before = audit.before_json or {}
        start_value = before.get("start_date") or before.get("payroll_start_date")
        end_value = before.get("end_date") or before.get("payroll_end_date")
        if start_value:
            old_start = date.fromisoformat(start_value)
            old_end = date.fromisoformat(end_value) if end_value else date.max
            if overlaps(target, half_day_span(old_start, old_end)):
                return True
    return False


def leave_date_label(record, translate):
    start, end = record.leave_date, record.end_date or record.leave_date
    am, pm = translate("employee.morning"), translate("employee.afternoon")
    if start == end:
        session = "" if record.start_session == "am" and record.end_session == "pm" else (
            " " + (am if record.start_session == "am" else pm))
        return f"{start:%Y-%m-%d}{session}"
    return f"{start:%Y-%m-%d} {am if record.start_session == 'am' else pm} – {end:%Y-%m-%d} {am if record.end_session == 'am' else pm}"
