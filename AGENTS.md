# HKR HR Workspace Rules

This is the active workspace for the independent HKR HR Staff MVP.

## Required Reading

Before changing the Flask app under `hkr_hr_mvp`, read:

1. [`hkr_hr_mvp/AGENTS.md`](hkr_hr_mvp/AGENTS.md) for executable development and deployment rules.
2. [`CONTEXT.md`](CONTEXT.md) for stable vocabulary, current architecture, and operational facts.
3. [`hkr_hr_mvp/docs/adr/README.md`](hkr_hr_mvp/docs/adr/README.md) for accepted design decisions relevant to the change.

Historical files under `hkr_hr_mvp/docs/archive/` are evidence only. They are not current instructions or product authority.

## Workspace Boundary

- Development workspace: `C:\Projects\02.HKR_HR`
- Flask app root: `C:\Projects\02.HKR_HR\hkr_hr_mvp`
- This system is independent from TMC.
- Never deploy HKR HR to `T:\` or `D:\TMC_FileServer`.
- Production is `R:\` from the laptop and `D:\HKR_HR` on the mini PC.
- Runtime data belongs only in the independent PostgreSQL database `hkr_hr_db`.

TMC may be studied for interaction patterns, but do not copy or share its runtime assets, database, routes, templates, deployment roots, or services. See [ADR-0005](hkr_hr_mvp/docs/adr/0005-tmc-pattern-reuse-without-runtime-coupling.md).

## Source Control Boundary

- The official source repository is `https://github.com/LouisLV1984/hkr_hr`.
- Publish only this workspace's `AGENTS.md`, `CONTEXT.md`, and the `hkr_hr_mvp` application source and current documentation.
- Never commit employee records, attendance or payroll source files, signed contracts, credentials, `.env` files, runtime data, generated output, backups, or local verification evidence.
- Keep the root `.gitignore` deny-by-default because this workspace also contains real HR business files outside the application source tree.
