# Archived HKR HR Redesign Requirements

> Historical requirements snapshot dated 2026-07-09. Later decisions and implementation superseded parts of this file, including its two-path employee-create flow and unresolved payroll questions. It is not a current source of truth. See [`../../../CONTEXT.md`](../../../CONTEXT.md) and the [`ADR index`](../adr/README.md).

Last updated: 2026-07-09

This document records the confirmed product decisions for the HKR HR redesign. It is the working source of truth before changing database schema, UI flows, OCR intake, payroll, or exports.

## Product Direction

HKR HR should be an employee-centered HR master system, not a collection of unrelated feature pages.

The core object is the employee. Documents, OCR, contracts, attendance, salary changes, certificate expiry, payroll, dashboard metrics, and exports should all be organized around the employee record.

The system must support:

- Employee information storage and maintenance.
- Document storage, preview, update, and download.
- OCR-assisted data extraction from 三寶, Staff Record, signed contract, and signed attendance PDF.
- Manual data entry and correction.
- Historical tracking of project, position, salary, and employee type changes.
- Certificate and visa expiry reminders.
- Payroll calculation from confirmed attendance summaries and effective salary history.
- XLSX exports by project, month, trade/position, employee type, payroll scope, or employee data scope.
- Contract generation from templates after employee information is available.

## Confirmed Employee Types

First version employee types:

| Type | Meaning |
|---|---|
| `HKR` | 瑞沃合同-月工 |
| `HKRD` | 瑞沃合同-日工 |
| `TE` | 臨時工 |
| `ASMTP` | 輸入內地人才計劃 |
| `BV` | 因公簽證 |
| `LD` | 勞務派遣 |
| `PRO` | 瑞港合同 |
| `MCR` | 澳門瑞沃 |
| `OTHER` | 其他 |

For now, `ASMTP` is treated as an employee type, not a separate visa-only attribute.

## Confirmed Employee Status

First version statuses:

- 在職
- 離職

離職 is only a status. It must not change the employee type or employee number.

## Employee Number Rules

Employee numbers should be generated automatically by employee type prefix.

Examples:

- `HKR0036`
- `HKRD0001`
- `ASMTP0014`

The system should find the next available number for the selected type.

If an employee is first created as `OTHER` and later changed to a known type, the system may generate a new employee number based on the new type. The user accepts this because the true type is normally known when the contract is signed.

Manual adjustment of employee number should still be possible for admin/authorized users.

## Employee Master Table

The employee master table should feel like a human-readable HR master sheet, not a raw database console.

Default visible columns:

- Employee number
- Status
- Employee type
- Chinese name
- English name
- Mobile
- HKID / Mainland ID
- Current project
- Current position
- Current salary
- Start date
- Missing document reminders
- Certificate expiry reminders

The table should support filtering and batch editing.

Confirmed low-risk batch editable fields:

- Status
- Current project
- Current position
- Remarks
- Data status note

Salary should not be edited directly in the master table. Salary changes must use the salary/project/position change workflow so that history and evidence are preserved.

Missing documents or missing evidence should be displayed like TMC requirement warning lights, with clear red indicators and filters.

## Employee Detail Page

Confirmed sections:

- Basic information
- Documents
- Current employment / salary
- Employment / salary history
- Certificates / visa
- Attendance and payroll
- Audit / operation history

Current project, current position, and current salary should show only the latest effective record. Full history appears in the history section.

## Required Data To Create Employee

Minimum fields to save a new employee:

- Chinese name or English name
- Employee type

Default status should be 在職.

All other information can be completed later.

## New Employee Flow

The new employee page should have two sub-options on one page:

1. Manual create.
2. Create from documents.

The right-side work area should change according to the selected sub-option.

Supported first-version document creation combinations:

- 三寶 only.
- Staff Record only.
- 三寶 + Staff Record.
- Contract can be added after or together with employee source files.

Contract alone should usually be uploaded to an existing employee rather than create a new employee by itself.

OCR conflict behavior:

