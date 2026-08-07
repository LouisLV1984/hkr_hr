# ADR-0013: Task-Oriented Navigation And Data Preservation

**Status:** Accepted  
**Date:** 2026-07-31

## Context

HKR HR had grown into a collection of functions. Attendance and Payroll shared one top-level label, while report/export functions duplicated Payroll actions. Admin tools were mixed with HR-maintained reference data. Empty pages also exposed large inactive work areas before the operator had selected or uploaded anything.

Reference-data deletion could clear values from existing employee, attendance, or Payroll records. That made routine option maintenance capable of changing historical business facts.

## Decision

The primary navigation follows six HR tasks:

1. Work Overview;
2. Employees;
3. Annual Leave;
4. Attendance;
5. Payroll & Exports;
6. Reference Data.

Attendance contains collection and entry only. Payroll calculation, Payroll export, employee-record export, attachment bundles, and salary certificates share the Payroll & Exports workspace. Admin tools are reached through the signed-in Admin account and are not mixed into HR reference-data navigation.

Pages show a purposeful start state until data exists. Workbenches appear only after the operator has selected or uploaded a record.

Reference values and projects with existing usage cannot be deleted. HR can disable them for new records without changing historical records. Only unused values may be deleted.

## Consequences

- Operators navigate by outcome rather than data table or implementation module.
- Payroll has one canonical calculation/export entry.
- Admin and HR maintenance remain visibly separate.
- Existing employee and payroll history cannot be damaged by deleting a dropdown option.
- Disabling a value is the normal retirement operation; deletion is reserved for unused setup mistakes.
