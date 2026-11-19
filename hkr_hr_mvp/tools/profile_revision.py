"""Scope-specific optimistic revisions; the route locks the employee before checking."""
import hashlib
import hmac
import json

from flask import current_app
from tools.hr_core import current_month
from tools.attendance_policy import attendance_required


FIELDS = {
    "profile": ("gender", "date_of_birth", "mobile_region_code", "mobile_number",
                "email", "residential_address", "emergency_contact_name",
                "emergency_contact_region_code", "emergency_contact_phone",
                "emergency_contact_relation", "remarks"),
    "education": ("education_level", "major", "graduation_school"),
    "visa_requirement": ("visa_required",),
    "attendance_policy": (),
}


def profile_revision(employee, scope="all"):
    fields = FIELDS.get(scope, sum(FIELDS.values(), ()))
    values = {field: getattr(employee, field) for field in fields}
    if scope in {"all", "attendance_policy"}:
        values["attendance_month"] = current_month()
        values["attendance_required"] = attendance_required(employee, current_month())
    if scope == "all":
        values["bank_name"] = employee.bank_name
        values["bank_account_no"] = employee.bank_account_no
    payload = json.dumps([employee.id, scope, values], default=str, sort_keys=True)
    return hmac.new(current_app.secret_key.encode(), payload.encode(), hashlib.sha256).hexdigest()
