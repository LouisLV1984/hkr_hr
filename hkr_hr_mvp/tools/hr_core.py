import calendar
import hashlib
import re
import shutil
import unicodedata
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

from flask import current_app
from werkzeug.utils import secure_filename

from tools.security import validate_uploaded_file

from models import (
    AuditLog,
    Employee,
    EmployeeAnnualLeaveAllocation,
    EmployeeAnnualLeaveBalance,
    EmployeeAnnualLeaveRecord,
    EmployeeCompLeaveAllocation,
    EmployeeCompLeaveCredit,
    EmployeeAssignment,
    EmployeeBankAccount,
    EmployeeDocument,
    EmployeeEmploymentPeriod,
    EmployeeMpfEnrollment,
    EmployeeSalary,
    MpfScheme,
    PayrollEmployeeResult,
    PayrollRun,
    ReferenceList,
    ReferenceValue,
    WorkCalendarHoliday,
    WorkProject,
    db,
)


def current_bank_account_on(employee, on_date):
    return next(
        (
            item
            for item in employee.bank_accounts
            if item.status == "active"
            and item.effective_from <= on_date
            and (item.effective_to is None or item.effective_to >= on_date)
        ),
        None,
    )


REFERENCE_LISTS = {
    "employee_type": "員工編號類別",
    "employer": "聘用單位",
    "payroll_entity": "發薪單位",
    "social_insurance_entity": "社保繳納單位",
    "labour_dispatch_entity": "勞務派遣單位",
    "work_region": "工作地區",
    "department": "所屬部門",
    "position": "職務 / 工種",
    "visa_category": "VISA 類別",
    "certificate_type": "證件類型",
    "bank": "銀行",
    "phone_region": "電話區號",
    "currency": "幣種",
    "education_level": "學歷",
}

EMPLOYEE_TYPES = [
    ("HKR", "瑞沃合約（月工）"),
    ("HKRD", "瑞沃合約（日工）"),
    ("TE", "臨時工"),
    ("ASMTP", "輸入內地人才計劃"),
    ("BV", "因公簽證"),
    ("LD", "勞務派遣"),
    ("PRO", "瑞港合約"),
    ("MCR", "澳門瑞沃"),
    ("OTHER", "其他"),
]

