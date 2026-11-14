# Phase 16 — Real Telemetry Baseline Evaluation

## Completed scope

- Added an evaluator for irregularly sampled historical telemetry.
- Used actual observed intervals rather than forcing the source into the
  synthetic fixed-10-minute feature builder.
- Discarded long gaps and cross-split boundary samples.
- Compared autoregressive Ridge, persistence, and linear-trend baselines.
- Added validation-residual interval coverage reporting.
- Generated a reproducible Nandambakkam evaluation artifact.

## Result

Dataset: `phase15-nandambakkam`  
Station: `NANDAMBAKKAM_CHECKDAM`  
Usable samples: **26,738**  
Test samples: **5,475**

| Model | MAE (m) | RMSE (m) | R² |
|---|---:|---:|---:|
| Autoregressive Ridge | 0.4362 | 2.0925 | 0.8880 |
| Persistence | **0.3425** | 2.1547 | 0.8812 |
| Linear trend | 0.6702 | 3.4208 | 0.7006 |

Ridge has the lowest RMSE, but persistence has the lower MAE. This is not a
universal ML win and should be reported as a metric trade-off, not as proof
that Ridge is the correct operational model.

The validation-derived interval covered only **65.95%** of test observations.
It is therefore explicitly **not calibrated for operational use**.

## Scientific boundaries

This is a station-specific, next-observation, stage-only evaluation. Rainfall
was not present in the source and was not invented. River stage was not
converted into discharge or flood thresholds. The source is historical and its
licensing, vertical datum, and operational representativeness remain separate
provenance questions.

## Completion

Phase 16 is complete for real historical telemetry benchmarking. The next
phase is spatial/event evidence integration: joining the telemetry timeline to
documented flood extent and terrain layers without treating the extent product
as perfectly calibrated ground truth.
