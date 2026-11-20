"""Shared trilingual translation engine for HKR HR.

Each module owns its UI strings in ``hkr_hr/<module>/words.py`` and registers
them through ``hkr_hr.app.words.configure_words()``.
"""
from __future__ import annotations

import re

LANGUAGE_OPTIONS = [
    ("zh-Hant", "繁", "繁體中文"),
    ("zh-Hans", "简", "简体中文"),
    ("en", "EN", "English"),
]

OPTION_TRANSLATION_KEYS = {
    "payroll_group": {
        "all": "common.all",
        "site_daily": "payroll.group_daily",
        "site_monthly": "payroll.group_monthly",
        "management": "payroll.group_management",
        "unassigned": "common.not_set",
    },
    "mpf_mode": {
        "regular": "employee.mpf_regular",
        "casual": "employee.mpf_casual",
        "exempt": "employee.mpf_exempt",
    },
    "reference_list": {
        "employee_type": "reference_list.employee_type",
        "employer": "reference_list.employer",
        "payroll_entity": "reference_list.payroll_entity",
        "social_insurance_entity": "reference_list.social_insurance_entity",
        "labour_dispatch_entity": "reference_list.labour_dispatch_entity",
        "work_region": "reference_list.work_region",
        "department": "reference_list.department",
        "position": "reference_list.position",
        "visa_category": "reference_list.visa_category",
        "certificate_type": "reference_list.certificate_type",
        "bank": "reference_list.bank",
        "phone_region": "reference_list.phone_region",
        "currency": "reference_list.currency",
        "education_level": "reference_list.education_level",
    },
    "document_category": {
        "three_treasures": "document_category.three_treasures",
        "staff_record": "document_category.staff_record",
        "bank_proof": "document_category.bank_proof",
        "identity": "document_category.identity",
        "visa": "document_category.visa",
        "qualification": "document_category.qualification",
        "cv": "document_category.cv",
        "contract_draft": "document_category.contract_draft",
        "signed_contract": "document_category.signed_contract",
        "change_evidence": "document_category.change_evidence",
        "probation_confirmation": "document_category.probation_confirmation",
        "attendance_pdf": "document_category.attendance_pdf",
        "termination_letter": "document_category.termination_letter",
        "name_change_evidence": "document_category.name_change_evidence",
        "other": "document_category.other",
    },
    "identity_type": {
        "hkid": "identity_type.hkid",
        "mainland_id": "identity_type.mainland_id",
        "macau_id": "identity_type.macau_id",
        "passport": "identity_type.passport",
        "other": "identity_type.other",
    },
    "termination_reason": {
        "resignation": "termination_reason.resignation",
        "company_termination": "termination_reason.company_termination",
        "redundancy": "termination_reason.redundancy",
        "contract_expiry": "termination_reason.contract_expiry",
        "failed_probation": "termination_reason.failed_probation",
        "other": "termination_reason.other",
    },
    "replacement_reason": {
        "資料更新": "replacement_reason.data_update",
        "舊文件錯誤": "replacement_reason.old_file_error",
        "重新掃描": "replacement_reason.rescan",
        "補簽版本": "replacement_reason.signed_replacement",
        "其他": "replacement_reason.other",
    },
    "document_status": {
        "active": "documents.active",
        "replaced": "documents.replaced",
        "voided": "documents.voided",
    },
    "role": {
        "admin": "role.admin",
        "hr": "role.hr",
    },
    "audit_entity": {
        "User": "audit.entity.user",
        "Employee": "audit.entity.employee",
        "EmployeeAssignment": "audit.entity.assignment",
        "EmployeeSalary": "audit.entity.salary",
        "EmployeeIdentity": "audit.entity.identity",
        "EmployeeCertificate": "audit.entity.certificate",
        "EmployeeVisa": "audit.entity.visa",
        "EmployeeQualification": "audit.entity.qualification",
        "EmployeeEmploymentPeriod": "audit.entity.employment_period",
        "EmployeeAnnualLeaveRecord": "audit.entity.annual_leave",
        "EmployeeAnnualLeaveBalance": "audit.entity.annual_leave_balance",
        "EmployeeTaskNote": "audit.entity.task_note",
        "EmployeeDocument": "audit.entity.document",
        "GeneratedContract": "audit.entity.contract",
        "AttendanceMonthlySummary": "audit.entity.attendance",
        "PayrollRun": "audit.entity.payroll_run",
        "PayrollAdjustment": "audit.entity.payroll_adjustment",
        "EmployeeFinalPaymentCase": "audit.entity.final_payment",
        "ReferenceValue": "audit.entity.reference_value",
        "WorkProject": "audit.entity.project",
        "MpfScheme": "audit.entity.mpf_scheme",
        "EmployeeMpfEnrollment": "audit.entity.mpf_enrollment",
        "SalaryRecord": "audit.entity.salary_record",
        "WorkCalendarHoliday": "audit.entity.work_calendar",
        "EmployeeAttendancePolicy": "audit.entity.attendance_policy",
        "EmployeeWorkInjuryPeriod": "audit.entity.work_injury",
        "EmployeeWorkInjuryMonthlyExpense": "audit.entity.work_injury_expense",
        "EmployeeBankAccount": "audit.entity.bank_account",
        "EmployeeAllowance": "audit.entity.allowance",
        "AttendanceCorrection": "audit.entity.attendance_correction",
    },
    "workflow_status": {
        "pending": "status.pending",
        "saved": "status.saved",
        "skipped": "status.skipped",
        "open": "status.open",
        "preview": "status.preview",
        "imported": "status.imported",
        "completed": "status.completed",
        "received": "status.received",
        "not_required": "status.not_required",
        "missing": "status.missing",
        "draft": "status.draft",
        "ready": "status.ready",
        "exported": "status.exported",
        "active": "common.active",
        "departed": "common.departed",
    },
}

