# ADR-0015: Shared Readiness And Production Safety

## Status

Accepted

## Context

The Dashboard, employee profile and Payroll previously derived missing data independently. This produced inconsistent status wording and encouraged a separate task-note workflow that did not change the underlying employee facts. Production also needs recoverable data and routine web protections without adding steps to HR's normal work.

## Decision

1. One shared readiness service derives three views for an employee and selected month:
   - employee data completeness;
   - monthly attendance status;
   - Payroll blockers.
2. Employee Management is the canonical readiness matrix. It shows all filtered employees with Employee File, selected-month Attendance, and selected-month Payroll Status columns. Completed checks use green check chips; required missing or blocking checks use red chips. Each actionable item links to the employee profile or relevant operating page.
3. Work Overview presents only a compact current-month action summary and links to Employee Management with the corresponding month and action filter. It does not duplicate the full employee table.
4. Operator wording follows the source fact instead of generic `missing data` language: fields are filled/not filled, effective records are created or configured/not created or configured, documents are filed/not filed, attendance is received/not received/exempt, and Payroll is ready/not ready with a specific reason.
5. Payroll bank details and bank account proof are separate. Bank name, account number and payroll confirmation are required Payroll facts. Bank account proof remains an optional employee attachment and does not create a Dashboard warning or Payroll blocker until company policy explicitly makes it mandatory.
6. Derived missing-data conditions do not have separate progress states or notes. Correcting the source employee, document, attendance or Payroll fact removes the condition automatically.
7. Permanent employee deletion remains available only to Admin and is named `Delete employee`. It is intentionally absent from HR accounts and requires an explicit irreversible-action confirmation.
8. Production recovery uses two layers:
   - short-retention snapshots under the mini PC production storage for rapid recovery;
   - encrypted, incremental and deduplicated long-retention snapshots on the authorised laptop.
   PostgreSQL dumps, attachments and templates are covered together, and restoration is tested in an isolated target.
9. Production uses CSRF protection, login throttling, local-only post-login redirects, a required non-placeholder secret key, server-side upload validation, and friendly error pages for common HTTP failures.

## Consequences

- Employee Management status and the Dashboard action summary remain projections of business data rather than a second task database.
- Employee detail and Payroll consume the same completeness vocabulary.
- HR's normal forms and upload flow do not gain approval steps. Security controls are visible only for repeated failed logins, invalid uploads, expired sessions or errors.
- The short-retention copy on the mini PC is operational convenience, not an independent disaster-recovery copy. The laptop repository provides the independent device boundary.
- Restoring a backup must be verified; successful file creation alone is not considered recovery proof.

## Alternatives Rejected

- Keeping independent Dashboard notes and progress states: rejected because they do not update the source employee facts and create stale parallel state.
- Taking a full attachment copy every day: rejected because storage grows unnecessarily.
- Removing permanent deletion entirely: rejected because Admin still needs a controlled correction tool for erroneous employee records.
