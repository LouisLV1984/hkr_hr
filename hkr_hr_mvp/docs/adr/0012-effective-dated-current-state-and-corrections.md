# ADR-0012: Effective-Dated Current State And Corrections

- Status: Accepted
- Date: 2026-07-30

## Context

HR needs the employee file to show today's facts first while preserving employment, salary, document and leave history. A future last working day must not remove an employee from attendance or Payroll early. Incorrect entries must be fixable without deleting the evidence trail.

## Decision

- Derive displayed employment status from employment-period dates.
- A future last working day keeps the employee active until that date.
- Employee tabs show current personal, assignment, salary, credential and document state before related history.
- Assignment and salary records support evidence supplements, correction and withdrawal. Withdrawal marks the record voided and rebuilds effective ranges; it does not delete history.
- Employee documents support active, replaced and voided states. Replacement relinks dependent HR records to the new active document.
- Annual leave records support correction and withdrawal in 0.5-day units.
- Termination details can be corrected or withdrawn. Statutory amounts remain editable HR estimates, not legal determinations.
- Use the same four operator actions across domains:
  - **Correct** changes a wrong field or effective date on the current record and audits before/after values.
  - **Withdraw / Void** excludes an entire invalid record from current state and calculations without deleting it.
  - **Replace** creates a new active attachment, marks the wrong attachment replaced, and retains the old file.
  - **Supplement evidence** attaches a missing document later without blocking the underlying employment or salary record.
- Normal click opens an attachment. Visible actions remain the primary workflow; a TMC-style right-click may open the same correction form as an optional shortcut.

## Consequences

- Lists, Dashboard, attendance and Payroll use the same effective-date status rule.
- Audit and employee timelines retain corrections and withdrawals.
- Payroll ignores withdrawn attendance and adjustment rows; expiry reminders ignore voided credentials.
- HR does not need administrator intervention to correct ordinary entry mistakes.
- HR no longer needs a separate timeline page to understand the current record and its history.
- Additive schema changes are required; no production database reset is required.
