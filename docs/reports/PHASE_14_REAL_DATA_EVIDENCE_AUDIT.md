# Phase 14 — Real-Data Evidence Audit

## Purpose

This milestone audits the research assets already present in PRISM before they
are used for model training or resume claims. It checks file integrity,
schema, timestamps, duplicate station-time records, missing values, and basic
XML validity. It does not infer licensing, datum correctness, scientific
ground truth, or operational validity from file presence.

## Findings

- Historical telemetry file: **72,875 rows**, four stations, coverage through
  2025-12-31, zero missing values, zero invalid values/timestamps, and zero
  duplicate station-timestamp rows.
- 2026 telemetry file: **20,359 rows**, four stations, coverage through
  2026-10-01, zero missing values, zero invalid values/timestamps, and zero
  duplicate station-timestamp rows.
- Six KML research assets: XML-valid and present, but their geometry and
  attributes are not automatically treated as survey-grade ground truth.
- FABDEM tile: present and hash-manifested, but spatial coverage, vertical
  datum, resolution adequacy, and licensing still require domain review.

## Scientific boundaries

The telemetry values are historical river-level observations, not discharge,
water-surface elevation, or flood thresholds. The existing source documentation
also records that the NRSC flood simulation lacked downstream discharge
calibration. PRISM therefore may use these assets for a reproducible historical
case study, but must not claim calibrated flood prediction or operational
accuracy from them alone.

## Reproducibility

Run:

```powershell
python scripts/audit_research_assets.py --output docs/research/artifacts/phase14_real_data_audit.json
```

The generated JSON contains per-file SHA-256 hashes, temporal coverage,
station counts, validation status, and explicit limitations.

## Completion

The evidence-audit milestone is complete. The next data milestone is to build
a station-specific adapter and a documented historical evaluation dataset that
joins verified telemetry with rainfall and event/flood-extent labels without
inventing missing fields.
