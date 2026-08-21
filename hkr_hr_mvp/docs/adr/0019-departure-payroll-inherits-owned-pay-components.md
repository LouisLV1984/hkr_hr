# ADR-0019: Departure Payroll Inherits Owned Pay Components

- Status: Accepted
- Date: 2026-08-18

## Context

A departing employee is excluded from ordinary Monthly Payroll in the departure month. Fixed allowances, month-specific adjustments, substitute-shift allowance entered in Attendance, and work-injury medical reimbursement nevertheless remain payable sources owned by their respective modules. Requiring HR to re-enter them in Departure Payroll would create duplicate-entry and omission risks.

## Decision

- Use the user-facing name `Departure Payroll` (`離職 Payroll`); retain `Final Payment` in the formal English workbook template and internal identifiers.
- Carry fixed allowances effective through the last working day into Departure Payroll. Transport and meal allowance use the recorded daily rate multiplied by paid calendar days through departure. Special allowance is prorated by effective calendar days through departure over all calendar days in the month.
- Carry active month-specific Payroll adjustments and Attendance substitute-shift allowance into Departure Payroll automatically.
- Carry active work-injury medical reimbursement into net pay, but exclude it from MPF relevant income.
- Keep manual allowance and other-payment fields only for exceptional items that have no other system source, and show a permanent warning against duplicate entry.
- Require one payroll entity for formal export. Preview may show all entities.
- Keep one employee per workbook row. Employee MPF remains on that row and never creates a separate line.

## Consequences

- The departure month has one wage source without losing payments owned by other modules.
- HR corrects a source item in its owning module instead of copying the same value between pages.
- The page and exported calculation notes expose how automatic and manual components differ.
- Formal exports remain separable by payroll entity and auditable by filename.
