from tools.payroll_review import review_sources
from tools.payroll_export_policy import export_message, saved_export_message, policy_text, export_issues, is_payroll_ready
from tools.payroll_exchange import valid_rate, exchange_settings
from tools.payroll_engine import currency_summary
import json
from types import SimpleNamespace
from tools.attendance_rates import allocation_issue
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
    session,
    send_file,
    url_for,
)
from flask_login import current_user, login_required
from tools.i18n import TRANSLATIONS
from openpyxl import load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.workbook.properties import CalcProperties

from openpyxl.comments import Comment
from models import (
    AttendanceCorrection,
    Employee,
    EmployeeDocument,
    EmployeeEmploymentPeriod,
    EmployeeFinalPaymentCase,
    MpfScheme,
    PayrollAdjustment,
    AttendanceMonthlySummary,
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
    current_assignment_on,
    current_mpf_on,
    file_sha256,
    parse_decimal,
    parse_year_month,
    reference_options,
    store_employee_file,
    write_audit,
)
from tools.payroll_engine import (
    PAYROLL_GROUP_CODES,
    RULE_VERSION,
    calculate_payroll,
    employees_for_payroll,
    decimal_value,
    project_summary,
    rounded,
    snapshot_payroll,
    snapshot_employee,
)
from tools.attendance_policy import assignment_workweek_days
from tools.text_search import chinese_search_variants


payroll_bp = Blueprint("payroll", __name__)

GROUP_SHEETS = {
    "site_monthly": "月工",
    "management": "OFFICE",
    "site_daily": "日工",
}

FORMULA_NOTES = [
    "payroll.rule.period",
    "payroll.rule.monthly",
    "payroll.rule.monthly_pay_methods",
    "payroll.rule.daily",
    "payroll.rule.ha",
    "payroll.rule.ecall",
    "payroll.rule.holiday_calendar",
    "payroll.rule.forecast",
    "payroll.rule.reconciliation",
    "payroll.rule.departure",
    "payroll.rule.mpf",
    "payroll.rule.no_attendance_required",
    "payroll.rule.special_day",
    "payroll.rule.leave",
    "payroll.rule.work_injury",
    "payroll.rule.allowance",
    "payroll.rule.xlsx_formulas",
    "payroll.rule.absence_rate",
    "payroll.rule.blockers",
]

FINAL_PAYMENT_FORMULA_NOTES = [
    "final_payment.rule.actual_attendance",
    "final_payment.rule.departure_payroll",
    "final_payment.rule.pay_components",
    "final_payment.rule.annual_leave",
    "final_payment.rule.statutory_holiday",
    "final_payment.rule.eligibility",
    "final_payment.rule.monthly_basis",
    "final_payment.rule.daily_basis",
    "final_payment.rule.transition",
    "final_payment.rule.service_proration",
    "final_payment.rule.cap",
    "final_payment.rule.mpf_offset",
    "final_payment.rule.wage_definition",
    "final_payment.rule.hr_check",
]

LABOUR_DEPARTMENT_RULE_SOURCES = [
    {
        "label_key": "final_payment.source_employment_ordinance",
        "url": "https://www.labour.gov.hk/tc/faq/cap57l_whole.htm",
    },
    {
        "label_key": "final_payment.source_mpf_transition",
        "url": "https://www.op.labour.gov.hk/tc/before-1-may.html",
    },
    {
        "label_key": "final_payment.source_calculator",
        "url": "https://www.lr.labour.gov.hk/web/tc/calculator/index.html",
    },
]

FINAL_PAYMENT_EXPORT_RULES_ZH_HANT = [
    "離職 Payroll 自動承接最後工作日前生效的固定補貼、指定月份調整、考勤替班其他津貼及工傷醫療實銷；手動補貼／其他應付只用於沒有其他系統來源的例外款項，不可重複輸入。工傷醫療實銷增加實發金額，但不納入 MPF 有關入息。",
    "遣散費：僱員須按連續性合約受僱不少於 24 個月，並符合裁員、因裁員不獲續約或停工等法定條件。",
    "長期服務金：僱員須按連續性合約受僱滿 5 年，並符合《僱傭條例》指定的終止僱傭情況。同一段受僱期不可同時取得遣散費及長期服務金。",
    "月薪僱員：每年款額為所選月薪工資基數乘以 2/3。僱員可選最後一個完整月份工資，或有關日期前 12 個月的平均月薪。",
    "日薪或件薪僱員：每年款額為最後 30 個正常工作日中由僱員選取任何 18 日的工資總和；僱員亦可選有關日期前 12 個月平均日薪的 18 倍。『最後 30 日』只是選取範圍，不是把 30 日工資全部相加。",
    "受僱期橫跨 2025-05-01 且屬轉制安排涵蓋僱員時，轉制日前及轉制日起的服務期分開計算；轉制前使用緊接轉制日前的工資基數，轉制後使用終止僱傭前的工資基數。",
    "未滿一年的服務期按實際可追溯服務期比例計算，不把未滿一年直接當作一整年。",
    "每年計算基數上限為 HKD 15,000；遣散費／長期服務金總額上限為 HKD 390,000。超額部分先從轉制後部分扣減。",
    "僱主強制性 MPF 供款累算權益只可抵銷轉制前部分，不可抵銷轉制後部分；實際可抵銷額由 HR 核對後輸入。",
    "法定『工資』不一定只等於合同基本薪金；HR 須按《僱傭條例》核對應包括及應排除的工資項目。",
    "系統計算只供 HR 初步核對，不取代勞工處計算機、僱傭合約、個案事實或法律意見。",
]


def selected_group():
    value = request.values.get("payroll_group") or "all"
    return value if value in {*PAYROLL_GROUP_CODES, "all"} else "all"


def selected_month():
    value = request.values.get("year_month") or session.get("operating_month") or date.today().strftime("%Y-%m")
    try:
        datetime.strptime(value, "%Y-%m")
    except ValueError:
        value = date.today().strftime("%Y-%m")
    session["operating_month"] = value
    return value


def selected_payroll_entity():
    value = request.values.get("payroll_entity_id", session.get("operating_entity_id", ""))
    value = str(value or "").strip()
    session["operating_entity_id"] = value
    return int(value) if value.isdigit() else None


