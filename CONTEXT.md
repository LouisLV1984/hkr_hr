# HKR HR Context

Updated: 2026-11-18

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

`hkr_hr/*/models.py` (assembled by `hkr_hr/app/models.py`, governed by [`hkr_hr_mvp/docs/architecture.md`](hkr_hr_mvp/docs/architecture.md)) is current application schema truth. PostgreSQL stores file paths and metadata; document binaries remain on the filesystem.

GitHub source control contains application source and current project documentation only. Employee, attendance, payroll, contract, credential, runtime, generated, backup, and local verification data remain outside version control.

## Small-Team Operating Model

Approximately three operators use this internal system. Shared monthly context, one-save initial setup, actionable exception lists and reusable source editors are the normal workflow. No new approval hierarchy is required. New contract drafts and Payroll snapshots preserve their own historical facts; they do not alter formal terms or prove payment. Runtime dependency maintenance uses a local wheelhouse, and work calendars support local CSV. See ADR-0026 for the current decision and precise legacy limits.

## Employee Vocabulary

- Employee status displayed by the application is derived from effective-dated employment periods. A future last working day remains `active` until that date; after the period ends it becomes `departed`.
- Employee-name search expands the entered text to Traditional and Simplified Chinese variants before matching; stored employee data is not changed.
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

1. Employee Workbench (expiry, confirmations, leave, attendance and payroll by employee);
2. Employee Files (browse name and staff-number cards by department or primary position, search, or create an employee);
3. Leave & Work Injury;
4. Attendance Entry (PDF batch intake and resume);
5. Payroll.

Data Settings & Export is a utility in the header. See [ADR-0029](hkr_hr_mvp/docs/adr/0029-employee-workbench-and-task-pages.md).

Attendance Entry handles PDF collection, Payroll-group-specific fields and the Sunday/statutory-holiday Payroll/Comp Leave decision. Monthly Payroll, Monthly MPF Contributions and Departure Payroll live under Payroll Analytics & Export. The departure workbook retains the formal English label Final Payment. Employee-record exports and attachment bundles live under Data Settings & Export. Admin tools remain separate.

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
| `other` | General attachment classified by a configurable general-attachment type |

三寶 covers identity evidence, construction worker registration, and safety training/card evidence. Stable source precedence is:

- Identity and construction/safety certificate facts: 三寶.
- Contact, bank, emergency-contact, education, and background facts: Staff Record.
- Contract/employment/salary facts: signed contract or later confirmed change evidence.
- Existing manually confirmed values are never silently overwritten.

V1 does not use OCR. HR previews the source document and enters or corrects the relevant structured data manually.
Staff Record review captures contact, residential address, emergency-contact, education, employment-start and bank facts. Bank details create or update the employee's effective-dated bank-account history and link the Staff Record as evidence without replacing an identical dedicated bank proof.

The Credentials and Files tab contains the credential cards and the Contracts & Attachments library. The library provides one employee-profile document gateway. Three Treasures, Staff Record, signed Employment Contract, CV, and general attachments can be uploaded and reviewed there. Bank, identity/credential, employment/pay, probation, leave, work-injury, attendance, termination, and name-change evidence is routed to the owning structured record so an attachment cannot exist without the business fact it supports. System document purposes are fixed; only general-attachment subtypes are maintained in Data Options. See ADR-0024.

Annual leave is deducted once in this order: compensation leave, the 2023-and-earlier balance, then the oldest valid 2024+ balance. Calendar-year leave taken and usage of a specific entitlement bucket are separate measures; one leave record must never be counted against two balances.

Employee document status is `active`, `replaced`, or `voided`. Replacing or voiding requires a reason.
Employee documents store a SHA-256 content digest. Identical-content checks are scoped to the same employee and document category; attendance PDFs are further scoped to the same payroll month. HR must explicitly confirm an identical replacement.
Replacing a document updates linked identity, certificate, VISA, qualification, assignment, salary, attendance, contract and employment-period references to the new active document while retaining the old file as history.

## Attendance And Payroll

- Attendance has one employee/month summary and project detail segments for four periods:
  - current-month days 1-20 actual;
  - current-month days 21 to month end forecast;
  - previous-month days 21 to month end actual;
  - previous-month days 21 to month end original forecast.
