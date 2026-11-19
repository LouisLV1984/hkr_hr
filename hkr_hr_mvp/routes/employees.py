from tools.payroll_review import originating_payroll, salary_gaps
from tools.employee_loading import workbench_options
from tools.hr_core import valid_salary_amount
from tools.profile_revision import profile_revision
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
from tools.absence_integrity import conflicting_absence
from tools.profile_integrity import active_successor, credential_form_validation, credential_state, identity_conflict, renewal_source

from models import (
    AttendanceCorrection,
    AuditLog,
    AttendanceBatch,
    AttendanceMonthlySummary,
    AttendanceBatchItem,
    Employee,
    EmployeeAnnualLeaveBalance,
    EmployeeAnnualLeaveRecord,
    EmployeeAllowance,
    EmployeeCompLeaveCredit,
    EmployeeAssignment,
    EmployeeAssignmentPosition,
    EmployeeBankAccount,
    EmployeeCertificate,
    EmployeeDocument,
    EmployeeEmploymentPeriod,
    EmployeeIdentity,
    EmployeeMpfEnrollment,
    EmployeeQualification,
    EmployeeSalary,
    EmployeeWorkInjuryPeriod,
    EmployeeWorkInjuryMonthlyExpense,
    EmployeeVisa,
    GeneratedContract,
    MpfScheme,
    PayrollAdjustment,
    PayrollEmployeeResult,
    PayrollRun,
    ReferenceValue,
    WorkProject,
    db,
)
from tools.completeness import employee_data_items, employee_readiness, missing_employee_data_labels, mpf_data_item
from tools.attendance_policy import (
    attendance_required,
    policy_on,
    set_long_term_attendance_policy,
)
from tools.hr_core import (
    DOCUMENT_CATEGORIES,
    IDENTITY_TYPE_OPTIONS,
    PAYROLL_GROUPS,
    TERMINATION_REASONS,
    annual_leave_summary,
    annual_leave_days_between,
    allocate_annual_leave_with_comp,
    average_wage_prefill,
    create_assignment,
    create_mpf_enrollment,
    create_salary,
    clear_leave_allocations,
    comp_leave_summary,
    current_assignment_on,
    current_bank_account_on,
    current_mpf_on,
    current_salary_on,
    current_month,
    delete_employee_files,
    employee_files_path,
    employee_audit_snapshot,
    ensure_current_employment_period,
    file_sha256,
    format_money,
    masked_bank_account,
    next_employee_no,
    normalize_identity_number,
    normalize_workweek_days,
    parse_bool,
    parse_date,
    parse_decimal,
    parse_year_month,
    reference_map,
    reference_options,
    rebuild_effective_ranges,
    REPLACEMENT_REASONS,
    set_annual_leave_allocations,
    store_employee_file,
    termination_estimate,
    uploaded_file_sha256,
    write_audit,
)
from tools.payroll_engine import calculate_employee, calculate_payroll
from tools.text_search import chinese_search_variants


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


@employees_bp.route("/annual-leave/<int:record_id>/evidence", methods=["POST"])
@login_required
def supplement_leave_evidence(record_id):
    record = db.get_or_404(EmployeeAnnualLeaveRecord, record_id)
    if record.status != "active":
        abort(400)
    uploaded = request.files.get("evidence")
    if not uploaded or not uploaded.filename:
        flash("profile.select_evidence", "error")
        return annual_leave_redirect(record.employee_id, record.entitlement_year)
    before = {"evidence_document_id": record.evidence_document_id}
    document = replace_record_evidence(record.employee, record.evidence_document,
                                       uploaded, "change_evidence", "假期憑證")
    if not document:
        return annual_leave_redirect(record.employee_id, record.entitlement_year)
    record.evidence_document_id = document.id
    # Payroll uses the leave revision time to decide whether attendance needs
    # another review. The document and audit carry the time of this upload.
    record.updated_at = EmployeeAnnualLeaveRecord.updated_at
    write_audit("leave_evidence_added", "EmployeeAnnualLeaveRecord", record.id,
                employee_id=record.employee_id, detail="補交假期憑證（不改動假期日期及日數）",
                before=before, after={"evidence_document_id": document.id})
    db.session.commit()
    flash("profile.evidence_saved", "success")
    return annual_leave_redirect(record.employee_id, record.entitlement_year)


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
    from tools.profile_integrity import document_reference_count
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
    from tools.datetime_utils import hong_kong_datetime
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


@employees_bp.route("/api/employees/next-no")
@login_required
def api_next_employee_no():
    employee_type = db.session.get(ReferenceValue, request.args.get("employee_type_id", type=int))
    if not employee_type:
        return {"employee_no": ""}
    return {"employee_no": next_employee_no(employee_type)}


@employees_bp.route("/employees")
@login_required
def list_employees():
    year_month = request.args.get("month") or session.get("operating_month") or current_month()
    try:
        month_start, month_end = parse_year_month(year_month)
    except (TypeError, ValueError):
        year_month = current_month()
        month_start, month_end = parse_year_month(year_month)
    session["operating_month"] = year_month
    session["employee_list_url"] = request.full_path.rstrip("?")
    employees = employee_query().options(*workbench_options()).all()
    status = request.args.get("status", "active")
    if status in {"active", "departed"}:
        employees = [
            employee
            for employee in employees
            if employee.derived_status == status
        ]
    readiness_filter = request.args.get("readiness", "")
    impact_filter = request.args.get("impact", "")
    monthly_view = readiness_filter in {"needs_action", "attendance", "payroll"} or bool(impact_filter)
    impact_counts = {}
    if monthly_view:
        summaries = {
            row.employee_id: row
            for row in AttendanceMonthlySummary.query.filter_by(
                year_month=year_month,
            ).all()
        }
        payroll_rows = {
            row["employee"].id: row
            for row in calculate_payroll(year_month, "all")
        }
        readiness_rows = [
            employee_readiness(
                employee,
                year_month,
                payroll_row=payroll_rows.get(employee.id),
                summary=summaries.get(employee.id),
                in_scope=employee.employed_during(month_start, month_end),
            )
            for employee in employees
        ]
        for row in readiness_rows:
            for item in row["payroll"]:
                target = {"薪酬未設定": ("employment", "salary"), "出糧銀行資料未填寫": ("personal", "bank"), "日工暫不支持固定補貼，請先撤回補貼記錄": ("employment", "allowance")}.get(item.get("label"))
                if target:
                    item["action_url"] = url_for("employees.view_employee", employee_id=row["employee"].id, tab=target[0], focus=target[1])
            summary = summaries.get(row["employee"].id)
            row["attendance_url"] = url_for("attendance.attendance_home", month=year_month, view="collection", employee_id=row["employee"].id, **({"summary_id": summary.id} if summary else {}))
        readiness_rows.sort(key=lambda row: (not any(not i["ok"] for i in row["payroll"]), row["attendance"]["ok"], row["employee"].employee_no))
        document_codes = {
            "staff_record",
            "signed_contract",
            "three_treasures",
            "visa",
            "sick_evidence",
        }
        impact_counts = {
            "payroll": 0,
            "leave": 0,
            "mpf": 0,
            "documents": 0,
        }
        for row in readiness_rows:
            missing_codes = {
                item["code"] for item in row["employee_data"] if not item["ok"]
            }
            row["impact"] = {
                "payroll": (
                    not row["attendance"]["ok"]
                    or any(not item["ok"] for item in row["payroll"])
                ),
                "leave": "employment" in missing_codes,
                "mpf": "mpf" in missing_codes,
                "documents": bool(missing_codes & document_codes),
            }
            for code, affected in row["impact"].items():
                if affected:
                    impact_counts[code] += 1
        if readiness_filter == "needs_action":
            readiness_rows = [row for row in readiness_rows if row["has_issue"]]
        elif readiness_filter == "attendance":
            readiness_rows = [
                row for row in readiness_rows if not row["attendance"]["ok"]
            ]
        elif readiness_filter == "payroll":
            readiness_rows = [
                row
                for row in readiness_rows
                if any(not item["ok"] for item in row["payroll"])
            ]
        if impact_filter in impact_counts:
            readiness_rows = [
                row for row in readiness_rows if row["impact"][impact_filter]
            ]
    else:
        readiness_rows = []
        for employee in sorted(employees, key=lambda person: person.employee_no):
            data = employee_data_items(employee)
            if employee.employed_during(month_start, month_end):
                data.append(mpf_data_item(employee, month_end))
            readiness_rows.append({"employee": employee, "employee_data": data})
    if readiness_filter == "employee_data":
        readiness_rows = [row for row in readiness_rows if any(not item["ok"] for item in row["employee_data"])]
    group_by = "position" if request.args.get("group_by") == "position" else "department"
    directory_groups = {}
    for row in readiness_rows:
        assignment = row["employee"].current_assignment
        group = (assignment.primary_position if group_by == "position" else assignment.department) if assignment else None
        directory_groups.setdefault(group.display_name if group else "", []).append(row)
    return render_template(
        "employees/list.html",
        readiness_rows=readiness_rows, group_by=group_by,
        directory_groups=sorted(directory_groups.items(), key=lambda pair: (not pair[0], pair[0].casefold())),
        year_month=year_month,
        readiness_filter=readiness_filter,
        impact_filter=impact_filter,
        impact_counts=impact_counts,
        employee_types=reference_options("employee_type"),
        projects=WorkProject.query.filter_by(active=True).order_by(
            WorkProject.name
        ).all(),
        payroll_groups=PAYROLL_GROUPS,
    )


@employees_bp.route("/employees/new", methods=["GET", "POST"])
@login_required
def new_employee():
    employee_types = reference_options("employee_type")
    if request.method == "POST":
        chinese_name = request.form.get("chinese_name", "").strip() or None
        english_name = request.form.get("english_name", "").strip() or None
        employee_type = db.session.get(
            ReferenceValue,
            form_int("employee_type_id"),
        )
        payroll_group = request.form.get("payroll_group", "").strip()
        if not (chinese_name or english_name):
            flash("中文名或英文名至少填寫一項。", "error")
        elif not employee_type:
            flash("請選擇員工編號類別。", "error")
        elif payroll_group not in {item[0] for item in PAYROLL_GROUPS}:
            flash("請選擇薪酬組別。", "error")
        else:
            employee = Employee(
                employee_no=next_employee_no(employee_type),
                employee_type=employee_type,
                payroll_group=payroll_group,
                chinese_name=chinese_name,
                english_name=english_name,
                status="active",
            )
            db.session.add(employee)
            db.session.flush()
            if request.form.get("requires_attendance", "1") == "0":
                db.session.add(
                    set_long_term_attendance_policy(
                        employee,
                        current_month(),
                        False,
                        created_by=current_user.id,
                        remarks="建立員工檔案時設定長期免交考勤",
                    )
                )
            write_audit(
                "employee_created",
                "Employee",
                employee.id,
                employee_id=employee.id,
                detail=f"建立員工檔案 {employee.employee_no}",
                after=employee_audit_snapshot(employee),
            )
            db.session.commit()
            flash("員工檔案已建立。", "success")
            return redirect(url_for("employees.view_employee", employee_id=employee.id))
    return render_template(
        "employees/new.html",
        employee_types=employee_types,
        payroll_groups=PAYROLL_GROUPS,
    )