@payroll_bp.route("/attendance-payroll")
@login_required
def attendance_payroll():
    year_month = selected_month()
    group = selected_group()
    payroll_entity_id = selected_payroll_entity()
    if request.args.get("status") == "unassigned":
        payroll_entity_id = None
        session["operating_entity_id"] = ""
    _, month_end = parse_year_month(year_month)
    population = employees_for_payroll(year_month, group)
    scope = []
    unassigned_ids = set()
    for employee in population:
        assignment = current_assignment_on(employee, month_end)
        entity = assignment.payroll_entity_id if assignment else None
        if entity is None:
            unassigned_ids.add(employee.id)
        if not payroll_entity_id or entity == payroll_entity_id:
            scope.append(employee)
    rows = calculate_payroll(year_month, employees=scope)
    blockers = [row for row in rows if not is_payroll_ready(row)]
    counts = {
        code: sum(1 for row in rows if row["group"] == code)
        for code in PAYROLL_GROUP_CODES
    }
    ready_rows = [row for row in rows if is_payroll_ready(row)]
    selected_status = request.args.get("status") or ("pending" if blockers else "ready")
    if selected_status not in {"ready", "pending", "all", "unassigned"}:
        selected_status = "ready"
    employee_q = request.args.get("q", "").strip()
    selected_employee_id = request.args.get("employee_id", type=int)

    if selected_status == "unassigned":
        visible_rows = [row for row in rows if row["employee"].id in unassigned_ids]
    elif selected_status == "ready":
        visible_rows = list(ready_rows)
    elif selected_status == "pending":
        visible_rows = list(blockers)
    else:
        visible_rows = list(rows)
    if employee_q:
        needles = chinese_search_variants(employee_q)
        visible_rows = [
            row
            for row in visible_rows
            if any(
                needle.casefold()
                in " ".join(
                    chinese_search_variants(
                        " ".join(
                            filter(
                                None,
                                [
                                    row["employee"].employee_no,
                                    row["employee"].chinese_name,
                                    row["employee"].english_name,
                                ],
                            )
                        )
                    )
                ).casefold()
                for needle in needles
            )
        ]
    if selected_employee_id:
        visible_rows = [
            row for row in visible_rows
            if row["employee"].id == selected_employee_id
        ]
    pay_context = dict(from_payroll="1", pay_month=year_month, pay_group=group,
                       pay_entity=payroll_entity_id or "", pay_status=selected_status,
                       pay_q=employee_q, pay_employee=selected_employee_id or "")
    for row in visible_rows:
        if not is_payroll_ready(row):
            row["tasks"], row["sources"] = review_sources(row, pay_context)
    summary = {"ready_count": len(ready_rows), "blocked_count": len(blockers),
               "currencies": currency_summary(ready_rows)}
    return render_template(
        "payroll/index.html",
        unassigned_count=len(unassigned_ids),
        saved_runs=PayrollRun.query.filter_by(year_month=year_month).order_by(PayrollRun.id.desc()).all(),
        export_review=export_message(rows),
        exchange_settings=exchange_settings(),
        year_month=year_month,
        selected_group=group,
        selected_payroll_entity_id=payroll_entity_id,
        payroll_entities=reference_options("payroll_entity"),
        payroll_groups=PAYROLL_GROUPS,
        rows=rows,
        visible_rows=visible_rows,
        selected_status=selected_status,
        employee_q=employee_q,
        blockers=blockers,
        ready_rows=ready_rows,
        is_payroll_ready=is_payroll_ready,

        project_summary=project_summary(ready_rows),
        counts=counts,
        summary=summary,
        formula_notes=FORMULA_NOTES,
        rule_version=RULE_VERSION,
        projects=WorkProject.query.filter_by(active=True).order_by(
            WorkProject.name
        ).all(),
        corrections_by_employee=pay_month_corrections(year_month),
    )


def pay_month_corrections(year_month):
    records = {}
    for correction in AttendanceCorrection.query.filter_by(pay_month=year_month).order_by(AttendanceCorrection.source_month):
        records.setdefault(correction.employee_id, []).append(correction)
    return records


def employee_hkid(employee):
    return next(
        (
            item.identity_number
            for item in employee.identities
            if item.status == "active" and item.identity_type == "hkid"
        ),
        None,
    )


def masked_identity_number(value):
    text = str(value or "").strip()
    if not text:
        return ""
    compact = "".join(char for char in text if char.isalnum())
    return f"{compact[:4]}{'*' * max(4, len(compact) - 4)}"


def mpf_export_issues(row):
    issues = list(row["blockers"]) + [policy_text(key) for key in export_issues(row)]
    enrollment = row.get("mpf_enrollment")
    if row["blockers"]:
        return issues
    if enrollment and enrollment.is_exempt and not enrollment.scheme:
        return issues
    if not enrollment or not enrollment.scheme:
        issues.append("未設定 MPF 計劃")
    if not row["employee"].english_name:
        issues.append("未填寫身份證英文姓名")
    if not employee_hkid(row["employee"]):
        issues.append("未填寫香港身份證")
    return list(dict.fromkeys(issues))


