# ADR-0020: Work calendar and effective-dated monthly pay method

- Status: Accepted
- Date: 2026-08-19
- Superseded in part by: [ADR-0023](0023-payroll-group-holiday-calendars.md)

## Context

Most monthly and management staff receive a full calendar-month salary, but a small contractually defined group works only when called and must be paid by actual calendar attendance days. Treating both groups with one attendance form either overpays the exception or makes ordinary monthly staff look as if normal attendance must be entered. Employees may contractually use 5, 5.5 or 6 normal workdays per week, so forecast and extra-work treatment cannot be inferred only from Payroll group. Regional statutory holidays must also be available to Attendance and Payroll without a live internet dependency.

## Decision

Salary history stores an effective-dated `monthly_pay_method`: `full_month` is the default and `attendance_days` is the explicit exception. The exception uses monthly salary divided by calendar days multiplied by actual paid attendance days. Saturdays, Sundays and statutory holidays actually worked are included directly and do not create an additional Sunday/statutory-holiday work payment.

Assignment history stores effective-dated `workweek_days` with allowed values 5, 5.5 and 6. Five days counts Monday-Friday, 5.5 also counts Saturday morning as 0.5 day, and 6 counts Monday-Saturday. Regional holidays are maintained locally in a work calendar and excluded from forecast normal work according to the Payroll-group-specific calendar in ADR-0023. Attendance-prorated monthly staff forecast zero unless HR enters a confirmed arrangement.

Work outside the effective workweek is entered by total and date, with one `pay`/`comp_leave` choice for the monthly attendance record. Five-day Saturday, Sunday and work on a date in the employee's applicable holiday calendar counts as one day; under a 5.5-day workweek, only Saturday afternoon is outside the workweek and counts as 0.5 day. It is not OT. Company policy grants daily workers one normal daily rate for every regional statutory holiday from employment start even without work. Actual work on that holiday adds another 1x when `pay` is selected, or adds comp leave without work pay when `comp_leave` is selected.

Data-option retirement remains a preserved active/archive state. The UI calls it Archive/Restore, retains history and audit, and permits permanent deletion only when no data references the value.

## Consequences

- Existing monthly salary rows remain `full_month` after migration.
- Existing Monthly assignments migrate to a 6-day workweek and existing Management/OFFICE assignments to a 5-day workweek; HR can correct contract exceptions through assignment history.
- Pay method changes follow salary effective dates and correction history.
- HR must maintain the applicable statutory and general-holiday calendars from official sources before the affected Payroll month; ADR-0023 defines the Payroll-group mapping.
- The attendance page permanently explains which day count is payroll-bearing for each method.
- Daily statutory-holiday pay uses the statutory scope, while forecast normal-work dates use the Payroll-group-specific scope defined in ADR-0023.
- Missing assignments remain derived missing data and are not represented by synthetic reference values.
