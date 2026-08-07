# Archived HKR HR MVP Lean Scope

> Historical decision snapshot dated 2026-07-13. Its accepted tradeoffs have been consolidated into current ADRs and `CONTEXT.md`; this copy remains evidence only. See [`../../../CONTEXT.md`](../../../CONTEXT.md) and [ADR-0006](../adr/0006-lean-derived-state-design.md).

Updated: 2026-07-13

This document records the confirmed first-version product decisions. When a future idea conflicts with this scope, keep the simpler behavior until HR has a real operating need.

## Product Principle

- Apply Occam's razor: complete the daily HR workflow before adding extra states, approvals, filters, or settings.
- Employee records, documents, attendance and payroll are one connected workflow, not separate feature pages.
- OCR only pre-fills fields. A blank OCR result never blocks document preview, manual correction, import, archive, or export.
- Keep the full timeline visible. Do not add timeline filters in the first version.

## Employee And Employment

- One person keeps one employee number across rehire.
- Rehire creates a new employment period. Service continuity is explicitly reset or recognized.
- Employment status remains only `active` or `departed`.
- Probation is derived from probation end date and confirmation date; do not add a probation status machine.
- Probation applies only to the management/head-office payroll group and defaults to three months unless the contract says otherwise.
- Confirmation may proceed without evidence, but the missing confirmation document remains a red reminder.
- Ordinary phone, address, email and bank details are editable; before/after values remain in the audit timeline.
- A changed bank account must be confirmed before payroll. Supporting evidence may be added later.
- Name change reasons are only system correction and actual/legal name change. Only the latter requires evidence.

## Identity, Documents And Leave

- An employee may hold multiple identity documents. One is primary; an identity can have a long-term expiry.
- Documents use `active`, `replaced` and `voided`; do not add document version numbers.
- Core document cards include three treasures, Staff Record, signed contract, identity/certificate, VISA, CV, attendance PDF, probation confirmation and termination evidence.
- Annual leave supports half days. The common leave year is 1 January to 31 December.
- Contract leave and statutory leave are shown separately; usable entitlement is the higher value plus any explicit adjustment.
- Prior-year leave is usable until 31 March of the following year and remains a reminder if unused.

## Attendance And Payroll

- Attendance is one signed PDF per employee per month, with HR-confirmed employee, month, project, working days, OT hours and Sunday/holiday days.
- Payroll groups are exactly:
  - `site_daily`: 地盤工人（日工）
  - `site_monthly`: 地盤工人（月工）
  - `management`: 管理人員及總部人員
- HR chooses one group for one XLSX or all groups for a ZIP containing three XLSX files.
- Daily worker OT uses divisor 9, except TMC046/HA projects use divisor 10.
- Payroll calculation and MPF rules must remain visible on the payroll page.
- Missing attendance, salary, or bank payroll confirmation blocks export. Other missing documents appear as warnings and can be acknowledged.
- Employees aged 65 or above have no mandatory MPF contribution.
- Payment in lieu of notice, severance and long-service amounts are reference estimates only and require HR verification.

## Termination

- Reasons: resignation, company termination, redundancy, fixed-contract expiry, failed probation, or other.
- Resignation requires a resignation letter. Company termination and redundancy require a termination notice.
- Final-month payroll includes confirmed payment in lieu, severance and long-service values from the employment period.

## Deferred

- E-call.
- Complex approval workflows and probation states.
- Timeline filters.
- Attachment bundle export.
- Detailed day-by-day attendance OCR.
- Unconfirmed future statutory edge cases beyond the clearly labelled estimate logic.
