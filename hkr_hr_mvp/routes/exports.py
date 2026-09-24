import io
import zipfile
from datetime import date, datetime
from pathlib import Path

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from flask_login import current_user, login_required
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill

from models import (
    AttendanceMonthlySummary,
    Employee,
    EmployeeCertificate,
    EmployeeDocument,
    EmployeeVisa,
    PayrollEmployeeResult,
    PayrollRun,
    WorkProject,
    db,
)
from tools.hr_core import (
    DOCUMENT_CATEGORIES,
    IDENTITY_TYPE_OPTIONS,
    PAYROLL_GROUPS,
    TERMINATION_REASONS,
    annual_leave_summary,
    current_month,
    reference_map,
    write_audit,
)


exports_bp = Blueprint("exports", __name__)

ATTACHMENT_BUNDLE_GROUPS = {
    "all": None,
    "three_treasures": {"three_treasures"},
    "staff_record": {"staff_record"},
    "credentials": {"identity", "visa", "qualification"},
    "contracts": {"contract_draft", "signed_contract"},
    "bank_cv": {"bank_proof", "cv"},
    "attendance": {"attendance_pdf"},
    "employment_evidence": {
        "change_evidence",
        "probation_confirmation",
        "termination_letter",
        "name_change_evidence",
        "other",
    },
}
PAYROLL_GROUP_CODES = {code for code, _label in PAYROLL_GROUPS}
IDENTITY_TYPE_LABELS = dict(IDENTITY_TYPE_OPTIONS)
TERMINATION_REASON_LABELS = dict(TERMINATION_REASONS)
EMPLOYEE_STATUS_LABELS = {"active": "在職", "departed": "離職"}
DOCUMENT_STATUS_LABELS = {
    "active": "有效",
    "replaced": "已替換",
    "voided": "已作廢",
}
SALARY_BASIS_LABELS = {"monthly": "月薪", "daily": "日薪"}
MPF_MODE_LABELS = {
    "regular": "一般僱員",
    "casual": "建造業臨時僱員",
    "exempt": "豁免",
}
QUALIFICATION_CATEGORY_LABELS = {
    "degree": "學歷",
    "skill": "技能",
}


def xlsx_response(workbook, filename):
    output = io.BytesIO()
    workbook.save(output)
    output.seek(0)
    return send_file(
        output,
        as_attachment=True,
        download_name=filename,
        mimetype=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
    )


def autosize(sheet):
    for column_cells in sheet.columns:
        width = max(len(str(cell.value or "")) for cell in column_cells)
        letter = column_cells[0].column_letter
        sheet.column_dimensions[letter].width = min(max(width + 2, 12), 42)


def finish_sheet(sheet, date_columns=(), money_columns=()):
    header_fill = PatternFill("solid", fgColor="176B62")
    for cell in sheet[1]:
        cell.fill = header_fill
        cell.font = Font(color="FFFFFF", bold=True)
        cell.alignment = Alignment(vertical="center", wrap_text=True)
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    for column in date_columns:
        for cell in sheet[column][1:]:
            if cell.value:
                cell.number_format = "yyyy-mm-dd"
    for column in money_columns:
        for cell in sheet[column][1:]:
            if cell.value is not None:
                cell.number_format = "#,##0.00"
    autosize(sheet)


def timestamp():
    return datetime.utcnow().strftime("%Y%m%d_%H%M%S")


def normalized_month(value):
    value = value or current_month()
    try:
        datetime.strptime(value, "%Y-%m")
    except ValueError:
        return current_month()
    return value


def document_name(document):
    return document.original_filename if document else ""


def reference_name(value):
    return value.display_name if value else ""


def active_categories(employee):
    return {
        document.category
        for document in employee.documents
        if document.status == "active"
    }