def mpf_preview_rows(year_month):
    rows = calculate_payroll(year_month, "all")
    for final in calculate_final_payments(year_month, "all"):
        line = {
            "project": final["project"],
            "working_days": final["working_days"],
            "holiday_days": final["holiday_days"],
            "current_ot_hours": final["ot_hours"],
            "previous_ot_hours": Decimal("0"),
            "previous_holiday_days": Decimal("0"),
            "current_large_ecall_count": final["large_ecall_count"],
            "current_ecall_count": final["ecall_count"],
            "previous_large_ecall_count": Decimal("0"),
            "previous_ecall_count": Decimal("0"),
            "base_amount": final["base_amount"],
            "holiday_amount": final["holiday_amount"],
            "ot_amount": final["ot_amount"],
            "previous_ot_amount": Decimal("0"),
            "previous_holiday_amount": Decimal("0"),
            "large_ecall_amount": Decimal("0"),
            "ecall_amount": final["ecall_amount"],
            "previous_large_ecall_amount": Decimal("0"),
            "previous_ecall_amount": Decimal("0"),
            "allowance_amount": final["allowance_amount"],
            "traffic_meal_allowance_amount": final[
                "traffic_meal_allowance_amount"
            ],
            "special_allowance_amount": final["special_allowance_amount"],
            "sick_leave_amount": Decimal("0"),
            "work_injury_amount": Decimal("0"),
            "annual_leave_amount": final["annual_leave_pay"],
            "adjustment_amount": final["other_payment"],
            "attendance_other_allowance_amount": final[
                "attendance_other_allowance_amount"
            ],
            "gross_amount": final["wage_income"],
            "base_rate": final["base_rate"],
            "holiday_rate": final["holiday_rate"],
            "ot_rate": final["ot_rate"],
            "ot_divisor": Decimal("9"),
            "forecast_working_days": Decimal("0"),
            "forecast_holiday_days": Decimal("0"),
            "forecast_base_amount": Decimal("0"),
            "forecast_holiday_amount": Decimal("0"),
        }
        rows.append(
            {
                "employee": final["employee"],
                "group": final["group"],
                "currency": final["salary"].currency if final["salary"] else "HKD",
                "salary_basis": final["salary"].salary_basis if final["salary"] else None,
                "monthly_pay_method": final["salary"].monthly_pay_method if final["salary"] else "full_month",
                "workweek_days": str(assignment_workweek_days(final["assignment"])),
                "statutory_holiday_paid_days": Decimal("0"),
                "salary_amount": decimal_value(final["salary"].amount) if final["salary"] else Decimal("0"),
                "assignment": final["assignment"],
                "bank_account": None,
                "attendance": final["attendance"]["summary"],
                "base_amount": final["base_amount"],
                "holiday_amount": final["holiday_amount"],
                "ot_amount": final["ot_amount"],
                "large_ecall_amount": Decimal("0"),
                "ecall_amount": final["ecall_amount"],
                "allowance_amount": final["allowance_amount"],
                "traffic_meal_allowance_amount": final[
                    "traffic_meal_allowance_amount"
                ],
                "special_allowance_amount": final[
                    "special_allowance_amount"
                ],
                "sick_leave_amount": Decimal("0"),
                "work_injury_amount": Decimal("0"),
                "work_injury_medical_reimbursement_amount": final[
                    "work_injury_medical_reimbursement_amount"
                ],
                "unpaid_leave_deduction": Decimal("0"),
                "annual_leave_days": final["legacy_leave_days"] + final["post_2024_leave_days"],
                "sick_leave_days": Decimal("0"),
                "unpaid_leave_days": Decimal("0"),
                "work_injury_days": Decimal("0"),
                "adjustment_amount": final["other_payment"],
                "attendance_other_allowance_amount": final[
                    "attendance_other_allowance_amount"
                ],
                "overpay_amount": final["overpay_amount"],
                "underpay_amount": final["underpay_amount"],
                "gross_amount": final["wage_income"],
                "employee_mpf": final["employee_mpf"],
                "employer_mpf": final["employer_mpf"],
                "mpf_enrollment": final["mpf_enrollment"],
                "mpf_calculation_mode": final["mpf_calculation_mode"],
                "payment_in_lieu": final["payment_in_lieu"],
                "severance_long_service": final["benefit"]["net"],
                "net_amount": final["net_amount"],
                "forecast_tail_total": Decimal("0"),
                "current_actual_total": final["wage_income"],
                "current_pay_total": final["wage_income"],
                "actual_previous_tail": Decimal("0"),
                "expected_previous_tail": Decimal("0"),
                "reconciliation_amount": Decimal("0"),
                "current_actual_days": final["working_days"],
                "current_forecast_days": Decimal("0"),
                "previous_actual_days": Decimal("0"),
                "previous_forecast_days": Decimal("0"),
                "warnings": final["warnings"],
                "blockers": final["blockers"],
                "lines": [line],
                "is_final_payment": True,
            }
        )
    for row in rows:
        row["mpf_issues"] = mpf_export_issues(row)
    return rows


@payroll_bp.route("/mpf-contributions")
@login_required
def mpf_contributions():
    year_month = selected_month()
    rows = mpf_preview_rows(year_month)
    schemes = MpfScheme.query.filter_by(active=True).order_by(MpfScheme.name).all()
    summaries = []
    for scheme in schemes:
        scheme_rows = [
            row
            for row in rows
            if row.get("mpf_enrollment")
            and row["mpf_enrollment"].scheme_id == scheme.id
        ]
        ready = [row for row in scheme_rows if not row["mpf_issues"]]
        summaries.append(
            {
                "scheme": scheme,
                "employees": len(scheme_rows),
                "ready": len(ready),
                "relevant_income": sum(
                    (row["gross_amount"] for row in ready), Decimal("0")
                ),
                "employee_mpf": sum(
                    (row["employee_mpf"] for row in ready), Decimal("0")
                ),
                "employer_mpf": sum(
                    (row["employer_mpf"] for row in ready), Decimal("0")
                ),
            }
        )
    return render_template(
        "payroll/mpf.html",
        export_review=export_message(rows),
        year_month=year_month,
        rows=rows,
        schemes=schemes,
        summaries=summaries,
        missing_rows=[row for row in rows if row["mpf_issues"]],
    )


