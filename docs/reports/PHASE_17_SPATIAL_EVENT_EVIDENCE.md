# Phase 17 — Spatial/Event Evidence Integration

## Purpose

Phase 17 connects the Phase 15 canonical Nandambakkam telemetry timeline to the existing DEM/KML research assets without manufacturing flood labels. The telemetry begins in 2021, while the available NRSC, GCC, and road layers describe the 2015 Chennai event. They therefore cannot be joined as same-event supervised truth.

## Implemented

- Added a reproducible spatial/event evidence audit.
- Reprojected station and vector layers to EPSG:32644 for distance/intersection calculations.
- Counted GCC points within 2 km of the station and NRSC features intersecting the station coordinate.
- Summarized the road evidence status distribution.
- Recorded the temporal join as `NOT_JOINED` and the operational/supervised-label gates as false.
- Added a regression test and a script that writes the artifact.

## Scientific boundary

The output is contextual spatial consistency evidence only. It does not establish a gauge threshold, absolute water-surface elevation, polygon accuracy, road closure causality, or telemetry-to-2015 event correspondence. The historical layers remain source-derived reference evidence and are not treated as ground truth.

## Reproduction

```powershell
cd D:\Projects\PRISM\apps\api
python ..\..\scripts\run_phase17_spatial_event_evidence.py
python -m pytest tests/test_phase17_spatial_event_evidence.py -q
```

## Completion

Phase 17 is complete for bounded historical spatial/context integration. A future phase may expose this artifact in the operator UI as research evidence, but must preserve the non-operational label and temporal-separation gate.
