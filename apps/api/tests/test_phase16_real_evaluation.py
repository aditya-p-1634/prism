from pathlib import Path

from app.research.a16_real_evaluation import evaluate_irregular_stage_series, load_canonical_csv


def test_real_telemetry_evaluation_uses_actual_irregular_intervals():
    root = Path(__file__).resolve().parents[3]
    canonical = root / "data" / "derived" / "nandambakkam_telemetry_canonical.csv"
    rows = load_canonical_csv(canonical, "NANDAMBAKKAM_CHECKDAM")
    report = evaluate_irregular_stage_series(rows, dataset_id="phase15-nandambakkam", station_code="NANDAMBAKKAM_CHECKDAM")
    assert report["usable_samples"] > 1000
    assert report["discarded_long_or_invalid_gaps"] > 0
    assert set(report["metrics"]) == {"AUTOREGRESSIVE_RIDGE", "PERSISTENCE_BASELINE", "LINEAR_TREND_BASELINE"}
    assert report["uncertainty"]["operationally_calibrated"] is False
    assert report["operational_claim_allowed"] is False
