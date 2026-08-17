# ADR-0016: Effective-Dated MPF Schemes And Exports

- Status: Accepted
- Date: 2026-08-12

## Context

HKR uses several MPF schemes with different employer accounts, payroll group identifiers and contribution calculations. An employee's Member Account No. belongs to the selected scheme and may change when the scheme changes. Monthly MPF amounts must reconcile with Payroll without creating a second manual calculation workflow.

## Decision

- Store MPF schemes as maintained reference records containing scheme name, employer account number, payroll group ID and calculation mode.
- Store employee MPF enrollment as an effective-dated record containing scheme, scheme-specific Member Account No., contribution mode and effective date.
- Do not ask HR for an end date. A later active record automatically closes the prior effective period.
- Show the current MPF record beside current salary. Merge assignment, salary and MPF into one effective-date ordered `Change history`; attach audit activity to its originating record instead of rendering a second parallel timeline.
- Use the employee English name as the MPF member name and the active Hong Kong identity as the masked ID value.
- Calculate MPF from the same four-part monthly Payroll result. Do not maintain a separate manually entered MPF amount.
- A Payroll-ready employee may still have missing MPF metadata. That gap blocks the MPF contribution report only; it does not block Payroll.
- Export one template-based XLSX for one scheme or a ZIP containing one XLSX for each populated scheme. Retain zero-income and exempt employees in the report.
- Display an absent payroll group ID as `N/A` in the UI but leave the template cell blank.
- Do not split one contribution month when an employee changes MPF scheme mid-month in the current core.

## Consequences

- Historical Payroll and MPF reports can retain the scheme and Member Account No. that applied at the time.
- HR corrects or withdraws a wrong MPF record using the same effective-record pattern as assignment and salary.
- MPF export eligibility is explainable without weakening ordinary Payroll eligibility.
- Additive PostgreSQL tables and Payroll snapshot columns are required; no employee-data reset is required.
