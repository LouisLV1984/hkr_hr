# ADR-0023: Payroll-group-specific Hong Kong holiday calendars

- Status: Accepted
- Date: 2026-08-21
- Supersedes in part: [ADR-0020](0020-work-calendar-and-effective-dated-monthly-pay-method.md), [ADR-0022](0022-daily-prefill-and-official-holiday-import.md)

## Context

Hong Kong statutory holidays under the Employment Ordinance and general holidays under the General Holidays Ordinance are different annual schedules. HKR's Site Daily and Site Monthly staff use statutory holidays, while Management and Head Office staff follow the company's general-holiday schedule. A single undifferentiated regional calendar therefore produces incorrect OFFICE forecasts and misleading attendance wording.

HKR has also confirmed that its employer choice for the statutory Winter Solstice/Christmas item is always Christmas Day. Asking HR to repeat this choice during every annual import creates unnecessary work and an avoidable inconsistency risk.

## Decision

- Each Work Calendar date records whether it applies to the statutory calendar, the general-holiday calendar, or both. The existing regional date remains one record even when both calendars share that date.
- Site Daily and Site Monthly use the statutory calendar. Management and Head Office use the general-holiday calendar. The effective Payroll category selects the calendar automatically; there is no employee-level holiday-calendar setting.
- HKR's statutory importer always chooses Christmas Day, never Winter Solstice, for the employer-choice item.
- One Hong Kong import action retrieves both the Labour Department statutory list and the GovHK gazetted general-holiday list. It adds missing dates and may add a confirmed calendar scope to an existing date, but it does not restore, archive, delete or rename existing records.
- The main import action targets the next calendar year automatically. If that year already contains records, the action becomes a check-and-complete operation; the independent year filter remains only for viewing historical or future calendars.
- Recurring Sundays remain workweek/rest-day logic and are not persisted as individual general-holiday rows.
- Attendance shows the applied calendar and dates in context. Employee Employment & Salary shows the derived calendar as read-only information. Payroll calculation rules permanently state the category-to-calendar mapping.
- Attendance and Payroll calculate only from locally saved Work Calendar records; no payroll calculation or export depends on a live internet request.

## Consequences

- Daily statutory-holiday entitlement remains limited to statutory dates.
- Monthly Site forecasts exclude statutory dates; Management/Head Office forecasts exclude general-holiday dates.
- OFFICE work on a general holiday is treated as genuine work outside the applicable schedule under the existing Payroll/Comp Leave rule.
- Existing Work Calendar rows migrate as statutory-only unless an official general-holiday import confirms the same date or HR changes the scope.
- HR maintains one regional calendar workspace without duplicating employee settings.
