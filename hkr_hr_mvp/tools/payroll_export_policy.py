"""HR-approved export checks, independent of the ability to calculate pay."""
from decimal import Decimal

from flask import has_request_context, session
from tools.i18n import TRANSLATIONS, normalize_language


def policy_text(key):
    language = normalize_language(session.get("lang")) if has_request_context() else "zh-Hant"
    return TRANSLATIONS[language].get(key, key)


def export_issues(row):
    issues = []
    if "assignment" in row and not getattr(row["assignment"], "payroll_entity_id", None):
        issues.append("hr.fill_entity")
    if Decimal(str(row.get("net_amount") or 0)) < 0:
        issues.append("review.negative_net")
    if "leave.attendance_recheck" in (row.get("warnings") or []):
        issues.append("leave.attendance_recheck")
    return issues


def is_payroll_ready(row):
    return not row['blockers'] and not export_issues(row)


def export_message(rows):
    return "；".join(
        f"{row['employee'].employee_no} · {row['employee'].display_name}："
        + " / ".join(policy_text(issue) for issue in export_issues(row))
        for row in rows if export_issues(row)
    )


def saved_export_message(run, groups=None, employee_ids=None):
    """Downloads reproduce the saved run. Current changes belong to a new calculation."""
    rows = []
    for result in run.employee_results:
        if employee_ids is not None and result.employee_id not in employee_ids:
            continue
        if groups is not None and (result.calculation_json or {}).get("group") not in groups:
            continue
        rows.append({"employee": result.employee, "net_amount": result.net_amount,
                     "warnings": result.warnings_json or []})
    return export_message(rows)
