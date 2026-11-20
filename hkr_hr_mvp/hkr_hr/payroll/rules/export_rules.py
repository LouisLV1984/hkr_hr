"""Pure HR-approved payroll export readiness rules (zero Flask/DB)."""
from __future__ import annotations

from decimal import Decimal


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
    return not row["blockers"] and not export_issues(row)
