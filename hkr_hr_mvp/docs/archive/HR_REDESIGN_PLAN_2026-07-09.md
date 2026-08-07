# Archived HKR HR Complete Redesign Plan

> Historical pre-implementation proposal dated 2026-07-09. It contains superseded approval gates, open questions, draft schema, and a rejected two-path employee-create flow. It is not current product authority. See [`../../../CONTEXT.md`](../../../CONTEXT.md) and the [`ADR index`](../adr/README.md).

Last updated: 2026-07-09

This document is the approval-ready redesign proposal for HKR HR. It is based on `HR_REDESIGN_REQUIREMENTS.md` and the reviewed TMC web platform implementation under `T:\_system\app`.

No application code should be changed for this redesign until the user explicitly approves this plan.

## 1. Product Goal

HKR HR should become an employee-centered HR operating system.

The employee record is the center. Documents, OCR import, contract generation, project/position/salary changes, certificates, visa records, attendance PDFs, payroll preview, payroll export, management dashboard, and export packages should all connect back to one employee profile.

The first complete redesign should solve these business jobs:

- Preserve employee documents in an organized, previewable archive.
- Maintain clean employee master data without exposing raw database tables.
- Use Tesseract OCR only as a prefill assistant.
- Let HR confirm every imported value before it writes to the database.
- Track current and historical project, position, salary, employee type, and evidence.
- Show certificate/visa expiry and missing-document warnings.
- Import signed monthly attendance PDFs and confirm monthly summaries.
- Calculate payroll preview from confirmed attendance and effective salary history.
- Export payroll, employee records, management summaries, and document packages.
- Generate contracts from templates using confirmed employee data.

## 2. TMC Reuse Strategy

HKR HR remains independent. Do not connect to TMC database, schema, routes, app root, file server root, or service scripts.

TMC can still be reused as a product and UI pattern library.

Reference source:

- The reference TMC platform is the mini PC web version on `T:\`.
- Use `T:\_system\app` as the only TMC source for UI/flow reference.

Reviewed TMC web files:

- `T:\_system\app\tools\site_app\templates\base.html`
- `T:\_system\app\tools\site_app\templates\intake.html`
- `T:\_system\app\tools\site_app\templates\workflow.html`
- `T:\_system\app\tools\site_app\templates\reports.html`
- `T:\_system\app\tools\site_app\static\site.css`
- `T:\_system\app\tools\site_app\i18n.py`
- `T:\_system\app\tools\site_app\app.py`
- `T:\_system\app\tools\lib\document_intake_store.py`
- `T:\_system\app\tools\lib\intake_preview_engine.py`

Browser-verified TMC pages:

- `http://hkriver.tail73281d.ts.net:8879/intake`
- `http://hkriver.tail73281d.ts.net:8879/reports`

Key browser-observed layout facts:

- Document intake is a three-zone workbench, not a simple two-column page:
  - Left rail: upload panel and recent batch list.
  - Middle stage: PDF/Excel preview with document viewer controls.
  - Right review panel: current file summary, status, existing-file warning, field correction, side-by-side current-vs-existing comparison, and import action.
- Report center uses:
  - Left module navigation.
  - Right-side report condition cards.
  - Segmented controls.
  - Checkbox grids.
  - Clear export buttons.
  - Separate document package export cards.

Do not use the TMC attendance UI as an HKR reference. The TMC attendance module is not a suitable model for HKR HR.

Reusable TMC concepts:

- Left-side upload area and recent batch list.
- One batch contains many files.
- One active review card at a time.
- Three-zone PDF/Excel review workspace: batch rail, document preview stage, review/confirmation panel.
- Status chips such as ready, needs review, imported, existing.
- Existing-file/value warning before import.
- Side-by-side comparison panels.
- Current file value vs existing system value.
- Previous / next review navigation.
- Dirty-state detection for manually corrected values.
- Import confirmation modal, especially when replacing existing data.
- Responsive behavior: desktop side-by-side, narrow screens stacked.
- Top system tabs plus module side navigation, as seen in `base.html`.
- Three-language UI switch using language options and translation keys.
- Report center condition cards, checkbox grids, segmented controls, preview counts, and explicit export actions.
- Document/package export cards from the report center.

