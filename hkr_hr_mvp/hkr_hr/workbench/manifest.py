"""Workbench module manifest."""
from __future__ import annotations

from pathlib import Path

from hkr_hr.workbench.web.admin import admin_bp
from hkr_hr.workbench.web.attendance import attendance_bp
from hkr_hr.workbench.web.dashboard import dashboard_bp
from hkr_hr.workbench.web.documents import documents_bp
from hkr_hr.workbench.web.employees import employees_bp
from hkr_hr.workbench.web.exports import exports_bp
from hkr_hr.workbench.web.leave import leave_bp
from hkr_hr.workbench.web.references import references_bp

BLUEPRINTS = (
    dashboard_bp,
    employees_bp,
    documents_bp,
    leave_bp,
    attendance_bp,
    exports_bp,
    references_bp,
    admin_bp,
)
TEMPLATE_DIR = Path(__file__).resolve().parent / "web" / "templates"
