# ADR-0018: Work-Injury Pay Modes, Final-Payment MPF And Single Payroll Entries

- Status: Accepted
- Date: 2026-08-17
- Supersedes: the fixed four-fifths pay decision in ADR-0017; ADR-0017 remains authoritative for dated injury periods, attendance exemption and visible rules.

## Context

HR confirmed that a work-injury record may be paid either under the four-fifths work-injury rule or at full pay. Monthly follow-up consultation and medical expenses must be reimbursed separately in the workbook's Work Injury Compensation / Medical Expenses column (AM on Daily; AN on Monthly and OFFICE). The previous employee-profile work-injury form was difficult to find and created the risk of parallel maintenance paths.

Departure-month wages also require one source. Ordinary Payroll and Final Payment previously overlapped, while the monthly MPF return still needs the departing employee's contribution until the next contribution day. Fixed allowances, substitute-shift allowances and one-off wage corrections have different time horizons and must not share ambiguous entry points.

## Decision

- Rename the top-level workspace to Leave & Work Injury. Its left rail contains peer Leave Management and Work Injury Management cards.
- Work Injury Management is the only create/correct/withdraw entry for injury periods and monthly medical reimbursement. The employee profile shows summary/history and a link only.
- Store an explicit injury pay mode: `four_fifths` or `full_pay`. Both use HR-verified accident-time monthly earnings; the contract salary is only a prefill. Covered dates remain attendance-exempt.
- Store monthly medical reimbursement separately from wage income. It increases net pay, exports to Work Injury Compensation / Medical Expenses (AM on Daily; AN on Monthly and OFFICE), and is excluded from MPF relevant income.
- Exclude employees whose employment period ends in the selected month from ordinary Payroll. Final Payment is their wage source. Monthly MPF replaces the ordinary row with the confirmed Final Payment contribution; an unconfirmed Final Payment blocks that employee's MPF export. Later months exclude the employee.
- Prorate departure-year annual-leave entitlement by inclusive employment days divided by 365 or 366. Offset overuse against other available leave first; deduct any remaining deficit in Final Payment.
- Calculate annual-leave pay from HR-verified previous-12-month wage total divided by 365. Show the number of Payroll months found and keep a manual daily-rate override for incomplete history.
- Treat HR-entered actual paid workdays as the sole wage basis for daily workers; linked unpaid-leave records are reconciliation evidence and do not create a second deduction. For Monthly and OFFICE staff, deduct unpaid leave once from monthly salary at the calendar-day rate. Keep the applicable rule visible in Attendance and Payroll.
- Keep effective-dated meal, transport and special allowances in the employee's Fixed Allowances card. Enter substitute-shift other allowance only on actual Attendance project rows. Enter wage corrections and other one-off adjustments only from the selected employee/month in Monthly Payroll. Both latter sources export to Other Payment but retain separate source facts.

## Consequences

- HR has one discoverable work-injury workspace and one maintenance entry per type of payment.
- Work-injury medical reimbursement no longer inflates wages or MPF relevant income.
- Departure-month salary and MPF cannot be duplicated between ordinary Payroll and Final Payment.
- Payroll snapshots need separate fields for attendance-derived other allowance and medical reimbursement, even though the workbook combines some outputs.
- The permanent UI calculation notes and operator guide must change whenever these calculation rules change.
