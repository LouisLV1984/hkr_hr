import calendar
import io
import zipfile
from copy import copy
from datetime import date, datetime
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
    send_file,
    url_for,
)
from flask_login import current_user, login_required
from openpyxl import load_workbook
from openpyxl.workbook.properties import CalcProperties

from models import (
    Employee,
    EmployeeDocument,
    EmployeeEmploymentPeriod,
    EmployeeFinalPaymentCase,
    PayrollAdjustment,
    PayrollRun,
    WorkProject,
    db,
)
from tools.final_payment import (
    FINAL_PAYMENT_RULE_VERSION,
    calculate_final_payments,
    final_payment_case,
    group_for_period,
)
from tools.hr_core import (
    PAYROLL_GROUPS,
    file_sha256,
    parse_decimal,
    parse_year_month,
    store_employee_file,
    write_audit,
)
from tools.payroll_engine import (
    PAYROLL_GROUP_CODES,
    RULE_VERSION,
    calculate_payroll,
    decimal_value,
    project_summary,
    rounded,
    snapshot_payroll,
)


payroll_bp = Blueprint("payroll", __name__)

GROUP_SHEETS = {
    "site_monthly": "月工",
    "management": "OFFICE",
    "site_daily": "日工",
}

FORMULA_NOTES = [
    "payroll.rule.period",
    "payroll.rule.monthly",
    "payroll.rule.daily",
    "payroll.rule.ha",
    "payroll.rule.ecall",
    "payroll.rule.forecast",
    "payroll.rule.reconciliation",
    "payroll.rule.mpf",
    "payroll.rule.xlsx_formulas",
    "payroll.rule.blockers",
]

FINAL_PAYMENT_FORMULA_NOTES = [
    "final_payment.rule.actual_attendance",
    "final_payment.rule.annual_leave",
    "final_payment.rule.statutory_holiday",
    "final_payment.rule.service_benefit",
    "final_payment.rule.transition",
    "final_payment.rule.cap",
    "final_payment.rule.mpf_offset",
    "final_payment.rule.hr_check",
]


def selected_group():
    value = request.values.get("payroll_group") or "all"
    return value if value in {*PAYROLL_GROUP_CODES, "all"} else "all"


def selected_month():
    value = request.values.get("year_month") or date.today().strftime("%Y-%m")
    try:
        datetime.strptime(value, "%Y-%m")
    except ValueError:
        value = date.today().strftime("%Y-%m")
    return value


@payroll_bp.route("/attendance-payroll")
@login_required
def attendance_payroll():
    year_month = selected_month()
    group = selected_group()
    rows = calculate_payroll(year_month, group)
    blockers = [row for row in rows if row["blockers"]]
    counts = {
        code: sum(1 for row in rows if row["group"] == code)
        for code in PAYROLL_GROUP_CODES
    }
    ready_rows = [row for row in rows if not row["blockers"]]
    summary = {
        "ready_count": len(ready_rows),
        "blocked_count": len(blockers),
        "gross": sum(
            (row["gross_amount"] for row in ready_rows),
            Decimal("0"),
        ),
        "employee_mpf": sum(
            (row["employee_mpf"] for row in ready_rows),
            Decimal("0"),
        ),
        "employer_mpf": sum(
            (row["employer_mpf"] for row in ready_rows),
            Decimal("0"),
        ),
        "net": sum(
            (row["net_amount"] for row in ready_rows),
            Decimal("0"),
        ),
    }
    return render_template(
        "payroll/index.html",
        year_month=year_month,
        selected_group=group,
        payroll_groups=PAYROLL_GROUPS,
        rows=rows,
        blockers=blockers,
        project_summary=project_summary(rows),
        counts=counts,
        summary=summary,
        formula_notes=FORMULA_NOTES,
        rule_version=RULE_VERSION,
    )


@payroll_bp.route("/final-payment")
@login_required
def final_payment():
    year_month = selected_month()
    group = selected_group()
    rows = calculate_final_payments(year_month, group)
    blockers = [row for row in rows if row["blockers"]]
    counts = {
        code: sum(1 for row in rows if row["group"] == code)
        for code in PAYROLL_GROUP_CODES
    }
    ready_rows = [row for row in rows if not row["blockers"]]
    summary = {
        "ready_count": len(ready_rows),
        "blocked_count": len(blockers),
        "gross": sum(
            (row["wage_income"] for row in ready_rows),
            Decimal("0"),
        ),
        "benefit": sum(
            (row["benefit"]["net"] for row in ready_rows),
            Decimal("0"),
        ),
        "net": sum(
            (row["net_amount"] for row in ready_rows),
            Decimal("0"),
        ),
    }
    return render_template(
        "payroll/final_payment.html",
        year_month=year_month,
        selected_group=group,
        payroll_groups=PAYROLL_GROUPS,
        rows=rows,
        blockers=blockers,
        counts=counts,
        summary=summary,
        formula_notes=FINAL_PAYMENT_FORMULA_NOTES,
        rule_version=FINAL_PAYMENT_RULE_VERSION,
    )


def nonnegative_form_decimal(name, default=Decimal("0")):
    value = parse_decimal(request.form.get(name), default)
    if value is None or value < 0:
        raise ValueError(name)
    return value


def optional_nonnegative_form_decimal(name):
    value = parse_decimal(request.form.get(name))
    if value is not None and value < 0:
        raise ValueError(name)
    return value


