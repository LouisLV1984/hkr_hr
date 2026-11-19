"""Date-specific attendance only where a salary change affects a period."""
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from types import SimpleNamespace
from tools.hr_core import current_salary_on

FIELDS = ("working_days", "ot_hours", "sunday_holiday_days", "large_ecall_count")

def rate_windows(employee, start, end):
    windows, previous = [], object()
    day = start
    while day <= end:
        if not employee.is_active_on(day):
            day += timedelta(days=1)
            continue
        salary = current_salary_on(employee, day)
        signature = (salary.salary_basis, salary.amount, salary.monthly_pay_method) if salary else None
        if signature != previous:
            windows.append({"start": day.isoformat(), "end": day.isoformat(),
                            "amount": str(salary.amount) if salary else None})
        else:
            windows[-1]["end"] = day.isoformat()
        previous = signature
        day += timedelta(days=1)
    return windows

def active_allocations(rows, windows):
    """Trim previously saved rate bands to employment; ignore empty outside bands."""
    result = []
    for row in rows:
        left, right = row["start"], row["end"]
        overlaps = [w for w in windows if w["start"] <= right and w["end"] >= left]
        if not overlaps:
            if any(Decimal(str(row.get(f, 0))) for f in FIELDS):
                raise ValueError("Attendance outside employment")
            continue
        if len(overlaps) != 1:
            raise ValueError("Allocation covers multiple rates")
        window = overlaps[0]
        result.append({**row, "start": max(left, window["start"]), "end": min(right, window["end"])})
    return result


def allocation_issue(employee, segment, start, end, *, recording_attendance=False):
    windows = rate_windows(employee, start, end)
    totals = {field: Decimal(str(getattr(segment, field, 0) or 0)) for field in FIELDS}
    has_flat_payment = any(getattr(segment, field, 0) for field in ("ecall_count", "other_allowance_amount"))
    if not any(totals.values()) and not has_flat_payment:
        return None
    if not windows:
        return f"{start} 至 {end} 沒有在職日期，請核對考勤日數。"
    # An unpriced attendance sheet can be filed; the payroll calculation still needs a salary.
    if recording_attendance and all(window["amount"] is None for window in windows):
        return None
    if any(window["amount"] is None for window in windows):
        return f"{start} 至 {end} 的在職日期缺少生效薪酬，請先補回薪酬記錄。"
    if not any(totals.values()):
        return None
    rows = getattr(segment, "rate_allocations", None) or []
    if len(windows) == 1 and not rows:
        return None
    try:
        rows = active_allocations(rows, windows)
        if [(r["start"], r["end"]) for r in rows] != [(r["start"], r["end"]) for r in windows]:
            raise ValueError()
        for field, total in totals.items():
            values = [Decimal(str(r.get(field, 0))) for r in rows]
            if any(not v.is_finite() or v < 0 for v in values) or sum(values) != total:
                raise ValueError()
            if field == "large_ecall_count" and any(v != int(v) for v in values):
                raise ValueError()
        for row in rows:
            days = Decimal(str(row.get("working_days", 0))) + Decimal(str(row.get("sunday_holiday_days", 0)))
            if days > (date.fromisoformat(row["end"]) - date.fromisoformat(row["start"])).days + 1:
                raise ValueError()
    except (KeyError, TypeError, ValueError, InvalidOperation):
        return f"{start:%Y-%m-%d} 至 {end:%Y-%m-%d} 跨薪酬生效日，請在考勤按日期分配日數、OT 及大 E-CALL。"
    return None

def rated_segments(employee, segments, start, end):
    for segment in segments:
        issue = allocation_issue(employee, segment, start, end)
        if issue:
            raise ValueError(issue)
        rows = getattr(segment, "rate_allocations", None)
        windows = rate_windows(employee, start, end)
        if not windows:
            continue
        if len(windows) == 1 or not rows:
            yield segment, date.fromisoformat(windows[0]["start"]), date.fromisoformat(windows[-1]["end"])
            continue
        for index, row in enumerate(active_allocations(rows, windows)):
            values = {field: Decimal(str(row.get(field, 0))) for field in FIELDS}
            values.update(id=getattr(segment, "id", None), project=segment.project,
                          project_id=segment.project_id, period_kind=segment.period_kind,
                          ecall_count=segment.ecall_count if index == 0 else 0,
                          other_allowance_amount=segment.other_allowance_amount if index == 0 else 0,
                          rate_start=date.fromisoformat(row["start"]), rate_end=date.fromisoformat(row["end"]))
            yield SimpleNamespace(**values), values["rate_start"], values["rate_end"]

def summary_rate_issues(employee, summary):
    from tools.attendance_policy import attendance_period_ranges
    if not summary:
        return []
    bounds = attendance_period_ranges(summary.year_month)
    return list(dict.fromkeys(issue for s in summary.segments
        if s.period_kind in bounds
        if (issue := allocation_issue(employee, s, *bounds[s.period_kind]))))