@employees_bp.post("/employees/<int:employee_id>/initial-setup")
@login_required
def initial_setup(employee_id):
    """Fill missing initial records in one transaction using the existing owners."""
    employee = db.get_or_404(Employee, employee_id)
    effective = parse_date(request.form.get("effective_from"))
    amount = parse_decimal(request.form.get("amount"))
    basis = request.form.get("salary_basis", "daily" if employee.payroll_group == "site_daily" else "monthly")
    method = request.form.get("monthly_pay_method") or "full_month"
    bank_name = request.form.get("bank_name", "").strip()
    bank_no = request.form.get("account_no", "").strip()
    currency = request.form.get("currency") or "HKD"
    try:
        if not effective:
            raise ValueError("請填寫入職／初始生效日期。")
        if not employee.salaries and (not valid_salary_amount(amount) or basis not in {"monthly", "daily"} or method not in {"full_month", "attendance_days"}):
            raise ValueError("請完整填寫薪酬類型及金額。")
        if not employee.bank_accounts and bool(bank_name) != bool(bank_no):
            raise ValueError("銀行名稱及戶口號碼請一起填寫，或稍後補齊。")
        mpf_values = requested_mpf_values() if not employee.mpf_enrollments and (request.form.get("mpf_selection") or request.form.get("mpf_exempt")) else None
    except ValueError as exc:
        flash(str(exc), "error")
        return employee_redirect(employee.id, "overview")
    initial_leave = parse_decimal(request.form.get("initial_leave_days") or "7")
    if not employee.employment_periods:
        from tools.annual_leave_setup import validate
        try:
            validate(effective, initial_leave)
        except ValueError:
            flash("leave.setup_invalid", "error")
            return employee_redirect(employee.id, "overview")
    created = []
    if not employee.employment_periods:
        period = EmployeeEmploymentPeriod(employee=employee, start_date=effective, contract_annual_leave_days=initial_leave, annual_leave_policy_year=date.today().year, annual_leave_contract_verified=False)
        db.session.add(period)
        created.append(("EmployeeEmploymentPeriod", period, {"start_date": effective.isoformat()}))
    if not employee.assignments:
        assignment = create_assignment(employee, effective, employee.payroll_group,
            workweek_days=request.form.get("workweek_days"),
            region_id=form_int("region_id"), project_id=form_int("project_id"),
            department_id=form_int("department_id"), employer_id=form_int("employer_id"),
            payroll_entity_id=form_int("payroll_entity_id"),
            position_ids=[int(i) for i in request.form.getlist("position_ids") if str(i).isdigit()])
        created.append(("EmployeeAssignment", assignment, assignment_snapshot(assignment)))
    if not employee.salaries:
        salary = create_salary(employee, effective, basis, currency, amount, monthly_pay_method=method)
        created.append(("EmployeeSalary", salary, salary_snapshot(salary)))
    if not employee.bank_accounts and bank_name and bank_no:
        account = EmployeeBankAccount(employee=employee, effective_from=effective, bank_name=bank_name, account_no=bank_no, currency=currency, status="active")
        db.session.add(account)
        db.session.flush()
        sync_legacy_bank_fields(employee)
        created.append(("EmployeeBankAccount", account, bank_account_snapshot(account)))
    if mpf_values:
        _, scheme, member, mode = mpf_values
        mpf = create_mpf_enrollment(employee, effective, scheme=scheme, member_account_no=member, contribution_mode=mode)
        created.append(("EmployeeMpfEnrollment", mpf, mpf_snapshot(mpf)))
    db.session.flush()
    if any(name == "EmployeeEmploymentPeriod" for name, _, _ in created):
        from tools.annual_leave_policy import save_current_balance
        balance = save_current_balance(employee)
        write_audit("annual_leave_balance_updated", "EmployeeAnnualLeaveBalance", balance.id,
                    employee_id=employee.id, detail="初始任職建立本年度年假",
                    after={"initial_days": str(initial_leave), "applied": str(balance.calculated_entitled_days)})
    for model_name, record, after in created:
        write_audit("initial_setup", model_name, record.id, employee_id=employee.id, before=None, after=after)
    db.session.commit()
    flash("入職資料已保存。", "success")
    return employee_redirect(employee.id, "overview")

@employees_bp.route("/employees/<int:employee_id>")
@login_required
def view_employee(employee_id):
    from tools.leave_review import review_rows
    employee = db.get_or_404(Employee, employee_id)
    refs = reference_map()
    attendance_rows = AttendanceMonthlySummary.query.filter_by(
        employee_id=employee.id
    ).order_by(AttendanceMonthlySummary.year_month.desc()).all()
    payroll_by_month = {}
    payroll_results = (
        PayrollEmployeeResult.query.join(PayrollRun)
        .filter(PayrollEmployeeResult.employee_id == employee.id)
        .order_by(
            PayrollRun.year_month.desc(),
            PayrollRun.created_at.desc(),
            PayrollRun.id.desc(),
            PayrollEmployeeResult.id.desc(),
        )
        .all()
    )
    for result in payroll_results:
        payroll_by_month.setdefault(result.run.year_month, result)
    corrections_by_month = {}
    for record in AttendanceCorrection.query.filter_by(employee_id=employee.id).order_by(AttendanceCorrection.source_month):
        corrections_by_month.setdefault(record.pay_month, []).append(record)
    extra_months = sorted((payroll_by_month.keys() | corrections_by_month.keys()) -
                          {item.year_month for item in attendance_rows}, reverse=True)
    current_bank = current_bank_account_on(employee, date.today())
    document_management_tabs = {
        document.id: document_management_tab(document)
        for document in employee.documents
    }
    hash_counts = {}
    for document in employee.documents:
        if document.status == "active" and document.content_sha256:
            hash_counts[document.content_sha256] = hash_counts.get(document.content_sha256, 0) + 1
    shared_document_hashes = {digest for digest, count in hash_counts.items() if count > 1}
    pay_month = request.args.get("pay_month", "")
    payroll_return = originating_payroll(request.args, pay_month)
    pay_assignment = None
    salary_dates = []
    if payroll_return:
        _, pay_end = parse_year_month(pay_month)
        pay_assignment = current_assignment_on(employee, pay_end)
        if request.args.get("focus") == "salary":
            pay_summary = calculate_employee(employee, pay_month).get("attendance")
            salary_dates = salary_gaps(employee, pay_summary)
    return render_template(
        "employees/detail.html",
        payroll_return=payroll_return, pay_assignment=pay_assignment, salary_dates=salary_dates,
        active_successor=active_successor, credential_state=credential_state,
        leave_review_count=len(review_rows(employee.id)[0]),
        employee=employee,
        today=date.today(),
        refs=refs,
        projects=WorkProject.query.filter_by(active=True).order_by(
            WorkProject.name
        ).all(),
        payroll_groups=PAYROLL_GROUPS,
        mpf_schemes=MpfScheme.query.filter_by(active=True).order_by(
            MpfScheme.name
        ).all(),
        identity_types=IDENTITY_TYPE_OPTIONS,
        termination_reasons=TERMINATION_REASONS,
        change_history=build_change_history(employee),
        personal_history=build_personal_history(employee),
        credential_history=build_credential_history(employee),
        employment_status_history=build_employment_status_history(employee),
        missing=missing_employee_data_labels(employee),
        missing_items=[
            item for item in employee_data_items(employee) if not item["ok"]
        ],
        leave=annual_leave_summary(employee),
        comp_leave=comp_leave_summary(employee),
        leave_records=EmployeeAnnualLeaveRecord.query.filter_by(
            employee_id=employee.id
        ).order_by(
            EmployeeAnnualLeaveRecord.leave_date.desc(),
            EmployeeAnnualLeaveRecord.id.desc(),
        ).all(),
        work_injury_periods=EmployeeWorkInjuryPeriod.query.filter_by(
            employee_id=employee.id
        ).order_by(
            EmployeeWorkInjuryPeriod.payroll_start_date.desc(),
            EmployeeWorkInjuryPeriod.id.desc(),
        ).all(),
        allowances=EmployeeAllowance.query.filter_by(
            employee_id=employee.id
        ).order_by(
            EmployeeAllowance.effective_from.desc(),
            EmployeeAllowance.id.desc(),
        ).all(),
        average_wage=average_wage_prefill(employee),
        current_bank=current_bank,
        bank_accounts=EmployeeBankAccount.query.filter_by(
            employee_id=employee.id
        ).order_by(
            EmployeeBankAccount.effective_from.desc(),
            EmployeeBankAccount.id.desc(),
        ).all(),
        masked_bank=masked_bank_account(
            current_bank.account_no if current_bank else employee.bank_account_no
        ),
        contracts=GeneratedContract.query.filter_by(employee_id=employee.id)
        .order_by(GeneratedContract.created_at.desc())
        .all(),
        attendance=attendance_rows,
        payroll_by_month=payroll_by_month, corrections_by_month=corrections_by_month, extra_months=extra_months,
        payroll_adjustments=PayrollAdjustment.query.filter_by(
            employee_id=employee.id
        ).order_by(
            PayrollAdjustment.year_month.desc(),
            PayrollAdjustment.id.desc(),
        ).all(),
        default_payroll_month=current_month(),
        attendance_required_now=attendance_required(
            employee,
            current_month(),
        ),
        attendance_policy=policy_on(employee.id, current_month()),
        document_categories={**DOCUMENT_CATEGORIES, "credential": "證件"},
        certificate_files={c.document_id: c.certificate_type.display_name for c in employee.certificates
                           if c.document_id and c.document and c.document.category == "qualification"
                           and c.certificate_type.code not in {"DEGREE", "SKILL"}},
        replacement_reasons=REPLACEMENT_REASONS,
        document_management_tabs=document_management_tabs,
        shared_document_hashes=shared_document_hashes,
    )


@employees_bp.route("/employees/<int:employee_id>/personal", methods=["POST"])
@login_required
def update_personal(employee_id):
    employee = Employee.query.filter_by(id=employee_id).with_for_update().populate_existing().first_or_404()
    scope = request.form.get("form_scope", "all")
    if scope not in {"all", "profile", "education", "visa_requirement", "attendance_policy"}:
        abort(400)
    if not hmac.compare_digest(request.form.get("profile_revision", "").encode(), profile_revision(employee, scope).encode()):
        db.session.rollback()
        flash("review.profile_conflict", "error")
        return employee_redirect(employee_id, "personal")
    before = employee_audit_snapshot(employee)
    previous_attendance_required = attendance_required(
        employee,
        current_month(),
    )
    if scope in {"all", "profile"}:
        employee.gender = request.form.get("gender") or None
        employee.date_of_birth = parse_date(request.form.get("date_of_birth"))
        employee.mobile_region_code = request.form.get("mobile_region_code") or None
        employee.mobile_number = request.form.get("mobile_number", "").strip() or None
        employee.email = request.form.get("email", "").strip() or None
        employee.residential_address = (
            request.form.get("residential_address", "").strip() or None
        )
        employee.emergency_contact_name = (
            request.form.get("emergency_contact_name", "").strip() or None
        )
        employee.emergency_contact_region_code = (
            request.form.get("emergency_contact_region_code") or None
        )
        employee.emergency_contact_phone = (
            request.form.get("emergency_contact_phone", "").strip() or None
        )
        employee.emergency_contact_relation = (
            request.form.get("emergency_contact_relation", "").strip() or None
        )
        employee.remarks = request.form.get("remarks", "").strip() or None
    if scope == "all" and (
        "bank_name" in request.form or "bank_account_no" in request.form
    ):
        bank_name = request.form.get("bank_name", "").strip()
        account_no = request.form.get("bank_account_no", "").strip()
        if bank_name and account_no:
            current_bank = current_bank_account_on(employee, date.today())
            if not current_bank:
                current_bank = EmployeeBankAccount(
                    employee=employee,
                    effective_from=(
                        employee.current_period.start_date
                        if employee.current_period
                        else date.today()
                    ),
                    bank_name=bank_name,
                    account_no=account_no,
                    currency="HKD",
                    status="active",
                )
                db.session.add(current_bank)
                db.session.flush()
            else:
                current_bank.bank_name = bank_name
                current_bank.account_no = account_no
            rebuild_effective_ranges(employee.bank_accounts)
            sync_legacy_bank_fields(employee)
    if scope in {"all", "education"}:
        employee.education_level = request.form.get("education_level") or None
        employee.major = request.form.get("major", "").strip() or None
        employee.graduation_school = (
            request.form.get("graduation_school", "").strip() or None
        )
    if scope in {"all", "visa_requirement"}:
        employee.visa_required = parse_bool(request.form.get("visa_required"))
    requested_attendance_required = (
        request.form.get("requires_attendance") == "1"
        if "requires_attendance" in request.form
        else previous_attendance_required
    )
    if scope in {"all", "attendance_policy"} and (
        requested_attendance_required != previous_attendance_required
    ):
        db.session.add(
            set_long_term_attendance_policy(
                employee,
                current_month(),
                requested_attendance_required,
                created_by=current_user.id,
                remarks="由員工檔案更新每月考勤要求",
            )
        )
        write_audit(
            "attendance_policy_required"
            if requested_attendance_required
            else "attendance_policy_exempted",
            "EmployeeAttendancePolicy",
            employee_id=employee.id,
            detail=(
                f"自 {current_month()} 起需要每月考勤"
                if requested_attendance_required
                else f"自 {current_month()} 起長期免交考勤"
            ),
            before={"requires_attendance": previous_attendance_required},
            after={"requires_attendance": requested_attendance_required},
        )
    after = employee_audit_snapshot(employee)
    if before != after:
        action = {
            "education": "education_background_updated",
            "visa_requirement": "visa_requirement_updated",
        }.get(scope, "personal_data_updated")
        detail = {
            "profile": "更新個人資料",
            "education": "更新教育背景",
            "visa_requirement": "更新工作許可要求",
            "attendance_policy": "更新每月考勤要求",
        }.get(scope, "更新個人資料")
        write_audit(
            action,
            "Employee",
            employee.id,
            employee_id=employee.id,
            detail=detail,
            before=before,
            after=after,
        )
    db.session.commit()
    flash(
        {
            "education": "教育背景已保存。",
            "visa_requirement": "工作許可要求已保存。",
            "attendance_policy": "每月考勤要求已保存。",
        }.get(scope, "個人資料已保存。"),
        "success",
    )
    return employee_redirect(
        employee.id,
        "credentials"
        if scope in {"education", "visa_requirement"}
        else "employment"
        if scope == "attendance_policy"
        else "personal",
    )


