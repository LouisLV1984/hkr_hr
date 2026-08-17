# ADR-0017: Dated Work-Injury Payroll And Visible Rules

- Status: Accepted
- Date: 2026-08-12

## Context

An employee may be unable to work because of a work injury for days or months. The work-injury period affects attendance and Payroll, but it does not replace the employee's derived active/departed employment status. Separate operator-selected states such as `work injury`, `returned to work`, and `case closed` would duplicate facts already expressed by dates and would make routine HR entry harder to understand.

Work-injury pay also requires an HR-reviewed earnings basis. The contractual base salary is a useful starting value, but it is not itself the confirmed statutory earnings basis. HR must see the calculation rule where the work-injury facts are entered and reviewed instead of having to find it only on a central Payroll rules page.

Part-time employment has no confirmed HKR case or pay rule yet and is therefore outside this decision.

## Decision

- Keep employee employment status derived as `active` or `departed`. Do not add work injury or part-time employment to the same status field.
- Store work injury as an effective dated employee record, not as a manually maintained employee status.
- A work-injury record contains the accident date, Payroll start date, optional Payroll end date, HR-confirmed monthly earnings at the time of the accident, monthly earnings during temporary incapacity, evidence and remarks.
- An empty end date means that the work-injury Payroll period is continuing. Entering an end date stops its attendance and Payroll effect after that date. Do not add separate `returned to work` or `case closed` states to the current core.
- Derive a visible `work injury in progress` badge only while today's date falls inside an open work-injury period. Historical periods remain in the employee record and audit timeline without a permanent employee-status badge.
- Exempt only the dates covered by the work-injury Payroll period from attendance entry. A full-month work-injury period requires no attendance entry; a partial month continues to require normal attendance outside the covered dates. Attendance displays the imported work-injury period read-only and directs corrections back to the employee work-injury record.
- Calculate work-injury periodical payment from the first covered day at four-fifths, without the ordinary sick-leave first-day-full-pay rule:

  `Work-injury periodical payment = (HR-confirmed monthly earnings at the time of the accident - monthly earnings during temporary incapacity) x 4/5`

- Prefill the contractual base salary as a convenience only. HR must review and may replace it with the confirmed monthly earnings at the time of the accident before Payroll export.
- Keep ordinary sick leave and work injury as separate calculation components. Ordinary sick leave follows the confirmed company rule of the first aggregate day in a calendar month at full pay and subsequent days at four-fifths; work injury is at four-fifths from the first covered day.
- The existing `Sick Leave / Work Injury` XLSX block may combine both components. `Days` is the combined covered days, `Amount` is the sum of the separately calculated amounts, and `Rate` is `Amount / Days`. Payroll snapshots retain the sick-leave and work-injury breakdown even though the export shows an average rate.
- Keep the applicable rule visible at every decision point; do not hide it only in a tooltip or only on the central Payroll rules page:
  - Below the work-injury earnings fields, always show that contractual base salary is only a prefill and that HR must verify monthly earnings under the Labour Department rule. Show the full four-fifths formula and a link to the official Labour Department guidance.
  - In Attendance Entry, whenever the selected month contains work-injury dates, always show the covered period, the read-only source rule, and the fact that those dates require no attendance entry.
  - In Payroll employee details and the permanent calculation-rules area, always show the work-injury dates, confirmed earnings basis, temporary-incapacity earnings, four-fifths rate and calculated amount.
- Use this Traditional Chinese helper copy below the work-injury earnings fields as the canonical source for translated UI text:

  `工傷計薪基數已預填合約底薪，僅供參考。請按勞工處規則核實僱員發生意外時的每月收入並按需要調整。工傷按期付款＝（發生意外時的每月收入－暫時喪失工作能力期間的每月收入）× 4/5；由工傷計薪首日起計，不設首日全薪。`

- Do not implement part-time status, attendance exemptions, or Payroll rules until a real HKR part-time arrangement and pay basis are available.

## Consequences

- HR ends the Payroll effect of a work injury by entering one end date instead of maintaining overlapping workflow states.
- Attendance exemption is date-aware and does not incorrectly exempt the employee before or after the work-injury period.
- Payroll retains an auditable HR-confirmed earnings basis instead of silently treating contractual base salary as the statutory amount.
- Repeating the calculation rule in the work-injury, attendance and Payroll interfaces is intentional because each page contains a decision or verification point.
- The current core remains focused on confirmed full-time cases and does not guess future part-time Payroll behavior.
- Additive schema and UI changes are required; no employee-data reset is required.

## Reference

- Hong Kong Labour Department, Employees' Compensation Ordinance: <https://www.labour.gov.hk/tc/legislat/content1.htm>