DEFAULT_REFERENCE_VALUES = {
    "employer": [
        ("HK_RIVER", "香港瑞沃工程有限公司"),
        ("MACAU_RIVER", "香港瑞沃（澳門）工程有限公司"),
        ("PROSPER", "瑞港建設有限公司"),
        ("HAIFA", "青島海發國有資本投資運營集團有限公司"),
    ],
    "payroll_entity": [
        ("HK_RIVER", "香港瑞沃工程有限公司"),
        ("MACAU_RIVER", "香港瑞沃（澳門）工程有限公司"),
        ("PROSPER", "瑞港建設有限公司"),
    ],
    "social_insurance_entity": [
        ("NONE", "無"),
        ("HAIFA", "青島海發國有資本投資運營集團有限公司"),
    ],
    "labour_dispatch_entity": [("NONE", "無")],
    "work_region": [
        ("HK", "香港"),
        ("MO", "澳門"),
        ("ID", "印尼"),
        ("CN", "中國內地"),
        ("OTHER", "其他"),
    ],
    "department": [
        ("ENGINEERING", "工程管理部"),
        ("COMMERCIAL", "成本合約部"),
        ("HR", "人事行政部"),
        ("FINANCE", "財務部"),
        ("MANAGEMENT", "管理層"),
        ("SITE", "地盤"),
    ],
    "position": [
        ("WORKER", "工人"),
        ("FOREMAN", "管工"),
        ("TECHNICIAN", "技術員"),
        ("CLERK", "文員"),
        ("PROJECT_MANAGER", "項目經理"),
        ("ENGINEER", "工程師"),
        ("SURVEYOR", "測量員"),
        ("WELDER", "焊工"),
        ("OPERATOR", "機手"),
        ("SAILOR", "水手"),
        ("CAPTAIN", "船長"),
        ("MECHANIC", "機修"),
        ("COMMERCIAL", "合約"),
    ],
    "visa_category": [
        ("QUALITY_MIGRANT", "優才"),
        ("BUSINESS", "因公往來"),
        ("IANG", "IANG"),
        ("ASMTP", "輸入內地人才計劃（專才）"),
        ("LABOUR", "輸入內地人才計劃（勞工）"),
        ("OTHER", "其他"),
    ],
    "certificate_type": [
        ("SAFETY_CARD", "平安卡"),
        ("WORKER_REGISTRATION", "建造業工人註冊證"),
        ("DEGREE", "學位證書"),
        ("SKILL", "技能證書"),
        ("OTHER", "其他"),
    ],
    "phone_region": [
        ("HK", "+852 香港"),
        ("CN", "+86 中國內地"),
        ("MO", "+853 澳門"),
        ("TW", "+886 台灣"),
        ("ID", "+62 印尼"),
        ("PH", "+63 菲律賓"),
        ("MY", "+60 馬來西亞"),
    ],
    "currency": [
        ("HKD", "HKD"),
        ("CNY", "CNY"),
        ("MOP", "MOP"),
        ("IDR", "IDR"),
        ("USD", "USD"),
    ],
    "education_level": [
        ("PRIMARY", "小學"),
        ("JUNIOR", "初中"),
        ("SECONDARY", "高中"),
        ("VOCATIONAL", "中專 / 職中"),
        ("ASSOCIATE", "大專"),
        ("BACHELOR", "本科"),
        ("MASTER", "碩士"),
        ("DOCTOR", "博士"),
        ("OTHER", "其他"),
    ],
    "bank": [
        ("BOCHK", "BANK OF CHINA (HONG KONG) LIMITED / 中國銀行（香港）"),
        ("HSBC", "THE HONGKONG AND SHANGHAI BANKING CORPORATION LIMITED / 香港上海滙豐銀行"),
        ("HASE", "HANG SENG BANK LIMITED / 恒生銀行"),
        ("SCB", "STANDARD CHARTERED BANK (HONG KONG) LIMITED / 渣打銀行（香港）"),
        ("BEA", "BANK OF EAST ASIA, LIMITED / 東亞銀行"),
        ("CCBA", "CHINA CONSTRUCTION BANK (ASIA) CORPORATION LIMITED / 中國建設銀行（亞洲）"),
        ("ICBCA", "INDUSTRIAL AND COMMERCIAL BANK OF CHINA (ASIA) LIMITED / 中國工商銀行（亞洲）"),
        ("DBS", "DBS BANK (HONG KONG) LIMITED / 星展銀行（香港）"),
        ("CITI", "CITIBANK (HONG KONG) LIMITED / 花旗銀行（香港）"),
        ("NCB", "NANYANG COMMERCIAL BANK, LIMITED / 南洋商業銀行"),
        ("CMBWL", "CMB WING LUNG BANK LIMITED / 招商永隆銀行"),
        ("DSB", "DAH SING BANK, LIMITED / 大新銀行"),
        ("CHB", "CHONG HING BANK LIMITED / 創興銀行"),
        ("OCBC", "OCBC BANK (HONG KONG) LIMITED / 華僑銀行（香港）"),
        ("FUBON", "FUBON BANK (HONG KONG) LIMITED / 富邦銀行（香港）"),
        ("ZA", "ZA BANK LIMITED / 眾安銀行"),
        ("WELAB", "WELAB BANK LIMITED / 匯立銀行"),
        ("OTHER", "其他"),
    ],
}

DEFAULT_PROJECTS = [
    {
        "code": "UNASSIGNED",
        "name": "未分配",
        "region_code": "HK",
        "daily_ot_divisor": Decimal("9"),
    },
    {
        "code": "PC_AD014",
        "name": "PC AD014",
        "region_code": "HK",
        "daily_ot_divisor": Decimal("9"),
    },
    {
        "code": "TMC046",
        "name": "TMC046 醫管局項目",
        "region_code": "HK",
        "daily_ot_divisor": Decimal("10"),
    },
    {
        "code": "SFK",
        "name": "SFK",
        "region_code": "HK",
        "daily_ot_divisor": Decimal("9"),
    },
]

DEFAULT_MPF_SCHEMES = [
    ("BCT_SERIES_800", "BCT MPF Scheme Series 800", "66774665", None, "regular"),
    ("BCOM_MONTHLY", "交銀（BCOM）月工", "56852169", "MM00-0", "regular"),
    (
        "BCT_MONTHLY",
        "銀聯（BCT）月工",
        "53419540",
        "MONTHLY (CALENDAR MONTH)",
        "regular",
    ),
    ("BCT_DAILY", "銀聯（BCT）日工", "53419540", "CEENEXT", "casual"),
]

