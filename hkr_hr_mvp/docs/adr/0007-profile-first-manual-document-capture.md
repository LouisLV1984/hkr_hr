# ADR-0007: Profile-First Manual Document Capture

- Status: Accepted
- Date: 2026-07-27
- Supersedes: [ADR-0003](0003-ocr-assisted-reviewed-import.md) for the V1 operating flow

## Context

OCR review became a second onboarding workflow and drew attention away from the actual HR job: create one employee record, preserve source documents, complete structured data, and retrieve those records later. The available source files are inconsistent enough that manual review remains necessary even when OCR returns values.

## Decision

- Create one minimal employee record before collecting employee documents.
- Continue all onboarding work from that employee profile.
- Upload, preview, classify, archive, replace, void, download, and export employee documents without requiring OCR.
- Enter or correct structured employee facts manually while viewing the source document.
- Do not let document upload create another employee record.
- Keep document status as `active`, `replaced`, or `voided`, and retain the replacement history.
- Treat OCR as outside V1. It may be reconsidered only when a measured HR task justifies it.

## Consequences

- `HrIntakeBatch`, OCR field decisions, re-OCR, document-name matching, and create-from-document onboarding leave the active V1 flow.
- Three Treasures, Staff Record, bank proof, identity, VISA, qualification, contract, and change evidence remain first-class document categories.
- The employee profile is the only continuation point for employee data and documents.
- Manual data entry must remain usable even when every extracted field is blank.
