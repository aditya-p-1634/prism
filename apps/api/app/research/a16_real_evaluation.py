"""Evaluate PRISM stage forecasts on irregular real telemetry intervals."""

import csv
import json
from pathlib import Path
from typing import Any, Dict, Sequence

import numpy as np

from app.engines.e1_hazard.prediction.models import (
    AutoregressiveRidgeModel,
    LinearTrendBaselineModel,
    PersistenceBaselineModel,
    compute_regression_metrics,
)


def load_canonical_csv(path: str | Path, station_code: str) -> list[dict[str, Any]]:
    rows = []
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if row.get("station_code") == station_code:
                rows.append({**row, "simulation_time_min": float(row["simulation_time_min"]), "river_stage_m": float(row["river_stage_m"])})
    rows.sort(key=lambda row: row["simulation_time_min"])
    if len(rows) < 30:
        raise ValueError("REAL_EVALUATION_INSUFFICIENT_ROWS: at least 30 station rows are required")
    return rows


def evaluate_irregular_stage_series(
    rows: Sequence[dict[str, Any]],
    *,
    dataset_id: str,
    station_code: str,
    max_gap_minutes: float = 90.0,
) -> dict[str, Any]:
    if not rows:
        raise ValueError("REAL_EVALUATION_EMPTY_SERIES")
    split_index = {"TRAIN": int(len(rows) * 0.6), "VAL": int(len(rows) * 0.8)}
    X, y, split_labels, horizons = [], [], [], []
    discarded_gaps = 0
    discarded_boundaries = 0
    for index in range(len(rows) - 1):
        current = rows[index]
        target = rows[index + 1]
        gap = target["simulation_time_min"] - current["simulation_time_min"]
        if gap <= 0 or gap > max_gap_minutes:
            discarded_gaps += 1
            continue
        current_split = "TRAIN" if index < split_index["TRAIN"] else "VAL" if index < split_index["VAL"] else "TEST"
        target_index = index + 1
        target_split = "TRAIN" if target_index < split_index["TRAIN"] else "VAL" if target_index < split_index["VAL"] else "TEST"
        if current_split != target_split:
            discarded_boundaries += 1
            continue
        stage = current["river_stage_m"]
        lag = rows[index - 1]["river_stage_m"] if index else stage
        X.append([1.0, stage, lag, stage - lag, 0.0, 0.0, gap])
        y.append(target["river_stage_m"])
        split_labels.append(current_split)
        horizons.append(gap)

    X = np.asarray(X, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    split_labels = np.asarray(split_labels)
    masks = {name: split_labels == name for name in ("TRAIN", "VAL", "TEST")}
    if any(not mask.any() for mask in masks.values()):
        raise ValueError("REAL_EVALUATION_INSUFFICIENT_SPLIT_SAMPLES")

    ridge = AutoregressiveRidgeModel(alpha=0.1).fit(X[masks["TRAIN"]], y[masks["TRAIN"]])
    persistence = PersistenceBaselineModel()
    trend = LinearTrendBaselineModel(sample_interval_minutes=60.0)
    predictions = {
        "AUTOREGRESSIVE_RIDGE": ridge.predict(X[masks["TEST"]]),
        "PERSISTENCE_BASELINE": persistence.predict(X[masks["TEST"]]),
        "LINEAR_TREND_BASELINE": trend.predict(X[masks["TEST"]]),
    }
    metrics = {name: compute_regression_metrics(y[masks["TEST"]], prediction) for name, prediction in predictions.items()}
    best_model = min(metrics, key=lambda name: metrics[name]["rmse"])
    validation_residuals = np.abs(y[masks["VAL"]] - ridge.predict(X[masks["VAL"]]))
    conformal_q = float(np.quantile(validation_residuals, 0.95, method="higher")) if len(validation_residuals) else None
    test_ridge = predictions["AUTOREGRESSIVE_RIDGE"]
    test_coverage = float(np.mean(np.abs(y[masks["TEST"]] - test_ridge) <= conformal_q)) if conformal_q is not None else None
    return {
        "report_version": "phase16-v1",
        "dataset_id": dataset_id,
        "station_code": station_code,
        "measurement_target": "NEXT_OBSERVED_RIVER_STAGE_M",
        "feature_policy": "stage-only; rainfall intentionally absent from source",
        "split_policy": "chronological 60/20/20 with cross-boundary samples discarded",
        "source_rows": len(rows),
        "usable_samples": int(len(y)),
        "train_samples": int(masks["TRAIN"].sum()),
        "validation_samples": int(masks["VAL"].sum()),
        "test_samples": int(masks["TEST"].sum()),
        "discarded_long_or_invalid_gaps": discarded_gaps,
        "discarded_split_boundaries": discarded_boundaries,
        "metrics": metrics,
        "best_model_by_test_rmse": best_model,
        "uncertainty": {
            "method": "VALIDATION_ABSOLUTE_RESIDUAL_95TH_PERCENTILE",
            "interval_half_width_m": conformal_q,
            "test_coverage": test_coverage,
            "operationally_calibrated": False,
        },
        "operational_claim_allowed": False,
        "limitations": [
            "Rainfall is not present in the evaluated source and is not inferred.",
            "Next-observation forecasting is not equivalent to a fixed operational lead time.",
            "The source is historical and station-specific; generalization is unverified.",
            "No flood threshold or discharge conversion is applied.",
        ],
    }


def save_json(report: dict[str, Any], path: str | Path) -> None:
    Path(path).write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
