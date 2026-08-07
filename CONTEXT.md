# HKR HR Context

Updated: 2026-08-07

This file records stable vocabulary, current architecture, and operational facts. It does not record task progress or deployment status. Executable rules live in [`AGENTS.md`](AGENTS.md) and [`hkr_hr_mvp/AGENTS.md`](hkr_hr_mvp/AGENTS.md); design rationale lives in the [`ADR index`](hkr_hr_mvp/docs/adr/README.md).

## System Identity

HKR HR is an independent employee-centered HR system. An employee profile is the organizing record for personal data, identities, employment periods, employment/salary history, documents, certificates/VISA, attendance, contracts, exports, and audit events.

HKR HR may adapt useful interaction patterns observed in TMC, but it does not share TMC runtime code, templates, routes, data, credentials, deployment roots, or services.

## Runtime And Storage

| Item | Current value |
|---|---|
| Development workspace | `C:\Projects\02.HKR_HR` |
| Source repository | `https://github.com/LouisLV1984/hkr_hr` |
| Flask app | `C:\Projects\02.HKR_HR\hkr_hr_mvp` |
| Laptop production mapping | `R:\` |
| Mini PC production root | `D:\HKR_HR` |
| Production app | `D:\HKR_HR\_system\app` |
| Uploaded attachments | `D:\HKR_HR\01.Attachments` |
| Contract templates | `D:\HKR_HR\02.Templates\contract_templates` |
| Payroll templates | `D:\HKR_HR\02.Templates\payroll` |
| Generated contracts | `D:\HKR_HR\03.Output\generated_contracts` |
| Runtime database | PostgreSQL `hkr_hr_db` |
| LAN login | `http://192.168.128.70:5000/login` |

`models.py` is current application schema truth. PostgreSQL stores file paths and metadata; document binaries remain on the filesystem.

GitHub source control contains application source and current project documentation only. Employee, attendance, payroll, contract, credential, runtime, generated, backup, and local verification data remain outside version control.

## Employee Vocabulary

- Employee status displayed by the application is derived from effective-dated employment periods. A future last working day remains `active` until that date; after the period ends it becomes `departed`.
- Rehire retains the employee number and creates a new employment period.
- Employee type codes: `HKR`, `HKRD`, `TE`, `ASMTP`, `BV`, `LD`, `PRO`, `MCR`, and `OTHER`.
- Payroll groups:
  - `site_daily`: 地盤工人（日工）
  - `site_monthly`: 地盤工人（月工）
  - `management`: 管理人員及總部人員
- A person may have multiple identity records. One active identity may be primary, and an identity may be long-term.
- Employment/project/position/salary changes use effective-dated records. Active records can be corrected or withdrawn, and missing evidence can be supplied later without deleting historical rows.
- The shared correction vocabulary is: `correct` for wrong fields/dates, `withdraw` or `void` for an invalid whole record, `replace` for a wrong attachment, and `supplement evidence` for a missing attachment. Corrections preserve before/after audit values.

## Approved Employee Creation

The approved workflow has one start:

1. Create a minimal employee using Chinese or English name plus employee type.
2. Open that employee profile.
3. Complete fields manually while previewing 三寶, Staff Record, signed contract, and other documents attached to that employee.

Document capture must not create a parallel employee-onboarding path. [ADR-0002](hkr_hr_mvp/docs/adr/0002-single-employee-create-flow.md) and [ADR-0007](hkr_hr_mvp/docs/adr/0007-profile-first-manual-document-capture.md) are the product decisions.

## Operator Workspaces

Primary navigation is organized by HR outcomes:

1. Work Overview;
2. Employee Management;
3. Annual Leave;
4. Attendance Management;
5. Payroll & Exports;
6. Reference Data.

Attendance handles PDF collection and attendance entry. Payroll calculation and export, employee-record exports, attachment bundles, and salary certificates live under Payroll & Exports. Admin tools are reached through the signed-in Admin account and are not mixed into HR reference-data navigation.

Referenced projects and dropdown values cannot be deleted because deletion would change historical employee, attendance, or Payroll facts. They may be disabled for new records. Only unused setup values may be deleted.

## Employee Documents

Current intake document type codes are:

| Code | Meaning |
|---|---|
| `three_treasures` | 三寶 |
| `staff_record` | Staff Record |
| `signed_contract` | Signed employment contract |
| `attendance_pdf` | Signed monthly attendance PDF |
| `bank_proof` | Bank-account evidence |
| `identity` | Identity evidence |
| `visa` | VISA evidence |
| `qualification` | Degree or skill certificate |
| `change_evidence` | Employment or salary change evidence |
| `cv` | Curriculum vitae |

