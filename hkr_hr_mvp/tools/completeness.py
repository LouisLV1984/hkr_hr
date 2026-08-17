from models import AttendanceMonthlySummary
from tools.attendance_policy import attendance_required
from tools.hr_core import current_mpf_on, parse_year_month


EMPLOYEE_DATA_REQUIREMENTS = (
    ("employment", "employment"),
    ("assignment", "employment"),
    ("salary", "employment"),
    ("bank", "personal"),
    ("staff_record", "documents"),
    ("signed_contract", "documents"),
    ("three_treasures", "credentials"),
    ("visa", "credentials"),
)


def active_document_categories(employee):
    return {
        document.category
        for document in employee.documents
        if document.status == "active"
    }


def employee_data_items(employee):
    categories = active_document_categories(employee)
    active_certificate_codes = {
        item.certificate_type.code
        for item in employee.certificates
        if item.status == "active" and item.certificate_type
    }
    three_treasures_complete = bool(
        any(item.status == "active" for item in employee.identities)
        and "SAFETY_CARD" in active_certificate_codes
        and "WORKER_REGISTRATION" in active_certificate_codes
    )
    checks = {
        "employment": bool(employee.current_period),
        "assignment": bool(employee.current_assignment),
        "salary": bool(employee.current_salary),
        "bank": bool(employee.bank_name and employee.bank_account_no),
        "staff_record": "staff_record" in categories,
        "signed_contract": "signed_contract" in categories,
        "three_treasures": (
            employee.payroll_group not in {"site_daily", "site_monthly"}
            or three_treasures_complete
        ),
        "visa": (
            not employee.visa_required
            or any(item.status == "active" for item in employee.visas)
        ),
    }
    items = [
        {
            "code": code,
            "label_key": (
                f"readiness.{code}_complete"
                if checks[code]
                else f"readiness.{code}_missing"
            ),
            "tab": tab,
            "ok": checks[code],
        }
        for code, tab in EMPLOYEE_DATA_REQUIREMENTS
        if code not in {"three_treasures", "visa"}
        or (
            code == "three_treasures"
            and employee.payroll_group in {"site_daily", "site_monthly"}
        )
        or (code == "visa" and employee.visa_required)
    ]
    if any(
        record.status == "active"
        and record.leave_type == "sick"
        and not record.evidence_document_id
        for record in employee.annual_leave_records
    ):
        items.append(
            {
                "code": "sick_evidence",
                "label_key": "readiness.sick_evidence_missing",
                "tab": "leave",
                "ok": False,
            }
        )
    return items


def mpf_data_item(employee, on_date):
    enrollment = current_mpf_on(employee, on_date)
    complete = bool(
        enrollment
        and enrollment.scheme_id
        and enrollment.member_account_no
    )
    return {
        "code": "mpf",
        "label_key": (
            "readiness.mpf_complete"
            if complete
            else "readiness.mpf_missing"
        ),
        "tab": "employment",
        "ok": complete,
    }


def missing_employee_data_labels(employee):
    return [
        item["label_key"]
        for item in employee_data_items(employee)
        if not item["ok"]
    ]


def attendance_item(employee, year_month, summary=None):
    if summary is None:
        summary = AttendanceMonthlySummary.query.filter_by(
            employee_id=employee.id,
            year_month=year_month,
        ).first()
    if summary and summary.status == "received":
        return {
            "ok": True,
            "code": "received",
            "label_key": "readiness.attendance_received",
        }
    if not attendance_required(employee, year_month, summary=summary):
        return {
            "ok": True,
            "code": "not_required",
            "label_key": "readiness.attendance_not_required",
        }
    return {
        "ok": False,
        "code": "missing",
        "label_key": "readiness.attendance_missing",
    }


def payroll_items(payroll_row):
    blockers = list((payroll_row or {}).get("blockers") or [])
    if not blockers:
        return [
            {
                "ok": True,
                "code": "ready",
                "label_key": "readiness.payroll_ready",
                "label": None,
            }
        ]
    return [
        {
            "ok": False,
            "code": "blocked",
            "label_key": None,
            "label": blocker,
        }
        for blocker in blockers
    ]


def employee_readiness(
    employee,
    year_month,
    payroll_row=None,
    summary=None,
    in_scope=True,
):
    data_items = employee_data_items(employee)
    if in_scope:
        month_end = parse_year_month(year_month)[1]
        data_items.append(mpf_data_item(employee, month_end))
    attendance = (
        attendance_item(employee, year_month, summary=summary)
        if in_scope
        else {
            "ok": True,
            "code": "not_applicable",
            "label_key": "readiness.not_applicable",
        }
    )
    payroll = (
        payroll_items(payroll_row)
        if in_scope
        else [
            {
                "ok": True,
                "code": "not_applicable",
                "label_key": "readiness.not_applicable",
                "label": None,
            }
        ]
    )
    has_issue = (
        any(not item["ok"] for item in data_items)
        or not attendance["ok"]
        or any(not item["ok"] for item in payroll)
    )
    return {
        "employee": employee,
        "employee_data": data_items,
        "attendance": attendance,
        "payroll": payroll,
        "has_issue": has_issue,
    }
