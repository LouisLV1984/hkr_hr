"""Transitional compatibility shim; employee loading lives in ``hkr_hr.employees.service.loading``."""
from hkr_hr.employees.service.loading import workbench_options

__all__ = ["workbench_options"]
