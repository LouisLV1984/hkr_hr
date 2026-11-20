# HKR HR App Rules

These are executable development, data-safety, and deployment rules. Stable domain vocabulary and current architecture live in [`../CONTEXT.md`](../CONTEXT.md); design rationale lives in the [`docs/adr/` index](docs/adr/README.md); setup and current mechanics live in [`README.md`](README.md).

## System And Data Boundary

- HKR HR is independent from TMC. Never connect it to a TMC database, schema, route, template, deployment root, file root, service, or credential.
- Pattern-level reuse from TMC is allowed only after removing TMC-specific business concepts and runtime dependencies. See [ADR-0005](docs/adr/0005-tmc-pattern-reuse-without-runtime-coupling.md).
- Runtime data uses PostgreSQL database `hkr_hr_db`; never place HR tables in `tmc_platform`.
- `hkr_hr/*/models.py` (aggregated by `hkr_hr/app/models.py`) is schema truth until a migration system supersedes it. See [`docs/architecture.md`](docs/architecture.md) for module boundaries and layering rules.
- Do not add a production SQLite fallback.
- Keep credentials and connection strings in `.env`; never hardcode new production secrets.
- Treat HKID, address, phone, bank, salary, contract, and attachment data as sensitive.

## File Separation

- Application code belongs under `D:\HKR_HR\_system\app`.
- Business files and generated files stay outside the app directory.
- Store attachment and contract paths in PostgreSQL, not file binaries.
- Do not casually edit the production mirror. Change source, validate locally, and deploy from source.

## Change Workflow

1. Inspect the current route, model, template, config, and relevant ADR before changing behavior.
2. Preserve the approved single employee-create flow in [ADR-0002](docs/adr/0002-single-employee-create-flow.md).
3. Run the smallest relevant validation (module tests under `hkr_hr/<module>/tests/` plus `tests/test_architecture_rules.py`). For broad Python changes, compile all application modules:

```powershell
$files = @('app.py') + (Get-ChildItem hkr_hr -Recurse -Filter *.py | Where-Object { $_.FullName -notmatch '\\(__pycache__|tests)\\' } | ForEach-Object FullName) + (Get-ChildItem scripts -Filter *.py | ForEach-Object FullName)
.\.venv\Scripts\python.exe -m py_compile $files
```

4. When deployment is requested, run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\deploy_to_hkr_hr.ps1
```

5. Report copying/deployment separately from process restart and live browser verification. Use the HKR HR restart inbox after its one-time installation documented in [README.md](README.md). If it is unavailable, the mini-PC operator can use `D:\HKR_HR\scripts\mini_pc_restart_hkr_hr_app.bat`.
6. For every release, review [`操作指南.md`](操作指南.md) together with `hkr_hr/workbench/service/releases.py`. Any user-facing change to navigation, forms, fields, permissions, document handling, attendance, Payroll, exports, or operating rules must update the guide in the same change. Keep its applicable version and update date aligned with `CURRENT_VERSION`; internal-only fixes may leave the guide body unchanged after confirming that no operator instruction changed.
7. Do not fold a later material set of business rules or workflow changes into an already published release. Add a new release entry with its actual publication date, preserve the prior release's date and scope, and align the operator guide to the new current version.

## Deployment Safety

- Laptop production mapping: `R:\`; mini PC production root: `D:\HKR_HR`.
- Never deploy to `T:\` or `D:\TMC_FileServer`.
- Production uses Waitress, not the Flask development server.
- Do not pass `--reset` to database initialization unless the user explicitly authorizes destructive table recreation for the named database.
- Before any database initialization, confirm the target database is exactly `hkr_hr_db`.
- If a code deploy cannot be followed by restart or live verification, say so explicitly.

## UI And Audit Rules

- Keep Python identifiers, database names, route names, and filenames in English.
- Use the existing translation system for HR-facing UI text.
- Expose maintained business fields through an HR-facing workflow; do not create orphan database fields.
- V1 document capture is manual and employee-profile-first. Do not reintroduce OCR or document-created employees without a later accepted decision. See [ADR-0007](docs/adr/0007-profile-first-manual-document-capture.md).
- Preserve an audit trail for sensitive edits, document import/replacement, employment and salary changes, attendance confirmation, payroll export, and employee export.

## General Safety

- Do not log raw passwords or unnecessary sensitive employee values.
- For bulk imports, validate a small sample in the UI before processing the full source.
- Do not reset, remove, or overwrite production data or business files without explicit user authorization and target verification.
