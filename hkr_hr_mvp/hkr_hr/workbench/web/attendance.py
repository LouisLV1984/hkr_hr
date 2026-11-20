from hkr_hr.payroll.api import originating_payroll
from types import SimpleNamespace
from hkr_hr.attendance.api import rate_windows, allocation_issue, FIELDS
import hashlib
import hmac
import json
import shutil
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    send_file,
    url_for,
)
from flask_login import current_user, login_required

from hkr_hr.platform.db import AuditLog, db
from hkr_hr.attendance.api import AttendanceBatch, AttendanceBatchItem, AttendanceMonthlySummary, AttendanceSegment, AttendanceSpecialDay
from hkr_hr.employees.api import Employee, EmployeeAttendancePolicy
from hkr_hr.leave.api import EmployeeAnnualLeaveRecord, EmployeeCompLeaveCredit, EmployeeWorkInjuryPeriod
from hkr_hr.documents.api import EmployeeDocument
from hkr_hr.payroll.api import PayrollEmployeeResult, PayrollRun
from hkr_hr.references.api import WorkProject
from hkr_hr.payroll.api import correction_history_for as history_for
from hkr_hr.attendance.api import assignment_workweek_days, attendance_required, injury_covers_month, automatic_attendance_rows as policy_automatic_attendance_rows, employee_payroll_holidays, holiday_calendar_kind_for_payroll_group, policy_on, special_work_day_units
from hkr_hr.platform.dates import attendance_period_bounds, PAYROLL_GROUPS, current_month, parse_bool, parse_date, parse_decimal, parse_year_month, previous_month
from hkr_hr.leave.api import allocate_annual_leave_with_comp, clear_leave_allocations
from hkr_hr.platform.files import copy_file_to_employee, file_sha256, store_employee_file
from hkr_hr.employees.api import create_assignment, current_assignment_on, current_salary_on
from hkr_hr.documents.api import find_duplicate_employee_document
from hkr_hr.references.api import reference_options
from hkr_hr.platform.audit import write_audit
from hkr_hr.platform.search import chinese_search_variants
from hkr_hr.platform.security import UploadValidationError, validate_uploaded_file
from hkr_hr.attendance.api import ProjectAllocationError, update_allocation_from_form


attendance_bp = Blueprint("attendance", __name__)


def batch_no():
    return f"ATT-{datetime.utcnow():%Y%m%d-%H%M%S-%f}"


def employees_expected_for_month(year_month):
    month_start, month_end = parse_year_month(year_month)
    rows = [
        employee
        for employee in Employee.query.order_by(Employee.employee_no).all()
        if employee.employed_during(month_start, month_end)
    ]
    summaries = {
        row.employee_id: row
        for row in AttendanceMonthlySummary.query.filter_by(
            year_month=year_month,
        ).all()
    }
    return [
        employee
        for employee in rows
        if attendance_required(employee, year_month, summaries.get(employee.id))
    ]


def attendance_segments(summary, kind):
    if not summary:
        return []
    return [item for item in summary.segments if item.period_kind == kind]


def selected_context():
    selected_batch = None
    selected_item = None
    batch_id = request.args.get("batch_id", type=int)
    item_id = request.args.get("item_id", type=int)
    if batch_id:
        selected_batch = db.session.get(AttendanceBatch, batch_id)
    if item_id:
        selected_item = db.session.get(AttendanceBatchItem, item_id)
        selected_batch = selected_item.batch if selected_item else selected_batch
    return selected_batch, selected_item


def payroll_snapshot_exists(employee_id, year_month):
    if not employee_id or not year_month:
        return False
    return (
        db.session.query(PayrollEmployeeResult.id)
        .join(PayrollRun, PayrollEmployeeResult.run_id == PayrollRun.id)
        .filter(
            PayrollEmployeeResult.employee_id == employee_id,
            PayrollRun.year_month == year_month,
        )
        .first()
        is not None
    )


def automatic_attendance_rows(employee, start_date, end_date):
    return [
        {
            **row,
            "ot_hours": 0,
            "large_ecall_count": 0,
            "ecall_count": 0,
        }
        for row in policy_automatic_attendance_rows(
            employee,
            start_date,
            end_date,
        )
    ]


def automatic_forecast_rows(employee, year_month):
    month_start, month_end = parse_year_month(year_month)
    return automatic_attendance_rows(
        employee,
        month_start.replace(day=21),
        month_end,
    )


def generated_segment_rows(segments):
    return [
        {
            "project_id": item.project_id,
            "rate_allocations": item.rate_allocations,
            "working_days": item.working_days,
            "sunday_holiday_days": item.sunday_holiday_days,
            "ot_hours": 0,
            "large_ecall_count": 0,
            "ecall_count": 0,
        }
        for item in segments
    ]


def add_generated_segments(summary, period_kind, rows):
    for row in rows:
        db.session.add(
            AttendanceSegment(
                summary=summary,
                period_kind=period_kind,
                project_id=row.get("project_id"),
                rate_allocations=row.get("rate_allocations"),
                working_days=row.get("working_days", 0),
                ot_hours=0,
                sunday_holiday_days=row.get("sunday_holiday_days", 0),
                large_ecall_count=0,
                ecall_count=0,
            )
        )


def add_default_full_attendance(summary, employee, year_month):
    month_start, month_end = parse_year_month(year_month)
    previous_year_month = previous_month(year_month)
    previous_start, previous_end = parse_year_month(previous_year_month)
    previous_start = previous_start.replace(day=21)

    current_actual = automatic_attendance_rows(
        employee,
        month_start,
        min(month_end, month_start.replace(day=20)),
    )
    current_forecast = automatic_forecast_rows(employee, year_month)
    previous_summary = AttendanceMonthlySummary.query.filter_by(
        employee_id=employee.id,
        year_month=previous_year_month,
    ).first()
    previous_forecast_segments = attendance_segments(
        previous_summary,
        "current_21_end_forecast",
    )
    previous_forecast = (
        generated_segment_rows(previous_forecast_segments)
        if previous_forecast_segments
        else automatic_attendance_rows(
            employee,
            previous_start,
            previous_end,
        )
    )

    add_generated_segments(summary, "current_1_20", current_actual)
    add_generated_segments(
        summary,
        "current_21_end_forecast",
        current_forecast,
    )
    add_generated_segments(summary, "previous_21_end", previous_forecast)
    add_generated_segments(
        summary,
        "previous_21_end_forecast",
        previous_forecast,
    )


def attendance_segment_rows(employee, summary, year_month):
    bounds = attendance_period_bounds(year_month)
    rows = {}
    sources = {}

    current_actual = attendance_segments(summary, "current_1_20")
    rows["current_1_20"] = current_actual or automatic_attendance_rows(
        employee,
        *bounds["current_1_20"],
    )
    sources["current_1_20"] = "saved" if current_actual else "calendar"

    current_forecast = attendance_segments(
        summary,
        "current_21_end_forecast",
    )
    rows["current_21_end_forecast"] = (
        current_forecast or automatic_forecast_rows(employee, year_month)
    )
    sources["current_21_end_forecast"] = (
        "saved" if current_forecast else "calendar"
    )

    prior_summary = AttendanceMonthlySummary.query.filter_by(
        employee_id=employee.id,
        year_month=previous_month(year_month),
    ).first()
    prior_saved_forecast = attendance_segments(
        prior_summary,
        "current_21_end_forecast",
    )
    inferred_previous_tail = prior_saved_forecast or automatic_attendance_rows(
        employee,
        *bounds["previous_21_end"],
    )
    inferred_source = "prior_forecast" if prior_saved_forecast else "calendar"

    previous_actual = attendance_segments(summary, "previous_21_end")
    rows["previous_21_end"] = previous_actual or inferred_previous_tail
    sources["previous_21_end"] = (
        "saved" if previous_actual else inferred_source
    )

    previous_forecast = attendance_segments(
        summary,
        "previous_21_end_forecast",
    )
    rows["previous_21_end_forecast"] = (
        previous_forecast or inferred_previous_tail
    )
    sources["previous_21_end_forecast"] = (
        "saved" if previous_forecast else inferred_source
    )
    return rows, sources


