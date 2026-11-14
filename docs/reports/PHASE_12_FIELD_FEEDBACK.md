# Phase 12 — Field Feedback and State Reconciliation

## Completed scope

- Added snapshot-scoped `FieldObservation` records.
- Added API contracts for road, destination, and allocation observations.
- Required timezone-aware observation timestamps, source references, and
  confidence values in `[0, 1]`.
- Added list and reconciliation endpoints.
- Compared observations against the selected snapshot state.
- Added explicit `MATCH`, `CONFLICT`, and `UNRESOLVED` outcomes.
- Added E6 audit events for every reconciliation.
- Preserved the invariant that field reports do not silently mutate plans or
  mark evacuation as complete.
- Added migration `0005_field_observations`.

## Deliberate boundary

This phase records and reconciles field evidence; it does not automatically
close roads, change shelter capacity, move allocations, or confirm household
arrival. Human authority remains responsible for acting on a conflict.

## Verification

- Phase 12 plus preceding phase focused tests: **9 passed**.
- Python compilation: passed.
- Git diff validation: passed.

## Completion

Phase 12 is complete for provenance-preserving field feedback and conflict
surfacing. Automatic operational state application remains intentionally out
of scope for safety.