@payroll_bp.route("/final-payment")
@login_required
def final_payment():
    year_month = selected_month()
    group = selected_group()
    payroll_entity_id = selected_payroll_entity()
    rows = calculate_final_payments(year_month, group, payroll_entity_id)
    blockers = [row for row in rows if row["blockers"]]
    counts = {
        code: sum(1 for row in rows if row["group"] == code)
        for code in PAYROLL_GROUP_CODES
    }
    ready_rows = [row for row in rows if is_payroll_ready(row)]
    currency_totals = {}
    for row in ready_rows:
        currency = row["salary"].currency if row.get("salary") else "HKD"
        item = currency_totals.setdefault(currency, {"gross": Decimal("0"), "benefit": Decimal("0"), "net": Decimal("0")})
        item["gross"] += row["wage_income"]
        item["benefit"] += row["benefit"]["net"]
        item["net"] += row["net_amount"]
    summary = {"ready_count": len(ready_rows), "blocked_count": len(blockers),
               "currencies": [{"currency": key, **currency_totals[key]} for key in sorted(currency_totals)]}
    return render_template(
        "payroll/final_payment.html",
        projects=WorkProject.query.filter_by(active=True).order_by(WorkProject.name).all(),
        corrections_by_employee=pay_month_corrections(year_month),
        export_review=export_message(rows),
        year_month=year_month,
        selected_group=group,
        selected_payroll_entity_id=payroll_entity_id,
        payroll_entities=reference_options("payroll_entity"),
        payroll_groups=PAYROLL_GROUPS,
        rows=rows,
        blockers=blockers,
        counts=counts,
        summary=summary,
        formula_notes=FINAL_PAYMENT_FORMULA_NOTES,
        rule_version=FINAL_PAYMENT_RULE_VERSION,
        labour_sources=LABOUR_DEPARTMENT_RULE_SOURCES,
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
    payroll_entity_id = selected_payroll_entity()
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
    rate_issue = None
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
        case.leave_wage_total = nonnegative_form_decimal(
            "leave_wage_total"
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
        case.rate_allocations = json.loads(request.form.get("rate_allocations") or "[]")
        rate_issue = allocation_issue(period.employee, SimpleNamespace(working_days=case.actual_working_days, ot_hours=case.actual_ot_hours, sunday_holiday_days=case.actual_holiday_days, large_ecall_count=case.large_ecall_count, rate_allocations=case.rate_allocations), max(period.start_date, period.end_date.replace(day=1)), period.end_date)
        if rate_issue:
            raise ValueError(rate_issue)
    except (ValueError, TypeError):
        db.session.rollback()
        flash(rate_issue or "請檢查離職 Payroll 日數、次數及金額，不可填寫負數。", "error")
        return redirect(
            url_for(
                "payroll.final_payment",
                year_month=year_month,
                payroll_group=group,
                payroll_entity_id=payroll_entity_id or "",
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
    flash("離職 Payroll 資料已保存，頁面金額已重新計算。", "success")
    return redirect(
        url_for(
            "payroll.final_payment",
            year_month=year_month,
            payroll_group=group,
            payroll_entity_id=payroll_entity_id or "",
        )
    )


def create_current_payroll_run(
    year_month,
    group,
    *,
    employee_ids=None,
    ready_only=False,
    payroll_entity_id=None,
):
    rows = calculate_payroll(year_month, group, payroll_entity_id)
    all_rows_by_employee_id = {
        row["employee"].id: row
        for row in rows
    }
    if employee_ids is not None:
        requested_ids = set(employee_ids)
        if not requested_ids or requested_ids - set(all_rows_by_employee_id):
            missing_ids = requested_ids - set(all_rows_by_employee_id)
            missing_people = Employee.query.filter(Employee.id.in_(missing_ids)).all()
            missing_names = "、".join(
                f"{employee.employee_no} · {employee.display_name}"
                for employee in missing_people
            )
            flash(
                "所選員工不在目前月份、Payroll 組別或發薪單位內，請重新選擇。"
                + (f"（{missing_names}）" if missing_names else ""),
                "error",
            )
            return None
        rows = [
            row
            for row in rows
            if row["employee"].id in requested_ids
        ]
    if employee_ids is None and ready_only:
        rows = [row for row in rows if is_payroll_ready(row)]
    review = export_message(rows)
    if review:
        flash(policy_text("review.export_blocked") + " " + review, "error")
        return None

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
        flash("目前範圍沒有可出糧員工。", "error")
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
        detail=(
            f"{year_month} / {group} / {len(run.employee_results)} 人"
            f" / {'selected' if employee_ids is not None else 'ready' if ready_only else 'all'}"
        ),
    )
    db.session.commit()
    return run


@payroll_bp.route("/payroll/preview", methods=["POST"])
@login_required
def preview_payroll():
    year_month = selected_month()
    group = selected_group()
    payroll_entity_id = selected_payroll_entity()
    if payroll_entity_id is None:
        inferred_entities = {
            row["assignment"].payroll_entity_id
            for row in calculate_payroll(year_month, group)
            if row.get("assignment") and row["assignment"].payroll_entity_id
        }
        if len(inferred_entities) == 1:
            payroll_entity_id = next(iter(inferred_entities))
        else:
            flash("保存 Payroll 前請先選擇發薪單位。", "error")
    if payroll_entity_id is not None and create_current_payroll_run(
        year_month,
        group,
        payroll_entity_id=payroll_entity_id,
    ):
        flash("Payroll 計算已保存。", "success")
    return redirect(
        url_for(
            "payroll.attendance_payroll",
            year_month=year_month,
            payroll_group=group,
            payroll_entity_id=payroll_entity_id or "",
        )
    )


@payroll_bp.route("/payroll/export-current", methods=["GET", "POST"])
@login_required
def export_current_payroll():
    year_month = selected_month()
    group = selected_group()
    payroll_entity_id = selected_payroll_entity()
    if request.method == "GET":
        return redirect(url_for("payroll.attendance_payroll", year_month=year_month,
                                payroll_group=group, payroll_entity_id=payroll_entity_id or ""))
    if payroll_entity_id is None:
        inferred_entities = {
            row["assignment"].payroll_entity_id
            for row in calculate_payroll(year_month, group)
            if row.get("assignment")
            and row["assignment"].payroll_entity_id
        }
        if len(inferred_entities) == 1:
            payroll_entity_id = next(iter(inferred_entities))
        else:
            flash("正式導出前請先選擇發薪單位。", "error")
            return redirect(
                url_for(
                    "payroll.attendance_payroll",
                    year_month=year_month,
                    payroll_group=group,
                    payroll_entity_id="",
                )
            )
    scope = request.form.get("scope", "ready")
    employee_ids = None
    ready_only = False
    if scope == "selected":
        raw_ids = request.form.getlist("employee_ids")
        if not raw_ids or any(not value.isdigit() for value in raw_ids):
            flash("請先勾選需要導出的員工。", "error")
            return redirect(
                url_for(
                    "payroll.attendance_payroll",
                    year_month=year_month,
                    payroll_group=group,
                    payroll_entity_id=payroll_entity_id,
                )
            )
        employee_ids = {int(value) for value in raw_ids}
    elif scope == "ready":
        ready_only = True
    else:
        abort(400)
    run = create_current_payroll_run(
        year_month,
        group,
        employee_ids=employee_ids,
        ready_only=ready_only,
        payroll_entity_id=payroll_entity_id,
    )
    if not run:
        return redirect(
            url_for(
                "payroll.attendance_payroll",
                year_month=year_month,
                payroll_group=group,
                payroll_entity_id=payroll_entity_id,
            )
        )
    return redirect(url_for("payroll.export_payroll", run_id=run.id), code=303)


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
    enrollment = current_mpf_on(employee, month_end)
    mode = enrollment.contribution_mode if enrollment else employee.mpf_mode
    if mode == "exempt":
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

    if (result.mpf_calculation_mode or result.employee.mpf_mode) == "casual":
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
    # Payroll month is a month identifier, not an accounting date. Writing a
    # string also prevents Excel from displaying an artificial first day.
    sheet["F4"] = year_month
    sheet["F4"].number_format = "@"
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
    lines = calculation.get("lines") or [
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
    # Old snapshots may retain attendance counts on a zero-pay allocation
    # line. Such rows must not become standalone MPF rows: only lines that
    # actually carry a payroll amount are exported.
    monetary_fields = (
        "base_amount",
        "holiday_amount",
        "ot_amount",
        "previous_ot_amount",
        "previous_holiday_amount",
        "large_ecall_amount",
        "ecall_amount",
        "previous_large_ecall_amount",
        "previous_ecall_amount",
        "allowance_amount",
        "traffic_meal_allowance_amount",
        "special_allowance_amount",
        "sick_leave_amount",
        "work_injury_amount",
        "adjustment_amount",
        "attendance_other_allowance_amount",
        "gross_amount",
    )
    active = [
        line
        for line in lines
        if line.get("attendance_corrections") or any(decimal_value(line.get(key)) != 0 for key in monetary_fields)
    ]
    if active:
        lines = active
    return sorted(
        lines,
        key=lambda line: (
            decimal_value(line.get("base_amount")),
            decimal_value(line.get("gross_amount")),
        ),
        reverse=True,
    )


def saved_employee_facts(result):
    facts = (result.calculation_json or {}).get("employee_snapshot")
    if facts is None:
        # Legacy runs never captured these facts; keep the compatibility fallback explicit.
        facts = snapshot_employee(result.employee, result.employee.current_assignment, result.run.year_month)
    facts = dict(facts)
    if facts.get("employment_start"):
        facts["employment_start"] = date.fromisoformat(facts["employment_start"])
    return facts


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
    facts = saved_employee_facts(result)
    project = project_for_line(line)
    calculation = result.calculation_json or {}
    allocated = bool(calculation.get('monthly_project_allocation'))
    absence_days = (decimal_value(line.get('allocated_absence_days')) if allocated else
                    (decimal_value(result.sick_leave_days) + decimal_value(result.work_injury_days) if first else Decimal('0')))
    absence_amount = (decimal_value(line.get('sick_leave_amount')) + decimal_value(line.get('work_injury_amount')) if allocated else
                      (decimal_value(result.sick_leave_amount) + decimal_value(result.work_injury_amount) if first else Decimal('0')))
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
            + decimal_value(result.work_injury_medical_reimbursement_amount)
        )
    return {
        1: row_number - 6,
        2: line.get("project_name", project.name if project else "未分配"),
        3: "是" if calculation.get("group") == "management" else "",
        4: "eMPF",
        5: facts["employee_no"],
        6: facts["english_name"],
        7: facts["chinese_name"],
        8: facts["position"],
        9: facts["employment_start"],
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
        28: float(decimal_value(line.get("special_allowance_amount"))),
        29: float(absence_days),
        30: float(effective_rate(absence_amount, absence_days, 0)),
        31: float(absence_amount),
        32: float(overpay),
        33: float(underpay),
        34: float(decimal_value(line.get("adjustment_amount"))),
        35: 1,
        36: float(total),
        37: float(decimal_value(result.employee_mpf)) if first else 0,
        38: float(decimal_value(result.employer_mpf)) if first else 0,
        39: float(decimal_value(line.get("traffic_meal_allowance_amount"))),
        40: float(decimal_value(result.work_injury_medical_reimbursement_amount)) if first else 0,
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
    facts = saved_employee_facts(result)
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
            + decimal_value(result.work_injury_medical_reimbursement_amount)
        )
    return {
        1: row_number - 6,
        2: line.get("project_name", project.name if project else "未分配"),
        3: "",
        4: "eMPF",
        5: facts["employee_no"],
        6: facts["english_name"],
        7: facts["chinese_name"],
        8: facts["position"],
        9: facts["employment_start"],
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
        27: float(decimal_value(line.get("special_allowance_amount"))),
        28: float(
            decimal_value(result.sick_leave_days)
            + decimal_value(result.work_injury_days)
        ) if first else 0,
        29: float(effective_rate(
            decimal_value(result.sick_leave_amount)
            + decimal_value(result.work_injury_amount),
            decimal_value(result.sick_leave_days)
            + decimal_value(result.work_injury_days),
            0,
        )) if first else 0,
        30: float(
            decimal_value(result.sick_leave_amount)
            + decimal_value(result.work_injury_amount)
        ) if first else 0,
        31: float(overpay),
        32: float(underpay),
        33: float(decimal_value(line.get("adjustment_amount"))),
        34: 1,
        35: float(total),
        36: float(decimal_value(result.employee_mpf)) if first else 0,
        37: float(decimal_value(result.employer_mpf)) if first else 0,
        38: float(decimal_value(line.get("traffic_meal_allowance_amount"))),
        39: float(decimal_value(result.work_injury_medical_reimbursement_amount)) if first else 0,
        40: float(decimal_value(result.payment_in_lieu)) if first else 0,
        41: (
            float(decimal_value(result.severance_long_service))
            if first
            else 0
        ),
        42: float(net),
    }


def monthly_formulas(result, line, first, row_number, last_row, values):
    # Keep the effective sick/injury rate from monthly_values, not the ordinary daily rate.
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
        31: f"=ROUND(AC{row_number}*AD{row_number},2)",
        36: (
            f"=ROUND(M{row_number}+P{row_number}+S{row_number}"
            f"+T{row_number}+W{row_number}+Z{row_number}+AA{row_number}"
            f"+AB{row_number}+AE{row_number}"
            f"-AF{row_number}+AG{row_number}+AH{row_number}"
            f"+AM{row_number},2)"
        ),
        43: (
            f"=ROUND(AJ{row_number}-AK{row_number}"
            f"+AN{row_number}+AO{row_number}+AP{row_number},2)"
        ),
    }

    month_start = parse_year_month(result.run.year_month)[0]
    month_days = Decimal(calendar.monthrange(month_start.year, month_start.month)[1])
    standard_rate = decimal_value(values[10]) / month_days
    allocated = bool((result.calculation_json or {}).get('monthly_project_allocation'))
    base_matches = (rounded(line.get('base_amount')) == rounded(standard_rate * working_days)
                    if allocated else formula_matches(line.get("base_amount"), standard_rate, working_days))
    if base_matches:
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
    # Keep the effective sick/injury rate from daily_values, including mixed pay factors.
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
        30: f"=ROUND(AB{row_number}*AC{row_number},2)",
        35: (
            f"=ROUND(L{row_number}+O{row_number}+R{row_number}"
            f"+S{row_number}+V{row_number}+Y{row_number}+Z{row_number}"
            f"+AA{row_number}+AD{row_number}"
            f"-AE{row_number}+AF{row_number}+AG{row_number}"
            f"+AL{row_number},2)"
        ),
        42: (
            f"=ROUND(AI{row_number}-AJ{row_number}"
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


def add_correction_comment(cell, entries, other_payment):
    if not entries:
        return
    notes = []
    for entry in entries:
        quantity = ("+" if entry["direction"] == "add" else "-") + entry["quantity"]
        unit = "OT 小時" if entry["kind"] == "ot" else "出勤日"
        note = f"{entry['date']} {quantity} {unit}：{entry['amount']}"
        if entry["included"]:
            note += "（已計入上月尾段）"
        notes.append(note)
    remainder = decimal_value(other_payment) - sum(Decimal(e["amount"]) for e in entries)
    if remainder:
        notes.append(f"其他款項：{remainder:.2f}")
    cell.comment = Comment("\n".join(notes), "HKR HR")
    cell.comment.width = 320
    cell.comment.height = max(90, 20 * len(notes))


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
        other_col = 33 if group == "site_daily" else 34
        add_correction_comment(sheet.cell(index, other_col), line.get("attendance_corrections"), values[other_col])
        formulas = (
            daily_formulas(result, line, first, index, last_row, values)
            if group == "site_daily"
            else monthly_formulas(result, line, first, index, last_row, values)
        )
        for column, formula in formulas.items():
            sheet.cell(index, column).value = formula
        last_column = 43 if group == "site_daily" else 44
        warnings = "；".join(TRANSLATIONS["zh-Hant"].get(item, item) for item in (result.warnings_json or []))
        if decimal_value(line.get("ot_divisor")) == Decimal("10"):
            warnings = "；".join(
                item for item in [warnings, "HA 日工 OT 除數 10"] if item
            )
        warnings = "；".join(
            item for item in [warnings, ecall_note(line)] if item
        )
        attendance_remarks = (
            (result.calculation_json or {}).get("attendance_remarks")
            if first
            else None
        )
        warnings = "；".join(
            item
            for item in (
                warnings,
                (
                    f"考勤備註：{attendance_remarks}"
                    if attendance_remarks
                    else None
                ),
            )
            if item
        )
        if not (result.calculation_json or {}).get("employee_snapshot"):
            warnings = "；".join(filter(None, [warnings, "舊批次未保存員工身份快照；身份及職位使用現時資料，金額仍為原批次。 / Legacy batch: current identity; original amounts."]))
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
    merged_ranges = {str(item) for item in sheet.merged_cells.ranges}
    for title_range in ("A1:Z1", "A2:Z2", "A3:Z3"):
        if title_range not in merged_ranges:
            sheet.merge_cells(title_range)
    sheet["A1"] = "Hong Kong River Engineering Co. Ltd."
    sheet["A2"] = "Final Payment"
    sheet["A3"] = "Payroll of Local Staff"
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
            result["benefit"]["net"]
            + result["special_compensation"]
            + result["work_injury_medical_reimbursement_amount"]
        )
        leave_payment = (
            result["annual_leave_pay"]
            + result["statutory_holiday_pay"]
            - result["annual_leave_overuse_deduction"]
        )
        base_rate = (
            result["base_amount"] / result["working_days"]
            if result["working_days"] > 0
            else result["base_rate"]
        )
        ot_rate = (
            result["ot_amount"] / result["ot_hours"]
            if result["ot_hours"] > 0
            else result["ot_rate"]
        )
        holiday_rate = (
            result["holiday_amount"] / result["holiday_days"]
            if result["holiday_days"] > 0
            else result["holiday_rate"]
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
            9: float(base_rate),
            11: float(result["ot_hours"]),
            12: float(ot_rate),
            14: float(result["holiday_days"]),
            15: float(holiday_rate),
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
                        (
                            "固定補貼 "
                            f"{result['fixed_allowance_amount']:,.2f}；"
                            "手動補貼 "
                            f"{result['manual_allowance_amount']:,.2f}"
                            if result["fixed_allowance_amount"]
                            or result["manual_allowance_amount"]
                            else None
                        ),
                        (
                            "工傷醫療實銷 "
                            f"{result['work_injury_medical_reimbursement_amount']:,.2f}"
                            if result[
                                "work_injury_medical_reimbursement_amount"
                            ]
                            else None
                        ),
                        (
                            f"超用年假追扣 {result['annual_leave_overused_days']} 日"
                            if result["annual_leave_overused_days"] > 0
                            else None
                        ),
                    ),
                )
            ),
        }
        for column, value in values.items():
            sheet.cell(row_number, column).value = value
        add_correction_comment(sheet.cell(row_number, 18), result.get("attendance_corrections"), combined_adjustment)
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
        for column in (9, 12, 15):
            sheet.cell(row_number, column).number_format = "#,##0.0000"
        for column in (6, 7):
            sheet.cell(row_number, column).number_format = "yyyy-mm-dd"
    sheet.freeze_panes = "A8"
    add_final_payment_rules_sheet(workbook)
    return workbook


