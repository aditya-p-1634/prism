# PRISM Phase 5 — Operational Hardening

Phase 5 establishes safer runtime configuration and deployment health
boundaries without changing E1–E6 decision algorithms.

Implemented scope:

- Production and staging settings reject the demo JWT secret or secrets shorter
  than 32 characters.
- Wildcard CORS is rejected outside demo/test environments.
- CORS origins are configured through `CORS_ORIGINS` instead of being hard-coded
  to `*`.
- `/api/v1/health/readiness` checks database connectivity and verifies that
  `SNAP_BASE_001` exists, is typed `BASELINE`, and is immutable.

The liveness endpoint remains lightweight and does not require a database. The
readiness endpoint is intended for deployment orchestration and returns HTTP
503 when the service cannot safely accept operational traffic.
