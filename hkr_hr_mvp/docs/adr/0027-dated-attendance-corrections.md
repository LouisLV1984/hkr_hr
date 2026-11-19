# ADR-0027: Dated corrections from the current attendance PDF

Accepted 2026-11-17. Supersedes the manual Payroll adjustment entry of ADR-0018 and ADR-0026. Existing manual amounts and evidence remain available.

Operators enter previously agreed corrections while working on that employee's current PDF. One record per employee, work month and payroll month contains dated ordinary attendance and OT differences and one optional collection of evidence. Source facts and the signed PDF stay available alongside the correction history. Effective work-date rates and the actual project determine the gross difference. Corrections already covered by the preceding tail actuals contribute zero additional pay. Legacy aggregates cannot identify individual dates, so the operator identifies overlap in that period.

Monthly Payroll and Departure Payroll consume the same correction facts. The monthly workbook places the difference in Other Payment and freezes the explanation with the snapshot. Later corrections of an already settled amount belong to the next payment month as the remaining difference.