@employees_bp.route("/employees/<int:employee_id>/bank-accounts", methods=["POST"])
@login_required
def add_bank_account(employee_id):
    employee = db.get_or_404(Employee, employee_id)
    effective_from = parse_date(request.form.get("effective_from"))
    bank_name = request.form.get("bank_name", "").strip()
    account_no = request.form.get("account_no", "").strip()
    if not effective_from or not bank_name or not account_no:
        flash("請填寫生效日期、銀行及賬戶號碼。", "error")
        return employee_redirect(employee.id, "personal")
    evidence = save_evidence(
        employee,
        request.files.get("evidence"),
        "bank_proof",
        "銀行賬戶證明",
    )
    account = EmployeeBankAccount(
        employee=employee,
        effective_from=effective_from,
        bank_name=bank_name,
        account_no=account_no,
        currency=(request.form.get("currency", "HKD").strip() or "HKD").upper(),
        evidence_document=evidence,
        status="active",
        remarks=request.form.get("remarks", "").strip() or None,
    )
    db.session.add(account)
    db.session.flush()
    rebuild_effective_ranges(employee.bank_accounts)
    sync_legacy_bank_fields(employee)
    write_audit(
        "bank_account_added",
        "EmployeeBankAccount",
        account.id,
        employee_id=employee.id,
        detail=f"銀行賬戶由 {effective_from:%Y-%m-%d} 生效",
        after=bank_account_snapshot(account),
    )
    db.session.commit()
    flash("銀行賬戶記錄已新增。", "success")
    return employee_redirect(employee.id, "personal", saved=True)


@employees_bp.route("/bank-accounts/<int:account_id>/correct", methods=["POST"])
@login_required
def correct_bank_account(account_id):
    account = db.get_or_404(EmployeeBankAccount, account_id)
    before = bank_account_snapshot(account)
    effective_from = parse_date(request.form.get("effective_from"))
    bank_name = request.form.get("bank_name", "").strip()
    account_no = request.form.get("account_no", "").strip()
    if not effective_from or not bank_name or not account_no:
        flash("請填寫生效日期、銀行及賬戶號碼。", "error")
        return employee_redirect(account.employee_id, "personal")
    account.effective_from = effective_from
    account.bank_name = bank_name
    account.account_no = account_no
    account.currency = (request.form.get("currency", "HKD").strip() or "HKD").upper()
    account.remarks = request.form.get("remarks", "").strip() or None
    account.evidence_document = replace_record_evidence(
        account.employee,
        account.evidence_document,
        request.files.get("evidence"),
        "bank_proof",
        "銀行賬戶證明",
        "更正銀行賬戶證明",
    )
    rebuild_effective_ranges(account.employee.bank_accounts)
    sync_legacy_bank_fields(account.employee)
    write_audit(
        "bank_account_corrected",
        "EmployeeBankAccount",
        account.id,
        employee_id=account.employee_id,
        detail="更正銀行賬戶記錄",
        before=before,
        after=bank_account_snapshot(account),
    )
    db.session.commit()
    flash("銀行賬戶記錄已更正；舊附件仍保留在附件歷史。", "success")
    return employee_redirect(account.employee_id, "personal")


@employees_bp.route("/bank-accounts/<int:account_id>/withdraw", methods=["POST"])
@login_required
def withdraw_bank_account(account_id):
    account = db.get_or_404(EmployeeBankAccount, account_id)
    if account.status != "active":
        return employee_redirect(account.employee_id, "personal")
    before = bank_account_snapshot(account)
    account.status = "voided"
    account.remarks = request.form.get("reason", "").strip() or account.remarks
    rebuild_effective_ranges(account.employee.bank_accounts)
    sync_legacy_bank_fields(account.employee)
    write_audit(
        "bank_account_withdrawn",
        "EmployeeBankAccount",
        account.id,
        employee_id=account.employee_id,
        detail=account.remarks or "撤回銀行賬戶記錄",
        before=before,
        after=bank_account_snapshot(account),
    )
    db.session.commit()
    flash("銀行賬戶記錄已撤回並保留於變更歷史。", "success")
    return employee_redirect(account.employee_id, "personal")


@employees_bp.route("/employees/<int:employee_id>/name", methods=["POST"])
@login_required
def update_name(employee_id):
    employee = db.get_or_404(Employee, employee_id)
    reason = request.form.get("reason")
    if reason not in {"correction", "legal_change"}:
        abort(400)
    evidence = save_evidence(
        employee,
        request.files.get("evidence"),
        "name_change_evidence",
        "改名證明",
    )
    if reason == "legal_change" and not evidence:
        flash("正式改名必須上傳證明。", "error")
        return employee_redirect(employee.id, "personal")
    before = employee_audit_snapshot(employee)
    employee.chinese_name = request.form.get("chinese_name", "").strip() or None
    employee.english_name = request.form.get("english_name", "").strip() or None
    write_audit(
        "employee_name_updated",
        "Employee",
        employee.id,
        employee_id=employee.id,
        detail=(
            "修正系統錄入錯誤"
            if reason == "correction"
            else "員工正式改名"
        ),
        before=before,
        after=employee_audit_snapshot(employee),
    )
    db.session.commit()
    flash("姓名已更新。", "success")
    return employee_redirect(employee.id, "personal")


@employees_bp.route("/employees/<int:employee_id>/assignment", methods=["POST"])
@login_required
def add_assignment(employee_id):
    employee = db.get_or_404(Employee, employee_id)
    previous_current = current_assignment_on(employee, date.today())
    effective_from = parse_date(request.form.get("effective_from"))
    if not effective_from:
        flash("任職調整必須填寫生效日期。", "error")
        return employee_redirect(employee.id, "employment")
    if any(
        item.status == "active" and item.effective_from == effective_from
        for item in employee.assignments
    ):
        flash("此生效日期已有任職記錄；請修正原有記錄。", "error")
        return employee_redirect(employee.id, "employment")
    evidence = save_evidence(
        employee,
        request.files.get("evidence"),
        "change_evidence",
        "任職調整憑證",
    )
    payroll_group = request.form.get("payroll_group") or employee.payroll_group
    workweek_days = normalize_workweek_days(
        request.form.get("workweek_days"),
        payroll_group,
    )
    assignment = create_assignment(
        employee=employee,
        effective_from=effective_from,
        payroll_group=payroll_group,
        workweek_days=workweek_days,
        region_id=form_int("region_id"),
        project_id=form_int("project_id"),
        department_id=form_int("department_id"),
        employer_id=form_int("employer_id"),
        payroll_entity_id=form_int("payroll_entity_id"),
        social_insurance_entity_id=form_int("social_insurance_entity_id"),
        labour_dispatch_entity_id=form_int("labour_dispatch_entity_id"),
        position_ids=[
            int(item)
            for item in request.form.getlist("position_ids")
            if str(item).isdigit()
        ],
        evidence_document_id=evidence.id if evidence else None,
        remarks=request.form.get("remarks", "").strip() or None,
    )
    current_assignment = current_assignment_on(employee, date.today())
    if current_assignment:
        employee.payroll_group = current_assignment.payroll_group
    leave_period = ensure_current_employment_period(employee, effective_from)
    if not employee.annual_leave_balances and leave_period.contract_annual_leave_days is None and request.form.get("initial_leave_days"):
        from tools.annual_leave_setup import validate
        from tools.annual_leave_policy import save_current_balance
        initial = parse_decimal(request.form.get("initial_leave_days"))
        try:
            validate(effective_from, initial)
        except ValueError:
            db.session.rollback()
            flash("leave.setup_invalid", "error")
            return employee_redirect(employee.id, "employment")
        leave_period.contract_annual_leave_days = initial
        leave_period.annual_leave_policy_year = date.today().year
        balance = save_current_balance(employee)
        write_audit("annual_leave_balance_updated", "EmployeeAnnualLeaveBalance", balance.id,
                    employee_id=employee.id, detail="初始任職建立本年度年假",
                    after={"year": date.today().year, "initial_days": str(initial),
                           "applied": str(balance.calculated_entitled_days)})
    write_audit(
        "assignment_changed",
        "EmployeeAssignment",
        assignment.id,
        employee_id=employee.id,
        detail=f"任職資料由 {effective_from:%Y-%m-%d} 生效",
        after={
            "project_id": assignment.project_id,
            "department_id": assignment.department_id,
            "payroll_group": assignment.payroll_group,
            "workweek_days": str(assignment.workweek_days),
            "evidence_missing": evidence is None,
        },
    )
    db.session.commit()
    if effective_from > date.today():
        flash(
            f"任職調整已保存，將於 {effective_from:%Y-%m-%d} 生效；目前任職暫不變。",
            "success",
        )
    elif previous_current:
        flash("任職調整已保存，當前任職已更新。", "success")
    else:
        flash("初始任職已保存，當前任職已建立。", "success")
    return employee_redirect(employee.id, "employment", saved=True)


@employees_bp.route("/employees/<int:employee_id>/salary", methods=["POST"])
@login_required
def add_salary(employee_id):
    employee = db.get_or_404(Employee, employee_id)
    effective_from = parse_date(request.form.get("effective_from"))
    amount = parse_decimal(request.form.get("amount"))
    salary_basis = request.form.get("salary_basis")
    monthly_pay_method = request.form.get("monthly_pay_method") or "full_month"
    if not effective_from or not valid_salary_amount(amount) or salary_basis not in {"monthly", "daily"}:
        flash("請完整填寫薪酬類型、金額及生效日期。", "error")
        return employee_redirect(employee.id, "employment")
    if monthly_pay_method not in {"full_month", "attendance_days"}:
        flash("請選擇有效的月薪計薪方式。", "error")
        return employee_redirect(employee.id, "employment")
    if any(
        item.status == "active" and item.effective_from == effective_from
        for item in employee.salaries
    ):
        flash("此生效日期已有薪酬記錄；請修正原有記錄。", "error")
        return employee_redirect(employee.id, "employment")
    evidence = save_evidence(
        employee,
        request.files.get("evidence"),
        "change_evidence",
        "薪酬調整憑證",
    )
    salary = create_salary(
        employee,
        effective_from,
        salary_basis,
        request.form.get("currency") or "HKD",
        amount,
        monthly_pay_method=monthly_pay_method,
        evidence_document_id=evidence.id if evidence else None,
        remarks=request.form.get("remarks", "").strip() or None,
    )
    write_audit(
        "salary_changed",
        "EmployeeSalary",
        salary.id,
        employee_id=employee.id,
        detail=f"薪酬由 {effective_from:%Y-%m-%d} 生效",
        after={
            "basis": salary_basis,
            "monthly_pay_method": salary.monthly_pay_method,
            "currency": salary.currency,
            "amount": str(salary.amount),
            "evidence_missing": evidence is None,
        },
    )
    db.session.commit()
    flash("薪酬資料已保存。", "success")
    return employee_redirect(employee.id, "employment", saved=True)


def replace_linked_evidence(old_document, new_document, reason):
    if not old_document or old_document.id == new_document.id:
        return
    from tools.profile_integrity import document_reference_count
    if old_document.status != "active" or document_reference_count(old_document) > 1:
        return
    old_document.status = "replaced"
    old_document.replaced_by_document_id = new_document.id
    old_document.replacement_reason = reason


@employees_bp.route(
    "/assignments/<int:assignment_id>/evidence",
    methods=["POST"],
)
@login_required
def supplement_assignment_evidence(assignment_id):
    assignment = db.get_or_404(EmployeeAssignment, assignment_id)
    document = save_evidence(
        assignment.employee,
        request.files.get("evidence"),
        "change_evidence",
        "任職調整憑證",
    )
    if not document:
        flash("請選擇憑證文件。", "error")
        return employee_redirect(assignment.employee_id, "employment")
    replace_linked_evidence(
        assignment.evidence_document,
        document,
        "補充或更正任職調整憑證",
    )
    assignment.evidence_document_id = document.id
    write_audit(
        "assignment_evidence_added",
        "EmployeeAssignment",
        assignment.id,
        employee_id=assignment.employee_id,
        detail=document.original_filename,
    )
    db.session.commit()
    flash("任職調整憑證已保存。", "success")
    return employee_redirect(assignment.employee_id, "employment")


