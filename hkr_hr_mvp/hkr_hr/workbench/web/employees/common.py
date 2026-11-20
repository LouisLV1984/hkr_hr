"""Shared blueprint, snapshots, history builders, and query helpers for the employee workspace."""
from hkr_hr.payroll.api import originating_payroll, salary_gaps


from hkr_hr.employees.api import workbench_options


from hkr_hr.platform.dates import valid_salary_amount


from hkr_hr.attendance.api import profile_revision


import hmac


from datetime import date, datetime


from pathlib import Path


from flask import (
    Blueprint,
    abort,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)


from flask_login import current_user, login_required


from sqlalchemy import or_


from hkr_hr.leave.api import conflicting_absence


from hkr_hr.employees.api import active_successor, credential_form_validation, credential_state, identity_conflict, renewal_source


from hkr_hr.attendance.api import AttendanceCorrection, AttendanceBatch, AttendanceMonthlySummary, AttendanceBatchItem


from hkr_hr.platform.db import AuditLog, db


from hkr_hr.employees.api import Employee, EmployeeAllowance, EmployeeAssignment, EmployeeAssignmentPosition, EmployeeBankAccount, EmployeeCertificate, EmployeeEmploymentPeriod, EmployeeIdentity, EmployeeMpfEnrollment, EmployeeQualification, EmployeeSalary, EmployeeVisa


from hkr_hr.leave.api import EmployeeAnnualLeaveBalance, EmployeeAnnualLeaveRecord, EmployeeCompLeaveCredit, EmployeeWorkInjuryPeriod, EmployeeWorkInjuryMonthlyExpense


from hkr_hr.documents.api import EmployeeDocument, GeneratedContract


from hkr_hr.references.api import MpfScheme, ReferenceValue, WorkProject


from hkr_hr.payroll.api import PayrollAdjustment, PayrollEmployeeResult, PayrollRun


from hkr_hr.payroll.api import employee_data_items, employee_readiness, missing_employee_data_labels, mpf_data_item


from hkr_hr.attendance.api import attendance_required, policy_on, set_long_term_attendance_policy


from hkr_hr.platform.dates import DOCUMENT_CATEGORIES, IDENTITY_TYPE_OPTIONS, PAYROLL_GROUPS, TERMINATION_REASONS, annual_leave_days_between, current_month, format_money, masked_bank_account, normalize_identity_number, normalize_workweek_days, parse_bool, parse_date, parse_decimal, parse_year_month, REPLACEMENT_REASONS


from hkr_hr.leave.api import annual_leave_summary, allocate_annual_leave_with_comp, clear_leave_allocations, comp_leave_summary, set_annual_leave_allocations


from hkr_hr.payroll.api import average_wage_prefill, termination_estimate


from hkr_hr.employees.api import create_assignment, create_mpf_enrollment, create_salary, current_assignment_on, current_bank_account_on, current_mpf_on, current_salary_on, employee_audit_snapshot, ensure_current_employment_period, next_employee_no, rebuild_effective_ranges


from hkr_hr.platform.files import delete_employee_files, employee_files_path, file_sha256, store_employee_file, uploaded_file_sha256


from hkr_hr.references.api import reference_map, reference_options, reference_sort_key


from hkr_hr.platform.audit import write_audit


from hkr_hr.payroll.api import calculate_employee, calculate_payroll


from hkr_hr.platform.search import chinese_search_variants


employees_bp = Blueprint("employees", __name__)


def document_management_tab(document):
    """Return the employee module that owns changes to a linked document."""
    document_id = document.id
    if document.category == 'salary_record':
        return 'attendance'
    if EmployeeBankAccount.query.filter_by(
        evidence_document_id=document_id
    ).first():
        return "personal"
    if (
        EmployeeIdentity.query.filter_by(document_id=document_id).first()
        or EmployeeCertificate.query.filter_by(document_id=document_id).first()
        or EmployeeVisa.query.filter_by(document_id=document_id).first()
        or EmployeeQualification.query.filter_by(document_id=document_id).first()
    ):
        return "credentials"
    if (
        EmployeeAnnualLeaveRecord.query.filter_by(
            evidence_document_id=document_id
        ).first()
        or EmployeeWorkInjuryPeriod.query.filter_by(
            evidence_document_id=document_id
        ).first()
    ):
        return "leave"
    if AttendanceMonthlySummary.query.filter_by(document_id=document_id).first():
        return "attendance"
    if (
        EmployeeAssignment.query.filter_by(
            evidence_document_id=document_id
        ).first()
        or EmployeeSalary.query.filter_by(
            evidence_document_id=document_id
        ).first()
        or EmployeeAllowance.query.filter_by(
            evidence_document_id=document_id
        ).first()
        or EmployeeEmploymentPeriod.query.filter(
            or_(
                EmployeeEmploymentPeriod.confirmation_document_id == document_id,
                EmployeeEmploymentPeriod.termination_document_id == document_id,
            )
        ).first()
    ):
        return "employment"
    return {
        "identity": "credentials",
        "visa": "credentials",
        "qualification": "credentials",
        "bank_proof": "personal",
        "name_change_evidence": "personal",
        "attendance_pdf": "attendance",
        "change_evidence": "employment",
        "contract_draft": "employment",
        "probation_confirmation": "employment_status",
        "termination_letter": "employment_status",
    }.get(document.category)


