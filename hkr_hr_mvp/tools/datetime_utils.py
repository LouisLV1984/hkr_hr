"""Transitional compatibility shim; datetime helpers live in ``hkr_hr.platform.dates``."""
from hkr_hr.platform.dates import HONG_KONG_TIMEZONE, hong_kong_datetime

__all__ = ["HONG_KONG_TIMEZONE", "hong_kong_datetime"]
