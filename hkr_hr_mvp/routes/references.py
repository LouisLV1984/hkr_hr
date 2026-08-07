from decimal import Decimal

from flask import (
    Blueprint,
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
    EmployeeSalary,
    EmployeeVisa,
    PayrollAdjustment,
    PayrollProjectLine,
    ReferenceList,
    ReferenceValue,
    WorkProject,
    db,
)
from tools.hr_core import (
    REFERENCE_LISTS,
    normalize_reference_display,
    parse_decimal,
    slug_code,
    write_audit,
)


references_bp = Blueprint("references", __name__)


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
    query = usage_query(value)
    return query.count() if query is not None else 0


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
        ReferenceValue.query.filter_by(list_id=selected.id)
        .order_by(ReferenceValue.display_name.asc())
        .all()
        if selected
        else []
    )
    counts = {value.id: usage_count(value) for value in values}
    projects = WorkProject.query.order_by(WorkProject.name.asc()).all()
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
        project_counts=project_counts,
        regions=(
            ReferenceValue.query.join(ReferenceList)
            .filter(
                ReferenceList.code == "work_region",
                ReferenceValue.active.is_(True),
            )
            .order_by(ReferenceValue.display_name)
            .all()
        ),
        selected_code=selected_code,
        can_edit=editor_allowed(),
        return_to=safe_return_to(request.args.get("return_to")),
    )


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
            _, created, reactivated = ensure_reference_value(
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
            before = {"display_name": old_name, "active": value.active}
            value.display_name = display_name
            value.normalized_name = display_name.casefold()
            value.active = request.form.get("active") == "on"
            value.remarks = request.form.get("remarks", "").strip() or None
            propagate_text_usage(value, old_name)
            write_audit(
                "reference_updated",
                "ReferenceValue",
                value.id,
                detail=f"{old_name} → {display_name}",
                before=before,
                after={
                    "display_name": display_name,
                    "active": value.active,
                },
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
    project.active = request.form.get("active") == "on"
    write_audit(
        "project_updated",
        "WorkProject",
        project.id,
        detail=f"{old_name} → {project.name}",
    )
    db.session.commit()
    flash("項目已更新，既有員工與考勤引用會同步顯示新名稱。", "success")
    return references_redirect("projects")


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
            f"此項目仍被 {count} 筆任職、考勤或 Payroll 資料引用，不能刪除；如不再使用，請關閉「可供新資料選用」。",
            "error",
        )
        return references_redirect("projects")
    db.session.delete(project)
    db.session.commit()
    flash("項目已刪除。", "success")
    return references_redirect("projects")