def filtered_employees(args):
    query = Employee.query
    status = args.get("status")
    payroll_group = args.get("payroll_group")
    if payroll_group:
        query = query.filter(Employee.payroll_group == payroll_group)
    employee_type_id = args.get("employee_type_id", type=int)
    if employee_type_id:
        query = query.filter(Employee.employee_type_id == employee_type_id)
    rows = query.order_by(Employee.employee_no.asc()).all()
    if status in {"active", "departed"}:
        rows = [
            employee
            for employee in rows
            if employee.derived_status == status
        ]

    project_id = args.get("project_id", type=int)
    department_id = args.get("department_id", type=int)
    region_id = args.get("region_id", type=int)
    position_id = args.get("position_id", type=int)
    if any((project_id, department_id, region_id, position_id)):
        filtered = []
        for employee in rows:
            assignment = employee.current_assignment
            if not assignment:
                continue
            if project_id and assignment.project_id != project_id:
                continue
            if department_id and assignment.department_id != department_id:
                continue
            if region_id and assignment.region_id != region_id:
                continue
            if position_id and not any(
                item.position_id == position_id for item in assignment.positions
            ):
                continue
            filtered.append(employee)
        rows = filtered

    warning = args.get("warning")
    if warning == "missing_staff_record":
        rows = [
            employee
            for employee in rows
            if "staff_record" not in active_categories(employee)
        ]
    elif warning == "missing_contract":
        rows = [
            employee
            for employee in rows
            if "signed_contract" not in active_categories(employee)
        ]
    expiry = args.get("expiry")
    if expiry == "due_60" or warning == "expiry":
        today = date.today()
        cutoff = date.fromordinal(today.toordinal() + 60)
        rows = [
            employee
            for employee in rows
            if any(
                item.expiry_date
                and today <= item.expiry_date <= cutoff
                and getattr(item, "status", "active") == "active"
                for item in (
                    list(employee.identities)
                    + list(employee.certificates)
                    + list(employee.visas)
                    + list(employee.qualifications)
                )
            )
        ]
    return rows


@exports_bp.route("/exports")
@login_required
def export_center():
    section = request.args.get("section") or "attachments"
    if section == "payroll":
        return redirect(
            url_for(
                "payroll.attendance_payroll",
                year_month=normalized_month(request.args.get("year_month")),
            )
        )
    if section not in {"attachments", "employees"}:
        section = "attachments"
    year_month = normalized_month(request.args.get("year_month"))
    return render_template(
        "exports/index.html",
        refs=reference_map(),
        projects=WorkProject.query.filter_by(active=True).order_by(
            WorkProject.name
        ).all(),
        payroll_groups=PAYROLL_GROUPS,
        section=section,
        year_month=year_month,
        bundle_groups=ATTACHMENT_BUNDLE_GROUPS,
        employee_count=Employee.query.count(),
        active_attachment_count=EmployeeDocument.query.filter_by(
            status="active"
        ).count(),
        employees=Employee.query.order_by(Employee.employee_no.asc()).all(),
        today_iso=date.today().isoformat(),
    )


