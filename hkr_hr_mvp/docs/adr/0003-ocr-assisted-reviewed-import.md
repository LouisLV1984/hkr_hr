# ADR-0003: OCR-Assisted Reviewed Import

- Status: Superseded for V1 by [ADR-0007](0007-profile-first-manual-document-capture.md)
- Date: 2026-07-24

## Context

HR source documents may be scanned, multilingual, or handwritten. OCR can accelerate entry, but its output is not reliable enough to become employee truth without review.

## Decision

- OCR proposes values and source/confidence information.
- The review UI shows the source document, existing system value, imported value, and manual correction.
- HR confirmation is required before imported values affect employee, certificate, employment, or attendance records.
- Existing manually confirmed data is never silently overwritten.
- OCR failure does not block preview, manual entry, reviewed import, or archival.

## Consequences

- Manual completion remains a first-class path.
- Intake decisions and resulting changes must be auditable.
- Re-OCR and fully automatic employee creation are not required core behavior.
- Historical OCR material is evidence only; current intake vocabulary is in [CONTEXT.md](../../../CONTEXT.md).
