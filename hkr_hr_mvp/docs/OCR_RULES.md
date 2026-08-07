# HKR HR OCR Status

Updated: 2026-07-27

OCR is outside the V1 operating flow. The accepted decision is
[ADR-0007](adr/0007-profile-first-manual-document-capture.md), which
supersedes [ADR-0003](adr/0003-ocr-assisted-reviewed-import.md) for V1.

## V1 Flow

1. HR creates one minimal employee profile and permanent employee number.
2. HR continues all onboarding work from that employee profile.
3. Employee documents are uploaded, previewed, classified, archived, replaced,
   voided, downloaded, and exported without OCR.
4. HR enters or corrects structured facts manually while viewing the source
   document.
5. Attendance uses one signed PDF per employee and Payroll month. HR previews
   the PDF and enters the confirmed attendance figures manually.

OCR failure therefore cannot block any V1 workflow because no V1 workflow
depends on OCR.

## Deferred Scope

OCR may return in a later version only after a measured HR task shows that it
reduces work without recreating a second employee-onboarding path. Any future
OCR output must remain a suggestion, require HR review, and never silently
overwrite confirmed employee data.
