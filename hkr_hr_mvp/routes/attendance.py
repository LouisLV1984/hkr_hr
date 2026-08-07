import shutil
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from flask_login import current_user, login_required

from models import (
    AttendanceBatch,
    AttendanceBatchItem,
    AttendanceMonthlySummary,
    AttendanceSegment,
    Employee,
    EmployeeDocument,
    WorkProject,
    db,
)
from tools.hr_core import (
    copy_file_to_employee,
    create_assignment,
    current_assignment_on,
    current_month,
    current_salary_on,
    file_sha256,
    find_duplicate_employee_document,
    parse_bool,
    parse_date,
    parse_decimal,
    parse_year_month,
    previous_month,
    store_employee_file,
    write_audit,
)


attendance_bp = Blueprint("attendance", __name__)


def batch_no():
    return f"ATT-{datetime.utcnow():%Y%m%d-%H%M%S-%f}"


def employees_expected_for_month(year_month):
    month_start, month_end = parse_year_month(year_month)
    rows = []
    for employee in Employee.query.order_by(Employee.employee_no).all():
        if any(
            period.start_date <= month_end
            and (period.end_date is None or period.end_date >= month_start)
            for period in employee.employment_periods
        ):
            rows.append(employee)
        elif employee.status == "active" and not employee.employment_periods:
            rows.append(employee)
    not_required = {
        row.employee_id
        for row in AttendanceMonthlySummary.query.filter_by(
            year_month=year_month,
            status="not_required",
        ).all()
    }
    return [employee for employee in rows if employee.id not in not_required]


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
    if selected_batch and not selected_item:
        selected_item = next(
            (item for item in selected_batch.items if item.status == "pending"),
            selected_batch.items[0] if selected_batch.items else None,
        )
    return selected_batch, selected_item


def automatic_forecast_rows(employee, year_month):
    month_start, month_end = parse_year_month(year_month)
    day = month_start.replace(day=21)
    rows = defaultdict(
        lambda: {
            "project_id": None,
            "working_days": 0,
            "sunday_holiday_days": 0,
            "ot_hours": 0,
            "large_ecall_count": 0,
            "ecall_count": 0,
        }
    )
    while day <= month_end:
        assignment = current_assignment_on(employee, day)
        project_id = assignment.project_id if assignment else None
        row = rows[project_id]
        row["project_id"] = project_id
        salary = current_salary_on(employee, day)
        is_daily = (
            salary.salary_basis == "daily"
            if salary
            else employee.payroll_group == "site_daily"
        )
        if day.weekday() == 6:
            if not is_daily:
                row["sunday_holiday_days"] += 1
        else:
            row["working_days"] += 1
        day += timedelta(days=1)
    return [row for row in rows.values() if row["working_days"] or row["sunday_holiday_days"]]


def attendance_segment_rows(employee, summary, year_month):
    rows = {}
    for kind in ("current_1_20", "previous_21_end"):
        existing = attendance_segments(summary, kind)
        rows[kind] = existing or [None]

    current_forecast = attendance_segments(
        summary,
        "current_21_end_forecast",
    )
    rows["current_21_end_forecast"] = (
        current_forecast or automatic_forecast_rows(employee, year_month)
    )

    previous_forecast = attendance_segments(
        summary,
        "previous_21_end_forecast",
    )
    if previous_forecast:
        rows["previous_21_end_forecast"] = previous_forecast
    else:
        prior_summary = AttendanceMonthlySummary.query.filter_by(
            employee_id=employee.id,
            year_month=previous_month(year_month),
        ).first()
        prior_rows = attendance_segments(
            prior_summary,
            "current_21_end_forecast",
        )
        rows["previous_21_end_forecast"] = (
            prior_rows
            or automatic_forecast_rows(
                employee,
                previous_month(year_month),
            )
        )
    return rows


def summary_snapshot(summary):
    return {
        "employee_id": summary.employee_id,
        "year_month": summary.year_month,
        "status": summary.status,
        "document_id": summary.document_id,
        "segments": [
            {
                "period_kind": item.period_kind,
                "project_id": item.project_id,
                "working_days": str(item.working_days),
                "ot_hours": str(item.ot_hours),
                "sunday_holiday_days": str(item.sunday_holiday_days),
                "large_ecall_count": item.large_ecall_count,
                "ecall_count": item.ecall_count,
            }
            for item in summary.segments
        ],
    }


