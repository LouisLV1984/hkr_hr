# Archived HKR HR V0.1 Acceptance Checklist

> Historical incomplete release checklist dated 2026-07-13. Every checkbox was left unchecked, so this file is not proof that a release gate passed. Preserve it as planning evidence only; use current code/runtime verification and release evidence for acceptance.

Release target: `V0.1`

Release date: `2026-07-13`

This checklist is the release gate. A checkbox may be marked complete only when current code and a relevant test or browser check prove the behavior.

## Employee Editing Boundaries

- [ ] Ordinary edit only changes contact phone, email, address, bank, emergency contact, education and general remarks.
- [ ] Chinese and English names can only change through the two-reason name-change action.
- [ ] A legal/actual name change requires an attachment; a system correction does not.
- [ ] Only admin can edit an existing employee number.
- [ ] Employee type, employer, department, project, position, payroll group, start date, contract leave and salary cannot be changed through ordinary edit.
- [ ] Employment and salary changes require an effective date and create a history event.
- [ ] A changed bank account blocks payroll until HR confirms the new bank details.

## Timeline And Identity History

- [ ] Timeline entries show date and time, operator, source and a human-readable title.
- [ ] Data changes show concrete old and new values; bank and identity numbers are masked.
- [ ] Timeline covers profile edits, bank confirmation, name changes, identities, documents, intake, employment/salary, probation, annual leave, attendance, termination and rehire.
- [ ] An employee can hold multiple active identity documents and one primary identity.
- [ ] Identity supports long-term validity.
- [ ] Replacing identity details archives the old record as `replaced` and creates a new active record.
- [ ] Identity attachments may be added later.

## Document Intake

- [ ] Existing values appear only when they exist; the corrected/import value remains directly editable.
- [ ] Enter saves text corrections and dropdown selection saves immediately.
- [ ] OCR returning no fields does not block preview, manual entry, import or archive.
- [ ] Import records the source document and actual employee field changes in the employee timeline.
- [ ] Attendance PDF import records employee, month, project, working days, OT and Sunday/holiday days and archives the PDF.

## Language Coverage

- [ ] Traditional Chinese, Simplified Chinese and English switch without leaving the current page or losing query parameters.
- [ ] Page titles, field labels, placeholders, buttons, tables, empty states, warnings, flash messages, JavaScript confirmations, tooltips and payroll rules are translated.
- [ ] Derived UI states such as active/departed, probation and missing-document alerts are translated.
- [ ] Employee names, project names, position names, reference values and filenames remain unchanged data.
- [ ] Dashboard, employee list/form/detail, intake, payroll, exports, references, contracts, admin and audit pages pass browser checks in all three languages.

## Release Notes

- [ ] The top-right current version is visible and clickable to every signed-in user.
- [ ] `/updates` lists releases newest first from one structured source.
- [ ] Every release has a `YYYY-MM-DD` date.
- [ ] V0.1 notes list core features, improvements and known limitations in all three UI languages.

## Regression And Deployment

- [ ] Local `py_compile` passes for all application Python files.
- [ ] Flask smoke tests cover admin/hr permissions, employee edit boundaries, timeline differences, identity replacement, intake, attendance, payroll, contracts and exports.
- [ ] The three local QA employees remain present.
- [ ] Desktop and 390px browser layouts have no incoherent overlap or horizontal overflow.
- [ ] One-group payroll XLSX and all-groups ZIP open successfully from clean templates.
- [ ] Contract package contains editable Office and Site DOCX files.
- [ ] Code and templates are copied to `R:\_system\app` and template roots with matching hashes.
- [ ] Production database is not reset and the existing `HKR0001` / `QA-LIVE-*` employees remain present.
- [ ] Deployment is reported separately from the user's manual mini PC restart.
