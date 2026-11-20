"""Manual salary history. Never calls a payroll calculator or contribution writer."""
from datetime import date
from decimal import Decimal
from io import BytesIO
from pathlib import Path

from flask import Blueprint, abort, current_app, flash, jsonify, render_template, request, send_file, session, url_for
from flask_login import current_user, login_required
from itsdangerous import BadData, URLSafeTimedSerializer
from sqlalchemy.exc import IntegrityError

from hkr_hr.platform.db import db, AuditLog
from hkr_hr.employees.api import Employee
from hkr_hr.documents.api import EmployeeDocument
from hkr_hr.payroll.models import PayrollEmployeeResult, PayrollRun, SalaryRecord
from hkr_hr.references.api import ReferenceValue
from hkr_hr.platform.audit import write_audit
from hkr_hr.references.api import reference_options
from hkr_hr.platform.files import store_employee_file, file_sha256
from hkr_hr.platform.i18n import TRANSLATIONS, normalize_language
from hkr_hr.payroll.service.salary_records import START_MONTH, MONEY_FIELDS, annual_summary, checked_month, monthly_rows, parse_values, record_values
from hkr_hr.platform.security import validate_uploaded_file, CANONICAL_MIME_TYPES

salary_records_bp = Blueprint("salary_records", __name__)


@salary_records_bp.after_request
def private_response(response):
    response.headers['Cache-Control'] = 'private, no-store'
    return response


@salary_records_bp.app_template_filter('hong_kong_datetime')
def display_time(value, fmt='%Y-%m-%d %H:%M'):
    from hkr_hr.platform.dates import hong_kong_datetime
    local = hong_kong_datetime(value)
    return local.strftime(fmt) if local else '—'


def t(key, **values):
    return TRANSLATIONS[normalize_language(session.get("lang"))].get(key,
        TRANSLATIONS["zh-Hant"].get(key, key)).format(**values)


def serializer():
    return URLSafeTimedSerializer(current_app.secret_key, salt="salary-record-editor-v1")


def identity(record):
    return [record.id, record.revision, record.status] if record else None


def snapshot(record):
    return dict(record_values(record), month=record.year_month, entity_id=record.payroll_entity_id,
                status=record.status, revision=record.revision, evidence_document_id=record.evidence_document_id)


def entity_options():
    return reference_options('payroll_entity', active_only=False)


def selected_entity(raw, required=False):
    if not raw and not required:
        return None
    row = next((row for row in entity_options() if row.id == int(raw)), None) if str(raw).isdigit() else None
    if row is None:
        raise ValueError("salary_record.choose_entity")
    return row.id


@salary_records_bp.get("/salary-records")
@login_required
def index():
    try:
        requested_month = request.args.get("month")
        if requested_month:
            month = checked_month(requested_month)
        else:
            month = session.get("operating_month") or date.today().strftime("%Y-%m")
            try:
                month = checked_month(month)
            except ValueError:
                month = date.today().strftime("%Y-%m")
                flash(t("hr.salary_record_month", month=month), "info")
        entity_id = selected_entity(request.args.get("entity_id", session.get("operating_entity_id")))
    except ValueError as exc:
        abort(400, description=t(str(exc)))
    session["operating_month"] = month
    session["operating_entity_id"] = entity_id or ""
    rows = monthly_rows(month, entity_id, request.args.get("employee_id", type=int), request.args.get("q", "")) if entity_id else []
    token = serializer().dumps(dict(user=current_user.id, month=month, entity=entity_id,
        rows={str(r["employee"].id): dict(identity=identity(r["record"]), values=r["values"]) for r in rows}))
    record_ids = [r["record"].id for r in rows if r["record"]]
    history = AuditLog.query.filter(AuditLog.entity_type == "SalaryRecord", AuditLog.entity_id.in_(record_ids)).order_by(AuditLog.id.desc()).all() if record_ids else []
    return render_template("salary_records/index.html", month=month, entity_id=entity_id,
        entities=entity_options(), currencies=reference_options('currency', active_only=False),
        rows=rows, editor_token=token, history=history,
        all_employees=Employee.query.order_by(Employee.employee_no).all(), start_month=START_MONTH,
        max_month=date.today().strftime("%Y-%m"), money_fields=MONEY_FIELDS)