DOCUMENT_CATEGORIES = {
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


def normalize_reference_display(value):
    text = unicodedata.normalize("NFKC", str(value or "")).strip()
    return re.sub(r"\s+", " ", text)


def normalize_identity_number(value):
    text = unicodedata.normalize("NFKC", str(value or "")).upper()
    return re.sub(r"[^A-Z0-9]", "", text)


def slug_code(value):
    text = unicodedata.normalize("NFKD", str(value or "")).encode(
        "ascii",
        "ignore",
    ).decode("ascii")
    text = re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_").upper()
    return text[:80] or f"VALUE_{datetime.utcnow():%H%M%S%f}"


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
        return value
    text = str(value or "").replace(",", "").strip()
    if not text:
        return default
    try:
        return Decimal(text)
    except InvalidOperation:
        return default


def money(value):
    return (parse_decimal(value, Decimal("0")) or Decimal("0")).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )


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


def ensure_reference_value(ref_list, code, display_name, remarks=None):
    display_name = normalize_reference_display(display_name)
    normalized = display_name.casefold()
    seed_code = slug_code(code)
    existing = ReferenceValue.query.filter_by(
        list_id=ref_list.id,
        code=seed_code,
    ).first()
    if existing:
        if not existing.active:
            existing.active = True
        return existing
    existing = ReferenceValue.query.filter_by(
        list_id=ref_list.id,
        normalized_name=normalized,
    ).first()
    if existing:
        if not existing.active:
            existing.active = True
        return existing
    item = ReferenceValue(
        reference_list=ref_list,
        code=seed_code,
        display_name=display_name,
        normalized_name=normalized,
        active=True,
        remarks=remarks,
    )
    db.session.add(item)
    db.session.flush()
    return item


def ensure_reference_seed():
    lists = {}
    for code, label in REFERENCE_LISTS.items():
        ref_list = ReferenceList.query.filter_by(code=code).first()
        if not ref_list:
            ref_list = ReferenceList(code=code, label=label, active=True)
            db.session.add(ref_list)
            db.session.flush()
        else:
            ref_list.label = label
            ref_list.active = True
        lists[code] = ref_list

    for code, label in EMPLOYEE_TYPES:
        ensure_reference_value(lists["employee_type"], code, label)

    for list_code, values in DEFAULT_REFERENCE_VALUES.items():
        for code, label in values:
            ensure_reference_value(lists[list_code], code, label)

    regions = {
        item.code: item
        for item in ReferenceValue.query.filter_by(
            list_id=lists["work_region"].id,
        ).all()
    }
    hong_kong = regions.get("HK")
    if hong_kong:
        july_first = WorkCalendarHoliday.query.filter_by(
            region_id=hong_kong.id,
            holiday_date=date(2026, 7, 1),
        ).first()
        if not july_first:
            db.session.add(
                WorkCalendarHoliday(
                    region=hong_kong,
                    holiday_date=date(2026, 7, 1),
                    name="香港特別行政區成立紀念日",
                    applies_to_statutory=True,
                    applies_to_public=True,
                    active=True,
                    remarks="V0.3.4 官方法定假日補正",
                )
            )
        else:
            july_first.applies_to_statutory = True
            july_first.applies_to_public = True
    for seed in DEFAULT_PROJECTS:
        project = WorkProject.query.filter_by(code=seed["code"]).first()
        if not project:
            project = WorkProject(code=seed["code"], name=seed["name"])
            db.session.add(project)
        project.name = seed["name"]
        project.region = regions.get(seed["region_code"])
        project.daily_ot_divisor = seed["daily_ot_divisor"]
        project.active = True

    for code, name, employer_no, group_no, calculation_mode in DEFAULT_MPF_SCHEMES:
        scheme = MpfScheme.query.filter_by(code=code).first()
        if not scheme:
            scheme = MpfScheme(code=code)
            db.session.add(scheme)
        scheme.name = name
        scheme.employer_account_no = employer_no
        scheme.payroll_group_no = group_no
        scheme.calculation_mode = calculation_mode
        scheme.active = True

    db.session.commit()
    return lists


def reference_options(list_code, active_only=True):
    ref_list = ReferenceList.query.filter_by(code=list_code).first()
    if not ref_list:
        return []
    query = ReferenceValue.query.filter_by(list_id=ref_list.id)
    if active_only:
        query = query.filter_by(active=True)
    return query.order_by(ReferenceValue.display_name.asc()).all()


def reference_map():
    return {
        code: reference_options(code)
        for code in REFERENCE_LISTS
    }


def reference_by_code(list_code, code):
    ref_list = ReferenceList.query.filter_by(code=list_code).first()
    if not ref_list:
        return None
    return ReferenceValue.query.filter_by(
        list_id=ref_list.id,
        code=str(code or "").upper(),
    ).first()


def employee_type_by_code(code):
    return reference_by_code("employee_type", code)