def add_final_payment_rules_sheet(workbook):
    if "計算說明" in workbook.sheetnames:
        del workbook["計算說明"]
    sheet = workbook.create_sheet("計算說明")
    sheet.sheet_view.showGridLines = False
    sheet.column_dimensions["A"].width = 7
    sheet.column_dimensions["B"].width = 44
    sheet.column_dimensions["C"].width = 76
    sheet.merge_cells("A1:C1")
    sheet["A1"] = "Final Payment 計算說明（勞工處規則摘要）"
    sheet["A1"].font = Font(size=16, bold=True, color="FFFFFF")
    sheet["A1"].fill = PatternFill("solid", fgColor="166E65")
    sheet["A1"].alignment = Alignment(vertical="center")
    sheet.row_dimensions[1].height = 28

    sheet.merge_cells("A2:C2")
    sheet["A2"] = (
        "遣散費／長期服務金部分根據香港特別行政區政府勞工處公開資料整理；"
        "其他離職工資、年假及公司政策仍須由 HR 按實際個案核對。"
    )
    sheet["A2"].alignment = Alignment(wrap_text=True, vertical="top")
    sheet.row_dimensions[2].height = 36

    sheet.merge_cells("A4:C4")
    sheet["A4"] = "官方來源"
    sheet["A4"].font = Font(bold=True, color="FFFFFF")
    for cell in sheet[4][:3]:
        cell.fill = PatternFill("solid", fgColor="3C7F78")
    source_rows = [
        (
            "《僱傭條例》遣散費及長期服務金問答",
            "https://www.labour.gov.hk/tc/faq/cap57l_whole.htm",
        ),
        (
            "2025年5月1日前入職僱員的取消強積金對沖安排",
            "https://www.op.labour.gov.hk/tc/before-1-may.html",
        ),
        (
            "勞工處法定僱傭權益參考計算機",
            "https://www.lr.labour.gov.hk/web/tc/calculator/index.html",
        ),
    ]
    for row_number, (label, url) in enumerate(source_rows, start=5):
        sheet.cell(row_number, 2).value = label
        sheet.cell(row_number, 3).value = url
        sheet.cell(row_number, 3).hyperlink = url
        sheet.cell(row_number, 3).style = "Hyperlink"
        sheet.cell(row_number, 2).alignment = Alignment(wrap_text=True)
        sheet.row_dimensions[row_number].height = 28

    header_row = 9
    sheet.cell(header_row, 1).value = "編號"
    sheet.cell(header_row, 2).value = "規則摘要"
    sheet.merge_cells(start_row=header_row, start_column=2, end_row=header_row, end_column=3)
    for cell in sheet[header_row][:3]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="3C7F78")
    for row_number, rule in enumerate(
        FINAL_PAYMENT_EXPORT_RULES_ZH_HANT,
        start=header_row + 1,
    ):
        sheet.merge_cells(
            start_row=row_number,
            start_column=2,
            end_row=row_number,
            end_column=3,
        )
        sheet.cell(row_number, 1).value = row_number - header_row
        sheet.cell(row_number, 2).value = rule
        sheet.cell(row_number, 1).alignment = Alignment(
            horizontal="center",
            vertical="top",
        )
        sheet.cell(row_number, 2).alignment = Alignment(
            wrap_text=True,
            vertical="top",
        )
        sheet.row_dimensions[row_number].height = 42
    sheet.freeze_panes = "A10"