- Existing database values should be preserved by default.
- OCR values should be shown as differences.
- UI should use a TMC-style side-by-side comparison when an existing value/file exists.
- HR can manually confirm replacement after comparing.

## Documents

Every employee should have a document checklist.

Confirmed checklist categories:

- 三寶
- Staff Record
- Signed contract
- HKID / Mainland ID / passport
- Bank information
- Change evidence
- Attendance PDF

Each category can contain multiple attachments.

三寶 may be stored as one combined attachment or split into individual certificate attachments. The system should allow multiple attachments under each category either way.

Only `HKR` monthly workers and `HKRD` daily workers require 三寶 in the first version.

Staff Record is expected eventually even if it is often received late. Missing Staff Record should be shown as a data status warning.

Signed contract is also expected eventually. Missing signed contract should be shown as a data status warning.

## Certificate And Visa Reminders

First-version certificate/visa reminders should cover:

- 平安卡
- 建造業工人註冊證
- Visa / work permit

## Employment / Salary / Project History

Project, position, salary, and employee type changes must keep history.

Every change record should include:

- Effective date
- Change type: salary, project, position, employee type, or combined change
- Old value
- New value
- Remarks
- Evidence attachment, optional at save time

If evidence attachment is missing, the change can still be saved, but the system must show a missing evidence warning in the first version.

Evidence may include signed contract, email screenshot, formal notice, or other PDF/image proof. Evidence can be uploaded later.

Contract is only one possible source of salary/project/position evidence. It must not be the only authority. Manual changes with evidence are supported.

## Attendance

First version should store monthly attendance summary, not daily detail.

Confirmed attendance summary fields:

- Employee
- Month
- Project
- Working days
- OT hours
- Sunday / holiday days
- Attendance PDF attachment
- Manual confirmation status

The signed attendance PDF should be stored as an attachment and easy to preview from the employee/month view.

OCR is used to assist extracting the monthly summary from signed attendance PDF. OCR raw text does not need to be shown or kept as a user-facing field.

Daily attendance details can be added later if needed, but are not first-version scope.

## Payroll

`Payroll PC AD014 - 202605(2).xlsx` is the current reference for the monthly staff payroll layout.

The title/layout indicates two formula families:

- Monthly staff: monthly salary divided by days in month times working days, plus OT and Sunday/holiday amounts.
- Daily staff: day rate times working days, plus OT.

First version should support filtering payroll by project, employee, or all employees.

Payroll should be generated from:

- Confirmed attendance monthly summaries.
- Effective salary/project/position history for that month.
- Employee type.

First-version payroll behavior:

- Payroll is previewed and exported as XLSX.
- Do not store each generated payroll result as a long-lived payroll status in the first version.
- Each preview/export should calculate from current employee data, employment/salary history, and confirmed monthly attendance summaries.
- If salary changes during a month, payroll should split/prorate by effective date.

First-version formulas:

- Monthly staff: monthly salary / days in month * working days + OT amount + Sunday/holiday amount.
- Daily staff: daily rate * working days + OT amount + Sunday/holiday amount.

Payroll calculation rules must be visible on the payroll page at all times so the user can understand and later change them.

OT calculation details are still pending confirmation. Existing workbook formulas must be reviewed before implementation.

Payroll blocking rules:

- Missing attendance: cannot generate payroll.
- Missing salary: cannot generate payroll.

Payroll warning rules:

- Missing change evidence.
- Missing bank information.
- Missing contract.
- Other non-blocking data warnings.

For warnings, the system should show a confirmation prompt. The user must click confirm before continuing payroll generation/export.

## Dashboard

First-version dashboard metrics:

- Active employee count.
- Current month estimated payroll amount.

The dashboard should look polished and management-friendly, but should stay grounded in confirmed HR/payroll data.

Login should land on the dashboard.

Dashboard first screen should include:

- Active employee count.
- Current month estimated payroll amount.
- Certificate expiry warnings.
- Pending work / reminders.

