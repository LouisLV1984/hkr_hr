# ADR-0008: Segmented Attendance And Payroll Snapshots

- Status: Accepted
- Date: 2026-07-27
- Supersedes: [ADR-0004](0004-monthly-attendance-live-payroll.md) where attendance grain and live-only payroll conflict

Current workflow amendments: [ADR-0026](0026-small-team-workflow-and-stable-outputs.md). Historical wording below is superseded only in the scopes explicitly listed there.

## Context

HR receives one signed attendance PDF per employee for a payroll month. Payroll uses actual attendance for the current month from day 1 to day 20, actual attendance for the previous month from day 21 to month end, and a forecast for the current month after day 20. An employee can also transfer project during the month, so one employee result may need more than one project allocation line.

## Decision

- Keep one attendance summary and one active source PDF per employee and payroll month.
- Store attendance details as project segments for:
  - current month days 1 to 20 actual;
  - previous month days 21 to month end actual.
- Enter attendance manually while previewing the signed PDF. V1 does not OCR attendance.
- Record a project transfer as an effective-dated assignment change. Attendance can then contain one line per project.
- Count expected, received, and missing attendance by employee rather than by project line.
- Calculate one employee payroll result with one or more project allocation lines.
- Store payroll calculation snapshots and rule inputs, but regenerate XLSX or ZIP files from templates when downloaded.
- Continue to support `site_daily`, `site_monthly`, and `management`.

## Consequences

- The old single-project `attendance_monthly_summaries` shape is replaced by summary and segment tables.
- Correcting source facts creates a new payroll calculation snapshot rather than silently changing an already-reviewed result.
- Payroll can show employee totals while exports preserve project-level detail.
- Missing attendance or salary blocks export. Other missing evidence remains a visible warning.
