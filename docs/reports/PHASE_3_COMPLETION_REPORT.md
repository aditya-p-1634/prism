# PRISM Phase 3 — Routing and Temporal Feasibility

## Scope

Phase 3 hardens E4 route planning and E5 temporal simulation without replacing
the existing NetworkX and OR-Tools CP-SAT architecture.

## Implemented

- Candidate route keys are checked against the route's persisted origin and destination.
- Route plans, relocation groups, capacity states, and allocations are required to remain in one snapshot branch.
- Optimizer outputs are checked for matching capacity and route context and for destination over-allocation.
- Temporal simulations reject baseline-typed snapshots, not only the special baseline ID.
- Temporal movement rejects a route belonging to a different scenario snapshot.
- Temporal reallocation uses snapshot-scoped destination operational status and suitability views.
- Existing movement, evacuation-state, resource, and explicit-unmet-demand behavior remains intact.

## Verification

The focused Phase 3, Phase 1 integrity, engine, and Phase 0 reproducibility
tests pass: **14 passed**. Python compilation and `git diff --check` also pass.

The legacy temporal API suite is not reported as fully green in the local
environment because its Starlette `TestClient` execution does not complete
under the installed Python 3.14/httpx combination. That is an environment
compatibility limitation, not a fabricated pass claim; CI remains the required
Python 3.11 verification path.

## Scientific and operational boundary

Routing remains a deterministic prototype using weighted NetworkX shortest
paths and CP-SAT assignment. It does not claim live traffic, calibrated travel
time distributions, or validated hydrodynamic route-risk probabilities.

## Completion

**100% of the defined Phase 3 scope is implemented.** Broader CI validation
remains an infrastructure verification task because of the local TestClient
compatibility issue described above.