def next_employee_no(employee_type):
    prefix = (employee_type.code or "OTHER").upper()
    pattern = re.compile(rf"^{re.escape(prefix)}(\d+)$", re.I)
    maximum = 0
    for number, in db.session.query(Employee.employee_no).filter(
        Employee.employee_no.ilike(f"{prefix}%")
    ):
        match = pattern.match(number or "")
        if match:
            maximum = max(maximum, int(match.group(1)))
    return f"{prefix}{maximum + 1:04d}"


def write_audit(
    action,
    entity_type,
    entity_id=None,
    employee_id=None,
    detail=None,
    before=None,
    after=None,
    user_id=None,
):
    if user_id is None:
        try:
            from flask_login import current_user

            user_id = current_user.id if current_user.is_authenticated else None
        except RuntimeError:
            user_id = None
    db.session.add(
        AuditLog(
            user_id=user_id,
            employee_id=employee_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            before_json=before,
            after_json=after,
            detail=detail,
        )
    )


def employee_audit_snapshot(employee):
    assignment = employee.current_assignment
    salary = employee.current_salary
    identity = employee.primary_identity
    return {
        "employee_no": employee.employee_no,
        "status": employee.status,
        "employee_type": (
            employee.employee_type.display_name if employee.employee_type else ""
        ),
        "payroll_group": employee.payroll_group,
        "chinese_name": employee.chinese_name or "",
        "english_name": employee.english_name or "",
        "gender": employee.gender or "",
        "date_of_birth": str(employee.date_of_birth or ""),
        "mobile": " ".join(
            item
            for item in [employee.mobile_region_code, employee.mobile_number]
            if item
        ),
        "email": employee.email or "",
        "address": employee.residential_address or "",
        "emergency_contact_name": employee.emergency_contact_name or "",
        "emergency_contact_phone": " ".join(
            item
            for item in [
                employee.emergency_contact_region_code,
                employee.emergency_contact_phone,
            ]
            if item
        ),
        "emergency_contact_relation": employee.emergency_contact_relation or "",
        "education_level": employee.education_level or "",
        "major": employee.major or "",
        "graduation_school": employee.graduation_school or "",
        "visa_required": employee.visa_required,
        "remarks": employee.remarks or "",
        "bank_name": employee.bank_name or "",
        "bank_account": employee.bank_account_no or "",
        "primary_identity": identity.identity_number if identity else "",
        "project": assignment.project.name if assignment and assignment.project else "",
        "department": (
            assignment.department.display_name
            if assignment and assignment.department
            else ""
        ),
        "salary_basis": salary.salary_basis if salary else "",
        "salary_currency": salary.currency if salary else "",
        "salary_amount": str(salary.amount if salary else ""),
    }


def safe_employee_folder(employee):
    name = secure_filename(employee.employee_no or f"employee_{employee.id}")
    return name or f"employee_{employee.id}"


def unique_filename(original_filename):
    source = secure_filename(original_filename or "file")
    stem = Path(source).stem[:100] or "file"
    suffix = Path(source).suffix.lower()
    return f"{datetime.utcnow():%Y%m%d_%H%M%S_%f}_{stem}{suffix}"


def store_employee_file(employee, uploaded_file, category):
    validate_uploaded_file(uploaded_file)
    root = Path(current_app.config["HKR_HR_UPLOAD_ROOT"])
    folder = root / safe_employee_folder(employee) / category
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / unique_filename(uploaded_file.filename)
    uploaded_file.save(target)
    return target


def copy_file_to_employee(employee, source_path, original_filename, category):
    root = Path(current_app.config["HKR_HR_UPLOAD_ROOT"])
    folder = root / safe_employee_folder(employee) / category
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / unique_filename(original_filename)
    shutil.copy2(source_path, target)
    return target


def file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def uploaded_file_sha256(uploaded_file):
    stream = uploaded_file.stream
    position = stream.tell()
    stream.seek(0)
    digest = hashlib.sha256()
    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
        digest.update(chunk)
    stream.seek(position)
    return digest.hexdigest()


def find_duplicate_employee_document(
    employee_id,
    category,
    content_sha256,
    effective_month=None,
):
    digest = str(content_sha256 or "").strip().lower()
    if len(digest) != 64:
        return None
    query = EmployeeDocument.query.filter_by(
        employee_id=employee_id,
        category=category,
        status="active",
    )
    if effective_month is not None:
        query = query.filter_by(effective_month=effective_month)
    for document in query.order_by(EmployeeDocument.id.desc()):
        if not document.content_sha256:
            path = Path(document.stored_path)
            if path.is_file():
                document.content_sha256 = file_sha256(path)
        if (document.content_sha256 or "").lower() == digest:
            return document
    return None


def current_assignment_on(employee, on_date):
    rows = [
        row
        for row in employee.assignments
        if row.status == "active"
        if row.effective_from <= on_date
        and (row.effective_to is None or row.effective_to >= on_date)
    ]
    return rows[0] if rows else None