def form_int(name):
    try:
        return int(request.form.get(name, "").strip())
    except (TypeError, ValueError):
        return None


def employee_redirect(employee_id, tab="overview", *, saved=False):
    context = {key: request.form[key] for key in ("from_payroll", "pay_month", "pay_group",
               "pay_entity", "pay_status", "pay_q", "pay_employee", "focus") if key in request.form}
    back = originating_payroll(context, context.get("pay_month"))
    if saved and back:
        return redirect(back)
    return redirect(url_for("employees.view_employee", employee_id=employee_id, tab=tab, **context))


def bank_account_snapshot(account):
    return {
        "effective_from": account.effective_from.isoformat(),
        "effective_to": account.effective_to.isoformat() if account.effective_to else None,
        "bank_name": account.bank_name,
        "account_no": masked_bank_account(account.account_no),
        "currency": account.currency,
        "status": account.status,
        "evidence_document_id": account.evidence_document_id,
        "remarks": account.remarks,
    }


def sync_legacy_bank_fields(employee):
    current = current_bank_account_on(employee, date.today())
    employee.bank_name = current.bank_name if current else None
    employee.bank_account_no = current.account_no if current else None


def annual_leave_redirect(employee_id, year=None):
    if request.form.get("return_to") == "annual_leave":
        return redirect(
            url_for(
                "leave.leave_home",
                origin="workbench" if request.form.get("origin")=="workbench" else None,
                employee_id=employee_id,
                year=year or date.today().year,
                **{key: request.form["back_" + key] for key in ("q","status","action","project_id","payroll_group")
                   if request.form.get("back_" + key)},
            )
            + "#employee-leave"
        )
    return employee_redirect(employee_id, "leave")


def save_evidence(employee, uploaded, category, title):
    if not uploaded or not uploaded.filename:
        return None
    path = store_employee_file(employee, uploaded, category)
    document = EmployeeDocument(
        employee=employee,
        category=category,
        title=title,
        original_filename=uploaded.filename,
        stored_path=str(path),
        mime_type=uploaded.mimetype,
        file_ext=Path(uploaded.filename).suffix.lower(),
        file_size=path.stat().st_size,
        content_sha256=file_sha256(path),
        status="active",
        uploaded_by=current_user.id,
    )
    db.session.add(document)
    db.session.flush()
    return document


def replace_record_evidence(
    employee,
    current_document,
    uploaded,
    category,
    title,
    replacement_reason="證件資料更新",
):
    if not uploaded or not uploaded.filename:
        return current_document
    digest = uploaded_file_sha256(uploaded)
    if (
        current_document
        and digest
        and digest == (current_document.content_sha256 or "")
    ):
        return current_document
    document = save_evidence(employee, uploaded, category, title)
    if not document or not current_document:
        return document
    from hkr_hr.documents.api import document_reference_count
    linked_rows = document_reference_count(current_document)
    if linked_rows <= 1 and current_document.status == "active":
        current_document.status = "replaced"
        current_document.replaced_by_document_id = document.id
        current_document.replacement_reason = replacement_reason
    return document


def credential_snapshot(item, fields):
    return {
        field: (
            value.isoformat()
            if isinstance((value := getattr(item, field, None)), date)
            else value
        )
        for field in fields
    }


def assignment_snapshot(assignment):
    return {
        "effective_from": assignment.effective_from.isoformat(),
        "effective_to": (
            assignment.effective_to.isoformat()
            if assignment.effective_to
            else None
        ),
        "region_id": assignment.region_id,
        "project_id": assignment.project_id,
        "department_id": assignment.department_id,
        "payroll_group": assignment.payroll_group,
        "workweek_days": str(assignment.workweek_days),
        "position_ids": [
            item.position_id for item in assignment.positions
        ],
        "status": assignment.status,
        "evidence_document_id": assignment.evidence_document_id,
    }


