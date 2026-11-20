"""Shared synthetic test fixtures for HKR HR.

Test modules import shared helpers from here instead of importing other test files.
"""
from tests.fixtures.app_case import (
    APP_ROOT,
    HrAppTestCase,
    ProfileTestCase,
    PayrollTestCase,
    current_profile_revision,
    pdf_bytes,
)

__all__ = [
    "APP_ROOT",
    "HrAppTestCase",
    "ProfileTestCase",
    "PayrollTestCase",
    "current_profile_revision",
    "pdf_bytes",
]
