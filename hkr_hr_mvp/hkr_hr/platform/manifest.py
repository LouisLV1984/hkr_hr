"""Platform module manifest."""
from __future__ import annotations

from pathlib import Path

from hkr_hr.platform.web.auth import auth_bp

BLUEPRINTS = (auth_bp,)
TEMPLATE_DIR = Path(__file__).resolve().parent / "web" / "templates"
