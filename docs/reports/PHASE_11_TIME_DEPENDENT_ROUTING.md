# Phase 11 — Time-Dependent Routing and Assisted Evacuation

## Completed scope

- Added route validity windows: `valid_from_min`, `valid_until_min`, and
  `planned_departure_min`.
- Added a migration and SQLite startup compatibility handling for existing
  databases.
- Added edge-level route feasibility logic requiring both departure and
  estimated arrival to fit the route validity window.
- Added simulation-time invalidation when an in-transit route can no longer
  support its current departure and arrival time.
- Added an explicit `/assistance/queue` read model for blocked, stuck, and
  assistance-required groups.
- Added explicit `dispatch_capability: NOT_IMPLEMENTED` and
  `field_confirmation_available: false` markers.

## Deliberate boundary

This phase does not dispatch real teams or vehicles. It exposes assistance
demand safely and keeps unresolved groups visible. Rescue resources, pickup
points, vehicle capacities, and field confirmation remain Phase 12+ work.

## Verification

- Focused routing, simulation, boundary, and validation tests: **25 passed**.
- Python compilation: passed.
- Git diff validation: passed.

## Completion

Phase 11 is complete for time-window feasibility and assisted-demand exposure.
Operational rescue dispatch is intentionally not claimed.
