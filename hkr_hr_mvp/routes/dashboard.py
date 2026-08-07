from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required
from markdown import Markdown
from markupsafe import Markup
from sqlalchemy import and_, or_

from models import (
    AttendanceMonthlySummary,
    Employee,
    EmployeeCertificate,
    EmployeeIdentity,
    EmployeeTaskNote,
    EmployeeVisa,
    db,
)
from tools.hr_core import current_month, parse_year_month, write_audit
from tools.payroll_engine import calculate_payroll
from tools.releases import RELEASES


dashboard_bp = Blueprint("dashboard", __name__)
GUIDE_FILENAME = "操作指南.md"
TASK_TYPES = {
    "missing_salary": ("缺薪酬資料", "danger"),
    "missing_staff_record": ("缺 Staff Record", "warning"),
    "missing_signed_contract": ("缺已簽署合同", "warning"),
}
TASK_PROGRESS = {"pending", "in_progress", "waiting"}


def guide_path():
    return Path(current_app.root_path) / GUIDE_FILENAME


@dashboard_bp.route("/updates")
@login_required
def updates():
    return render_template("updates.html", releases=RELEASES)


@dashboard_bp.route("/guide")
@login_required
def guide():
    path = guide_path()
    if not path.is_file():
        abort(404)
    source = path.read_text(encoding="utf-8")
    renderer = Markdown(extensions=["extra", "toc"], output_format="html5")
    guide_html = Markup(renderer.convert(source))
    return render_template("guide.html", guide_html=guide_html)