@attendance_bp.route("/attendance")
@login_required
def attendance_home():
    year_month = request.args.get("month") or current_month()
    expected = employees_expected_for_month(year_month)
    received = AttendanceMonthlySummary.query.filter_by(
        year_month=year_month,
        status="received",
    ).all()
    received_ids = {row.employee_id for row in received}
    selected_batch, selected_item = selected_context()
    selected_summary = (
        db.session.get(AttendanceMonthlySummary, selected_item.summary_id)
        if selected_item and selected_item.summary_id
        else None
    )
    summary_id = request.args.get("summary_id", type=int)
    if summary_id:
        candidate = db.session.get(AttendanceMonthlySummary, summary_id)
        if candidate and candidate.year_month == year_month:
            selected_summary = candidate
            selected_batch = None
            selected_item = None
    selected_employee_id = request.args.get("employee_id", type=int)
    if not selected_employee_id and selected_summary:
        selected_employee_id = selected_summary.employee_id
    selected_employee = (
        db.session.get(Employee, selected_employee_id)
        if selected_employee_id
        else None
    )
    if selected_employee:
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
    previous_item = None
    next_item = None
    if selected_batch and selected_item:
        items = list(selected_batch.items)
        index = items.index(selected_item)
        previous_item = items[index - 1] if index > 0 else None
        next_item = items[index + 1] if index + 1 < len(items) else None
    segment_rows = (
        attendance_segment_rows(
            selected_employee,
            selected_summary,
            year_month,
        )
        if selected_employee
        else {}
    )
    previous_summary = (
        AttendanceMonthlySummary.query.filter_by(
            employee_id=selected_employee.id,
            year_month=previous_month(year_month),
        ).first()
        if selected_employee
        else None
    )
    employee_choices = list(expected)
    if (
        selected_employee
        and selected_employee.id not in {item.id for item in employee_choices}
    ):
        employee_choices.append(selected_employee)
        employee_choices.sort(key=lambda item: item.employee_no)
    return render_template(
        "attendance/index.html",
        year_month=year_month,
        expected=expected,
        received=received,
        missing=[item for item in expected if item.id not in received_ids],
        recent_batches=AttendanceBatch.query.order_by(
            AttendanceBatch.created_at.desc()
        ).limit(20).all(),
        selected_batch=selected_batch,
        selected_item=selected_item,
        selected_summary=selected_summary,
        edit_summary_mode=bool(selected_summary and not selected_item),
        selected_employee_id=selected_employee_id,
        selected_employee=selected_employee,
        segment_rows=segment_rows,
        previous_summary=previous_summary,
        duplicate_document=duplicate_document,
        previous_item=previous_item,
        next_item=next_item,
        employees=employee_choices,
        projects=WorkProject.query.filter_by(active=True).order_by(
            WorkProject.name
        ).all(),
    )


