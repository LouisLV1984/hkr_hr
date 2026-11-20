"""Localized export policy messages wrapping pure ``export_rules``."""
from __future__ import annotations

from flask import has_request_context, session

from hkr_hr.payroll.rules.export_rules import export_issues, is_payroll_ready
from hkr_hr.platform.i18n import TRANSLATIONS, normalize_language


def policy_text(key):
    language = normalize_language(session.get("lang")) if has_request_context() else "zh-Hant"
    return TRANSLATIONS[language].get(key, key)


def export_message(rows):
    return "；".join(
        f"{row['employee'].employee_no} · {row['employee'].display_name}："
        + " / ".join(policy_text(issue) for issue in export_issues(row))
        for row in rows
        if export_issues(row)
    )


def saved_export_message(run, groups=None, employee_ids=None):
    """Downloads reproduce the saved run. Current changes belong to a new calculation."""
    rows = []
    for result in run.employee_results:
        if employee_ids is not None and result.employee_id not in employee_ids:
            continue
        if groups is not None and (result.calculation_json or {}).get("group") not in groups:
            continue
        rows.append(
            {
                "employee": result.employee,
                "net_amount": result.net_amount,
                "warnings": result.warnings_json or [],
            }
        )
    return export_message(rows)


__all__ = [
    "export_issues",
    "export_message",
    "is_payroll_ready",
    "policy_text",
    "saved_export_message",
]
