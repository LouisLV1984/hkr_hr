"""Pure unit tests for references rules (zero Flask/DB — runs in milliseconds)."""
from __future__ import annotations

from types import SimpleNamespace
import unittest

from hkr_hr.references.rules.sorting import (
    normalize_reference_display,
    reference_sort_key,
    reference_sort_order,
    slug_code,
)


class ReferencesPureRulesTests(unittest.TestCase):
    def test_department_corporate_hierarchy_order(self):
        hr = SimpleNamespace(code="HR", display_name="人事行政部", metadata_json=None)
        mgmt = SimpleNamespace(code="MANAGEMENT", display_name="管理層", metadata_json=None)
        eng = SimpleNamespace(code="ENGINEERING", display_name="工程管理部", metadata_json=None)
        custom = SimpleNamespace(code="CUSTOM", display_name="自訂部門", metadata_json={"sort_order": 15})
        ordered = sorted([hr, eng, custom, mgmt], key=lambda v: reference_sort_key("department", v))
        self.assertEqual([v.code for v in ordered], ["MANAGEMENT", "CUSTOM", "ENGINEERING", "HR"])
        self.assertEqual(reference_sort_order("department", None), 9999)

    def test_display_normalization_and_slug(self):
        self.assertEqual(normalize_reference_display("  工程   管理部 "), "工程 管理部")
        self.assertEqual(slug_code("PC AD014 (HK)"), "PC_AD014_HK")


if __name__ == "__main__":
    unittest.main()