- Attendance is required by default. HR may mark an employee/month as not requiring an attendance PDF; the system records the action and uses generated full attendance with zero OT and E-CALL. HR may restore the requirement, which blocks Payroll until attendance is imported.
- Attendance expected/missing lists follow employment-period overlap with the selected month: the departure month remains in scope, while later months do not.
- The signed attendance PDF is stored as an employee document.
- Daily attendance records ordinary paid workdays. Monthly and OFFICE salary history defaults to `full_month`, so ordinary-workday counts do not determine base salary. A contractually explicit `attendance_days` exception instead records actual paid calendar attendance days; Saturday, Sunday and statutory-holiday work is included directly and receives no additional Sunday/statutory-holiday work payment. The exception is effective-dated with salary history and forecasts zero unless HR has a confirmed arrangement. See ADR-0020.
- Monthly and OFFICE assignments carry an effective-dated `workweek_days` value of 5, 5.5 or 6. Existing Monthly assignments default to 6 and existing Management/OFFICE assignments default to 5. Forecasts count Monday-Friday for 5 days, add Saturday morning as 0.5 for 5.5 days, or count Monday-Saturday for 6 days. Site Daily and Site Monthly then exclude the employee's regional statutory holidays; Management and Head Office exclude regional general holidays. Hong Kong statutory and general-holiday dates can be imported together from official sources; the statutory Winter Solstice/Christmas choice is fixed to Christmas Day under company policy. The primary workflow imports a local CSV; optional online import can prepare the next calendar year when connectivity is available. Payroll itself has no live internet dependency.
- HR selects each date genuinely worked outside the employee's workweek; the system derives the total. Sunday/statutory-holiday and 5-day Saturday work count as one day; 5.5-day Saturday afternoon counts as 0.5 day without a separate session selector. One monthly attendance record applies one treatment: `pay` or `comp_leave`; paid days add one applicable daily rate while comp leave adds an auditable no-expiry credit with no extra work pay.
- Company policy pays a daily worker one normal daily rate for each regional statutory holiday from the employment start date even when no work is performed. Daily ordinary attendance includes every non-statutory-holiday date actually worked, including Sunday; an unworked Sunday is unpaid. Unsaved daily attendance prefills Monday-Saturday only and excludes statutory holidays plus recorded leave/work injury, after which HR adds confirmed Sunday or statutory-holiday work from the PDF. If the employee works a statutory holiday, `pay` adds another one daily rate while `comp_leave` keeps the automatic holiday pay and adds one comp-leave day. Sunday is never entered in the statutory-holiday work field.
- Annual, sick and unpaid leave are effective dated leave records in 0.5-day units and are read-only in Attendance. Annual leave is paid and consumes comp leave, then 2023-and-earlier leave, then the earliest valid 2024+ balance. For daily workers, HR-entered actual paid workdays are the sole wage basis, so linked unpaid-leave records are for reconciliation and are not deducted again. For Monthly and OFFICE staff, unpaid leave is deducted once from monthly salary at the calendar-day rate. After probation, sick leave pays the first aggregate day in a calendar month in full and later days at four-fifths; before probation it pays four-fifths from day one. Missing sick evidence is a non-blocking red warning.
- Work injury is not an employee status. It is maintained only in the Work Injury card under Leave & Work Injury; the employee profile shows a read-only summary/history link. Each period uses HR-verified monthly earnings at the accident and explicitly selects four-fifths work-injury pay or full pay. Covered dates are attendance-exempt. Monthly follow-up/medical reimbursement exports to the workbook's Work Injury Compensation / Medical Expenses column (AM on Daily; AN on Monthly and OFFICE), increases net pay, and is excluded from MPF relevant income. See ADR-0018.
- Large E-CALL adds one applicable daily rate per occurrence. For daily workers, the same work event is entered either as one ordinary attendance day or one Large E-CALL, never both. Ordinary E-CALL adds HKD 400 per occurrence and may be recorded for a separate call-out beyond a completed attendance day.
- Current-month E-CALL is included in current payroll. Previous-month days 21 to month end E-CALL is included in overpay/underpay reconciliation. Current-month tail forecasts assume zero E-CALL until actual attendance is received.
- Payroll stores calculation snapshots with employee totals, project allocation lines, source facts, warnings, and a rule version. Export files are regenerated from templates.
- Payroll is calculated live on page load and filter changes. Export is the only commit action and creates the calculation snapshot automatically.
- Missing attendance, salary, or payroll bank details blocks payroll export.
- Monthly Payroll may be previewed across payroll entities, but a formal export contains exactly one payroll entity. Employees without an effective payroll entity do not enter any entity-specific payroll workbook.
- Other missing evidence/documents are warnings that require acknowledgement.
- One payroll group exports one XLSX; all groups export a ZIP containing three XLSX files.
- Daily-worker OT divisor is 10 for TMC046/HA projects and 9 for other daily projects.
- Standard Monthly and OFFICE contract salary is allocated by calendar day. Weekday after-hours OT is 1.5 times the hourly rate; genuine work beyond the effective 5/5.5/6-day workweek uses `pay` at an additional 1 times the daily rate or `comp_leave` with no extra work pay. Saturday afternoon counts as 0.5 day under a 5.5-day workweek. The `attendance_days` exception instead pays base salary by actual paid calendar attendance days and does not add a separate Sunday/statutory-holiday work payment.
- Effective-dated meal, transport and special allowances are maintained as Fixed Allowances in Employment & Salary. Meal/transport export to `Traffic Allowance / Meal Allowance`; special allowance exports to `Bonus / Fixed Allowance`. Substitute-shift other allowance is entered only on actual Attendance project rows and exports to `Other Payment`; historical manual amounts remain readable. Dated ordinary-attendance and OT corrections are entered from the current employee’s Attendance PDF, retain the source month, settlement month and shared evidence, and feed Other Payment. See ADR-0027.
- Casual construction-worker MPF uses the MPFA daily relevant-income contribution scale. Regular MPF and casual MPF both follow the four-part payroll reconciliation; employees aged 65 or above have no mandatory contribution.
- MPF scheme and Member Account No. are effective-dated employee records. The system derives the current record and automatically closes the prior record when a later scheme starts.
- Four seeded company MPF schemes hold the employer account and payroll group identifiers. MPF reports use the same monthly Payroll results, export one XLSX per scheme or a ZIP for all schemes, and retain zero-income or exempt employees.
- Employee MPF Member Account No. is optional. Effective date remains required; non-exempt records require a scheme. Explicit exempt records may omit the scheme, count as complete, and do not enter or block scheme reports. Exempt records with a scheme remain in that report. Other missing MPF metadata can block the MPF report, not otherwise ready Payroll. Mid-month scheme splitting is outside the current core.
- V0.5.6 monthly project allocation was refined on 2026-09-16: opt-in temporary target ranges transfer only scheduled workday shares, using effective employment schedules and applicable paid holidays. Rest days and paid holidays retain the original employment project; Saturday transfers 0 / 0.5 / 1 day for 5 / 5.5 / 6-day schedules. Partial ranges are allowed; overlaps and out-of-month dates are rejected. Base pay, sickness/injury components and unassigned fixed allowances use the same shares; attendance extras and prior-tail reconciliation keep their own project rows. One PDF supports multiple project rows in the existing editor. Previously saved calendar-inclusive allocation remains explicit legacy evidence until HR converts it; snapshots require re-export. Daily, attendance-based monthly and Departure Payroll retain existing paths. No employee data is bulk-converted.
- Annual leave records support start/end dates and AM/PM sessions in 0.5-day units. The combined 2023-and-earlier balance does not expire. Each balance from 2024 onward normally expires on March 31 of the following year and may have an approved extension date.
- From V0.5.3, new or explicitly corrected annual, sick and unpaid leave derive from effective assignments and saved local holiday calendars: 5/5.5-day schedules exclude Saturday and Sunday; 6-day schedules count Saturday and exclude Sunday. Applicable Payroll-group holidays are excluded, with AM/PM each 0.5 day. Contractual attendance is unchanged (5.5-day Saturday remains 0.5 attendance day); work-injury calendar-day pay is unchanged. Each new/corrected leave stores its date-unit allocation for consistent attendance and Payroll use. Legacy records retain their prior basis until HR explicitly corrects them. Source writes reject overlapping active leave/injury periods; inconsistent legacy data continues to block affected Payroll until corrected.
- V0.5.4 adds an explicitly confirmed, employee-filtered batch operation on the existing leave-difference page. Employment & Salary links to outstanding differences. Selected records keep dates, sessions, evidence and remarks; update only day counts and allocations. During the current reconciliation phase, confirmation also recalculates that employee's existing Payroll months from the earliest affected month onward, preserving historical snapshots and before/after audits; no attendance input rewrite. Final Payment leave-pay days follow the balance delta while retaining prior manual offsets and other inputs. All changes are atomic; stale previews, zero-day records, overlaps or calculation blockers cannot silently partially apply. Downloaded workbooks require re-export; a snapshot is not proof of payment.
- Leave/injury changes after Attendance confirmation produce a derived recheck warning in Attendance and Payroll without automatically modifying entered attendance totals. Unchanged compensation-leave sources retain their IDs and allocations on attendance resave.
- One leave record may allocate days to both the legacy balance and 2024-onward balances. Regular leave uses the oldest valid balance first. Incorrect records can be corrected or withdrawn.
- Leave details follow the employee-profile current-state/history pattern: current-year, 2023-and-earlier and compensation-leave cards sit above one change history. Current-year entitlement and the legacy confirmed total are adjusted independently; compensation leave has no manual-add path.
- Departure Payroll (the export workbook still uses the formal English label Final Payment) is separate from ordinary four-part Payroll. A departing employee is excluded from Monthly Payroll in the departure month; Departure Payroll is the wage source. It inherits fixed allowances effective through the last working day, month-specific adjustments, Attendance substitute-shift allowance and work-injury medical reimbursement. Medical reimbursement increases net pay but is excluded from MPF relevant income. Its MPF replaces (rather than duplicates) ordinary Payroll MPF in that month's MPF report, and an unconfirmed Departure Payroll blocks that employee's MPF export. Annual-leave pay uses the HR-verified previous-12-month wage total divided by 365; departure-year entitlement is prorated by inclusive employment days, with overuse offset against other leave and any remainder deducted in Departure Payroll.
- Departure Payroll service benefits split at 2025-05-01 where applicable. HR selects statutory eligibility and the reviewed wage basis; the system applies service proration, the HKD 15,000 annual unit cap, the HKD 390,000 overall cap, and any HR-entered pre-transition MPF offset.
- One Departure Payroll group exports one XLSX; all groups export a ZIP containing daily, monthly, and management/head-office XLSX files. The output retains Excel formulas and keeps employee MPF on the employee's single wage row.
- Employee Salary Certificates use the latest three generated Payroll months up to a selected month and retain Excel formulas.
- Payroll and statutory calculations are operational estimates where the UI says HR verification is required.