@payroll_bp.route(
    "/final-payment/<int:period_id>/save",
    methods=["POST"],
)
@login_required
def save_final_payment(period_id):
    period = db.get_or_404(EmployeeEmploymentPeriod, period_id)
    if not period.end_date:
        abort(400)
    year_month = request.form.get("year_month") or period.end_date.strftime(
        "%Y-%m"
    )
    group = request.form.get("payroll_group") or "all"
    if group not in {*PAYROLL_GROUP_CODES, "all"}:
        group = "all"
    case = final_payment_case(period)
    if case is None:
        case = EmployeeFinalPaymentCase(
            employee=period.employee,
            employment_period=period,
            settlement_month=year_month,
            status="active",
        )
        db.session.add(case)
    before = {
        "working_days": str(case.actual_working_days or ""),
        "ot_hours": str(case.actual_ot_hours or ""),
        "benefit_type": case.benefit_type,
        "legacy_leave_days": str(case.legacy_leave_days or ""),
        "post_2024_leave_days": str(case.post_2024_leave_days or ""),
    }
    try:
        case.actual_working_days = nonnegative_form_decimal("actual_working_days")
        case.actual_ot_hours = nonnegative_form_decimal("actual_ot_hours")
        case.actual_holiday_days = nonnegative_form_decimal(
            "actual_holiday_days"
        )
        large_ecall_count = nonnegative_form_decimal("large_ecall_count")
        ecall_count = nonnegative_form_decimal("ecall_count")
        if (
            large_ecall_count != large_ecall_count.to_integral_value()
            or ecall_count != ecall_count.to_integral_value()
        ):
            raise ValueError("ecall_count")
        case.large_ecall_count = int(large_ecall_count)
        case.ecall_count = int(ecall_count)
        case.allowance_amount = nonnegative_form_decimal("allowance_amount")
        case.other_payment = nonnegative_form_decimal("other_payment")
        case.overpay_amount = nonnegative_form_decimal("overpay_amount")
        case.underpay_amount = nonnegative_form_decimal("underpay_amount")
        case.legacy_leave_days = nonnegative_form_decimal("legacy_leave_days")
        case.post_2024_leave_days = nonnegative_form_decimal(
            "post_2024_leave_days"
        )
        case.statutory_holiday_days = nonnegative_form_decimal(
            "statutory_holiday_days"
        )
        case.leave_average_wage = nonnegative_form_decimal(
            "leave_average_wage"
        )
        case.leave_daily_rate_override = optional_nonnegative_form_decimal(
            "leave_daily_rate_override"
        )
        case.holiday_daily_rate_override = optional_nonnegative_form_decimal(
            "holiday_daily_rate_override"
        )
        case.pre_basis_last = optional_nonnegative_form_decimal("pre_basis_last")
        case.pre_basis_average = optional_nonnegative_form_decimal(
            "pre_basis_average"
        )
        case.post_basis_last = optional_nonnegative_form_decimal(
            "post_basis_last"
        )
        case.post_basis_average = optional_nonnegative_form_decimal(
            "post_basis_average"
        )
        case.mpf_offset_amount = nonnegative_form_decimal("mpf_offset_amount")
        case.special_compensation = nonnegative_form_decimal(
            "special_compensation"
        )
        period.payment_in_lieu = nonnegative_form_decimal("payment_in_lieu")
    except (ValueError, TypeError):
        db.session.rollback()
        flash("請檢查離職結算日數、次數及金額，不可填寫負數。", "error")
        return redirect(
            url_for(
                "payroll.final_payment",
                year_month=year_month,
                payroll_group=group,
            )
        )
    benefit_type = request.form.get("benefit_type", "none")
    if benefit_type not in {"none", "severance", "long_service"}:
        benefit_type = "none"
    case.benefit_type = benefit_type
    for prefix in ("pre", "post"):
        choice = request.form.get(f"{prefix}_basis_choice")
        setattr(
            case,
            f"{prefix}_basis_choice",
            choice if choice in {"last", "average"} else "last",
        )
    case.settlement_month = year_month
    case.remarks = request.form.get("remarks", "").strip() or None
    case.updated_by = current_user.id
    db.session.flush()
    write_audit(
        "final_payment_updated",
        "EmployeeFinalPaymentCase",
        case.id,
        employee_id=period.employee_id,
        detail=f"{year_month} / {group_for_period(period)}",
        before=before,
        after={
            "working_days": str(case.actual_working_days),
            "ot_hours": str(case.actual_ot_hours),
            "benefit_type": case.benefit_type,
            "legacy_leave_days": str(case.legacy_leave_days),
            "post_2024_leave_days": str(case.post_2024_leave_days),
        },
    )
    db.session.commit()
    flash("離職結算資料已保存，頁面金額已重新計算。", "success")
    return redirect(
        url_for(
            "payroll.final_payment",
            year_month=year_month,
            payroll_group=group,
        )
    )


def create_current_payroll_run(year_month, group):
    rows = calculate_payroll(year_month, group)
    blockers = [row for row in rows if row["blockers"]]
    if blockers:
        names = "、".join(
            f"{row['employee'].employee_no} ({' / '.join(row['blockers'])})"
            for row in blockers[:8]
        )
        suffix = "…" if len(blockers) > 8 else ""
        flash(f"暫時不能導出：{names}{suffix}", "error")
        return None
    if not rows:
        flash("此月份及組別沒有可出糧員工。", "error")
        return None
    run = snapshot_payroll(
        year_month,
        group,
        rows,
        current_user.id,
    )
    write_audit(
        "payroll_snapshot_created",
        "PayrollRun",
        run.id,
        detail=f"{year_month} / {group} / {len(run.employee_results)} 人",
    )
    db.session.commit()
    return run