@exports_bp.route("/export/employees")
@login_required
def export_employees():
    rows = filtered_employees(request.args)
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "員工資料總表"
    sheet.append(
        [
            "員工編號",
            "狀態",
            "員工類型",
            "Payroll 組別",
            "中文姓名",
            "英文姓名",
            "性別",
            "出生日期",
            "聯絡電話",
            "電子郵箱",
            "住址",
            "緊急聯絡人",
            "緊急聯絡人關係",
            "緊急聯絡電話",
            "學歷",
            "專業",
            "畢業院校",
            "主要身份證件類型",
            "主要身份證件號碼",
            "工作區域",
            "工作項目",
            "所在部門",
            "職務",
            "聘用單位",
            "發薪單位",
            "社保繳納單位",
            "勞務派遣單位",
            "薪酬類型",
            "幣種",
            "薪酬金額",
            "入職日期",
            "試用期到期日",
            "轉正日期",
            "合同年假",
            "本年應享年假",
            "已放年假",
            "剩餘年假",
            "銀行",
            "銀行帳戶",
            "MPF 類別",
            "是否需要 VISA",
            "缺失提示",
            "備註",
        ]
    )
    group_labels = dict(PAYROLL_GROUPS)
    for employee in rows:
        assignment = employee.current_assignment
        salary = employee.current_salary
        period = employee.current_period
        primary = employee.primary_identity
        leave = annual_leave_summary(employee)
        categories = active_categories(employee)
        missing = []
        if not assignment:
            missing.append("任職")
        if not salary:
            missing.append("薪酬")
        if not employee.bank_account_no:
            missing.append("銀行")
        if "staff_record" not in categories:
            missing.append("Staff Record")
        if "signed_contract" not in categories:
            missing.append("合同")
        sheet.append(
            [
                employee.employee_no,
                EMPLOYEE_STATUS_LABELS.get(
                    employee.derived_status,
                    employee.derived_status,
                ),
                employee.employee_type.display_name,
                group_labels.get(employee.payroll_group, employee.payroll_group),
                employee.chinese_name,
                employee.english_name,
                employee.gender,
                employee.date_of_birth,
                " ".join(
                    item
                    for item in [
                        employee.mobile_region_code,
                        employee.mobile_number,
                    ]
                    if item
                ),
                employee.email,
                employee.residential_address,
                employee.emergency_contact_name,
                employee.emergency_contact_relation,
                " ".join(
                    item
                    for item in [
                        employee.emergency_contact_region_code,
                        employee.emergency_contact_phone,
                    ]
                    if item
                ),
                employee.education_level,
                employee.major,
                employee.graduation_school,
                (
                    IDENTITY_TYPE_LABELS.get(
                        primary.identity_type,
                        primary.identity_type,
                    )
                    if primary
                    else ""
                ),
                primary.identity_number if primary else "",
                assignment.region.display_name if assignment and assignment.region else "",
                assignment.project.name if assignment and assignment.project else "",
                assignment.department.display_name if assignment and assignment.department else "",
                "、".join(
                    item.position.display_name for item in assignment.positions
                )
                if assignment
                else "",
                assignment.employer.display_name if assignment and assignment.employer else "",
                assignment.payroll_entity.display_name if assignment and assignment.payroll_entity else "",
                assignment.social_insurance_entity.display_name if assignment and assignment.social_insurance_entity else "",
                assignment.labour_dispatch_entity.display_name if assignment and assignment.labour_dispatch_entity else "",
                SALARY_BASIS_LABELS.get(
                    salary.salary_basis,
                    salary.salary_basis,
                )
                if salary
                else "",
                salary.currency if salary else "",
                float(salary.amount) if salary else None,
                period.start_date if period else None,
                period.probation_end_date if period else None,
                period.confirmation_date if period else None,
                float(period.contract_annual_leave_days)
                if period and period.contract_annual_leave_days is not None
                else None,
                float(leave["entitled"]),
                float(leave["used"]),
                float(leave["remaining"]),
                employee.bank_name,
                employee.bank_account_no,
                MPF_MODE_LABELS.get(employee.mpf_mode, employee.mpf_mode),
                "是" if employee.visa_required else "否",
                "、".join(missing),
                employee.remarks,
            ]
        )
    finish_sheet(
        sheet,
        date_columns=("H", "AE", "AF", "AG"),
        money_columns=("AD",),
    )
    for column in ("AH", "AI", "AJ", "AK"):
        for cell in sheet[column][1:]:
            if cell.value is not None:
                cell.number_format = "0.0"

    credentials = workbook.create_sheet("證件及資歷")
    credentials.append(
        [
            "員工編號",
            "員工",
            "資料類型",
            "證件／資歷類別",
            "號碼",
            "簽發／生效日期",
            "到期日",
            "長期",
            "主要證件",
            "狀態",
            "附件",
            "備註",
        ]
    )
    for employee in rows:
        for identity in employee.identities:
            credentials.append(
                [
                    employee.employee_no,
                    employee.display_name,
                    "身份證件",
                    IDENTITY_TYPE_LABELS.get(
                        identity.identity_type,
                        identity.identity_type,
                    ),
                    identity.identity_number,
                    identity.issue_date,
                    identity.expiry_date,
                    "是" if identity.is_long_term else "否",
                    "是" if identity.is_primary else "否",
                    DOCUMENT_STATUS_LABELS.get(
                        identity.status,
                        identity.status,
                    ),
                    document_name(identity.document),
                    identity.remarks,
                ]
            )
        for certificate in employee.certificates:
            credentials.append(
                [
                    employee.employee_no,
                    employee.display_name,
                    "員工證件",
                    reference_name(certificate.certificate_type),
                    certificate.certificate_no,
                    certificate.valid_from,
                    certificate.expiry_date,
                    "是" if certificate.is_long_term else "否",
                    "",
                    DOCUMENT_STATUS_LABELS.get(
                        certificate.status,
                        certificate.status,
                    ),
                    document_name(certificate.document),
                    certificate.remarks,
                ]
            )
        for visa in employee.visas:
            credentials.append(
                [
                    employee.employee_no,
                    employee.display_name,
                    "VISA",
                    reference_name(visa.visa_category),
                    visa.visa_no,
                    visa.issue_date,
                    visa.expiry_date,
                    "",
                    "",
                    DOCUMENT_STATUS_LABELS.get(
                        visa.status,
                        visa.status,
                    ),
                    document_name(visa.document),
                    visa.remarks,
                ]
            )
        for qualification in employee.qualifications:
            credentials.append(
                [
                    employee.employee_no,
                    employee.display_name,
                    "學歷／技能",
                    qualification.qualification_name,
                    qualification.certificate_no,
                    qualification.issue_date,
                    qualification.expiry_date,
                    "",
                    "",
                    (
                        QUALIFICATION_CATEGORY_LABELS.get(
                            qualification.category,
                            qualification.category,
                        )
                        + " / "
                        + DOCUMENT_STATUS_LABELS.get(
                            qualification.status,
                            qualification.status,
                        )
                    ),
                    document_name(qualification.document),
                    qualification.remarks,
                ]
            )
    finish_sheet(credentials, date_columns=("F", "G"))

    history = workbook.create_sheet("任職及薪酬歷史")
    history.append(
        [
            "員工編號",
            "員工",
            "記錄類型",
            "生效／開始日期",
            "結束日期",
            "試用期到期日",
            "轉正日期",
            "合同年假",
            "工作區域",
            "工作項目",
            "所在部門",
            "職務",
            "聘用單位",
            "發薪單位",
            "社保繳納單位",
            "勞務派遣單位",
            "Payroll 組別",
            "薪酬／津貼／離職原因",
            "幣種",
            "金額",
            "平均工資",
            "代通知金",
            "遣散費",
            "長期服務金",
            "憑證",
            "備註",
        ]
    )
    for employee in rows:
        for period in employee.employment_periods:
            evidence = "、".join(
                item
                for item in [
                    document_name(period.confirmation_document),
                    document_name(period.termination_document),
                ]
                if item
            )
            history.append(
                [
                    employee.employee_no,
                    employee.display_name,
                    "任職期間",
                    period.start_date,
                    period.end_date,
                    period.probation_end_date,
                    period.confirmation_date,
                    (
                        float(period.contract_annual_leave_days)
                        if period.contract_annual_leave_days is not None
                        else None
                    ),
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    TERMINATION_REASON_LABELS.get(
                        period.termination_reason,
                        period.termination_reason,
                    ),
                    "",
                    None,
                    (
                        float(period.average_wage)
                        if period.average_wage is not None
                        else None
                    ),
                    (
                        float(period.payment_in_lieu)
                        if period.payment_in_lieu is not None
                        else None
                    ),
                    (
                        float(period.severance_payment)
                        if period.severance_payment is not None
                        else None
                    ),
                    (
                        float(period.long_service_payment)
                        if period.long_service_payment is not None
                        else None
                    ),
                    evidence,
                    period.remarks,
                ]
            )
        for assignment in employee.assignments:
            history.append(
                [
                    employee.employee_no,
                    employee.display_name,
                    "任職調整",
                    assignment.effective_from,
                    assignment.effective_to,
                    None,
                    None,
                    None,
                    reference_name(assignment.region),
                    assignment.project.name if assignment.project else "",
                    reference_name(assignment.department),
                    "、".join(
                        item.position.display_name
                        for item in assignment.positions
                    ),
                    reference_name(assignment.employer),
                    reference_name(assignment.payroll_entity),
                    reference_name(assignment.social_insurance_entity),
                    reference_name(assignment.labour_dispatch_entity),
                    group_labels.get(
                        assignment.payroll_group,
                        assignment.payroll_group,
                    ),
                    "",
                    "",
                    None,
                    None,
                    None,
                    None,
                    None,
                    document_name(assignment.evidence_document),
                    assignment.remarks,
                ]
            )
        for salary in employee.salaries:
            history.append(
                [
                    employee.employee_no,
                    employee.display_name,
                    "薪酬調整",
                    salary.effective_from,
                    salary.effective_to,
                    None,
                    None,
                    None,
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    SALARY_BASIS_LABELS.get(
                        salary.salary_basis,
                        salary.salary_basis,
                    ),
                    salary.currency,
                    float(salary.amount),
                    None,
                    None,
                    None,
                    None,
                    document_name(salary.evidence_document),
                    salary.remarks,
                ]
            )
        for allowance in employee.allowances:
            history.append(
                [
                    employee.employee_no,
                    employee.display_name,
                    "津貼",
                    allowance.effective_from,
                    allowance.effective_to,
                    None,
                    None,
                    None,
                    "",
                    allowance.project.name if allowance.project else "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    allowance.label,
                    allowance.currency,
                    float(allowance.amount),
                    None,
                    None,
                    None,
                    None,
                    document_name(allowance.evidence_document),
                    allowance.remarks,
                ]
            )
    finish_sheet(
        history,
        date_columns=("D", "E", "F", "G"),
        money_columns=("T", "U", "V", "W", "X"),
    )
    for cell in history["H"][1:]:
        if cell.value is not None:
            cell.number_format = "0.0"

    documents = workbook.create_sheet("附件索引")
    documents.append(
        [
            "員工編號",
            "員工",
            "附件類別",
            "標題",
            "狀態",
            "文件日期",
            "考勤月份",
            "檔案名稱",
            "檔案大小 KB",
            "上傳時間",
            "替換／作廢原因",
            "備註",
        ]
    )
    for employee in rows:
        for document in employee.documents:
            documents.append(
                [
                    employee.employee_no,
                    employee.display_name,
                    (
                        document.general_document_type.display_name
                        if document.general_document_type
                        else (
                            document.title
                            if document.category == "change_evidence"
                            and document.title
                            else DOCUMENT_CATEGORIES.get(
                                document.category,
                                document.category,
                            )
                        )
                    ),
                    document.title,
                    DOCUMENT_STATUS_LABELS.get(
                        document.status,
                        document.status,
                    ),
                    document.document_date,
                    document.effective_month,
                    document.original_filename,
                    (
                        round(document.file_size / 1024, 1)
                        if document.file_size is not None
                        else None
                    ),
                    document.uploaded_at,
                    document.replacement_reason,
                    document.remarks,
                ]
            )
    finish_sheet(documents, date_columns=("F", "J"))

    write_audit(
        "employee_export",
        "Employee",
        detail=f"匯出員工資料總表：{len(rows)} 名員工",
        user_id=current_user.id,
    )
    db.session.commit()
    return xlsx_response(
        workbook,
        f"HKR_員工資料總表_{timestamp()}.xlsx",
    )


