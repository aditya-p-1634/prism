# PRISM Phase A.8.6 — Terrain Experiment Readiness

This phase implements an executable readiness boundary for the proposed
terrain-aware flood experiment. It does not claim that the experiment is
validated or operational.

## Required prerequisites

- Surveyed Nandambakkam CheckDam gauge-zero elevation and verified vertical datum.
- Southern FABDEM tile `N12E080`.
- Official NRSC metadata defining pixel values `1` and `13`.
- A hydrodynamic river/connectivity representation.

The readiness gate also verifies that the A.8.5 reference datasets exist and
are non-empty. It computes file hashes for traceability but does not interpret
hash presence as scientific validation.

## Safety boundary

The implementation is isolated under `app.research.a8_6`. It performs no
database writes and is not imported by E1-E6 operational execution paths. It
rejects execution while any prerequisite is missing. It does not convert gauge
stage into water-surface elevation, infer a global DEM bathtub threshold, or
write experimental outputs into operational snapshots.

## Current status

The repository contains the A.8.5 reference files, but the four A.8.6
prerequisites above are not verified in the workspace. Therefore the readiness
status is intentionally `NOT_READY`.