The dashboard is the default home page, not the employee list.

Dashboard warning counts should be clickable. For example, clicking "3 expiring certificates" should open the employee master table with the matching filter applied, showing the three employees and the certificate details.

To avoid duplication, missing documents should primarily appear in the to-do/reminder area, while top-level dashboard metric cards stay focused on:

- Active employee count.
- Current month estimated payroll amount.
- Certificate/visa expiry reminders.

To-do/reminder items should include:

- Missing Staff Record.
- Missing signed contract.
- Missing change evidence.
- Pending OCR confirmations.
- Attendance not entered for the selected/current month.

## Main Navigation

First-version main navigation should be limited and logical:

- Dashboard
- Employee master
- New employee
- Document intake
- Attendance / Payroll
- Export center

Raw DB management must not be a normal navigation item. If retained, it should be hidden as an admin advanced tool.

The first version should avoid:

- Too many technical tables.
- Too many unrelated buttons.
- SQL-facing screens.
- Confusing English-only internal statuses.
- Complex permissions before they are truly needed.
- Prematurely over-automated payroll steps.

## UI Language

The UI should support language switching:

- Traditional Chinese.
- Simplified Chinese.
- English.

This should feel similar to the TMC platform language switching behavior.

## Employee Master UI

Employee master table behavior:

- Clicking a row opens the employee detail page.
- Editing is done in the employee detail page, not inline in the table.
- Batch editing can be considered later for selected low-risk fields, but it is not a first-priority interaction.

First version does not need advanced filters yet.

The employee detail page should start with an employee profile card showing:

- Name.
- Employee number.
- Status.
- Employee type.
- Current project.
- Current position.
- Current salary.
- Missing document warning lights.

Salary shown in the profile card should include monthly salary or daily rate plus amount.

Current employment/salary and employment/salary history should remain separate. The top area shows only the latest effective record. The full history appears below as a table or timeline.

The adjustment entry point should sit beside the employee profile card as a clear "Adjust" action.

One adjustment can update multiple fields at the same effective date, for example project + position + salary.

## Employee Detail Documents UI

The document section should include both:

- Category cards, such as 三寶, Staff Record, contract, attendance, bank information, change evidence.
- Timeline of uploaded files and document-related actions.

Document card first-version actions:

- Preview.
- Upload new version.
- Mark replaced / voided.
- Download.

Document timeline may also include related data-change events. For example, a salary adjustment with an email screenshot can appear both in the document timeline and in salary history.

## New Employee UI

The New Employee page should contain two sub-options on one page:

- Manual create.
- Create from documents.

Manual create should be a single-page form. It should not require file upload because file-driven creation belongs to the document-create option.

Manual create fields are flexible because the user may only have partial information at the time of creation.

Create from documents should follow the TMC intake pattern:

- Left side: upload files.
- Middle: file preview.
- Right side: OCR field comparison and confirmation.

OCR confirmation should be one file at a time, similar to the TMC document intake workflow.

Before redesign implementation, review the current HKR intake rules/code and the TMC intake workflow, then reuse the parts that fit.

## Document Intake UI

Document intake is the single entry point for all scanned/OCR documents:

- New employee source documents.
- Existing employee supplementary documents.
- 三寶.
- Staff Record.
- Signed contract.
- Signed attendance PDF.
- Other OCR-supported HR documents added later.

Attendance PDF should also enter through document intake.

OCR is only a prefill aid. It is not the purpose of the workflow.

The purpose is:

- Store the original document.
- Preview the document.
- Prefill fields when OCR can help.
- Let HR manually confirm or fill missing fields.
- Import the confirmed data and attach the document to the employee.

Do not over-optimize around OCR retry workflows. If OCR fails, the file is still stored and previewable; the relevant fields remain blank and HR can type them manually. Re-OCR is not a required first-version feature.

The correct business wording is "import" or "document import", not "OCR confirmation" as the final business action.

## OCR Extraction Scope

### 三寶

三寶 OCR should try to prefill:

- Chinese name / English name.
- HKID / Mainland ID / other identity number.
- Gender.
- Date of birth.
- Safety card number and valid period.
- Construction worker registration number and valid period.

### Staff Record

Staff Record OCR should try to prefill:

- Chinese name / English name.
- Mobile country/region code and mobile number.
- Residential address.
- HKID / Mainland ID / other identity number.
- Bank name.
- Bank account number.
- Emergency contact name.
- Emergency contact phone.
- Education level.
- Major.
- Graduation school.
- Professional qualification / certificate entries.
- Start date.

### Signed Contract

Signed contract OCR should try to prefill:

- Chinese name / English name.
- Contract signing date.
- Contract effective date.
- Employer / hiring company.
- Project.
- Position.
- Monthly salary / daily rate.
- Currency.
- Amount.

Contract OCR salary/project/position information should create a pending employment/salary change for HR review. HR must confirm it before it writes to employment/salary history.

When confirming a pending employment/salary change, HR must enter or confirm the effective date.

### Source Priority

First-version source priority:

- Identity data: 三寶 wins.
- Bank/contact/personal background data: Staff Record wins.
- Salary/position/project: signed contract or later change evidence wins.
- Existing manually confirmed data is never silently overwritten.

### Comparison UI

Document import confirmation should use a TMC-style comparison:

- Left side: current system value/file.
- Right side: imported/OCR value/file.
- HR chooses existing value, imported value, or manual value.
- Replacement only happens after explicit HR confirmation.

Replacing an existing file should require a reason, such as:

- Data update.
- Existing file is wrong.
- Better scan / rescan.
- Signed or completed version.
- Other.

## Attendance / Payroll UI

Attendance is handled as monthly employee-level PDF intake.

Reality:

- One employee has one signed attendance PDF for one month.
- HR may upload a batch of PDFs.
- The system should OCR each PDF one by one.
- HR confirms the extracted monthly attendance summary.

Employee matching for attendance PDF:

- Use OCR-recognized employee name.
- HR can manually adjust/select the employee.
- Do not rely on filename to identify the employee.
- If matching fails, keep it pending manual confirmation.
- If the PDF/OCR does not identify an employee, HR must manually select the employee.

Attendance month:

- HR selects the year/month at upload time.
- The selected month is the batch default and has priority over OCR/file content.

Attendance import first-version confirmation fields:

- Employee.
- Month.
- Project.
- Working days.
- OT hours.
- Sunday / holiday days.
- PDF preview.

Attendance PDF import should attach the PDF to the employee's Attendance PDF document category.

Document import should support a recent batch list so HR can return to unfinished batches and continue one-file-at-a-time confirmation.

Attendance status should stay simple:

- 考勤表已錄入.
- 考勤表未錄入.

The view should require/select year and month. Default month should be the previous month.

Payroll export is an action, not a long-lived status. Do not create complicated statuses like exported/generated unless there is a real operational need later.

Attendance / Payroll first screen should show attendance entry status grouped by project for the selected month.

## Export Center

First version export center should be organized by business audience/purpose rather than raw report type, but the wording should be professional.

Possible wording to refine later:

- Management Overview / 管理總覽.
- HR Records / 人事資料.
- Payroll & Attendance / 考勤出糧.

First-version grouping is accepted, but the UI should explain what each group contains.

Suggested meaning:

- Management Overview / 管理總覽: project headcount, current month estimated payroll, management summary by project/month.
- HR Records / 人事資料: employee master data, missing document list, certificate/visa expiry list, staff document checklist.
- Payroll & Attendance / 考勤出糧: payroll workbook, attendance entered/missing list, monthly attendance summary.

Export grouping labels must support Traditional Chinese, Simplified Chinese, and English translations.

Export Center should not be limited to XLSX data. It may include both:

- Structured data exports, such as XLSX/CSV reports.
- Document/package exports, such as employee attachment bundles, attendance PDF packages, or selected HR document downloads.

The UI must clearly separate data report exports from document/package exports.

