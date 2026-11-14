"""Leakage-safe, baseline-first validation for hydrometric prediction.

This module deliberately evaluates supplied data without bundling or inventing
real observations. The caller must provide a source manifest and decide
whether the dataset is verified for research use.
"""

import csv
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

import numpy as np

from app.engines.e1_hazard.prediction.features import FeatureExtractor
from app.engines.e1_hazard.prediction.models import (
    AutoregressiveRidgeModel,
    LinearTrendBaselineModel,
    PersistenceBaselineModel,
    compute_regression_metrics,
)


REQUIRED_COLUMNS = {"river_stage_m", "rainfall_rate_mmh"}


class DatasetContractError(ValueError):
    """Raised when a supplied validation dataset is unsafe or ambiguous."""


def _finite(value: Any, name: str) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise DatasetContractError(f"INVALID_DATASET_VALUE: {name} must be numeric") from exc
    if not math.isfinite(parsed):
        raise DatasetContractError(f"INVALID_DATASET_VALUE: {name} must be finite")
    return parsed


def load_hydrometric_csv(path: str | Path) -> List[Dict[str, Any]]:
    """Load and validate the minimal external hydrometric CSV contract.

    Required columns are ``simulation_time_min``, ``river_stage_m``, and
    ``rainfall_rate_mmh``. ``source_time`` is retained as provenance when
    supplied but is not used as a model feature.
    """
    csv_path = Path(path)
    if not csv_path.is_file():
        raise DatasetContractError(f"DATASET_NOT_FOUND: {csv_path}")

    with csv_path.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        columns = set(reader.fieldnames or [])
        missing = {"simulation_time_min", *REQUIRED_COLUMNS} - columns
        if missing:
            raise DatasetContractError(f"MISSING_DATASET_COLUMNS: {sorted(missing)}")

        rows: List[Dict[str, Any]] = []
        previous_time = None
        for index, raw in enumerate(reader):
            time_min = _finite(raw.get("simulation_time_min"), f"row {index} simulation_time_min")
            if previous_time is not None and time_min <= previous_time:
                raise DatasetContractError("NON_MONOTONIC_TIME: observations must be strictly increasing")
            previous_time = time_min
            rows.append({
                "simulation_time_min": time_min,
                "river_stage_m": _finite(raw.get("river_stage_m"), f"row {index} river_stage_m"),
                "rainfall_rate_mmh": _finite(raw.get("rainfall_rate_mmh"), f"row {index} rainfall_rate_mmh"),
                "source_time": raw.get("source_time") or raw.get("timestamp"),
            })

    if len(rows) < 30:
        raise DatasetContractError("INSUFFICIENT_DATASET_HISTORY: at least 30 ordered observations are required")
    return rows


def _assign_chronological_splits(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Assign fixed chronological 60/20/20 splits without shuffling."""
    n = len(rows)
    train_end = max(1, int(n * 0.6))
    val_end = max(train_end + 1, int(n * 0.8))
    result = []
    for index, row in enumerate(rows):
        copied = dict(row)
        copied["split_assignment"] = "TRAIN" if index < train_end else "VAL" if index < val_end else "TEST"
        result.append(copied)
    return result


def _evaluate_horizon(rows: Sequence[Dict[str, Any]], horizon_steps: int) -> Dict[str, Any]:
    prepared = _assign_chronological_splits(rows)
    X, y, splits = FeatureExtractor.build_dataset_from_series(prepared, horizon_steps=horizon_steps)
    train = np.array([split == "TRAIN" for split in splits])
    val = np.array([split == "VAL" for split in splits])
    test = np.array([split == "TEST" for split in splits])
    if not train.any() or not val.any() or not test.any():
        raise DatasetContractError(f"INSUFFICIENT_SPLIT_SAMPLES: horizon_steps={horizon_steps}")

    ridge = AutoregressiveRidgeModel(alpha=0.1).fit(X[train], y[train])
    persistence = PersistenceBaselineModel()
    trend = LinearTrendBaselineModel(sample_interval_minutes=10.0)
    models = {
        "AUTOREGRESSIVE_RIDGE": ridge.predict(X[test]),
        "PERSISTENCE_BASELINE": persistence.predict(X[test]),
        "LINEAR_TREND_BASELINE": trend.predict(X[test]),
    }
    metrics = {name: compute_regression_metrics(y[test], prediction) for name, prediction in models.items()}
    best = min(metrics, key=lambda name: metrics[name]["rmse"])
    return {
        "horizon_minutes": horizon_steps * 10,
        "sample_counts": {"train": int(train.sum()), "validation": int(val.sum()), "test": int(test.sum())},
        "metrics": metrics,
        "best_model_by_test_rmse": best,
        "ml_outperformed_all_baselines": best == "AUTOREGRESSIVE_RIDGE",
    }


def evaluate_hydrometric_series(
    rows: Sequence[Dict[str, Any]],
    *,
    source_manifest: Dict[str, Any],
    horizons: Tuple[int, ...] = (1, 3, 6, 12),
) -> Dict[str, Any]:
    """Evaluate multiple horizons and return a provenance-rich report."""
    if not isinstance(source_manifest, dict) or not source_manifest.get("dataset_id"):
        raise DatasetContractError("MISSING_SOURCE_MANIFEST: dataset_id is required")
    if not rows:
        raise DatasetContractError("EMPTY_DATASET: at least one observation is required")
    reports = [_evaluate_horizon(rows, horizon) for horizon in horizons]
    return {
        "report_version": "phase10-v1",
        "dataset": {
            **source_manifest,
            "row_count": len(rows),
            "dataset_class": source_manifest.get("dataset_class", "EXTERNAL_UNVERIFIED"),
        },
        "split_policy": {
            "method": "STRICT_CHRONOLOGICAL_60_20_20",
            "shuffle": False,
            "boundary_samples_discarded": True,
            "future_target_leakage": False,
        },
        "horizons": reports,
        "operational_claim_allowed": source_manifest.get("verified", False) is True,
        "limitations": [
            "Metrics are dataset-specific and do not establish generalization beyond the supplied domain.",
            "Prediction intervals require separate calibration against ground-truth observations.",
            "A verified real-world manifest is required before operational claims are allowed.",
        ],
    }


def save_report(report: Dict[str, Any], path: str | Path) -> None:
    """Persist a deterministic JSON report for CI or research review."""
    Path(path).write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