@employees_bp.route(
    "/assignments/<int:assignment_id>/correct",
    methods=["POST"],
)
@login_required
def correct_assignment(assignment_id):
    assignment = db.get_or_404(EmployeeAssignment, assignment_id)
    if assignment.status != "active":
        abort(400)
    before = assignment_snapshot(assignment)
    effective_from = parse_date(request.form.get("effective_from"))
    payroll_group = request.form.get("payroll_group")
    if not effective_from or payroll_group not in {
        item[0] for item in PAYROLL_GROUPS
    }:
        flash("請完整填寫任職生效日期及薪酬組別。", "error")
        return employee_redirect(assignment.employee_id, "employment")
    duplicate = EmployeeAssignment.query.filter(
        EmployeeAssignment.employee_id == assignment.employee_id,
        EmployeeAssignment.effective_from == effective_from,
        EmployeeAssignment.status == "active",
        EmployeeAssignment.id != assignment.id,
    ).first()
    if duplicate:
        flash("同一生效日期已有一筆任職記錄，請修正原記錄。", "error")
        return employee_redirect(assignment.employee_id, "employment")
    assignment.effective_from = effective_from
    assignment.region_id = form_int("region_id")
    assignment.project_id = form_int("project_id")
    assignment.department_id = form_int("department_id")
    assignment.employer_id = form_int("employer_id")
    assignment.payroll_entity_id = form_int("payroll_entity_id")
    assignment.social_insurance_entity_id = form_int(
        "social_insurance_entity_id"
    )
    assignment.labour_dispatch_entity_id = form_int(
        "labour_dispatch_entity_id"
    )
    assignment.payroll_group = payroll_group
    assignment.workweek_days = normalize_workweek_days(
        request.form.get("workweek_days"),
        payroll_group,
    )
    assignment.remarks = request.form.get("remarks", "").strip() or None
    assignment.positions.clear()
    db.session.flush()
    for index, value in enumerate(request.form.getlist("position_ids")):
        if str(value).isdigit():
            assignment.positions.append(
                EmployeeAssignmentPosition(
                    position_id=int(value),
                    is_primary=index == 0,
                )
            )
    document = save_evidence(
        assignment.employee,
        request.files.get("evidence"),
        "change_evidence",
        "任職調整憑證",
    )
    if document:
        replace_linked_evidence(
            assignment.evidence_document,
            document,
            "更正任職調整憑證",
        )
        assignment.evidence_document_id = document.id
    rebuild_effective_ranges(assignment.employee.assignments)
    current = current_assignment_on(assignment.employee, date.today())
    if current:
        assignment.employee.payroll_group = current.payroll_group
    write_audit(
        "assignment_corrected",
        "EmployeeAssignment",
        assignment.id,
        employee_id=assignment.employee_id,
        detail=f"更正任職記錄，生效日 {effective_from:%Y-%m-%d}",
        before=before,
        after=assignment_snapshot(assignment),
    )
    db.session.commit()
    flash("任職記錄已更正。", "success")
    return employee_redirect(assignment.employee_id, "employment", saved=True)


@employees_bp.route(
    "/assignments/<int:assignment_id>/withdraw",
    methods=["POST"],
)
@login_required
def withdraw_assignment(assignment_id):
    assignment = db.get_or_404(EmployeeAssignment, assignment_id)
    before = assignment_snapshot(assignment)
    assignment.status = "voided"
    rebuild_effective_ranges(assignment.employee.assignments)
    current = current_assignment_on(assignment.employee, date.today())
    if current:
        assignment.employee.payroll_group = current.payroll_group
    write_audit(
        "assignment_withdrawn",
        "EmployeeAssignment",
        assignment.id,
        employee_id=assignment.employee_id,
        detail=request.form.get("reason", "").strip() or "撤回錯誤記錄",
        before=before,
        after=assignment_snapshot(assignment),
    )
    db.session.commit()
    flash("任職記錄已撤回，原記錄保留在歷史中。", "success")
    return employee_redirect(assignment.employee_id, "employment")


@employees_bp.route(
    "/salaries/<int:salary_id>/evidence",
    methods=["POST"],
)
@login_required
def supplement_salary_evidence(salary_id):
    salary = db.get_or_404(EmployeeSalary, salary_id)
    document = save_evidence(
        salary.employee,
        request.files.get("evidence"),
        "change_evidence",
        "薪酬調整憑證",
    )
    if not document:
        flash("請選擇憑證文件。", "error")
        return employee_redirect(salary.employee_id, "employment")
    replace_linked_evidence(
        salary.evidence_document,
        document,
        "補充或更正薪酬調整憑證",
    )
    salary.evidence_document_id = document.id
    write_audit(
        "salary_evidence_added",
        "EmployeeSalary",
        salary.id,
        employee_id=salary.employee_id,
        detail=document.original_filename,
    )
    db.session.commit()
    flash("薪酬調整憑證已保存。", "success")
    return employee_redirect(salary.employee_id, "employment")


@employees_bp.route(
    "/salaries/<int:salary_id>/correct",
    methods=["POST"],
)
@login_required
def correct_salary(salary_id):
    salary = db.get_or_404(EmployeeSalary, salary_id)
    if salary.status != "active":
        abort(400)
    before = salary_snapshot(salary)
    effective_from = parse_date(request.form.get("effective_from"))
    amount = parse_decimal(request.form.get("amount"))
    salary_basis = request.form.get("salary_basis")
    monthly_pay_method = request.form.get("monthly_pay_method") or "full_month"
    if (
        not effective_from
        or not valid_salary_amount(amount)
        or salary_basis not in {"monthly", "daily"}
        or monthly_pay_method not in {"full_month", "attendance_days"}
    ):
        flash("請完整填寫薪酬類型、金額及生效日期。", "error")
        return employee_redirect(salary.employee_id, "employment")
    duplicate = EmployeeSalary.query.filter(
        EmployeeSalary.employee_id == salary.employee_id,
        EmployeeSalary.effective_from == effective_from,
        EmployeeSalary.status == "active",
        EmployeeSalary.id != salary.id,
    ).first()
    if duplicate:
        flash("同一生效日期已有一筆薪酬記錄，請修正原記錄。", "error")
        return employee_redirect(salary.employee_id, "employment")
    salary.effective_from = effective_from
    salary.salary_basis = salary_basis
    salary.monthly_pay_method = (
        monthly_pay_method if salary_basis == "monthly" else "full_month"
    )
    salary.currency = request.form.get("currency") or "HKD"
    salary.amount = amount
    salary.remarks = request.form.get("remarks", "").strip() or None
    document = save_evidence(
        salary.employee,
        request.files.get("evidence"),
        "change_evidence",
        "薪酬調整憑證",
    )
    if document:
        replace_linked_evidence(
            salary.evidence_document,
            document,
            "更正薪酬調整憑證",
        )
        salary.evidence_document_id = document.id
    rebuild_effective_ranges(salary.employee.salaries)
    write_audit(
        "salary_corrected",
        "EmployeeSalary",
        salary.id,
        employee_id=salary.employee_id,
        detail=f"更正薪酬記錄，生效日 {effective_from:%Y-%m-%d}",
        before=before,
        after=salary_snapshot(salary),
    )
    db.session.commit()
    flash("薪酬記錄已更正。", "success")
    return employee_redirect(salary.employee_id, "employment")


@employees_bp.route(
    "/salaries/<int:salary_id>/withdraw",
    methods=["POST"],
)
@login_required
def withdraw_salary(salary_id):
    salary = db.get_or_404(EmployeeSalary, salary_id)
    before = salary_snapshot(salary)
    salary.status = "voided"
    rebuild_effective_ranges(salary.employee.salaries)
    write_audit(
        "salary_withdrawn",
        "EmployeeSalary",
        salary.id,
        employee_id=salary.employee_id,
        detail=request.form.get("reason", "").strip() or "撤回錯誤記錄",
        before=before,
        after=salary_snapshot(salary),
    )
    db.session.commit()
    flash("薪酬記錄已撤回，原記錄保留在歷史中。", "success")
    return employee_redirect(salary.employee_id, "employment")


def requested_mpf_values():
    effective_from = parse_date(request.form.get("effective_from"))
    selection = request.form.get("mpf_selection")
    if not effective_from:
        raise ValueError("MPF 記錄必須填寫生效日期。")
    exempt = request.form.get("mpf_exempt") == "on"
    if not selection and exempt:
        return effective_from, None, None, "exempt"
    if not str(selection or "").isdigit():
        raise ValueError("請選擇 MPF 計劃。")
    scheme = db.session.get(MpfScheme, int(selection))
    if not scheme or not scheme.active:
        raise ValueError("所選 MPF 計劃無效。")
    member_account_no = (
        request.form.get("member_account_no", "").strip() or None
    )
    contribution_mode = (
        "exempt"
        if request.form.get("mpf_exempt") == "on"
        else scheme.calculation_mode
    )
    return (
        effective_from,
        scheme,
        member_account_no,
        contribution_mode,
    )


@employees_bp.route("/employees/<int:employee_id>/mpf", methods=["POST"])
@login_required
def add_mpf_enrollment(employee_id):
    employee = db.get_or_404(Employee, employee_id)
    try:
        effective_from, scheme, member_no, mode = requested_mpf_values()
    except ValueError as exc:
        flash(str(exc), "error")
        return employee_redirect(employee.id, "employment")
    if any(
        item.status == "active" and item.effective_from == effective_from
        for item in employee.mpf_enrollments
    ):
        flash("此生效日期已有 MPF 記錄；請更正原有記錄。", "error")
        return employee_redirect(employee.id, "employment")
    enrollment = create_mpf_enrollment(
        employee,
        effective_from,
        scheme=scheme,
        member_account_no=member_no,
        contribution_mode=mode,
        remarks=request.form.get("remarks", "").strip() or None,
    )
    write_audit(
        "mpf_enrollment_added",
        "EmployeeMpfEnrollment",
        enrollment.id,
        employee_id=employee.id,
        detail=f"MPF 記錄由 {effective_from:%Y-%m-%d} 生效",
        after=mpf_snapshot(enrollment),
    )
    db.session.commit()
    flash("MPF 記錄已保存。", "success")
    return employee_redirect(employee.id, "employment")


@employees_bp.route(
    "/mpf-enrollments/<int:enrollment_id>/correct",
    methods=["POST"],
)
@login_required
def correct_mpf_enrollment(enrollment_id):
    enrollment = db.get_or_404(EmployeeMpfEnrollment, enrollment_id)
    if enrollment.status != "active":
        abort(400)
    try:
        effective_from, scheme, member_no, mode = requested_mpf_values()
    except ValueError as exc:
        flash(str(exc), "error")
        return employee_redirect(enrollment.employee_id, "employment")
    duplicate = EmployeeMpfEnrollment.query.filter(
        EmployeeMpfEnrollment.employee_id == enrollment.employee_id,
        EmployeeMpfEnrollment.effective_from == effective_from,
        EmployeeMpfEnrollment.status == "active",
        EmployeeMpfEnrollment.id != enrollment.id,
    ).first()
    if duplicate:
        flash("同一生效日期已有一筆 MPF 記錄。", "error")
        return employee_redirect(enrollment.employee_id, "employment")
    before = mpf_snapshot(enrollment)
    enrollment.effective_from = effective_from
    enrollment.scheme = scheme
    enrollment.member_account_no = member_no
    enrollment.contribution_mode = mode
    enrollment.remarks = request.form.get("remarks", "").strip() or None
    rebuild_effective_ranges(enrollment.employee.mpf_enrollments)
    current = current_mpf_on(enrollment.employee, date.today())
    enrollment.employee.mpf_mode = (
        current.contribution_mode if current else "regular"
    )
    write_audit(
        "mpf_enrollment_corrected",
        "EmployeeMpfEnrollment",
        enrollment.id,
        employee_id=enrollment.employee_id,
        detail=f"更正 MPF 記錄，生效日 {effective_from:%Y-%m-%d}",
        before=before,
        after=mpf_snapshot(enrollment),
    )
    db.session.commit()
    flash("MPF 記錄已更正。", "success")
    return employee_redirect(enrollment.employee_id, "employment")


@employees_bp.route(
    "/mpf-enrollments/<int:enrollment_id>/withdraw",
    methods=["POST"],
)
@login_required
def withdraw_mpf_enrollment(enrollment_id):
    enrollment = db.get_or_404(EmployeeMpfEnrollment, enrollment_id)
    before = mpf_snapshot(enrollment)
    enrollment.status = "voided"
    rebuild_effective_ranges(enrollment.employee.mpf_enrollments)
    current = current_mpf_on(enrollment.employee, date.today())
    enrollment.employee.mpf_mode = (
        current.contribution_mode if current else "regular"
    )
    write_audit(
        "mpf_enrollment_withdrawn",
        "EmployeeMpfEnrollment",
        enrollment.id,
        employee_id=enrollment.employee_id,
        detail=request.form.get("reason", "").strip() or "撤回錯誤記錄",
        before=before,
        after=mpf_snapshot(enrollment),
    )
    db.session.commit()
    flash("MPF 記錄已撤回，原記錄保留在變更歷史。", "success")
    return employee_redirect(enrollment.employee_id, "employment")