## Roles, Language, And Audit

- Application roles are `admin` and `hr`.
- Admin-only areas include user management and audit navigation.
- Primary operating pages support Traditional Chinese, Simplified Chinese, and English.
- User-entered/reference values remain as stored; only interface text is translated.
- User accounts retain last-login, last-seen and logout timestamps; a signed-in account active within the last 15 minutes is shown as online.
- Sensitive changes and business actions preserve audit events, including login success/failure, logout, employee edits, identities, documents, intake, employment/salary changes, attendance confirmation, payroll export, and employee export.

## Readiness And Production Safety

- One shared readiness service derives Employee File, selected-month Attendance, and selected-month Payroll Status. Employee Management is the full status matrix; Work Overview shows only a compact action summary linking to the filtered employee list. Neither maintains separate progress states or notes.
- List and management workspaces use the left rail for the active submodule, month/year, filters and current selection; the right pane displays filtered results and performs actions. Work Overview and the grouped card directory have no left rail, and focused preview/form workbenches retain task-specific layouts.
- Attendance Management includes Attendance Details, Attendance Collection, Specific-month Attendance Exemption, and Long-term Attendance Exemption. A specific-month exemption applies only to the selected month and automatically returns to attendance-required afterwards.
- Payroll bank details (bank name and account number) are required Payroll facts. Bank account proof is an optional attachment and does not block Payroll.
- HR-facing status wording states the actual condition: filled/not filled, created or configured/not created or configured, filed/not filed, attendance received/not received/exempt, and Payroll ready/not ready with a specific reason.
- Missing conditions disappear when the source employee, document, attendance or Payroll data is corrected. Status items link to the relevant employee or operating page.
- Permanent employee deletion is an Admin-only correction tool named `Delete employee`; HR accounts do not see it.
- Recovery has two layers: short-retention snapshots under mini PC production storage and encrypted incremental long-retention snapshots on the authorised laptop. PostgreSQL dumps, attachments and templates are restored only into isolated test targets during verification.
- Production requires CSRF protection, login throttling, local post-login redirects, a non-placeholder secret key, server-side upload validation and friendly HTTP error pages. These controls must not add approval steps to ordinary HR work.