def linked_absences_for_attendance(employee, year_month):
    if not employee:
        return []
    month_start, month_end = parse_year_month(year_month)
    previous_start, _ = parse_year_month(previous_month(year_month))
    window_start = previous_start.replace(day=21)
    rows = []

    def attendance_scope(start, end):
        if end < month_start:
            return "previous_tail"
        if start >= month_start:
            return "current_month"
        return "both_periods"

    for leave in EmployeeAnnualLeaveRecord.query.filter_by(
        employee_id=employee.id,
        status="active",
    ).all():
        end = leave.end_date or leave.leave_date
        if leave.leave_date <= month_end and end >= window_start:
            rows.append(
                {
                    "kind": leave.leave_type,
                    "start": leave.leave_date,
                    "end": end,
                    "days": leave.days,
                    "source": "leave",
                    "visible_start": max(leave.leave_date, window_start),
                    "visible_end": min(end, month_end),
                    "is_clipped": (
                        leave.leave_date < window_start or end > month_end
                    ),
                    "scope": attendance_scope(leave.leave_date, end),
                    "evidence_missing": (
                        leave.leave_type == "sick"
                        and not leave.evidence_document_id
                    ),
                }
            )
    for injury in EmployeeWorkInjuryPeriod.query.filter_by(
        employee_id=employee.id,
        status="active",
    ).all():
        end = injury.payroll_end_date or date.max
        if injury.payroll_start_date <= month_end and end >= window_start:
            rows.append(
                {
                    "kind": "work_injury",
                    "start": max(injury.payroll_start_date, window_start),
                    "end": min(end, month_end),
                    "days": (
                        min(end, month_end)
                        - max(injury.payroll_start_date, window_start)
                    ).days
                    + 1,
                    "source": "work_injury",
                    "visible_start": max(
                        injury.payroll_start_date,
                        window_start,
                    ),
                    "visible_end": min(end, month_end),
                    "is_clipped": False,
                    "scope": attendance_scope(
                        injury.payroll_start_date,
                        end,
                    ),
                    "evidence_missing": False,
                }
            )
    return sorted(rows, key=lambda item: (item["start"], item["kind"]))


def summary_snapshot(summary):
    return {
        "monthly_project_allocation": summary.monthly_project_allocation,
        "employee_id": summary.employee_id,
        "year_month": summary.year_month,
        "status": summary.status,
        "no_attendance_reason": summary.no_attendance_reason,
        "document_id": summary.document_id,
        "special_day_handling": summary.special_day_handling,
        "special_days": [
            {
                "work_date": item.work_date.isoformat(),
                "day_kind": item.day_kind,
                "session": item.session,
                "handling": item.handling,
                "days": str(item.days),
            }
            for item in summary.special_days
            if item.status == "active"
        ],
        "segments": [
            {
                "rate_allocations": item.rate_allocations,
                "period_kind": item.period_kind,
                "project_id": item.project_id,
                "project_name": item.project.name if item.project else None,
                "working_days": str(item.working_days),
                "ot_hours": str(item.ot_hours),
                "sunday_holiday_days": str(item.sunday_holiday_days),
                "large_ecall_count": item.large_ecall_count,
                "ecall_count": item.ecall_count,
                "other_allowance_amount": str(item.other_allowance_amount),
            }
            for item in summary.segments
        ],
    }


def attendance_summary_revision(summary):
    db.session.expire(summary, ["segments", "special_days"])
    snapshot = summary_snapshot(summary)
    snapshot["segments"] = sorted(
        snapshot.get("segments", []),
        key=lambda row: (row.get("period_kind") or "", row.get("project_id") or 0),
    )
    snapshot["special_days"] = sorted(
        snapshot.get("special_days", []),
        key=lambda row: (row.get("work_date") or "", row.get("session") or ""),
    )
    payload = json.dumps(
        {
            "snapshot": snapshot,
            "remarks": summary.remarks,
            "confirmed_at": (
                summary.confirmed_at.isoformat() if summary.confirmed_at else None
            ),
        },
        default=str,
        sort_keys=True,
    )
    return hmac.new(
        current_app.secret_key.encode(),
        payload.encode(),
        hashlib.sha256,
    ).hexdigest()


def set_summary_confirmed(summary):
    now = datetime.utcnow()
    summary.confirmed_by = current_user.id
    summary.confirmed_at = (
        max(now, summary.confirmed_at + timedelta(microseconds=1))
        if summary.confirmed_at
        else now
    )


def set_monthly_attendance_requirement(
    employee,
    year_month,
    requires_attendance,
):
    summary = AttendanceMonthlySummary.query.filter_by(
        employee_id=employee.id,
        year_month=year_month,
    ).first()
    if summary and summary.status == "received":
        return False
    if not summary:
        summary = AttendanceMonthlySummary(
            employee=employee,
            year_month=year_month,
            status="required",
        )
        db.session.add(summary)
        db.session.flush()
    before = summary_snapshot(summary)
    for segment in list(summary.segments):
        db.session.delete(segment)
    db.session.flush()
    set_summary_confirmed(summary)
    summary.document = None
    if requires_attendance:
        summary.status = "required"
        summary.no_attendance_reason = None
        action = "attendance_required"
        detail = f"{year_month}: 改回需要考勤表"
    else:
        summary.status = "not_required"
        summary.no_attendance_reason = "HR 設定本月免交考勤表"
        add_default_full_attendance(summary, employee, year_month)
        action = "attendance_not_required"
        detail = f"{year_month}: 本月免交考勤表"
    db.session.flush()
    write_audit(
        action,
        "AttendanceMonthlySummary",
        summary.id,
        employee_id=employee.id,
        detail=detail,
        before=before,
        after=summary_snapshot(summary),
    )
    return True


def archived_figures(item):
    if item.archived_summary:
        return item.archived_summary
    # Earlier batches stored the figures only in the attendance audit log.
    # An identical filename and hash may belong to several revisions.
    if not item.content_sha256:
        return None
    versions = EmployeeDocument.query.filter_by(
        employee_id=item.employee_id, effective_month=item.effective_year_month,
        category="attendance_pdf", status="replaced", original_filename=item.original_filename,
        content_sha256=item.content_sha256,
    ).limit(2).all()
    if len(versions) != 1:
        return None
    logs = AuditLog.query.filter_by(entity_type="AttendanceMonthlySummary", entity_id=item.summary_id)
    for log in logs.order_by(AuditLog.id.desc()):
        for snapshot in (log.after_json, log.before_json):
            if snapshot and snapshot.get("document_id") == versions[0].id and "segments" in snapshot:
                return snapshot
    return None


