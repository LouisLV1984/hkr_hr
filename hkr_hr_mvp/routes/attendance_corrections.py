"""Dated corrections entered while working on an employee's payment month."""
import calendar
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from flask import Blueprint, abort, jsonify, render_template, request, session, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import StaleDataError

from models import AttendanceCorrection, AttendanceMonthlySummary, Employee, EmployeeDocument, WorkProject, db
from tools.hr_core import current_assignment_on, current_salary_on, file_sha256, previous_month, store_employee_file, write_audit
from tools.i18n import TRANSLATIONS, normalize_language
from tools.payroll_engine import employment_period_on, rounded, salary_rate_for_date
from tools.security import UploadValidationError, validate_uploaded_file

bp = Blueprint("corrections", __name__)


def fail(key):
    raise ValueError(TRANSLATIONS[normalize_language(session.get("lang"))]["corr." + key])


def month_start(value):
    try:
        return date.fromisoformat(value + "-01")
    except (TypeError, ValueError):
        abort(400)


def price_rows(employee, pay, source, form):
    dates = form.getlist("work_date")
    month_end = date(pay.year, pay.month, calendar.monthrange(pay.year, pay.month)[1])
    salary = current_salary_on(employee, month_end)
    # A departing worker can have an end-dated salary before month end.
    if not salary:
        salary = next((s for s in sorted(employee.salaries, key=lambda s: s.effective_from, reverse=True)
                       if s.status == "active" and s.effective_from <= month_end
                       and (not s.effective_to or s.effective_to >= pay)), None)
    if not salary:
        fail("missing_rate")
    lines = []
    for i, raw in enumerate(dates):
        try:
            day = date.fromisoformat(raw)
            kind, direction, quantity, project_code, tail = (
                form.getlist(key)[i] for key in ("kind", "direction", "quantity", "project", "tail")
            )
            units = Decimal(quantity)
        except (ValueError, IndexError, InvalidOperation):
            fail("invalid")
        if (day.replace(day=1) != source or kind not in ("ot", "day")
                or direction not in ("add", "deduct") or not units.is_finite()
                or not 0 < units <= (24 if kind == "ot" else 1) or units * 2 != int(units * 2)):
            fail("invalid")
        if not employment_period_on(employee, day):
            fail("missing_rate")
        assignment = current_assignment_on(employee, day)
        project = assignment.project if assignment else None
        if project_code:
            project = db.session.get(WorkProject, int(project_code))
            if not project:
                fail("invalid")
        rates = salary_rate_for_date(employee, day, project)
        if not rates or rates["salary"].currency != salary.currency:
            fail("missing_rate")
        old_salary = rates["salary"]
        if kind == "ot":
            rate = rates["ot_rate"]
        elif old_salary.salary_basis == "monthly" and old_salary.monthly_pay_method != "attendance_days":
            rate = Decimal(0)
        else:
            rate = rates["base_rate"]
        overlaps_tail = day.day >= 21 and previous_month(pay.strftime("%Y-%m")) == day.strftime("%Y-%m")
        if overlaps_tail and tail not in ("included", "extra"):
            fail("tail_choice")
        included = overlaps_tail and tail == "included"
        signed = units if direction == "add" else -units
        amount = Decimal(0) if included else rounded(signed * rate)
        lines.append(dict(date=raw, kind=kind, direction=direction, quantity=str(units),
                          project_id=project.id if project else None, project=project.name if project else "",
                          chosen_project=project_code, rate=str(rate), amount=str(amount),
                          tail=tail if overlaps_tail else "", included=included))
    return lines, salary.currency


def history_for(employee_id, month):
    return AttendanceCorrection.query.filter(
        AttendanceCorrection.employee_id == employee_id,
        db.or_(AttendanceCorrection.source_month == month, AttendanceCorrection.pay_month == month),
    ).order_by(AttendanceCorrection.pay_month.desc(), AttendanceCorrection.source_month.desc()).all()


@bp.route("/attendance/<int:employee_id>/corrections/<pay_month>/<source_month>", methods=["GET", "POST"])
@login_required
def editor(employee_id, pay_month, source_month):
    employee = db.get_or_404(Employee, employee_id)
    pay, source = month_start(pay_month), month_start(source_month)
    if source >= pay:
        abort(400)
    record = AttendanceCorrection.query.filter_by(employee_id=employee_id, pay_month=pay_month,
                                                 source_month=source_month).one_or_none()
    if request.method == "GET":
        summary = AttendanceMonthlySummary.query.filter_by(employee_id=employee_id, year_month=source_month).first()
        return render_template("attendance/_correction_editor.html", employee=employee, pay=pay_month,
                               source=source_month, record=record, summary=summary,
                               prior=AttendanceCorrection.query.filter_by(employee_id=employee_id, source_month=source_month).filter(AttendanceCorrection.pay_month != pay_month).all(),
                               projects=WorkProject.query.order_by(WorkProject.name).all(),
                               source_end=source.replace(day=calendar.monthrange(source.year, source.month)[1]))
    saved_paths = []
    committed = False
    try:
        lines, currency = price_rows(employee, pay, source, request.form)
        total = sum((Decimal(line["amount"]) for line in lines), Decimal("0.00"))
        if request.form.get("action") == "preview":
            return jsonify(lines=lines, total=str(total), currency=currency)
        if not lines and not record:
            fail("invalid")
        if request.form.get("revision", type=int) != (record.revision if record else 0):
            fail("stale")
        uploads = [f for f in request.files.getlist("evidence") if f.filename]
        for upload in uploads:
            validate_uploaded_file(upload, allowed_extensions={".pdf", ".jpg", ".jpeg", ".png"})
        if not record:
            record = AttendanceCorrection(employee_id=employee_id, source_month=source_month, pay_month=pay_month)
            db.session.add(record)
        before = dict(lines=record.lines, amount=str(record.amount)) if record.id else None
        record.lines, record.amount, record.currency, record.edited_by = lines, total, currency, current_user.id
        record.updated_at = datetime.utcnow()
        db.session.flush()
        for upload in uploads:
            path = store_employee_file(employee, upload, "change_evidence")
            saved_paths.append(path)
            document = EmployeeDocument(employee_id=employee_id, category="change_evidence", title="考勤更正憑證",
                                        original_filename=upload.filename, stored_path=str(path),
                                        file_ext="." + upload.filename.rsplit(".", 1)[-1].lower(), mime_type=upload.mimetype,
                                        file_size=path.stat().st_size, content_sha256=file_sha256(path),
                                        uploaded_by=current_user.id, status="active")
            record.documents.append(document)
        db.session.flush()
        write_audit("attendance_corrected_for_payroll", "AttendanceCorrection", record.id,
                    employee_id=employee_id, before=before,
                    after=dict(source=source_month, pay=pay_month, lines=lines, amount=str(total),
                               documents=[d.id for d in record.documents]))
        db.session.commit()
        committed = True
        return jsonify(history=render_template("attendance/_correction_history.html",
                                               records=history_for(employee_id, pay_month)), total=str(total))
    except (IntegrityError, StaleDataError):
        return jsonify(error=TRANSLATIONS[normalize_language(session.get("lang"))]["corr.stale"]), 409
    except (ValueError, UploadValidationError) as exc:
        return jsonify(error=str(exc)), 400
    finally:
        if not committed and request.form.get("action") != "preview":
            db.session.rollback()
            for path in saved_paths:
                path.unlink(missing_ok=True)