def salary_snapshot(salary):
    return {
        "effective_from": salary.effective_from.isoformat(),
        "effective_to": (
            salary.effective_to.isoformat() if salary.effective_to else None
        ),
        "salary_basis": salary.salary_basis,
        "monthly_pay_method": salary.monthly_pay_method or "full_month",
        "currency": salary.currency,
        "amount": str(salary.amount),
        "status": salary.status,
        "evidence_document_id": salary.evidence_document_id,
    }


def mpf_snapshot(enrollment):
    return {
        "effective_from": enrollment.effective_from.isoformat(),
        "effective_to": (
            enrollment.effective_to.isoformat()
            if enrollment.effective_to
            else None
        ),
        "scheme_id": enrollment.scheme_id,
        "scheme_name": enrollment.scheme.name if enrollment.scheme else None,
        "member_account_no": enrollment.member_account_no,
        "contribution_mode": enrollment.contribution_mode,
        "status": enrollment.status,
    }


def employment_period_snapshot(period):
    return {
        "start_date": period.start_date.isoformat(),
        "contract_annual_leave_days": str(period.contract_annual_leave_days) if period.contract_annual_leave_days is not None else None,
        "annual_leave_policy_year": period.annual_leave_policy_year,
        "annual_leave_contract_verified": period.annual_leave_contract_verified,
        "end_date": period.end_date.isoformat() if period.end_date else None,
        "probation_end_date": (
            period.probation_end_date.isoformat()
            if period.probation_end_date
            else None
        ),
        "confirmation_date": (
            period.confirmation_date.isoformat()
            if period.confirmation_date
            else None
        ),
        "confirmation_document_id": period.confirmation_document_id,
        "termination_reason": period.termination_reason,
        "average_wage": (
            str(period.average_wage)
            if period.average_wage is not None
            else None
        ),
        "payment_in_lieu": (
            str(period.payment_in_lieu)
            if period.payment_in_lieu is not None
            else None
        ),
        "severance_payment": (
            str(period.severance_payment)
            if period.severance_payment is not None
            else None
        ),
        "long_service_payment": (
            str(period.long_service_payment)
            if period.long_service_payment is not None
            else None
        ),
        "termination_document_id": period.termination_document_id,
    }


AUDIT_FIELD_LABELS = {
    "effective_from": "audit.field.effective_from",
    "effective_to": "audit.field.effective_to",
    "start_date": "audit.field.start_date",
    "end_date": "audit.field.end_date",
    "year_month": "audit.field.year_month",
    "region_id": "audit.field.region",
    "project_id": "audit.field.project",
    "department_id": "audit.field.department",
    "position_ids": "audit.field.positions",
    "payroll_group": "audit.field.payroll_group",
    "workweek_days": "employee.workweek_days",
    "salary_basis": "audit.field.salary_basis",
    "monthly_pay_method": "employee.monthly_pay_method",
    "currency": "audit.field.currency",
    "amount": "audit.field.amount",
    "label": "audit.field.label",
    "allowance_type": "audit.field.allowance_type",
    "exchange_rate": "audit.field.exchange_rate",
    "identity_type": "audit.field.identity_type",
    "identity_number": "audit.field.identity_number",
    "certificate_type_id": "audit.field.certificate_type",
    "certificate_no": "audit.field.certificate_no",
    "visa_category_id": "audit.field.visa_category",
    "visa_no": "audit.field.visa_no",
    "qualification_name": "audit.field.qualification_name",
    "chinese_name": "audit.field.chinese_name",
    "english_name": "audit.field.english_name",
    "gender": "audit.field.gender",
    "date_of_birth": "audit.field.date_of_birth",
    "mobile": "audit.field.mobile",
    "email": "audit.field.email",
    "address": "audit.field.address",
    "emergency_contact_name": "audit.field.emergency_contact",
    "emergency_contact_phone": "audit.field.emergency_phone",
    "emergency_contact_relation": "audit.field.emergency_relation",
    "education_level": "audit.field.education_level",
    "major": "audit.field.major",
    "graduation_school": "audit.field.graduation_school",
    "visa_required": "audit.field.visa_required",
    "remarks": "audit.field.remarks",
    "issue_date": "audit.field.issue_date",
    "expiry_date": "audit.field.expiry_date",
    "is_long_term": "audit.field.is_long_term",
    "is_primary": "audit.field.is_primary",
    "probation_end_date": "audit.field.probation_end_date",
    "contract_annual_leave_days": "contract.annual_leave",
    "confirmation_date": "audit.field.confirmation_date",
    "status": "audit.field.status",
    "termination_reason": "audit.field.termination_reason",
    "average_wage": "audit.field.average_wage",
    "payment_in_lieu": "audit.field.payment_in_lieu",
    "severance_payment": "audit.field.severance_payment",
    "long_service_payment": "audit.field.long_service_payment",
}


