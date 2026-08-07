# Archived Codex Handoff - HKR HR MVP

> Historical status snapshot from 2026-07-13. It is preserved as evidence and is not current authority. Do not infer current deployment, restart, runtime, or data state from this file. Use [`../../../CONTEXT.md`](../../../CONTEXT.md), the [`ADR index`](../adr/README.md), and current verification instead.

Updated: 2026-07-13

## Roots And Boundary

- Development: `C:\Projects\02.HKR_HR\hkr_hr_mvp`
- Laptop production mirror: `R:\`
- Mini PC production: `D:\HKR_HR`
- Production app: `D:\HKR_HR\_system\app`
- Database: independent PostgreSQL `hkr_hr_db`
- Remote URL: `http://hkriver.tail73281d.ts.net:5000/login`
- Never deploy this app to `T:\` or `D:\TMC_FileServer`.
- The user restarts production manually with `D:\HKR_HR\scripts\mini_pc_restart_hkr_hr_app.bat`.

## Product Truth

Read these before changing behavior:

- `docs/HR_REDESIGN_REQUIREMENTS.md`
- `docs/HR_REDESIGN_PLAN.md`
- `docs/HR_MVP_LEAN_SCOPE.md` (latest confirmed simplifications)

Apply Occam's razor. Complete the HR core workflow before adding states, filters, approvals or settings.

## Current Core

- Dashboard with active headcount, estimated payroll, expiry/probation reminders and to-do counts.
- Employee master and employee profile with editable personal, contact, bank, employment and salary data.
- Full audit timeline for ordinary edits and sensitive changes.
- Multiple identities with one primary record and long-term expiry support.
- Employee documents with active/replaced/voided states and preview/download.
- TMC-style three-pane document intake: upload/batches, PDF preview, correction/import.
- OCR is prefill only; OCR failure does not block manual import.
- Staff Record, three treasures, signed contract and signed attendance PDF import.
- Employment/salary history, probation end/confirmation, annual leave, VISA/certificate attachments.
- Termination calculation reference fields and rehire on the same employee number with a new employment period.
- Contract Draft Package generation from Office/Site DOCX templates.
- Three payroll groups and templates:
  - `site_daily`: 地盤工人（日工）
  - `site_monthly`: 地盤工人（月工）
  - `management`: 管理人員及總部人員
- One group exports XLSX; all groups export a ZIP containing three XLSX files.
- TMC046/HA daily worker OT divisor is 10; other daily projects use 9.
- Payroll page keeps calculation and MPF rules visible.
- Export Center provides employee master, certificate/VISA expiry, attendance and management summary XLSX.
- UI language session switching works for Traditional Chinese, Simplified Chinese and English on primary operating pages. Data values are not translated.
- Admin user management and audit navigation are admin-only.

## Acceptance Data

The local database intentionally retains these three acceptance employees:

- `QA-HKR-M01` - 黃文飛 - site monthly
- `QA-HKRD-D01` - 黃振雄 - site daily / TMC046
- `QA-ASMTP-V01` - 余英奇 - management / VISA / multiple identities

Do not delete these three unless the user asks. The idempotent seed is:

```powershell
.\.venv\Scripts\python.exe .\scripts\seed_acceptance_data.py
```

## Validation

Compile all Python modules:

```powershell
$files = @('app.py','config.py','models.py') + (Get-ChildItem routes -Filter *.py | ForEach-Object FullName) + (Get-ChildItem tools -Filter *.py | ForEach-Object FullName) + (Get-ChildItem scripts -Filter *.py | ForEach-Object FullName)
.\.venv\Scripts\python.exe -m py_compile $files
```

Deployment from the laptop:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\deploy_to_hkr_hr.ps1
```

Deployment only copies/mirrors files. It does not prove the mini PC process has restarted. After deployment the user restarts the service manually.

## Latest Deployment Status

- On 2026-07-13 the current app, two contract templates and three clean payroll templates were copied to `R:\`.
- SHA-256 checks matched for the main Python routes, intake template, CSS and all three in-app payroll template copies.
- The mirrored app passed `py_compile` for 20 Python files.
- The production `.env` uses `PAYROLL_TEMPLATE_ROOT=D:\HKR_HR\02.Templates\payroll`.
- The obsolete `Payroll PC AD014 - 202605(2).xlsx` was removed from both production template locations.
- This deployment is **copied but not restarted**. Run `D:\HKR_HR\scripts\mini_pc_restart_hkr_hr_app.bat` once before live acceptance.
- A pre-restart remote check confirmed production still retains `HKR0001` and the three existing `QA-LIVE-*` workers. Deployment does not replace or clear the production database.
- Before restart, new templates may display raw translation keys because the old Python process has not loaded the new translation dictionary; this is an expected temporary mixed-version state.

## Deferred

- E-call.
- Detailed day-by-day attendance OCR.
- Attachment bundle export.
- Complex probation/approval status machines.
- Timeline filters.
- Complete legal automation for every termination/MPF edge case; current amounts are clearly labelled estimates requiring HR verification.