@exports_bp.route("/export/salary-certificate")
@login_required
def export_salary_certificate():
    employee = db.session.get(
        Employee,
        request.args.get("employee_id", type=int),
    )
    if not employee:
        flash("請選擇員工。", "error")
        return redirect(
            url_for("exports.export_center", section="employees")
        )
    year_month = normalized_month(request.args.get("year_month"))
    issue_date = request.args.get("issue_date")
    try:
        issue_date_value = datetime.strptime(
            issue_date or date.today().isoformat(),
            "%Y-%m-%d",
        ).date()
    except ValueError:
        issue_date_value = date.today()

    template_path = (
        Path(current_app.config["PAYROLL_TEMPLATE_ROOT"])
        / "Employee_Salary_Certificate_Template.xlsx"
    )
    if not template_path.is_file():
        flash("找不到僱員薪金證明書模板，請聯絡 Admin。", "error")
        return redirect(
            url_for("exports.export_center", section="employees")
        )

    candidates = (
        PayrollEmployeeResult.query.join(PayrollRun)
        .filter(
            PayrollEmployeeResult.employee_id == employee.id,
            PayrollRun.year_month <= year_month,
        )
        .order_by(
            PayrollRun.year_month.desc(),
            PayrollRun.created_at.desc(),
            PayrollRun.id.desc(),
        )
        .all()
    )
    results = []
    seen_months = set()
    for result in candidates:
        if result.run.year_month in seen_months:
            continue
        seen_months.add(result.run.year_month)
        results.append(result)
        if len(results) == 3:
            break
    results.reverse()
    if not results:
        flash("此員工尚未有已生成的 Payroll，無法製作薪金證明書。", "error")
        return redirect(
            url_for("exports.export_center", section="employees")
        )

    workbook = load_workbook(template_path)
    sheet = workbook[workbook.sheetnames[0]]
    for row_index in range(9, 12):
        for column_index in range(1, 11):
            sheet.cell(row=row_index, column=column_index).value = None

    assignment = employee.current_assignment
    position = (
        "、".join(
            item.position.display_name
            for item in assignment.positions
        )
        if assignment
        else ""
    )
    period = employee.current_period
    for row_index, result in enumerate(results, start=9):
        month_value = datetime.strptime(
            result.run.year_month,
            "%Y-%m",
        ).date()
        sheet.cell(row=row_index, column=1, value=month_value)
        sheet.cell(row=row_index, column=1).number_format = "mmm-yy"
        sheet.cell(
            row=row_index,
            column=2,
            value=employee.english_name or "",
        )
        sheet.cell(
            row=row_index,
            column=3,
            value=employee.chinese_name or "",
        )
        sheet.cell(row=row_index, column=4, value=position)
        sheet.cell(
            row=row_index,
            column=5,
            value=period.start_date if period else None,
        )
        sheet.cell(row=row_index, column=5).number_format = "dd/mm/yy"
        sheet.cell(
            row=row_index,
            column=6,
            value=float(result.base_amount or 0),
        )
        sheet.cell(
            row=row_index,
            column=7,
            value=float(result.ot_amount or 0),
        )
        sheet.cell(
            row=row_index,
            column=8,
            value=float(result.gross_amount or 0),
        )
        sheet.cell(
            row=row_index,
            column=9,
            value=-float(result.employee_mpf or 0),
        )
        sheet.cell(
            row=row_index,
            column=10,
            value=f"=H{row_index}+I{row_index}",
        )
        for column_index in range(6, 11):
            sheet.cell(
                row=row_index,
                column=column_index,
            ).number_format = '#,##0.00;[Red](#,##0.00)'
    employer = (
        assignment.employer.display_name
        if assignment and assignment.employer
        else "Hong Kong River Engineering Company Limited"
    )
    sheet["H14"] = f"For and on behalf of\n{employer}"
    sheet["H19"] = f"Date / 日期：{issue_date_value:%d %B %Y}"

    write_audit(
        "salary_certificate_exported",
        "Employee",
        employee.id,
        employee_id=employee.id,
        detail=(
            f"僱員薪金證明書："
            f"{results[0].run.year_month} 至 {results[-1].run.year_month}"
        ),
    )
    db.session.commit()
    return xlsx_response(
        workbook,
        (
            f"{year_month.replace('-', '')}_{employee.employee_no}_"
            f"{employee.display_name}_僱員薪金證明書.xlsx"
        ),
    )


