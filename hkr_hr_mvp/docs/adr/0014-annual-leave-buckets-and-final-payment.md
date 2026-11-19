# ADR-0014: Annual Leave Buckets And Final Payment

- Status: Accepted
- Date: 2026-08-07

Company calendar-year entitlement activation and progression are defined by [ADR-0025](0025-calendar-year-advance-annual-leave.md). The bucket, expiry and Final Payment decisions below remain effective.

Current workflow amendments: [ADR-0026](0026-small-team-workflow-and-stable-outputs.md). Historical wording below is superseded only in the scopes explicitly listed there.

## Context

The company treats annual leave earned in 2023 or earlier differently from leave earned from 2024 onward. The legacy balance does not expire. A balance from 2024 onward normally expires on March 31 of the following year, unless the company approves a specific extension date. One leave period may use both sources.

Final Payment also differs from ordinary monthly Payroll. It uses actual attendance only up to the last working day, may pay unused annual leave and statutory holidays, and may include payment in lieu of notice, severance payment, or long-service payment. Ordinary month-end forecasts and prior-month reconciliation must not enter the final-month calculation.

## Decision

- Store one annual-leave balance per employee and entitlement year.
- Treat the `2023` balance row as the combined permanent bucket for 2023 and earlier.
- Give each 2024-onward balance a March 31 default expiry and an optional approved extension date.
- Allocate each leave record to one or more balance rows. Current rule: compensatory leave, 2023-and-earlier leave, then the earliest-expiring valid annual balance. The original HR-entered legacy split is superseded by ADR-0026.
- Keep leave in 0.5-day units for ordinary leave records. Final Payment prorated entitlement may use greater precision and is not rounded to a half day before conversion to money.
- Use a separate Final Payment case per employment period. It stores HR-reviewed actual attendance, leave and statutory-holiday days, wage bases, MPF offset, and other settlement inputs.
- Final Payment calculations are separate from the four-part monthly Payroll calculation.
- Split severance or long-service payment at 2025-05-01 when the service period spans that date.
- HR selects the statutory benefit type and the last-month/18-day or 12-month-average wage basis. The application calculates the resulting amount and applies the statutory annual and total caps.
- Employer mandatory MPF accrued benefits entered by HR may offset only the pre-transition portion.
- Export one workbook for a selected Payroll group or a ZIP containing all three group workbooks. Generated workbooks retain auditable Excel formulas.

## Consequences

- HR can explain exactly which annual-leave balance a leave record consumed.
- Approved extensions preserve a balance without changing the normal company expiry rule for other employees.
- Ordinary Payroll and Final Payment show different rules and do not silently share forecasts or reconciliation inputs.
- Statutory eligibility, average-wage exclusions, unused statutory-holiday days, and MPF offset values remain HR review items rather than automated legal decisions.
