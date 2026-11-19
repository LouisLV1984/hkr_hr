# ADR-0025: Calendar-Year Advance Annual Leave

- Status: Accepted
- Date: 2026-10-09

## Decision

HR confirms the actual employment start date and editable initial contract leave (default 7 days) before activating the company calendar-year rule. Initial leave remains pending contract verification until HR explicitly applies its reviewed value from a signed contract; later changes to that initial value clear verification. Initial leave is 7–14 days in half-day units. For initial 7 days, the hire calendar year and following calendar year use 7; subsequent years add one day to a maximum of 14. For initial leave above 7, each following calendar year adds one day, capped at 14. This is the company allocation rule, not an automated legal interpretation.

The hire year uses inclusive calendar days from the start date through December 31, divided by the actual year length, multiplied by the initial leave. Round to the nearest half day, ties upward. Departure earning retains full precision from January 1 or the start date through the last day; do not prorate an already prorated hire-year allocation again. A manual annual entitlement is prorated over its scheduled employment days in that calendar year.

Activation and corrections save only the current year's calculation and audit before/after amounts. Earlier accounts, allocations and approved balances remain intact. Manual overrides remain effective for their specific year unless HR explicitly chooses the calculated entitlement. A current account stores its calculation basis so later-year contract changes do not rewrite earlier allocations.

HR maintains the existing combined 2023-and-earlier balance manually; its card remains visible even when zero. ADR-0014's bucket allocation, expiry and settlement separation remain effective. This ADR defines the company annual entitlement calculation for activated accounts from 2026 onward; unconfirmed existing employees retain their previous calculation with a visible pending notice.

The interface defaults to the actual current year and previews only that year. On the first authenticated GET after the year changes, configured employees receive the current-year account exactly once, including catch-up after downtime. It does not generate intervening historical accounts. Thus no continuously running midnight scheduler is required.

Departure previews show earning, usage, other valid balance offsets, excess usage and the estimated deduction. Existing Final Payment daily-rate review, net calculation and exports own the monetary deduction. Excess usage without a valid positive rate blocks export. Signed-contract review can explicitly correct the initial basis; generated draft contracts cannot overwrite confirmed leave settings.

## Consequences

When HR corrects an activated employee's hire date in leave setup or Staff Record review, saving requires an explicit choice between recalculating and retaining the current year's entitlement. The latter stores a current-year override only. Future accounts use the corrected hire date. Cancellation saves nothing; prior accounts and used leave remain intact.

HR can repair a 2020 hire without recreating 2020–2025 accounts. The review list exposes missing bases, current-year calculated amounts, manual overrides and latest saved corrections. Existing balances are not bulk overwritten. Saved Payroll exports remain historical evidence and require review and re-export when corrections affect settlement.