@attendance_bp.route("/attendance")
@login_required
def attendance_home():
    selected_batch, selected_item = selected_context()
    summary_id = request.args.get("summary_id", type=int)
    selected_summary = (
        db.session.get(AttendanceMonthlySummary, selected_item.summary_id)
        if selected_item and selected_item.summary_id
        else None
    )
    if selected_item and selected_item.status == "replaced":
        return render_template("attendance/replaced.html", item=selected_item, figures=archived_figures(selected_item))
    if summary_id:
        selected_summary = db.session.get(AttendanceMonthlySummary, summary_id)
    identity_correction_mode = bool(
        selected_summary
        and request.args.get("correct_identity") == "1"
    )
    year_month = (
        (
            selected_summary.year_month
            if selected_summary and not identity_correction_mode
            else None
        )
        or request.args.get("month")
        or (selected_item.effective_year_month if selected_item else None)
        or (selected_batch.year_month if selected_batch else None)
        or session.get("operating_month")
        or current_month()
    )
    try:
        datetime.strptime(str(year_month), "%Y-%m")
    except (TypeError, ValueError):
        year_month = current_month()
    session["operating_month"] = year_month
    view = request.args.get("view") or ("details" if request.args.get("status") else "collection")
    if request.args.get("batch_id") or request.args.get("item_id") or request.args.get("summary_id"):
        view = "collection"
    if view not in {"details", "collection", "monthly_exemptions", "policies"}:
        view = "details"
    detail_status = request.args.get("status", "missing")
    if detail_status not in {"expected", "missing", "received"}:
        detail_status = ""
    search = request.args.get("q", "").strip()
    policy_sort = request.args.get("sort", "employee")
    if policy_sort not in {"employee", "payroll_group"}:
        policy_sort = "employee"
    policy_direction = request.args.get("direction", "asc")
    if policy_direction not in {"asc", "desc"}:
        policy_direction = "asc"
    payroll_group_filter = request.args.get("payroll_group", "")
    position_id = request.args.get("position_id", type=int)
    month_start, month_end = parse_year_month(year_month)
    employed = [
        employee
        for employee in Employee.query.order_by(Employee.employee_no).all()
        if employee.employed_during(month_start, month_end)
    ]
    policy_rows = []
    search_variants = [item.casefold() for item in chinese_search_variants(search)]
    for employee in employed:
        haystack = f"{employee.employee_no} {employee.chinese_name or ''} {employee.english_name or ''}".casefold()
        if search_variants and not any(item in haystack for item in search_variants):
            continue
        if payroll_group_filter and employee.payroll_group != payroll_group_filter:
            continue
        assignment = current_assignment_on(employee, month_end)
        if position_id and (
            not assignment
            or position_id not in {
                item.position_id for item in assignment.positions
            }
        ):
            continue
        summary = AttendanceMonthlySummary.query.filter_by(
            employee_id=employee.id,
            year_month=year_month,
        ).first()
        policy = policy_on(employee.id, year_month)
        policy_rows.append(
            {
                "employee": employee,
                "policy": policy,
                "requires_attendance": attendance_required(
                    employee,
                    year_month,
                    summary,
                ),
                "monthly_status": summary.status if summary else None,
                "injury_exempt": not summary and injury_covers_month(employee, month_start, month_end),
            }
        )
    payroll_group_order = {
        "site_daily": 0,
        "site_monthly": 1,
        "management": 2,
        "unassigned": 3,
    }
    if policy_sort == "payroll_group":
        policy_rows.sort(
            key=lambda row: (
                payroll_group_order.get(row["employee"].payroll_group, 99),
                row["employee"].employee_no,
            ),
            reverse=policy_direction == "desc",
        )
    else:
        policy_rows.sort(
            key=lambda row: row["employee"].employee_no,
            reverse=policy_direction == "desc",
        )
    expected = employees_expected_for_month(year_month)
    received_all = AttendanceMonthlySummary.query.filter_by(
        year_month=year_month,
        status="received",
    ).all()
    not_required = AttendanceMonthlySummary.query.filter_by(
        year_month=year_month,
        status="not_required",
    ).order_by(AttendanceMonthlySummary.id).all()
    expected_ids = {employee.id for employee in expected}
    received = [row for row in received_all if row.employee_id in expected_ids]
    received_ids = {row.employee_id for row in received}
    missing = [item for item in expected if item.id not in received_ids]
    attendance_roster_projects = {}
    for employee in expected:
        assignments = [
            assignment
            for assignment in employee.assignments
            if assignment.status == "active"
            and assignment.effective_from <= month_end
            and (
                assignment.effective_to is None
                or assignment.effective_to >= month_start
            )
        ]
        attendance_roster_projects[employee.id] = list(
            dict.fromkeys(
                assignment.project.name
                for assignment in sorted(
                    assignments,
                    key=lambda item: (item.effective_from, item.id),
                )
                if assignment.project
            )
        )
    recent_batches = AttendanceBatch.query.order_by(
        AttendanceBatch.created_at.desc()
    ).limit(20).all()
    if view == "collection" and not selected_batch and not summary_id:
        month_batches = AttendanceBatch.query.filter_by(year_month=year_month)
        selected_batch = (
            month_batches.filter(AttendanceBatch.items.any(AttendanceBatchItem.status == "pending"))
            .order_by(AttendanceBatch.id.desc()).first()
            or month_batches.order_by(AttendanceBatch.id.desc()).first()
        )
    resume_batch = selected_batch
    other_pending_batches = []
    if view == "collection" and not selected_item and not summary_id:
        for batch in (
            AttendanceBatch.query.filter(
                AttendanceBatch.items.any(AttendanceBatchItem.status == "pending")
            )
            .order_by(AttendanceBatch.id.desc())
            .all()
        ):
            if resume_batch and batch.id == resume_batch.id:
                continue
            pending_items = [row for row in batch.items if row.status == "pending"]
            if not pending_items:
                continue
            target_month = pending_items[0].effective_year_month
            if batch.year_month != year_month or target_month != year_month:
                other_pending_batches.append(
                    {
                        "batch": batch,
                        "first_pending": pending_items[0],
                        "pending_count": len(pending_items),
                        "year_month": target_month,
                    }
                )
            if len(other_pending_batches) >= 5:
                break
    if summary_id:
        if selected_summary:
            selected_batch = None
            selected_item = None
    selected_employee_id = (
        request.args.get("employee_id", type=int)
        if not selected_summary or identity_correction_mode
        else selected_summary.employee_id
    )
    if not selected_employee_id and selected_summary:
        selected_employee_id = selected_summary.employee_id
    selected_employee = (
        db.session.get(Employee, selected_employee_id)
        if selected_employee_id
        else None
    )
    if selected_employee and not selected_item and not summary_id:
        employee_summary = AttendanceMonthlySummary.query.filter_by(
            employee_id=selected_employee.id,
            year_month=year_month,
        ).first()
        if employee_summary:
            selected_summary = employee_summary
    duplicate_document_id = request.args.get(
        "duplicate_document_id",
        type=int,
    )
    duplicate_document = (
        db.session.get(EmployeeDocument, duplicate_document_id)
        if duplicate_document_id
        else None
    )
    if (
        duplicate_document
        and (
            duplicate_document.employee_id != selected_employee_id
            or duplicate_document.effective_month != year_month
            or duplicate_document.category != "attendance_pdf"
            or duplicate_document.status != "active"
        )
    ):
        duplicate_document = None
    existing_document = None
    if selected_item and not selected_item.summary_id and selected_employee:
        current = AttendanceMonthlySummary.query.filter_by(employee_id=selected_employee.id, year_month=year_month).first()
        existing_document = current.document if current and current.status == "received" else None
    previous_item = None
    next_item = None
    if selected_batch and selected_item:
        items = list(selected_batch.items)
        index = items.index(selected_item)
        previous_item = items[index - 1] if index > 0 else None
        next_item = items[index + 1] if index + 1 < len(items) else None
    if selected_employee:
        segment_rows, segment_prefill_sources = attendance_segment_rows(
            selected_employee,
            selected_summary,
            year_month,
        )
    else:
        segment_rows, segment_prefill_sources = {}, {}
    segment_special_days = defaultdict(list)
    if selected_summary:
        for special_day in selected_summary.special_days:
            if special_day.status == "active" and special_day.segment_id:
                segment_special_days[special_day.segment_id].append(
                    {
                        "work_date": special_day.work_date,
                        "session": special_day.session or (
                            "full_day"
                            if special_day.days == parse_decimal("1")
                            else "am"
                        ),
                        "days": special_day.days,
                    }
                )
    previous_summary = (
        AttendanceMonthlySummary.query.filter_by(
            employee_id=selected_employee.id,
            year_month=previous_month(year_month),
        ).first()
        if selected_employee
        else None
    )
    # Historical entry follows employment in the selected month.
    employee_choices = employed
    attendance_employee_options = []
    for employee in employee_choices:
        option_assignment = current_assignment_on(employee, month_end)
        option_payroll_group = (
            option_assignment.payroll_group
            if option_assignment
            else employee.payroll_group
        )
        search_terms = {
            employee.employee_no or "",
            employee.chinese_name or "",
            employee.english_name or "",
            *chinese_search_variants(employee.chinese_name or ""),
        }
        attendance_employee_options.append(
            {
                "employee": employee,
                "payroll_group": option_payroll_group,
                "workweek_days": str(
                    assignment_workweek_days(option_assignment)
                ),
                "monthly_pay_method": (
                    salary.monthly_pay_method
                    if (
                        (salary := current_salary_on(employee, month_end))
                        and salary.salary_basis == "monthly"
                    )
                    else "full_month"
                ),
                "search_text": " ".join(
                    term for term in sorted(search_terms) if term
                ),
            }
        )
    period_bounds = attendance_period_bounds(year_month)
    selected_assignment = (
        current_assignment_on(selected_employee, month_end)
        if selected_employee
        else None
    )
    selected_previous_assignment = (
        current_assignment_on(
            selected_employee,
            period_bounds["previous_21_end"][1],
        )
        if selected_employee
        else None
    )
    period_default_projects = {
        kind: (
            assignment.project
            if (
                assignment := current_assignment_on(
                    selected_employee,
                    bounds[1],
                )
            )
            else None
        )
        for kind, bounds in period_bounds.items()
    } if selected_employee else {}
    selected_workweek_days = str(
        assignment_workweek_days(selected_assignment)
    )
    current_sundays = []
    calendar_day = month_start
    while calendar_day <= month_end:
        if calendar_day.weekday() == 6:
            current_sundays.append(calendar_day)
        calendar_day += timedelta(days=1)
    current_statutory_holidays = (
        employee_payroll_holidays(
            selected_employee, month_start, month_end
        )
        if selected_employee
        else {}
    )
    special_date_start = period_bounds["previous_21_end"][0]
    selectable_statutory_holidays = (
        employee_payroll_holidays(
            selected_employee, special_date_start, month_end
        )
        if selected_employee
        else {}
    )
    linked_absences = linked_absences_for_attendance(selected_employee, year_month)
    from hkr_hr.leave.api import absence_data_issues, absences_changed_since_attendance
    absence_issues = absence_data_issues(selected_employee, special_date_start, month_end) if selected_employee else []
    absence_recheck = bool(selected_employee and absences_changed_since_attendance(
        selected_employee, selected_summary, special_date_start, month_end))
    linked_absence_counts = [
        (kind, sum(1 for item in linked_absences if item["kind"] == kind))
        for kind in ("annual", "sick", "unpaid", "work_injury")
    ]
    linked_absence_counts = [
        (kind, count) for kind, count in linked_absence_counts if count
    ]
    return render_template(
        "attendance/index.html",
        corrections=history_for(selected_employee.id, year_month) if selected_employee else [],
        rate_windows_by_period={kind: rate_windows(selected_employee, *bounds) for kind, bounds in period_bounds.items()} if selected_employee else {},
        year_month=year_month,
        view=view,
        detail_status=detail_status,
        search=search,
        policy_sort=policy_sort,
        policy_direction=policy_direction,
        payroll_group_filter=payroll_group_filter,
        originating_payroll_url=originating_payroll(request.args, year_month),
        position_id=position_id,
        policy_rows=policy_rows,
        expected=expected,
        received=received,
        not_required=not_required,
        missing=missing,
        attendance_roster_projects=attendance_roster_projects,
        recent_batches=recent_batches,
        resume_batch=resume_batch,
        other_pending_batches=other_pending_batches,
        selected_batch=selected_batch,
        selected_item=selected_item,
        selected_summary=selected_summary,
        summary_revision=(
            attendance_summary_revision(selected_summary)
            if selected_summary
            else ""
        ),
        edit_summary_mode=bool(selected_summary and not selected_item),
        identity_correction_mode=identity_correction_mode,
        selected_employee_id=selected_employee_id,
        selected_employee=selected_employee,
        selected_assignment=selected_assignment,
        selected_previous_assignment=selected_previous_assignment,
        period_default_projects=period_default_projects,
        selected_workweek_days=selected_workweek_days,
        selected_holiday_calendar_kind=(
            holiday_calendar_kind_for_payroll_group(
                selected_assignment.payroll_group
                if selected_assignment
                else selected_employee.payroll_group
            )
            if selected_employee
            else "statutory"
        ),
        selected_salary=(
            current_salary_on(selected_employee, month_end)
            if selected_employee
            else None
        ),
        segment_rows=segment_rows,
        segment_prefill_sources=segment_prefill_sources,
        segment_special_days=segment_special_days,
        linked_absences=linked_absences,
        absence_issues=absence_issues,
        absence_recheck=absence_recheck,
        linked_absence_counts=linked_absence_counts,
        previous_summary=previous_summary,
        existing_document=existing_document,
        duplicate_document=duplicate_document,
        previous_item=previous_item,
        next_item=next_item,
        employees=employee_choices,
        attendance_employee_options=attendance_employee_options,
        projects=WorkProject.query.filter_by(active=True).order_by(
            WorkProject.name
        ).all(),
        position_options=reference_options("position"),
        payroll_groups=PAYROLL_GROUPS,
        period_bounds=period_bounds,
        current_sundays=current_sundays,
        current_statutory_holidays=current_statutory_holidays,
        selectable_statutory_holiday_dates=[
            item.isoformat() for item in selectable_statutory_holidays
        ],
    )