def current_salary_on(employee, on_date):
    rows = [
        row
        for row in employee.salaries
        if row.status == "active"
        if row.effective_from <= on_date
        and (row.effective_to is None or row.effective_to >= on_date)
    ]
    return rows[0] if rows else None


def current_mpf_on(employee, on_date):
    rows = [
        row
        for row in employee.mpf_enrollments
        if row.status == "active"
        if row.effective_from <= on_date
        and (row.effective_to is None or row.effective_to >= on_date)
    ]
    return rows[0] if rows else None


def close_previous_record(records, effective_from):
    for item in records:
        if getattr(item, "status", "active") != "active":
            continue
        if item.effective_from < effective_from and (
            item.effective_to is None or item.effective_to >= effective_from
        ):
            item.effective_to = effective_from - timedelta(days=1)


def rebuild_effective_ranges(records):
    active = sorted(
        (
            item
            for item in records
            if getattr(item, "status", "active") == "active"
        ),
        key=lambda item: (item.effective_from, item.id or 0),
    )
    for index, item in enumerate(active):
        item.effective_to = (
            active[index + 1].effective_from - timedelta(days=1)
            if index + 1 < len(active)
            else None
        )
    return active


def create_mpf_enrollment(
    employee,
    effective_from,
    scheme=None,
    member_account_no=None,
    contribution_mode=None,
    remarks=None,
):
    mode = contribution_mode or (
        scheme.calculation_mode if scheme else "exempt"
    )
    enrollment = EmployeeMpfEnrollment(
        employee=employee,
        scheme=scheme,
        member_account_no=member_account_no or None,
        contribution_mode=mode,
        effective_from=effective_from,
        status="active",
        remarks=remarks,
    )
    db.session.add(enrollment)
    db.session.flush()
    rebuild_effective_ranges(employee.mpf_enrollments)
    current = current_mpf_on(employee, date.today())
    if current:
        employee.mpf_mode = current.contribution_mode
    return enrollment


def create_assignment(
    employee,
    effective_from,
    payroll_group,
    workweek_days=None,
    region_id=None,
    project_id=None,
    department_id=None,
    employer_id=None,
    payroll_entity_id=None,
    social_insurance_entity_id=None,
    labour_dispatch_entity_id=None,
    position_ids=None,
    evidence_document_id=None,
    remarks=None,
):
    assignment = EmployeeAssignment(
        employee=employee,
        effective_from=effective_from,
        payroll_group=payroll_group,
        workweek_days=normalize_workweek_days(workweek_days, payroll_group),
        region_id=region_id,
        project_id=project_id,
        department_id=department_id,
        employer_id=employer_id,
        payroll_entity_id=payroll_entity_id,
        social_insurance_entity_id=social_insurance_entity_id,
        labour_dispatch_entity_id=labour_dispatch_entity_id,
        evidence_document_id=evidence_document_id,
        remarks=remarks,
        status="active",
    )
    db.session.add(assignment)
    db.session.flush()
    rebuild_effective_ranges(employee.assignments)
    from models import EmployeeAssignmentPosition

    for index, position_id in enumerate(position_ids or []):
        db.session.add(
            EmployeeAssignmentPosition(
                assignment=assignment,
                position_id=position_id,
                is_primary=index == 0,
            )
        )
    return assignment


def create_salary(
    employee,
    effective_from,
    salary_basis,
    currency,
    amount,
    monthly_pay_method="full_month",
    evidence_document_id=None,
    remarks=None,
):
    salary = EmployeeSalary(
        employee=employee,
        effective_from=effective_from,
        salary_basis=salary_basis,
        monthly_pay_method=(
            monthly_pay_method if salary_basis == "monthly" else "full_month"
        ),
        currency=currency,
        amount=money(amount),
        evidence_document_id=evidence_document_id,
        remarks=remarks,
        status="active",
    )
    db.session.add(salary)
    db.session.flush()
    rebuild_effective_ranges(employee.salaries)
    return salary


def ensure_current_employment_period(employee, start_date=None):
    period = employee.current_period
    if period and period.end_date is None:
        return period
    period = EmployeeEmploymentPeriod(
        employee=employee,
        start_date=start_date or date.today(),
    )
    db.session.add(period)
    return period


def statutory_annual_leave_days(start_date, year):
    if not start_date:
        return Decimal("0")
    service_years = max(0, year - start_date.year)
    if date(year, 12, 31) < date(
        start_date.year + service_years,
        start_date.month,
        min(start_date.day, 28),
    ):
        service_years -= 1
    if service_years < 1:
        return Decimal("0")
    if service_years <= 2:
        return Decimal("7")
    return Decimal(str(min(14, service_years + 5)))


