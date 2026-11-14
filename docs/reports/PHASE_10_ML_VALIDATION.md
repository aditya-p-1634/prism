# Phase 10 — Reproducible ML and Data Validation

## Completed scope

- Added a strict hydrometric CSV contract requiring ordered simulation time,
  river stage, and rainfall rate.
- Added finite-value and monotonic-time validation.
- Added deterministic chronological 60/20/20 splitting with boundary samples
  discarded when targets cross partitions.
- Added multi-horizon evaluation for 10, 30, 60, and 120 minutes.
- Benchmarked autoregressive Ridge against persistence and linear-trend
  baselines.
- Added provenance-rich JSON reports and a CLI:
  `python scripts/run_phase10_validation.py <csv> --dataset-id <id>`.
- Added explicit `verified` gating so external metrics cannot be presented as
  operational evidence without a verified source manifest.

## Scientific boundary

No real-world dataset was fabricated or bundled. The existing Vayu series is
synthetic demonstration data and remains marked non-operational. This phase
provides the reproducible validation mechanism; real-world accuracy claims
require a verified dataset, documented licensing, domain metadata, and
ground-truth calibration.

## Verification

- Phase 10 and related regression tests: **13 passed**.
- Python compilation: application modules passed.
- Frontend and existing Phase 9 verification remain green.

## Completion

Phase 10 is complete for the validation framework and safety contract. The
external-data population step remains intentionally dependent on a verified
dataset supplied by the project team.