@attendance_bp.route("/attendance/policies/batch", methods=["POST"])
@login_required
def update_attendance_policies():
    year_month = request.form.get("effective_from_month", "").strip()
    action = request.form.get("action")
    employee_ids = sorted(set(request.form.getlist("employee_ids")))
    try:
        datetime.strptime(str(year_month), "%Y-%m")
    except (TypeError, ValueError):
        flash("請選擇有效的生效月份。", "error")
        return redirect(
            url_for("attendance.attendance_home", view="policies")
        )
    if action not in {"exempt", "require"} or not employee_ids:
        flash("請先選擇員工及操作。", "error")
        return redirect(
            url_for(
                "attendance.attendance_home",
                month=year_month,
                view="policies",
            )
        )
    requires_attendance = action == "require"
    changed = 0
    for employee_id in employee_ids:
        if not str(employee_id).isdigit():
            continue
        employee = db.session.get(Employee, int(employee_id))
        if not employee:
            continue
        before_policy = policy_on(employee.id, year_month)
        before = {
            "requires_attendance": (
                before_policy.requires_attendance if before_policy else True
            ),
            "effective_from_month": (
                before_policy.effective_from_month if before_policy else None
            ),
        }
        policy = EmployeeAttendancePolicy.query.filter_by(
            employee_id=employee.id,
            effective_from_month=year_month,
        ).first()
        if not policy:
            policy = EmployeeAttendancePolicy(
                employee=employee,
                effective_from_month=year_month,
                created_by=current_user.id,
            )
            db.session.add(policy)
        policy.requires_attendance = requires_attendance
        policy.remarks = request.form.get("remarks", "").strip() or None
        db.session.flush()
        write_audit(
            (
                "attendance_policy_required"
                if requires_attendance
                else "attendance_policy_exempted"
            ),
            "EmployeeAttendancePolicy",
            policy.id,
            employee_id=employee.id,
            detail=(
                f"自 {year_month} 起"
                + ("需要考勤表" if requires_attendance else "永久無需考勤表")
            ),
            before=before,
            after={
                "requires_attendance": requires_attendance,
                "effective_from_month": year_month,
            },
        )
        changed += 1
    db.session.commit()
    flash(
        f"已更新 {changed} 名員工；設定由 {year_month} 起生效。",
        "success",
    )
    return redirect(
        url_for(
            "attendance.attendance_home",
            month=year_month,
            view="policies",
        )
    )


@attendance_bp.route(
    "/attendance/monthly-exemptions/batch",
    methods=["POST"],
)
@login_required
def update_monthly_exemptions():
    year_month = request.form.get("year_month", "").strip()
    action = request.form.get("action")
    employee_ids = sorted(set(request.form.getlist("employee_ids")))
    try:
        datetime.strptime(str(year_month), "%Y-%m")
    except (TypeError, ValueError):
        flash("請選擇有效月份。", "error")
        return redirect(
            url_for(
                "attendance.attendance_home",
                view="monthly_exemptions",
            )
        )
    if action not in {"exempt", "require"} or not employee_ids:
        flash("請先選擇員工和操作。", "error")
        return redirect(
            url_for(
                "attendance.attendance_home",
                month=year_month,
                view="monthly_exemptions",
            )
        )
    updated = 0
    skipped = 0
    requires_attendance = action == "require"
    for employee_id in employee_ids:
        if not str(employee_id).isdigit():
            continue
        employee = db.session.get(Employee, int(employee_id))
        if not employee:
            continue
        if set_monthly_attendance_requirement(
            employee,
            year_month,
            requires_attendance,
        ):
            updated += 1
        else:
            skipped += 1
    db.session.commit()
    if updated:
        flash(
            (
                f"已把 {updated} 名員工恢復為本月需要考勤。"
                if requires_attendance
                else f"已把 {updated} 名員工設為本月免交考勤。"
            ),
            "success",
        )
    if skipped:
        flash(f"另有 {skipped} 名員工已有已收考勤，沒有更改。", "info")
    return redirect(
        url_for(
            "attendance.attendance_home",
            month=year_month,
            view="monthly_exemptions",
        )
    )


@attendance_bp.route("/attendance/batches", methods=["POST"])
@login_required
def create_batch():
    # One default month for this upload; individual PDFs remain editable.
    year_month = request.form.get("year_month", "").strip() or current_month()
    try:
        datetime.strptime(year_month, "%Y-%m")
    except (TypeError, ValueError):
        year_month = current_month()
    uploads = [
        item
        for item in request.files.getlist("files")
        if item and item.filename
    ]
    if not uploads:
        flash("請選擇 PDF。", "error")
        return redirect(
            url_for(
                "attendance.attendance_home",
                month=year_month,
                view="collection",
            )
        )
    try:
        for upload in uploads:
            validate_uploaded_file(upload, allowed_extensions={".pdf"})
    except UploadValidationError as exc:
        flash(str(exc), "error")
        return redirect(
            url_for(
                "attendance.attendance_home",
                month=year_month,
                view="collection",
            )
        )
    batch_id = request.form.get("batch_id", type=int)
    batch = db.get_or_404(AttendanceBatch, batch_id) if batch_id else AttendanceBatch(
        batch_no=batch_no(), year_month=year_month, created_by=current_user.id, status="open")
    db.session.add(batch)
    db.session.flush()
    root = Path(current_app.config["ATTENDANCE_BATCH_ROOT"]) / batch.batch_no
    root.mkdir(parents=True, exist_ok=True)
    for index, upload in enumerate(uploads, start=len(batch.items) + 1):
        target = root / f"{index:03d}_{Path(upload.filename).name}"
        upload.save(target)
        db.session.add(
            AttendanceBatchItem(
                batch=batch,
                original_filename=upload.filename,
                stored_path=str(target),
                mime_type="application/pdf",
                file_size=target.stat().st_size,
                content_sha256=file_sha256(target),
                year_month=year_month,
                status="pending",
            )
        )
    db.session.commit()
    first = batch.items[0] if batch.items else None
    if request.headers.get("X-HKR-Upload-Queue") == "1":
        return jsonify(batch_id=batch.id, redirect=url_for("attendance.attendance_home", month=year_month, view="collection", batch_id=batch.id, item_id=first.id if first else None))
    if not first:
        shutil.rmtree(root, ignore_errors=True)
        db.session.delete(batch)
        db.session.commit()
        flash("批次沒有可用的 PDF。", "error")
        return redirect(
            url_for(
                "attendance.attendance_home",
                month=year_month,
                view="collection",
            )
        )
    flash("考勤批次已建立。", "success")
    return redirect(
        url_for(
            "attendance.attendance_home",
            month=year_month,
            view="collection",
            batch_id=batch.id,
            item_id=first.id,
        )
    )


