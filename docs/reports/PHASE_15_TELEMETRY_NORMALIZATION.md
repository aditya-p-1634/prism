# Phase 15 — Historical Telemetry Normalization

## Completed scope

- Added a canonical telemetry adapter for the audited Tamil Nadu source files.
- Normalized station names into stable PRISM station codes.
- Converted timezone-naive source timestamps using an explicit declared
  timezone assumption (`Asia/Kolkata`) and stored normalized UTC timestamps.
- Normalized the measurement unit to metres.
- Preserved source file, source row number, source timestamp, and timezone
  assumption for every emitted observation.
- Detected duplicate station-time records and reportable gaps.
- Generated a station-specific manifest for Nandambakkam CheckDam.

## Findings

- Nandambakkam normalized rows: **27,634**.
- Duplicate station-time rows: **0**.
- Missing/invalid rows: **0**.
- Gaps over 1.5 hours: **893**.
- Rainfall join: **not performed** because this source does not contain
  rainfall observations.

The gaps are preserved as a quality signal. No interpolation or fabricated
rainfall was introduced.

## Reproducibility

```powershell
python scripts/prepare_historical_telemetry.py `
  data/telemetry/rwl_tel_hr_tamil_nadu_sw_gw_27_2021_2025.csv `
  data/telemetry/rwl_tel_hr_tamil_nadu_sw_gw_27_2026_2030.csv `
  --station NANDAMBAKKAM_CHECKDAM `
  --input-timezone Asia/Kolkata `
  --output data/derived/nandambakkam_telemetry_canonical.csv `
  --manifest docs/research/artifacts/phase15_nandambakkam_manifest.json
```

## Completion boundary

Phase 15 is complete for telemetry normalization. The dataset is suitable for
historical observation analysis, but not yet for rainfall-conditioned ML
evaluation until a separately verified rainfall source is joined.
