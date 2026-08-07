# ADR-0002: Single Employee-Create Flow

- Status: Accepted
- Date: 2026-07-24

## Context

An earlier design offered “manual create” and “create from documents” as parallel starts. That split made document intake a second onboarding system and could create duplicate or partially disconnected employee records.

## Decision

Use one onboarding path:

1. Create the employee with Chinese or English name plus employee type.
2. Open the new employee profile.
3. Complete data manually or import 三寶, Staff Record, signed contract, and other documents into that employee.

Document intake may match and update existing employees, but it is not a separate employee-creation entry.

## Consequences

- Every document and correction has an employee anchor from the start.
- The employee profile becomes the continuation point for all onboarding work.
- The legacy `/employees/new` chooser, `/employees/from-documents` handoff, and intake-created employee behavior are implementation gaps until code is aligned.
- Archived redesign documents that describe two start modes are historical evidence only.