AUDIT_OPTION_CATEGORIES = {
    "identity_type": "identity_type",
    "payroll_group": "payroll_group",
    "salary_basis": "salary_basis",
    "monthly_pay_method": "monthly_pay_method",
    "status": "document_status",
    "termination_reason": "termination_reason",
}


AUDIT_REFERENCE_FIELDS = {
    "region_id",
    "department_id",
    "certificate_type_id",
    "visa_category_id",
}


def audit_value(field, value):
    if value in (None, ""):
        return None
    if field == "project_id":
        project = db.session.get(WorkProject, int(value))
        return project.name if project else str(value)
    if field in AUDIT_REFERENCE_FIELDS:
        reference = db.session.get(ReferenceValue, int(value))
        return reference.display_name if reference else str(value)
    if field == "position_ids":
        values = value if isinstance(value, list) else [value]
        names = []
        for item in values:
            reference = db.session.get(ReferenceValue, int(item))
            names.append(reference.display_name if reference else str(item))
        return "、".join(names)
    if field.endswith("_document_id") or field == "document_id":
        document = db.session.get(EmployeeDocument, int(value))
        return document.original_filename if document else str(value)
    if isinstance(value, bool):
        return value
    return str(value)


def audit_change_rows(log):
    before = log.before_json or {}
    after = log.after_json or {}
    rows = []
    for field, label_key in AUDIT_FIELD_LABELS.items():
        if field not in before and field not in after:
            continue
        old_value = before.get(field)
        new_value = after.get(field)
        if old_value == new_value:
            continue
        rows.append(
            {
                "label_key": label_key,
                "before": audit_value(field, old_value),
                "after": audit_value(field, new_value),
                "option_category": AUDIT_OPTION_CATEGORIES.get(field),
                "is_boolean": isinstance(old_value, bool)
                or isinstance(new_value, bool),
            }
        )
    return rows


def build_change_history(employee):
    entity_kinds = {
        "EmployeeAssignment": "employment",
        "EmployeeSalary": "salary",
        "EmployeeMpfEnrollment": "mpf",
        "EmployeeAllowance": "allowance",
        "EmployeeEmploymentPeriod": "employment_status",
    }
    audits_by_record = {}
    logs = AuditLog.query.filter_by(employee_id=employee.id).filter(
        AuditLog.entity_type.in_(entity_kinds)
    ).order_by(AuditLog.created_at.desc())
    for log in logs:
        if log.entity_id is None:
            continue
        audits_by_record.setdefault((log.entity_type, log.entity_id), []).append(
            {
                "date": audit_entry(log)["date"],
                "title": log.action,
                "detail": log.detail or "",
                "changes": audit_change_rows(log),
                "author": log.user.username if log.user else "system",
            }
        )

    records = []
    groups = (
        ("employment", "EmployeeAssignment", employee.assignments),
        ("salary", "EmployeeSalary", employee.salaries),
        ("mpf", "EmployeeMpfEnrollment", employee.mpf_enrollments),
        ("allowance", "EmployeeAllowance", employee.allowances),
        ("employment_status", "EmployeeEmploymentPeriod", employee.employment_periods),
    )
    for kind, entity_type, items in groups:
        for item in items:
            records.append(
                {
                    "kind": kind,
                    "record": item,
                    "audits": audits_by_record.get((entity_type, item.id), []),
                }
            )
    kind_order = {
        "employment": 0,
        "salary": 1,
        "mpf": 2,
        "allowance": 3,
        "employment_status": 4,
    }

    def _history_date(item):
        rec = item["record"]
        if item["kind"] == "employment_status":
            return rec.start_date or date.min
        return rec.effective_from or date.min

    records.sort(
        key=lambda item: (
            _history_date(item),
            -kind_order[item["kind"]],
        ),
        reverse=True,
    )
    return records


def audit_entry(log):
    from hkr_hr.platform.dates import hong_kong_datetime
    return {
        "date": hong_kong_datetime(log.created_at),
        "title": log.action,
        "detail": log.detail or "",
        "changes": audit_change_rows(log),
        "author": log.user.username if log.user else "system",
    }