@employees_bp.route("/employees/<int:employee_id>/identities", methods=["POST"])
@login_required
@credential_form_validation("identity")
def add_identity(employee_id):
    employee = db.get_or_404(Employee, employee_id)
    try:
        old = renewal_source(EmployeeIdentity, employee)
    except ValueError as error:
        flash(str(error), "error")
        return employee_redirect(employee.id, "credentials")
    identity_type = request.form.get("identity_type")
    identity_number = request.form.get("identity_number", "").strip()
    if not identity_type or not identity_number:
        flash("請填寫身份證件類型和號碼。", "error")
        return employee_redirect(employee.id, "credentials")
    conflict = identity_conflict(identity_type, identity_number, renewal=old)
    if conflict:
        flash(
            f"此證件號碼已屬於 {conflict.employee.employee_no} "
            f"{conflict.employee.display_name}，請先核對。",
            "error",
        )
        return employee_redirect(employee.id, "credentials")
    primary = (old.is_primary if old else False) or parse_bool(request.form.get("is_primary")) or not employee.identities
    if primary and not (old and old.is_primary):
        for item in employee.identities:
            item.is_primary = False
    evidence = save_evidence(
        employee,
        request.files.get("evidence"),
        "identity",
        "身份證明",
    )
    identity = EmployeeIdentity(
        renews_id=old.id if old else None,
        employee=employee,
        identity_type=identity_type,
        identity_number=identity_number,
        issue_date=parse_date(request.form.get("issue_date")),
        expiry_date=parse_date(request.form.get("expiry_date")),
        is_long_term=parse_bool(request.form.get("is_long_term")),
        is_primary=primary,
        document_id=evidence.id if evidence else None,
    )
    db.session.add(identity)
    db.session.flush()
    write_audit(
        "identity_added",
        "EmployeeIdentity",
        identity.id,
        employee_id=employee.id,
        detail=f"新增 {identity_type}",
    )
    db.session.commit()
    flash("身份證件已新增。", "success")
    return employee_redirect(employee.id, "credentials")


@employees_bp.route("/identities/<int:identity_id>/update", methods=["POST"])
@login_required
@credential_form_validation("identity")
def update_identity(identity_id):
    identity = db.get_or_404(EmployeeIdentity, identity_id)
    if identity.status != "active":
        abort(400)
    identity_type = request.form.get("identity_type", "").strip()
    identity_number = request.form.get("identity_number", "").strip()
    if identity_type not in dict(IDENTITY_TYPE_OPTIONS) or not identity_number:
        flash("請填寫身份證件類型和號碼。", "error")
        return employee_redirect(identity.employee_id, "credentials")
    conflict = identity_conflict(
        identity_type,
        identity_number,
        exclude_id=identity.id, renewal=identity,
    )
    if conflict:
        flash(
            f"此證件號碼已屬於 {conflict.employee.employee_no} "
            f"{conflict.employee.display_name}，請先核對。",
            "error",
        )
        return employee_redirect(identity.employee_id, "credentials")
    fields = (
        "identity_type",
        "identity_number",
        "issue_date",
        "expiry_date",
        "is_long_term",
        "is_primary",
        "document_id",
        "remarks",
    )
    before = credential_snapshot(identity, fields)
    identity.identity_type = identity_type
    identity.identity_number = identity_number
    identity.issue_date = parse_date(request.form.get("issue_date"))
    identity.is_long_term = parse_bool(request.form.get("is_long_term"))
    identity.expiry_date = (
        None
        if identity.is_long_term
        else parse_date(request.form.get("expiry_date"))
    )
    identity.remarks = request.form.get("remarks", "").strip() or None
    wants_primary = parse_bool(request.form.get("is_primary"))
    active_others = [
        item
        for item in identity.employee.identities
        if item.id != identity.id and item.status == "active"
    ]
    if wants_primary:
        for item in active_others:
            item.is_primary = False
        identity.is_primary = True
    elif identity.is_primary and active_others:
        identity.is_primary = False
        active_others[0].is_primary = True
    elif not active_others:
        identity.is_primary = True
    evidence = replace_record_evidence(
        identity.employee,
        identity.document,
        request.files.get("evidence"),
        "identity",
        "身份證明",
    )
    if evidence:
        identity.document_id = evidence.id
    write_audit(
        "identity_corrected",
        "EmployeeIdentity",
        identity.id,
        employee_id=identity.employee_id,
        detail=f"更正 {identity_type} 資料",
        before=before,
        after=credential_snapshot(identity, fields),
    )
    db.session.commit()
    flash("身份證件資料已更正。", "success")
    return employee_redirect(identity.employee_id, "credentials")


@employees_bp.route("/identities/<int:identity_id>/void", methods=["POST"])
@login_required
def void_identity(identity_id):
    identity = db.get_or_404(EmployeeIdentity, identity_id)
    fields = (
        "identity_type",
        "identity_number",
        "issue_date",
        "expiry_date",
        "is_long_term",
        "is_primary",
        "document_id",
        "status",
    )
    before = credential_snapshot(identity, fields)
    identity.status = "voided"
    identity.is_primary = False
    replacement = next(
        (
            item
            for item in identity.employee.identities
            if item.id != identity.id and item.status == "active"
        ),
        None,
    )
    if replacement and not any(
        item.is_primary
        for item in identity.employee.identities
        if item.id != identity.id and item.status == "active"
    ):
        replacement.is_primary = True
    write_audit(
        "identity_voided",
        "EmployeeIdentity",
        identity.id,
        employee_id=identity.employee_id,
        detail=request.form.get("reason", "").strip() or "作廢身份證件記錄",
        before=before,
        after=credential_snapshot(identity, fields),
    )
    db.session.commit()
    flash("身份證件已標記作廢，歷史記錄仍然保留。", "success")
    return employee_redirect(identity.employee_id, "credentials")


@employees_bp.route("/identities/<int:identity_id>/replace", methods=["POST"])
@login_required
def replace_identity(identity_id):
    old = db.get_or_404(EmployeeIdentity, identity_id)
    old.status = "replaced"
    if old.is_primary:
        old.is_primary = False
    request.form = request.form.copy()
    return add_identity(old.employee_id)


@employees_bp.route("/employees/<int:employee_id>/certificates", methods=["POST"])
@login_required
@credential_form_validation("certificate")
def add_certificate(employee_id):
    employee = db.get_or_404(Employee, employee_id)
    try:
        old = renewal_source(EmployeeCertificate, employee)
    except ValueError as error:
        flash(str(error), "error")
        return employee_redirect(employee.id, "credentials")
    certificate_type_id = form_int("certificate_type_id")
    if not certificate_type_id:
        abort(400)
    evidence = save_evidence(
        employee,
        request.files.get("evidence"),
        "qualification",
        "證件附件",
    )
    certificate = EmployeeCertificate(
        renews_id=old.id if old else None,
        employee=employee,
        certificate_type_id=certificate_type_id,
        certificate_no=request.form.get("certificate_no", "").strip() or None,
        valid_from=parse_date(request.form.get("valid_from")),
        expiry_date=parse_date(request.form.get("expiry_date")),
        is_long_term=parse_bool(request.form.get("is_long_term")),
        document_id=evidence.id if evidence else None,
        remarks=request.form.get("remarks", "").strip() or None,
    )
    db.session.add(certificate)
    db.session.flush()
    write_audit(
        "certificate_added",
        "EmployeeCertificate",
        certificate.id,
        employee_id=employee.id,
        detail="新增證件",
    )
    db.session.commit()
    flash("證件已新增。", "success")
    return employee_redirect(employee.id, "credentials")


@employees_bp.route(
    "/certificates/<int:certificate_id>/update",
    methods=["POST"],
)
@login_required
@credential_form_validation("certificate")
def update_certificate(certificate_id):
    certificate = db.get_or_404(EmployeeCertificate, certificate_id)
    if certificate.status != "active":
        abort(400)
    certificate_type_id = form_int("certificate_type_id")
    if not certificate_type_id:
        flash("請選擇證件類型。", "error")
        return employee_redirect(certificate.employee_id, "credentials")
    fields = (
        "certificate_type_id",
        "certificate_no",
        "valid_from",
        "expiry_date",
        "is_long_term",
        "document_id",
        "remarks",
    )
    before = credential_snapshot(certificate, fields)
    certificate.certificate_type_id = certificate_type_id
    certificate.certificate_no = (
        request.form.get("certificate_no", "").strip() or None
    )
    certificate.valid_from = parse_date(request.form.get("valid_from"))
    certificate.is_long_term = parse_bool(request.form.get("is_long_term"))
    certificate.expiry_date = (
        None
        if certificate.is_long_term
        else parse_date(request.form.get("expiry_date"))
    )
    certificate.remarks = request.form.get("remarks", "").strip() or None
    evidence = replace_record_evidence(
        certificate.employee,
        certificate.document,
        request.files.get("evidence"),
        "qualification",
        "證件附件",
    )
    if evidence:
        certificate.document_id = evidence.id
    write_audit(
        "certificate_corrected",
        "EmployeeCertificate",
        certificate.id,
        employee_id=certificate.employee_id,
        detail="更正證件資料",
        before=before,
        after=credential_snapshot(certificate, fields),
    )
    db.session.commit()
    flash("證件資料已更正。", "success")
    return employee_redirect(certificate.employee_id, "credentials")


@employees_bp.route(
    "/certificates/<int:certificate_id>/void",
    methods=["POST"],
)
@login_required
def void_certificate(certificate_id):
    certificate = db.get_or_404(EmployeeCertificate, certificate_id)
    fields = (
        "certificate_type_id",
        "certificate_no",
        "valid_from",
        "expiry_date",
        "is_long_term",
        "document_id",
        "status",
    )
    before = credential_snapshot(certificate, fields)
    certificate.status = "voided"
    write_audit(
        "certificate_voided",
        "EmployeeCertificate",
        certificate.id,
        employee_id=certificate.employee_id,
        detail=request.form.get("reason", "").strip() or "作廢證件記錄",
        before=before,
        after=credential_snapshot(certificate, fields),
    )
    db.session.commit()
    flash("證件已標記作廢，歷史記錄仍然保留。", "success")
    return employee_redirect(certificate.employee_id, "credentials")


@employees_bp.route("/employees/<int:employee_id>/visas", methods=["POST"])
@login_required
@credential_form_validation("visa")
def add_visa(employee_id):
    employee = db.get_or_404(Employee, employee_id)
    try:
        old = renewal_source(EmployeeVisa, employee)
    except ValueError as error:
        flash(str(error), "error")
        return employee_redirect(employee.id, "credentials")
    visa_category_id = form_int("visa_category_id")
    if not visa_category_id:
        abort(400)
    evidence = save_evidence(
        employee,
        request.files.get("evidence"),
        "visa",
        "VISA 附件",
    )
    visa = EmployeeVisa(
        renews_id=old.id if old else None,
        employee=employee,
        visa_category_id=visa_category_id,
        visa_no=request.form.get("visa_no", "").strip() or None,
        issue_date=parse_date(request.form.get("issue_date")),
        expiry_date=parse_date(request.form.get("expiry_date")),
        document_id=evidence.id if evidence else None,
        remarks=request.form.get("remarks", "").strip() or None,
    )
    db.session.add(visa)
    employee.visa_required = True
    db.session.flush()
    write_audit(
        "visa_added",
        "EmployeeVisa",
        visa.id,
        employee_id=employee.id,
        detail="新增 VISA",
    )
    db.session.commit()
    flash("VISA 已新增。", "success")
    return employee_redirect(employee.id, "credentials")


@employees_bp.route("/visas/<int:visa_id>/update", methods=["POST"])
@login_required
@credential_form_validation("visa")
def update_visa(visa_id):
    visa = db.get_or_404(EmployeeVisa, visa_id)
    if visa.status != "active":
        abort(400)
    visa_category_id = form_int("visa_category_id")
    if not visa_category_id:
        flash("請選擇 VISA 類別。", "error")
        return employee_redirect(visa.employee_id, "credentials")
    fields = (
        "visa_category_id",
        "visa_no",
        "issue_date",
        "expiry_date",
        "document_id",
        "remarks",
    )
    before = credential_snapshot(visa, fields)
    visa.visa_category_id = visa_category_id
    visa.visa_no = request.form.get("visa_no", "").strip() or None
    visa.issue_date = parse_date(request.form.get("issue_date"))
    visa.expiry_date = parse_date(request.form.get("expiry_date"))
    visa.remarks = request.form.get("remarks", "").strip() or None
    evidence = replace_record_evidence(
        visa.employee,
        visa.document,
        request.files.get("evidence"),
        "visa",
        "VISA 附件",
    )
    if evidence:
        visa.document_id = evidence.id
    write_audit(
        "visa_corrected",
        "EmployeeVisa",
        visa.id,
        employee_id=visa.employee_id,
        detail="更正 VISA 資料",
        before=before,
        after=credential_snapshot(visa, fields),
    )
    db.session.commit()
    flash("VISA 資料已更正。", "success")
    return employee_redirect(visa.employee_id, "credentials")