def save_adjustment_evidence(employee, uploaded, current_document=None):
    if not uploaded or not uploaded.filename:
        return current_document
    path = store_employee_file(employee, uploaded, "change_evidence")
    document = EmployeeDocument(
        employee=employee,
        category="change_evidence",
        title="Payroll 調整憑證",
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
    if current_document and current_document.status == "active":
        current_document.status = "replaced"
        current_document.replaced_by_document_id = document.id
        current_document.replacement_reason = "更正 Payroll 調整憑證"
    return document


@payroll_bp.route("/payroll/preview", methods=["POST"])
@login_required
def preview_payroll():
    year_month = selected_month()
    group = selected_group()
    if create_current_payroll_run(year_month, group):
        flash("Payroll 計算已保存。", "success")
    return redirect(
        url_for(
            "payroll.attendance_payroll",
            year_month=year_month,
            payroll_group=group,
        )
    )


@payroll_bp.route("/payroll/export-current", methods=["GET", "POST"])
@login_required
def export_current_payroll():
    year_month = selected_month()
    group = selected_group()
    run = create_current_payroll_run(year_month, group)
    if not run:
        return redirect(
            url_for(
                "payroll.attendance_payroll",
                year_month=year_month,
                payroll_group=group,
            )
        )
    return export_payroll(run.id)


@payroll_bp.route("/employees/<int:employee_id>/payroll-adjustments", methods=["POST"])
@login_required
def add_adjustment(employee_id):
    employee = db.get_or_404(Employee, employee_id)
    year_month = selected_month()
    amount = parse_decimal(request.form.get("amount"))
    label = request.form.get("label", "").strip()
    if amount is None or not label:
        flash("請填寫調整名稱及金額。", "error")
    else:
        evidence = save_adjustment_evidence(
            employee,
            request.files.get("evidence"),
        )
        adjustment = PayrollAdjustment(
            employee=employee,
            year_month=year_month,
            label=label,
            amount=rounded(amount),
            project_id=request.form.get("project_id", type=int),
            evidence_document_id=evidence.id if evidence else None,
            remarks=request.form.get("remarks", "").strip() or None,
            status="active",
        )
        db.session.add(adjustment)
        db.session.flush()
        write_audit(
            "payroll_adjustment_added",
            "PayrollAdjustment",
            adjustment.id,
            employee_id=employee.id,
            detail=f"{year_month}: {label} {rounded(amount)}",
        )
        db.session.commit()
        flash("Payroll 調整已保存。", "success")
    return redirect(
        url_for(
            "employees.view_employee",
            employee_id=employee.id,
            tab="attendance",
        )
    )


@payroll_bp.route(
    "/payroll-adjustments/<int:adjustment_id>/correct",
    methods=["POST"],
)
@login_required
def correct_adjustment(adjustment_id):
    adjustment = db.get_or_404(PayrollAdjustment, adjustment_id)
    if adjustment.status != "active":
        abort(400)
    year_month = selected_month()
    amount = parse_decimal(request.form.get("amount"))
    label = request.form.get("label", "").strip()
    if amount is None or not label:
        flash("請填寫調整名稱及金額。", "error")
        return redirect(
            url_for(
                "employees.view_employee",
                employee_id=adjustment.employee_id,
                tab="attendance",
            )
        )
    before = {
        "year_month": adjustment.year_month,
        "label": adjustment.label,
        "amount": str(adjustment.amount),
        "project_id": adjustment.project_id,
    }
    adjustment.year_month = year_month
    adjustment.label = label
    adjustment.amount = rounded(amount)
    adjustment.project_id = request.form.get("project_id", type=int)
    adjustment.remarks = request.form.get("remarks", "").strip() or None
    evidence = save_adjustment_evidence(
        adjustment.employee,
        request.files.get("evidence"),
        adjustment.evidence_document,
    )
    if evidence:
        adjustment.evidence_document_id = evidence.id
    write_audit(
        "payroll_adjustment_corrected",
        "PayrollAdjustment",
        adjustment.id,
        employee_id=adjustment.employee_id,
        detail=f"{year_month}: {label}",
        before=before,
        after={
            "year_month": adjustment.year_month,
            "label": adjustment.label,
            "amount": str(adjustment.amount),
            "project_id": adjustment.project_id,
        },
    )
    db.session.commit()
    flash("Payroll 調整項目已更正。", "success")
    return redirect(
        url_for(
            "employees.view_employee",
            employee_id=adjustment.employee_id,
            tab="attendance",
        )
    )


@payroll_bp.route(
    "/payroll-adjustments/<int:adjustment_id>/withdraw",
    methods=["POST"],
)
@login_required
def withdraw_adjustment(adjustment_id):
    adjustment = db.get_or_404(PayrollAdjustment, adjustment_id)
    before = {
        "status": adjustment.status,
        "year_month": adjustment.year_month,
        "label": adjustment.label,
        "amount": str(adjustment.amount),
    }
    adjustment.status = "voided"
    write_audit(
        "payroll_adjustment_withdrawn",
        "PayrollAdjustment",
        adjustment.id,
        employee_id=adjustment.employee_id,
        detail=request.form.get("reason", "").strip() or "撤回錯誤記錄",
        before=before,
        after={
            "status": adjustment.status,
            "year_month": adjustment.year_month,
            "label": adjustment.label,
            "amount": str(adjustment.amount),
        },
    )
    db.session.commit()
    flash("Payroll 調整項目已撤回，不再參與計算。", "success")
    return redirect(
        url_for(
            "employees.view_employee",
            employee_id=adjustment.employee_id,
            tab="attendance",
        )
    )


def copy_row_format(sheet, source_row, target_row):
    sheet.row_dimensions[target_row].height = sheet.row_dimensions[source_row].height
    for column in range(1, sheet.max_column + 1):
        source = sheet.cell(source_row, column)
        target = sheet.cell(target_row, column)
        if source.has_style:
            target._style = copy(source._style)
        target.number_format = source.number_format
        target.alignment = copy(source.alignment)
        target.font = copy(source.font)
        target.fill = copy(source.fill)
        target.border = copy(source.border)
        target.protection = copy(source.protection)


def effective_rate(amount, units, fallback=0):
    amount = decimal_value(amount)
    units = decimal_value(units)
    if units:
        return amount / units
    return decimal_value(fallback)


def excel_number(value):
    text = format(decimal_value(value), "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def formula_matches(amount, rate, units):
    expected = rounded(decimal_value(rate) * decimal_value(units))
    return abs(expected - rounded(decimal_value(amount))) <= Decimal("0.01")


def employee_mpf_exempt(employee, month_end):
    if employee.mpf_mode == "exempt":
        return True
    if not employee.date_of_birth:
        return False
    age = month_end.year - employee.date_of_birth.year - (
        (month_end.month, month_end.day)
        < (employee.date_of_birth.month, employee.date_of_birth.day)
    )
    return age < 18 or age >= 65


def mpf_formulas(result, row_number, last_row, total_column, days_column, first):
    if not first or employee_mpf_exempt(
        result.employee,
        parse_year_month(result.run.year_month)[1],
    ):
        return "=0", "=0"

    employee_number = f"E{row_number}"
    employee_range = f"$E$7:$E${last_row}"
    total_range = f"${total_column}$7:${total_column}${last_row}"
    days_range = f"${days_column}$7:${days_column}${last_row}"
    income = (
        f"SUMIF({employee_range},{employee_number},{total_range})"
    )
    days = f"SUMIF({employee_range},{employee_number},{days_range})"

    if result.employee.mpf_mode == "casual":
        calculation = result.calculation_json or {}
        net_days = (
            decimal_value(calculation.get("current_actual_days"))
            + decimal_value(calculation.get("current_forecast_days"))
            + decimal_value(calculation.get("previous_actual_days"))
            - decimal_value(calculation.get("previous_forecast_days"))
        )
        days = excel_number(max(Decimal("0"), net_days))
        daily_income = f"({income}/MAX(1,{days}))"
        employee_daily = (
            f"IF({daily_income}<280,0,"
            f"IF({daily_income}<350,15,"
            f"IF({daily_income}<450,20,"
            f"IF({daily_income}<550,25,"
            f"IF({daily_income}<650,30,"
            f"IF({daily_income}<750,35,"
            f"IF({daily_income}<850,40,"
            f"IF({daily_income}<950,45,50))))))))"
        )
        employer_daily = (
            f"IF({daily_income}<280,10,"
            f"IF({daily_income}<350,15,"
            f"IF({daily_income}<450,20,"
            f"IF({daily_income}<550,25,"
            f"IF({daily_income}<650,30,"
            f"IF({daily_income}<750,35,"
            f"IF({daily_income}<850,40,"
            f"IF({daily_income}<950,45,50))))))))"
        )
        employee_formula = (
            f"=ROUND(IF({days}=0,0,{employee_daily}*{days}),2)"
        )
        employer_formula = (
            f"=ROUND(IF({days}=0,0,{employer_daily}*{days}),2)"
        )
        return employee_formula, employer_formula

    employee_formula = (
        f"=ROUND(IF({income}<7100,0,MIN({income}*0.05,1500)),2)"
    )
    employer_formula = f"=ROUND(MIN({income}*0.05,1500),2)"
    return employee_formula, employer_formula


def ecall_formula(line, row_number, rate_column, rate_value, previous=False):
    prefix = "previous_" if previous else "current_"
    large_count = decimal_value(line.get(f"{prefix}large_ecall_count"))
    normal_count = decimal_value(line.get(f"{prefix}ecall_count"))
    large_amount = decimal_value(
        line.get(f"{prefix}large_ecall_amount")
        if previous
        else line.get("large_ecall_amount")
    )
    terms = []
    if large_count:
        rate_expression = f"{rate_column}{row_number}"
        if not formula_matches(large_amount, rate_value, large_count):
            rate_expression = excel_number(
                effective_rate(large_amount, large_count, rate_value)
            )
        terms.append(f"{excel_number(large_count)}*{rate_expression}")
    if normal_count:
        terms.append(f"{excel_number(normal_count)}*400")
    return f"=ROUND({'+'.join(terms) if terms else '0'},2)"


def template_path():
    configured = (
        Path(current_app.config["PAYROLL_TEMPLATE_ROOT"])
        / "Payroll_PC_AD014_V1_Template.xlsx"
    )
    if not configured.exists():
        abort(500, "Payroll template is missing")
    return configured


def period_labels(sheet, year_month):
    month_start, month_end = parse_year_month(year_month)
    previous_end = month_start - date.resolution
    previous_start = previous_end.replace(day=21)
    sheet["F4"] = month_start
    sheet["F4"].number_format = "yyyy-mm-dd"
    current_period_cell = "M4" if sheet.title == "日工" else "N4"
    previous_period_cell = "T4" if sheet.title == "日工" else "U4"
    sheet[current_period_cell] = (
        f"{month_start:%d/%m/%Y} - "
        f"{month_start.replace(day=20):%d/%m/%Y}"
    )
    sheet[previous_period_cell] = (
        f"{previous_start:%d/%m/%Y} - {previous_end:%d/%m/%Y}"
    )
    sheet["G5"] = calendar.monthrange(month_start.year, month_start.month)[1]


def result_lines(result):
    calculation = result.calculation_json or {}
    return calculation.get("lines") or [
        {
            "project": None,
            "working_days": "0",
            "holiday_days": "0",
            "current_ot_hours": "0",
            "previous_ot_hours": "0",
            "previous_holiday_days": "0",
            "current_large_ecall_count": "0",
            "current_ecall_count": "0",
            "previous_large_ecall_count": "0",
            "previous_ecall_count": "0",
            "base_amount": str(result.base_amount),
            "holiday_amount": str(result.holiday_amount),
            "ot_amount": str(result.ot_amount),
            "previous_ot_amount": "0",
            "previous_holiday_amount": "0",
            "large_ecall_amount": str(result.large_ecall_amount),
            "ecall_amount": str(result.ecall_amount),
            "previous_large_ecall_amount": "0",
            "previous_ecall_amount": "0",
            "allowance_amount": str(result.allowance_amount),
            "adjustment_amount": str(result.adjustment_amount),
            "gross_amount": str(result.gross_amount),
            "base_rate": "0",
            "holiday_rate": "0",
            "ot_rate": "0",
            "ot_divisor": "9",
        }
    ]


def project_for_line(line):
    project_id = line.get("project")
    return db.session.get(WorkProject, project_id) if project_id else None


def employee_position(employee):
    assignment = employee.current_assignment
    position = assignment.primary_position if assignment else None
    return position.display_name if position else ""


def ecall_amount(line, previous=False):
    prefix = "previous_" if previous else ""
    return (
        decimal_value(line.get(f"{prefix}large_ecall_amount"))
        + decimal_value(line.get(f"{prefix}ecall_amount"))
    )


def count_text(value):
    number = decimal_value(value)
    if number == number.to_integral_value():
        return str(int(number))
    return format(number.normalize(), "f")


def ecall_note(line):
    parts = []
    current_large = decimal_value(line.get("current_large_ecall_count"))
    current_regular = decimal_value(line.get("current_ecall_count"))
    previous_large = decimal_value(line.get("previous_large_ecall_count"))
    previous_regular = decimal_value(line.get("previous_ecall_count"))
    if current_large or current_regular:
        parts.append(
            "本期 "
            f"大 E-CALL {count_text(current_large)} 次 / "
            f"E-CALL {count_text(current_regular)} 次"
        )
    if previous_large or previous_regular:
        parts.append(
            "上月尾 "
            f"大 E-CALL {count_text(previous_large)} 次 / "
            f"E-CALL {count_text(previous_regular)} 次"
        )
    return "；".join(parts)


def set_ecall_headers(sheet):
    current_column = 19 if sheet.title == "日工" else 20
    previous_column = 26 if sheet.title == "日工" else 27
    for column in (current_column, previous_column):
        sheet.cell(5, column).value = "E-CALL"
        sheet.cell(6, column).value = "Amount\nE-CALL 金額"


def monthly_values(result, line, first, row_number):
    employee = result.employee
    project = project_for_line(line)
    calculation = result.calculation_json or {}
    current_ot_hours = decimal_value(line.get("current_ot_hours"))
    previous_ot_hours = decimal_value(line.get("previous_ot_hours"))
    holiday_days = decimal_value(line.get("holiday_days"))
    previous_holiday_days = decimal_value(line.get("previous_holiday_days"))
    working_days = decimal_value(line.get("working_days"))
    base_rate = effective_rate(
        line.get("base_amount"),
        working_days,
        line.get("base_rate"),
    )
    current_ot_rate = effective_rate(
        line.get("ot_amount"),
        current_ot_hours,
        line.get("ot_rate"),
    )
    previous_ot_rate = effective_rate(
        line.get("previous_ot_amount"),
        previous_ot_hours,
        line.get("ot_rate"),
    )
    holiday_rate = effective_rate(
        line.get("holiday_amount"),
        holiday_days,
        line.get("holiday_rate"),
    )
    previous_holiday_rate = effective_rate(
        line.get("previous_holiday_amount"),
        previous_holiday_days,
        line.get("holiday_rate"),
    )
    line_gross = decimal_value(line.get("gross_amount"))
    overpay = decimal_value(result.overpay_amount) if first else Decimal("0")
    underpay = decimal_value(result.underpay_amount) if first else Decimal("0")
    total = line_gross - overpay + underpay
    net = total
    if first:
        net = (
            total
            - decimal_value(result.employee_mpf)
            + decimal_value(result.payment_in_lieu)
            + decimal_value(result.severance_long_service)
        )
    return {
        1: row_number - 6,
        2: project.name if project else "未分配",
        3: "是" if calculation.get("group") == "management" else "",
        4: "eMPF",
        5: employee.employee_no,
        6: employee.english_name,
        7: employee.chinese_name,
        8: employee_position(employee),
        9: employee.current_period.start_date if employee.current_period else None,
        10: float(decimal_value(calculation.get("salary_amount"))),
        11: float(base_rate),
        12: float(working_days),
        13: float(decimal_value(line.get("base_amount"))),
        14: float(current_ot_hours),
        15: float(current_ot_rate),
        16: float(decimal_value(line.get("ot_amount"))),
        17: float(holiday_days),
        18: float(holiday_rate),
        19: float(decimal_value(line.get("holiday_amount"))),
        21: float(previous_ot_hours),
        22: float(previous_ot_rate),
        23: float(decimal_value(line.get("previous_ot_amount"))),
        24: float(previous_holiday_days),
        25: float(previous_holiday_rate),
        26: float(decimal_value(line.get("previous_holiday_amount"))),
        20: float(ecall_amount(line)),
        27: float(ecall_amount(line, previous=True)),
        28: float(decimal_value(line.get("allowance_amount"))),
        29: 0,
        30: 0,
        31: 0,
        32: float(overpay),
        33: float(underpay),
        34: float(decimal_value(line.get("adjustment_amount"))),
        35: 1,
        36: float(total),
        37: float(decimal_value(result.employee_mpf)) if first else 0,
        38: float(decimal_value(result.employer_mpf)) if first else 0,
        39: 0,
        40: 0,
        41: float(decimal_value(result.payment_in_lieu)) if first else 0,
        42: (
            float(decimal_value(result.severance_long_service))
            if first
            else 0
        ),
        43: float(net),
    }


def daily_values(result, line, first, row_number):
    employee = result.employee
    project = project_for_line(line)
    calculation = result.calculation_json or {}
    working_days = decimal_value(line.get("working_days"))
    current_ot_hours = decimal_value(line.get("current_ot_hours"))
    previous_ot_hours = decimal_value(line.get("previous_ot_hours"))
    holiday_days = decimal_value(line.get("holiday_days"))
    previous_holiday_days = decimal_value(line.get("previous_holiday_days"))
    base_rate = effective_rate(
        line.get("base_amount"),
        working_days,
        calculation.get("salary_amount"),
    )
    current_ot_rate = effective_rate(
        line.get("ot_amount"),
        current_ot_hours,
        line.get("ot_rate"),
    )
    previous_ot_rate = effective_rate(
        line.get("previous_ot_amount"),
        previous_ot_hours,
        line.get("ot_rate"),
    )
    holiday_rate = effective_rate(
        line.get("holiday_amount"),
        holiday_days,
        line.get("holiday_rate"),
    )
    previous_holiday_rate = effective_rate(
        line.get("previous_holiday_amount"),
        previous_holiday_days,
        line.get("holiday_rate"),
    )
    line_gross = decimal_value(line.get("gross_amount"))
    overpay = decimal_value(result.overpay_amount) if first else Decimal("0")
    underpay = decimal_value(result.underpay_amount) if first else Decimal("0")
    total = line_gross - overpay + underpay
    net = total
    if first:
        net = (
            total
            - decimal_value(result.employee_mpf)
            + decimal_value(result.payment_in_lieu)
            + decimal_value(result.severance_long_service)
        )
    return {
        1: row_number - 6,
        2: project.name if project else "未分配",
        3: "",
        4: "eMPF",
        5: employee.employee_no,
        6: employee.english_name,
        7: employee.chinese_name,
        8: employee_position(employee),
        9: employee.current_period.start_date if employee.current_period else None,
        10: float(base_rate),
        11: float(working_days),
        12: float(decimal_value(line.get("base_amount"))),
        13: float(current_ot_hours),
        14: float(current_ot_rate),
        15: float(decimal_value(line.get("ot_amount"))),
        16: float(holiday_days),
        17: float(holiday_rate),
        18: float(decimal_value(line.get("holiday_amount"))),
        20: float(previous_ot_hours),
        21: float(previous_ot_rate),
        22: float(decimal_value(line.get("previous_ot_amount"))),
        23: float(previous_holiday_days),
        24: float(previous_holiday_rate),
        25: float(decimal_value(line.get("previous_holiday_amount"))),
        19: float(ecall_amount(line)),
        26: float(ecall_amount(line, previous=True)),
        27: float(decimal_value(line.get("allowance_amount"))),
        28: 0,
        29: 0,
        30: 0,
        31: float(overpay),
        32: float(underpay),
        33: float(decimal_value(line.get("adjustment_amount"))),
        34: 1,
        35: float(total),
        36: float(decimal_value(result.employee_mpf)) if first else 0,
        37: float(decimal_value(result.employer_mpf)) if first else 0,
        38: 0,
        39: 0,
        40: float(decimal_value(result.payment_in_lieu)) if first else 0,
        41: (
            float(decimal_value(result.severance_long_service))
            if first
            else 0
        ),
        42: float(net),
    }


def monthly_formulas(result, line, first, row_number, last_row, values):
    working_days = decimal_value(line.get("working_days"))
    current_ot_hours = decimal_value(line.get("current_ot_hours"))
    previous_ot_hours = decimal_value(line.get("previous_ot_hours"))
    holiday_days = decimal_value(line.get("holiday_days"))
    previous_holiday_days = decimal_value(line.get("previous_holiday_days"))
    base_rate = decimal_value(values[11])
    formulas = {
        13: f"=ROUND(K{row_number}*L{row_number},2)",
        16: f"=ROUND(O{row_number}*N{row_number},2)",
        19: f"=ROUND(R{row_number}*Q{row_number},2)",
        20: ecall_formula(
            line,
            row_number,
            "K",
            base_rate,
        ),
        23: f"=ROUND(V{row_number}*U{row_number},2)",
        26: f"=ROUND(Y{row_number}*X{row_number},2)",
        27: ecall_formula(
            line,
            row_number,
            "K",
            base_rate,
            previous=True,
        ),
        30: f"=K{row_number}",
        31: f"=ROUND(AC{row_number}*AD{row_number},2)",
        36: (
            f"=ROUND(M{row_number}+P{row_number}+S{row_number}"
            f"+T{row_number}+AB{row_number}+AE{row_number}"
            f"-AF{row_number}+AG{row_number}+AH{row_number},2)"
        ),
        43: (
            f"=ROUND(AJ{row_number}-AK{row_number}+AM{row_number}"
            f"+AN{row_number}+AO{row_number}+AP{row_number},2)"
        ),
    }

    month_start = parse_year_month(result.run.year_month)[0]
    month_days = Decimal(calendar.monthrange(month_start.year, month_start.month)[1])
    standard_rate = decimal_value(values[10]) / month_days
    if formula_matches(line.get("base_amount"), standard_rate, working_days):
        formulas[11] = f"=J{row_number}/$G$5"
        base_rate = standard_rate

    current_ot_rate = base_rate / Decimal("9") * Decimal("1.5")
    if formula_matches(line.get("ot_amount"), current_ot_rate, current_ot_hours):
        formulas[15] = f"=K{row_number}/9*1.5"
    if formula_matches(
        line.get("previous_ot_amount"),
        current_ot_rate,
        previous_ot_hours,
    ):
        formulas[22] = f"=K{row_number}/9*1.5"
    if formula_matches(line.get("holiday_amount"), base_rate, holiday_days):
        formulas[18] = f"=K{row_number}"
    if formula_matches(
        line.get("previous_holiday_amount"),
        base_rate,
        previous_holiday_days,
    ):
        formulas[25] = f"=K{row_number}"

    employee_mpf, employer_mpf = mpf_formulas(
        result,
        row_number,
        last_row,
        "AJ",
        "L",
        first,
    )
    formulas[37] = employee_mpf
    formulas[38] = employer_mpf
    return formulas


def daily_formulas(result, line, first, row_number, last_row, values):
    working_days = decimal_value(line.get("working_days"))
    current_ot_hours = decimal_value(line.get("current_ot_hours"))
    previous_ot_hours = decimal_value(line.get("previous_ot_hours"))
    holiday_days = decimal_value(line.get("holiday_days"))
    previous_holiday_days = decimal_value(line.get("previous_holiday_days"))
    base_rate = decimal_value(values[10])
    divisor = decimal_value(line.get("ot_divisor")) or Decimal("9")
    formulas = {
        12: f"=ROUND(J{row_number}*K{row_number},2)",
        15: f"=ROUND(N{row_number}*M{row_number},2)",
        18: f"=ROUND(Q{row_number}*P{row_number},2)",
        19: ecall_formula(
            line,
            row_number,
            "J",
            base_rate,
        ),
        22: f"=ROUND(U{row_number}*T{row_number},2)",
        25: f"=ROUND(X{row_number}*W{row_number},2)",
        26: ecall_formula(
            line,
            row_number,
            "J",
            base_rate,
            previous=True,
        ),
        29: f"=J{row_number}",
        30: f"=ROUND(AB{row_number}*AC{row_number},2)",
        35: (
            f"=ROUND(L{row_number}+O{row_number}+R{row_number}"
            f"+S{row_number}+AA{row_number}+AD{row_number}"
            f"-AE{row_number}+AF{row_number}+AG{row_number},2)"
        ),
        42: (
            f"=ROUND(AI{row_number}-AJ{row_number}+AL{row_number}"
            f"+AM{row_number}+AN{row_number}+AO{row_number},2)"
        ),
    }

    ot_rate = base_rate / divisor * Decimal("1.5")
    if formula_matches(line.get("ot_amount"), ot_rate, current_ot_hours):
        formulas[14] = (
            f"=J{row_number}/{excel_number(divisor)}*1.5"
        )
    if formula_matches(
        line.get("previous_ot_amount"),
        ot_rate,
        previous_ot_hours,
    ):
        formulas[21] = (
            f"=J{row_number}/{excel_number(divisor)}*1.5"
        )
    if formula_matches(line.get("holiday_amount"), base_rate, holiday_days):
        formulas[17] = f"=J{row_number}"
    if formula_matches(
        line.get("previous_holiday_amount"),
        base_rate,
        previous_holiday_days,
    ):
        formulas[24] = f"=J{row_number}"

    employee_mpf, employer_mpf = mpf_formulas(
        result,
        row_number,
        last_row,
        "AI",
        "K",
        first,
    )
    formulas[36] = employee_mpf
    formulas[37] = employer_mpf
    return formulas


def build_group_workbook(run, group):
    source = load_workbook(template_path())
    if source.calculation is None:
        source.calculation = CalcProperties()
    source.calculation.calcMode = "auto"
    source.calculation.fullCalcOnLoad = True
    source.calculation.forceFullCalc = True
    source.calculation.calcOnSave = True
    keep = GROUP_SHEETS[group]
    for sheet_name in list(source.sheetnames):
        if sheet_name != keep:
            del source[sheet_name]
    sheet = source[keep]
    period_labels(sheet, run.year_month)
    set_ecall_headers(sheet)
    results = [
        result
        for result in run.employee_results
        if (result.calculation_json or {}).get("group") == group
    ]
    output_rows = []
    for result in results:
        lines = result_lines(result)
        for index, line in enumerate(lines):
            output_rows.append((result, line, index == 0))
    last_row = 6 + len(output_rows)
    if len(output_rows) > 1:
        sheet.insert_rows(8, amount=len(output_rows) - 1)
    if not output_rows:
        for column in range(1, sheet.max_column + 1):
            sheet.cell(7, column).value = None
    for index, (result, line, first) in enumerate(output_rows, start=7):
        copy_row_format(sheet, 7, index)
        for column in range(1, sheet.max_column + 1):
            sheet.cell(index, column).value = None
        values = (
            daily_values(result, line, first, index)
            if group == "site_daily"
            else monthly_values(result, line, first, index)
        )
        for column, value in values.items():
            sheet.cell(index, column).value = value
        formulas = (
            daily_formulas(result, line, first, index, last_row, values)
            if group == "site_daily"
            else monthly_formulas(result, line, first, index, last_row, values)
        )
        for column, formula in formulas.items():
            sheet.cell(index, column).value = formula
        last_column = 43 if group == "site_daily" else 44
        warnings = "；".join(result.warnings_json or [])
        if decimal_value(line.get("ot_divisor")) == Decimal("10"):
            warnings = "；".join(
                item for item in [warnings, "HA 日工 OT 除數 10"] if item
            )
        warnings = "；".join(
            item for item in [warnings, ecall_note(line)] if item
        )
        sheet.cell(index, last_column).value = warnings
        for column in range(10, last_column):
            sheet.cell(index, column).number_format = "#,##0.00"
        sheet.cell(index, 9).number_format = "yyyy-mm-dd"
    sheet.freeze_panes = "A7"
    return source


def final_payment_template_path():
    configured = (
        Path(current_app.config["PAYROLL_TEMPLATE_ROOT"])
        / "Final_Payment_V1_Template.xlsx"
    )
    if not configured.exists():
        abort(500, "Final Payment template is missing")
    return configured


def build_final_payment_workbook(year_month, group, rows):
    workbook = load_workbook(final_payment_template_path())
    if workbook.calculation is None:
        workbook.calculation = CalcProperties()
    workbook.calculation.calcMode = "auto"
    workbook.calculation.fullCalcOnLoad = True
    workbook.calculation.forceFullCalc = True
    workbook.calculation.calcOnSave = True
    sheet = workbook.active
    sheet.title = GROUP_SHEETS[group]
    sheet["A1"] = "Final Payment Calculation"
    sheet["A2"] = f"Settlement month: {year_month}"
    sheet["A3"] = f"Payroll group: {dict(PAYROLL_GROUPS).get(group, group)}"
    headers = {
        1: "No.",
        2: "English Name",
        3: "Chinese Name",
        4: "Employee No.",
        5: "Position",
        6: "Date Joined",
        7: "Last Date",
        8: "Actual Working Day(s)",
        9: "Rate",
        10: "Basic Salary",
        11: "OT Hours",
        12: "OT Rate",
        13: "OT Amount",
        14: "Holiday Day(s)",
        15: "Holiday Rate",
        16: "Holiday Amount",
        17: "E-CALL",
        18: "Allowance / Other / Adjustment",
        19: "Payment in Lieu",
        20: "SP / LSP / Compensation",
        21: "Annual Leave / Statutory Holiday Pay",
        22: "Gross Total",
        23: "Employee MPF",
        24: "Net Total",
        25: "Actual Payment",
        26: "Remarks",
    }
    for column, value in headers.items():
        sheet.cell(7, column).value = value
    if len(rows) > 1:
        sheet.insert_rows(9, amount=len(rows) - 1)
    if not rows:
        for column in range(1, 27):
            sheet.cell(8, column).value = None
    for row_number, result in enumerate(rows, start=8):
        copy_row_format(sheet, 8, row_number)
        for column in range(1, 27):
            sheet.cell(row_number, column).value = None
        employee = result["employee"]
        position = employee_position(employee)
        combined_adjustment = (
            result["allowance_amount"]
            + result["other_payment"]
            - result["overpay_amount"]
            + result["underpay_amount"]
        )
        service_payment = (
            result["benefit"]["net"] + result["special_compensation"]
        )
        leave_payment = (
            result["annual_leave_pay"] + result["statutory_holiday_pay"]
        )
        values = {
            1: row_number - 7,
            2: employee.english_name,
            3: employee.chinese_name,
            4: employee.employee_no,
            5: position,
            6: result["period"].start_date,
            7: result["period"].end_date,
            8: float(result["working_days"]),
            9: float(result["base_rate"]),
            11: float(result["ot_hours"]),
            12: float(result["ot_rate"]),
            14: float(result["holiday_days"]),
            15: float(result["holiday_rate"]),
            17: float(result["ecall_amount"]),
            18: float(combined_adjustment),
            19: float(result["payment_in_lieu"]),
            20: float(service_payment),
            21: float(leave_payment),
            23: -float(result["employee_mpf"]),
            26: "；".join(
                filter(
                    None,
                    (
                        result["case"].remarks if result["case"] else None,
                        (
                            "遣散費"
                            if result["benefit"]["type"] == "severance"
                            else "長期服務金"
                            if result["benefit"]["type"] == "long_service"
                            else None
                        ),
                        f"僱主 MPF {result['employer_mpf']:,.2f}",
                    ),
                )
            ),
        }
        for column, value in values.items():
            sheet.cell(row_number, column).value = value
        sheet.cell(row_number, 10).value = f"=ROUND(H{row_number}*I{row_number},2)"
        sheet.cell(row_number, 13).value = f"=ROUND(K{row_number}*L{row_number},2)"
        sheet.cell(row_number, 16).value = f"=ROUND(N{row_number}*O{row_number},2)"
        sheet.cell(row_number, 22).value = (
            f"=ROUND(J{row_number}+M{row_number}+P{row_number}+Q{row_number}"
            f"+R{row_number}+S{row_number}+T{row_number}+U{row_number},2)"
        )
        sheet.cell(row_number, 24).value = f"=ROUND(V{row_number}+W{row_number},2)"
        sheet.cell(row_number, 25).value = f"=X{row_number}"
        for column in range(8, 26):
            sheet.cell(row_number, column).number_format = "#,##0.00"
        for column in (6, 7):
            sheet.cell(row_number, column).number_format = "yyyy-mm-dd"
    sheet.freeze_panes = "A8"
    return workbook


def workbook_bytes(workbook):
    memory = io.BytesIO()
    workbook.save(memory)
    memory.seek(0)
    return memory


@payroll_bp.route("/final-payment/export", methods=["POST"])
@login_required
def export_final_payment():
    year_month = selected_month()
    group = selected_group()
    rows = calculate_final_payments(year_month, group)
    blockers = [row for row in rows if row["blockers"]]
    if not rows:
        flash("所選月份沒有離職員工。", "error")
        return redirect(
            url_for(
                "payroll.final_payment",
                year_month=year_month,
                payroll_group=group,
            )
        )
    if blockers:
        flash("請先完成所有離職員工的結算資料，才可匯出。", "error")
        return redirect(
            url_for(
                "payroll.final_payment",
                year_month=year_month,
                payroll_group=group,
            )
        )
    write_audit(
        "final_payment_exported",
        "EmployeeFinalPaymentCase",
        detail=f"{year_month} / {group} / {len(rows)} 人",
    )
    db.session.commit()
    if group != "all":
        return send_file(
            workbook_bytes(build_final_payment_workbook(year_month, group, rows)),
            as_attachment=True,
            download_name=f"HKR_Final_Payment_{year_month}_{group}.xlsx",
            mimetype=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
        )
    archive_memory = io.BytesIO()
    with zipfile.ZipFile(
        archive_memory,
        "w",
        compression=zipfile.ZIP_DEFLATED,
    ) as archive:
        for selected in PAYROLL_GROUP_CODES:
            selected_rows = [row for row in rows if row["group"] == selected]
            workbook = build_final_payment_workbook(
                year_month,
                selected,
                selected_rows,
            )
            archive.writestr(
                f"HKR_Final_Payment_{year_month}_{selected}.xlsx",
                workbook_bytes(workbook).getvalue(),
            )
    archive_memory.seek(0)
    return send_file(
        archive_memory,
        as_attachment=True,
        download_name=f"HKR_Final_Payment_{year_month}_ALL.zip",
        mimetype="application/zip",
    )


@payroll_bp.route("/payroll/runs/<int:run_id>/export")
@login_required
def export_payroll(run_id):
    run = db.get_or_404(PayrollRun, run_id)
    group = request.args.get("payroll_group") or run.payroll_group
    if group not in {*PAYROLL_GROUP_CODES, "all"}:
        abort(400)
    available = {
        (result.calculation_json or {}).get("group")
        for result in run.employee_results
    }
    groups = (
        [code for code in PAYROLL_GROUP_CODES if code in available]
        if group == "all"
        else [group]
    )
    if not groups or any(code not in available for code in groups):
        flash("此計算快照不包含所選 Payroll 組別。", "error")
        return redirect(
            url_for(
                "payroll.attendance_payroll",
                year_month=run.year_month,
                payroll_group=run.payroll_group,
                run_id=run.id,
            )
        )
    write_audit(
        "payroll_exported",
        "PayrollRun",
        run.id,
        detail=f"{run.year_month} / {group}",
    )
    db.session.commit()
    if len(groups) == 1:
        selected = groups[0]
        return send_file(
            workbook_bytes(build_group_workbook(run, selected)),
            as_attachment=True,
            download_name=f"HKR_Payroll_{run.year_month}_{selected}.xlsx",
            mimetype=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
        )
    archive_memory = io.BytesIO()
    with zipfile.ZipFile(
        archive_memory,
        "w",
        compression=zipfile.ZIP_DEFLATED,
    ) as archive:
        for selected in groups:
            workbook = build_group_workbook(run, selected)
            archive.writestr(
                f"HKR_Payroll_{run.year_month}_{selected}.xlsx",
                workbook_bytes(workbook).getvalue(),
            )
    archive_memory.seek(0)
    return send_file(
        archive_memory,
        as_attachment=True,
        download_name=f"HKR_Payroll_{run.year_month}_ALL.zip",
        mimetype="application/zip",
    )