## Current Scope Boundaries

- Company calendar-year advance annual leave is activated by HR confirmation of actual employment start and initial contract leave. Current-year corrections preserve historical accounts and year-specific manual overrides; later years are persisted on first authenticated use after rollover. See ADR-0025. The permanent 2023-and-earlier card remains visible and manually maintained.

- Salary Records (`employee_salary_records`, `/salary-records`) is an independent manual register from 2026-04. It records gross pay, employee MPF actually deducted (including catch-up deductions in the deduction month), net payment, currency, entity, remarks and evidence. It never feeds Payroll/MPF calculations, leave/final-payment averages or payment execution. Explicit saved-Payroll prefill is read-only until HR saves a separate record.
- One employee/month/payroll-entity record is revisioned with audit and withdrawal. The central monthly table is the only editor; employee profiles display read-only records. April–March summaries separate currency and entity, include departed workers and flag missing employment months through the current month. Export is reconciliation material, not a statutory tax return.

Not part of the current core:

- Detailed day-by-day attendance OCR.
- OCR-assisted employee or attendance entry.
- Complex probation/approval state machines.
- Timeline filters.
- Fully automated legal decisions for every termination or MPF edge case.

These are scope facts, not a commitment to implement them later.

PDF previews use bundled Mozilla PDF.js assets (including fonts, CMaps and WASM) and existing authenticated file routes. No browser PDF plugin or runtime CDN is required; original-byte download remains available.
