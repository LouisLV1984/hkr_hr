# ADR-0005: TMC Pattern Reuse Without Runtime Coupling

- Status: Accepted
- Date: 2026-07-24

## Context

TMC already demonstrates useful operator patterns such as a three-pane intake workbench, side-by-side comparison, recent batches, and explicit export actions. Directly sharing TMC assets or services would violate HKR HR isolation.

## Decision

TMC may be inspected as a product and interaction-pattern reference. HKR HR may independently implement adapted patterns after removing TMC business concepts.

Do not copy, import, mount, or depend on TMC:

- Database or schema.
- Routes or live services.
- Templates or static runtime assets.
- File/deployment roots.
- Credentials or permissions.
- Workbook writeback and commercial workflow logic.

## Consequences

- Familiar patterns can reduce operator learning cost.
- HKR HR remains independently deployable and testable.
- Similar markup or behavior must be reviewed for HR vocabulary, permissions, sensitive data, and responsive use before adoption.
