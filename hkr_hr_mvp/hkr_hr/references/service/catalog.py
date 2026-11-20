"""Reference list seeding and query services."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from hkr_hr.platform.db import db
from hkr_hr.references.models import (
    MpfScheme,
    ReferenceList,
    ReferenceValue,
    WorkCalendarHoliday,
    WorkProject,
)
from hkr_hr.references.rules.sorting import (
    normalize_reference_display,
    reference_sort_key,
    slug_code,
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
    "general_document_type": "一般附件類型",
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
    "general_document_type": [
        ("GENERAL_OTHER", "其他一般文件"),
        ("RECOMMENDATION", "推薦信"),
        ("TRAINING_RECORD", "培訓記錄"),
        ("EMPLOYEE_DECLARATION", "員工聲明"),
        ("CORRESPONDENCE", "往來文件"),
    ],
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
    items = query.order_by(ReferenceValue.display_name.asc()).all()
    return sorted(items, key=lambda item: reference_sort_key(list_code, item))


def reference_map():
    return {code: reference_options(code) for code in REFERENCE_LISTS}


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