@exports_bp.route("/export/certificates")
@login_required
def export_certificates():
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "證件到期"
    sheet.append(
        [
            "員工編號",
            "員工",
            "證件類型",
            "證件號碼",
            "有效期開始",
            "到期日",
            "長期",
            "附件",
        ]
    )
    for employee in Employee.query.order_by(Employee.employee_no).all():
        for identity in employee.identities:
            if identity.status != "active":
                continue
            sheet.append(
                [
                    employee.employee_no,
                    employee.display_name,
                    identity.identity_type,
                    identity.identity_number,
                    identity.issue_date,
                    identity.expiry_date,
                    "是" if identity.is_long_term else "否",
                    identity.document.original_filename
                    if identity.document
                    else "",
                ]
            )
        for certificate in employee.certificates:
            if certificate.status != "active":
                continue
            sheet.append(
                [
                    employee.employee_no,
                    employee.display_name,
                    certificate.certificate_type.display_name,
                    certificate.certificate_no,
                    certificate.valid_from,
                    certificate.expiry_date,
                    "是" if certificate.is_long_term else "否",
                    certificate.document.original_filename
                    if certificate.document
                    else "",
                ]
            )
    finish_sheet(sheet, date_columns=("E", "F"))
    visa_sheet = workbook.create_sheet("VISA 到期")
    visa_sheet.append(
        [
            "員工編號",
            "員工",
            "VISA 類別",
            "VISA 號碼",
            "簽發日",
            "到期日",
            "附件",
        ]
    )
    for visa in EmployeeVisa.query.filter_by(status="active").order_by(
        EmployeeVisa.expiry_date.asc().nullslast()
    ):
        visa_sheet.append(
            [
                visa.employee.employee_no,
                visa.employee.display_name,
                visa.visa_category.display_name,
                visa.visa_no,
                visa.issue_date,
                visa.expiry_date,
                visa.document.original_filename if visa.document else "",
            ]
        )
    finish_sheet(visa_sheet, date_columns=("E", "F"))
    return xlsx_response(
        workbook,
        f"HKR_Certificate_VISA_{timestamp()}.xlsx",
    )