Things not to reuse directly:

- TMC WO/claim/commercial document types.
- TMC Master.xlsx writeback logic.
- TMC workflow snapshot logic.
- TMC portal integration.
- TMC filesystem roots.
- TMC permission names.
- TMC attendance worker database or exact workforce tables.
- TMC attendance UI and attendance workflow.

HKR adaptation:

- `WO No` becomes employee identity / employee match.
- TMC `action` becomes HR document type: three treasures, Staff Record, signed contract, attendance PDF, change evidence, identity document, bank document.
- TMC existing target warning becomes existing employee document/value warning.
- TMC import-to-Master becomes import-to-HKR-PostgreSQL after HR confirmation.
- TMC batch review becomes HR document import batch review.
- TMC report center becomes HKR Export Center with HR/payroll/document groups.

## 3. Navigation

First version navigation should be small and human:

- Dashboard
- Employee Master
- New Employee
- Document Intake
- Attendance / Payroll
- Export Center

Remove:

- Raw `DB 管理` navigation.
- Existing rushed/test `/admin/db` page.
- Any old test-only screens that do not fit the redesigned workflow.

Login should land on Dashboard.

## 4. Data Model Draft

This is a logical schema draft. Exact SQLAlchemy model names can be refined during implementation, but these are the required concepts.

### 4.1 Users And Audit

`users`

- id
- username
- password_hash
- role: admin / hr
- active
- created_at

`audit_logs`

- id
- user_id
- action
- entity_type
- entity_id
- before_json
- after_json
- detail
- created_at

Audit must cover salary changes, project changes, position changes, employee type changes, import confirmation, value replacement, document upload, document void/replacement, contract generation, attendance confirmation, payroll export, and employee data export.

### 4.2 Reference Lists

`reference_lists`

- id
- code, for example `project`, `department`, `position`, `employer`, `visa_category`, `certificate_type`, `employee_type`
- label
- active

`reference_values`

- id
- list_id
- code
- display_name
- sort_order
- active
- remarks
- created_at
- updated_at

Reference values should be editable. If a value is renamed, employee screens show the new name because employees reference the value id rather than copied text where practical.

Initial values should be imported or pre-read from:

- `瑞港集团员工档案月度更新（截至26年4月） - 试(1).xlsx`
- Its employee type/numbering sheets.
- Its employee Visa sheet.
- Existing local payroll and staff record samples.

### 4.3 Employees

`employees`

- id
- employee_no
- status: active / departed
- employee_type_id
- chinese_name
- english_name
- gender
- date_of_birth
- mobile_region_code
- mobile_number
- email
- residential_address
- id_region
- id_type
- id_number
- hkid_no
- mainland_id_no
- macau_id_no
- passport_no
- exit_entry_permit_no
- bank_name
- bank_account_no
- emergency_contact_name
- emergency_contact_region_code
- emergency_contact_phone
- emergency_contact_relation
- education_level
- major
- graduation_school
- employer_id
- start_date
- visa_required
- visa_category_id
- visa_no
- visa_issue_date
- visa_expiry_date
- remarks
- created_at
- updated_at

Current project, current position, and current salary are displayed as current facts on the profile. Internally they should come from the latest effective employment/salary history record.

`employee_qualifications`

- id
- employee_id
- qualification_name
- certificate_no
- issue_date
- expiry_date
- remarks

### 4.4 Employment And Salary History

`employee_employment_events`

- id
- employee_id
- effective_date
- event_type: salary / project / position / employee_type / combined
- project_id
- department_id
- position_id
- employee_type_id
- salary_basis: monthly / daily
- salary_currency
- salary_amount
- old_values_json
- new_values_json
- remarks
- evidence_document_id, nullable
- evidence_missing
- created_by
- created_at

