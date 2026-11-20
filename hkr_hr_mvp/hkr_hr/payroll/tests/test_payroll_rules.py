"""Pure unit tests for payroll rules (zero Flask/DB — runs in milliseconds)."""
from __future__ import annotations

from decimal import Decimal
import unittest

from hkr_hr.payroll.rules.export_rules import export_issues, is_payroll_ready


class PayrollPureRulesTests(unittest.TestCase):
    def test_export_readiness_rules(self):
        ready_row = {"blockers": [], "net_amount": Decimal("15000.00")}
        neg_row = {"blockers": [], "net_amount": Decimal("-10.00")}
        blocked_row = {"blockers": ["缺考勤"], "net_amount": Decimal("0")}
        self.assertTrue(is_payroll_ready(ready_row))
        self.assertEqual(export_issues(ready_row), [])
        self.assertFalse(is_payroll_ready(neg_row))
        self.assertTrue(export_issues(neg_row))
        self.assertFalse(is_payroll_ready(blocked_row))


if __name__ == "__main__":
    unittest.main()
