# ADR-0022: Daily-worker prefill and official statutory-holiday import

- Status: Accepted
- Date: 2026-08-21
- Supersedes in part: [ADR-0021](0021-daily-sunday-attendance-and-guided-prefill.md)
- Superseded in part by: [ADR-0023](0023-payroll-group-holiday-calendars.md)

Current workflow amendments: [ADR-0026](0026-small-team-workflow-and-stable-outputs.md). Historical wording below is superseded only in the scopes explicitly listed there.

## Context

Daily workers are paid for Sunday only when they actually work. Prefilling every non-statutory-holiday calendar date therefore made Sunday look like expected attendance and required HR to remove it repeatedly. Known annual leave, sick leave, unpaid leave and work-injury dates could also remain inside the attendance baseline even though Payroll calculates those dates separately, creating a risk of duplicate pay for daily workers.

The Work Calendar already stores regional statutory holidays locally, but HR could only enter each Hong Kong date manually. The Labour Department publishes an annual statutory-holiday list. ADR-0023 later added a separate general-holiday scope and fixed HKR's employer choice at Christmas Day.

## Decision

- An unsaved daily-worker attendance segment prefills Monday to Saturday only. Sunday and statutory holidays start at zero and are added only after HR confirms actual work from the signed attendance PDF or a confirmed forecast arrangement.
- Known annual leave, sick leave, unpaid leave and work-injury units are removed from the daily-worker prefill. They are not actual attendance; Payroll applies their own paid, reduced-pay or unpaid rules separately.
- Sunday actually worked remains part of the daily worker's ordinary non-statutory-holiday attendance. Statutory-holiday work remains in the dedicated dated field. Existing saved attendance is never rewritten automatically.
- Work Calendar provides one operator-triggered action that now follows ADR-0023: it fetches both the Labour Department statutory list and the GovHK general-holiday list, persists missing dates and adds confirmed calendar scopes to existing dates.
- HKR's statutory employer choice is fixed at Christmas Day. The import does not overwrite names, restore, archive or delete existing records.
- Attendance and Payroll continue to read only the locally persisted Work Calendar. They never depend on a live internet request during calculation or export.

## Consequences

- A normal daily-worker baseline is faster to review because Sundays, statutory holidays and known absences no longer require routine subtraction.
- Annual leave remains full pay without being misrepresented as actual attendance.
- Official-source import is auditable and repeatable while preserving HR corrections and local operational independence; ADR-0023 controls the current dual-calendar behavior.
- Non-Hong-Kong work regions remain manually maintained from their applicable official sources.
