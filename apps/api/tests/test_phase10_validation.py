import csv

import pytest

from app.research.a10_validation import DatasetContractError, evaluate_hydrometric_series, load_hydrometric_csv
from app.seed.synthetic_data import get_vayu_hydrometric_time_series


def test_phase10_evaluator_is_baseline_first_and_leakage_safe():
    rows = get_vayu_hydrometric_time_series()
    report = evaluate_hydrometric_series(
        rows,
        source_manifest={"dataset_id": "synthetic-vayu-demo", "verified": False},
        horizons=(1, 3),
    )
    assert report["split_policy"]["shuffle"] is False
    assert report["split_policy"]["future_target_leakage"] is False
    assert report["operational_claim_allowed"] is False
    assert len(report["horizons"]) == 2
    for horizon in report["horizons"]:
        assert set(horizon["metrics"]) == {
            "AUTOREGRESSIVE_RIDGE",
            "PERSISTENCE_BASELINE",
            "LINEAR_TREND_BASELINE",
        }


def test_phase10_csv_contract_rejects_missing_or_non_monotonic_data(tmp_path):
    path = tmp_path / "bad.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["simulation_time_min", "river_stage_m"])
        writer.writeheader()
        writer.writerow({"simulation_time_min": 0, "river_stage_m": 10})
    with pytest.raises(DatasetContractError, match="MISSING_DATASET_COLUMNS"):
        load_hydrometric_csv(path)


def test_phase10_csv_contract_accepts_ordered_history(tmp_path):
    path = tmp_path / "valid.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["simulation_time_min", "river_stage_m", "rainfall_rate_mmh"])
        writer.writeheader()
        for index in range(40):
            writer.writerow({"simulation_time_min": index * 10, "river_stage_m": 10 + index * 0.01, "rainfall_rate_mmh": 2})
    rows = load_hydrometric_csv(path)
    assert len(rows) == 40
    assert rows[0]["simulation_time_min"] == 0
