# ADR-0021: Daily Sunday Attendance And Guided Four-Part Prefill

- Status: Accepted
- Date: 2026-08-20
- Clarifies: [ADR-0009](0009-manual-ecall-payroll-rule.md), [ADR-0011](0011-four-part-attendance-payroll-reconciliation.md), [ADR-0020](0020-work-calendar-and-effective-dated-monthly-pay-method.md)
- Superseded in part by: [ADR-0022](0022-daily-prefill-and-official-holiday-import.md)

## Context

Daily workers are paid only when they actually work, except for the company's separate statutory-holiday entitlement from employment start. The prior combined Sunday/statutory-holiday entry made Sunday look like an automatically paid or compensatory rest day and allowed HR to place the same Sunday work in either ordinary attendance or the extra-work field. HR also had to build several four-part attendance values from zero even when the effective workweek and regional Work Calendar provided a useful review baseline.

Large E-CALL equals one applicable daily rate, but it describes an alternative way to pay the same call-out and must not duplicate a daily worker's ordinary attendance day. Ordinary E-CALL is a separate HKD 400 event and may occur after a completed shift. The attendance summary stores counts rather than event-level E-CALL dates, so the system cannot safely infer whether two entries describe the same event.

## Decision

- A daily worker's ordinary actual attendance includes every non-statutory-holiday date actually worked, including Sunday. An unworked Sunday is unpaid.
- The daily-worker Payroll/Comp Leave field and date picker contain statutory holidays only. Working a statutory holiday adds another one daily rate under Payroll or adds equal Comp Leave without work pay; the automatic base statutory-holiday entitlement remains separate.
- Large and ordinary E-CALL counts remain manually entered from the attendance PDF. Permanent field guidance tells HR not to enter the same daily work event as both one attendance day and one Large E-CALL. No automatic E-CALL mutual-exclusion rule is added without event dates.
- When a four-part segment has no saved rows, the attendance page creates a review baseline from effective assignment, Payroll category, monthly pay method, workweek, selected year/month and regional Work Calendar. OT and E-CALL remain zero.
- Daily-worker baselines count all non-statutory-holiday calendar dates, including Sundays. They are visibly labelled as unconfirmed and HR must remove rest and non-work days.
- Standard Monthly and OFFICE forecasts follow the effective 5/5.5/6-day workweek. Attendance-day-prorated monthly exceptions remain zero by default.
- Previous-tail actual and original-forecast segments first reuse the prior month's saved current-tail forecast; when none exists, the system derives a clearly labelled calendar baseline.

## Consequences

- HR can start from a consistent, explainable baseline while the signed attendance PDF remains the authority for actual attendance.
- Daily Sunday work appears in ordinary paid attendance and cannot generate Comp Leave through the statutory-holiday picker.
- Daily statutory-holiday pay remains one automatic entitlement day plus, when applicable, one work-pay day or Comp Leave.
- The UI must keep Payroll-group, pay-method, workweek, Sunday dates and statutory-holiday dates visible in the selected-month banner and show rule-specific guidance beside the affected fields.
- Existing Payroll snapshots remain historical evidence. Any legacy daily Sunday entry in the former combined field must be reviewed before correction rather than silently rewritten.