def annual_leave_expiry(balance):
    if balance.year <= 2023:
        return None
    return (
        balance.extended_until
        or balance.expiry_date
        or date(balance.year + 1, 3, 31)
    )


def ensure_annual_leave_balance(employee, year):
    balance = EmployeeAnnualLeaveBalance.query.filter_by(
        employee_id=employee.id,
        year=year,
    ).first()
    if not balance:
        balance = EmployeeAnnualLeaveBalance(employee=employee, year=year)
        if year >= 2024:
            balance.expiry_date = date(year + 1, 3, 31)
        db.session.add(balance)
        db.session.flush()
    return balance


def annual_leave_allocated_days(balance):
    allocations = [
        item
        for item in balance.allocations
        if item.record and item.record.status == "active"
    ]
    allocated_record_ids = {item.record_id for item in allocations}
    allocated = sum(
        (Decimal(str(item.days)) for item in allocations),
        Decimal("0"),
    )
    legacy_records = EmployeeAnnualLeaveRecord.query.filter_by(
        employee_id=balance.employee_id,
        entitlement_year=balance.year,
        status="active",
    ).all()
    fallback = sum(
        (
            Decimal(str(item.days))
            for item in legacy_records
            if item.id not in allocated_record_ids
        ),
        Decimal("0"),
    )
    return allocated + fallback


def annual_leave_bucket(employee, balance, as_of=None, prorate_current=False):
    as_of = as_of or date.today()
    year = balance.year
    period = employee.current_period
    start_date = period.start_date if period else None
    statutory = statutory_annual_leave_days(start_date, year)
    contract = (
        Decimal(str(period.contract_annual_leave_days))
        if period and period.contract_annual_leave_days is not None
        else Decimal("0")
    )
    calculated = max(statutory, contract)
    override = (
        Decimal(str(balance.entitled_days_override))
        if balance.entitled_days_override is not None
        else None
    )
    entitled = override if override is not None else calculated
    if year <= 2023:
        entitled = override or Decimal("0")
    if prorate_current and year == as_of.year and start_date:
        year_start = date(year, 1, 1)
        employed_from = max(start_date, year_start)
        employed_days = max(0, (as_of - employed_from).days + 1)
        days_in_year = Decimal("366" if calendar.isleap(year) else "365")
        entitled = entitled * Decimal(employed_days) / days_in_year
    carried = Decimal(str(balance.carried_from_previous_days or 0))
    manual = Decimal(str(balance.manual_adjustment_days or 0))
    used = annual_leave_allocated_days(balance)
    expiry = annual_leave_expiry(balance)
    expired = bool(expiry and expiry < as_of)
    total = entitled + carried + manual
    return {
        "balance": balance,
        "year": year,
        "is_legacy": year <= 2023,
        "statutory": statutory,
        "contract": contract,
        "calculated_entitled": calculated,
        "entitled_override": override,
        "entitled": entitled,
        "carried": carried,
        "manual": manual,
        "used": used,
        "total": total,
        "remaining": total - used,
        "expiry_date": expiry,
        "extended_until": balance.extended_until,
        "expired": expired,
    }


def annual_leave_buckets(
    employee,
    as_of=None,
    include_expired=True,
    prorate_current=False,
):
    as_of = as_of or date.today()
    balances = list(
        EmployeeAnnualLeaveBalance.query.filter_by(employee_id=employee.id)
        .order_by(EmployeeAnnualLeaveBalance.year.asc())
        .all()
    )
    if not any(item.year == as_of.year for item in balances):
        balance = EmployeeAnnualLeaveBalance(
            employee_id=employee.id,
            year=as_of.year,
        )
        balance.expiry_date = date(as_of.year + 1, 3, 31)
        balances.append(balance)
    rows = [
        annual_leave_bucket(
            employee,
            balance,
            as_of=as_of,
            prorate_current=prorate_current,
        )
        for balance in balances
    ]
    if not include_expired:
        rows = [item for item in rows if not item["expired"]]
    return rows


