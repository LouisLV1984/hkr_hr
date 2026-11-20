"""Static architecture rule enforcement for HKR HR (see docs/architecture.md)."""
from __future__ import annotations

import ast
import importlib
import unittest
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
PKG_ROOT = APP_ROOT / "hkr_hr"

LAYERS: dict[str, int] = {
    "platform": 0,
    "references": 1,
    "documents": 1,
    "employees": 2,
    "leave": 3,
    "attendance": 3,
    "payroll": 4,
    "workbench": 5,
}
COMPOSITION_ROOTS = {"app"}

PURE_RULE_BANNED_ROOTS = {"flask", "flask_login", "flask_sqlalchemy", "sqlalchemy"}

# Flipped to True once Phase 3 retires all legacy root packages.
ENFORCE_NO_LEGACY_ROOTS = False


def _iter_module_py_files(include_tests: bool = False):
    for path in sorted(PKG_ROOT.rglob("*.py")):
        parts = path.relative_to(PKG_ROOT).parts
        if "__pycache__" in parts:
            continue
        if not include_tests and "tests" in parts:
            continue
        yield path


def _iter_all_test_files():
    for root in (APP_ROOT / "tests", PKG_ROOT):
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("test_*.py")):
            if "__pycache__" in path.parts:
                continue
            yield path


def _imported_targets(tree: ast.AST) -> list[tuple[int, str]]:
    targets: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                targets.append((node.lineno, alias.name))
        elif isinstance(node, ast.ImportFrom) and node.module:
            base = node.module
            targets.append((node.lineno, base))
            for alias in node.names:
                if alias.name != "*":
                    targets.append((node.lineno, f"{base}.{alias.name}"))
    return targets


class ArchitectureRulesTests(unittest.TestCase):
    def test_only_declared_modules_exist_under_hkr_hr(self):
        actual = {
            p.name
            for p in PKG_ROOT.iterdir()
            if p.is_dir() and p.name != "__pycache__"
        }
        allowed = set(LAYERS) | COMPOSITION_ROOTS
        self.assertEqual(actual, allowed)

    def test_every_module_has_readme_words_and_tests(self):
        for mod in LAYERS:
            mod_dir = PKG_ROOT / mod
            self.assertTrue((mod_dir / "README.md").is_file(), f"{mod}: missing README.md")
            self.assertTrue((mod_dir / "words.py").is_file(), f"{mod}: missing words.py")
            self.assertTrue((mod_dir / "tests").is_dir(), f"{mod}: missing tests/")

    def test_cross_module_imports_go_downwards_and_through_api(self):
        violations: list[str] = []
        for path in _iter_module_py_files(include_tests=False):
            rel = path.relative_to(PKG_ROOT)
            if len(rel.parts) < 2:
                continue
            source_mod = rel.parts[0]
            if source_mod in COMPOSITION_ROOTS:
                continue
            source_layer = LAYERS[source_mod]
            tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
            for lineno, target in _imported_targets(tree):
                if not target.startswith("hkr_hr."):
                    continue
                parts = target.split(".")
                if len(parts) < 2:
                    continue
                target_mod = parts[1]
                if target_mod == source_mod:
                    continue
                if target_mod in COMPOSITION_ROOTS:
                    violations.append(
                        f"{rel.as_posix()}:{lineno} imports composition root '{target}'"
                    )
                    continue
                if target_mod not in LAYERS:
                    violations.append(
                        f"{rel.as_posix()}:{lineno} imports unknown module '{target}'"
                    )
                    continue
                if LAYERS[target_mod] >= source_layer:
                    violations.append(
                        f"{rel.as_posix()}:{lineno} ({source_mod} L{source_layer}) "
                        f"must not import {target_mod} (L{LAYERS[target_mod]}): '{target}'"
                    )
                if target_mod == "platform":
                    if len(parts) >= 3 and parts[2].startswith("_"):
                        violations.append(
                            f"{rel.as_posix()}:{lineno} imports private platform symbol '{target}'"
                        )
                else:
                    if len(parts) < 3 or parts[2] != "api":
                        violations.append(
                            f"{rel.as_posix()}:{lineno} must import '{target_mod}' via hkr_hr.{target_mod}.api (got '{target}')"
                        )
        self.assertEqual(violations, [], "\n".join(violations))

    def test_pure_rules_never_import_web_or_orm_frameworks(self):
        violations: list[str] = []
        for path in _iter_module_py_files(include_tests=False):
            rel = path.relative_to(PKG_ROOT)
            if "rules" not in rel.parts:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
            for lineno, target in _imported_targets(tree):
                root = target.split(".", 1)[0]
                if root in PURE_RULE_BANNED_ROOTS:
                    violations.append(
                        f"{rel.as_posix()}:{lineno} pure rule imports '{target}'"
                    )
        self.assertEqual(violations, [], "\n".join(violations))

    def test_no_test_file_imports_another_test_file(self):
        violations: list[str] = []
        for path in _iter_all_test_files():
            tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
            for lineno, target in _imported_targets(tree):
                leaf_parts = target.split(".")
                if any(part.startswith("test_") for part in leaf_parts):
                    violations.append(
                        f"{path.relative_to(APP_ROOT).as_posix()}:{lineno} imports test module '{target}'"
                    )
        self.assertEqual(violations, [], "\n".join(violations))

    def test_modular_words_have_no_duplicates_and_complete_locales(self):
        seen: dict[str, str] = {}
        duplicates: list[str] = []
        for mod in sorted(LAYERS):
            words_mod = importlib.import_module(f"hkr_hr.{mod}.words")
            catalogue = words_mod.WORDS
            for key, triple in catalogue.items():
                self.assertEqual(len(triple), 3, f"{mod}.words:{key} must have 3 locales")
                if key in seen:
                    duplicates.append(f"{key} in both {seen[key]} and {mod}")
                seen[key] = mod
        self.assertEqual(duplicates, [], "\n".join(duplicates))

        from hkr_hr.app.words import TRANSLATIONS

        self.assertEqual(set(TRANSLATIONS["zh-Hant"]), set(seen))
        self.assertEqual(set(TRANSLATIONS["zh-Hans"]), set(seen))
        self.assertEqual(set(TRANSLATIONS["en"]), set(seen))

    def test_no_legacy_roots_when_strict(self):
        if not ENFORCE_NO_LEGACY_ROOTS:
            return
        legacy_paths = [
            APP_ROOT / "routes",
            APP_ROOT / "tools",
            APP_ROOT / "templates",
            APP_ROOT / "models.py",
            APP_ROOT / "config.py",
        ]
        existing = [p.relative_to(APP_ROOT).as_posix() for p in legacy_paths if p.exists()]
        self.assertEqual(existing, [], f"Legacy paths still exist: {existing}")


if __name__ == "__main__":
    unittest.main()
