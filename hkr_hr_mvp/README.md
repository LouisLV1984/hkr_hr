# HKR HR Staff V1

Independent Flask/PostgreSQL HR console for employee records, employee
attachments, contract generation, attendance PDF capture and payroll export.

## Authority

- Executable rules: [`AGENTS.md`](AGENTS.md)
- Stable architecture and vocabulary: [`../CONTEXT.md`](../CONTEXT.md)
- Accepted decisions: [`docs/adr/README.md`](docs/adr/README.md)
- Historical material: [`docs/archive/README.md`](docs/archive/README.md)

## Runtime Boundary

- Development: `C:\Projects\02.HKR_HR\hkr_hr_mvp`
- Laptop production mapping: `R:\`
- Mini PC root: `D:\HKR_HR`
- Production app: `D:\HKR_HR\_system\app`
- PostgreSQL database: `hkr_hr_db`
- LAN URL: `http://192.168.128.70:5000/login`

HKR HR is independent from TMC. TMC interaction patterns may be studied, but
runtime assets, routes, data and services are never shared.

## V1 Workflow

1. Create one minimal employee profile and permanent employee number.
2. Complete personal details, effective-dated assignment and salary on that
   profile.
3. Use the employee's single document gateway for 三寶, Staff Record, CV,
   signed contracts and general attachments. Bank and other structured
   evidence is uploaded in its owning profile module. Preview the original and
   enter any facts manually. V1 does not use OCR.
4. Generate an editable SITE or OFFICE contract package from current profile
   data.
5. Upload attendance PDFs in a batch. For each PDF, select the employee and
   enter current-month days 1–20 plus prior-month days 21–end.
6. Review payroll and export one XLSX group or all three groups as a ZIP; the
   export creates an immutable calculation snapshot automatically.
7. Maintain each employee's effective-dated MPF scheme and Member Account No.,
   then export one monthly MPF XLSX per scheme or all schemes as a ZIP.
8. Maintain annual, sick and unpaid leave in Leave Management. Comp leave is
   generated only from rest-day/statutory-holiday attendance; work injury is a
   separate dated attendance-exemption and payroll record.
9. Maintain meal, transport and special allowances as effective-dated monthly
   amounts under Employment & Salary. One-off Payroll changes remain
   month-specific adjustments.

## Routes

- `/dashboard`
- `/employees`
- `/employees/new`
- `/employees/<id>`
- `/employees/<id>/documents/new`
- `/annual-leave`
- `/attendance`
- `/attendance-payroll`
- `/mpf-contributions`
- `/exports`
- `/references`
- `/admin/users`
- `/admin/audit`
- `/updates`

There is no raw database console, OCR intake route or second employee-create
path.

## Local Setup

```powershell
cd C:\Projects\02.HKR_HR\hkr_hr_mvp
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts\init_db.py --username admin --password "choose-a-local-password"
.\.venv\Scripts\python.exe app.py
```

An intentional destructive rebuild requires both flags:

```powershell
.\.venv\Scripts\python.exe scripts\init_db.py --username admin --password "choose-a-local-password" --reset --confirm-reset hkr_hr_db
```

The script refuses any database name other than `hkr_hr_db`.

## Deployment

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\deploy_to_hkr_hr.ps1
```

Deployment mirrors code and templates to `R:\`; it does not restart the mini
PC. The operator restart remains:

```text
D:\HKR_HR\scripts\mini_pc_restart_hkr_hr_app.bat
```

Admin passwords are never stored in source control. For first-time database
bootstrap or an explicit admin-password reset, set `HKR_HR_ADMIN_PASSWORD` in
the current mini-PC process environment before running the initialization
script. A normal restart of an already initialized database does not reset the
admin password.

When upgrading the disposable V0.1 test database to the V1 schema, run the
following file once. It requires typing `RESET` before rebuilding only
`hkr_hr_db`, then restarts the HR app:

```text
D:\HKR_HR\scripts\mini_pc_upgrade_hkr_hr_v1_and_restart.bat
```

After that one-time rebuild, use only the normal restart file.

## Backup And Restore

Production uses two encrypted, deduplicated Restic repositories. The mini PC
keeps seven daily short-term snapshots under `D:\HKR_HR\04.Backups`; the
laptop keeps longer incremental history under
`%USERPROFILE%\HKR_HR_Backups`. Unchanged multi-gigabyte attachments are not
copied again in every snapshot.

Run each setup once on the relevant machine:

```powershell
# On the mini PC
powershell -NoProfile -ExecutionPolicy Bypass -File D:\HKR_HR\scripts\setup_hkr_hr_backup.ps1 -Mode MiniPc

# On the laptop, from this workspace
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup_hkr_hr_backup.ps1 -Mode Laptop
```

The scheduled tasks run daily when the machine is available. Verify an actual
restore periodically; mini-PC mode also restores PostgreSQL into a temporary,
isolated database and queries the employee table:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File D:\HKR_HR\scripts\verify_hkr_hr_backup_restore.ps1 -Mode MiniPc
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify_hkr_hr_backup_restore.ps1 -Mode Laptop
```

The generated Restic password files are machine-local secrets and must not be
committed or copied into the application folder.

## Validation

```powershell
$files = @('app.py','config.py','models.py') + (Get-ChildItem routes,tools,scripts -Filter *.py | ForEach-Object FullName)
.\.venv\Scripts\python.exe -m py_compile $files
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Employee-editor browser regression uses an isolated synthetic fixture, not the
configured PostgreSQL runtime. Start it in one terminal, then run the browser
checks in another (Node must resolve `playwright`, and Chrome must be installed):

```powershell
.\.venv\Scripts\python.exe tests\profile_workspace_preview.py
# In another terminal, from the app root:
node tests\profile_workspace_browser.cjs
```

The fixture listens only on `127.0.0.1:8766`. Stop it with Ctrl+C after testing;
temporary records and files are cleaned up. Screenshots under `tmp` stay outside
Git and deployment. Never point this test at a live employee database.
