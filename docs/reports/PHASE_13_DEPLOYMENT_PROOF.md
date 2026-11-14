# Phase 13 — Deployment and Portfolio Proof

## Completed scope

- Added API container entrypoint that applies Alembic migrations before
  startup.
- Added explicit `PRISM_SEED_DEMO` control for synthetic demonstration data.
- Made Docker Compose database password, JWT secret, and CORS configurable.
- Added a non-production environment template.
- Added a Windows release verification script covering focused backend tests,
  Python compilation, frontend TypeScript, and production build.
- Added deployment and portfolio runbooks.
- Added backend compilation to CI.
- Corrected CI migration execution to run from repository root.
- Made evidence provenance migration idempotent with the transitional baseline
  schema.

## Verification

- Release verification: **17 tests passed**.
- Frontend production build: passed.
- Docker Compose configuration: passed.
- Fresh SQLite Alembic chain through `0005_field_observations`: passed.
- Python compilation and Git diff checks: passed.

## Deliberate boundary

The Docker stack is a reproducible demonstration deployment, not a certified
emergency-operations deployment. Production still requires managed secrets,
TLS, identity integration, backups, observability, disaster recovery, and
approved operational datasets.

## Completion

Phase 13 is complete for reproducible local deployment, CI verification, and
portfolio presentation proof.