## Audit Trail

Important operations must be logged:

- Salary changes.
- Project changes.
- Position changes.
- Employee type changes.
- OCR confirmation.
- Manual replacement of existing data with OCR data.
- Document upload.
- Contract generation.
- Attendance confirmation.
- Payroll export.
- Employee data export.

## Permissions

First-version permission roles:

- `admin`
- `hr`

Keep permissions simple in the first version.

## Admin / DB Management Direction

The user does not want a raw technical database console as the main management tool.

Preferred direction:

- Human-readable employee master table.
- Filterable and batch editable.
- Employee-level detail pages.
- Raw DB/admin tools should be removed in the redesign and rebuilt only if a clear human workflow requires them.

The existing `/admin/db` page should be deleted during the redesign rather than kept as a visible or hidden feature.

## Redesign Delivery Decisions

The redesign should be planned as a complete product redesign, but implemented in phases for review and control.

Confirmed delivery posture:

- Do not start code changes until the user explicitly approves the方案文檔.
- Produce documentation first: complete redesign proposal, database/schema draft, UI wireframe description, and phased implementation plan.
- Build the complete system direction, but validate phase by phase.
- Existing rushed/test pages can be removed instead of preserved.
- Existing test data can be deleted; no production DB backup is required for the current test-only dataset.
- Old DB/admin management page should be deleted and redesigned from scratch only if needed.

TMC reuse requirement:

- Before implementation, inspect the TMC platform workflow/document intake logic and reuse suitable UI/flow/code patterns where practical.
- Do not rewrite TMC-style side-by-side comparison or intake workflow from scratch if existing TMC code can be adapted.
- HKR HR remains an independent system and must not connect to the TMC database/schema/services.

## Data Field Decisions

This section records confirmed data-field decisions from requirement discussion round 7.

### Employee Basic Fields

First-version employee basic fields should include:

- Employee number.
- Status.
- Employee type.
- Chinese name.
- English name.
- Gender.
- Date of birth.
- Mobile country/region code, for example `+852`.
- Mobile number, for example `68819887`.
- Email.
- Residential address / 住址.
- ID country/region/type, for example Mainland China, Hong Kong, Macau, or other country.
- ID number.
- HKID number, where relevant.
- Mainland ID number, where relevant.
- Macau ID number, where relevant.
- Passport number, where relevant.
- Exit-entry permit / 通行證 number, where relevant.
- Bank name.
- Bank account number.
- Emergency contact name.
- Emergency contact phone.
- Department.
- Project.
- Position / trade.
- Employer / hiring company.
- Education level.
- Major.
- Graduation school.
- Professional qualification / certificate entries, multiple entries allowed.
- Start date.
- Whether visa/work permit is required.
- Visa category, shown only when visa/work permit is required.
- Visa number.
- Visa issue date.
- Visa expiry date.
- Remarks.

Address should be labelled as residential address / 住址.

Mobile phone should be split into country/region code and phone number.

ID should support a country/region/type selector before entering the number.

Employer / hiring company should be selected from a reference list where possible. Initial known examples:

- 香港瑞沃工程有限公司.
- 青岛海发国有资本投资运营集团有限公司.

### Reference Lists / Dropdowns

The system should avoid free typing where a controlled list is practical.

Reference lists should exist for:

- Projects.
- Departments.
- Positions / trades.
- Employer / hiring companies.
- Employee types.
- Visa categories.
- Certificate types.
- Other repeated HR values discovered during implementation.

HR users should be able to add new reference values easily when the needed value does not exist.

When adding a new value, HR should be able to see existing values to avoid duplicates.

Reference values should be editable. If a reference value is renamed, existing employees using that value should reflect the new name. For example, if five employees use `XX8` and the reference is renamed to `XX7`, those five employees show `XX7`.

Initial position/trade and reference values should be pre-read from `瑞港集团员工档案月度更新（截至26年4月） - 试(1).xlsx` where possible.