def workbook_bytes(workbook):
    memory = io.BytesIO()
    workbook.save(memory)
    memory.seek(0)
    return memory


def mpf_template_path():
    path = (
        Path(current_app.config["PAYROLL_TEMPLATE_ROOT"])
        / "MPF_Contribution_Template.xlsx"
    )
    if not path.is_file():
        abort(500, "MPF contribution template is missing")
    return path


def employment_start_for_month(employee, year_month):
    month_start, month_end = parse_year_month(year_month)
    periods = [
        period
        for period in employee.employment_periods
        if period.start_date <= month_end
        and (period.end_date is None or period.end_date >= month_start)
    ]
    return max(periods, key=lambda item: item.start_date).start_date if periods else None


def build_mpf_workbook(run, scheme):
    workbook = load_workbook(mpf_template_path())
    sheet = workbook["BILL_Submitted Employee(s)"]
    sheet["B2"] = "HONG KONG RIVER ENGINEERING COMPANY LIMITED"
    sheet["H2"] = scheme.employer_account_no
    sheet["J2"] = scheme.payroll_group_no or ""
    results = sorted(
        (
            result
            for result in run.employee_results
            if result.mpf_scheme_code == scheme.code
        ),
        key=lambda item: (
            (item.mpf_member_name or "").casefold(),
            item.employee.employee_no,
        ),
    )
    if results:
        sheet["H2"] = results[0].mpf_employer_account_no
        sheet["J2"] = results[0].mpf_payroll_group_no or ""
    month_start, month_end = parse_year_month(run.year_month)
    for row_number, result in enumerate(results, start=8):
        facts = saved_employee_facts(result)
        values = (
            result.mpf_member_name or "",
            masked_identity_number(facts["hkid"]),
            result.mpf_member_account_no or "",
            facts["employment_start"],
            "APPROVED",
            month_start,
            month_end,
            float(result.mpf_relevant_income),
            None,
            float(result.employee_mpf + result.employer_mpf),
            float(result.employer_mpf),
            float(result.employee_mpf),
        )
        for column, value in enumerate(values, start=1):
            sheet.cell(row_number, column, value)
        for column in (4, 6, 7):
            sheet.cell(row_number, column).number_format = "dd/mm/yyyy"
        for column in (8, 9, 10, 11, 12):
            sheet.cell(row_number, column).number_format = "#,##0.00"
    if workbook.calculation is None:
        workbook.calculation = CalcProperties()
    workbook.calculation.calcMode = "auto"
    return workbook