Rules:

- One adjustment can change project, position, salary, and employee type together.
- Effective date is mandatory.
- Evidence attachment is optional at save time, but missing evidence must show a warning.
- Contract is one possible evidence source, not the only source.
- Existing manually confirmed values must not be silently overwritten by OCR.

### 4.5 Documents

`employee_documents`

- id
- employee_id
- category: three_treasures / staff_record / signed_contract / identity / bank / change_evidence / attendance_pdf / other
- document_type
- original_filename
- stored_path
- file_ext
- file_size
- status: active / voided / replaced
- document_date
- effective_month, for attendance PDFs
- contract_signing_date, nullable
- contract_effective_date, nullable
- replacement_reason
- replaced_by_document_id
- uploaded_by
- uploaded_at
- remarks

Document actions:

- Preview.
- Download.
- Upload new version.
- Mark replaced.
- Mark voided.
- Attach as evidence to an adjustment.

### 4.6 Certificates And Visa

`employee_certificates`

- id
- employee_id
- certificate_type_id
- certificate_no
- valid_from
- issue_date
- expiry_date
- document_id
- remarks

Safety card and construction worker registration should support valid-from and valid-to where available.

Visa data may live on `employees` for the current simple version, but a later `employee_visas` table is cleaner if one employee can have multiple visa/work permit records.

### 4.7 Document Intake

`hr_intake_batches`

- id
- batch_no
- source: document_intake / new_employee_documents / attendance
- default_year_month
- status: draft / in_review / completed / cancelled
- created_by
- created_at
- notes

`hr_intake_items`

- id
- batch_id
- document_id, nullable until final attachment copy
- original_filename
- stored_path
- document_type
- detected_employee_name
- matched_employee_id
- match_status: matched / needs_manual_match / new_employee
- status: needs_review / reviewed / imported / skipped
- raw_ocr_text, internal diagnostic only
- extracted_json
- field_sources_json
- conflicts_json
- warnings_json
- reviewed_by
- reviewed_at
- imported_at

`hr_intake_field_decisions`

- id
- intake_item_id
- field_name
- existing_value
- imported_value
- chosen_source: existing / imported / manual
- manual_value
- final_value
- confidence
- remarks

This table supports the side-by-side comparison and makes the import auditable.

### 4.8 Attendance

`attendance_monthly_summaries`

- id
- employee_id
- year_month
- project_id
- working_days
- ot_hours
- sunday_holiday_days
- document_id
- status: entered / missing
- confirmed_by
- confirmed_at
- source_intake_item_id
- remarks

First version does not store daily detail.

### 4.9 Payroll

`payroll_export_logs`

- id
- year_month
- filter_json
- row_count
- warning_json
- output_path
- exported_by
- exported_at

Payroll result rows do not need long-lived status in the first version. Payroll preview/export should calculate live from:

- employee master data
- employment/salary history
- confirmed attendance monthly summaries

## 5. Employee Numbering

Employee number prefixes:

- HKR
- HKRD
- TE
- ASMTP
- BV
- LD
- PRO
- MCR
- OTHER

System behavior:

- Generate next available number after employee type is selected.
- Allow admin/authorized manual override.
- If employee is created as OTHER and later changed to a known type, the system may generate a new number after explicit confirmation.
- Departed status does not change employee number.

## 6. Page Designs

### 6.1 Dashboard

Purpose: first page for HR and boss-level overview.

Top metric cards:

- Active employees.
- Current month estimated payroll.
- Certificate / visa expiry warnings.

Reminder area:

- Missing Staff Record.
- Missing signed contract.
- Missing change evidence.
- Pending document imports.
- Attendance not entered for selected month.

Interactions:

- Clicking a warning count opens Employee Master with matching filters.
- Certificate expiry card opens employees and certificate detail rows.
- Month selector defaults to previous month where attendance/payroll is involved.