三寶 covers identity evidence, construction worker registration, and safety training/card evidence. Stable source precedence is:

- Identity and construction/safety certificate facts: 三寶.
- Contact, bank, emergency-contact, education, and background facts: Staff Record.
- Contract/employment/salary facts: signed contract or later confirmed change evidence.
- Existing manually confirmed values are never silently overwritten.

V1 does not use OCR. HR previews the source document and enters or corrects the relevant structured data manually.

Employee document status is `active`, `replaced`, or `voided`. Replacing or voiding requires a reason.
Employee documents store a SHA-256 content digest. Identical-content checks are scoped to the same employee and document category; attendance PDFs are further scoped to the same payroll month. HR must explicitly confirm an identical replacement.
Replacing a document updates linked identity, certificate, VISA, qualification, assignment, salary, attendance, contract and employment-period references to the new active document while retaining the old file as history.

## Attendance And Payroll

- Attendance has one employee/month summary and project detail segments for four periods:
  - current-month days 1-20 actual;
  - current-month days 21 to month end forecast;
  - previous-month days 21 to month end actual;
  - previous-month days 21 to month end original forecast.
- The signed attendance PDF is stored as an employee document.
- Confirmed fields include employee, month, project segments, working days, OT hours, Sunday/holiday days, Large E-CALL count, ordinary E-CALL count, document, confirmer, and confirmation time.
- Large E-CALL adds one applicable daily rate per occurrence. Ordinary E-CALL adds HKD 400 per occurrence.
- Current-month E-CALL is included in current payroll. Previous-month days 21 to month end E-CALL is included in overpay/underpay reconciliation. Current-month tail forecasts assume zero E-CALL until actual attendance is received.
- Payroll stores calculation snapshots with employee totals, project allocation lines, source facts, warnings, and a rule version. Export files are regenerated from templates.
- Payroll is calculated live on page load and filter changes. Export is the only commit action and creates the calculation snapshot automatically.
- Missing attendance, salary, or bank-change confirmation blocks payroll export.
- Other missing evidence/documents are warnings that require acknowledgement.
- One payroll group exports one XLSX; all groups export a ZIP containing three XLSX files.
- Daily-worker OT divisor is 10 for TMC046/HA projects and 9 for other daily projects.
- Casual construction-worker MPF uses the MPFA daily relevant-income contribution scale. Regular MPF and casual MPF both follow the four-part payroll reconciliation; employees aged 65 or above have no mandatory contribution.
- Annual leave records support start/end dates and AM/PM sessions in 0.5-day units. The combined 2023-and-earlier balance does not expire. Each balance from 2024 onward normally expires on March 31 of the following year and may have an approved extension date.
- One leave record may allocate days to both the legacy balance and 2024-onward balances. Regular leave uses the oldest valid balance first. Incorrect records can be corrected or withdrawn.
- Final Payment is separate from ordinary four-part Payroll. It uses actual attendance only up to the last working day and may include unused leave/statutory-holiday pay, payment in lieu, severance or long-service payment, and special compensation.
- Final Payment service benefits split at 2025-05-01 where applicable. HR selects statutory eligibility and the reviewed wage basis; the system applies service proration, the HKD 15,000 annual unit cap, the HKD 390,000 overall cap, and any HR-entered pre-transition MPF offset.
- One Final Payment group exports one XLSX; all groups export a ZIP containing daily, monthly, and management/head-office XLSX files. The output retains Excel formulas.
- Employee Salary Certificates use the latest three generated Payroll months up to a selected month and retain Excel formulas.
- Payroll and statutory calculations are operational estimates where the UI says HR verification is required.

## Roles, Language, And Audit

- Application roles are `admin` and `hr`.
- Admin-only areas include user management and audit navigation.
- Primary operating pages support Traditional Chinese, Simplified Chinese, and English.
- User-entered/reference values remain as stored; only interface text is translated.
- Sensitive changes and business actions preserve audit events, including employee edits, identities, documents, intake, employment/salary changes, attendance confirmation, payroll export, and employee export.

## Current Scope Boundaries

Not part of the current core:

- Detailed day-by-day attendance OCR.
- OCR-assisted employee or attendance entry.
- Complex probation/approval state machines.
- Timeline filters.
- Fully automated legal decisions for every termination or MPF edge case.

These are scope facts, not a commitment to implement them later.
