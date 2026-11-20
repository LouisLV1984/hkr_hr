"""Pure date, money, formatting, and domain-neutral value parsing utilities."""
from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import re
import unicodedata


HONG_KONG_TIMEZONE = timezone(timedelta(hours=8), name="HKT")

DOCUMENT_CATEGORIES = {
    "salary_record": "薪酬紀錄憑證",
    "three_treasures": "三寶",
    "staff_record": "Staff Record",
    "bank_proof": "銀行賬戶文件",
    "identity": "身份證明",
    "visa": "VISA / 工作許可",
    "qualification": "學歷 / 技能證書",
    "cv": "CV / 履歷",
    "contract_draft": "雇傭合約草稿",
    "signed_contract": "雇傭合約",
    "change_evidence": "任職 / 薪酬調整憑證",
    "probation_confirmation": "轉正憑證",
    "attendance_pdf": "考勤 PDF",
    "termination_letter": "離職 / 終止通知",
    "name_change_evidence": "改名證明",
    "other": "其他",
}

IDENTITY_TYPE_OPTIONS = [
    ("hkid", "香港 HKID"),
    ("mainland_id", "中國內地身份證"),
    ("macau_id", "澳門身份證"),
    ("passport", "護照"),
    ("other", "其他"),
]

PAYROLL_GROUPS = [
    ("site_daily", "地盤工人（日工）"),
    ("site_monthly", "地盤工人（月工）"),
    ("management", "管理人員及總部人員"),
]

WORKWEEK_DAY_OPTIONS = (
    Decimal("5"),
    Decimal("5.5"),
    Decimal("6"),
)

TERMINATION_REASONS = [
    ("resignation", "辭職"),
    ("company_termination", "公司終止"),
    ("redundancy", "裁員"),
    ("contract_expiry", "合約期滿不續約"),
    ("failed_probation", "未通過試用"),
    ("other", "其他"),
]

REPLACEMENT_REASONS = [
    "資料更新",
    "舊文件錯誤",
    "重新掃描",
    "補簽版本",
    "其他",
]


def hong_kong_datetime(value):
    """Convert a stored UTC datetime to Hong Kong time."""
    if value is None:
        return None
    utc_value = (
        value.replace(tzinfo=timezone.utc)
        if value.tzinfo is None
        else value
    )
    return utc_value.astimezone(HONG_KONG_TIMEZONE)


def default_workweek_days(payroll_group):
    return Decimal("5") if payroll_group == "management" else Decimal("6")


def normalize_workweek_days(value, payroll_group):
    if payroll_group == "site_daily":
        return Decimal("6")
    parsed = parse_decimal(value)
    return (
        parsed
        if parsed in WORKWEEK_DAY_OPTIONS
        else default_workweek_days(payroll_group)
    )


def normalize_identity_number(value):
    text = unicodedata.normalize("NFKC", str(value or "")).upper()
    return re.sub(r"[^A-Z0-9]", "", text)


def parse_date(value):
    if isinstance(value, date):
        return value
    text = str(value or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def parse_decimal(value, default=None):
    if isinstance(value, Decimal):
        return value if value.is_finite() else default
    text = str(value or "").replace(",", "").strip()
    if not text:
        return default
    try:
        parsed = Decimal(text)
        return parsed if parsed.is_finite() else default
    except InvalidOperation:
        return default


def money(value):
    return (parse_decimal(value, Decimal("0")) or Decimal("0")).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )


def valid_salary_amount(value):
    amount = parse_decimal(value)
    return amount is not None and Decimal("0") <= amount <= Decimal("9999999999.99")


def format_money(value):
    if value is None:
        return "-"
    return f"{money(value):,.2f}"


def format_date(value):
    return value.strftime("%Y-%m-%d") if isinstance(value, date) else "-"


def parse_bool(value):
    return str(value or "").strip().lower() in {"1", "true", "yes", "on", "y"}


def current_month():
    return date.today().strftime("%Y-%m")


def previous_month(value=None):
    base = parse_year_month(value or current_month())[0]
    previous = base.replace(day=1) - timedelta(days=1)
    return previous.strftime("%Y-%m")


def parse_year_month(value):
    try:
        start = datetime.strptime(str(value), "%Y-%m").date().replace(day=1)
    except (TypeError, ValueError):
        start = date.today().replace(day=1)
    end = start.replace(day=calendar.monthrange(start.year, start.month)[1])
    return start, end


def attendance_period_bounds(year_month):
    """Return the four Payroll attendance periods for one selected month."""
    month_start, month_end = parse_year_month(year_month)
    previous_start, previous_end = parse_year_month(previous_month(year_month))
    return {
        "current_1_20": (
            month_start,
            min(month_end, month_start.replace(day=20)),
        ),
        "current_21_end_forecast": (
            month_start.replace(day=min(21, month_end.day)),
            month_end,
        ),
        "previous_21_end": (
            previous_start.replace(day=min(21, previous_end.day)),
            previous_end,
        ),
        "previous_21_end_forecast": (
            previous_start.replace(day=min(21, previous_end.day)),
            previous_end,
        ),
    }


def month_days(year_month):
    start, end = parse_year_month(year_month)
    return (end - start).days + 1


def masked_bank_account(value):
    text = re.sub(r"\s+", "", str(value or ""))
    return f"•••• {text[-4:]}" if text else "-"


def annual_leave_days_between(
    start_date,
    end_date,
    start_session="am",
    end_session="pm",
):
    if (
        not start_date
        or not end_date
        or end_date < start_date
        or start_session not in {"am", "pm"}
        or end_session not in {"am", "pm"}
        or (start_date == end_date and start_session == "pm" and end_session == "am")
    ):
        return None
    days = Decimal((end_date - start_date).days + 1)
    if start_session == "pm":
        days -= Decimal("0.5")
    if end_session == "am":
        days -= Decimal("0.5")
    return days