@attendance_bp.route("/attendance/items/<int:item_id>/open")
@login_required
def open_item(item_id):
    item = db.get_or_404(AttendanceBatchItem, item_id)
    path = Path(item.stored_path)
    if not path.exists():
        abort(404)
    if request.args.get('raw') != '1' and request.args.get('download') != '1':
        return render_template('documents/pdf.html', title=item.original_filename,
            source_url=url_for('attendance.open_item', item_id=item.id, raw=1),
            download_url=url_for('attendance.open_item', item_id=item.id, download=1))
    return send_file(
        path,
        mimetype=item.mime_type or "application/pdf",
        as_attachment=request.args.get("download") == "1",
        download_name=item.original_filename,
    )


def parsed_special_dates(value):
    rows = []
    for token in str(value or "").replace("，", ",").replace("\n", ",").split(","):
        parsed = parse_date(token.strip())
        if parsed and parsed not in rows:
            rows.append(parsed)
    return rows


def parsed_special_day_entries_payload(value, employee=None, holiday_dates=None):
    """Return dated non-normal-work entries with schedule-aware day units."""
    try:
        values = json.loads(value or "[]")
    except (TypeError, ValueError):
        values = []
    entries = []
    seen = set()
    for item in values if isinstance(values, list) else []:
        if not isinstance(item, dict):
            continue
        work_date = parse_date(str(item.get("date") or "").strip())
        if not work_date or work_date in seen:
            continue
        units = (
            special_work_day_units(employee, work_date, holiday_dates)
            if employee
            else parse_decimal("1")
        )
        entries.append(
            {
                "work_date": work_date,
                "session": "pm" if units == parse_decimal("0.5") else "full_day",
                "days": units or parse_decimal("0"),
                "valid": units is not None,
            }
        )
        seen.add(work_date)
    return entries


def validate_sunday_holiday_entries(year_month):
    month_start, month_end = parse_year_month(year_month)
    previous_start, previous_end = parse_year_month(previous_month(year_month))
    bounds = {
        "current_1_20": (month_start, min(month_end, month_start.replace(day=20))),
        "previous_21_end": (previous_start.replace(day=21), previous_end),
    }
    used_dates = set()
    employee = db.session.get(Employee, request.form.get("employee_id", type=int))
    employee_assignment = (
        current_assignment_on(employee, month_end) if employee else None
    )
    employee_group = (
        employee_assignment.payroll_group
        if employee_assignment
        else (employee.payroll_group if employee else "site_daily")
    )
    holiday_term = "公眾假期" if employee_group == "management" else "法定假日"
    holiday_dates = (
        employee_payroll_holidays(employee, previous_start, month_end)
        if employee
        else {}
    )
    for prefix, (period_start, period_end) in bounds.items():
        day_values = request.form.getlist(f"{prefix}_holiday_days")
        payloads = request.form.getlist(f"{prefix}_special_work_entries")
        if not payloads:
            continue  # Backward-compatible V0.2.6 text-list submission.
        for index, payload in enumerate(payloads):
            requested_days = parse_decimal(
                day_values[index] if index < len(day_values) else "0",
                parse_decimal("0"),
            )
            entries = parsed_special_day_entries_payload(
                payload, employee, holiday_dates
            )
            selected_days = sum(
                (entry["days"] for entry in entries),
                parse_decimal("0"),
            )
            if requested_days < 0 or requested_days % parse_decimal("0.5"):
                return "非正常工作日出勤日數必須以 0.5 日為單位。"
            if any(not entry["valid"] for entry in entries):
                if employee and any(
                    (
                        assignment := current_assignment_on(
                            employee, entry["work_date"]
                        )
                    )
                    and assignment.payroll_group == "site_daily"
                    for entry in entries
                ):
                    return (
                        "日工的星期日工作應計入一般實際出勤日數；"
                        "本欄只可選擇法定假日實際工作日期。"
                    )
                return f"所選日期並非該員工工作制外日期或{holiday_term}。"
            if requested_days != selected_days:
                return f"工作制外／{holiday_term}的日期數必須與出勤日數一致。"
            for entry in entries:
                work_date = entry["work_date"]
                if work_date < period_start or work_date > period_end:
                    return f"工作制外／{holiday_term}日期必須屬於所填寫的考勤期間。"
                if work_date in used_dates:
                    return f"同一工作制外／{holiday_term}日期不可重複填寫。"
                used_dates.add(work_date)
    return None


def validate_attendance_segment_totals(year_month):
    """Reject impossible or malformed four-period attendance totals."""
    bounds = attendance_period_bounds(year_month)
    for prefix, (period_start, period_end) in bounds.items():
        span_days = (period_end - period_start).days + 1
        working_values = request.form.getlist(f"{prefix}_working_days")
        holiday_values = request.form.getlist(f"{prefix}_holiday_days")
        ot_values = request.form.getlist(f"{prefix}_ot_hours")
        large_values = request.form.getlist(f"{prefix}_large_ecall_count")
        ecall_values = request.form.getlist(f"{prefix}_ecall_count")
        row_count = max(
            len(request.form.getlist(f"{prefix}_project_id")),
            len(working_values),
            len(holiday_values),
            1,
        )
        working_total = parse_decimal("0")
        holiday_total = parse_decimal("0")
        for index in range(row_count):
            working = parse_decimal(
                working_values[index] if index < len(working_values) else "0",
                parse_decimal("0"),
            )
            holiday = parse_decimal(
                holiday_values[index] if index < len(holiday_values) else "0",
                parse_decimal("0"),
            )
            if working < 0 or working % parse_decimal("0.5"):
                return "一般工作日出勤日數必須為非負數，並以 0.5 日為單位。"
            if holiday < 0 or holiday % parse_decimal("0.5"):
                return "星期日／法定節假日出勤日數必須為非負數，並以 0.5 日為單位。"
            working_total += working
            holiday_total += holiday
        if working_total + holiday_total > span_days:
            return (
                f"{period_start:%Y-%m-%d} 至 {period_end:%Y-%m-%d} "
                f"的出勤合計不可超過 {span_days} 日。"
            )
        for values, label, integer_only in (
            (ot_values, "OT 時數", False),
            (large_values, "大 E-CALL 次數", True),
            (ecall_values, "普通 E-CALL 次數", True),
        ):
            for value in values:
                parsed = parse_decimal(value, parse_decimal("0"))
                if parsed < 0 or (integer_only and parsed != int(parsed)):
                    suffix = "非負整數" if integer_only else "非負數"
                    return f"{label}必須為{suffix}。"
    employee = db.session.get(Employee, request.form.get("employee_id", type=int))
    if employee:
        for prefix, (start, end) in bounds.items():
            payloads = request.form.getlist(f"{prefix}_rate_allocations")
            projects = request.form.getlist(f"{prefix}_project_id")
            for index in range(len(projects)):
                values = {}
                for field in FIELDS:
                    form_name = "holiday_days" if field == "sunday_holiday_days" else field
                    inputs = request.form.getlist(f"{prefix}_{form_name}")
                    values[field] = parse_decimal(inputs[index] if index < len(inputs) else "0", parse_decimal("0"))
                try:
                    values["rate_allocations"] = json.loads(payloads[index]) if index < len(payloads) else []
                except (ValueError, TypeError):
                    return "請填寫按薪酬生效日期分段的考勤。"
                issue = allocation_issue(employee, SimpleNamespace(**values), start, end, recording_attendance=True)
                if issue:
                    return issue
    return None


def replace_summary_segments(summary, replace=True):
    """Preserve identical credits; reconcile genuine removals AFTER replacements exist."""
    if replace:
        update_allocation_from_form(summary, request.form)
    reusable = {}
    for special_day in list(summary.special_days):
        credit = special_day.comp_leave_credit
        if credit:
            key = (credit.employee_id, special_day.work_date, special_day.session, special_day.days)
            if credit.status == "active":
                reusable[key] = credit
            if replace:
                credit.source_special_day = None
        if replace:
            db.session.delete(special_day)
    if replace:
        for segment in list(summary.segments):
            db.session.delete(segment)
    db.session.flush()
    summary._reusable_comp_credits = reusable
    try:
        if replace:
            for prefix in ("current_1_20", "current_21_end_forecast", "previous_21_end", "previous_21_end_forecast"):
                add_segments(summary, prefix)
        affected = {}
        for credit in reusable.values():
            credit.status = "voided"
            for allocation in credit.allocations:
                record = allocation.leave_record
                if record and record.status == "active":
                    affected[record.id] = record
        db.session.flush()
        records = sorted(affected.values(), key=lambda row: (row.leave_date, row.id))
        for record in records:
            clear_leave_allocations(record)
        db.session.flush()
        for record in records:
            db.session.expire(record.employee, ["comp_leave_credits"])
            from hkr_hr.leave.api import annual_leave_buckets, comp_leave_credit_remaining
            zero = parse_decimal("0")
            available = sum((comp_leave_credit_remaining(credit)
                             for credit in record.employee.comp_leave_credits
                             if credit.status == "active" and credit.source_date <= record.leave_date), zero)
            available += sum((max(zero, bucket["remaining"]) for bucket in annual_leave_buckets(
                record.employee, as_of=record.leave_date, include_expired=False)), zero)
            if available < record.days:
                raise ValueError("Changed compensation credit would overdraw annual leave.")
            allocate_annual_leave_with_comp(record, as_of=record.leave_date)
    finally:
        del summary._reusable_comp_credits


