"""Admin-only read-only checks over historical attendance, injuries, and credentials."""
from datetime import date
from decimal import Decimal

from models import (
    AttendanceBatchItem,
    AttendanceMonthlySummary,
    AuditLog,
    Employee,
    EmployeeDocument,
    EmployeeIdentity,
    EmployeeQualification,
    EmployeeVisa,
    EmployeeWorkInjuryPeriod,
    PayrollEmployeeResult,
    PayrollRun,
    db,
)
from tools.datetime_utils import hong_kong_datetime
from tools.hr_core import current_assignment_on, current_salary_on
from tools.profile_integrity import CREDENTIAL_GROUPS, credential_state


ACTUAL_PERIODS = ("current_1_20", "previous_21_end")


def _decimal(value):
    return Decimal(str(value or 0))


def _summarize_snapshot_segments(segments):
    totals = {
        "working_days": Decimal("0"),
        "ot_hours": Decimal("0"),
        "sunday_holiday_days": Decimal("0"),
        "large_ecall_count": 0,
        "ecall_count": 0,
    }
    for row in segments or ():
        if row.get("period_kind") not in ACTUAL_PERIODS:
            continue
        totals["working_days"] += _decimal(row.get("working_days"))
        totals["ot_hours"] += _decimal(row.get("ot_hours"))
        totals["sunday_holiday_days"] += _decimal(row.get("sunday_holiday_days"))
        totals["large_ecall_count"] += int(row.get("large_ecall_count") or 0)
        totals["ecall_count"] += int(row.get("ecall_count") or 0)
    return totals


def _summarize_live_summary(summary):
    if not summary or summary.status != "received":
        return None
    totals = {
        "working_days": Decimal("0"),
        "ot_hours": Decimal("0"),
        "sunday_holiday_days": Decimal("0"),
        "large_ecall_count": 0,
        "ecall_count": 0,
    }
    for row in summary.segments:
        if row.period_kind not in ACTUAL_PERIODS:
            continue
        totals["working_days"] += _decimal(row.working_days)
        totals["ot_hours"] += _decimal(row.ot_hours)
        totals["sunday_holiday_days"] += _decimal(row.sunday_holiday_days)
        totals["large_ecall_count"] += int(row.large_ecall_count or 0)
        totals["ecall_count"] += int(row.ecall_count or 0)
    return totals


def _latest_replacement_target(doc):
    current = doc
    seen = {doc.id}
    while current and current.replaced_by_document_id:
        next_id = current.replaced_by_document_id
        if next_id in seen:
            break
        seen.add(next_id)
        nxt = db.session.get(EmployeeDocument, next_id)
        if not nxt:
            break
        current = nxt
    return None if current.id == doc.id else current


def _find_old_snapshot(old_doc, batch_item, summary):
    if batch_item and batch_item.archived_summary:
        return batch_item.archived_summary
    if not summary:
        return None
    logs = (
        AuditLog.query.filter_by(
            entity_type="AttendanceMonthlySummary",
            entity_id=summary.id,
        )
        .order_by(AuditLog.id.desc())
        .all()
    )
    for log in logs:
        for snapshot in (log.after_json, log.before_json):
            if (
                snapshot
                and snapshot.get("document_id") == old_doc.id
                and "segments" in snapshot
            ):
                return snapshot
    return None


def replaced_attendance_rows():
    replaced_docs = (
        EmployeeDocument.query.filter_by(
            category="attendance_pdf",
            status="replaced",
        )
        .order_by(EmployeeDocument.effective_month.desc(), EmployeeDocument.id.desc())
        .all()
    )
    rows = []
    for old_doc in replaced_docs:
        current_doc = _latest_replacement_target(old_doc)
        summary = (
            AttendanceMonthlySummary.query.filter_by(
                employee_id=old_doc.employee_id,
                year_month=old_doc.effective_month,
            ).first()
            if old_doc.effective_month
            else None
        )
        item_candidates = [
            item
            for item in AttendanceBatchItem.query.filter_by(
                employee_id=old_doc.employee_id,
                original_filename=old_doc.original_filename,
            )
            .order_by(AttendanceBatchItem.id.desc())
            .all()
            if item.effective_year_month == old_doc.effective_month
            and (
                not old_doc.content_sha256
                or item.content_sha256 == old_doc.content_sha256
            )
        ]
        batch_item = next(
            (item for item in item_candidates if item.status == "replaced"),
            item_candidates[0] if item_candidates else None,
        )
        old_snapshot = _find_old_snapshot(old_doc, batch_item, summary)
        old_totals = (
            _summarize_snapshot_segments(old_snapshot.get("segments"))
            if old_snapshot
            else None
        )
        current_totals = _summarize_live_summary(summary)
        figures_differ = bool(
            old_totals is not None
            and current_totals is not None
            and old_totals != current_totals
        )
        payroll_rows = []
        if old_doc.effective_month:
            results = (
                PayrollEmployeeResult.query.join(
                    PayrollRun, PayrollEmployeeResult.run_id == PayrollRun.id
                )
                .filter(
                    PayrollEmployeeResult.employee_id == old_doc.employee_id,
                    PayrollRun.year_month == old_doc.effective_month,
                )
                .order_by(PayrollRun.id.desc())
                .all()
            )
            payroll_rows = [
                {
                    "run_id": res.run_id,
                    "created_at_hkt": hong_kong_datetime(res.run.created_at),
                    "currency": res.currency,
                    "ot_amount": res.ot_amount,
                    "gross_amount": res.gross_amount,
                    "net_amount": res.net_amount,
                }
                for res in results
            ]
        different_file = bool(
            current_doc
            and (
                (
                    old_doc.content_sha256
                    and current_doc.content_sha256
                    and old_doc.content_sha256 != current_doc.content_sha256
                )
                or old_doc.original_filename != current_doc.original_filename
            )
        )
        rows.append(
            {
                "employee": old_doc.employee,
                "year_month": old_doc.effective_month,
                "old_doc": old_doc,
                "current_doc": current_doc,
                "summary": summary,
                "batch_item": batch_item,
                "old_totals": old_totals,
                "current_totals": current_totals,
                "figures_differ": figures_differ,
                "different_file": different_file,
                "filename_changed": bool(
                    current_doc
                    and old_doc.original_filename != current_doc.original_filename
                ),
                "payroll_results": payroll_rows,
            }
        )
    return rows


