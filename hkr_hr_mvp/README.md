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
2. Complete missing initial employment, assignment, salary, bank and MPF records
   together on that profile. One date and one save; existing records retain their correction editors.
3. Use the employee's single document gateway for 三寶, Staff Record, CV,
   signed contracts and general attachments. Bank and other structured
   evidence is uploaded in its owning profile module. Preview the original and
   enter any facts manually. V1 does not use OCR.
4. Generate a uniquely versioned SITE or OFFICE draft using facts on its effective date.
   Draft generation never updates formal employment terms.
5. Choose a default month and queue attendance PDFs into one batch. Retry only failed files.
   For each PDF, select the employee and
   enter current-month days 1–20 plus prior-month days 21–end.
6. Review payroll and export one XLSX group or all three groups as a ZIP; the
   export creates an immutable calculation snapshot automatically.
7. Maintain each employee's effective-dated MPF scheme and Member Account No.,
   then export one monthly MPF XLSX per scheme or all schemes as a ZIP.
8. Maintain annual, sick and unpaid leave in Leave Management. Comp leave is
   generated only from rest-day/statutory-holiday attendance; work injury is a
   separate dated attendance-exemption and payroll record.
9. Maintain meal and transport daily-rate allowances and monthly special allowances
   under Employment & Salary. One-off changes are month-specific adjustments,
   available from both monthly Payroll and departure settlement.

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

## Offline Operation

Production startup does not contact a package index. Prepare dependencies on a connected development PC
with `scripts/build_offline_wheels.ps1` using the same Python version and Windows architecture as production.
Copy the resulting folder to `D:\HKR_HR\_system\wheelhouse`. The setup script installs using
`--no-index --find-links`; unchanged installations only run the existing import check.

Work Calendar can export/import local UTF-8 CSV with columns `date,name,scope,region_code`.
Scopes are `statutory`, `public`, or `both`. Existing names and archived states are preserved.
No holiday dates are invented. Online official import remains an optional connected maintenance action.

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
PC. To deploy changes to the restart tools alone, use the same command with
`-RestartToolsOnly`. The operator can always restart directly on the mini PC:

```text
D:\HKR_HR\scripts\mini_pc_restart_hkr_hr_app.bat
```

For remote restarts, run `D:\HKR_HR\scripts\mini_pc_install_hkr_hr_restart_inbox.bat`
once on the mini PC from the Windows account that operates HKR HR. It registers
`HKR HR Restart Inbox`, which checks every minute while that account is signed
in. The app does not need to be running for the task to pick up a request.

From the laptop, at the app root:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\request_hkr_hr_restart.ps1
# On timeout, check the same ID. Do not queue another restart to check status.
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\request_hkr_hr_restart.ps1 -RequestId <printed-id>
```

The task sees an empty marker file in `R:\_system\restart_inbox`. A `.running`
marker without a result means the restart started and may have been interrupted;
inspect `R:\03.Output\logs\restart_inbox` and check the live login page before
requesting another restart. A successful result includes a local login HTTP check;
confirm the expected version and affected page from the laptop separately.

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

The supplied backup setup supports two encrypted, deduplicated Restic repositories.
Their availability must be verified on each installation; this is not proof that
the schedules or repositories have already been configured. The mini PC
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

### Isolated PostgreSQL regression

Use a disposable local PostgreSQL cluster whose data directory is below this
application's ignored `tmp` directory, with a database named `hkr_hr_db`. Never
use the production cluster. Set `HKR_HR_TEST_DATABASE_URL` to that cluster's
`postgresql://` URL, then run:

```powershell
.\.venv\Scripts\python.exe scripts\test_postgres.py --data-directory <absolute-disposable-data-directory>
```

The runner checks the server's real `data_directory` before running tests and
creates a fresh schema for every fixture app (including migration fixtures).
Only schemas created by that invocation are removed. `--pattern` selects a test
file. User identity fixtures select the admin by username, not unordered rows.

Backup verification reports its scope explicitly: laptop mode lists the dump
and extracts templates; mini-PC mode additionally restores a temporary database.
Neither mode currently proves attachment recovery. The system page marks these
logs as partial verification, including older generic success messages.

### Offline PDF preview

Mozilla PDF.js 6.5.438 is vendored under `static/vendor/pdfjs` with its Apache 2.0 license and source manifest. `static/js/pdf-preview.mjs` uses local worker, fonts, CMaps and WASM. Document and attendance open routes serve a viewer by default and preserve original PDF bytes with `?raw=1`; downloads remain attachments. No CDN, browser PDF plugin, or new Python dependency is required.