def add_special_days(
    summary,
    segment,
    prefix,
    project_id,
    entries,
):
    handling = summary.special_day_handling
    for entry in entries:
        work_date = entry["work_date"]
        session = entry["session"]
        days = entry["days"]
        special_day = AttendanceSpecialDay(
            summary=summary,
            segment=segment,
            period_kind=prefix,
            project_id=project_id,
            work_date=work_date,
            day_kind="sunday_statutory_holiday",
            session=session,
            handling=handling,
            days=days,
            status="active",
        )
        db.session.add(special_day)
        db.session.flush()
        if handling == "comp_leave":
            key = (summary.employee_id, work_date, session, days)
            existing = getattr(summary, "_reusable_comp_credits", {}).pop(key, None)
            if existing:
                existing.source_special_day = special_day
                continue
            db.session.add(
                EmployeeCompLeaveCredit(
                    employee_id=summary.employee_id,
                    source_special_day=special_day,
                    source_date=work_date,
                    source_kind="sunday_statutory_holiday",
                    days=days,
                    status="active",
                    remarks="由考勤錄入自動產生；暫不設到期日",
                )
            )


def add_segments(summary, prefix):
    _, month_end = parse_year_month(summary.year_month)
    salary = current_salary_on(summary.employee, month_end)
    attendance_prorated = bool(
        salary
        and salary.salary_basis == "monthly"
        and salary.monthly_pay_method == "attendance_days"
    )
    projects = request.form.getlist(f"{prefix}_project_id")
    working_days = request.form.getlist(f"{prefix}_working_days")
    ot_hours = request.form.getlist(f"{prefix}_ot_hours")
    holiday_days = request.form.getlist(f"{prefix}_holiday_days")
    large_ecall_counts = request.form.getlist(
        f"{prefix}_large_ecall_count"
    )
    ecall_counts = request.form.getlist(f"{prefix}_ecall_count")
    other_allowance_amounts = request.form.getlist(
        f"{prefix}_other_allowance_amount"
    )
    special_entry_values = request.form.getlist(
        f"{prefix}_special_work_entries"
    )
    # Keep the V0.2.6 text-list payload readable while existing saved forms or
    # tests transition to the date picker. New UI submissions use the fields
    # above and no longer distinguish Sunday from statutory holiday.
    legacy_rest_date_values = request.form.getlist(
        f"{prefix}_rest_day_dates"
    )
    legacy_statutory_date_values = request.form.getlist(
        f"{prefix}_statutory_holiday_dates"
    )
    for index, project_value in enumerate(projects):
        project_id = int(project_value) if str(project_value).isdigit() else None
        days = parse_decimal(
            working_days[index] if index < len(working_days) else "",
            parse_decimal("0"),
        )
        ot = parse_decimal(
            ot_hours[index] if index < len(ot_hours) else "",
            parse_decimal("0"),
        )
        holiday = parse_decimal(
            holiday_days[index] if index < len(holiday_days) else "",
            parse_decimal("0"),
        )
        entries = parsed_special_day_entries_payload(
            special_entry_values[index]
            if index < len(special_entry_values)
            else "",
            summary.employee,
        )
        if not entries:
            legacy_dates = []
            for values in (legacy_rest_date_values, legacy_statutory_date_values):
                raw = values[index] if index < len(values) else ""
                for work_date in parsed_special_dates(raw):
                    if work_date not in legacy_dates:
                        legacy_dates.append(work_date)
            entries = [
                {
                    "work_date": work_date,
                    "session": "full_day",
                    "days": parse_decimal("1"),
                }
                for work_date in legacy_dates
            ]
        dated_holiday_days = sum(
            (entry["days"] for entry in entries),
            parse_decimal("0"),
        )
        if entries:
            holiday = dated_holiday_days
        if attendance_prorated:
            holiday = parse_decimal("0")
            entries = []
        large_ecall = max(
            0,
            int(
                parse_decimal(
                    (
                        large_ecall_counts[index]
                        if index < len(large_ecall_counts)
                        else ""
                    ),
                    parse_decimal("0"),
                )
            ),
        )
        ecall = max(
            0,
            int(
                parse_decimal(
                    ecall_counts[index] if index < len(ecall_counts) else "",
                    parse_decimal("0"),
                )
            ),
        )
        other_allowance = max(
            parse_decimal(
                other_allowance_amounts[index]
                if index < len(other_allowance_amounts)
                else "",
                parse_decimal("0"),
            ),
            parse_decimal("0"),
        )
        if project_id or days or ot or holiday or large_ecall or ecall or other_allowance:
            segment = AttendanceSegment(
                    summary=summary,
                    period_kind=prefix,
                    project_id=project_id,
                    rate_allocations=(json.loads(request.form.getlist(f"{prefix}_rate_allocations")[index]) if index < len(request.form.getlist(f"{prefix}_rate_allocations")) else None),
                    working_days=days,
                    ot_hours=ot,
                    sunday_holiday_days=holiday,
                    large_ecall_count=large_ecall,
                    ecall_count=ecall,
                    other_allowance_amount=other_allowance,
                )
            db.session.add(segment)
            db.session.flush()
            add_special_days(
                summary,
                segment,
                prefix,
                project_id,
                entries,
            )


