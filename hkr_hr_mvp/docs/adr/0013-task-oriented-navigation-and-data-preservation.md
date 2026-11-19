# ADR-0013: Task-Oriented Navigation And Data Preservation

**Status:** Accepted  
**Date:** 2026-07-31

Current workflow amendments: [ADR-0026](0026-small-team-workflow-and-stable-outputs.md). Historical wording below is superseded only in the scopes explicitly listed there.

The navigation and default landing pages are updated by [ADR-0029](0029-employee-workbench-and-task-pages.md).

## Context

HKR HR had grown into a collection of functions. Attendance and Payroll shared one top-level label, while report/export functions duplicated Payroll actions. Admin tools were mixed with HR-maintained reference data. Empty pages also exposed large inactive work areas before the operator had selected or uploaded anything.

Reference-data deletion could clear values from existing employee, attendance, or Payroll records. That made routine option maintenance capable of changing historical business facts.

## Decision

Historical navigation grouping (superseded by ADR-0026; current labels and locations are in CONTEXT.md):

1. Work Overview;
2. Employees;
3. Annual Leave;
4. Attendance;
5. Payroll & Exports;
6. Reference Data.

Attendance contains collection and entry only. Payroll calculation, Payroll export, employee-record export, attachment bundles, and salary certificates share the Payroll & Exports workspace. Admin tools are reached through the signed-in Admin account and are not mixed into HR reference-data navigation.

Pages show a purposeful start state until data exists. Workbenches appear only after the operator has selected or uploaded a record.

List and management workspaces use a consistent two-part layout. The fixed left rail contains the active submodule, selected month or year, filters, and the current work context. The right pane displays filtered results and the actions that change those results. Filters appear only under the active submodule. ADR-0026 replaces the universal `All` default with task-specific missing/exception views. Work Overview has no left rail. Focused preview workbenches, employee forms and dialogs may use a task-specific layout instead of adding an empty rail.

Employee Management and Annual Leave Management follow this layout. Attendance Management has four peer submodules: Attendance Details, Attendance Collection, Specific-month Attendance Exemption, and Long-term Attendance Exemption. The two exemption views retain the selected month and filter by position/trade and Payroll group; bulk changes are performed above the right-side result list. A specific-month exemption automatically returns to attendance-required in the following month.

Reference values and projects with existing usage cannot be deleted. HR can disable them for new records without changing historical records. Only unused values may be deleted.

## Consequences

- Operators navigate by outcome rather than data table or implementation module.
- Payroll has one canonical calculation/export entry.
- Admin and HR maintenance remain visibly separate.
- Existing employee and payroll history cannot be damaged by deleting a dropdown option.
- Disabling a value is the normal retirement operation; deletion is reserved for unused setup mistakes.
- Filters and actions have predictable ownership across list workspaces, while focused forms are not forced into an unsuitable sidebar layout.