def audits_for_records(employee, entity_types):
    grouped = {}
    logs = (
        AuditLog.query.filter_by(employee_id=employee.id)
        .filter(AuditLog.entity_type.in_(entity_types))
        .order_by(AuditLog.created_at.desc())
        .all()
    )
    for log in logs:
        if log.entity_id is not None:
            grouped.setdefault((log.entity_type, log.entity_id), []).append(
                audit_entry(log)
            )
    return grouped


def build_personal_history(employee):
    grouped = audits_for_records(employee, {"EmployeeBankAccount"})
    entries = [
        {
            "kind": "bank",
            "record": account,
            "sort_at": datetime.combine(account.effective_from, datetime.min.time()),
            "audits": grouped.get(("EmployeeBankAccount", account.id), []),
        }
        for account in employee.bank_accounts
    ]
    logs = (
        AuditLog.query.filter_by(employee_id=employee.id, entity_type="Employee")
        .filter(
            AuditLog.action.in_(
                {"employee_created", "personal_data_updated", "employee_name_updated"}
            )
        )
        .order_by(AuditLog.created_at.desc())
        .all()
    )
    entries.extend(
        {
            "kind": "profile",
            "record": None,
            "sort_at": log.created_at,
            "audits": [audit_entry(log)],
        }
        for log in logs
    )
    entries.sort(key=lambda entry: entry["sort_at"], reverse=True)
    return entries


def credential_record_date(record):
    for field in ("issue_date", "valid_from", "expiry_date"):
        value = getattr(record, field, None)
        if value:
            return value
    return record.created_at.date()


def build_credential_history(employee):
    entity_kinds = {
        "EmployeeIdentity": "identity",
        "EmployeeCertificate": "certificate",
        "EmployeeVisa": "visa",
        "EmployeeQualification": "qualification",
    }
    grouped = audits_for_records(employee, set(entity_kinds))
    groups = (
        ("identity", "EmployeeIdentity", employee.identities),
        ("certificate", "EmployeeCertificate", employee.certificates),
        ("visa", "EmployeeVisa", employee.visas),
        ("qualification", "EmployeeQualification", employee.qualifications),
    )
    entries = []
    for kind, entity_type, records in groups:
        for record in records:
            entries.append(
                {
                    "kind": kind,
                    "record": record,
                    "sort_at": datetime.combine(
                        credential_record_date(record), datetime.min.time()
                    ),
                    "audits": grouped.get((entity_type, record.id), []),
                }
            )
    profile_logs = (
        AuditLog.query.filter_by(employee_id=employee.id, entity_type="Employee")
        .filter(
            AuditLog.action.in_(
                {"education_background_updated", "visa_requirement_updated"}
            )
        )
        .order_by(AuditLog.created_at.desc())
        .all()
    )
    entries.extend(
        {
            "kind": (
                "education"
                if log.action == "education_background_updated"
                else "visa_requirement"
            ),
            "record": None,
            "sort_at": log.created_at,
            "audits": [audit_entry(log)],
        }
        for log in profile_logs
    )
    entries.sort(key=lambda entry: entry["sort_at"], reverse=True)
    return entries


def build_employment_status_history(employee):
    grouped = audits_for_records(employee, {"EmployeeEmploymentPeriod"})
    entries = [
        {
            "record": period,
            "sort_at": datetime.combine(period.start_date, datetime.min.time()),
            "audits": grouped.get(("EmployeeEmploymentPeriod", period.id), []),
        }
        for period in employee.employment_periods
    ]
    entries.sort(key=lambda entry: entry["sort_at"], reverse=True)
    return entries


def employee_query():
    query = Employee.query
    search = request.args.get("q", "").strip()
    if search:
        fields = (
            Employee.employee_no,
            Employee.chinese_name,
            Employee.english_name,
            Employee.mobile_number,
            Employee.email,
        )
        query = query.filter(
            or_(
                *(
                    field.ilike(f"%{variant}%")
                    for variant in chinese_search_variants(search)
                    for field in fields
                )
            )
        )
    payroll_group = request.args.get("payroll_group", "")
    if payroll_group:
        query = query.filter(Employee.payroll_group == payroll_group)
    employee_type_id = request.args.get("employee_type_id", type=int)
    if employee_type_id:
        query = query.filter(Employee.employee_type_id == employee_type_id)
    project_id = request.args.get("project_id", type=int)
    if project_id:
        query = query.filter(
            Employee.assignments.any(
                EmployeeAssignment.project_id == project_id
            )
        )
    return query.order_by(Employee.employee_no.asc())

