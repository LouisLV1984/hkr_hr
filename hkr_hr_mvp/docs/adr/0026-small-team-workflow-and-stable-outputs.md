# ADR-0026: Small-Team Monthly Workflow And Stable Outputs

- Status: Accepted; the manual Payroll adjustment entry is superseded by [ADR-0027](0027-dated-attendance-corrections.md).
- Date: 2026-11-04
- Decision owner: Louis, authorizing all four audit recommendation sections for the approximately three-operator internal system.

The navigation and default landing pages are updated by [ADR-0029](0029-employee-workbench-and-task-pages.md).

## Context

The system is internal and has approximately three operators. Repeated entry, lost form values, unclear export eligibility and mutable historical output create more operational cost than an additional approval hierarchy would solve.

## Decision

- Keep the existing single employee creation flow. Inside that profile, one initial setup form writes missing employment, assignment, salary, bank and MPF records with one effective date and one transaction. Existing records use their original correction owners.
- Share the working month and payroll entity across employee, attendance, monthly Payroll, MPF, departure and actual salary-record navigation. Default attendance to missing submissions; default Payroll to exceptions when any exist; default injury overview to cases requiring attention.
- Show current-month operational issues before optional attachment completeness. Reference rules, account breakdowns and project summaries can be expanded when needed.
- Reuse export eligibility for readiness and selection. “All ready” excludes missing-source and review-blocked employees; explicitly selected invalid employees must be corrected before that selection exports. MPF and final-payment scopes remain their own reports with their displayed requirements.
- Upload attendance one PDF at a time into one batch with a shared default month. Retain successful files and retry failed ones. Duplicate-file confirmation and validation errors preserve the current form.
- Enter exceptional work dates once and derive their day total. Salary changes inside a period require date-range attendance allocations for that affected period only. Never average calendar rates against undated actual attendance. Calendar-generated forecast allocation uses known dates; old aggregate actuals require the operator to supply the split.
- A contract draft reads assignment and salary on its effective date, preserves zero terms, owns a unique output path and does not modify formal employment terms.
- New Payroll snapshots freeze identifying display facts and project names with their amounts. Downloading an original snapshot does not recalculate current source facts. Changes create a new calculation. Old snapshots that never captured identity facts cannot reconstruct them; keep an explicit legacy limitation.
- Actual salary records may prefill blank rows from saved Payroll but remain unsaved until HR reviews and saves them. Payroll generation does not establish payment.
- Show leave available at a selected date after all registered bookings, excluding expired or future-year balances, plus next expiry and a new-request allocation preview. Keep the legacy annual-leave card visible. Preserve the existing allocation order: compensatory leave, pre-2024 leave, then earliest-expiring valid annual leave; no separate manual legacy split in ordinary leave entry.
- Runtime startup and dependency repair use a local wheelhouse. Build that package on a connected development machine matching production Python/Windows. Working calendars can be maintained and exchanged by local CSV; daily payroll calculations never fetch online calendars.
- Add no new login, approval, security or compliance stages.

## Superseded scope

- [ADR-0013](0013-task-oriented-navigation-and-data-preservation.md): historical navigation grouping and universal All/blank defaults. Employee/attachment exports are under Data Settings & Export; pending work can be the default.
- [ADR-0014](0014-annual-leave-buckets-and-final-payment.md): manually entered legacy leave allocation. Bucket ownership, expiry, precision and separate final payment remain.
- [ADR-0008](0008-segmented-attendance-payroll-snapshots.md): supplemented with dated attendance allocations and frozen identifying output facts.
- [ADR-0022](0022-daily-prefill-and-official-holiday-import.md): online import is optional maintenance; offline CSV and wheelhouse are the normal disconnected route.

## Consequences

The common path stays short. Additional inputs appear only when a real salary change makes undated totals ambiguous. This does not infer missing historical data, change signed contracts or treat an export as payment.