@employees_bp.route("/visas/<int:visa_id>/void", methods=["POST"])
@login_required
def void_visa(visa_id):
    visa = db.get_or_404(EmployeeVisa, visa_id)
    fields = (
        "visa_category_id",
        "visa_no",
        "issue_date",
        "expiry_date",
        "document_id",
        "status",
    )
    before = credential_snapshot(visa, fields)
    visa.status = "voided"
    write_audit(
        "visa_voided",
        "EmployeeVisa",
        visa.id,
        employee_id=visa.employee_id,
        detail=request.form.get("reason", "").strip() or "作廢 VISA 記錄",
        before=before,
        after=credential_snapshot(visa, fields),
    )
    db.session.commit()
    flash("VISA 已標記作廢，歷史記錄仍然保留。", "success")
    return employee_redirect(visa.employee_id, "credentials")


@employees_bp.route(
    "/employees/<int:employee_id>/qualifications",
    methods=["POST"],
)
@login_required
@credential_form_validation("qualification")
def add_qualification(employee_id):
    employee = db.get_or_404(Employee, employee_id)
    try:
        old = renewal_source(EmployeeQualification, employee)
    except ValueError as error:
        flash(str(error), "error")
        return employee_redirect(employee.id, "credentials")
    category = request.form.get("category", "skill").strip()
    name = request.form.get("qualification_name", "").strip()
    if category not in {"degree", "skill"} or not name:
        flash("請選擇學歷或技能類別並填寫名稱。", "error")
        return employee_redirect(employee.id, "credentials")
    evidence = save_evidence(
        employee,
        request.files.get("evidence"),
        "qualification",
        "學歷 / 技能證書",
    )
    qualification = EmployeeQualification(
        renews_id=old.id if old else None,
        employee=employee,
        category=category,
        qualification_name=name,
        certificate_no=(
            request.form.get("certificate_no", "").strip() or None
        ),
        issue_date=parse_date(request.form.get("issue_date")),
        expiry_date=parse_date(request.form.get("expiry_date")),
        document_id=evidence.id if evidence else None,
        remarks=request.form.get("remarks", "").strip() or None,
        status="active",
    )
    db.session.add(qualification)
    db.session.flush()
    write_audit(
        "qualification_added",
        "EmployeeQualification",
        qualification.id,
        employee_id=employee.id,
        detail=f"新增 {name}",
    )
    db.session.commit()
    flash("學歷 / 技能證書已新增。", "success")
    return employee_redirect(employee.id, "credentials")


@employees_bp.route(
    "/qualifications/<int:qualification_id>/update",
    methods=["POST"],
)
@login_required
@credential_form_validation("qualification")
def update_qualification(qualification_id):
    qualification = db.get_or_404(EmployeeQualification, qualification_id)
    if qualification.status != "active":
        abort(400)
    category = request.form.get("category", "").strip()
    name = request.form.get("qualification_name", "").strip()
    if category not in {"degree", "skill"} or not name:
        flash("請選擇學歷或技能類別並填寫名稱。", "error")
        return employee_redirect(qualification.employee_id, "credentials")
    fields = (
        "category",
        "qualification_name",
        "certificate_no",
        "issue_date",
        "expiry_date",
        "document_id",
        "remarks",
    )
    before = credential_snapshot(qualification, fields)
    qualification.category = category
    qualification.qualification_name = name
    qualification.certificate_no = (
        request.form.get("certificate_no", "").strip() or None
    )
    qualification.issue_date = parse_date(request.form.get("issue_date"))
    qualification.expiry_date = parse_date(request.form.get("expiry_date"))
    qualification.remarks = request.form.get("remarks", "").strip() or None
    evidence = replace_record_evidence(
        qualification.employee,
        qualification.document,
        request.files.get("evidence"),
        "qualification",
        "學歷 / 技能證書",
    )
    if evidence:
        qualification.document_id = evidence.id
    write_audit(
        "qualification_corrected",
        "EmployeeQualification",
        qualification.id,
        employee_id=qualification.employee_id,
        detail=f"更正 {name}",
        before=before,
        after=credential_snapshot(qualification, fields),
    )
    db.session.commit()
    flash("學歷 / 技能證書資料已更正。", "success")
    return employee_redirect(qualification.employee_id, "credentials")


@employees_bp.route(
    "/qualifications/<int:qualification_id>/void",
    methods=["POST"],
)
@login_required
def void_qualification(qualification_id):
    qualification = db.get_or_404(EmployeeQualification, qualification_id)
    fields = (
        "category",
        "qualification_name",
        "certificate_no",
        "issue_date",
        "expiry_date",
        "document_id",
        "status",
    )
    before = credential_snapshot(qualification, fields)
    qualification.status = "voided"
    write_audit(
        "qualification_voided",
        "EmployeeQualification",
        qualification.id,
        employee_id=qualification.employee_id,
        detail=request.form.get("reason", "").strip() or "作廢學歷 / 技能證書記錄",
        before=before,
        after=credential_snapshot(qualification, fields),
    )
    db.session.commit()
    flash("學歷 / 技能證書已標記作廢，歷史記錄仍然保留。", "success")
    return employee_redirect(qualification.employee_id, "credentials")


@employees_bp.route("/employees/<int:employee_id>/probation", methods=["POST"])
@login_required
def update_probation(employee_id):
    employee = db.get_or_404(Employee, employee_id)
    period = ensure_current_employment_period(
        employee,
        parse_date(request.form.get("start_date")) or date.today(),
    )
    before = employment_period_snapshot(period)
    evidence = replace_record_evidence(
        employee,
        period.confirmation_document,
        request.files.get("evidence"),
        "probation_confirmation",
        "通過試用期申請表",
        "更正通過試用期申請表",
    )
    period.probation_end_date = parse_date(request.form.get("probation_end_date"))
    period.confirmation_date = parse_date(request.form.get("confirmation_date"))
    if evidence:
        period.confirmation_document_id = evidence.id
    write_audit(
        "probation_updated",
        "EmployeeEmploymentPeriod",
        period.id,
        employee_id=employee.id,
        detail="更新試用期 / 轉正資料",
        before=before,
        after=employment_period_snapshot(period),
    )
    db.session.commit()
    flash("試用期資料已保存。", "success")
    return employee_redirect(employee.id, "employment_status")


@employees_bp.route("/employees/<int:employee_id>/annual-leave", methods=["POST"])
@login_required
def add_annual_leave(employee_id):
    from tools.attendance_policy import leave_day_units
    employee = db.get_or_404(Employee, employee_id)
    leave_type = request.form.get("leave_type", "annual").strip()
    if leave_type not in {"annual", "sick", "unpaid"}:
        leave_type = "annual"
    leave_date = parse_date(
        request.form.get("start_date") or request.form.get("leave_date")
    )
    end_date = parse_date(request.form.get("end_date")) or leave_date
    start_session = request.form.get("start_session") or "am"
    end_session = request.form.get("end_session") or "pm"
    try:
        units = leave_day_units(employee, leave_date, end_date, start_session, end_session)
    except ValueError as exc:
        flash(str(exc), "error")
        return annual_leave_redirect(employee.id, request.form.get("entitlement_year", type=int))
    calculated_days = sum(units.values(), parse_decimal("0"))
    if not calculated_days:
        flash("leave.zero_days", "error")
        return annual_leave_redirect(employee.id, leave_date.year)
    manual_days = parse_decimal(request.form.get("days"))
    days = calculated_days
    if (
        (manual_days is not None and manual_days != calculated_days)
        or not leave_date
        or not calculated_days
        or not days
        or days < parse_decimal("0.5")
        or days % parse_decimal("0.5")
    ):
        flash("請填寫正確的請假起止日期；日數以 0.5 日為單位。", "error")
        return annual_leave_redirect(
            employee.id,
            request.form.get("entitlement_year", type=int),
        )
    if conflicting_absence(employee, leave_date, end_date, start_session, end_session):
        flash("leave.overlap", "error")
        return annual_leave_redirect(employee.id, leave_date.year)
    evidence = save_evidence(employee, request.files.get("evidence"), "change_evidence",
                             {"annual": "年假憑證", "sick": "病假憑證", "unpaid": "無薪假憑證"}[leave_type])
    record = EmployeeAnnualLeaveRecord(
        employee=employee,
        leave_date=leave_date,
        end_date=end_date,
        start_session=start_session,
        end_session=end_session,
        entitlement_year=request.form.get("entitlement_year", type=int)
        or leave_date.year,
        days=days,
        leave_units_json={day.isoformat(): str(value) for day, value in units.items()},
        leave_type=leave_type,
        evidence_document=evidence,
        status="active",
        remarks=request.form.get("remarks", "").strip() or None,
        created_by=current_user.id,
    )
    db.session.add(record)
    db.session.flush()
    entitlement_year = record.entitlement_year
    if leave_type == "annual":
        try:
            allocate_annual_leave_with_comp(record, as_of=leave_date)
        except ValueError:
            db.session.rollback()
            flash("假期結餘不足，請核對補休及年假可用日數。", "error")
            return annual_leave_redirect(employee.id, entitlement_year)
    write_audit(
        "leave_added",
        "EmployeeAnnualLeaveRecord",
        record.id,
        employee_id=employee.id,
        detail=(
            f"{leave_type}: {leave_date:%Y-%m-%d} 至 {end_date:%Y-%m-%d} "
            f"{days} 日"
        ),
    )
    db.session.commit()
    flash("請假記錄已新增。", "success")
    return annual_leave_redirect(employee.id, record.entitlement_year)


@employees_bp.route(
    "/annual-leave/<int:record_id>/update",
    methods=["POST"],
)
@login_required
def update_annual_leave(record_id):
    from tools.attendance_policy import leave_day_units
    record = db.get_or_404(EmployeeAnnualLeaveRecord, record_id)
    employee_id = record.employee_id
    before = {
        "leave_type": record.leave_type,
        "start_date": record.leave_date.isoformat(),
        "end_date": (
            (record.end_date or record.leave_date).isoformat()
        ),
        "start_session": record.start_session,
        "end_session": record.end_session,
        "days": str(record.days),
        "leave_units_json": record.leave_units_json,
        "entitlement_year": record.entitlement_year,
        "status": record.status,
    }
    start_date = parse_date(request.form.get("start_date"))
    leave_type = request.form.get("leave_type", record.leave_type).strip()
    if leave_type not in {"annual", "sick", "unpaid"}:
        leave_type = record.leave_type
    end_date = parse_date(request.form.get("end_date")) or start_date
    start_session = request.form.get("start_session") or "am"
    end_session = request.form.get("end_session") or "pm"
    try:
        units = leave_day_units(record.employee, start_date, end_date, start_session, end_session)
    except ValueError as exc:
        flash(str(exc), "error")
        return annual_leave_redirect(employee_id, request.form.get("entitlement_year", type=int))
    calculated = sum(units.values(), parse_decimal("0"))
    if not calculated:
        flash("leave.zero_days", "error")
        return annual_leave_redirect(employee_id, start_date.year)
    manual = parse_decimal(request.form.get("days"))
    days = calculated
    if (
        (manual is not None and manual != calculated)
        or not calculated
        or not days
        or days < parse_decimal("0.5")
        or days % parse_decimal("0.5")
    ):
        flash("請填寫正確的請假起止日期；日數以 0.5 日為單位。", "error")
        return annual_leave_redirect(
            record.employee_id,
            request.form.get("entitlement_year", type=int),
        )
    if conflicting_absence(record.employee, start_date, end_date, start_session, end_session,
                           exclude=("leave", record.id)):
        flash("leave.overlap", "error")
        return annual_leave_redirect(employee_id, start_date.year)
    record.leave_date = start_date
    record.end_date = end_date
    record.start_session = start_session
    record.end_session = end_session
    record.days = days
    record.leave_units_json = {day.isoformat(): str(value) for day, value in units.items()}
    record.leave_type = leave_type
    record.entitlement_year = (
        request.form.get("entitlement_year", type=int) or start_date.year
    )
    record.remarks = request.form.get("remarks", "").strip() or None
    record.status = "active"
    evidence = save_evidence(
        record.employee,
        request.files.get("evidence"),
        "change_evidence",
        "請假憑證",
    )
    if evidence:
        record.evidence_document = evidence
    clear_leave_allocations(record)
    if leave_type == "annual":
        try:
            allocate_annual_leave_with_comp(record, as_of=start_date)
        except ValueError:
            db.session.rollback()
            flash("假期結餘不足，請核對補休及年假可用日數。", "error")
            return annual_leave_redirect(
                employee_id,
                request.form.get("entitlement_year", type=int),
            )
    write_audit(
        "leave_corrected",
        "EmployeeAnnualLeaveRecord",
        record.id,
        employee_id=record.employee_id,
        detail=f"{start_date:%Y-%m-%d} 至 {end_date:%Y-%m-%d}，{days} 日",
        before=before,
        after={
            "leave_type": record.leave_type,
            "start_date": record.leave_date.isoformat(),
            "end_date": (record.end_date or record.leave_date).isoformat(),
            "start_session": record.start_session,
            "end_session": record.end_session,
            "days": str(record.days),
            "leave_units_json": record.leave_units_json,
            "entitlement_year": record.entitlement_year,
            "status": record.status,
        },
    )
    db.session.commit()
    flash("請假記錄已更正。", "success")
    return annual_leave_redirect(record.employee_id, record.entitlement_year)