def set_annual_leave_allocations(
    record,
    legacy_days,
    regular_days,
    as_of=None,
):
    as_of = as_of or record.leave_date
    legacy_days = Decimal(str(legacy_days or 0))
    regular_days = Decimal(str(regular_days or 0))
    if legacy_days < 0 or regular_days < 0:
        raise ValueError("Annual leave allocation cannot be negative.")

    if legacy_days:
        legacy_balance = ensure_annual_leave_balance(record.employee, 2023)
        legacy = annual_leave_bucket(record.employee, legacy_balance, as_of=as_of)
        if legacy["remaining"] < legacy_days:
            raise ValueError("Insufficient 2023-and-earlier annual leave.")
        db.session.add(
            EmployeeAnnualLeaveAllocation(
                record=record,
                balance=legacy_balance,
                days=legacy_days,
            )
        )

    if regular_days:
        ensure_annual_leave_balance(record.employee, as_of.year)
        buckets = [
            item
            for item in annual_leave_buckets(
                record.employee,
                as_of=as_of,
                include_expired=False,
            )
            if not item["is_legacy"] and item["remaining"] > 0
        ]
        buckets.sort(
            key=lambda item: (
                item["expiry_date"] or date.max,
                item["year"],
            )
        )
        remaining = regular_days
        for bucket in buckets:
            if remaining <= 0:
                break
            allocated = min(remaining, bucket["remaining"])
            if allocated <= 0:
                continue
            db.session.add(
                EmployeeAnnualLeaveAllocation(
                    record=record,
                    balance=bucket["balance"],
                    days=allocated,
                )
            )
            remaining -= allocated
        if remaining > 0:
            current_balance = ensure_annual_leave_balance(
                record.employee,
                as_of.year,
            )
            db.session.add(
                EmployeeAnnualLeaveAllocation(
                    record=record,
                    balance=current_balance,
                    days=remaining,
                )
            )


def comp_leave_credit_remaining(credit, excluding_record_id=None):
    used = sum(
        (
            Decimal(str(allocation.days or 0))
            for allocation in credit.allocations
            if allocation.leave_record
            and allocation.leave_record.status == "active"
            and allocation.leave_record_id != excluding_record_id
        ),
        Decimal("0"),
    )
    return max(Decimal("0"), Decimal(str(credit.days or 0)) - used)


def comp_leave_summary(employee):
    total = Decimal("0")
    used = Decimal("0")
    for credit in employee.comp_leave_credits:
        if credit.status != "active":
            continue
        total += Decimal(str(credit.days or 0))
        used += Decimal(str(credit.days or 0)) - comp_leave_credit_remaining(
            credit
        )
    return {
        "total": total,
        "used": used,
        "remaining": max(Decimal("0"), total - used),
    }


def clear_leave_allocations(record):
    record.allocations.clear()
    record.comp_leave_allocations.clear()
    db.session.flush()


def allocate_annual_leave_with_comp(record, as_of=None):
    """Allocate annual leave: comp leave, legacy 2023, then oldest valid year."""
    as_of = as_of or record.leave_date
    remaining = Decimal(str(record.days or 0))
    credits = sorted(
        (
            credit
            for credit in record.employee.comp_leave_credits
            if credit.status == "active"
            and credit.source_date <= as_of
            and comp_leave_credit_remaining(
                credit, excluding_record_id=record.id
            )
            > 0
        ),
        key=lambda credit: (credit.source_date, credit.id),
    )
    for credit in credits:
        if remaining <= 0:
            break
        allocated = min(
            remaining,
            comp_leave_credit_remaining(
                credit, excluding_record_id=record.id
            ),
        )
        db.session.add(
            EmployeeCompLeaveAllocation(
                leave_record=record,
                credit=credit,
                days=allocated,
            )
        )
        remaining -= allocated

    if remaining <= 0:
        return

    legacy_balance = ensure_annual_leave_balance(record.employee, 2023)
    legacy = annual_leave_bucket(record.employee, legacy_balance, as_of=as_of)
    legacy_days = min(remaining, legacy["remaining"])
    if legacy_days > 0:
        db.session.add(
            EmployeeAnnualLeaveAllocation(
                record=record,
                balance=legacy_balance,
                days=legacy_days,
            )
        )
        remaining -= legacy_days

    if remaining > 0:
        set_annual_leave_allocations(
            record,
            Decimal("0"),
            remaining,
            as_of=as_of,
        )


def annual_leave_summary(employee, year=None):
    year = year or date.today().year
    balance = EmployeeAnnualLeaveBalance.query.filter_by(
        employee_id=employee.id,
        year=year,
    ).first()
    if not balance:
        balance = EmployeeAnnualLeaveBalance(employee_id=employee.id, year=year)
        if year >= 2024:
            balance.expiry_date = date(year + 1, 3, 31)
    period = employee.current_period
    termination_date = (
        period.end_date
        if period and period.end_date and period.end_date.year == year
        else None
    )
    as_of = termination_date or date(year, 12, 31)
    current = annual_leave_bucket(
        employee,
        balance,
        as_of=as_of,
        prorate_current=bool(termination_date),
    )
    current["termination_prorated"] = bool(termination_date)
    current["termination_date"] = termination_date
    legacy_balance = EmployeeAnnualLeaveBalance.query.filter_by(
        employee_id=employee.id,
        year=2023,
    ).first()
    legacy = (
        annual_leave_bucket(employee, legacy_balance, as_of=date.today())
        if legacy_balance
        else None
    )
    current.update(
        {
            "legacy_remaining": (
                legacy["remaining"] if legacy else Decimal("0")
            ),
            "legacy_used": legacy["used"] if legacy else Decimal("0"),
            "carry_deadline": annual_leave_expiry(balance),
        }
    )
    return current