### 6.2 Employee Master

Purpose: human-readable HR master sheet, not DB admin.

Default columns:

- Employee no.
- Status.
- Employee type.
- Chinese name.
- English name.
- Mobile.
- ID summary.
- Current project.
- Current position.
- Current salary.
- Start date.
- Missing document warnings.
- Certificate/visa expiry warnings.

Behavior:

- Click row to open employee detail.
- Filters for status, employee type, project, position, document warning, certificate warning, attendance status.
- Batch edit can come later for low-risk fields; first version focuses on detail edits.

### 6.3 Employee Detail

Top profile card:

- Name.
- Employee number.
- Status.
- Employee type.
- Current project.
- Current position.
- Salary basis and amount.
- Warning lights.
- `Adjust` button next to profile facts.

Sections:

- Basic information.
- Documents.
- Current employment / salary.
- Employment / salary history.
- Certificates / visa.
- Attendance and payroll.
- Audit / operation history.

Document section:

- Category cards.
- Timeline.
- Preview / upload new version / replace / void / download.
- Replacement reason required.

Adjustment panel:

- Effective date.
- Project.
- Department.
- Position.
- Employee type.
- Salary basis.
- Currency.
- Amount.
- Remarks.
- Evidence attachment optional.
- Missing evidence warning if no attachment.

### 6.4 New Employee

One page with two sub-options:

1. Manual create.
2. Create from documents.

Manual create:

- Single form.
- Minimum required: Chinese or English name + employee type.
- No file upload.
- Status defaults to active.

Create from documents:

- Reuse TMC intake layout.
- Left rail: upload and recent source batches.
- Middle stage: PDF/image preview.
- Right panel: OCR prefilled fields, existing system values, comparison, and confirmation.
- HR chooses existing/imported/manual values.
- Confirm import creates or updates employee after review.

### 6.5 Document Intake

Single entry for scanned/OCR files:

- Three treasures.
- Staff Record.
- Signed contract.
- Signed attendance PDF.
- Identity document.
- Bank document.
- Change evidence.

First version flow:

1. Upload one or multiple files.
2. Select document type or allow assisted detection where reliable.
3. OCR each file with Tesseract.
4. Show file preview in the middle document stage.
5. Show extracted fields and existing database values in the right review panel.
6. Match existing employee or mark as new employee.
7. HR chooses existing/imported/manual values.
8. HR confirms values.
9. System imports confirmed values and stores the file.

No re-OCR workflow is required in the first version. If OCR fails, fields remain blank and HR manually fills them.

### 6.6 Attendance / Payroll

First screen:

- Year/month selector, default previous month.
- Project-grouped employee list.
- Attendance status: entered / missing.
- Upload attendance PDFs through Document Intake.
- Confirm monthly summary per employee.

Do not reference or copy the TMC attendance interface. HKR attendance is a different workflow.

HKR attendance source of truth:

- Each employee has one signed attendance PDF per month.
- HR uploads a batch of signed attendance PDFs.
- The upload batch is handled through Document Intake.
- HR selects the attendance year/month when uploading; this selected month is the batch default and has priority over OCR/file content.
- Tesseract OCR tries to read employee name, project, working days, OT hours, and Sunday/holiday days.
- The middle stage shows the PDF preview.
- The right review panel shows OCR fields and employee matching.
- HR manually selects/corrects the employee if OCR matching is uncertain.
- HR confirms one PDF/employee/month summary at a time.
- Confirmed summaries write to `attendance_monthly_summaries`.
- The signed PDF is stored as an employee attendance attachment.

Attendance / Payroll page should therefore show:

- Year/month selector, default previous month.
- Project-grouped employee rows for the selected month.
- Employee name, employee no, type, project, position, salary basis.
- Attendance status: entered / missing.
- Confirmed working days.
- Confirmed OT hours.
- Confirmed Sunday/holiday days.
- PDF preview/open action when entered.
- Warning lights for missing salary, missing attendance, missing evidence, missing contract, and missing bank information.

