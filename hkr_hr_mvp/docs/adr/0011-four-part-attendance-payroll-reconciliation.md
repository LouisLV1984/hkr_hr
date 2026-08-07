# ADR-0011: Four-Part Attendance And Payroll Reconciliation

- Status: Accepted
- Date: 2026-07-30
- Supersedes: [ADR-0008](0008-segmented-attendance-payroll-snapshots.md) where it stores only the two actual attendance periods

## Context

Payroll is prepared before the current month ends. HR therefore pays the known current-month attendance plus a forecast for the remaining days, then corrects the prior month's forecast when the next signed PDF arrives. The original forecast must remain visible and editable so HR can explain every overpayment or underpayment.

## Decision

- Keep one signed attendance PDF and one monthly summary per employee.
- Store project segments for:
  - current month days 1-20 actual;
  - current month days 21 to month end forecast;
  - previous month days 21 to month end actual;
  - previous month days 21 to month end original forecast.
- Payroll is current actual + current forecast + previous actual - previous forecast.
- Current forecast is derived from effective-dated assignment and salary records, then may be corrected by HR.
- Previous forecast is copied from the prior month's saved current forecast, then may be corrected by HR.
- Forecast periods do not assume OT or E-CALL.
- Regular MPF uses the reconciled relevant income. Construction casual-worker MPF uses the MPFA daily relevant-income contribution scale over the same four-part reconciliation.

## Consequences

- Payroll snapshots preserve all four day totals and amounts used for reconciliation.
- Overpayment and underpayment are explainable without reopening an old exported workbook.
- The signed PDF remains the source for actual attendance; V1 still does not OCR attendance.
- Existing attendance summaries remain readable. Missing forecast segments fall back to the derived forecast until HR saves the record again.
