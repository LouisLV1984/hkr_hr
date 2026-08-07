# ADR-0010: Content Hash And Confirmed Document Replacement

- Status: Accepted
- Date: 2026-07-29

## Context

Employee documents and signed attendance PDFs may be uploaded again under a different filename even when their binary content is unchanged. Filename, upload date, and file size are not reliable evidence that two files are identical. Silently replacing an existing HR document would also weaken the document history and could hide an operator mistake.

## Decision

- Calculate SHA-256 from the complete file bytes and store the digest with each employee document and attendance batch item.
- Ignore filenames when deciding whether file content is identical.
- For ordinary employee documents, compare active documents only within the same employee and document category.
- For attendance PDFs, compare active documents within the same employee, attendance category, and payroll month.
- Do not compare documents across employees, categories, or attendance months.
- When identical content is detected, require HR to choose either cancel or replace anyway. Never replace silently.
- Cancelling creates no employee-document record and leaves the existing document unchanged.
- Confirming replacement creates the new active document and marks the applicable existing document as replaced.
- Calculate missing digests from accessible legacy files when they are first compared.
- Add digest columns through a backward-compatible additive migration; do not require a database reset.

## Consequences

- Renaming an unchanged file does not bypass duplicate detection.
- Shared templates or genuinely identical files belonging to different employees are not blocked.
- General document uploads use short-lived temporary storage while HR decides whether to replace.
- Attendance duplicate checks remain inside the existing employee-and-month review workflow.
- Hashing adds a small file-read cost during upload or first comparison but does not change document contents.