Attendance confirmation fields:

- Employee.
- Month.
- Project.
- Working days.
- OT hours.
- Sunday / holiday days.
- PDF preview.

Payroll page:

- Filters: year/month, project, employee type, employee, status.
- Always-visible calculation rules panel.
- Preview table.
- Blocking errors:
  - missing attendance
  - missing salary
- Non-blocking warnings:
  - missing change evidence
  - missing bank information
  - missing contract
- User must confirm warnings before export.
- Export one workbook similar to `Payroll PC AD014`.

Observed from `Payroll PC AD014 - 202605(2).xlsx`:

- Base monthly amount formula pattern: `monthly_rate / total_days * working_days`.
- OT rate pattern in sample: `monthly_rate / 30 / 9 * 1.5`.
- OT amount pattern: `ot_rate * ot_hours`.
- Sunday/holiday daily rate pattern: `monthly_rate / 30`.
- Workbook also contains MPF-like deduction formulas and total-pay formulas, so implementation must preserve a visible, auditable rule block before payroll export is finalized.

### 6.7 Export Center

The Export Center includes data exports and document/package exports.

Borrow the TMC report center interaction model:

- Left module navigation by export purpose.
- Right condition cards.
- Checkbox grids for scope selection.
- Segmented controls for mutually exclusive modes.
- Preview count before export where practical.
- Explicit export buttons.
- Separate document package cards for attachment bundles.

Group 1: Management Overview

- Project headcount.
- Current month estimated payroll.
- Payroll summary by project/month.

Group 2: HR Records

- Employee master data.
- Missing document list.
- Certificate/visa expiry list.
- Document checklist.
- Employee attachment package.

Group 3: Payroll & Attendance

- Payroll workbook.
- Attendance entered/missing list.
- Monthly attendance summary.
- Attendance PDF package.

The page should explain each group in Traditional Chinese, Simplified Chinese, and English.

## 7. OCR Rules

OCR engine:

- Tesseract for all supported documents.
- PDF/image conversion where needed.
- OCR output is not business truth.
- OCR is only used to prefill review fields.

Three treasures should prefill:

- Chinese/English name.
- Identity number.
- Gender.
- Date of birth.
- Safety card number and validity.
- Construction worker registration number and validity.

Staff Record should prefill:

- Names.
- Phone region code and number.
- Residential address.
- ID data.
- Bank.
- Emergency contact.
- Education.
- Major.
- Graduation school.
- Qualifications.
- Start date.

Signed contract should prefill:

- Names.
- Contract signing date.
- Contract effective date.
- Employer.
- Project.
- Position.
- Salary basis.
- Currency.
- Amount.

Attendance PDF should prefill:

- Employee name.
- Month, but selected upload month has priority.
- Project.
- Working days.
- OT hours.
- Sunday/holiday days.

## 8. Missing Document And Warning Rules

Required documents:

- HKR and HKRD: three treasures, Staff Record, signed contract.
- Other employee types: Staff Record, signed contract.

Warnings:

- Missing Staff Record.
- Missing signed contract.
- Missing three treasures where required.
- Missing change evidence.
- Certificate expiring soon.
- Visa/work permit expiring soon.
- Attendance missing for selected month.

Warning style should follow the TMC requirement-light idea: clear, filterable red/yellow indicators.

## 9. Permissions

First version roles:

- admin
- hr

Suggested split:

- HR can create/edit employees, upload/import documents, confirm attendance, generate contracts, and export normal HR/payroll reports.
- Admin can manage users, reset data during implementation, edit reference lists, override employee numbers, and perform maintenance-only actions.

No raw SQL/admin DB console in the normal app.

## 10. Multilingual UI

Supported UI languages:

- Traditional Chinese.
- Simplified Chinese.
- English.

Only interface labels are translated. User-entered values such as project names, positions, employer names, document names, and remarks stay as originally recorded.