@dashboard_bp.route("/dashboard")
@login_required
def dashboard():
    year_month = request.args.get("month") or current_month()
    month_start, month_end = parse_year_month(year_month)
    active_employees = [
        employee
        for employee in Employee.query.all()
        if employee.is_active_on(date.today())
    ]

    payroll_rows = calculate_payroll(year_month, "all")
    estimated_payroll = sum(
        (
            Decimal(str(row.get("net_amount", 0)))
            for row in payroll_rows
            if not row.get("blockers")
        ),
        Decimal("0"),
    )
    payroll_unready_count = sum(
        1 for row in payroll_rows if row.get("blockers")
    )
    tasks = []
    for employee in active_employees:
        if not employee.current_salary:
            tasks.append(
                {
                    "employee": employee,
                    "code": "missing_salary",
                    "label": TASK_TYPES["missing_salary"][0],
                    "kind": TASK_TYPES["missing_salary"][1],
                }
            )
        active_categories = {
            document.category
            for document in employee.documents
            if document.status == "active"
        }
        if "staff_record" not in active_categories:
            tasks.append(
                {
                    "employee": employee,
                    "code": "missing_staff_record",
                    "label": TASK_TYPES["missing_staff_record"][0],
                    "kind": TASK_TYPES["missing_staff_record"][1],
                }
            )
        if "signed_contract" not in active_categories:
            tasks.append(
                {
                    "employee": employee,
                    "code": "missing_signed_contract",
                    "label": TASK_TYPES["missing_signed_contract"][0],
                    "kind": TASK_TYPES["missing_signed_contract"][1],
                }
            )

    notes = (
        EmployeeTaskNote.query.filter(
            EmployeeTaskNote.employee_id.in_(
                [employee.id for employee in active_employees]
            )
        )
        .order_by(EmployeeTaskNote.created_at.desc())
        .all()
        if active_employees
        else []
    )
    notes_by_task = {}
    for note in notes:
        notes_by_task.setdefault(
            (note.employee_id, note.task_code),
            [],
        ).append(note)
    for task in tasks:
        task["notes"] = notes_by_task.get(
            (task["employee"].id, task["code"]),
            [],
        )
        task["progress"] = (
            task["notes"][0].progress if task["notes"] else "pending"
        )
    task_type = request.args.get("task_type", "")
    task_progress = request.args.get("task_progress", "")
    task_search = request.args.get("task_q", "").strip().casefold()
    if task_type in TASK_TYPES:
        tasks = [task for task in tasks if task["code"] == task_type]
    if task_progress in TASK_PROGRESS:
        tasks = [
            task for task in tasks if task["progress"] == task_progress
        ]
    if task_search:
        tasks = [
            task
            for task in tasks
            if task_search
            in (
                f"{task['employee'].employee_no} "
                f"{task['employee'].display_name}"
            ).casefold()
        ]

    expected = [
        employee
        for employee in Employee.query.all()
        if employee.employed_during(month_start, month_end)
    ]
    received_ids = {
        row.employee_id
        for row in AttendanceMonthlySummary.query.filter_by(
            year_month=year_month,
            status="received",
        ).all()
    }

    threshold = date.today() + timedelta(days=60)
    expiry_alerts = []
    for identity in EmployeeIdentity.query.filter(
        EmployeeIdentity.status == "active",
        EmployeeIdentity.is_long_term.is_(False),
        EmployeeIdentity.expiry_date.isnot(None),
        EmployeeIdentity.expiry_date <= threshold,
    ).all():
        expiry_alerts.append(
            {
                "employee": identity.employee,
                "label": identity.identity_type,
                "date": identity.expiry_date,
            }
        )
    for certificate in EmployeeCertificate.query.filter(
        EmployeeCertificate.status == "active",
        EmployeeCertificate.is_long_term.is_(False),
        EmployeeCertificate.expiry_date.isnot(None),
        EmployeeCertificate.expiry_date <= threshold,
    ).all():
        expiry_alerts.append(
            {
                "employee": certificate.employee,
                "label": certificate.certificate_type.display_name,
                "date": certificate.expiry_date,
            }
        )
    for visa in EmployeeVisa.query.filter(
        EmployeeVisa.status == "active",
        EmployeeVisa.expiry_date.isnot(None),
        EmployeeVisa.expiry_date <= threshold,
    ).all():
        expiry_alerts.append(
            {
                "employee": visa.employee,
                "label": visa.visa_category.display_name,
                "date": visa.expiry_date,
            }
        )
    expiry_alerts.sort(key=lambda item: item["date"] or date.max)

    return render_template(
        "dashboard.html",
        year_month=year_month,
        active_count=len(active_employees),
        estimated_payroll=estimated_payroll,
        payroll_unready_count=payroll_unready_count,
        attendance_expected=len(expected),
        attendance_received=len(received_ids.intersection({item.id for item in expected})),
        tasks=tasks,
        task_types=TASK_TYPES,
        task_progress_options=("pending", "in_progress", "waiting"),
        task_filters={
            "type": task_type,
            "progress": task_progress,
            "q": request.args.get("task_q", "").strip(),
        },
        expiry_alerts=expiry_alerts[:20],
    )


@dashboard_bp.route(
    "/dashboard/tasks/<int:employee_id>/<task_code>/notes",
    methods=["POST"],
)
@login_required
def add_task_note(employee_id, task_code):
    employee = db.get_or_404(Employee, employee_id)
    if task_code not in TASK_TYPES:
        abort(400)
    progress = request.form.get("progress", "pending")
    note_text = request.form.get("note", "").strip()
    if progress not in TASK_PROGRESS or not note_text:
        flash("請選擇進度並填寫備註。", "error")
    else:
        note = EmployeeTaskNote(
            employee=employee,
            task_code=task_code,
            progress=progress,
            note=note_text,
            created_by=current_user.id,
        )
        db.session.add(note)
        db.session.flush()
        write_audit(
            "task_note_added",
            "EmployeeTaskNote",
            note.id,
            employee_id=employee.id,
            detail=f"{TASK_TYPES[task_code][0]}：{progress}",
        )
        db.session.commit()
        flash("待辦進度備註已保存。", "success")
    return redirect(
        url_for(
            "dashboard.dashboard",
            month=request.form.get("month") or current_month(),
            task_type=request.form.get("task_type", ""),
            task_progress=request.form.get("task_progress", ""),
            task_q=request.form.get("task_q", ""),
        )
        + "#tasks"
    )