@exports_bp.route("/export/attendance-summary")
@login_required
def export_attendance_summary():
    year_month = request.args.get("year_month") or current_month()
    rows = AttendanceMonthlySummary.query.filter_by(
        year_month=year_month
    ).all()
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Attendance"
    sheet.append(
        [
            "月份",
            "員工編號",
            "員工",
            "區段",
            "項目",
            "實際出勤天數",
            "OT 小時",
            "星期日／公眾假期日數",
            "大 E-CALL 次數",
            "普通 E-CALL 次數",
            "PDF",
        ]
    )
    for summary in rows:
        for segment in summary.segments:
            sheet.append(
                [
                    summary.year_month,
                    summary.employee.employee_no,
                    summary.employee.display_name,
                    segment.period_kind,
                    segment.project.name if segment.project else "",
                    float(segment.working_days),
                    float(segment.ot_hours),
                    float(segment.sunday_holiday_days),
                    int(segment.large_ecall_count or 0),
                    int(segment.ecall_count or 0),
                    summary.document.original_filename
                    if summary.document
                    else "",
                ]
            )
    finish_sheet(sheet)
    return xlsx_response(
        workbook,
        f"HKR_Attendance_{year_month}.xlsx",
    )


@exports_bp.route("/export/payroll-summary")
@login_required
def export_payroll_summary():
    run_id = request.args.get("run_id", type=int)
    run = db.session.get(PayrollRun, run_id) if run_id else None
    if not run:
        flash("請先在考勤出糧頁建立 Payroll 計算快照。", "error")
        return redirect(url_for("exports.export_center"))
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Payroll Summary"
    sheet.append(
        [
            "月份",
            "Payroll 組別",
            "員工編號",
            "員工",
            "幣種",
            "基本薪酬",
            "OT",
            "假日薪酬",
            "大 E-CALL",
            "普通 E-CALL",
            "津貼",
            "多付",
            "少付",
            "其他調整",
            "僱員 MPF",
            "僱主 MPF",
            "代通知金",
            "遣散／長期服務金",
            "實發金額",
            "提示",
        ]
    )
    for result in run.employee_results:
        sheet.append(
            [
                run.year_month,
                (result.calculation_json or {}).get("group"),
                result.employee.employee_no,
                result.employee.display_name,
                result.currency,
                float(result.base_amount),
                float(result.ot_amount),
                float(result.holiday_amount),
                float(result.large_ecall_amount),
                float(result.ecall_amount),
                float(result.allowance_amount),
                float(result.overpay_amount),
                float(result.underpay_amount),
                float(result.adjustment_amount),
                float(result.employee_mpf),
                float(result.employer_mpf),
                float(result.payment_in_lieu),
                float(result.severance_long_service),
                float(result.net_amount),
                "；".join(result.warnings_json or []),
            ]
        )
    finish_sheet(
        sheet,
        money_columns=(
            "F",
            "G",
            "H",
            "I",
            "J",
            "K",
            "L",
            "M",
            "N",
            "O",
            "P",
            "Q",
            "R",
            "S",
        ),
    )
    return xlsx_response(
        workbook,
        f"HKR_Payroll_Summary_{run.year_month}_{run.id}.xlsx",
    )


