# ADR-0024: Unified Profile Document Intake And Owned-Record Routing

- Status: Accepted
- Date: 2026-08-28

## Context

Employee files were visible together in Contracts & Attachments, but their creation paths were inconsistent. CV and Other could be uploaded there, Staff Record lacked an obvious entry, and evidence for bank, credentials, employment, leave, work injury, and attendance could be uploaded without necessarily creating the structured record that Payroll, leave, reminders, and audit history actually use.

## Decision

Each employee profile has one visible `Upload document` gateway in Contracts & Attachments.

The gateway first asks HR to choose the document purpose:

- source documents that have their own review workflow—Three Treasures, Staff Record, signed Employment Contract, CV, and general attachments—are uploaded and reviewed there;
- evidence owned by a structured business record—bank, credentials, employment/pay, probation, leave, work injury, attendance, termination, and name change—routes HR to that record's owning module before a file is selected.

System document purposes remain fixed because they control validation, review fields, links, and downstream calculations. Only general-attachment subtypes are configurable in Data Options. Contextual shortcuts in Personal, Credentials, and Employment open the same gateway with the relevant source-document purpose already selected.

Contracts & Attachments remains the unified file library for preview, download, bundle, replacement history, and accurate purpose labels. It does not become a second editor for structured business records.

## Consequences

- Staff Record and other source documents have an obvious profile-first upload path.
- HR cannot create an orphan Payroll, leave, credential, or attendance evidence file from the generic uploader.
- General files can be classified with company-specific names without expanding system workflow code.
- Existing document category codes remain compatible; general subtypes add optional metadata rather than rewriting historical files.
- Correcting a structured record still occurs in its owning module, while replacing a standalone source or general file remains available from the file library.

## Alternatives Rejected

- A free-form category list for every document was rejected because renamed or duplicated system purposes would break routing and reporting semantics.
- Making Contracts & Attachments the only place to edit all structured records was rejected because it would duplicate domain forms and change histories.
- Keeping separate unrelated upload buttons was rejected because HR could not reliably know where a file belonged.