@salary_records_bp.post("/salary-records/save")
@login_required
def save():
    created_paths = []
    try:
        data = serializer().loads(request.form.get("editor_token", ""))
        if data["user"] != current_user.id:
            raise ValueError("salary_record.stale")
        month = checked_month(data["month"])
        entity_id = selected_entity(data["entity"], required=True)
        configured_currencies = {r.code for r in reference_options('currency', active_only=False)}
        changes = []
        for eid, initial in data["rows"].items():
            raw = {field: request.form.get(f"{eid}.{field}", "").strip() for field in initial["values"]}
            upload = request.files.get(f"{eid}.evidence")
            has_file = bool(upload and upload.filename)
            if raw == initial["values"] and not has_file:
                continue
            # A blank row is unrecorded, not a zero salary. Require all three amounts.
            if not any(raw[f] for f in MONEY_FIELDS) and not raw["remarks"] and not has_file and not initial["identity"]:
                continue
            values = parse_values(request.form, eid)
            if values['currency'] not in configured_currencies and not (
                initial['identity'] and values['currency'] == initial['values']['currency']
            ):
                raise ValueError('salary_record.invalid_currency')
            if values == initial["values"] and not has_file:
                continue
            if has_file:
                validate_uploaded_file(upload)
            changes.append((int(eid), initial, values, upload if has_file else None))
        # Serialize concurrent editors even when the employee-month row does not exist yet.
        for eid, initial, values, upload in sorted(changes, key=lambda c:c[0]):
            employee = Employee.query.filter_by(id=eid).with_for_update().populate_existing().first()
            if not employee:
                raise ValueError("salary_record.stale")
            record = SalaryRecord.query.filter_by(employee_id=eid, year_month=month, payroll_entity_id=entity_id).populate_existing().first()
            if identity(record) != initial["identity"]:
                raise ValueError("salary_record.stale")
            before = snapshot(record) if record else None
            if record is None:
                record = SalaryRecord(employee=employee, year_month=month, payroll_entity_id=entity_id, revision=0)
                db.session.add(record)
            for field, value in values.items():
                setattr(record, field, Decimal(value) if field in MONEY_FIELDS else value)
            record.status = "active"
            record.revision += 1
            record.updated_by = current_user.id
            if upload:
                path = store_employee_file(employee, upload, 'salary_record')
                # Track the file before any ORM flush can fail.
                created_paths.append(path)
                suffix = Path(upload.filename).suffix.lower()
                document = EmployeeDocument(employee=employee, category='salary_record',
                    title=f"{month} {t('salary_record.title')}", original_filename=upload.filename,
                    stored_path=str(path), mime_type=CANONICAL_MIME_TYPES[suffix], file_ext=suffix,
                    file_size=path.stat().st_size, content_sha256=file_sha256(path),
                    status='active', uploaded_by=current_user.id)
                db.session.add(document)
                record.evidence_document = document
            db.session.flush()
            write_audit("salary_record_saved", "SalaryRecord", record.id, eid,
                        before=before, after=snapshot(record))
        db.session.commit()
        flash(t("salary_record.saved", count=len(changes)), "success")
        return jsonify(redirect=url_for("salary_records.index", month=month, entity_id=entity_id,
                                       employee_id=request.form.get("extra_employee_id") or None, q=request.form.get("search") or None))
    except (BadData, KeyError, ValueError, IntegrityError) as exc:
        db.session.rollback()
        for path in created_paths:
            # Only files just created by this transaction, never pre-existing evidence.
            path.unlink(missing_ok=True)
        key = str(exc) if isinstance(exc, ValueError) else "salary_record.stale"
        return jsonify(error=t(key)), 422
    except Exception:
        db.session.rollback()
        for path in created_paths:
            path.unlink(missing_ok=True)
        raise


@salary_records_bp.post("/salary-records/<int:record_id>/withdraw")
@login_required
def withdraw(record_id):
    record = db.get_or_404(SalaryRecord, record_id)
    Employee.query.filter_by(id=record.employee_id).with_for_update().first()
    db.session.refresh(record)
    reason = request.form.get("reason", "").strip()
    if not reason or len(reason)>2000:
        return jsonify(error=t("salary_record.reason_required")), 422
    if record.revision != request.form.get("revision", type=int) or record.status != "active":
        return jsonify(error=t("salary_record.stale")), 409
    before = snapshot(record)
    record.status = "voided"
    record.revision += 1
    record.updated_by = current_user.id
    write_audit("salary_record_withdrawn", "SalaryRecord", record.id, record.employee_id,
                detail=reason, before=before, after=snapshot(record))
    db.session.commit()
    return jsonify(redirect=url_for("salary_records.index", month=record.year_month, entity_id=record.payroll_entity_id))


@salary_records_bp.get("/salary-records/prefill")
@login_required
def prefill():
    try:
        month = checked_month(request.args.get("month"))
        entity_id = selected_entity(request.args.get("entity_id"), True)
    except ValueError as exc:
        return jsonify(error=t(str(exc))), 400
    entity = db.session.get(ReferenceValue, entity_id)
    candidates = (PayrollEmployeeResult.query.join(PayrollRun)
        .filter(PayrollRun.year_month == month, PayrollEmployeeResult.employee_id == request.args.get("employee_id", type=int))
        .order_by(PayrollRun.created_at.desc(), PayrollRun.id.desc()).all())
    record = next((r for r in candidates if (r.calculation_json or {}).get("payroll_entity_code") == entity.code), None)
    if record is None:
        return jsonify(error=t("salary_record.no_snapshot")), 404
    return jsonify(values={**{f:str(getattr(record,f)) for f in MONEY_FIELDS}, "currency":record.currency},
                   message=t("salary_record.prefilled", run=record.run_id))


@salary_records_bp.get("/salary-records/annual")
@salary_records_bp.get("/salary-records/annual/export", endpoint="export")
@login_required
def annual():
    year = request.args.get("year", date.today().year if date.today().month>=4 else date.today().year-1, type=int)
    try:
        entity_id = selected_entity(request.args.get("entity_id"))
        rows, details, months = annual_summary(year, entity_id)
    except ValueError as exc:
        abort(400, description=t(str(exc)))
    if request.path.endswith("/export"):
        from hkr_hr.payroll.rules.salary_records_export import build_workbook
        workbook = build_workbook(year, rows, details, t)
        buffer = BytesIO()
        workbook.save(buffer)
        buffer.seek(0)
        write_audit("salary_records_exported", "SalaryRecord", detail=f"{year}-04/{year+1}-03; entity={entity_id}; rows={len(details)}")
        db.session.commit()
        return send_file(buffer, as_attachment=True, download_name=f"HKR_Salary_Records_{year}-{year+1}.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    return render_template("salary_records/annual.html", rows=rows, year=year, entity_id=entity_id,
        entities=entity_options(), years=range(2026,date.today().year+1), money_fields=MONEY_FIELDS)