SYSTEM_MESSAGE_TRANSLATION_KEYS = {
    "不能刪除目前登入的帳戶。": "admin.cannot_delete_current_user",
    "不能刪除系統最後一個啟用中的 Admin 帳戶。": "admin.cannot_delete_last_admin",
    "用戶已刪除。": "admin.user_deleted_success",
    "缺入職日期": "system.missing_start_date",
    "缺任職資料": "system.missing_assignment",
    "缺薪酬資料": "system.missing_salary_data",
    "缺銀行資料": "system.missing_bank_data",
    "銀行資料未完成": "system.bank_setup_incomplete",
    "缺 Staff Record": "system.missing_staff_record",
    "缺已簽署合同": "system.missing_signed_contract",
    "缺三寶": "system.missing_three_treasures",
    "缺 VISA 資料": "system.missing_visa_data",
    "缺銀行證明": "system.missing_bank_proof",
    "有任職調整缺憑證": "system.assignment_evidence_missing",
    "有薪酬調整缺憑證": "system.salary_evidence_missing",
    "缺考勤": "system.missing_attendance",
    "本月無需考勤表，按預設全勤及零 OT／E-CALL 計算": "system.attendance_not_required_default",
    "缺薪酬": "system.missing_salary",
    "雇傭合約未存檔": "system.employment_contract_missing",
    "考勤未收": "system.attendance_not_received",
    "薪酬未設定": "system.salary_not_set",
    "出糧銀行資料未填寫": "system.payroll_bank_missing",
    "MPF：員工標記為豁免": "system.mpf_exempt",
    "缺出生日期，請人工核對 MPF 年齡豁免": "system.mpf_missing_birth",
    "MPF：建造業臨時僱員按日供款門檻計算": "system.mpf_casual",
    "MPF：建造業臨時僱員按每日入息級距計算": "system.mpf_casual",
    "任職資料生效": "system.assignment_effective",
    "薪酬資料生效": "system.salary_effective",
    "user_created": "audit.action.user_created",
    "user_updated": "audit.action.user_updated",
    "user_deleted": "audit.action.user_deleted",
    "auth_login_success": "audit.action.auth_login_success",
    "auth_login_failed": "audit.action.auth_login_failed",
    "auth_logout": "audit.action.auth_logout",
    "employee_created": "audit.action.employee_created",
    "employee_deleted": "audit.action.employee_deleted",
    "personal_data_updated": "audit.action.personal_data_updated",
    "education_background_updated": "audit.action.education_background_updated",
    "visa_requirement_updated": "audit.action.visa_requirement_updated",
    "employee_name_updated": "audit.action.employee_name_updated",
    "assignment_changed": "audit.action.assignment_changed",
    "assignment_evidence_added": "audit.action.assignment_evidence_added",
    "assignment_corrected": "audit.action.assignment_corrected",
    "assignment_withdrawn": "audit.action.assignment_withdrawn",
    "salary_changed": "audit.action.salary_changed",
    "salary_evidence_added": "audit.action.salary_evidence_added",
    "salary_corrected": "audit.action.salary_corrected",
    "salary_withdrawn": "audit.action.salary_withdrawn",
    "identity_added": "audit.action.identity_added",
    "identity_corrected": "audit.action.identity_corrected",
    "identity_voided": "audit.action.identity_voided",
    "certificate_added": "audit.action.certificate_added",
    "certificate_corrected": "audit.action.certificate_corrected",
    "certificate_voided": "audit.action.certificate_voided",
    "visa_added": "audit.action.visa_added",
    "visa_corrected": "audit.action.visa_corrected",
    "visa_voided": "audit.action.visa_voided",
    "qualification_added": "audit.action.qualification_added",
    "qualification_corrected": "audit.action.qualification_corrected",
    "qualification_voided": "audit.action.qualification_voided",
    "probation_updated": "audit.action.probation_updated",
    "annual_leave_added": "audit.action.annual_leave_added",
    "annual_leave_corrected": "audit.action.annual_leave_corrected",
    "annual_leave_voided": "audit.action.annual_leave_voided",
    "annual_leave_balance_updated": "audit.action.annual_leave_balance_updated",
    "employment_terminated": "audit.action.employment_terminated",
    "employment_termination_cancelled": "audit.action.employment_termination_cancelled",
    "employee_rehired": "audit.action.employee_rehired",
    "document_uploaded": "audit.action.document_uploaded",
    "document_replaced": "audit.action.document_replaced",
    "document_review_saved": "audit.action.document_review_saved",
    "document_status_changed": "audit.action.document_status_changed",
    "document_source_updated": "audit.action.document_source_updated",
    "leave_evidence_added": "audit.action.leave_evidence_added",
    "contract_generated": "audit.action.contract_generated",
    "attendance_saved": "audit.action.attendance_saved",
    "attendance_corrected": "audit.action.attendance_corrected",
    "attendance_withdrawn": "audit.action.attendance_withdrawn",
    "attendance_not_required": "audit.action.attendance_not_required",
    "attendance_required": "audit.action.attendance_required",
    "project_transfer": "audit.action.project_transfer",
    "payroll_snapshot_created": "audit.action.payroll_snapshot_created",
    "payroll_adjustment_added": "audit.action.payroll_adjustment_added",
    "payroll_adjustment_corrected": "audit.action.payroll_adjustment_corrected",
    "payroll_adjustment_withdrawn": "audit.action.payroll_adjustment_withdrawn",
    "payroll_adjustment_voided": "audit.action.payroll_adjustment_withdrawn",
    "payroll_exchange_rate_updated": "audit.action.payroll_exchange_rate_updated",
    "payroll_leave_recalculated": "audit.action.payroll_leave_recalculated",
    "final_payment_leave_recalculated": "audit.action.final_payment_leave_recalculated",
    "salary_record_saved": "audit.action.salary_record_saved",
    "salary_record_withdrawn": "audit.action.salary_record_withdrawn",
    "salary_records_exported": "audit.action.salary_records_exported",
    "work_calendar_created": "audit.action.work_calendar_created",
    "work_calendar_updated": "audit.action.work_calendar_updated",
    "work_calendar_deleted": "audit.action.work_calendar_deleted",
    "work_calendar_csv_import": "audit.action.work_calendar_csv_import",
    "attendance_policy_exempted": "audit.action.attendance_policy_exempted",
    "attendance_policy_required": "audit.action.attendance_policy_required",
    "attendance_corrected_for_payroll": "audit.action.attendance_corrected_for_payroll",
    "work_injury_added": "audit.action.work_injury_added",
    "work_injury_corrected": "audit.action.work_injury_corrected",
    "work_injury_withdrawn": "audit.action.work_injury_withdrawn",
    "work_injury_expense_added": "audit.action.work_injury_expense_added",
    "work_injury_expense_corrected": "audit.action.work_injury_expense_corrected",
    "work_injury_expense_withdrawn": "audit.action.work_injury_expense_withdrawn",
    "initial_setup": "audit.action.initial_setup",
    "leave_corrected": "audit.action.leave_corrected",
    "bank_account_added": "audit.action.bank_account_added",
    "bank_account_corrected": "audit.action.bank_account_corrected",
    "bank_account_withdrawn": "audit.action.bank_account_withdrawn",
    "bank_account_evidence_linked": "audit.action.bank_account_evidence_linked",
    "payroll_exported": "audit.action.payroll_exported",
    "final_payment_updated": "audit.action.final_payment_updated",
    "final_payment_exported": "audit.action.final_payment_exported",
    "employee_export": "audit.action.employee_export",
    "attachment_bundle_export": "audit.action.attachment_bundle_export",
    "salary_certificate_exported": "audit.action.salary_certificate_exported",
    "reference_created": "audit.action.reference_created",
    "reference_updated": "audit.action.reference_updated",
    "reference_deleted": "audit.action.reference_deleted",
    "project_created": "audit.action.project_created",
    "project_updated": "audit.action.project_updated",
    "mpf_scheme_created": "audit.action.mpf_scheme_created",
    "mpf_scheme_updated": "audit.action.mpf_scheme_updated",
    "mpf_scheme_deleted": "audit.action.mpf_scheme_deleted",
    "mpf_enrollment_added": "audit.action.mpf_enrollment_added",
    "mpf_enrollment_corrected": "audit.action.mpf_enrollment_corrected",
    "mpf_enrollment_withdrawn": "audit.action.mpf_enrollment_withdrawn",
    "mpf_contributions_exported": "audit.action.mpf_contributions_exported",
    "allowance_added": "audit.action.allowance_added",
    "allowance_corrected": "audit.action.allowance_corrected",
    "allowance_withdrawn": "audit.action.allowance_withdrawn",
    "task_note_added": "audit.action.task_note_added",
    "缺離職日適用薪酬": "system.missing_departure_salary",
    "尚未確認離職月實際考勤及結算資料": "system.final_payment_unconfirmed",
    "缺年假補薪平均工資或日薪率": "system.missing_leave_pay_rate",
    "缺轉制前遣散／長服金工資基數": "system.missing_pre_transition_basis",
    "缺轉制後遣散／長服金工資基數": "system.missing_post_transition_basis",
}