@employees_bp.route(
    "/annual-leave/<int:record_id>/void",
    methods=["POST"],
)
@login_required
def void_annual_leave(record_id):
    record = db.get_or_404(EmployeeAnnualLeaveRecord, record_id)
    before = {"status": record.status, "days": str(record.days)}
    record.status = "voided"
    write_audit(
        "leave_voided",
        "EmployeeAnnualLeaveRecord",
        record.id,
        employee_id=record.employee_id,
        detail=request.form.get("reason", "").strip() or "撤回錯誤記錄",
        before=before,
        after={"status": record.status, "days": str(record.days)},
    )
    db.session.commit()
    flash("請假記錄已撤回。", "success")
    return annual_leave_redirect(
        record.employee_id,
        request.form.get("entitlement_year", type=int)
        or record.entitlement_year,
    )


@employees_bp.route("/employees/<int:employee_id>/leave-balance", methods=["POST"])
@login_required
def update_leave_balance(employee_id):
    employee = db.get_or_404(Employee, employee_id)
    year = request.form.get("year", type=int) or date.today().year
    balance = EmployeeAnnualLeaveBalance.query.filter_by(
        employee_id=employee.id,
        year=year,
    ).first()
    if not balance:
        balance = EmployeeAnnualLeaveBalance(employee=employee, year=year)
        db.session.add(balance)
    balance.carried_from_previous_days = parse_decimal(
        request.form.get("carried"),
        parse_decimal("0"),
    )
    balance.manual_adjustment_days = parse_decimal(
        request.form.get("manual_adjustment"),
        parse_decimal("0"),
    )
    db.session.commit()
    flash("年假結餘已保存。", "success")
    return employee_redirect(employee.id, "leave")


@employees_bp.route("/employees/<int:employee_id>/allowances", methods=["POST"])
@login_required
def add_allowance(employee_id):
    employee = db.get_or_404(Employee, employee_id)
    if employee.payroll_group == "site_daily":
        flash("固定補貼目前只支持月工及 OFFICE，不支持日工。", "error")
        return employee_redirect(employee.id, "employment")
    allowance_type = request.form.get("allowance_type", "").strip()
    effective_from = parse_date(request.form.get("effective_from"))
    effective_to = parse_date(request.form.get("effective_to"))
    amount = parse_decimal(request.form.get("amount"))
    currency = request.form.get("currency", "HKD").strip().upper()
    exchange_rate = parse_decimal(request.form.get("exchange_rate"))
    salary = current_salary_on(employee, effective_from or date.today())
    if allowance_type not in {"meal", "transport", "special"}:
        flash("請選擇餐補、交通補貼或特殊津貼。", "error")
        return employee_redirect(employee.id, "employment")
    if not effective_from or amount is None or amount < 0:
        flash("請填寫有效的補貼生效日期及金額。", "error")
        return employee_redirect(employee.id, "employment")
    if effective_to and effective_to < effective_from:
        flash("補貼結束日期不可早於生效日期。", "error")
        return employee_redirect(employee.id, "employment")
    if salary and currency != salary.currency and (
        exchange_rate is None or exchange_rate <= 0
    ):
        flash("補貼幣種與發薪幣種不同，必須填寫匯率。", "error")
        return employee_redirect(employee.id, "employment")
    evidence = save_evidence(
        employee,
        request.files.get("evidence"),
        "change_evidence",
        "補貼憑證",
    )
    labels = {"meal": "餐補", "transport": "交通補貼", "special": "特殊津貼"}
    allowance = EmployeeAllowance(
        employee=employee,
        allowance_type=allowance_type,
        label=labels[allowance_type],
        currency=currency,
        amount=amount,
        exchange_rate=(
            exchange_rate if salary and currency != salary.currency else None
        ),
        effective_from=effective_from,
        effective_to=effective_to,
        status="active",
        evidence_document=evidence,
        remarks=request.form.get("remarks", "").strip() or None,
    )
    db.session.add(allowance)
    db.session.flush()
    write_audit(
        "allowance_added",
        "EmployeeAllowance",
        allowance.id,
        employee_id=employee.id,
        detail=f"{labels[allowance_type]} {currency} {amount}",
    )
    db.session.commit()
    flash("補貼記錄已新增。", "success")
    return employee_redirect(employee.id, "employment")


@employees_bp.route("/allowances/<int:allowance_id>/correct", methods=["POST"])
@login_required
def correct_allowance(allowance_id):
    allowance = db.get_or_404(EmployeeAllowance, allowance_id)
    if allowance.employee.payroll_group == "site_daily":
        flash("固定補貼目前只支持月工及 OFFICE，不支持日工。", "error")
        return employee_redirect(allowance.employee_id, "employment")
    before = {
        "allowance_type": allowance.allowance_type,
        "currency": allowance.currency,
        "amount": str(allowance.amount),
        "exchange_rate": (
            str(allowance.exchange_rate) if allowance.exchange_rate else None
        ),
        "effective_from": allowance.effective_from.isoformat(),
        "effective_to": (
            allowance.effective_to.isoformat() if allowance.effective_to else None
        ),
    }
    allowance_type = request.form.get(
        "allowance_type", allowance.allowance_type
    ).strip()
    effective_from = parse_date(request.form.get("effective_from"))
    effective_to = parse_date(request.form.get("effective_to"))
    amount = parse_decimal(request.form.get("amount"))
    currency = request.form.get("currency", allowance.currency).strip().upper()
    exchange_rate = parse_decimal(request.form.get("exchange_rate"))
    salary = current_salary_on(allowance.employee, effective_from or date.today())
    if (
        allowance_type not in {"meal", "transport", "special"}
        or not effective_from
        or amount is None
        or amount < 0
        or (effective_to and effective_to < effective_from)
        or (
            salary
            and currency != salary.currency
            and (exchange_rate is None or exchange_rate <= 0)
        )
    ):
        flash("請核對補貼類型、日期、金額、幣種及匯率。", "error")
        return employee_redirect(allowance.employee_id, "employment")
    labels = {"meal": "餐補", "transport": "交通補貼", "special": "特殊津貼"}
    allowance.allowance_type = allowance_type
    allowance.label = labels[allowance_type]
    allowance.effective_from = effective_from
    allowance.effective_to = effective_to
    allowance.amount = amount
    allowance.currency = currency
    allowance.exchange_rate = (
        exchange_rate if salary and currency != salary.currency else None
    )
    allowance.remarks = request.form.get("remarks", "").strip() or None
    evidence = save_evidence(
        allowance.employee,
        request.files.get("evidence"),
        "change_evidence",
        "補貼憑證",
    )
    if evidence:
        allowance.evidence_document = evidence
    allowance.status = "active"
    write_audit(
        "allowance_corrected",
        "EmployeeAllowance",
        allowance.id,
        employee_id=allowance.employee_id,
        before=before,
        after={
            "allowance_type": allowance.allowance_type,
            "currency": allowance.currency,
            "amount": str(allowance.amount),
            "exchange_rate": (
                str(allowance.exchange_rate) if allowance.exchange_rate else None
            ),
            "effective_from": allowance.effective_from.isoformat(),
            "effective_to": (
                allowance.effective_to.isoformat() if allowance.effective_to else None
            ),
        },
    )
    db.session.commit()
    flash("補貼記錄已更正。", "success")
    return employee_redirect(allowance.employee_id, "employment")


@employees_bp.route("/allowances/<int:allowance_id>/withdraw", methods=["POST"])
@login_required
def withdraw_allowance(allowance_id):
    allowance = db.get_or_404(EmployeeAllowance, allowance_id)
    allowance.status = "voided"
    write_audit(
        "allowance_withdrawn",
        "EmployeeAllowance",
        allowance.id,
        employee_id=allowance.employee_id,
        detail=request.form.get("reason", "").strip() or "撤回補貼記錄",
    )
    db.session.commit()
    flash("補貼記錄已撤回。", "success")
    return employee_redirect(allowance.employee_id, "employment")


@employees_bp.route("/employees/<int:employee_id>/work-injuries", methods=["POST"])
@login_required
def add_work_injury(employee_id):
    employee = db.get_or_404(Employee, employee_id)
    accident_date = parse_date(request.form.get("accident_date"))
    payroll_start = parse_date(request.form.get("payroll_start_date"))
    payroll_end = parse_date(request.form.get("payroll_end_date"))
    confirmed = parse_decimal(request.form.get("confirmed_monthly_earnings"))
    during = parse_decimal(
        request.form.get("incapacity_monthly_earnings"), parse_decimal("0")
    )
    pay_mode = request.form.get("pay_mode", "four_fifths")
    if (
        not accident_date
        or not payroll_start
        or confirmed is None
        or confirmed < 0
        or during < 0
        or during > confirmed
        or (payroll_end and payroll_end < payroll_start)
        or pay_mode not in {"four_fifths", "full_pay"}
    ):
        flash("請核對工傷日期及計薪基數。", "error")
        return redirect(url_for("leave.leave_home", view="injury", employee_id=employee.id))
    if conflicting_absence(employee, payroll_start, payroll_end):
        flash("leave.overlap", "error")
        return redirect(url_for("leave.leave_home", view="injury", employee_id=employee.id))
    evidence = save_evidence(
        employee,
        request.files.get("evidence"),
        "change_evidence",
        "工傷證明",
    )
    salary = current_salary_on(employee, payroll_start)
    row = EmployeeWorkInjuryPeriod(
        employee=employee,
        accident_date=accident_date,
        payroll_start_date=payroll_start,
        payroll_end_date=payroll_end,
        confirmed_monthly_earnings=confirmed,
        incapacity_monthly_earnings=during,
        currency=request.form.get("currency")
        or (salary.currency if salary else "HKD"),
        evidence_document=evidence,
        remarks=request.form.get("remarks", "").strip() or None,
        status="active",
        pay_mode=pay_mode,
    )
    db.session.add(row)
    db.session.flush()
    write_audit(
        "work_injury_added",
        "EmployeeWorkInjuryPeriod",
        row.id,
        employee_id=employee.id,
        detail=f"{payroll_start:%Y-%m-%d} 至 {payroll_end or '至今'}",
    )
    db.session.commit()
    flash("工傷記錄已新增。", "success")
    filters = {key: request.form["back_" + key] for key in ("q", "status", "action", "project_id", "payroll_group")
               if request.form.get("back_" + key)}
    return redirect(url_for("leave.leave_home", view="injury", employee_id=employee.id,
                            year=request.form.get("entitlement_year") or None, **filters))


