# ADR-0006: Lean Workflows And Derived States

- Status: Accepted
- Date: 2026-07-24

## Context

Early proposals accumulated optional statuses, filters, approvals, and branching entry paths. Many can be derived from dates and records or deferred until an actual HR task requires them.

## Decision

- Prefer the smallest workflow that completes the confirmed HR task.
- Prefer state derived from existing dates and records over separately maintained status fields.
- Add approval layers, filters, exception categories, and abstractions only for a confirmed business need.
- Preserve audit evidence for sensitive changes without making every edit a separate approval workflow.
- Keep one clear action path for each HR job.

## Consequences

- Current workflows prioritize end-to-end completion over speculative flexibility.
- Deferred ideas are not promises or durable decisions.
- A new status or branch needs a concrete operational case and should be reconciled with existing derived state first.