@attendance_bp.route("/attendance/batches", methods=["POST"])
@login_required
def create_batch():
    year_month = request.form.get("year_month")
    try:
        datetime.strptime(year_month or "", "%Y-%m")
    except ValueError:
        flash("請選擇考勤月份。", "error")
        return redirect(url_for("attendance.attendance_home"))
    uploads = [
        item
        for item in request.files.getlist("files")
        if item and item.filename
    ]
    if not uploads:
        flash("請選擇 PDF。", "error")
        return redirect(url_for("attendance.attendance_home", month=year_month))
    batch = AttendanceBatch(
        batch_no=batch_no(),
        year_month=year_month,
        created_by=current_user.id,
        status="open",
    )
    db.session.add(batch)
    db.session.flush()
    root = Path(current_app.config["ATTENDANCE_BATCH_ROOT"]) / batch.batch_no
    root.mkdir(parents=True, exist_ok=True)
    for index, upload in enumerate(uploads, start=1):
        suffix = Path(upload.filename).suffix.lower()
        if suffix != ".pdf":
            continue
        target = root / f"{index:03d}_{Path(upload.filename).name}"
        upload.save(target)
        db.session.add(
            AttendanceBatchItem(
                batch=batch,
                original_filename=upload.filename,
                stored_path=str(target),
                mime_type=upload.mimetype or "application/pdf",
                file_size=target.stat().st_size,
                content_sha256=file_sha256(target),
                status="pending",
            )
        )
    db.session.commit()
    first = batch.items[0] if batch.items else None
    if not first:
        shutil.rmtree(root, ignore_errors=True)
        db.session.delete(batch)
        db.session.commit()
        flash("批次沒有可用的 PDF。", "error")
        return redirect(url_for("attendance.attendance_home", month=year_month))
    flash("考勤批次已建立。", "success")
    return redirect(
        url_for(
            "attendance.attendance_home",
            month=year_month,
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
    return send_file(
        path,
        mimetype=item.mime_type or "application/pdf",
        as_attachment=False,
        download_name=item.original_filename,
    )


def add_segments(summary, prefix):
    projects = request.form.getlist(f"{prefix}_project_id")
    working_days = request.form.getlist(f"{prefix}_working_days")
    ot_hours = request.form.getlist(f"{prefix}_ot_hours")
    holiday_days = request.form.getlist(f"{prefix}_holiday_days")
    large_ecall_counts = request.form.getlist(
        f"{prefix}_large_ecall_count"
    )
    ecall_counts = request.form.getlist(f"{prefix}_ecall_count")
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
        if project_id or days or ot or holiday or large_ecall or ecall:
            db.session.add(
                AttendanceSegment(
                    summary=summary,
                    period_kind=prefix,
                    project_id=project_id,
                    working_days=days,
                    ot_hours=ot,
                    sunday_holiday_days=holiday,
                    large_ecall_count=large_ecall,
                    ecall_count=ecall,
                )
            )


@attendance_bp.route("/attendance/items/<int:item_id>/save", methods=["POST"])
@login_required
def save_item(item_id):
    item = db.get_or_404(AttendanceBatchItem, item_id)
    employee = db.session.get(Employee, request.form.get("employee_id", type=int))
    if not employee:
        flash("必須選擇員工。", "error")
        return redirect(
            url_for(
                "attendance.attendance_home",
                month=item.batch.year_month,
                batch_id=item.batch_id,
                item_id=item.id,
            )
        )

    item_sha256 = item.content_sha256 or file_sha256(item.stored_path)
    item.content_sha256 = item_sha256
    duplicate_document = find_duplicate_employee_document(
        employee.id,
        "attendance_pdf",
        item_sha256,
        effective_month=item.batch.year_month,
    )
    if duplicate_document and not parse_bool(
        request.form.get("confirm_duplicate")
    ):
        db.session.commit()
        flash("考勤 PDF 與現有文件完全一致，請確認是否仍然替換。", "info")
        return redirect(
            url_for(
                "attendance.attendance_home",
                month=item.batch.year_month,
                batch_id=item.batch_id,
                item_id=item.id,
                employee_id=employee.id,
                duplicate_document_id=duplicate_document.id,
            )
        )

    summary = AttendanceMonthlySummary.query.filter_by(
        employee_id=employee.id,
        year_month=item.batch.year_month,
    ).first()
    if not summary:
        summary = AttendanceMonthlySummary(
            employee=employee,
            year_month=item.batch.year_month,
        )
        db.session.add(summary)
        db.session.flush()
    old_document = summary.document
    path = copy_file_to_employee(
        employee,
        item.stored_path,
        item.original_filename,
        "attendance_pdf",
    )
    document = EmployeeDocument(
        employee=employee,
        category="attendance_pdf",
        title=f"{item.batch.year_month} 考勤表",
        original_filename=item.original_filename,
        stored_path=str(path),
        mime_type=item.mime_type,
        file_ext=".pdf",
        file_size=path.stat().st_size,
        content_sha256=item_sha256,
        status="active",
        effective_month=item.batch.year_month,
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
    summary.no_attendance_reason = None
    summary.confirmed_by = current_user.id
    summary.confirmed_at = datetime.utcnow()
    summary.remarks = request.form.get("remarks", "").strip() or None
    for segment in list(summary.segments):
        db.session.delete(segment)
    db.session.flush()
    add_segments(summary, "current_1_20")
    add_segments(summary, "current_21_end_forecast")
    add_segments(summary, "previous_21_end")
    add_segments(summary, "previous_21_end_forecast")

    item.status = "saved"
    item.employee = employee
    item.summary_id = summary.id
    write_audit(
        "attendance_saved",
        "AttendanceMonthlySummary",
        summary.id,
        employee_id=employee.id,
        detail=f"{item.batch.year_month} 考勤已錄入",
    )
    db.session.commit()
    next_item = next(
        (row for row in item.batch.items if row.id > item.id and row.status == "pending"),
        None,
    )
    flash("考勤已保存。", "success")
    return redirect(
        url_for(
            "attendance.attendance_home",
            month=item.batch.year_month,
            batch_id=item.batch_id,
            item_id=next_item.id if next_item else item.id,
        )
    )


@attendance_bp.route(
    "/attendance/summaries/<int:summary_id>/correct",
    methods=["POST"],
)
@login_required
def correct_summary(summary_id):
    summary = db.get_or_404(AttendanceMonthlySummary, summary_id)
    employee = db.session.get(
        Employee,
        request.form.get("employee_id", type=int),
    )
    if not employee:
        flash("必須選擇員工。", "error")
        return redirect(
            url_for(
                "attendance.attendance_home",
                month=summary.year_month,
                employee_id=summary.employee_id,
                summary_id=summary.id,
            )
        )
    if employee.id != summary.employee_id:
        duplicate = AttendanceMonthlySummary.query.filter_by(
            employee_id=employee.id,
            year_month=summary.year_month,
        ).first()
        if duplicate and duplicate.id != summary.id:
            flash("目標員工本月已有考勤，請先核對或撤回該筆記錄。", "error")
            return redirect(
                url_for(
                    "attendance.attendance_home",
                    month=summary.year_month,
                    employee_id=summary.employee_id,
                    summary_id=summary.id,
                )
            )
    before = summary_snapshot(summary)
    old_employee_id = summary.employee_id
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
            title=old_document.title,
            original_filename=old_document.original_filename,
            stored_path=str(new_path),
            mime_type=old_document.mime_type,
            file_ext=old_document.file_ext,
            file_size=new_path.stat().st_size,
            content_sha256=old_document.content_sha256
            or file_sha256(new_path),
            status="active",
            effective_month=summary.year_month,
            uploaded_by=current_user.id,
        )
        db.session.add(new_document)
        db.session.flush()
        old_document.status = "replaced"
        old_document.replaced_by_document_id = new_document.id
        old_document.replacement_reason = "更正考勤所屬員工"
        summary.document = new_document
    summary.employee = employee
    summary.status = "received"
    summary.no_attendance_reason = None
    summary.confirmed_by = current_user.id
    summary.confirmed_at = datetime.utcnow()
    summary.remarks = request.form.get("remarks", "").strip() or None
    for item in AttendanceBatchItem.query.filter_by(summary_id=summary.id):
        item.employee = employee
        item.status = "saved"
    for segment in list(summary.segments):
        db.session.delete(segment)
    db.session.flush()
    add_segments(summary, "current_1_20")
    add_segments(summary, "current_21_end_forecast")
    add_segments(summary, "previous_21_end")
    add_segments(summary, "previous_21_end_forecast")
    db.session.flush()
    write_audit(
        "attendance_corrected",
        "AttendanceMonthlySummary",
        summary.id,
        employee_id=employee.id,
        detail=(
            f"更正 {summary.year_month} 考勤"
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
    return redirect(
        url_for(
            "attendance.attendance_home",
            month=summary.year_month,
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
    summary.status = "voided"
    if summary.document and summary.document.status == "active":
        summary.document.status = "voided"
        summary.document.replacement_reason = (
            request.form.get("reason", "").strip() or "撤回錯誤考勤"
        )
    for item in AttendanceBatchItem.query.filter_by(summary_id=summary.id):
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
    flash("考勤已撤回，不再參與 Payroll；原記錄仍保留。", "success")
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
    item.status = "skipped"
    db.session.commit()
    next_item = next(
        (row for row in item.batch.items if row.id > item.id and row.status == "pending"),
        None,
    )
    return redirect(
        url_for(
            "attendance.attendance_home",
            month=item.batch.year_month,
            batch_id=item.batch_id,
            item_id=next_item.id if next_item else item.id,
        )
    )


@attendance_bp.route("/attendance/batches/<int:batch_id>/delete", methods=["POST"])
@login_required
def delete_batch(batch_id):
    batch = db.get_or_404(AttendanceBatch, batch_id)
    year_month = batch.year_month
    folder = Path(current_app.config["ATTENDANCE_BATCH_ROOT"]) / batch.batch_no
    db.session.delete(batch)
    db.session.commit()
    shutil.rmtree(folder, ignore_errors=True)
    flash("批次已刪除；已歸檔到員工的考勤 PDF 不受影響。", "success")
    return redirect(url_for("attendance.attendance_home", month=year_month))


@attendance_bp.route("/attendance/not-required", methods=["POST"])
@login_required
def mark_not_required():
    employee = db.session.get(Employee, request.form.get("employee_id", type=int))
    year_month = request.form.get("year_month")
    reason = request.form.get("reason", "").strip()
    if not employee or not year_month or not reason:
        abort(400)
    summary = AttendanceMonthlySummary.query.filter_by(
        employee_id=employee.id,
        year_month=year_month,
    ).first()
    if not summary:
        summary = AttendanceMonthlySummary(
            employee=employee,
            year_month=year_month,
        )
        db.session.add(summary)
    summary.status = "not_required"
    summary.no_attendance_reason = reason
    summary.confirmed_by = current_user.id
    summary.confirmed_at = datetime.utcnow()
    write_audit(
        "attendance_not_required",
        "AttendanceMonthlySummary",
        employee_id=employee.id,
        detail=f"{year_month}: {reason}",
    )
    db.session.commit()
    return redirect(url_for("attendance.attendance_home", month=year_month))


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
            month=item.batch.year_month,
            batch_id=item.batch_id,
            item_id=item.id,
        )
    )