@payroll_bp.route("/mpf-contributions/export", methods=["POST"])
@login_required
def export_mpf_contributions():
    year_month = selected_month()
    scheme_code = request.form.get("scheme_code") or "all"
    schemes = MpfScheme.query.filter_by(active=True).order_by(MpfScheme.name).all()
    if scheme_code != "all":
        schemes = [scheme for scheme in schemes if scheme.code == scheme_code]
        if not schemes:
            abort(400)
    rows = mpf_preview_rows(year_month)
    payroll_ready = [row for row in rows if not row["blockers"]]
    selected_rows = [
        row
        for row in payroll_ready
        if row.get("mpf_enrollment")
        and row["mpf_enrollment"].scheme
        and any(
            row["mpf_enrollment"].scheme_id == scheme.id
            for scheme in schemes
        )
    ]
    review = export_message(selected_rows)
    if review:
        flash(policy_text("review.export_blocked") + " " + review, "error")
        return redirect(url_for("payroll.mpf_contributions", year_month=year_month))
    metadata_issues = [row for row in selected_rows if row["mpf_issues"]]
    if metadata_issues:
        names = "、".join(
            f"{row['employee'].employee_no}（{' / '.join(row['mpf_issues'])}）"
            for row in metadata_issues[:8]
        )
        flash(f"暫時不能導出 MPF：{names}", "error")
        return redirect(url_for("payroll.mpf_contributions", year_month=year_month))
    if scheme_code == "all":
        unassigned = [
            row
            for row in payroll_ready
            if not row.get("mpf_enrollment")
            or (not row["mpf_enrollment"].scheme
                and not row["mpf_enrollment"].is_exempt)
        ]
        if unassigned:
            names = "、".join(row["employee"].employee_no for row in unassigned[:8])
            flash(f"仍有可出糧員工未設定 MPF 計劃：{names}", "error")
            return redirect(url_for("payroll.mpf_contributions", year_month=year_month))
    if not selected_rows:
        flash("所選範圍沒有可導出的 MPF 員工。", "error")
        return redirect(url_for("payroll.mpf_contributions", year_month=year_month))
    run = snapshot_payroll(year_month, "all", selected_rows, current_user.id)
    write_audit(
        "mpf_contributions_exported",
        "PayrollRun",
        run.id,
        detail=f"{year_month} / {scheme_code} / {len(selected_rows)} 人",
    )
    db.session.commit()
    populated = [
        scheme
        for scheme in schemes
        if any(result.mpf_scheme_code == scheme.code for result in run.employee_results)
    ]
    if len(populated) == 1:
        scheme = populated[0]
        return send_file(
            workbook_bytes(build_mpf_workbook(run, scheme)),
            as_attachment=True,
            download_name=f"HKR_MPF_{year_month}_{scheme.code}.xlsx",
            mimetype=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
        )
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
        for scheme in populated:
            content = workbook_bytes(build_mpf_workbook(run, scheme)).getvalue()
            bundle.writestr(f"HKR_MPF_{year_month}_{scheme.code}.xlsx", content)
    archive.seek(0)
    return send_file(
        archive,
        as_attachment=True,
        download_name=f"HKR_MPF_{year_month}_ALL.zip",
        mimetype="application/zip",
    )