@attendance_bp.route("/attendance/items/<int:item_id>/save", methods=["POST"])
@login_required
def save_item(item_id):
    item = (
        AttendanceBatchItem.query.filter_by(id=item_id)
        .with_for_update()
        .populate_existing()
        .first_or_404()
    )
    if item.status == "replaced":
        db.session.rollback()
        flash("hr.attendance_item_already_saved", "error")
        return redirect(url_for("attendance.attendance_home", item_id=item.id))
    if item.summary_id:
        if request.form.get("expected_item_status") == "pending":
            db.session.rollback()
            flash("hr.attendance_item_already_saved", "error")
            return redirect(
                url_for(
                    "attendance.attendance_home",
                    month=item.effective_year_month or current_month(),
                    view="collection",
                    batch_id=item.batch_id,
                    item_id=item.id,
                )
            )
        # Keep old bookmarks/forms safe while the UI now posts saved items to
        # the explicit correction route.
        return correct_summary(item.summary_id)
    year_month = (
        request.form.get("year_month", "").strip()
        or item.effective_year_month
        or current_month()
    )
    try:
        datetime.strptime(year_month, "%Y-%m")
    except (TypeError, ValueError):
        flash("請選擇有效的考勤月份。", "error")
        return redirect(
            url_for(
                "attendance.attendance_home",
                month=item.effective_year_month or current_month(),
                view="collection",
                batch_id=item.batch_id,
                item_id=item.id,
            )
        )
    employee = (
        Employee.query.filter_by(id=request.form.get("employee_id", type=int))
        .with_for_update()
        .populate_existing()
        .first()
    )
    if not employee:
        flash("必須選擇員工。", "error")
        return redirect(
            url_for(
                "attendance.attendance_home",
                month=year_month,
                batch_id=item.batch_id,
                item_id=item.id,
            )
        )

    attendance_error = (
        validate_attendance_segment_totals(year_month)
        or validate_sunday_holiday_entries(year_month)
    )
    if attendance_error:
        flash(attendance_error, "error")
        return redirect(
            url_for(
                "attendance.attendance_home",
                month=year_month,
                view="collection",
                batch_id=item.batch_id,
                item_id=item.id,
                employee_id=employee.id,
            )
        )

    item_sha256 = item.content_sha256 or file_sha256(item.stored_path)
    item.content_sha256 = item_sha256
    duplicate_document = find_duplicate_employee_document(
        employee.id,
        "attendance_pdf",
        item_sha256,
        effective_month=year_month,
    )
    summary = (
        AttendanceMonthlySummary.query.filter_by(
            employee_id=employee.id,
            year_month=year_month,
        )
        .with_for_update()
        .populate_existing()
        .first()
    )
    original = summary.document if summary and summary.status == "received" else None
    confirmed_id = request.form.get("replace_document_id", type=int)
    same_file = original and duplicate_document and original.id == duplicate_document.id
    if original and original.id != confirmed_id and not (same_file and parse_bool(request.form.get("confirm_duplicate"))):
        if request.headers.get("X-HKR-Profile-Editor") == "1":
            return jsonify(replace_document_id=original.id, filename=original.original_filename,
                           confirm_duplicate=bool(same_file))
        return redirect(url_for("attendance.attendance_home", month=year_month, item_id=item.id,
                                employee_id=employee.id, duplicate_document_id=duplicate_document.id if same_file else None))
    if not summary:
        summary = AttendanceMonthlySummary(
            employee=employee,
            year_month=year_month,
        )
        db.session.add(summary)
        db.session.flush()
    old_document = summary.document
    if old_document:
        for previous in AttendanceBatchItem.query.filter_by(summary_id=summary.id, status="saved"):
            previous.archived_summary = summary_snapshot(summary)
            previous.status = "replaced"
    path = copy_file_to_employee(
        employee,
        item.stored_path,
        item.original_filename,
        "attendance_pdf",
    )
    document = EmployeeDocument(
        employee=employee,
        category="attendance_pdf",
        title=f"{year_month} 考勤表",
        original_filename=item.original_filename,
        stored_path=str(path),
        mime_type=item.mime_type,
        file_ext=".pdf",
        file_size=path.stat().st_size,
        content_sha256=item_sha256,
        status="active",
        effective_month=year_month,
        uploaded_by=current_user.id,
    )
    db.session.add(document)
    db.session.flush()
    replaced_documents = [
        row
        for row in (old_document, duplicate_document)
        if row and row.id != document.id
    ]
    for old in {row.id: row for row in replaced_documents}.values():
        old.status = "replaced"
        old.replaced_by_document_id = document.id
        old.replacement_reason = "更新考勤表"
    summary.document = document
    summary.status = "received"
    summary.special_day_handling = (
        "comp_leave"
        if request.form.get("special_day_handling") == "comp_leave"
        else "pay"
    )
    summary.no_attendance_reason = None
    set_summary_confirmed(summary)
    summary.remarks = request.form.get("remarks", "").strip() or None
    try:
        replace_summary_segments(summary)
    except ProjectAllocationError as exc:
        employee_id, month = summary.employee_id, summary.year_month
        db.session.rollback()
        flash(str(exc), "error")
        return redirect(url_for("attendance.attendance_home", month=month, employee_id=employee_id,
                                view="collection", batch_id=item.batch_id, item_id=item.id))
    except ValueError:
        employee_id, month = summary.employee_id, summary.year_month
        db.session.rollback()
        flash("leave.comp_reconcile_insufficient", "error")
        return redirect(url_for("attendance.attendance_home", month=month, employee_id=employee_id))

    item.status = "saved"
    item.employee = employee
    item.year_month = year_month
    item.summary_id = summary.id
    write_audit(
        "attendance_saved",
        "AttendanceMonthlySummary",
        summary.id,
        employee_id=employee.id,
        detail=f"{year_month} 考勤已錄入",
        after=summary_snapshot(summary),
    )
    db.session.commit()
    next_item = next(
        (row for row in item.batch.items if row.status == "pending" and row.id > item.id),
        next((row for row in item.batch.items if row.status == "pending"), None),
    )
    flash("考勤已保存。", "success")
    target = {
        "month": next_item.effective_year_month if next_item else year_month,
        "view": "collection",
        "batch_id": item.batch_id,
    }
    if next_item:
        target["item_id"] = next_item.id
    return redirect(
        url_for("attendance.attendance_home", **target)
    )


@attendance_bp.route(
    "/attendance/summaries/<int:summary_id>/correct",
    methods=["POST"],
)
@login_required
def correct_summary(summary_id):
    summary = (
        AttendanceMonthlySummary.query.filter_by(id=summary_id)
        .with_for_update()
        .populate_existing()
        .first_or_404()
    )
    if "editing_document_id" in request.form and (request.form.get("editing_document_id", type=int) or None) != summary.document_id:
        db.session.rollback()
        flash("原考勤表已被替換，請核對現行版本。", "error")
        return redirect(url_for("attendance.attendance_home", summary_id=summary.id))
    if "summary_revision" in request.form:
        submitted_rev = request.form.get("summary_revision", "")
        if not hmac.compare_digest(
            submitted_rev.encode(),
            attendance_summary_revision(summary).encode(),
        ):
            db.session.rollback()
            flash("hr.attendance_conflict", "error")
            return redirect(url_for("attendance.attendance_home", summary_id=summary.id))
    source_year_month = summary.year_month
    review_url = url_for(
        "attendance.attendance_home",
        month=source_year_month,
        employee_id=summary.employee_id,
        summary_id=summary.id,
        **{key: request.form[key] for key in ("from_payroll", "pay_group", "pay_entity", "pay_status", "pay_q", "pay_employee")
           if request.form.get(key)},
    )
    target_year_month = request.form.get("year_month", source_year_month).strip()
    try:
        datetime.strptime(target_year_month, "%Y-%m")
    except (TypeError, ValueError):
        flash("請選擇有效的考勤月份。", "error")
        return redirect(review_url)
    employee = db.session.get(
        Employee,
        request.form.get("employee_id", type=int),
    )
    if not employee:
        flash("必須選擇員工。", "error")
        return redirect(review_url)
    attendance_error = (
        validate_attendance_segment_totals(target_year_month)
        or validate_sunday_holiday_entries(target_year_month)
    )
    if attendance_error:
        flash(attendance_error, "error")
        return redirect(review_url)
    duplicate = AttendanceMonthlySummary.query.filter_by(
        employee_id=employee.id,
        year_month=target_year_month,
    ).first()
    if duplicate and duplicate.id != summary.id:
        flash(
            f"該員工在 {target_year_month} 已有考勤，請先核對原有記錄。",
            "error",
        )
        return redirect(review_url)
    before = summary_snapshot(summary)
    old_employee_id = summary.employee_id
    payroll_was_exported = any(
        payroll_snapshot_exists(employee_id, month)
        for employee_id, month in {
            (old_employee_id, source_year_month),
            (employee.id, target_year_month),
        }
    )
    if employee.id != old_employee_id and summary.document:
        old_document = summary.document
        new_path = copy_file_to_employee(
            employee,
            old_document.stored_path,
            old_document.original_filename,
            "attendance_pdf",
        )
        new_document = EmployeeDocument(
            employee=employee,
            category="attendance_pdf",
            title=f"{target_year_month} 考勤表",
            original_filename=old_document.original_filename,
            stored_path=str(new_path),
            mime_type=old_document.mime_type,
            file_ext=old_document.file_ext,
            file_size=new_path.stat().st_size,
            content_sha256=old_document.content_sha256
            or file_sha256(new_path),
            status="active",
            effective_month=target_year_month,
            uploaded_by=current_user.id,
        )
        db.session.add(new_document)
        db.session.flush()
        old_document.status = "replaced"
        old_document.replaced_by_document_id = new_document.id
        old_document.replacement_reason = "更正考勤所屬員工／月份"
        summary.document = new_document
    elif summary.document and target_year_month != source_year_month:
        summary.document.title = f"{target_year_month} 考勤表"
        summary.document.effective_month = target_year_month
    summary.employee = employee
    summary.year_month = target_year_month
    if summary.status != "not_required":
        summary.status = "received"
        summary.no_attendance_reason = None
    summary.special_day_handling = (
        "comp_leave"
        if request.form.get("special_day_handling") == "comp_leave"
        else "pay"
    )
    set_summary_confirmed(summary)
    summary.remarks = request.form.get("remarks", "").strip() or None
    for item in AttendanceBatchItem.query.filter_by(summary_id=summary.id, status="saved"):
        item.employee = employee
        item.year_month = target_year_month
        item.status = "saved"
    try:
        replace_summary_segments(summary)
    except ProjectAllocationError as exc:
        db.session.rollback()
        flash(str(exc), "error")
        return redirect(review_url)
    except ValueError:
        db.session.rollback()
        flash("leave.comp_reconcile_insufficient", "error")
        return redirect(review_url)
    db.session.flush()
    write_audit(
        "attendance_corrected",
        "AttendanceMonthlySummary",
        summary.id,
        employee_id=employee.id,
        detail=(
            f"更正 {source_year_month} 考勤"
            + (
                f"，月份改為 {target_year_month}"
                if source_year_month != target_year_month
                else ""
            )
            + (
                f"，員工由 {old_employee_id} 改為 {employee.id}"
                if old_employee_id != employee.id
                else ""
            )
        ),
        before=before,
        after=summary_snapshot(summary),
    )
    db.session.commit()
    flash("考勤資料已更正。", "success")
    if payroll_was_exported:
        flash(
            "原月份或新月份曾經匯出工資表。考勤更正後，請重新核對及匯出工資表。",
            "warning",
        )
    payroll_url = originating_payroll(request.form, source_year_month)
    if payroll_url:
        return redirect(payroll_url)
    return redirect(
        url_for(
            "attendance.attendance_home",
            month=target_year_month,
            employee_id=employee.id,
            summary_id=summary.id,
        )
    )


