"""Transitional compatibility shim; config now lives in ``hkr_hr.platform.config``."""
from hkr_hr.platform.config import BASE_DIR, Config, DATABASE_URL

__all__ = ["BASE_DIR", "Config", "DATABASE_URL"]
