import csv
import io
from datetime import date
from decimal import Decimal

from flask import (
    Blueprint,
    Response,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required

from models import (
    AttendanceSegment,
    Employee,
    EmployeeAllowance,
    EmployeeAssignment,
    EmployeeAssignmentPosition,
    EmployeeCertificate,
    EmployeeBankAccount,
    EmployeeDocument,
    EmployeeMpfEnrollment,
    EmployeeSalary,
    EmployeeVisa,
    MpfScheme,
    PayrollAdjustment,
    PayrollProjectLine,
    ReferenceList,
    ReferenceValue,
    SalaryRecord,
    WorkProject,
    WorkCalendarHoliday,
    db,
)
from tools.hr_core import (
    REFERENCE_LISTS,
    current_assignment_on,
    current_bank_account_on,
    current_mpf_on,
    current_salary_on,
    normalize_reference_display,
    parse_decimal,
    parse_date,
    reference_sort_key,
    reference_sort_order,
    slug_code,
    write_audit,
)
from tools.hk_statutory_holidays import (
    HolidayImportError,
    PUBLIC_SOURCE_URL_TEMPLATE,
    SOURCE_URL_TEMPLATE,
    fetch_hong_kong_public_holidays,
    fetch_hong_kong_statutory_holidays,
)


references_bp = Blueprint("references", __name__)


def work_calendar_scope(value):
    scope = (value or "").strip()
    if scope not in {"statutory", "public", "both"}:
        return None
    return scope


def set_work_calendar_scope(item, scope):
    item.applies_to_statutory = scope in {"statutory", "both"}
    item.applies_to_public = scope in {"public", "both"}


def work_calendar_scope_value(item):
    if item.applies_to_statutory and item.applies_to_public:
        return "both"
    return "public" if item.applies_to_public else "statutory"


class ReferenceCodeConflict(ValueError):
    def __init__(self, existing):
        super().__init__(existing.display_name)
        self.existing = existing

REFERENCE_NAV_GROUPS = (
    (
        "organization",
        (
            "work_region",
            "department",
            "employer",
            "payroll_entity",
            "social_insurance_entity",
            "labour_dispatch_entity",
        ),
    ),
    (
        "employment",
        (
            "employee_type",
            "position",
            "visa_category",
            "certificate_type",
            "education_level",
        ),
    ),
    (
        "finance_contact",
        ("bank", "currency", "phone_region"),
    ),
    (
        "documents",
        ("general_document_type",),
    ),
)

QUICK_REFERENCE_CODES = {
    "bank",
    "certificate_type",
    "currency",
    "department",
    "education_level",
    "employer",
    "labour_dispatch_entity",
    "payroll_entity",
    "position",
    "social_insurance_entity",
    "visa_category",
    "work_region",
}


def editor_allowed():
    return current_user.role in {"admin", "hr"}


def safe_return_to(value):
    candidate = str(value or "").strip()
    if candidate.startswith("/") and not candidate.startswith("//"):
        return candidate
    return None


def references_redirect(list_code):
    return_to = safe_return_to(
        request.form.get("return_to") or request.args.get("return_to")
    )
    return redirect(
        url_for(
            "references.references_home",
            list=list_code,
            **({"return_to": return_to} if return_to else {}),
        )
    )


def ensure_reference_value(ref_list, display_name, remarks=None):
    normalized = display_name.casefold()
    existing = ReferenceValue.query.filter_by(
        list_id=ref_list.id,
        normalized_name=normalized,
    ).first()
    if existing:
        reactivated = not existing.active
        existing.active = True
        if reactivated:
            write_audit(
                "reference_updated",
                "ReferenceValue",
                existing.id,
                detail=f"重新啟用 {ref_list.label}: {existing.display_name}",
                before={"active": False},
                after={"active": True},
            )
        return existing, False, reactivated

    generated_code = slug_code(display_name)
    code_match = ReferenceValue.query.filter_by(
        list_id=ref_list.id,
        code=generated_code,
    ).first()
    if code_match:
        raise ReferenceCodeConflict(code_match)

    value = ReferenceValue(
        reference_list=ref_list,
        code=generated_code,
        display_name=display_name,
        normalized_name=normalized,
        active=True,
        remarks=remarks,
    )
    db.session.add(value)
    db.session.flush()
    write_audit(
        "reference_created",
        "ReferenceValue",
        value.id,
        detail=f"{ref_list.label}: {display_name}",
    )
    return value, True, False


def usage_query(value):
    code = value.reference_list.code
    mapping = {
        "employee_type": (Employee, Employee.employee_type_id),
        "work_region": (EmployeeAssignment, EmployeeAssignment.region_id),
        "department": (EmployeeAssignment, EmployeeAssignment.department_id),
        "employer": (EmployeeAssignment, EmployeeAssignment.employer_id),
        "payroll_entity": (
            EmployeeAssignment,
            EmployeeAssignment.payroll_entity_id,
        ),
        "social_insurance_entity": (
            EmployeeAssignment,
            EmployeeAssignment.social_insurance_entity_id,
        ),
        "labour_dispatch_entity": (
            EmployeeAssignment,
            EmployeeAssignment.labour_dispatch_entity_id,
        ),
        "position": (
            EmployeeAssignmentPosition,
            EmployeeAssignmentPosition.position_id,
        ),
        "visa_category": (EmployeeVisa, EmployeeVisa.visa_category_id),
        "certificate_type": (
            EmployeeCertificate,
            EmployeeCertificate.certificate_type_id,
        ),
        "general_document_type": (
            EmployeeDocument,
            EmployeeDocument.general_document_type_id,
        ),
    }
    if code in mapping:
        model, column = mapping[code]
        return model.query.filter(column == value.id)
    if code == "bank":
        return Employee.query.filter(Employee.bank_name == value.display_name)
    if code == "education_level":
        return Employee.query.filter(
            Employee.education_level == value.display_name
        )
    if code == "currency":
        return EmployeeSalary.query.filter(EmployeeSalary.currency == value.code)
    return None


def usage_count(value):
    code = value.reference_list.code
    if code == 'payroll_entity':
        return usage_query(value).count() + SalaryRecord.query.filter_by(payroll_entity_id=value.id).count()
    if code == "bank":
        return (
            Employee.query.filter(Employee.bank_name == value.display_name).count()
            + EmployeeBankAccount.query.filter(
                EmployeeBankAccount.bank_name == value.display_name
            ).count()
        )
    if code == "phone_region":
        return Employee.query.filter(
            db.or_(
                Employee.mobile_region_code == value.code,
                Employee.emergency_contact_region_code == value.code,
            )
        ).count()
    if code == "currency":
        return (
            EmployeeSalary.query.filter(EmployeeSalary.currency == value.code).count()
            + EmployeeAllowance.query.filter(
                EmployeeAllowance.currency == value.code
            ).count()
            + SalaryRecord.query.filter_by(currency=value.code).count()
        )
    query = usage_query(value)
    return query.count() if query is not None else 0


def employee_link(employee):
    return {
        "id": employee.id,
        "employee_no": employee.employee_no,
        "display_name": employee.display_name,
        "status": employee.status,
    }


def current_reference_employee_ids(value, employees, on_date):
    code = value.reference_list.code
    ids = set()
    for employee in employees:
        assignment = current_assignment_on(employee, on_date)
        salary = current_salary_on(employee, on_date)
        if code == "employee_type" and employee.employee_type_id == value.id:
            ids.add(employee.id)
        elif code in {
            "work_region",
            "department",
            "employer",
            "payroll_entity",
            "social_insurance_entity",
            "labour_dispatch_entity",
        } and assignment and getattr(
            assignment,
            {
                "work_region": "region_id",
                "department": "department_id",
                "employer": "employer_id",
                "payroll_entity": "payroll_entity_id",
                "social_insurance_entity": "social_insurance_entity_id",
                "labour_dispatch_entity": "labour_dispatch_entity_id",
            }[code],
            None,
        ) == value.id:
            ids.add(employee.id)
        elif code == "position" and assignment and any(
            item.position_id == value.id for item in assignment.positions
        ):
            ids.add(employee.id)
        elif code == "visa_category" and any(
            item.status == "active" and item.visa_category_id == value.id
            for item in employee.visas
        ):
            ids.add(employee.id)
        elif code == "certificate_type" and any(
            item.status == "active" and item.certificate_type_id == value.id
            for item in employee.certificates
        ):
            ids.add(employee.id)
        elif code == "general_document_type" and any(
            item.status == "active"
            and item.general_document_type_id == value.id
            for item in employee.documents
        ):
            ids.add(employee.id)
        elif code == "bank" and (
            employee.bank_name == value.display_name
            or (
                (bank := current_bank_account_on(employee, on_date))
                and bank.bank_name == value.display_name
            )
        ):
            ids.add(employee.id)
        elif code == "education_level" and employee.education_level == value.display_name:
            ids.add(employee.id)
        elif code == "currency" and salary and salary.currency == value.code:
            ids.add(employee.id)
        elif code == "phone_region" and value.code in {
            employee.mobile_region_code,
            employee.emergency_contact_region_code,
        }:
            ids.add(employee.id)
    return ids


def historical_reference_employee_ids(value):
    code = value.reference_list.code
    if code in {'payroll_entity','currency'}:
        query = usage_query(value)
        ids = {row.employee_id for row in query.all()} if query is not None else set()
        column = SalaryRecord.payroll_entity_id if code == 'payroll_entity' else SalaryRecord.currency
        return ids | {row.employee_id for row in SalaryRecord.query.filter(column == (value.id if code == 'payroll_entity' else value.code)).all()}
    if code == "bank":
        return {
            row.employee_id
            for row in EmployeeBankAccount.query.filter_by(
                bank_name=value.display_name
            ).all()
        } | {
            row.id
            for row in Employee.query.filter_by(
                bank_name=value.display_name
            ).all()
        }
    if code == "phone_region":
        return {
            row.id
            for row in Employee.query.filter(
                db.or_(
                    Employee.mobile_region_code == value.code,
                    Employee.emergency_contact_region_code == value.code,
                )
            ).all()
        }
    query = usage_query(value)
    if query is None:
        return set()
    ids = set()
    for row in query.all():
        if isinstance(row, Employee):
            ids.add(row.id)
        elif hasattr(row, "employee_id"):
            ids.add(row.employee_id)
        elif hasattr(row, "assignment") and row.assignment:
            ids.add(row.assignment.employee_id)
    return ids


def missing_employee_ids(selected_code, employees, on_date):
    ids = set()
    for employee in employees:
        assignment = current_assignment_on(employee, on_date)
        if selected_code == "projects":
            if (
                assignment
                and assignment.payroll_group in {"site_daily", "site_monthly"}
                and not assignment.project_id
            ):
                ids.add(employee.id)
        elif selected_code in {
            "work_region",
            "department",
            "employer",
            "payroll_entity",
        }:
            field = {
                "work_region": "region_id",
                "department": "department_id",
                "employer": "employer_id",
                "payroll_entity": "payroll_entity_id",
            }[selected_code]
            if not assignment or not getattr(assignment, field):
                ids.add(employee.id)
        elif selected_code == "position":
            if not assignment or not assignment.positions:
                ids.add(employee.id)
        elif selected_code == "bank" and not (
            employee.bank_name and employee.bank_account_no
        ):
            ids.add(employee.id)
    return ids


def propagate_text_usage(value, old_name):
    code = value.reference_list.code
    if code == "bank":
        Employee.query.filter(Employee.bank_name == old_name).update(
            {"bank_name": value.display_name},
            synchronize_session=False,
        )
    elif code == "education_level":
        Employee.query.filter(Employee.education_level == old_name).update(
            {"education_level": value.display_name},
            synchronize_session=False,
        )


def quick_value_payload(value):
    return {
        "id": value.id,
        "code": value.code,
        "display_name": value.display_name,
    }


@references_bp.route("/references/quick-options/<string:list_code>")
@login_required
def quick_options(list_code):
    if list_code == "projects":
        projects = WorkProject.query.filter_by(active=True).order_by(
            WorkProject.name.asc()
        ).all()
        return jsonify(
            {
                "items": [
                    {
                        "id": item.id,
                        "code": item.code,
                        "display_name": item.name,
                        "region_id": item.region_id,
                        "daily_ot_divisor": str(item.daily_ot_divisor),
                    }
                    for item in projects
                ]
            }
        )
    if list_code not in QUICK_REFERENCE_CODES:
        abort(404)
    ref_list = ReferenceList.query.filter_by(code=list_code).first_or_404()
    values = ReferenceValue.query.filter_by(
        list_id=ref_list.id,
        active=True,
    ).order_by(ReferenceValue.display_name.asc()).all()
    return jsonify({"items": [quick_value_payload(item) for item in values]})


@references_bp.route("/references/quick-create", methods=["POST"])
@login_required
def quick_create_value():
    if not editor_allowed():
        abort(403)
    payload = request.get_json(silent=True) or request.form
    list_code = str(payload.get("list_code") or "").strip()
    if list_code not in QUICK_REFERENCE_CODES:
        return jsonify({"ok": False, "error": "此清單不支援快速新增。"}), 400
    ref_list = ReferenceList.query.filter_by(code=list_code).first()
    if not ref_list:
        return jsonify({"ok": False, "error": "找不到基礎資料清單。"}), 404
    display_name = normalize_reference_display(payload.get("display_name"))
    if not display_name:
        return jsonify({"ok": False, "error": "請填寫名稱。"}), 400
    try:
        value, created, reactivated = ensure_reference_value(
            ref_list,
            display_name,
            str(payload.get("remarks") or "").strip() or None,
        )
    except ReferenceCodeConflict as conflict:
        return jsonify(
            {
                "ok": False,
                "error_code": "reference_code_exists",
                "existing_item": quick_value_payload(conflict.existing),
            }
        ), 409
    db.session.commit()
    return jsonify(
        {
            "ok": True,
            "item": quick_value_payload(value),
            "created": created,
            "reactivated": reactivated,
        }
    )


@references_bp.route("/references/projects/quick-create", methods=["POST"])
@login_required
def quick_create_project():
    if not editor_allowed():
        abort(403)
    payload = request.get_json(silent=True) or request.form
    name = normalize_reference_display(payload.get("name"))
    if not name:
        return jsonify({"ok": False, "error": "請填寫項目名稱。"}), 400
    existing = next(
        (
            item
            for item in WorkProject.query.order_by(WorkProject.id.asc()).all()
            if item.name.casefold() == name.casefold()
        ),
        None,
    )
    if existing:
        reactivated = not existing.active
        existing.active = True
        if reactivated:
            write_audit(
                "project_updated",
                "WorkProject",
                existing.id,
                detail=f"重新啟用項目: {existing.name}",
                before={"active": False},
                after={"active": True},
            )
        db.session.commit()
        return jsonify(
            {
                "ok": True,
                "item": {
                    "id": existing.id,
                    "code": existing.code,
                    "display_name": existing.name,
                    "region_id": existing.region_id,
                    "daily_ot_divisor": str(existing.daily_ot_divisor),
                },
                "created": False,
                "reactivated": reactivated,
            }
        )

    region_id = payload.get("region_id")
    region = None
    if str(region_id or "").isdigit():
        region = db.session.get(ReferenceValue, int(region_id))
        if not region or region.reference_list.code != "work_region":
            return jsonify({"ok": False, "error": "工作地區無效。"}), 400
    raw_divisor = str(payload.get("daily_ot_divisor") or "").strip()
    divisor = parse_decimal(raw_divisor) if raw_divisor else Decimal("9")
    if divisor is None or divisor <= 0:
        return jsonify({"ok": False, "error": "日工 OT 除數必須大於 0。"}), 400
    base_code = slug_code(name)
    code = base_code
    suffix = 2
    while WorkProject.query.filter_by(code=code).first():
        code = f"{base_code}_{suffix}"
        suffix += 1
    project = WorkProject(
        code=code,
        name=name,
        region_id=region.id if region else None,
        daily_ot_divisor=divisor,
        active=True,
    )
    db.session.add(project)
    db.session.flush()
    write_audit(
        "project_created",
        "WorkProject",
        project.id,
        detail=project.name,
    )
    db.session.commit()
    return jsonify(
        {
            "ok": True,
            "item": {
                "id": project.id,
                "code": project.code,
                "display_name": project.name,
                "region_id": project.region_id,
                "daily_ot_divisor": str(project.daily_ot_divisor),
            },
            "created": True,
            "reactivated": False,
        }
    )


@references_bp.route("/references")
@login_required
def references_home():
    lists = ReferenceList.query.order_by(ReferenceList.label.asc()).all()
    list_map = {item.code: item for item in lists}
    selected_code = request.args.get("list") or "projects"
    selected = ReferenceList.query.filter_by(code=selected_code).first()
    values = (
        sorted(
            ReferenceValue.query.filter_by(list_id=selected.id)
            .order_by(ReferenceValue.display_name.asc())
            .all(),
            key=lambda item: reference_sort_key(selected.code, item),
        )
        if selected
        else []
    )
    counts = {value.id: usage_count(value) for value in values}
    projects = (
        WorkProject.query.filter(WorkProject.code != "UNASSIGNED")
        .order_by(WorkProject.name.asc())
        .all()
    )
    mpf_schemes = MpfScheme.query.order_by(MpfScheme.name.asc()).all()
    mpf_scheme_counts = {
        scheme.id: EmployeeMpfEnrollment.query.filter_by(
            scheme_id=scheme.id,
        ).count()
        for scheme in mpf_schemes
    }
    project_counts = {}
    for project in projects:
        project_counts[project.id] = sum(
            (
                EmployeeAssignment.query.filter_by(
                    project_id=project.id
                ).count(),
                AttendanceSegment.query.filter_by(
                    project_id=project.id
                ).count(),
                PayrollAdjustment.query.filter_by(
                    project_id=project.id
                ).count(),
                EmployeeAllowance.query.filter_by(
                    project_id=project.id
                ).count(),
                PayrollProjectLine.query.filter_by(
                    project_id=project.id
                ).count(),
            )
        )
    today = date.today()
    all_employees = Employee.query.order_by(Employee.employee_no.asc()).all()
    active_employees = [
        employee for employee in all_employees if employee.is_active_on(today)
    ]
    employees_by_id = {employee.id: employee for employee in all_employees}
    current_employee_links = {}
    historical_employee_links = {}
    for value in values:
        current_ids = current_reference_employee_ids(
            value,
            active_employees,
            today,
        )
        history_ids = historical_reference_employee_ids(value) - current_ids
        current_employee_links[value.id] = [
            employee_link(employees_by_id[item_id])
            for item_id in sorted(current_ids)
            if item_id in employees_by_id
        ]
        historical_employee_links[value.id] = [
            employee_link(employees_by_id[item_id])
            for item_id in sorted(history_ids)
            if item_id in employees_by_id
        ]
    project_employee_links = {}
    project_historical_links = {}
    for project in projects:
        current_ids = {
            employee.id
            for employee in active_employees
            if (
                (assignment := current_assignment_on(employee, today))
                and assignment.project_id == project.id
            )
        }
        historical_ids = {
            row.employee_id
            for row in EmployeeAssignment.query.filter_by(
                project_id=project.id
            ).all()
        } - current_ids
        project_employee_links[project.id] = [
            employee_link(employees_by_id[item_id])
            for item_id in sorted(current_ids)
            if item_id in employees_by_id
        ]
        project_historical_links[project.id] = [
            employee_link(employees_by_id[item_id])
            for item_id in sorted(historical_ids)
            if item_id in employees_by_id
        ]
    mpf_employee_links = {}
    mpf_historical_links = {}
    for scheme in mpf_schemes:
        current_ids = {
            employee.id
            for employee in active_employees
            if (
                (enrollment := current_mpf_on(employee, today))
                and enrollment.scheme_id == scheme.id
            )
        }
        historical_ids = {
            row.employee_id
            for row in EmployeeMpfEnrollment.query.filter_by(
                scheme_id=scheme.id
            ).all()
        } - current_ids
        mpf_employee_links[scheme.id] = [
            employee_link(employees_by_id[item_id])
            for item_id in sorted(current_ids)
            if item_id in employees_by_id
        ]
        mpf_historical_links[scheme.id] = [
            employee_link(employees_by_id[item_id])
            for item_id in sorted(historical_ids)
            if item_id in employees_by_id
        ]
    missing_ids = missing_employee_ids(selected_code, active_employees, today)
    missing_employees = [
        employee_link(employees_by_id[item_id])
        for item_id in sorted(missing_ids)
        if item_id in employees_by_id
    ]
    calendar_year = request.args.get("calendar_year", type=int) or today.year
    calendar_region_id = request.args.get("calendar_region_id", type=int)
    calendar_query = WorkCalendarHoliday.query.filter(
        db.extract("year", WorkCalendarHoliday.holiday_date) == calendar_year
    )
    if calendar_region_id:
        calendar_query = calendar_query.filter_by(region_id=calendar_region_id)
    calendar_holidays = calendar_query.order_by(
        WorkCalendarHoliday.holiday_date.asc()
    ).all()
    regions = (
        ReferenceValue.query.join(ReferenceList)
        .filter(
            ReferenceList.code == "work_region",
            ReferenceValue.active.is_(True),
        )
        .order_by(ReferenceValue.display_name)
        .all()
    )
    calendar_import_year = today.year + 1
    hong_kong_region = next(
        (region for region in regions if region.code == "HK"),
        None,
    )
    calendar_import_existing_count = 0
    if hong_kong_region:
        calendar_import_existing_count = WorkCalendarHoliday.query.filter_by(
            region_id=hong_kong_region.id,
        ).filter(
            db.extract("year", WorkCalendarHoliday.holiday_date)
            == calendar_import_year
        ).count()
    nav_groups = [
        (
            group_code,
            [list_map[code] for code in codes if code in list_map],
        )
        for group_code, codes in REFERENCE_NAV_GROUPS
    ]
    return render_template(
        "references/index.html",
        lists=lists,
        nav_groups=nav_groups,
        selected=selected,
        values=values,
        usage_counts=counts,
        projects=projects,
        mpf_schemes=mpf_schemes,
        mpf_scheme_counts=mpf_scheme_counts,
        project_counts=project_counts,
        current_employee_links=current_employee_links,
        historical_employee_links=historical_employee_links,
        project_employee_links=project_employee_links,
        project_historical_links=project_historical_links,
        mpf_employee_links=mpf_employee_links,
        mpf_historical_links=mpf_historical_links,
        missing_employees=missing_employees,
        calendar_holidays=calendar_holidays,
        calendar_year=calendar_year,
        calendar_import_year=calendar_import_year,
        calendar_import_existing_count=calendar_import_existing_count,
        calendar_region_id=calendar_region_id,
        regions=regions,
        selected_code=selected_code,
        reference_sort_order=reference_sort_order,
        can_edit=editor_allowed(),
        return_to=safe_return_to(request.args.get("return_to")),
    )


def mpf_scheme_values():
    name = normalize_reference_display(request.form.get("name"))
    employer_account_no = (request.form.get("employer_account_no") or "").strip()
    payroll_group_no = (request.form.get("payroll_group_no") or "").strip() or None
    if payroll_group_no and payroll_group_no.upper() == "N/A":
        payroll_group_no = None
    calculation_mode = request.form.get("calculation_mode")
    if not name or not employer_account_no:
        raise ValueError("請填寫 MPF 計劃名稱及僱主帳戶號碼。")
    if calculation_mode not in {"regular", "casual"}:
        raise ValueError("請選擇供款計算方式。")
    return name, employer_account_no, payroll_group_no, calculation_mode


@references_bp.route("/references/mpf-schemes", methods=["POST"])
@login_required
def create_mpf_scheme():
    if not editor_allowed():
        abort(403)
    try:
        name, employer_no, group_no, mode = mpf_scheme_values()
    except ValueError as exc:
        flash(str(exc), "error")
        return references_redirect("mpf_schemes")
    if MpfScheme.query.filter(MpfScheme.name.ilike(name)).first():
        flash(f"已有相同 MPF 計劃「{name}」。", "error")
        return references_redirect("mpf_schemes")
    base_code = slug_code(name)
    code = base_code
    suffix = 2
    while MpfScheme.query.filter_by(code=code).first():
        code = f"{base_code}_{suffix}"
        suffix += 1
    scheme = MpfScheme(
        code=code,
        name=name,
        employer_account_no=employer_no,
        payroll_group_no=group_no,
        calculation_mode=mode,
        active=True,
    )
    db.session.add(scheme)
    db.session.flush()
    write_audit("mpf_scheme_created", "MpfScheme", scheme.id, detail=name)
    db.session.commit()
    flash("MPF 計劃已新增。", "success")
    return references_redirect("mpf_schemes")


@references_bp.route("/references/mpf-schemes/<int:scheme_id>", methods=["POST"])
@login_required
def update_mpf_scheme(scheme_id):
    if not editor_allowed():
        abort(403)
    scheme = db.get_or_404(MpfScheme, scheme_id)
    try:
        name, employer_no, group_no, mode = mpf_scheme_values()
    except ValueError as exc:
        flash(str(exc), "error")
        return references_redirect("mpf_schemes")
    duplicate = MpfScheme.query.filter(
        MpfScheme.name.ilike(name),
        MpfScheme.id != scheme.id,
    ).first()
    if duplicate:
        flash(f"已有相同 MPF 計劃「{duplicate.name}」。", "error")
        return references_redirect("mpf_schemes")
    before = {
        "name": scheme.name,
        "employer_account_no": scheme.employer_account_no,
        "payroll_group_no": scheme.payroll_group_no,
        "calculation_mode": scheme.calculation_mode,
        "active": scheme.active,
    }
    scheme.name = name
    scheme.employer_account_no = employer_no
    scheme.payroll_group_no = group_no
    scheme.calculation_mode = mode
    write_audit(
        "mpf_scheme_updated",
        "MpfScheme",
        scheme.id,
        detail=name,
        before=before,
        after={
            "name": name,
            "employer_account_no": employer_no,
            "payroll_group_no": group_no,
            "calculation_mode": mode,
            "active": scheme.active,
        },
    )
    db.session.commit()
    flash("MPF 計劃已保存；員工資料會同步顯示新內容。", "success")
    return references_redirect("mpf_schemes")


@references_bp.route(
    "/references/mpf-schemes/<int:scheme_id>/delete",
    methods=["POST"],
)
@login_required
def delete_mpf_scheme(scheme_id):
    if not editor_allowed():
        abort(403)
    scheme = db.get_or_404(MpfScheme, scheme_id)
    count = EmployeeMpfEnrollment.query.filter_by(scheme_id=scheme.id).count()
    if count:
        flash(f"此 MPF 計劃仍被 {count} 筆員工記錄使用，不能刪除。", "error")
    else:
        write_audit("mpf_scheme_deleted", "MpfScheme", scheme.id, detail=scheme.name)
        db.session.delete(scheme)
        db.session.commit()
        flash("MPF 計劃已刪除。", "success")
    return references_redirect("mpf_schemes")


def _apply_sort_order(value, raw_value):
    meta = dict(value.metadata_json) if isinstance(value.metadata_json, dict) else {}
    raw_text = (raw_value or "").strip()
    if not raw_text:
        meta.pop("sort_order", None)
        value.metadata_json = meta or None
        return
    try:
        parsed = int(raw_text)
    except ValueError:
        return
    if 0 <= parsed <= 9999:
        meta["sort_order"] = parsed
        value.metadata_json = meta


@references_bp.route("/references/<int:list_id>/values", methods=["POST"])
@login_required
def create_value(list_id):
    if not editor_allowed():
        abort(403)
    ref_list = db.get_or_404(ReferenceList, list_id)
    display_name = normalize_reference_display(
        request.form.get("display_name")
    )
    if not display_name:
        flash("請填寫名稱。", "error")
    else:
        try:
            value, created, reactivated = ensure_reference_value(
                ref_list,
                display_name,
                request.form.get("remarks", "").strip() or None,
            )
        except ReferenceCodeConflict as conflict:
            flash(
                f"已有相同選項「{conflict.existing.display_name}」，請直接選擇。",
                "info",
            )
        else:
            if ref_list.code == "department" and (created or reactivated):
                _apply_sort_order(value, request.form.get("sort_order"))
            if created:
                flash("選項已新增。", "success")
            elif reactivated:
                flash("已有相同選項，已重新啟用。", "info")
            else:
                flash("已有相同選項。", "info")
            db.session.commit()
    return references_redirect(ref_list.code)


@references_bp.route("/references/values/<int:value_id>", methods=["POST"])
@login_required
def update_value(value_id):
    if not editor_allowed():
        abort(403)
    value = db.get_or_404(ReferenceValue, value_id)
    old_name = value.display_name
    display_name = normalize_reference_display(
        request.form.get("display_name")
    )
    if not display_name:
        flash("名稱不能留空。", "error")
    else:
        duplicate = ReferenceValue.query.filter(
            ReferenceValue.list_id == value.list_id,
            ReferenceValue.normalized_name == display_name.casefold(),
            ReferenceValue.id != value.id,
        ).first()
        if duplicate:
            flash("此清單已有相同名稱。", "error")
        else:
            before_sort = (
                value.metadata_json.get("sort_order")
                if isinstance(value.metadata_json, dict)
                else None
            )
            before = {"display_name": old_name, "active": value.active}
            if before_sort is not None:
                before["sort_order"] = before_sort
            value.display_name = display_name
            value.normalized_name = display_name.casefold()
            value.remarks = request.form.get("remarks", "").strip() or None
            if value.reference_list.code == "department":
                _apply_sort_order(value, request.form.get("sort_order"))
            after_sort = (
                value.metadata_json.get("sort_order")
                if isinstance(value.metadata_json, dict)
                else None
            )
            after = {
                "display_name": display_name,
                "active": value.active,
            }
            if after_sort is not None:
                after["sort_order"] = after_sort
            propagate_text_usage(value, old_name)
            write_audit(
                "reference_updated",
                "ReferenceValue",
                value.id,
                detail=f"{old_name} → {display_name}",
                before=before,
                after=after,
            )
            db.session.commit()
            flash(
                f"選項已修改；{usage_count(value)} 筆引用同步顯示新名稱。",
                "success",
            )
    return references_redirect(value.reference_list.code)


@references_bp.route("/references/values/<int:value_id>/delete", methods=["POST"])
@login_required
def delete_value(value_id):
    if not editor_allowed():
        abort(403)
    value = db.get_or_404(ReferenceValue, value_id)
    code = value.reference_list.code
    count = usage_count(value)
    if count:
        flash(
            f"此選項仍被 {count} 筆資料引用，不能刪除；如不再使用，請關閉「可供新資料選用」。",
            "error",
        )
    else:
        write_audit(
            "reference_deleted",
            "ReferenceValue",
            value.id,
            detail=value.display_name,
        )
        db.session.delete(value)
        db.session.commit()
        flash("選項已刪除。", "success")
    return references_redirect(code)


@references_bp.route("/references/projects", methods=["POST"])
@login_required
def create_project():
    if not editor_allowed():
        abort(403)
    name = normalize_reference_display(request.form.get("name"))
    code = slug_code(request.form.get("code") or name)
    if not name:
        flash("請填寫項目名稱。", "error")
    elif WorkProject.query.filter(
        (WorkProject.code == code) | (WorkProject.name == name)
    ).first():
        flash("項目代碼或名稱已存在。", "error")
    else:
        project = WorkProject(
            code=code,
            name=name,
            region_id=request.form.get("region_id", type=int),
            work_location=request.form.get("work_location", "").strip()
            or None,
            contact_name=request.form.get("contact_name", "").strip() or None,
            contact_phone=request.form.get("contact_phone", "").strip() or None,
            daily_ot_divisor=parse_decimal(
                request.form.get("daily_ot_divisor"),
                Decimal("9"),
            ),
            active=True,
        )
        db.session.add(project)
        db.session.flush()
        write_audit(
            "project_created",
            "WorkProject",
            project.id,
            detail=name,
        )
        db.session.commit()
        flash("項目已新增。", "success")
    return references_redirect("projects")


@references_bp.route("/references/projects/<int:project_id>", methods=["POST"])
@login_required
def update_project(project_id):
    if not editor_allowed():
        abort(403)
    project = db.get_or_404(WorkProject, project_id)
    old_name = project.name
    project.name = normalize_reference_display(request.form.get("name"))
    project.region_id = request.form.get("region_id", type=int)
    project.work_location = (
        request.form.get("work_location", "").strip() or None
    )
    project.contact_name = (
        request.form.get("contact_name", "").strip() or None
    )
    project.contact_phone = (
        request.form.get("contact_phone", "").strip() or None
    )
    project.daily_ot_divisor = parse_decimal(
        request.form.get("daily_ot_divisor"),
        Decimal("9"),
    )
    write_audit(
        "project_updated",
        "WorkProject",
        project.id,
        detail=f"{old_name} → {project.name}",
    )
    db.session.commit()
    flash("項目已更新，既有員工與考勤引用會同步顯示新名稱。", "success")
    return references_redirect("projects")


def set_archive_state(item, active, entity_name, display_name, return_code):
    before = {"active": item.active}
    item.active = active
    write_audit(
        f"{entity_name}_{'restored' if active else 'archived'}",
        type(item).__name__,
        item.id,
        detail=display_name,
        before=before,
        after={"active": active},
    )
    db.session.commit()
    flash("選項已恢復使用。" if active else "選項已封存；既有及歷史資料不受影響。", "success")
    return references_redirect(return_code)


@references_bp.route("/references/values/<int:value_id>/archive", methods=["POST"])
@login_required
def archive_value(value_id):
    if not editor_allowed():
        abort(403)
    value = db.get_or_404(ReferenceValue, value_id)
    return set_archive_state(
        value,
        request.form.get("action") == "restore",
        "reference",
        value.display_name,
        value.reference_list.code,
    )


@references_bp.route("/references/projects/<int:project_id>/archive", methods=["POST"])
@login_required
def archive_project(project_id):
    if not editor_allowed():
        abort(403)
    project = db.get_or_404(WorkProject, project_id)
    if project.code == "UNASSIGNED":
        abort(400)
    return set_archive_state(
        project,
        request.form.get("action") == "restore",
        "project",
        project.name,
        "projects",
    )


@references_bp.route("/references/mpf-schemes/<int:scheme_id>/archive", methods=["POST"])
@login_required
def archive_mpf_scheme(scheme_id):
    if not editor_allowed():
        abort(403)
    scheme = db.get_or_404(MpfScheme, scheme_id)
    return set_archive_state(
        scheme,
        request.form.get("action") == "restore",
        "mpf_scheme",
        scheme.name,
        "mpf_schemes",
    )



@references_bp.get("/references/work-calendar/csv")
@login_required
def export_work_calendar_csv():
    year = request.args.get("calendar_year", type=int) or date.today().year
    region_id = request.args.get("region_id", type=int)
    query = WorkCalendarHoliday.query.filter(db.extract("year", WorkCalendarHoliday.holiday_date) == year, WorkCalendarHoliday.active.is_(True))
    if region_id:
        query = query.filter_by(region_id=region_id)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["date", "name", "scope", "region_code"])
    for item in query.order_by(WorkCalendarHoliday.holiday_date).all():
        writer.writerow([item.holiday_date.isoformat(), item.name, work_calendar_scope_value(item), item.region.code])
    return Response("\ufeff" + output.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment; filename=work-calendar-{year}.csv"})


@references_bp.post("/references/work-calendar/csv")
@login_required
def import_work_calendar_csv():
    if not editor_allowed():
        abort(403)
    upload = request.files.get("calendar_csv")
    try:
        if not upload:
            raise ValueError("請選擇工作日曆 CSV。")
        reader = csv.DictReader(io.StringIO(upload.read().decode("utf-8-sig")))
        rows, seen = [], set()
        for index, row in enumerate(reader, start=2):
            day = parse_date(row.get("date"))
            name = normalize_reference_display(row.get("name"))
            scope = work_calendar_scope(row.get("scope"))
            region = ReferenceValue.query.join(ReferenceList).filter(ReferenceList.code == "work_region", ReferenceValue.code == row.get("region_code")).first()
            if not day or not name or not scope or not region:
                raise ValueError(f"CSV 第 {index} 行：請填日期、名稱、scope（statutory/public/both）及有效 region_code。")
            key = (region.id, day)
            if key in seen:
                raise ValueError(f"CSV 第 {index} 行：同地區日期重複，請合併適用日曆。")
            seen.add(key); rows.append((region.id, day, name, scope))
        if not rows:
            raise ValueError("CSV 沒有假日；可先下載現有日曆作為格式範本。")
    except (ValueError, UnicodeError, csv.Error) as exc:
        flash(str(exc), "error")
        return references_redirect("work_calendar")
    added = updated = 0
    for region_id, day, name, scope in rows:
        item = WorkCalendarHoliday.query.filter_by(region_id=region_id, holiday_date=day).first()
        before = None
        if item:
            before = {"name": item.name, "scope": work_calendar_scope_value(item), "active": item.active}
            item.applies_to_statutory = item.applies_to_statutory or scope in {"statutory", "both"}
            item.applies_to_public = item.applies_to_public or scope in {"public", "both"}
            updated += 1
        else:
            item = WorkCalendarHoliday(region_id=region_id, holiday_date=day, name=name, active=True)
            set_work_calendar_scope(item, scope)
            db.session.add(item); added += 1
        db.session.flush()
        write_audit("work_calendar_csv_import", "WorkCalendarHoliday", item.id, before=before,
                    after={"name": item.name, "scope": work_calendar_scope_value(item), "active": item.active},
                    detail=day.isoformat())
    db.session.commit()
    flash(f"離線日曆已匯入：新增 {added} 日，核對 {updated} 日。既有名稱及封存狀態保留。", "success")
    return references_redirect("work_calendar")

@references_bp.route("/references/work-calendar", methods=["POST"])
@login_required
def create_work_calendar_holiday():
    if not editor_allowed():
        abort(403)
    region_id = request.form.get("region_id", type=int)
    holiday_date = parse_date(request.form.get("holiday_date"))
    name = normalize_reference_display(request.form.get("name"))
    scope = work_calendar_scope(request.form.get("calendar_scope"))
    if not region_id or not holiday_date or not name or not scope:
        flash("請完整填寫工作地區、假日日期、名稱及適用日曆。", "error")
        return references_redirect("work_calendar")
    existing = WorkCalendarHoliday.query.filter_by(
        region_id=region_id,
        holiday_date=holiday_date,
    ).first()
    if existing:
        flash("該工作地區及日期已有工作日曆記錄。", "error")
        return references_redirect("work_calendar")
    item = WorkCalendarHoliday(
        region_id=region_id,
        holiday_date=holiday_date,
        name=name,
        remarks=request.form.get("remarks", "").strip() or None,
        active=True,
    )
    set_work_calendar_scope(item, scope)
    db.session.add(item)
    db.session.flush()
    write_audit(
        "work_calendar_created",
        "WorkCalendarHoliday",
        item.id,
        detail=f"{holiday_date:%Y-%m-%d} {name} [{scope}]",
    )
    db.session.commit()
    flash("假日已加入工作日曆。", "success")
    return redirect(url_for("references.references_home", list="work_calendar", calendar_year=holiday_date.year, calendar_region_id=region_id))


@references_bp.route(
    "/references/work-calendar/import-hong-kong",
    methods=["POST"],
)
@login_required
def import_hong_kong_work_calendar():
    if not editor_allowed():
        abort(403)
    calendar_year = request.form.get("calendar_year", type=int) or (
        date.today().year + 1
    )
    hong_kong = (
        ReferenceValue.query.join(ReferenceList)
        .filter(
            ReferenceList.code == "work_region",
            ReferenceValue.code == "HK",
        )
        .first()
    )
    if not hong_kong:
        flash("未找到香港工作地區，請先在資料選項中建立。", "error")
        return references_redirect("work_calendar")
    try:
        statutory_holidays = fetch_hong_kong_statutory_holidays(calendar_year)
        public_holidays = fetch_hong_kong_public_holidays(calendar_year)
    except HolidayImportError as exc:
        flash(str(exc), "error")
        return redirect(
            url_for(
                "references.references_home",
                list="work_calendar",
                calendar_year=calendar_year,
                calendar_region_id=hong_kong.id,
            )
        )

    existing = {
        item.holiday_date: item
        for item in WorkCalendarHoliday.query.filter_by(
            region_id=hong_kong.id,
        ).filter(
            db.extract("year", WorkCalendarHoliday.holiday_date)
            == calendar_year
        )
    }
    created = []
    extended = []
    retained = []

    def persist_official_holidays(rows, scope, source_url):
        for holiday_date, name in rows:
            item = existing.get(holiday_date)
            if not item:
                item = WorkCalendarHoliday(
                    region_id=hong_kong.id,
                    holiday_date=holiday_date,
                    name=name,
                    applies_to_statutory=scope == "statutory",
                    applies_to_public=scope == "public",
                    remarks="由香港政府官方年度假日清單帶入：" + source_url,
                    active=True,
                )
                db.session.add(item)
                existing[holiday_date] = item
                created.append(
                    {"date": holiday_date.isoformat(), "name": name, "scope": scope}
                )
                continue
            attribute = (
                "applies_to_statutory"
                if scope == "statutory"
                else "applies_to_public"
            )
            if not getattr(item, attribute):
                setattr(item, attribute, True)
                extended.append(
                    {"date": holiday_date.isoformat(), "scope": scope}
                )
            else:
                retained.append(
                    {"date": holiday_date.isoformat(), "scope": scope}
                )

    persist_official_holidays(
        statutory_holidays,
        "statutory",
        SOURCE_URL_TEMPLATE.format(year=calendar_year),
    )
    persist_official_holidays(
        public_holidays,
        "public",
        PUBLIC_SOURCE_URL_TEMPLATE.format(year=calendar_year),
    )

    write_audit(
        "work_calendar_hk_imported",
        "WorkCalendarHoliday",
        detail=(
            f"{calendar_year} 香港假日日曆：新增 {len(created)}，"
            f"補充適用範圍 {len(extended)}，保留既有 {len(retained)}"
        ),
        after={
            "year": calendar_year,
            "statutory_christmas_choice": True,
            "created": created,
            "extended_existing_dates": extended,
            "retained_existing_dates": retained,
            "statutory_source_url": SOURCE_URL_TEMPLATE.format(year=calendar_year),
            "public_source_url": PUBLIC_SOURCE_URL_TEMPLATE.format(year=calendar_year),
        },
    )
    db.session.commit()
    flash(
        f"已帶入 {calendar_year} 年香港法定假日及公眾假期："
        f"新增 {len(created)} 個日期，補充 {len(extended)} 個既有日期的適用範圍。",
        "success",
    )
    return redirect(
        url_for(
            "references.references_home",
            list="work_calendar",
            calendar_year=calendar_year,
            calendar_region_id=hong_kong.id,
        )
    )


@references_bp.route("/references/work-calendar/<int:item_id>", methods=["POST"])
@login_required
def update_work_calendar_holiday(item_id):
    if not editor_allowed():
        abort(403)
    item = db.get_or_404(WorkCalendarHoliday, item_id)
    before = {
        "region_id": item.region_id,
        "holiday_date": item.holiday_date.isoformat(),
        "name": item.name,
        "calendar_scope": work_calendar_scope_value(item),
        "active": item.active,
    }
    region_id = request.form.get("region_id", type=int)
    holiday_date = parse_date(request.form.get("holiday_date"))
    name = normalize_reference_display(request.form.get("name"))
    scope = work_calendar_scope(request.form.get("calendar_scope"))
    if not region_id or not holiday_date or not name or not scope:
        flash("請完整填寫工作地區、假日日期、名稱及適用日曆。", "error")
        return references_redirect("work_calendar")
    duplicate = WorkCalendarHoliday.query.filter(
        WorkCalendarHoliday.region_id == region_id,
        WorkCalendarHoliday.holiday_date == holiday_date,
        WorkCalendarHoliday.id != item.id,
    ).first()
    if duplicate:
        flash("該工作地區及日期已有工作日曆記錄。", "error")
        return references_redirect("work_calendar")
    item.region_id = region_id
    item.holiday_date = holiday_date
    item.name = name
    set_work_calendar_scope(item, scope)
    item.remarks = request.form.get("remarks", "").strip() or None
    write_audit(
        "work_calendar_updated",
        "WorkCalendarHoliday",
        item.id,
        detail=f"{holiday_date:%Y-%m-%d} {name}",
        before=before,
        after={
            "region_id": region_id,
            "holiday_date": holiday_date.isoformat(),
            "name": name,
            "calendar_scope": scope,
            "active": item.active,
        },
    )
    db.session.commit()
    flash("工作日曆已更新。", "success")
    return redirect(url_for("references.references_home", list="work_calendar", calendar_year=holiday_date.year, calendar_region_id=region_id))


@references_bp.route("/references/work-calendar/<int:item_id>/archive", methods=["POST"])
@login_required
def archive_work_calendar_holiday(item_id):
    if not editor_allowed():
        abort(403)
    item = db.get_or_404(WorkCalendarHoliday, item_id)
    return set_archive_state(
        item,
        request.form.get("action") == "restore",
        "work_calendar",
        f"{item.holiday_date:%Y-%m-%d} {item.name}",
        "work_calendar",
    )


@references_bp.route("/references/work-calendar/<int:item_id>/delete", methods=["POST"])
@login_required
def delete_work_calendar_holiday(item_id):
    if not editor_allowed():
        abort(403)
    item = db.get_or_404(WorkCalendarHoliday, item_id)
    write_audit(
        "work_calendar_deleted",
        "WorkCalendarHoliday",
        item.id,
        detail=f"{item.holiday_date:%Y-%m-%d} {item.name}",
    )
    db.session.delete(item)
    db.session.commit()
    flash("工作日曆記錄已刪除。", "success")
    return references_redirect("work_calendar")


@references_bp.route("/references/projects/<int:project_id>/delete", methods=["POST"])
@login_required
def delete_project(project_id):
    if not editor_allowed():
        abort(403)
    project = db.get_or_404(WorkProject, project_id)
    count = sum(
        (
            EmployeeAssignment.query.filter_by(project_id=project.id).count(),
            AttendanceSegment.query.filter_by(project_id=project.id).count(),
            PayrollAdjustment.query.filter_by(project_id=project.id).count(),
            EmployeeAllowance.query.filter_by(project_id=project.id).count(),
            PayrollProjectLine.query.filter_by(project_id=project.id).count(),
        )
    )
    if count:
        flash(
            f"此項目仍被 {count} 筆任職、考勤或工資表資料引用，不能刪除；如不再使用，請關閉「可供新資料選用」。",
            "error",
        )
        return references_redirect("projects")
    db.session.delete(project)
    db.session.commit()
    flash("項目已刪除。", "success")
    return references_redirect("projects")