def annual_leave_days_between(
    start_date,
    end_date,
    start_session="am",
    end_session="pm",
):
    if not start_date or not end_date or end_date < start_date:
        return None
    days = Decimal((end_date - start_date).days + 1)
    if start_session == "pm":
        days -= Decimal("0.5")
    if end_session == "am":
        days -= Decimal("0.5")
    return max(Decimal("0.5"), days)


def average_wage_prefill(employee, end_date=None):
    reference_date = end_date or date.today()
    month = previous_month(reference_date.strftime("%Y-%m"))
    results = []
    for _ in range(12):
        row = (
            PayrollEmployeeResult.query.join(PayrollRun)
            .filter(
                PayrollRun.year_month == month,
                PayrollEmployeeResult.employee_id == employee.id,
            )
            .order_by(PayrollRun.created_at.desc())
            .first()
        )
        if row:
            results.append(
                {
                    "month": month,
                    "amount": money(row.gross_amount),
                }
            )
        month = previous_month(month)
    average = (
        money(sum((item["amount"] for item in results), Decimal("0")) / len(results))
        if results
        else Decimal("0")
    )
    total = money(
        sum((item["amount"] for item in results), Decimal("0"))
    )
    return {
        "average": average,
        "total": total,
        "months": [item["month"] for item in reversed(results)],
        "count": len(results),
    }


def termination_estimate(employee, end_date, reason, average_wage=None):
    period = employee.current_period
    if not period or not end_date:
        return {
            "payment_in_lieu": Decimal("0"),
            "severance": Decimal("0"),
            "long_service": Decimal("0"),
            "note": "資料不足，須由 HR 核對。",
        }
    if average_wage in {None, ""}:
        average_wage = average_wage_prefill(employee, end_date)["average"]
    average_wage = money(average_wage or 0)
    service_days = max(0, (end_date - period.start_date).days + 1)
    service_years = Decimal(service_days) / Decimal("365")
    capped_year_amount = min(average_wage * Decimal("0.6666666667"), Decimal("15000"))
    payment_in_lieu = Decimal("0")
    if reason in {"company_termination", "redundancy", "failed_probation"}:
        notice_value = parse_decimal(
            period.notice_period_value,
            Decimal("0"),
        )
        notice_unit = (period.notice_period_unit or "day").strip().lower()
        if reason != "failed_probation" or service_days > 31:
            if notice_unit in {"month", "months"}:
                payment_in_lieu = average_wage * notice_value
            else:
                notice_days = (
                    notice_value * Decimal("7")
                    if notice_unit in {"week", "weeks"}
                    else notice_value
                )
                average_daily_wage = (
                    average_wage * Decimal("12") / Decimal("365")
                )
                payment_in_lieu = average_daily_wage * notice_days
    severance = (
        capped_year_amount * service_years
        if reason == "redundancy" and service_days >= 365 * 2
        else Decimal("0")
    )
    long_service = (
        capped_year_amount * service_years
        if reason
        in {
            "company_termination",
            "contract_expiry",
            "failed_probation",
        }
        and service_days >= 365 * 5
        else Decimal("0")
    )
    return {
        "payment_in_lieu": money(payment_in_lieu),
        "severance": min(money(severance), Decimal("390000")),
        "long_service": min(money(long_service), Decimal("390000")),
        "note": (
            "只作參考估算；代通知金假設公司沒有安排員工完成通知期。"
            "平均工資、跨越 2025-05-01 的個案及實際合資格情況，"
            "必須由 HR 按合同及勞工處計算機再核對。"
        ),
    }


def employee_files_path(employee):
    return (
        Path(current_app.config["HKR_HR_UPLOAD_ROOT"])
        / safe_employee_folder(employee)
    )


def delete_employee_files(employee=None, folder=None):
    folder = Path(folder) if folder else employee_files_path(employee)
    if folder.exists():
        shutil.rmtree(folder)


def masked_bank_account(value):
    text = re.sub(r"\s+", "", str(value or ""))
    return f"•••• {text[-4:]}" if text else "-"
