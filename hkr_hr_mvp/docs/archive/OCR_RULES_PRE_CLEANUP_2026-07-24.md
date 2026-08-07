# Archived HKR HR OCR Rules

> Historical OCR specification preserved before the 2026-07-24 documentation cleanup. It contains obsolete document codes, table names, field names, and an unsupported XLSX fallback claim. Do not implement from this file. See the current [`OCR_RULES.md`](../OCR_RULES.md), [`../../../CONTEXT.md`](../../../CONTEXT.md), and [ADR-0003](../adr/0003-ocr-assisted-reviewed-import.md).

This document fixes the first production OCR rules for HKR HR Staff MVP.

The OCR feature must be an assistive prefill workflow. It must not write OCR results directly into the employee master record without HR review and confirmation.

Current implementation also supports `contract` and `attendance_sheet` as document types. Contract OCR may prefill employment/salary fields, but the contract file is only saved as an employee attachment after HR confirmation. Signed attendance PDFs are handled as scanned documents: PDF pages are rendered and sent through Tesseract OCR, then parsed into `attendance_records` drafts. XLSX parsing remains only as a compatibility fallback.

## Upload Workflow

On the employee OCR/import page, one row should allow these uploads:

```text
三寶 PDF / image
僱員資料登記表 PDF / image
合同 PDF / image
已簽名考勤 PDF
```

HR may upload:

```text
三寶 only
僱員資料登記表 only
both 三寶 and 僱員資料登記表
contract together with employee source files
signed attendance PDF as an attendance draft batch
```

After upload:

1. Save uploaded files as employee attachments or temporary OCR files.
2. OCR PDF/image sources independently with Tesseract.
3. Merge OCR results into a prefill form.
4. Show source labels next to prefilled fields, for example `三寶`, `Staff Record`, `Contract`, `Attendance OCR`, or `手動`.
5. HR reviews and edits the prefill form.
6. Only after HR clicks confirm, write to `employees` and `employee_certificates`.

## Source Priority

Contract priority:

```text
三寶 wins for identity and certificate fields.
Staff Record wins for contact, bank, emergency contact, and salary when present.
Contract can fill employment, start date, position, workplace, and salary only when higher-priority sources are missing.
Contract OCR never creates or updates generated_contracts.
```

## Contract OCR Fields

Contract OCR may prefill:

| Field | OCR Reliability | Rule |
|---|---|---|
| `chinese_name` / `english_name` | Medium | Prefill when clearly labelled. |
| `hkid_no` | Medium | Prefill, but 三寶 wins if present. |
| `employment_type` | Medium | Prefill when contract wording is clear. |
| `department` / `project` | Low | Use only when clearly labelled; HR must review. |
| `position` | Medium | Prefill when clearly labelled as position/trade. |
| `work_location` | Medium | Prefill when contract states workplace/site. |
| `start_date` | Medium | Prefill from commencement/effective/start date. |
| `salary_amount` / `salary_basis` | Medium | Prefill salary amount and monthly/daily basis when clear. |

The contract file itself is saved as an employee attachment after HR confirmation. OCR must not create or update `generated_contracts`; that table remains controlled by the Word contract generation workflow.

When both documents provide the same field:

```text
Identity fields: 三寶 wins by default.
Certificate fields: 三寶 wins by default.
Employment/contact/bank/salary fields: 僱員資料登記表 wins by default.
Existing manual value: do not overwrite silently.
```

If OCR conflicts with an existing database value, the UI must show both values and require HR confirmation.

## 三寶 Prefill Fields

三寶 means:

```text
身份證 / HKID / Mainland ID / Passport
建造業工人註冊證
平安卡 / Construction Industry Safety Training Certificate
```

### employees

三寶 may prefill these `employees` fields:

| Field | OCR Reliability | Rule |
|---|---|---|
| `chinese_name` | Medium | Prefill if visible; HR must confirm. |
| `english_name` | High | Prefer card text, normalize comma format such as `CHAN, Hoi Tak` to `Chan Hoi Tak`. |
| `gender` | High | Map `M/男` to male, `F/女` to female. HR confirms. |
| `date_of_birth` | High | Parse from HKID/passport if visible. |
| `hkid_no` | High | Prefer HKID card number, normalize spaces and brackets. |
| `mainland_id_no` | Medium | Prefill only when a Mainland ID card is detected. |
| `passport_no` | Medium | Prefill only when a passport is detected. |
| `position` | Low/Medium | Do not infer from card title. May prefill only from registered trade if no better source exists. |
| `remarks` | Low | May append OCR notes only after HR confirms. |

三寶 must not prefill these `employees` fields:

```text
employee_no
mobile
email
address
employment_type
department
project
work_location
start_date
status
salary_amount
salary_basis
bank_name
bank_account_no
emergency_contact_name
emergency_contact_phone
emergency_contact_relation
staff_record_received
```

### employee_certificates

三寶 should prefill `employee_certificates` records:

| Certificate | `certificate_type` | Fields |
|---|---|---|
| 建造業工人註冊證 | `construction_worker_registration` | `certificate_no`, `trade`, `issue_date`, `expiry_date`, `attachment_id`, `remarks` |
| 平安卡 / 安全訓練證明 | `safety_training_certificate` | `certificate_no`, `issue_date`, `expiry_date`, `attachment_id`, `remarks` |
| HKID / identity document | `identity_document` | `certificate_no`, `issue_date` if visible, `attachment_id`, `remarks` |

For HKID, the primary employee value remains `employees.hkid_no`; the certificate row is optional but useful for attachment/source tracking.

## 僱員資料登記表 Prefill Fields

The Staff Record is the main source for employment/contact/payroll-related fields.

### employees

僱員資料登記表 may prefill these `employees` fields:

| Field | OCR Reliability | Rule |
|---|---|---|
| `employee_no` | Medium | Prefill only if the form has a clear employee number. Otherwise leave blank or system-generate later. |
| `chinese_name` | Medium | Prefill; HR must confirm because handwriting varies. |
| `english_name` | Medium | Prefill; HR must confirm. |
| `gender` | Medium | Use only when clearly read. |
| `date_of_birth` | Medium | Use only when clearly read. |
| `mobile` | Medium | Prefill; HR must confirm. |
| `email` | Low | Prefill only if clearly printed/written. |
| `address` | Low/Medium | Prefill; HR must confirm due to handwritten Chinese. |
| `hkid_no` | Medium | Prefill, but 三寶 value wins if both exist. |
| `employment_type` | Medium | Map work type such as `日工/月工`. HR confirms. |
| `position` | Medium | Prefill from `受僱職位`; HR confirms. |
| `work_location` | Medium | Prefill from `工作地點`; HR confirms. |
| `start_date` | Medium | Prefill from `起始工作日期`; HR confirms. |
| `salary_amount` | Medium | Prefill from company-filled salary field; HR must confirm. |
| `salary_basis` | Medium | Map `/日`, `/天`, `/月`, `日工`, `月工`. HR must confirm. |
| `bank_name` | Medium | Prefill from bank/account line when distinguishable. |
| `bank_account_no` | Medium | Prefill; HR must confirm carefully. |
| `emergency_contact_name` | Low/Medium | Prefill; HR must confirm. |
| `emergency_contact_phone` | Medium | Prefill; HR must confirm. |
| `emergency_contact_relation` | Low/Medium | Prefill; HR must confirm. |
| `staff_record_received` | High | Set to true when Staff Record is uploaded and HR confirms the OCR form. |
| `remarks` | Low | Only append OCR/import notes after HR confirms. |

僱員資料登記表 must not be the normal source for:

```text
department
project
status
mainland_id_no
passport_no
contract generated status
created_at
updated_at
```

`department`, `project`, and `status` should come from HR manual entry or existing Excel import unless the company later standardizes these fields on the Staff Record.

## Manual-Only / System Fields

These fields should be manual-only or system-controlled in the first OCR version:

| Field | Rule |
|---|---|
| `department` | HR manual or Excel import. |
| `project` | HR manual or Excel import. |
| `status` | HR manual, default `在職` for new confirmed employees. |
| `employee_no` | System-generated or HR manual if Staff Record does not clearly provide it. |
| `email` | Manual unless clearly present. |
| `remarks` | Manual; OCR may suggest notes only. |
| `created_at`, `updated_at` | System-controlled. |
| `uploaded_by`, `generated_by` | System-controlled from login user. |
| `generated_contracts.*` | Created only by contract generation workflow. |
| `audit_logs.*` | Created only by application actions. |

## Confidence Labels

The OCR prefill UI should label each field:

```text
High: likely safe to prefill, still requires HR confirmation.
Medium: prefill but visibly mark for review.
Low: show as suggestion only; do not auto-place into final value unless HR selects it.
Manual: no OCR prefill.
```

Suggested first version behavior:

```text
High and Medium -> fill into editable form with source label.
Low -> show under suggestions, HR can click to apply.
Manual -> empty input for HR.
```

## Conflict Handling

Examples:

```text
三寶 hkid_no != Staff Record hkid_no
Staff Record salary != existing employee salary
OCR name != existing employee name
```

Rules:

1. Never overwrite existing database values silently.
2. Show conflict rows in the review page.
3. Default selected value follows source priority.
4. HR can choose another value or type a corrected value.
5. Save the original OCR text and source attachment path for audit/recheck.

## Data Status Rules

After HR confirms OCR/import:

```text
Only 三寶 uploaded and confirmed:
  staff_record_received = false
  completeness status can show 只有三寶

Staff Record uploaded and confirmed:
  staff_record_received = true
  completeness status can show Staff Record 已收

Contract generation:
  controlled by generated_contracts table, not OCR
```

## First Implementation Scope

First OCR implementation should support:

```text
Upload one or both source files
OCR preview
Prefill review form
Conflict display
Confirm to create/update employee
Create/update certificate records from 三寶
Save source files as attachments
Audit log for OCR review confirmation
```

Do not implement fully automatic employee creation without a review screen.
