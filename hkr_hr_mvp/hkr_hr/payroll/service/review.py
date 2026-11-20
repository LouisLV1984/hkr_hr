"""Navigation and source labels for the monthly payroll review desk."""
from datetime import date, timedelta

from flask import url_for

from hkr_hr.attendance.api import attendance_period_ranges
from hkr_hr.attendance.api import rate_windows


def originating_payroll(values, year_month):
    if values.get("from_payroll") == "1" and year_month:
        try:
            date.fromisoformat(year_month + "-01")
        except ValueError:
            return None
        return url_for(
            "payroll.attendance_payroll",
            year_month=year_month,
            payroll_group=values.get("pay_group") or "all",
            payroll_entity_id=values.get("pay_entity", ""),
            status=values.get("pay_status") or "all",
            q=values.get("pay_q") or None,
            employee_id=values.get("pay_employee") or None,
        )


def salary_gaps(employee, summary):
    if not summary:
        return []
    periods = attendance_period_ranges(summary.year_month)
    bounds = {periods[s.period_kind] for s in summary.segments if s.period_kind in periods
              and any(getattr(s, field, 0) for field in ("working_days", "ot_hours", "sunday_holiday_days",
                      "large_ecall_count", "ecall_count", "other_allowance_amount"))}
    gaps = []
    for start, end in sorted(bounds):
        for window in rate_windows(employee, start, end):
            if window["amount"] is not None:
                continue
            first, last = date.fromisoformat(window["start"]), date.fromisoformat(window["end"])
            if gaps and first <= gaps[-1][1] + timedelta(days=1):
                gaps[-1] = (gaps[-1][0], max(gaps[-1][1], last))
            else:
                gaps.append((first, last))
    return [f"{first} – {last}" for first, last in gaps]


def review_sources(row, context):
    employee = row["employee"]
    month = context["pay_month"]
    summary = row.get("attendance")
    def profile(tab, **options):
        return url_for("employees.view_employee", employee_id=employee.id, tab=tab, **options, **context)
    attendance = (url_for("attendance.attendance_home", month=month, view="collection",
                          summary_id=summary.id, **context) if summary and summary.id else None)
    missing = url_for("attendance.attendance_home", month=month, view="details", status="missing",
                      _anchor=f"missing-{employee.id}", **context)
    sources = {
        "salary": profile("employment", focus="salary"),
        "terms": profile("employment"),
        "bank": profile("personal", focus="bank"),
        "entity": profile("employment", focus="pay_entity"),
        "leave": profile("leave"),
        "mpf": profile("employment", _anchor="pay-mpf"),
        "allowance": profile("employment", _anchor="pay-allowances"),
        "legacy": profile("attendance", _anchor="legacy-adjustments"),
        "departure": profile("employment_status"),
        "attendance": attendance or profile("leave" if row.get("work_injury_days") else "employment",
                                            _anchor="employee-leave" if row.get("work_injury_days") else "pay-attendance-policy"),
        "snapshot": profile("attendance", _anchor="pay-snapshot-" + str((row.get("tail_source") or {}).get("snapshot_id"))),
        "missing": missing,
    }
    actions = []
    blockers = row["blockers"]
    salary_issue = any("缺少生效薪酬" in msg for msg in blockers)
    if salary_issue or "薪酬未設定" in blockers:
        actions.append(("hr.fill_salary", sources["salary"], salary_gaps(employee, summary) if salary_issue else []))
    if "出糧銀行資料未填寫" in blockers:
        actions.append(("hr.fill_bank", sources["bank"], []))
    if not row["assignment"] or not row["assignment"].payroll_entity_id:
        actions.append(("hr.fill_entity", sources["entity"], []))
    if "考勤未收" in blockers:
        actions.append(("hr.missing_sheet", missing, []))
    if "leave.attendance_recheck" in row["warnings"]:
        key = "hr.exempt_check" if summary and summary.status == "not_required" else "hr.sheet_check"
        actions.append((key, sources["attendance"], []))
    for msg in blockers:
        if msg in {"薪酬未設定", "出糧銀行資料未填寫", "考勤未收"} or "缺少生效薪酬" in msg:
            continue
        target = "leave" if msg.startswith("leave.") else "attendance"
        if "固定補貼" in msg:
            target = "allowance"
        actions.append((msg, sources[target], []))
    return actions, sources
