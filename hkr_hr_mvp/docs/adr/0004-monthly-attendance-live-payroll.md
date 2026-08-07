# ADR-0004: Monthly Attendance And Live Payroll

- Status: Accepted
- Date: 2026-07-24

## Context

The available HR source is a signed monthly attendance PDF per employee. A daily-detail model and long-lived payroll workflow would add state without a confirmed operating need.

## Decision

- Store one confirmed attendance summary per employee and month in `attendance_monthly_summaries`.
- Keep the signed PDF as the source employee document.
- Calculate payroll preview/export live from employee facts, effective salary history, and monthly attendance.
- Do not create a long-lived status for each payroll result.
- Support three payroll groups: `site_daily`, `site_monthly`, and `management`.
- Export one XLSX for one group or a ZIP of three XLSX files for all groups.
- Use daily-worker OT divisor 10 for TMC046/HA and 9 for other daily projects.

## Consequences

- Correcting confirmed source data changes the next payroll calculation.
- Missing attendance, salary, or bank-change confirmation blocks export.
- Other missing documents/evidence remain acknowledgement warnings.
- Detailed daily OCR and complex legal/statutory automation remain outside the current core.