@payroll_bp.route("/final-payment/export", methods=["POST"])
@login_required
def export_final_payment():
    year_month = selected_month()
    group = selected_group()
    payroll_entity_id = selected_payroll_entity()
    if payroll_entity_id is None:
        flash("請先選擇發薪單位，才可匯出離職 Payroll。", "error")
        return redirect(
            url_for(
                "payroll.final_payment",
                year_month=year_month,
                payroll_group=group,
            )
        )
    rows = calculate_final_payments(
        year_month,
        group,
        payroll_entity_id,
    )
    review = export_message(rows)
    if review:
        flash(policy_text("review.export_blocked") + " " + review, "error")
        return redirect(url_for("payroll.final_payment", year_month=year_month, payroll_group=group, payroll_entity_id=payroll_entity_id))
    blockers = [row for row in rows if row["blockers"]]
    entity_codes = {
        row["assignment"].payroll_entity.code
        for row in rows
        if row.get("assignment") and row["assignment"].payroll_entity
    }
    entity_code = (
        next(iter(entity_codes)) if len(entity_codes) == 1 else "UNKNOWN"
    )
    entity_code = "".join(
        character
        for character in str(entity_code)
        if character.isalnum() or character in {"-", "_"}
    ) or "UNKNOWN"
    if not rows:
        flash("所選月份沒有離職員工。", "error")
        return redirect(
            url_for(
                "payroll.final_payment",
                year_month=year_month,
                payroll_group=group,
                payroll_entity_id=payroll_entity_id,
            )
        )
    if blockers:
        flash("請先完成所有離職員工的 Payroll 資料，才可匯出。", "error")
        return redirect(
            url_for(
                "payroll.final_payment",
                year_month=year_month,
                payroll_group=group,
                payroll_entity_id=payroll_entity_id,
            )
        )
    write_audit(
        "final_payment_exported",
        "EmployeeFinalPaymentCase",
        detail=(
            f"{year_month} / {group} / {entity_code} / {len(rows)} 人"
        ),
    )
    db.session.commit()
    if group != "all":
        return send_file(
            workbook_bytes(build_final_payment_workbook(year_month, group, rows)),
            as_attachment=True,
            download_name=(
                f"HKR_Final_Payment_{year_month}_{entity_code}_{group}.xlsx"
            ),
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
                f"HKR_Final_Payment_{year_month}_{entity_code}_{selected}.xlsx",
                workbook_bytes(workbook).getvalue(),
            )
    archive_memory.seek(0)
    return send_file(
        archive_memory,
        as_attachment=True,
        download_name=(
            f"HKR_Final_Payment_{year_month}_{entity_code}_ALL.zip"
        ),
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
    entity_codes = {
        (result.calculation_json or {}).get("payroll_entity_code")
        for result in run.employee_results
        if (result.calculation_json or {}).get("payroll_entity_code")
    }
    entity_code = (
        next(iter(entity_codes)) if len(entity_codes) == 1 else "MULTI"
    )
    entity_code = "".join(
        character
        for character in str(entity_code)
        if character.isalnum() or character in {"-", "_"}
    ) or "UNKNOWN"
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
    review = saved_export_message(run, groups)
    if review:
        flash(policy_text("review.export_blocked") + " " + review, "error")
        return redirect(url_for("payroll.attendance_payroll", year_month=run.year_month))
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
            download_name=(
                f"HKR_Payroll_{run.year_month}_{entity_code}_{selected}.xlsx"
            ),
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
                f"HKR_Payroll_{run.year_month}_{entity_code}_{selected}.xlsx",
                workbook_bytes(workbook).getvalue(),
            )
    archive_memory.seek(0)
    return send_file(
        archive_memory,
        as_attachment=True,
        download_name=f"HKR_Payroll_{run.year_month}_{entity_code}_ALL.zip",
        mimetype="application/zip",
    )


@payroll_bp.route("/payroll/exchange-rates", methods=["POST"])
@login_required
def save_exchange_rates():
    year_month = selected_month()
    changes = []
    for ref in reference_options("currency"):
        if ref.code == "HKD" or f"rate_{ref.code}" not in request.form:
            continue
        raw = request.form[f"rate_{ref.code}"].strip()
        try:
            rate = str(valid_rate(raw)) if raw else None
        except ValueError:
            flash(policy_text("review.fx_invalid").format(currency=ref.code), "error")
            return redirect(url_for("payroll.attendance_payroll", year_month=year_month))
        changes.append((ref, rate))
    for ref, rate in changes:
        metadata = dict(ref.metadata_json or {})
        old = metadata.get("payroll_hkd_rate")
        if rate is None:
            metadata.pop("payroll_hkd_rate", None)
        else:
            metadata["payroll_hkd_rate"] = rate
        ref.metadata_json = metadata
        if old != rate:
            write_audit("payroll_exchange_rate_updated", "ReferenceValue", ref.id,
                        detail=f"{ref.code}: {old or '-'} -> {rate or '-'} HKD")
    db.session.commit()
    flash(policy_text("review.fx_saved"), "success")
    return redirect(url_for("payroll.attendance_payroll", year_month=year_month))