## 11. Delete / Reset Plan

After explicit approval:

- Remove old `/admin/db` route and template.
- Remove old DB admin navigation.
- Remove or replace the old rushed intake UI.
- Remove or replace the old rushed export center UI.
- Rebuild employee pages around the new employee-centered information architecture.
- Reset existing test database data if the user confirms again at implementation time.
- Do not require a backup for the current test-only dataset, per user decision.
- Do not delete production business attachment folders without a separate explicit confirmation at the time of deletion.

## 12. Implementation Phases

The target design is complete, but implementation should still be checkpointed so the user can review real screens.

### Phase 0: Approval And Baseline

- Wait for explicit user approval of this plan.
- Inspect current code paths again before editing.
- Confirm whether to drop/recreate current test tables.
- Confirm source workbook/sample file paths.

### Phase 1: Foundation

- Redesign models and schema.
- Add reference-list system.
- Add employee numbering service.
- Add multilingual label structure.
- Replace main navigation.
- Remove `/admin/db`.
- Add new Dashboard route as home.

### Phase 2: Employee Core

- Employee Master table.
- Employee Detail profile card.
- Basic information edit.
- Documents category cards and timeline.
- Manual New Employee page.
- Adjustment workflow for project/position/salary/type.
- Audit logging for edits.

### Phase 3: Document Intake

- Adapt TMC intake layout and behavior.
- Build HKR intake batch/item models.
- Implement Tesseract OCR pipelines for three treasures, Staff Record, signed contract, and attendance PDF.
- Build side-by-side comparison.
- Implement employee matching and manual selection.
- Import confirmed values only.
- Store documents under HR attachment root.

### Phase 4: Attendance And Payroll

- Attendance month/project view.
- Attendance PDF monthly summary confirmation.
- Payroll preview.
- Visible calculation rules panel.
- Blocking/warning behavior.
- Payroll workbook export similar to `Payroll PC AD014`.
- Management payroll summary.

### Phase 5: Export Center And Deployment

- Management overview exports.
- HR records exports.
- Payroll/attendance exports.
- Document/package exports.
- Local validation.
- Deploy to `R:\_system\app`.
- User restarts mini PC service.
- Verify fixed URL after restart.

## 13. Validation Plan

Local checks:

- Python compile for app, config, models, routes, tools, scripts.
- Flask test client smoke tests for login, dashboard, employee master, document intake, employee import, attendance confirmation, payroll preview, exports.
- UI browser check for desktop and narrow screen.

Sample files:

- Three treasures samples under `C:\Projects\02.HKR_HR`.
- Staff Record PDFs under `C:\Projects\02.HKR_HR\Staff record`.
- Contract PDFs under `C:\Projects\02.HKR_HR\Contract`.
- Payroll reference workbook `C:\Projects\02.HKR_HR\Payroll PC AD014 - 202605(2).xlsx`.
- Employee archive workbook `瑞港集团员工档案月度更新（截至26年4月） - 试(1).xlsx` if present/available.

Production deployment:

- Deploy source to `R:\_system\app`.
- Separate "deployed" from "restarted".
- User restarts on mini PC.
- Verify URL after restart: `http://192.168.128.70:5000/login`.

## 14. Open Questions

These can be confirmed during or before implementation:

- Exact certificate/visa expiry thresholds, for example 30/60/90 days.
- Exact admin vs HR permission split.
- Exact employee type display labels in three languages.
- Whether employee number regeneration after type change must show a dedicated confirmation modal.
- Whether missing salary evidence remains warning-only or should block payroll later.
- Whether MPF/deductions in `Payroll PC AD014` should be included in first payroll calculation or left as template/formula-only fields.
- Final OT rules for daily workers.

## 15. Approval Gate

Do not begin implementation until the user says to proceed.

Suggested approval wording:

```text
我批准 HR_REDESIGN_PLAN.md，請開始第一階段實作。
```
