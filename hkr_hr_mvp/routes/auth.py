"""Transitional compatibility shim; auth blueprint lives in ``hkr_hr.platform.web.auth``."""
from hkr_hr.platform.web.auth import auth_bp

__all__ = ["auth_bp"]