ZH_HANT: dict[str, str] = {}
ZH_HANS: dict[str, str] = {}
EN: dict[str, str] = {}

TRANSLATIONS: dict[str, dict[str, str]] = {
    "zh-Hant": ZH_HANT,
    "zh-Hans": ZH_HANS,
    "en": EN,
}


def register_words(words: dict[str, tuple[str, str, str]]) -> None:
    """Register a module's trilingual word catalogue into TRANSLATIONS."""
    for key, (zh_hant, zh_hans, en) in words.items():
        ZH_HANT[key] = zh_hant
        ZH_HANS[key] = zh_hans
        EN[key] = en


def normalize_language(value):
    return value if value in TRANSLATIONS else "zh-Hant"


def translate_system_message(value, translate):
    if value is None:
        return ""
    text = str(value)
    if any(text in messages for messages in TRANSLATIONS.values()):
        return translate(text)
    if text.startswith("security.login_limited|minutes="):
        return translate(
            "security.login_limited",
            minutes=text.rsplit("=", 1)[-1],
        )
    key = SYSTEM_MESSAGE_TRANSLATION_KEYS.get(text)
    if key:
        return translate(key)

    age_match = re.fullmatch(r"MPF：(\d+) 歲，按年齡不供款", text)
    if age_match:
        return translate("system.mpf_age_exempt", age=age_match.group(1))

    adjustment_match = re.fullmatch(r"調整「(.+)」缺憑證", text)
    if adjustment_match:
        return translate(
            "system.adjustment_missing_evidence",
            label=adjustment_match.group(1),
        )

    policy_match = re.fullmatch(
        r"永久無需考勤表，按預設全勤及零 OT／E-CALL 計算（自 (\d{4}-\d{2}) 起）",
        text,
    )
    if policy_match:
        return translate(
            "system.attendance_long_term_exempt_default",
            month=policy_match.group(1),
        )

    if text.startswith("附件："):
        return translate("system.attachment_event", name=text[3:])
    return text
