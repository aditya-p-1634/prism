# Phase 21 — Full-System Verification and Boundary Hardening

## Verification scope

This pass covered the repository state, backend compilation, disposable test
database isolation, E1–E6 safety invariants, API boundary behavior, GeoJSON
integrity, frontend route rendering, and the local browser workflow. The
shared demonstration database was not used for automated tests or modified by
the verification work.

## Confirmed checks

### Backend and API

- `python -m compileall -q app` passed after the hardening changes.
- Read-only live smoke checks passed for health, readiness, telemetry,
  snapshots, scenarios, dashboard, hazards, population, destinations, roads,
  routes, allocations, reports, research evidence, and audit endpoints.
- The dashboard returned all nine geographic collections:
  study boundary, current flood, predicted flood, risk zones, habitations,
  habitation points, destinations, road segments, and active routes.
- GeoJSON inspection found 46 features with 8 Polygon, 7 Point, and 31
  LineString geometries. All checked geometries were non-empty, valid, and
  within longitude/latitude bounds.
- Unknown snapshot probes now consistently return `404
  SNAPSHOT_NOT_FOUND` for snapshot-scoped read models instead of silently
  returning an empty successful response.
- Invalid pagination boundaries already return 422 (for example `limit=0`
  and `limit=201`). Missing simulation runs return 404.

### Engine and safety invariants

The non-`TestClient` invariant group passed **32 tests**, covering:

- E1–E4 deterministic engine behavior.
- Explicit unmet demand and capacity limits.
- Snapshot isolation and baseline immutability.
- Cross-snapshot and route-identity rejection.
- Zero-duration simulation behavior.
- Production configuration security boundaries.
- Scenario parameter validation.

Additional boundary tests added in this pass confirm that:

- Unknown scenario override keys are rejected rather than silently ignored.
- Direct engine calls reject NaN, infinity, and boolean timestep/duration
  values.
- Optional A8.5 raster imports no longer break ordinary application import or
  test collection when `rasterio` is absent.

### Frontend and browser

All 12 frontend modules loaded through the live browser without an application
error: operator, map, hazards, population, resources, routing, simulation,
scenarios, overrides, reports, audit, and settings.

The map workflow additionally verified the MapLibre canvas, satellite and
streets basemaps, backend overlays, layer controls, navigation controls,
attribution, scale, study boundary, labels, and entity markers.

## Loopholes found and closed

### 1. Research dependency crashed full test collection

`rasterio` was imported at module import time but was not declared as a
dependency. The A8.5 module could therefore crash the entire suite before any
test ran. Raster imports are now lazy with explicit runtime guidance, the
research extra is declared in `apps/api/pyproject.toml`, and the A8.5 test
module skips transparently when the optional dependency is unavailable.

### 2. Unknown simulation parameters were silently accepted

The scenario validator checked known values but allowed arbitrary keys. A
misspelled operational override could appear in persisted parameters while
having no effect. A strict supported-key allowlist now rejects unknown keys.

### 3. Non-finite direct simulation bounds were not rejected

API schemas constrained normal requests, but direct engine callers could pass
NaN, infinity, or booleans to the timestep/duration validator. The engine now
rejects those values explicitly before tick calculation.

### 4. Unknown snapshots could look like empty reality

Several read endpoints returned HTTP 200 with empty data for nonexistent
snapshot IDs. A shared `require_existing_snapshot` guard now makes the missing
state explicit and consistent.

## Verification limitation

The complete pytest suite collects successfully at **255 tests**, but
Starlette's synchronous `TestClient` deadlocks in this workstation's Python
3.14/Windows Proactor + AnyIO combination before the `/health` handler is
entered. The stack trace is in the test harness's blocking portal, not PRISM
application code. Live HTTP checks against the running Uvicorn service passed,
and the non-`TestClient` invariant suite passed 32 tests.

The A8.5 raster validation file is skipped because this environment cannot
download the optional `rasterio` wheel. Its source imports are now safe and its
dependency is declared; the actual raster assertions remain pending an
environment with the research extra installed.

## Final assessment

The verified PRISM prototype is coherent for demonstration and research
development. The high-value safety boundaries are enforced, and the remaining
verification blockers are reproducible environment/dependency limitations,
not unreported application failures. The next engineering action should be to
standardize CI on a supported Python/runtime matrix and run the full suite
there, including the A8.5 research extra.