Project and position should feel like current facts on the employee profile. Internally, salary/project/position history can preserve effective-date changes, but users should not have to think in terms of a calculated current value during normal viewing.

### Salary / Employment History Fields

Salary and employment history records should include:

- Effective date.
- Change type: salary, project, position, employee type, or combined change.
- Old value.
- New value.
- Currency, where salary is involved.
- Amount, where salary is involved.
- Monthly salary / daily rate.
- Project.
- Position.
- Remarks.
- Evidence attachment, optional at save time.

Salary records require currency and amount.

OT calculation should be reviewed against existing payroll workbook formulas before deciding whether to expose a manual OT calculation field. Do not invent OT rules before checking Excel formula patterns.

### Attendance Summary Fields

First-version attendance should remain monthly summary, not daily detail.

Attendance monthly summary fields should include:

- Year/month.
- Employee.
- Project.
- Working days.
- OT hours.
- Sunday / holiday days.
- Attendance PDF attachment.
- HR confirmer.
- Confirmation time.

E-call is needed eventually, but is not urgent for the first redesign implementation. It can be added after the initial version is stable.

### Payroll Preview / Export Columns

Payroll preview/export should align with `Payroll PC AD014` as closely as practical:

- No.
- English Name.
- Chinese Name.
- Contract / Project.
- Post.
- Date Joined.
- Day(s).
- Rate.
- Amount.
- OT Hours.
- OT Rate.
- OT Amount.
- Sunday / Holiday.
- Total.

First-version payroll export should produce one workbook similar to `Payroll PC AD014`. Additional output formats, such as signed acknowledgement forms or other payroll packages, can be added later.

Payroll filters for first version:

- Year/month.
- Project.
- Employee type.
- Employee.
- Status.

Management payroll summary is needed in the first version:

- Project.
- Headcount.
- Monthly/daily wage subtotal.
- OT subtotal.
- Total payroll.

This summary can be adjusted later after real usage.

### Attachment Fields

Attachments do not need a full versioning model in the first version.

Use simple attachment status:

- active.
- voided / replaced.

Upload date must be recorded.

Document date fields are needed for certain document types:

- Contract signing date.
- Contract effective date.
- Attendance month.
- Construction worker registration certificate valid from / valid to.
- Safety card valid from / valid to.
- Visa/work permit issue date / expiry date.

### Certificate / Visa Fields

Certificate and visa records should include:

- Type.
- Certificate/visa number.
- Issue date.
- Expiry date.
- Attachment.
- Remarks.

For construction worker registration and safety card, both valid-from and valid-to dates are needed when available.

Visa/work permit should be conditional in employee basic information:

- Default: no visa/work permit required.
- If yes, show visa category, visa number, issue date, expiry date, attachment, and remarks.

Initial visa category values should be reviewed from the `員工Visa` sheet in the employee archive workbook. Known examples include:

- 優才.
- 因公往來.
- IANG.
- 輸入內地人才計劃（專才）.
- 輸入內地人才計劃（勞工）.

Exact labels should be normalized later from the workbook.

### Missing Document Rules

First-version missing document rules remain:

- `HKR` and `HKRD`: require 三寶, Staff Record, and signed contract.
- Other types: require Staff Record and signed contract.
- Any project/position/salary/type adjustment without evidence should show missing change evidence.

### Language Scope

Only UI labels need translation.

User-entered/reference data such as project names, position names, company names, and document names should stay as originally recorded. They do not need translation.

## Pending Questions

To confirm later:

- Exact first-version employee type labels shown in the UI.
- Whether `ASMTP`, `BV`, and `LD` later become visa/employment attributes rather than employee types.
- Exact payroll export layout and formulas for daily workers.
- Exact OT calculation rules and whether OT rate is auto-calculated or manually reviewed.
- Exact certificate expiry warning thresholds.
- Exact difference between `admin` and `hr` permissions.
- Whether employee number regeneration after type change should require explicit confirmation.
- Whether salary evidence should be mandatory before payroll generation or only shown as warning.