def daily_injury_earnings_rows():
    injuries = (
        EmployeeWorkInjuryPeriod.query.filter_by(status="active")
        .order_by(
            EmployeeWorkInjuryPeriod.accident_date.desc(),
            EmployeeWorkInjuryPeriod.id.desc(),
        )
        .all()
    )
    rows = []
    for injury in injuries:
        assignment = current_assignment_on(injury.employee, injury.accident_date)
        salary = current_salary_on(injury.employee, injury.accident_date)
        group = assignment.payroll_group if assignment else injury.employee.payroll_group
        if group != "site_daily" and not (salary and salary.salary_basis == "daily"):
            continue
        daily_rate = (
            salary.amount
            if (salary and salary.salary_basis == "daily")
            else None
        )
        suspect = bool(
            daily_rate is not None
            and injury.confirmed_monthly_earnings <= daily_rate * Decimal("5")
        )
        start_ym = injury.payroll_start_date.strftime("%Y-%m")
        end_ym = (
            injury.payroll_end_date.strftime("%Y-%m")
            if injury.payroll_end_date
            else None
        )
        query = (
            PayrollEmployeeResult.query.join(
                PayrollRun, PayrollEmployeeResult.run_id == PayrollRun.id
            )
            .filter(
                PayrollEmployeeResult.employee_id == injury.employee_id,
                PayrollRun.year_month >= start_ym,
            )
        )
        if end_ym:
            query = query.filter(PayrollRun.year_month <= end_ym)
        payroll_rows = [
            {
                "year_month": res.run.year_month,
                "run_id": res.run_id,
                "created_at_hkt": hong_kong_datetime(res.run.created_at),
                "work_injury_days": res.work_injury_days,
                "work_injury_amount": res.work_injury_amount,
                "net_amount": res.net_amount,
                "currency": res.currency,
            }
            for res in query.order_by(
                PayrollRun.year_month.desc(), PayrollRun.id.desc()
            ).all()
        ]
        rows.append(
            {
                "employee": injury.employee,
                "injury": injury,
                "daily_rate": daily_rate,
                "salary_currency": salary.currency if salary else injury.currency,
                "suspect": suspect,
                "payroll_results": payroll_rows,
            }
        )
    return rows


def mask_credential_no(item):
    if isinstance(item, EmployeeIdentity):
        raw = str(item.identity_number or "").strip()
        if not raw:
            return "—"
        compact = "".join(char for char in raw if char.isalnum())
        return f"{compact[:4]}{'*' * max(4, len(compact) - 4)}"
    if isinstance(item, EmployeeVisa):
        return str(item.visa_no or "").strip() or "—"
    return str(item.certificate_no or "").strip() or "—"


def _credential_kind_and_label(item):
    if isinstance(item, EmployeeIdentity):
        return "identity", item.identity_type
    if isinstance(item, EmployeeVisa):
        return (
            "visa",
            item.visa_category.display_name if item.visa_category else "—",
        )
    if isinstance(item, EmployeeQualification):
        return "qualification", item.qualification_name
    return (
        "certificate",
        item.certificate_type.display_name if item.certificate_type else "—",
    )


def unlinked_renewal_rows(today=None):
    today = today or date.today()
    rows = []
    for employee in Employee.query.order_by(Employee.employee_no).all():
        if not employee.employed_during(today, today):
            continue
        for model, (attr, type_field) in CREDENTIAL_GROUPS.items():
            active_items = [
                item for item in getattr(employee, attr) if item.status == "active"
            ]
            grouped = {}
            for item in active_items:
                if model is EmployeeQualification:
                    key = (
                        item.category,
                        (item.qualification_name or "").strip().casefold(),
                    )
                else:
                    key = getattr(item, type_field)
                grouped.setdefault(key, []).append(item)
            for group_items in grouped.values():
                if len(group_items) < 2:
                    continue
                for old in group_items:
                    state = credential_state(old, today)
                    if state["code"] not in {"expired", "expiring"}:
                        continue
                    candidates = [
                        cand
                        for cand in group_items
                        if cand.id != old.id
                        and cand.renews_id is None
                        and (
                            getattr(cand, "is_long_term", False)
                            or (
                                cand.expiry_date
                                and old.expiry_date
                                and cand.expiry_date > old.expiry_date
                            )
                        )
                    ]
                    if not candidates:
                        continue
                    best = max(
                        candidates,
                        key=lambda cand: (
                            bool(getattr(cand, "is_long_term", False)),
                            cand.expiry_date or date.min,
                            cand.id,
                        ),
                    )
                    kind, label = _credential_kind_and_label(old)
                    rows.append(
                        {
                            "employee": employee,
                            "kind": kind,
                            "label": label,
                            "state_code": state["code"],
                            "old_no": mask_credential_no(old),
                            "old_expiry": old.expiry_date,
                            "candidate_no": mask_credential_no(best),
                            "candidate_expiry": best.expiry_date,
                            "candidate_long_term": bool(
                                getattr(best, "is_long_term", False)
                            ),
                            "anchor": f"credential-{kind}-{old.id}",
                        }
                    )
    return rows
