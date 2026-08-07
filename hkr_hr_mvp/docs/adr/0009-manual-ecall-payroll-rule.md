# ADR-0009: Manual E-CALL Attendance And Payroll Rule

- Status: Accepted
- Date: 2026-07-29

## Context

Signed monthly attendance PDFs can mark either Large E-CALL or ordinary E-CALL in their remarks. V1 attendance remains a manual PDF-review workflow, and payroll already separates current-month days 1-20 actuals, previous-month days 21 to month end actuals, and current-month tail forecasts.

## Decision

- Record Large E-CALL count and ordinary E-CALL count on each attendance project segment.
- HR reads the PDF remarks and enters the counts manually. OCR is not required.
- Each Large E-CALL adds one applicable daily rate for that employee, project, and period.
- Each ordinary E-CALL adds HKD 400.
- Current-period E-CALL is included in current relevant income and payroll.
- Previous-tail E-CALL is included in actual prior-tail pay and therefore in overpay/underpay reconciliation.
- Current-tail forecasts assume zero E-CALL until actual attendance is received next month.
- Payroll exports use the existing current-period and previous-period Other columns as E-CALL amount columns, preserving the supplied workbook layout.

## Consequences

- A project transfer can allocate E-CALL to the correct project line.
- E-CALL is included when calculating MPF relevant income.
- Existing V1 databases receive additive columns without a destructive reset.
- Payroll snapshots preserve E-CALL counts, amounts, source periods, and the calculation rule version.
