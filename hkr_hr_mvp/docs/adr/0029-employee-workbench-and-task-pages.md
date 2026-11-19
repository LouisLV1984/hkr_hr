# ADR-0029: Employee workbench and task pages

- Status: Accepted
- Date: 2026-11-18

## Decision

The employee workbench is the home page. Employee Files, Leave & Work Injury, Attendance Entry and Payroll are its four peer destinations. Settings, exports of employee files and administration retain their utility entries. This updates the navigation in ADR-0013 and the default attendance landing page in ADR-0026.

A batch of signed PDFs arrives before HR identifies the employees. Open the first pending PDF in the relevant batch and assign its employee after preview. Persisted item status supports handover between operators. Missing employees are a separate roster. Dated corrections remain in the current attendance form.

Use one leave-entry form from both the employee profile and the leave workspace. Link from payroll issues to their existing source forms. Keep annual leave, compensation, final payment and historical payroll in their owning modules. No additional approval steps are introduced.

### Employee Files and payroll review

Employee Files opens a browsable card directory grouped by department or primary position. Unassigned staff are visible, and search, departed staff and the existing create flow remain available. The profile has five tabs. Employment status is grouped with terms, and the credentials and file library share one tab while retaining their respective record editors. Previous profile links still target the corresponding section.

The monthly review lists each employee once with links to missing source records. Negative net pay exposes the existing calculation and its sources. Exempt attendance is reviewed against leave and injury records without requiring a PDF.
