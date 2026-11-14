# Phase 18 — Research Evidence in the Operator Workflow

## Purpose

Phase 18 makes the Phase 17 spatial/event evidence discoverable in the operator workflow while preserving a hard boundary between research context and operational E1–E6 state.

## Implemented

- Added `GET /api/v1/research-evidence/spatial-event` as a read-only artifact endpoint.
- Added a non-operational research evidence panel to `/operator`.
- Displayed telemetry row count, historical GCC proximity, NRSC station intersection count, and temporal join status.
- Explicitly explains that 2015 spatial layers and 2021–2026 telemetry are not a supervised flood-label join.
- Added an endpoint regression test.

## Safety

The endpoint reads a generated artifact and does not write snapshots, hazard states, allocations, routes, simulations, or field observations. The UI marks the evidence `NON-OPERATIONAL`; approval and decision authority remain unchanged.

## Completion

Phase 18 is complete when the API test and frontend production build pass. The evidence remains research-only until a future, separately approved data contract establishes temporally aligned, licensed, quality-controlled observations.