@attendance_bp.route(
    "/attendance/summaries/<int:summary_id>/withdraw",
    methods=["POST"],
)
@login_required
def withdraw_summary(summary_id):
    summary = db.get_or_404(AttendanceMonthlySummary, summary_id)
    before = summary_snapshot(summary)
    try:
        replace_summary_segments(summary, replace=False)
    except ValueError:
        employee_id, month = summary.employee_id, summary.year_month
        db.session.rollback()
        flash("leave.comp_reconcile_insufficient", "error")
        return redirect(url_for("attendance.attendance_home", month=month, employee_id=employee_id))
    summary.status = "voided"
    if summary.document and summary.document.status == "active":
        summary.document.status = "voided"
        summary.document.replacement_reason = (
            request.form.get("reason", "").strip() or "撤回錯誤考勤"
        )
    for item in AttendanceBatchItem.query.filter_by(summary_id=summary.id, status="saved"):
        item.status = "voided"
    write_audit(
        "attendance_withdrawn",
        "AttendanceMonthlySummary",
        summary.id,
        employee_id=summary.employee_id,
        detail=request.form.get("reason", "").strip() or "撤回錯誤考勤",
        before=before,
        after={"status": "voided"},
    )
    db.session.commit()
    flash("考勤已撤回，不再參與出糧；原記錄仍保留。", "success")
    return redirect(
        url_for(
            "employees.view_employee",
            employee_id=summary.employee_id,
            tab="attendance",
        )
    )


@attendance_bp.route("/attendance/items/<int:item_id>/skip", methods=["POST"])
@login_required
def skip_item(item_id):
    item = db.get_or_404(AttendanceBatchItem, item_id)
    if item.status != "pending":
        return redirect(url_for("attendance.attendance_home", item_id=item.id))
    item.status = "skipped"
    db.session.commit()
    next_item = next(
        (row for row in item.batch.items if row.status == "pending" and row.id > item.id),
        next((row for row in item.batch.items if row.status == "pending"), None),
    )
    target = {
        "month": next_item.effective_year_month if next_item else item.effective_year_month,
        "view": "collection",
        "batch_id": item.batch_id,
    }
    if next_item:
        target["item_id"] = next_item.id
    return redirect(
        url_for("attendance.attendance_home", **target)
    )


@attendance_bp.route("/attendance/batches/<int:batch_id>/delete", methods=["POST"])
@login_required
def delete_batch(batch_id):
    batch = db.get_or_404(AttendanceBatch, batch_id)
    folder = Path(current_app.config["ATTENDANCE_BATCH_ROOT"]) / batch.batch_no
    db.session.delete(batch)
    db.session.commit()
    shutil.rmtree(folder, ignore_errors=True)
    flash("批次已刪除；已歸檔到員工的考勤 PDF 不受影響。", "success")
    return redirect(
        url_for(
            "attendance.attendance_home",
            view="collection",
        )
    )


@attendance_bp.route("/attendance/not-required", methods=["POST"])
@login_required
def mark_not_required():
    employee = db.session.get(Employee, request.form.get("employee_id", type=int))
    year_month = request.form.get("year_month")
    reason = request.form.get("reason", "").strip() or "HR 標記本月無需考勤表"
    if not employee or not year_month:
        abort(400)
    summary = AttendanceMonthlySummary.query.filter_by(
        employee_id=employee.id,
        year_month=year_month,
    ).first()
    if summary and summary.status == "received":
        flash("本月已有考勤表；如考勤記錄錯誤，請先撤回後再標記無需考勤表。", "error")
        return redirect(
            url_for(
                "attendance.attendance_home",
                month=year_month,
                view="details",
                status="received",
            )
        )
    if not summary:
        summary = AttendanceMonthlySummary(
            employee=employee,
            year_month=year_month,
            status="required",
        )
        db.session.add(summary)
        db.session.flush()
    before = summary_snapshot(summary)
    for segment in list(summary.segments):
        db.session.delete(segment)
    db.session.flush()
    summary.status = "not_required"
    summary.no_attendance_reason = reason
    summary.document = None
    set_summary_confirmed(summary)
    add_default_full_attendance(summary, employee, year_month)
    db.session.flush()
    write_audit(
        "attendance_not_required",
        "AttendanceMonthlySummary",
        employee_id=employee.id,
        detail=f"{year_month}: {reason}",
        before=before,
        after=summary_snapshot(summary),
    )
    db.session.commit()
    flash("已標記本月無需考勤表；工資表會按預設全勤及零 OT／E-CALL 計算。", "success")
    return redirect(
        url_for(
            "attendance.attendance_home",
            month=year_month,
            view="details",
            status="not_required",
        )
    )


@attendance_bp.route("/attendance/required", methods=["POST"])
@login_required
def mark_required():
    employee = db.session.get(Employee, request.form.get("employee_id", type=int))
    year_month = request.form.get("year_month")
    if not employee or not year_month:
        abort(400)
    summary = AttendanceMonthlySummary.query.filter_by(
        employee_id=employee.id,
        year_month=year_month,
    ).first()
    if not summary:
        summary = AttendanceMonthlySummary(
            employee=employee,
            year_month=year_month,
            status="required",
        )
        db.session.add(summary)
        db.session.flush()
    elif summary.status not in {"not_required", "required"}:
        flash("本月已有已收考勤，無需改回需要考勤。", "error")
        return redirect(
            url_for(
                "attendance.attendance_home",
                month=year_month,
                view="details",
                status="received",
            )
        )
    before = summary_snapshot(summary)
    for segment in list(summary.segments):
        db.session.delete(segment)
    summary.status = "required"
    summary.no_attendance_reason = None
    set_summary_confirmed(summary)
    db.session.flush()
    write_audit(
        "attendance_required",
        "AttendanceMonthlySummary",
        summary.id,
        employee_id=employee.id,
        detail=f"{year_month}: 改回需要考勤表",
        before=before,
        after=summary_snapshot(summary),
    )
    db.session.commit()
    flash("已改回需要考勤表；收到 PDF 後可按正常流程導入。", "success")
    return redirect(
        url_for(
            "attendance.attendance_home",
            month=year_month,
            view="details",
            status="missing",
        )
    )


@attendance_bp.route("/attendance/items/<int:item_id>/transfer", methods=["POST"])
@login_required
def transfer_project(item_id):
    item = db.get_or_404(AttendanceBatchItem, item_id)
    employee = db.session.get(Employee, request.form.get("employee_id", type=int))
    effective_from = parse_date(request.form.get("effective_from"))
    project_id = request.form.get("project_id", type=int)
    if not employee or not effective_from or not project_id:
        flash("轉項目必須選擇員工、項目和生效日期。", "error")
    else:
        evidence = request.files.get("evidence")
        evidence_document = None
        if evidence and evidence.filename:
            evidence_path = store_employee_file(
                employee,
                evidence,
                "change_evidence",
            )
            evidence_document = EmployeeDocument(
                employee=employee,
                category="change_evidence",
                title="轉項目憑證",
                original_filename=evidence.filename,
                stored_path=str(evidence_path),
                mime_type=evidence.mimetype,
                file_ext=Path(evidence.filename).suffix.lower(),
                file_size=evidence_path.stat().st_size,
                content_sha256=file_sha256(evidence_path),
                uploaded_by=current_user.id,
            )
            db.session.add(evidence_document)
            db.session.flush()
        current = employee.current_assignment
        assignment = create_assignment(
            employee=employee,
            effective_from=effective_from,
            payroll_group=employee.payroll_group,
            region_id=current.region_id if current else None,
            project_id=project_id,
            department_id=current.department_id if current else None,
            employer_id=current.employer_id if current else None,
            payroll_entity_id=current.payroll_entity_id if current else None,
            social_insurance_entity_id=(
                current.social_insurance_entity_id if current else None
            ),
            labour_dispatch_entity_id=(
                current.labour_dispatch_entity_id if current else None
            ),
            position_ids=[
                position.position_id for position in current.positions
            ]
            if current
            else [],
            evidence_document_id=(
                evidence_document.id if evidence_document else None
            ),
            remarks="由考勤工作台建立的轉項目記錄",
        )
        write_audit(
            "project_transfer",
            "EmployeeAssignment",
            assignment.id,
            employee_id=employee.id,
            detail=f"{effective_from:%Y-%m-%d} 轉項目",
        )
        db.session.commit()
        flash("轉項目已記入正式任職歷史。", "success")
    return redirect(
        url_for(
            "attendance.attendance_home",
            month=item.effective_year_month,
            batch_id=item.batch_id,
            item_id=item.id,
        )
    )
