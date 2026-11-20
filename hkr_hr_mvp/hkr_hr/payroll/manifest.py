"""Payroll module manifest."""
from __future__ import annotations

from pathlib import Path

from hkr_hr.payroll.web.attendance_corrections import bp as attendance_corrections_bp
from hkr_hr.payroll.web.routes import payroll_bp
from hkr_hr.payroll.web.salary_records import salary_records_bp

BLUEPRINTS = (payroll_bp, salary_records_bp, attendance_corrections_bp)
TEMPLATE_DIR = Path(__file__).resolve().parent / "web" / "templates"
