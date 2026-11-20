"""Employee 5-tab workspace blueprint assembled from cohesive route sub-modules."""
from hkr_hr.workbench.web.employees.common import employees_bp
from hkr_hr.workbench.web.employees import (
    credentials as _credentials,
    directory as _directory,
    employment as _employment,
    leave_actions as _leave_actions,
    profile as _profile,
)

__all__ = ["employees_bp"]
