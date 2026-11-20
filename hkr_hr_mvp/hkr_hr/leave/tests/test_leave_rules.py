"""Pure unit tests for leave entitlement rules (zero Flask/DB — runs in milliseconds)."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
import unittest

from hkr_hr.leave.rules.entitlement import (
    annual_leave_days_between,
    annual_leave_expiry,
    annual_rate,
    entitlement,
    statutory_annual_leave_days,
)


class LeavePureRulesTests(unittest.TestCase):
    def test_statutory_and_company_advance_entitlement_rules(self):
        self.assertEqual(statutory_annual_leave_days(date(2024, 1, 1), 2026), Decimal("7"))
        self.assertEqual(statutory_annual_leave_days(date(2020, 1, 1), 2026), Decimal("11"))
        self.assertEqual(
            annual_leave_expiry(SimpleNamespace(year=2026, extended_until=None, expiry_date=None)),
            date(2027, 3, 31),
        )
        self.assertIsNone(
            annual_leave_expiry(SimpleNamespace(year=2023, extended_until=None, expiry_date=None))
        )
        self.assertEqual(annual_rate(date(2026, 1, 1), 7, 2026), Decimal("7"))
        self.assertEqual(annual_rate(date(2026, 1, 1), 7, 2027), Decimal("7"))
        self.assertEqual(annual_rate(date(2026, 1, 1), 7, 2028), Decimal("8"))
        self.assertEqual(entitlement(date(2026, 7, 1), 8, 2026), Decimal("4"))
        self.assertEqual(
            annual_leave_days_between(date(2026, 8, 4), date(2026, 8, 4), "am", "am"),
            Decimal("0.5"),
        )
        self.assertIsNone(
            annual_leave_days_between(date(2026, 8, 4), date(2026, 8, 4), "pm", "am")
        )


if __name__ == "__main__":
    unittest.main()
