# ADR-0001: Independent HKR HR Runtime

- Status: Accepted
- Date: 2026-07-24

## Context

HR data is sensitive and operationally separate from TMC. Sharing a database, schema, app root, file root, or service would blur ownership and increase deployment and data-access risk.

## Decision

HKR HR uses its own:

- Flask application and routes.
- PostgreSQL database `hkr_hr_db`.
- Production root `D:\HKR_HR` (`R:\` from the laptop).
- Attachments, templates, outputs, credentials, and service scripts.

HKR HR tables must not be placed in `tmc_platform`, and HKR HR must not deploy under TMC roots.

## Consequences

- HKR HR can be deployed, restarted, backed up, and secured independently.
- Similar TMC and HR features may require separate implementations.
- Pattern reuse is governed separately by [ADR-0005](0005-tmc-pattern-reuse-without-runtime-coupling.md).
