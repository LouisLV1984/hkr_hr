"""Pure unit tests for employees rules (zero Flask/DB — runs in milliseconds)."""
from __future__ import annotations

from datetime import date
from types import SimpleNamespace
import unittest

from hkr_hr.employees.rules.credentials import (
    rebuild_effective_ranges,
    validate_credential_dates,
)


class EmployeesPureRulesTests(unittest.TestCase):
    def test_validate_credential_dates_rules(self):
        validate_credential_dates("2026-01-01", "2027-01-01", long_term=False, require_expiry=True)
        with self.assertRaisesRegex(ValueError, "profile.date_order"):
            validate_credential_dates("2026-05-01", "2026-01-01")
        with self.assertRaisesRegex(ValueError, "profile.expiry_conflict"):
            validate_credential_dates("2026-01-01", "2027-01-01", long_term=True)
        with self.assertRaisesRegex(ValueError, "profile.expiry_required"):
            validate_credential_dates("2026-01-01", "", long_term=False, require_expiry=True)

    def test_rebuild_effective_ranges_closes_previous_segments(self):
        r1 = SimpleNamespace(id=1, status="active", effective_from=date(2026, 1, 1), effective_to=None)
        r2 = SimpleNamespace(id=2, status="active", effective_from=date(2026, 6, 1), effective_to=None)
        r3 = SimpleNamespace(id=3, status="voided", effective_from=date(2026, 3, 1), effective_to=None)
        active = rebuild_effective_ranges([r2, r3, r1])
        self.assertEqual([r.id for r in active], [1, 2])
        self.assertEqual(r1.effective_to, date(2026, 5, 31))
        self.assertIsNone(r2.effective_to)


if __name__ == "__main__":
    unittest.main()
