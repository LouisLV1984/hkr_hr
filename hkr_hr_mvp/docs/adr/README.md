# Architecture Decision Records

ADRs record accepted design tradeoffs. They explain why the system follows a direction; they do not track implementation progress.

| ADR | Status | Decision |
|---|---|---|
| [ADR-0001](0001-independent-hr-runtime.md) | Accepted | Keep HKR HR runtime and data independent |
| [ADR-0002](0002-single-employee-create-flow.md) | Accepted | Use one minimal employee-create flow |
| [ADR-0003](0003-ocr-assisted-reviewed-import.md) | Superseded for V1 | OCR is assistive if reintroduced later; ADR-0007 controls V1 |
| [ADR-0004](0004-monthly-attendance-live-payroll.md) | Accepted | Store monthly attendance and calculate payroll live |
| [ADR-0005](0005-tmc-pattern-reuse-without-runtime-coupling.md) | Accepted | Reuse interaction patterns without TMC runtime coupling |
| [ADR-0006](0006-lean-derived-state-design.md) | Accepted | Prefer lean workflows and derived states |
| [ADR-0007](0007-profile-first-manual-document-capture.md) | Accepted | Use employee-profile-first manual document capture; OCR is outside V1 |
| [ADR-0008](0008-segmented-attendance-payroll-snapshots.md) | Accepted | Store segmented attendance and payroll calculation snapshots |
| [ADR-0009](0009-manual-ecall-payroll-rule.md) | Accepted | Enter E-CALL counts manually and include them in payroll and reconciliation |
| [ADR-0010](0010-content-hash-confirmed-document-replacement.md) | Accepted | Detect identical document content and require HR confirmation before replacement |
| [ADR-0011](0011-four-part-attendance-payroll-reconciliation.md) | Accepted | Reconcile Payroll using current actual/forecast and previous actual/forecast |
| [ADR-0012](0012-effective-dated-current-state-and-corrections.md) | Accepted | Derive current state from dates and preserve correction/withdrawal history |
| [ADR-0013](0013-task-oriented-navigation-and-data-preservation.md) | Accepted | Organize navigation by HR tasks and preserve referenced data |
| [ADR-0014](0014-annual-leave-buckets-and-final-payment.md) | Accepted | Separate annual-leave buckets and ordinary Payroll from Final Payment |
| [ADR-0015](0015-shared-readiness-and-production-safety.md) | Accepted | Derive shared readiness and apply unobtrusive production safety controls |
| [ADR-0016](0016-effective-dated-mpf-schemes-and-exports.md) | Accepted | Store effective-dated MPF schemes and export monthly contribution reports |
| [ADR-0017](0017-dated-work-injury-payroll-and-visible-rules.md) | Accepted | Use dated work-injury records, reviewed earnings and visible Payroll rules |
| [ADR-0018](0018-work-injury-pay-modes-final-payment-and-single-payroll-entry.md) | Accepted | Select work-injury pay mode, separate medical reimbursement, replace departure-month Payroll and keep one entry per payment type |

Stable terms and current facts are in [`../../../CONTEXT.md`](../../../CONTEXT.md). Executable rules are in [`../../AGENTS.md`](../../AGENTS.md).

## ADR Rules

- Add an ADR for a durable decision with meaningful alternatives or consequences.
- Do not use ADRs for task status, deployment status, one-off fixes, or current file inventories.
- Do not rewrite an accepted ADR to hide a later reversal. Add a superseding ADR and link both records.