@exports_bp.route("/export/attachments")
@login_required
def export_attachments():
    bundle_group = request.args.get("bundle_group") or "all"
    if bundle_group not in ATTACHMENT_BUNDLE_GROUPS:
        bundle_group = "all"
    categories = ATTACHMENT_BUNDLE_GROUPS[bundle_group]
    attendance_month = normalized_month(request.args.get("year_month"))
    memory = io.BytesIO()
    written = 0
    with zipfile.ZipFile(memory, "w", zipfile.ZIP_DEFLATED) as archive:
        for employee in Employee.query.order_by(Employee.employee_no):
            for document in employee.documents:
                if document.status != "active":
                    continue
                if categories is not None and document.category not in categories:
                    continue
                if (
                    bundle_group == "attendance"
                    and document.effective_month != attendance_month
                ):
                    continue
                path = Path(document.stored_path)
                if path.is_file():
                    archive.write(
                        path,
                        arcname=(
                            f"{employee.employee_no}_{employee.display_name}/"
                            f"{document.category}/{document.original_filename}"
                        ),
                    )
                    written += 1
    if not written:
        flash("目前沒有可打包的在用附件。", "error")
        return redirect(
            url_for("exports.export_center", section="attachments")
        )
    memory.seek(0)
    write_audit(
        "attachment_bundle_export",
        "EmployeeDocument",
        detail=(
            f"打包 {written} 份附件；類別={bundle_group}"
            + (
                f"；月份={attendance_month}"
                if bundle_group == "attendance"
                else ""
            )
        ),
        user_id=current_user.id,
    )
    db.session.commit()
    return send_file(
        memory,
        as_attachment=True,
        download_name=(
            f"HKR_Attachments_{bundle_group}"
            + (
                f"_{attendance_month}"
                if bundle_group == "attendance"
                else ""
            )
            + f"_{timestamp()}.zip"
        ),
        mimetype="application/zip",
    )


@exports_bp.route("/export/monthly-payroll")
@login_required
def export_monthly_payroll():
    year_month = normalized_month(request.args.get("year_month"))
    payroll_group = request.args.get("payroll_group") or "all"
    if payroll_group not in {*PAYROLL_GROUP_CODES, "all"}:
        payroll_group = "all"
    return redirect(
        url_for(
            "payroll.export_current_payroll",
            year_month=year_month,
            payroll_group=payroll_group,
        )
    )
