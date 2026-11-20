# HKR HR Architecture

Authoritative rules for where code, models, templates, translations, and tests live inside `hkr_hr_mvp`.
HKR HR is an independent modular monolith (see [ADR-0005](adr/0005-tmc-pattern-reuse-without-runtime-coupling.md)): one repository, one Flask/Waitress deployment on `D:\HKR_HR` (`R:\` from the laptop), and one PostgreSQL database (`hkr_hr_db`).

Section numbers are referenced by `tests/test_architecture_rules.py`.

## 1. Purpose and Principles

1. **One owner per business fact.** Every domain rule, table, template, and translation belongs to one module.
2. **Downwards-only dependencies.** A module may only import from strictly lower layers (`L0`–`L5`); modules in the same layer never import each other.
3. **Cross-module calls go through `api.py`.** Other modules import `hkr_hr.<module>.api`, never internal `service/`, `web/`, or underscore helpers (public subpackages under `hkr_hr.platform` are shared infrastructure).
4. **Pure rules stay framework-free.** Files under `hkr_hr/<module>/rules/` contain pure Python business logic (`Decimal`, `date`, dataclasses) with zero imports of `flask`, `flask_login`, `flask_sqlalchemy`, or `sqlalchemy`, so unit tests execute in milliseconds.
5. **Composition root holds zero business rules.** `hkr_hr/app/` only creates the Flask app, registers module manifests (blueprints, templates, translations, context helpers), and wires entrypoints.
6. **Module-local templates and words.** Each module owns its Jinja templates under `web/templates/` and its trilingual copy in `words.py`.
7. **Isolated, fast tests.** Test files never import other test files; shared synthetic harnesses live in `tests/fixtures/`.

## 2. Module Map and Layers

| Layer | Module | Responsibility | Owned Tables |
|---|---|---|---|
| L0 | `platform` | Config, SQLAlchemy `db` & `login_manager`, auth/security/CSRF, audit logging, i18n engine, dates/search/backup, base UI shell & error templates | `users`, `audit_logs` |
| L1 | `references` | Reference lists/values, work projects, work calendar & HK holiday parser, MPF schemes, corporate department ordering | `reference_lists`, `reference_values`, `work_projects`, `work_calendar_holidays`, `mpf_schemes` |
| L1 | `documents` | Employee file storage, SHA-256 verification, PDF preview/range streaming, contract templates & DOCX generation | `employee_documents`, `generated_contracts` |
| L2 | `employees` | Employee master record, employment periods, assignments, identities, visas, certificates, qualifications, bank accounts, salaries, allowances, MPF enrollments, completeness, profile integrity & revision | `employees`, `employee_employment_periods`, `employee_assignments`, `employee_identities`, `employee_visas`, `employee_certificates`, `employee_qualifications`, `employee_bank_accounts`, `employee_salaries`, `employee_allowances`, `employee_mpf_enrollments`, `employee_attendance_policies`, `employee_task_notes` |
| L3 | `leave` | Annual leave balances/allocations/records, comp leave credits/allocations, work injury periods & medical claims, absence integrity | `employee_annual_leave_balances`, `employee_annual_leave_allocations`, `employee_annual_leave_records`, `employee_comp_leave_credits`, `employee_comp_leave_allocations`, `employee_work_injury_periods`, `employee_work_injury_monthly_expenses` |
| L3 | `attendance` | Attendance PDF batches & intake items, monthly summaries, segments, special days, attendance policy/rates, project allocation, dated corrections | `attendance_batches`, `attendance_batch_items`, `attendance_monthly_summaries`, `attendance_segments`, `attendance_special_days`, `attendance_corrections` |
| L4 | `payroll` | Monthly/daily payroll engine, casual/regular MPF calculation, final payment calculation & review, payroll snapshots & adjustments, salary records register & exports | `payroll_runs`, `payroll_employee_results`, `payroll_adjustments`, `employee_final_payment_cases`, `salary_records` |
| L5 | `workbench` | HR workbench dashboard & alerts, staff master/certificate/attachment exports, admin pages (users, audit, historical review, system/backup), operator guide & release log | none (composes lower module APIs) |

Composition root: `hkr_hr/app/` (not a domain layer; wires all modules together). Thin root `app.py` delegates to `hkr_hr.app.create_app` for Waitress and production scripts.

## 3. Inside a Module

```text
hkr_hr/<module>/
  __init__.py      empty
  README.md        module scope, ownership, public api, and business rules
  manifest.py      blueprints, template loader folder, words registration
  api.py           sole public entry point for upper layers
  models.py        SQLAlchemy ORM models owned by this module (if any)
  rules/           pure Python business rules (zero Flask/SQLAlchemy imports)
  service/         DB queries, transactions, file/Excel/DOCX workflows
  web/             Flask Blueprint routes and module-owned Jinja templates/
  words.py         WORDS = {"key": (zh_Hant, zh_Hans, en), ...}
  tests/           module unit/ and integration tests
```

A module creates only the subdirectories it actually needs (`rules/`, `service/`, `web/` may be a single `.py` file or a subpackage).

## 4. Between Modules

1. **Layer rule:** Module A may import Module B only if `LAYERS[B] < LAYERS[A]`.
2. **Doorway rule:** Cross-module imports target `hkr_hr.<B>.api` (or `hkr_hr.platform.<subpackage>` for L0 shared infrastructure).
3. **No upward imports:** Lower layers receive upper-layer facts as parameters or via `hkr_hr.app` composition.
4. **No legacy spillover:** After Phase 3 completion, all application Python code and Jinja templates live under `hkr_hr/` (with thin root `app.py` and operational `scripts/`).

## 5. Templates and Static Assets

- Each module stores its Jinja templates under `hkr_hr/<module>/web/templates/` (preserving logical template paths such as `employees/detail.html`, `payroll/index.html`, `base.html`).
- `hkr_hr/app` mounts a `jinja2.ChoiceLoader` across registered module template directories (with `platform` providing `base.html`, `errors/`, `auth/`, and shared partials).
- Static assets remain under `static/` at the Flask app root.

## 6. Testing and Enforcement

1. `tests/fixtures/` holds shared synthetic harnesses (`HrAppTestCase`, `PayrollTestCase`, `ProfileTestCase`) using in-memory SQLite and precomputed password hashes.
2. No test file may import another `test_*.py` file.
3. `tests/test_architecture_rules.py` runs static AST checks on `hkr_hr/` and `tests/` to verify layer boundaries, `api.py` doorways, pure `rules/` isolation, i18n completeness, and zero cross-test imports.
4. Follow `AGENTS.md`: run the smallest relevant module test suite during normal development; run full discovery when touching shared platform layers or preparing a major refactor/release.
