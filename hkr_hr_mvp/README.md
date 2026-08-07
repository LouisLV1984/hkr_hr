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
3. Upload 三寶, Staff Record, bank proof, CV, signed contract and other
   attachments to that employee. Preview the original and enter any facts
   manually. V1 does not use OCR.
4. Generate an editable SITE or OFFICE contract package from current profile
   data.
5. Upload attendance PDFs in a batch. For each PDF, select the employee and
   enter current-month days 1–20 plus prior-month days 21–end.
6. Review payroll, create an immutable calculation snapshot and export one
   XLSX group or all three groups as a ZIP.

## Routes

- `/dashboard`
- `/employees`
- `/employees/new`
- `/employees/<id>`
- `/employees/<id>/documents/new`
- `/attendance`
- `/attendance-payroll`
- `/exports`
- `/references`
- `/admin/users`
- `/admin/import`
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

## Validation

```powershell
$files = @('app.py','config.py','models.py') + (Get-ChildItem routes,tools,scripts -Filter *.py | ForEach-Object FullName)
.\.venv\Scripts\python.exe -m py_compile $files
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```
