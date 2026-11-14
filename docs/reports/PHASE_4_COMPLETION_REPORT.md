# PRISM Phase 4 — A.8.6 Terrain Research Readiness

## Scope

Phase 4 implements the documented A.8.6 scientific safety boundary. The
repository does not contain all prerequisites needed to claim a terrain-aware
flood model, so this phase builds the executable readiness gate and isolated
research entry point rather than fabricating a model or its validation.

## Implemented

- Added isolated `app.research.a8_6` readiness package.
- Verifies the A.8.5 reference files are present and non-empty.
- Hashes reference files for traceability without treating hashing as validity.
- Requires surveyed gauge-zero datum, the southern FABDEM tile, official NRSC
  class metadata, and hydrodynamic connectivity before readiness can pass.
- Rejects missing, non-numeric, boolean, NaN, and infinite gauge datum values.
- Added a CLI readiness report with machine-readable JSON output and non-zero
  exit status when the experiment is not ready.
- Made A.8.5 optional geospatial imports lazy so lightweight readiness checks do
  not require rasterio/geopandas at import time.
- Added read-only and scientific-boundary regression tests.

## Current result

The workspace contains all eight A.8.5 reference files, but the four A.8.6
scientific prerequisites are not verified. The readiness CLI correctly returns
`NOT_READY` with explicit blockers:

- `GAUGE_ZERO_DATUM_UNVERIFIED`
- `SOUTHERN_FABDEM_TILE_MISSING`
- `NRSC_CLASS_METADATA_MISSING`
- `HYDRODYNAMIC_CONNECTIVITY_MISSING`

## Safety statement

No A.8.6 module writes the PRISM database or imports into E1-E6 operational
execution. No gauge stage is converted into absolute water-surface elevation,
no global DEM bathtub threshold is inferred, and no experimental result is
presented as operational flood prediction.

## Verification

The Phase 4 readiness suite passes: **4 passed**. The Phase 0/1/3 focused
regression suites remain green when run with it. Full A.8.5 raster analysis
requires the optional rasterio dependency, which is not installed in the local
environment.

## Completion

**100% of the defined Phase 4 readiness-gate scope is implemented.** The
terrain model itself remains intentionally blocked until the documented
scientific prerequisites are supplied.