@employees_bp.route("/work-injuries/<int:period_id>/correct", methods=["POST"])
@login_required
def correct_work_injury(period_id):
    row = db.get_or_404(EmployeeWorkInjuryPeriod, period_id)
    accident_date = parse_date(request.form.get("accident_date"))
    payroll_start = parse_date(request.form.get("payroll_start_date"))
    payroll_end = parse_date(request.form.get("payroll_end_date"))
    confirmed = parse_decimal(request.form.get("confirmed_monthly_earnings"))
    during = parse_decimal(
        request.form.get("incapacity_monthly_earnings"), parse_decimal("0")
    )
    pay_mode = request.form.get("pay_mode", "four_fifths")
    if (
        not accident_date
        or not payroll_start
        or confirmed is None
        or confirmed < 0
        or during < 0
        or during > confirmed
        or (payroll_end and payroll_end < payroll_start)
        or pay_mode not in {"four_fifths", "full_pay"}
    ):
        flash("請核對工傷日期及計薪基數。", "error")
        return redirect(url_for("leave.leave_home", view="injury", employee_id=row.employee_id))
    if conflicting_absence(row.employee, payroll_start, payroll_end, exclude=("injury", row.id)):
        flash("leave.overlap", "error")
        return redirect(url_for("leave.leave_home", view="injury", employee_id=row.employee_id))
    before = {
        "payroll_start_date": row.payroll_start_date.isoformat(),
        "payroll_end_date": (
            row.payroll_end_date.isoformat() if row.payroll_end_date else None
        ),
        "confirmed_monthly_earnings": str(row.confirmed_monthly_earnings),
        "incapacity_monthly_earnings": str(row.incapacity_monthly_earnings),
        "pay_mode": row.pay_mode,
    }
    row.accident_date = accident_date
    row.payroll_start_date = payroll_start
    row.payroll_end_date = payroll_end
    row.confirmed_monthly_earnings = confirmed
    row.incapacity_monthly_earnings = during
    row.pay_mode = pay_mode
    row.currency = request.form.get("currency") or row.currency
    row.remarks = request.form.get("remarks", "").strip() or None
    row.status = "active"
    evidence = save_evidence(
        row.employee,
        request.files.get("evidence"),
        "change_evidence",
        "工傷證明",
    )
    if evidence:
        row.evidence_document = evidence
    write_audit(
        "work_injury_corrected",
        "EmployeeWorkInjuryPeriod",
        row.id,
        employee_id=row.employee_id,
        before=before,
        after={
            "payroll_start_date": row.payroll_start_date.isoformat(),
            "payroll_end_date": (
                row.payroll_end_date.isoformat() if row.payroll_end_date else None
            ),
            "confirmed_monthly_earnings": str(row.confirmed_monthly_earnings),
            "incapacity_monthly_earnings": str(row.incapacity_monthly_earnings),
            "pay_mode": row.pay_mode,
        },
    )
    db.session.commit()
    flash("工傷記錄已更正。", "success")
    return redirect(url_for("leave.leave_home", view="injury", employee_id=row.employee_id))


@employees_bp.route("/work-injuries/<int:period_id>/withdraw", methods=["POST"])
@login_required
def withdraw_work_injury(period_id):
    row = db.get_or_404(EmployeeWorkInjuryPeriod, period_id)
    row.status = "voided"
    write_audit(
        "work_injury_withdrawn",
        "EmployeeWorkInjuryPeriod",
        row.id,
        employee_id=row.employee_id,
        detail=request.form.get("reason", "").strip() or "撤回工傷記錄",
    )
    db.session.commit()
    flash("工傷記錄已撤回。", "success")
    return redirect(url_for("leave.leave_home", view="injury", employee_id=row.employee_id))


@employees_bp.route(
    "/work-injuries/<int:period_id>/monthly-expenses", methods=["POST"]
)
@login_required
def add_work_injury_expense(period_id):
    period = db.get_or_404(EmployeeWorkInjuryPeriod, period_id)
    year_month = request.form.get("year_month", "").strip()
    amount = parse_decimal(request.form.get("amount"))
    try:
        parse_year_month(year_month)
    except (TypeError, ValueError):
        year_month = ""
    if not year_month or amount is None or amount < 0:
        flash("請核對復診／醫療開支月份及金額。", "error")
        return redirect(url_for("leave.leave_home", view="injury", employee_id=period.employee_id))
    evidence = save_evidence(
        period.employee,
        request.files.get("evidence"),
        "change_evidence",
        f"{year_month} 工傷醫療開支",
    )
    expense = EmployeeWorkInjuryMonthlyExpense(
        employee=period.employee,
        work_injury_period=period,
        year_month=year_month,
        amount=amount,
        currency=request.form.get("currency") or period.currency or "HKD",
        evidence_document=evidence,
        remarks=request.form.get("remarks", "").strip() or None,
        status="active",
    )
    db.session.add(expense)
    db.session.flush()
    write_audit(
        "work_injury_expense_added",
        "EmployeeWorkInjuryMonthlyExpense",
        expense.id,
        employee_id=period.employee_id,
        detail=f"{year_month}: {amount}",
    )
    db.session.commit()
    flash("工傷復診／醫療開支已保存，將匯入該月工資表的 AN 欄。", "success")
    return redirect(url_for("leave.leave_home", view="injury", employee_id=period.employee_id))


@employees_bp.route(
    "/work-injury-expenses/<int:expense_id>/correct", methods=["POST"]
)
@login_required
def correct_work_injury_expense(expense_id):
    expense = db.get_or_404(EmployeeWorkInjuryMonthlyExpense, expense_id)
    year_month = request.form.get("year_month", "").strip()
    amount = parse_decimal(request.form.get("amount"))
    try:
        parse_year_month(year_month)
    except (TypeError, ValueError):
        year_month = ""
    if not year_month or amount is None or amount < 0:
        flash("請核對復診／醫療開支月份及金額。", "error")
        return redirect(url_for("leave.leave_home", view="injury", employee_id=expense.employee_id))
    before = {"year_month": expense.year_month, "amount": str(expense.amount)}
    expense.year_month = year_month
    expense.amount = amount
    expense.currency = request.form.get("currency") or expense.currency
    expense.remarks = request.form.get("remarks", "").strip() or None
    evidence = save_evidence(
        expense.employee,
        request.files.get("evidence"),
        "change_evidence",
        f"{year_month} 工傷醫療開支",
    )
    if evidence:
        expense.evidence_document = evidence
    write_audit(
        "work_injury_expense_corrected",
        "EmployeeWorkInjuryMonthlyExpense",
        expense.id,
        employee_id=expense.employee_id,
        before=before,
        after={"year_month": expense.year_month, "amount": str(expense.amount)},
    )
    db.session.commit()
    flash("工傷復診／醫療開支已更正。", "success")
    return redirect(url_for("leave.leave_home", view="injury", employee_id=expense.employee_id))


@employees_bp.route(
    "/work-injury-expenses/<int:expense_id>/withdraw", methods=["POST"]
)
@login_required
def withdraw_work_injury_expense(expense_id):
    expense = db.get_or_404(EmployeeWorkInjuryMonthlyExpense, expense_id)
    expense.status = "voided"
    write_audit(
        "work_injury_expense_withdrawn",
        "EmployeeWorkInjuryMonthlyExpense",
        expense.id,
        employee_id=expense.employee_id,
        detail=request.form.get("reason", "").strip() or "撤回工傷醫療開支",
    )
    db.session.commit()
    flash("工傷復診／醫療開支已撤回。", "success")
    return redirect(url_for("leave.leave_home", view="injury", employee_id=expense.employee_id))


@employees_bp.route("/employees/<int:employee_id>/terminate", methods=["POST"])
@login_required
def terminate_employee(employee_id):
    employee = db.get_or_404(Employee, employee_id)
    end_date = parse_date(request.form.get("end_date"))
    reason = request.form.get("reason")
    if not end_date or reason not in {item[0] for item in TERMINATION_REASONS}:
        flash("請填寫最後工作日及離職原因。", "error")
        return employee_redirect(employee.id, "employment_status")
    period = employee.current_period or ensure_current_employment_period(employee)
    before = employment_period_snapshot(period)
    evidence = replace_record_evidence(
        employee,
        period.termination_document,
        request.files.get("evidence"),
        "termination_letter",
        "離職 / 終止通知",
        "更正離職 / 終止通知",
    )
    average_wage = parse_decimal(request.form.get("average_wage"))
    if average_wage is None:
        average_wage = average_wage_prefill(employee, end_date)["average"]
    estimate = termination_estimate(
        employee,
        end_date,
        reason,
        average_wage,
    )
    period.end_date = end_date
    period.termination_reason = reason
    period.average_wage = average_wage
    period.payment_in_lieu = parse_decimal(
        request.form.get("payment_in_lieu"),
        estimate["payment_in_lieu"],
    )
    period.severance_payment = parse_decimal(
        request.form.get("severance_payment"),
        estimate["severance"],
    )
    period.long_service_payment = parse_decimal(
        request.form.get("long_service_payment"),
        estimate["long_service"],
    )
    if evidence:
        period.termination_document_id = evidence.id
    employee.status = "active" if end_date >= date.today() else "departed"
    write_audit(
        "employment_terminated",
        "EmployeeEmploymentPeriod",
        period.id,
        employee_id=employee.id,
        detail=(
            f"{'更正' if before['end_date'] else '建立'}離職資料，"
            f"最後工作日 {end_date:%Y-%m-%d}"
        ),
        before=before,
        after=employment_period_snapshot(period),
    )
    db.session.commit()
    flash("離職資料已保存。估算金額仍須由 HR 核對。", "success")
    return employee_redirect(employee.id, "employment_status")


@employees_bp.route(
    "/employees/<int:employee_id>/termination/cancel",
    methods=["POST"],
)
@login_required
def cancel_termination(employee_id):
    employee = db.get_or_404(Employee, employee_id)
    period = employee.current_period
    if not period or not period.end_date:
        flash("目前沒有可撤回的離職記錄。", "info")
        return employee_redirect(employee.id, "employment_status")
    old_end_date = period.end_date
    before = employment_period_snapshot(period)
    period.end_date = None
    period.termination_reason = None
    period.average_wage = None
    period.payment_in_lieu = None
    period.severance_payment = None
    period.long_service_payment = None
    period.termination_document_id = None
    employee.status = "active"
    write_audit(
        "employment_termination_cancelled",
        "EmployeeEmploymentPeriod",
        period.id,
        employee_id=employee.id,
        detail=f"撤回原定 {old_end_date:%Y-%m-%d} 的離職資料",
        before=before,
        after=employment_period_snapshot(period),
    )
    db.session.commit()
    flash("離職資料已撤回，員工保持在職。", "success")
    return employee_redirect(employee.id, "employment_status")


@employees_bp.route("/employees/<int:employee_id>/rehire", methods=["POST"])
@login_required
def rehire_employee(employee_id):
    employee = db.get_or_404(Employee, employee_id)
    start_date = parse_date(request.form.get("start_date"))
    if not start_date:
        flash("請填寫重新入職日期。", "error")
        return employee_redirect(employee.id, "employment_status")
    period = EmployeeEmploymentPeriod(employee=employee, start_date=start_date)
    db.session.add(period)
    db.session.flush()
    employee.status = "active"
    write_audit(
        "employee_rehired",
        "EmployeeEmploymentPeriod",
        period.id,
        employee_id=employee.id,
        detail=f"重新入職 {start_date:%Y-%m-%d}",
        after=employment_period_snapshot(period),
    )
    db.session.commit()
    flash("已使用原員工編號建立新的任職期間。", "success")
    return employee_redirect(employee.id, "employment_status")


@employees_bp.route("/employees/<int:employee_id>/delete", methods=["POST"])
@login_required
def delete_employee(employee_id):
    if current_user.role != "admin":
        abort(403)
    employee = db.get_or_404(Employee, employee_id)
    if request.form.get("confirm_employee_no", "").strip() != employee.employee_no:
        flash("employee.delete_confirmation_failed", "error")
        return employee_redirect(employee.id, "employment")
    employee_no = employee.employee_no
    upload_folder = employee_files_path(employee)
    summary_ids = [item.id for item in employee.attendance_summaries]
    batch_items = AttendanceBatchItem.query.filter(
        (AttendanceBatchItem.employee_id == employee.id)
        | (AttendanceBatchItem.summary_id.in_(summary_ids))
    ).all()
    batch_ids = {item.batch_id for item in batch_items}
    batch_paths = [Path(item.stored_path) for item in batch_items]
    batch_folders = {path.parent for path in batch_paths}
    payroll_run_ids = {item.run_id for item in employee.payroll_results}
    generated_paths = [
        Path(contract.output_path) for contract in employee.generated_contracts
    ]
    for item in batch_items:
        db.session.delete(item)
    AuditLog.query.filter_by(employee_id=employee.id).delete(
        synchronize_session=False
    )
    db.session.delete(employee)
    db.session.flush()
    for batch_id in batch_ids:
        if not AttendanceBatchItem.query.filter_by(batch_id=batch_id).first():
            batch = db.session.get(AttendanceBatch, batch_id)
            if batch:
                db.session.delete(batch)
    for run_id in payroll_run_ids:
        run = db.session.get(PayrollRun, run_id)
        if run and not PayrollEmployeeResult.query.filter_by(
            run_id=run_id
        ).first():
            db.session.delete(run)
    write_audit(
        "employee_deleted",
        "Employee",
        employee.id,
        detail=f"刪除員工檔案 {employee_no}",
    )
    db.session.commit()
    for path in generated_paths + batch_paths:
        if path.is_file():
            path.unlink()
    for folder in batch_folders:
        if folder.is_dir() and not any(folder.iterdir()):
            folder.rmdir()
    delete_employee_files(folder=upload_folder)
    flash(f"員工 {employee_no}、考勤及工資表資料已全部刪除。", "success")
    return redirect(url_for("employees.list_employees"))
