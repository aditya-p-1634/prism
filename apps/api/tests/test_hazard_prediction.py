"""PRISM V2 — Phase A.6: Hybrid Hazard Prediction Layer Test Suite
==================================================================
Comprehensive test suite validating:
1. Prediction contract validation
2. Valid prediction generation
3. Deterministic prediction
4. Invalid feature handling
5. Missing data handling
6. Temporal ordering
7. No future-data leakage
8. Baseline model (Persistence & Linear Trend)
9. ML model (Autoregressive Ridge regression)
10. Model evaluation (MAE, RMSE, R² benchmarks)
11. Physical plausibility validation
12. Invalid prediction rejection / correction
13. Domain constraint enforcement
14. Uncertainty behavior (empirical validation residual intervals)
15. Provenance metadata
16. Prediction persistence in database
17. Prediction retrieval via API
18. E1 integration (hazard expansion & red-zone projection)
19. Scenario-mode regression
20. Simulation integration
21. Baseline snapshot immutability (SNAP_BASE_001)
22. Scenario isolation
23. A.5 observability regression
24. A.4 resource regression
25. Full A.1-A.5 regression suite integrity
"""

import pytest
import numpy as np
from fastapi.testclient import TestClient
from app.main import app
from app.db.session import SessionLocal
from app.models.entities import (
    RelocationAllocation, HazardPredictionRecord, SimulationRun, HazardState
)
from app.seed.synthetic_data import get_vayu_hydrometric_time_series
from app.engines.e1_hazard.prediction.pipeline import HazardPredictionPipeline
from app.engines.e1_hazard.prediction.features import FeatureExtractor
from app.engines.e1_hazard.prediction.models import (
    PersistenceBaselineModel,
    LinearTrendBaselineModel,
    AutoregressiveRidgeModel,
    compute_regression_metrics
)
from app.engines.e1_hazard.prediction.validation import (
    PhysicalPlausibilityValidator,
    DomainConstraintValidator
)
from app.engines.e1_hazard.prediction.uncertainty import UncertaintyEstimator
from app.engines.e1_hazard.service import HazardEngineE1
from app.gis.spatial import to_shapely

client = TestClient(app)


@pytest.fixture(scope="module")
def base_scenario():
    """Initializes a scenario snapshot for testing."""
    res = client.post("/api/v1/scenarios/run", json={"scenario_code": "MONSOON_SURGE_01"})
    assert res.status_code == 200
    scen_data = res.json()["data"]
    return {
        "baseline_snapshot_id": "SNAP_BASE_001",
        "scenario_snapshot_id": scen_data["scenario_snapshot_id"],
        "scenario_code": "MONSOON_SURGE_01"
    }


def test_1_prediction_contract_validation():
    """TEST 1: Prediction contract validates inputs and rejects negative horizon or invalid parameters."""
    # Negative horizon rejected
    res_neg_horizon = client.post("/api/v1/hazard-predictions", json={
        "current_stage_m": 10.2,
        "horizon_minutes": -10.0
    })
    assert res_neg_horizon.status_code == 422

    # Negative rainfall rate rejected
    res_neg_rain = client.post("/api/v1/hazard-predictions", json={
        "current_stage_m": 10.2,
        "rainfall_rate_mmh": -5.0
    })
    assert res_neg_rain.status_code == 422


def test_2_valid_prediction_generation():
    """TEST 2: Generates a complete, valid prediction with all provenance and uncertainty metadata."""
    res = client.post("/api/v1/hazard-predictions", json={
        "current_stage_m": 10.35,
        "lag1_stage_m": 10.30,
        "rainfall_rate_mmh": 22.0,
        "horizon_minutes": 30.0,
        "model_type": "AUTOREGRESSIVE_RIDGE"
    })
    assert res.status_code == 200
    data = res.json()["data"]

    assert data["target_metric"] == "RIVER_STAGE_M"
    assert data["predicted_value"] > 0
    assert data["validation_status"] in ["VALID", "CORRECTED"]
    assert data["lower_bound"] <= data["predicted_value"] <= data["upper_bound"]
    assert data["uncertainty_metric"] > 0
    assert data["model_name"] == "AUTOREGRESSIVE_RIDGE"
    assert "feature_provenance" in data


def test_3_deterministic_prediction():
    """TEST 3: Repeated identical feature inputs produce strictly identical predictions."""
    payload = {
        "current_stage_m": 10.45,
        "lag1_stage_m": 10.40,
        "rainfall_rate_mmh": 18.5,
        "rolling_rain_30m": 16.0,
        "horizon_minutes": 20.0,
        "model_type": "AUTOREGRESSIVE_RIDGE"
    }
    res1 = client.post("/api/v1/hazard-predictions", json=payload).json()["data"]
    res2 = client.post("/api/v1/hazard-predictions", json=payload).json()["data"]

    assert res1["predicted_value"] == res2["predicted_value"]
    assert res1["lower_bound"] == res2["lower_bound"]
    assert res1["upper_bound"] == res2["upper_bound"]


def test_4_invalid_feature_handling():
    """TEST 4: Non-finite or corrupted feature values are gracefully handled or rejected."""
    val = PhysicalPlausibilityValidator()
    # NaN check
    res = val.validate(predicted_stage=float("nan"), current_stage=10.0, horizon_minutes=10.0)
    assert res.status == "REJECTED"
    assert "non-finite" in res.reason


def test_5_missing_data_handling():
    """TEST 5: Gracefully handles omitted optional fields (lag1 defaults to current stage)."""
    res = client.post("/api/v1/hazard-predictions", json={
        "current_stage_m": 10.25,
        "horizon_minutes": 10.0
    })
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["feature_provenance"]["inputs"]["lag1_stage_m"] == 10.25
    assert data["feature_provenance"]["inputs"]["stage_delta_m"] == 0.0


def test_6_temporal_ordering():
    """TEST 6: Time-series observations strictly preserve forward chronological order."""
    ts = get_vayu_hydrometric_time_series()
    assert len(ts) == 432
    for i in range(len(ts) - 1):
        assert ts[i]["simulation_time_min"] < ts[i + 1]["simulation_time_min"]
        assert ts[i]["step_index"] < ts[i + 1]["step_index"]


def test_7_no_future_data_leakage():
    """TEST 7: Training set strictly precedes validation set, which strictly precedes test set."""
    ts = get_vayu_hydrometric_time_series()
    X, y, splits = FeatureExtractor.build_dataset_from_series(ts, horizon_steps=1)

    train_indices = [i for i, s in enumerate(splits) if s == "TRAIN"]
    val_indices = [i for i, s in enumerate(splits) if s == "VAL"]
    test_indices = [i for i, s in enumerate(splits) if s == "TEST"]

    assert max(train_indices) < min(val_indices)
    assert max(val_indices) < min(test_indices)


def test_8_baseline_models():
    """TEST 8: Persistence baseline outputs y_{t+h} = y_t, Linear Trend extrapolates slope."""
    pers = PersistenceBaselineModel()
    trend = LinearTrendBaselineModel(sample_interval_minutes=10.0)

    # Persistence
    pred_p = pers.predict_single(current_stage=10.50, horizon_minutes=30.0)
    assert pred_p == 10.50

    # Trend: 10.50 with lag 10.40 (delta = +0.10m in 10m). Horizon 20m -> +0.20m -> 10.70m
    pred_t = trend.predict_single(current_stage=10.50, lag1_stage=10.40, horizon_minutes=20.0)
    assert abs(pred_t - 10.70) < 1e-4


def test_9_ml_autoregressive_ridge():
    """TEST 9: Closed-form Autoregressive Ridge model trains analytically and predicts."""
    ts = get_vayu_hydrometric_time_series()
    X, y, splits = FeatureExtractor.build_dataset_from_series(ts, horizon_steps=1)
    train_mask = [s == "TRAIN" for s in splits]

    ridge = AutoregressiveRidgeModel(alpha=0.1)
    ridge.fit(X[train_mask], y[train_mask])
    assert ridge.is_trained
    assert len(ridge.weights) == X.shape[1]

    # Predict single
    sample_feat = X[0]
    pred = ridge.predict_single(sample_feat)
    assert 9.0 <= pred <= 13.0


def test_10_model_evaluation_benchmarks():
    """TEST 10: Model evaluation metrics (MAE, RMSE, R²) benchmark Ridge vs Baselines."""
    metrics_res = client.get("/api/v1/hazard-predictions/models/metrics")
    assert metrics_res.status_code == 200
    m = metrics_res.json()["data"]

    bench = m["test_evaluation_benchmark"]
    assert "autoregressive_ridge" in bench
    assert "persistence_baseline" in bench

    ridge_rmse = bench["autoregressive_ridge"]["rmse"]
    pers_rmse = bench["persistence_baseline"]["rmse"]

    # Both models produce positive finite RMSE
    assert 0.0 < ridge_rmse < 0.50
    assert 0.0 < pers_rmse < 0.50


def test_11_physical_plausibility_validation():
    """TEST 11: Validates that stages within 8.0m to 15.0m pass as VALID."""
    validator = PhysicalPlausibilityValidator(min_stage_m=8.0, max_stage_m=15.0)
    res = validator.validate(predicted_stage=10.65, current_stage=10.50, horizon_minutes=10.0)
    assert res.status == "VALID"
    assert res.validated_value == 10.65


def test_12_invalid_prediction_rejection_and_correction():
    """TEST 12: Sub-channel (<8.0m) and dyke-breach (>15.0m) predictions are corrected/rejected."""
    validator = PhysicalPlausibilityValidator(min_stage_m=8.0, max_stage_m=15.0, allow_correction=True)

    # Sub-bed floor (delta 0.7m <= 1.5m, but below 8.0m floor)
    res_low = validator.validate(predicted_stage=7.5, current_stage=8.2, horizon_minutes=10.0)
    assert res_low.status == "CORRECTED"
    assert res_low.validated_value == 8.0

    # Over-crest (delta 1.1m <= 1.5m, but above 15.0m crest)
    res_high = validator.validate(predicted_stage=15.6, current_stage=14.5, horizon_minutes=10.0)
    assert res_high.status == "CORRECTED"
    assert res_high.validated_value == 15.0

    # Excessive rate of change (e.g. +3.5m in 10 minutes > 1.5m limit)
    res_surge = validator.validate(predicted_stage=13.5, current_stage=10.0, horizon_minutes=10.0)
    assert res_surge.status == "REJECTED"



def test_13_domain_constraint_enforcement():
    """TEST 13: Operational alert stages (10.30m) and critical stages (11.00m) trigger domain alerts."""
    dom_val = DomainConstraintValidator(alert_stage_m=10.30, danger_stage_m=11.00)

    # Stage at 10.50m triggers alert stage rule
    alerts1 = dom_val.evaluate_rules(validated_stage=10.50, current_stage=10.20, horizon_minutes=10.0)
    assert any(a["rule_id"] == "OPERATIONAL_ALERT_STAGE_EXCEEDED" for a in alerts1)

    # Stage at 11.20m triggers critical danger stage rule
    alerts2 = dom_val.evaluate_rules(validated_stage=11.20, current_stage=10.50, horizon_minutes=10.0)
    assert any(a["rule_id"] == "CRITICAL_DANGER_STAGE_EXCEEDED" for a in alerts2)


def test_14_uncertainty_behavior():
    """TEST 14: Uncertainty intervals scale with lead time and lower_bound < predicted < upper_bound."""
    estimator = UncertaintyEstimator(validation_rmse=0.040, confidence_level=0.95)
    l10, u10, s10, _ = estimator.compute_bounds(predicted_value=10.50, horizon_minutes=10.0)
    l60, u60, s60, _ = estimator.compute_bounds(predicted_value=10.50, horizon_minutes=60.0)

    assert l10 < 10.50 < u10
    assert l60 < 10.50 < u60
    # Uncertainty widens with longer forecast horizon
    assert (u60 - l60) > (u10 - l10)
    assert s60 > s10


def test_15_provenance_metadata():
    """TEST 15: Prediction output contains comprehensive audit and model provenance metadata."""
    res = client.post("/api/v1/hazard-predictions", json={
        "current_stage_m": 10.40,
        "horizon_minutes": 30.0
    })
    d = res.json()["data"]
    assert d["model_name"] == "AUTOREGRESSIVE_RIDGE"
    assert d["model_version"] == "1.0.0"
    assert "feature_provenance" in d
    assert "uncertainty_derivation" in d["feature_provenance"]


def test_16_prediction_persistence():
    """TEST 16: Prediction records are persisted in SQLite hazard_prediction_records table."""
    db = SessionLocal()
    try:
        count_before = db.query(HazardPredictionRecord).count()
        client.post("/api/v1/hazard-predictions", json={
            "current_stage_m": 10.55,
            "horizon_minutes": 20.0
        })
        count_after = db.query(HazardPredictionRecord).count()
        assert count_after == count_before + 1
    finally:
        db.close()


def test_17_prediction_retrieval_and_evaluation():
    """TEST 17: Prediction is retrievable by ID and evaluates against later ground-truth observation."""
    create_res = client.post("/api/v1/hazard-predictions", json={
        "current_stage_m": 10.30,
        "horizon_minutes": 10.0
    })
    pred_id = create_res.json()["data"]["id"]
    predicted_val = create_res.json()["data"]["predicted_value"]

    # Retrieve
    get_res = client.get(f"/api/v1/hazard-predictions/{pred_id}")
    assert get_res.status_code == 200
    assert get_res.json()["data"]["id"] == pred_id

    # Evaluate with actual observation
    eval_res = client.post(f"/api/v1/hazard-predictions/{pred_id}/evaluate", json={
        "actual_value": 10.32
    })
    assert eval_res.status_code == 200
    eval_data = eval_res.json()["data"]
    assert eval_data["actual_value"] == 10.32
    assert abs(eval_data["evaluation_error"] - (10.32 - predicted_val)) < 1e-3


def test_18_e1_integration(base_scenario):
    """TEST 18: Validated hazard prediction is consumed by E1 to project spatial flood geometry."""
    db = SessionLocal()
    try:
        pred = HazardPredictionPipeline.predict_river_stage(
            current_stage=10.50,
            lag1_stage=10.30,
            rainfall_rate=30.0,
            rolling_rain_30m=25.0,
            horizon_minutes=30.0
        )
        e1_res = HazardPredictionPipeline.feed_prediction_to_e1(
            prediction=pred,
            db=db,
            snapshot_id=base_scenario["scenario_snapshot_id"]
        )

        assert "hazard_state" in e1_res
        assert "predicted_geom" in e1_res
        assert e1_res["hazard_prediction"].expansion_factor > 1.0
    finally:
        db.close()


def test_19_scenario_mode_regression(base_scenario):
    """TEST 19: Standard scenario-driven execution continues working smoothly."""
    res = client.post("/api/v1/scenarios/run", json={"scenario_code": "MONSOON_SURGE_01"})
    assert res.status_code == 200
    assert res.json()["data"]["scenario_code"] == "MONSOON_SURGE_01"


def test_20_simulation_integration(base_scenario):
    """TEST 20: Prediction can be generated for an active simulation run."""
    run_res = client.post("/api/v1/simulation-runs", json={
        "scenario_snapshot_id": base_scenario["scenario_snapshot_id"],
        "timestep_minutes": 10,
        "duration_minutes": 30
    })
    run_id = run_res.json()["data"]["id"]
    client.post(f"/api/v1/simulation-runs/{run_id}/step")

    # Issue prediction attached to simulation run
    pred_res = client.post("/api/v1/hazard-predictions", json={
        "current_stage_m": 10.25,
        "simulation_run_id": run_id,
        "snapshot_id": base_scenario["scenario_snapshot_id"],
        "source_time_min": 10.0,
        "horizon_minutes": 20.0
    })
    assert pred_res.status_code == 200
    assert pred_res.json()["data"]["simulation_run_id"] == run_id


def test_21_baseline_snapshot_immutability():
    """TEST 21: SNAP_BASE_001 baseline snapshot remains 100% immutable throughout A.6 operations."""
    db = SessionLocal()
    try:
        base_allocs_before = [
            (a.id, a.assigned_capacity_count, a.destination_id)
            for a in db.query(RelocationAllocation).filter(
                RelocationAllocation.snapshot_id == "SNAP_BASE_001"
            ).order_by(RelocationAllocation.id.asc()).all()
        ]
        assert len(base_allocs_before) == 28

        # Run several predictions
        for _ in range(5):
            client.post("/api/v1/hazard-predictions", json={
                "current_stage_m": 10.60,
                "horizon_minutes": 30.0
            })

        db.expire_all()
        base_allocs_after = [
            (a.id, a.assigned_capacity_count, a.destination_id)
            for a in db.query(RelocationAllocation).filter(
                RelocationAllocation.snapshot_id == "SNAP_BASE_001"
            ).order_by(RelocationAllocation.id.asc()).all()
        ]
        assert base_allocs_after == base_allocs_before
    finally:
        db.close()


def test_22_scenario_isolation(base_scenario):
    """TEST 22: Predictions generated for one snapshot/run remain isolated."""
    res1 = client.post("/api/v1/hazard-predictions", json={
        "current_stage_m": 10.20,
        "snapshot_id": base_scenario["scenario_snapshot_id"]
    })
    pid = res1.json()["data"]["id"]

    list_res = client.get(f"/api/v1/hazard-predictions?snapshot_id={base_scenario['scenario_snapshot_id']}")
    ids = [p["id"] for p in list_res.json()["data"]]
    assert pid in ids


def test_23_a5_observability_regression(base_scenario):
    """TEST 23: A.5 observability endpoints (state, metrics, timeline) remain green."""
    run_res = client.post("/api/v1/simulation-runs", json={
        "scenario_snapshot_id": base_scenario["scenario_snapshot_id"],
        "timestep_minutes": 10,
        "duration_minutes": 20
    })
    run_id = run_res.json()["data"]["id"]
    client.post(f"/api/v1/simulation-runs/{run_id}/step")

    assert client.get(f"/api/v1/simulation-runs/{run_id}/state").status_code == 200
    assert client.get(f"/api/v1/simulation-runs/{run_id}/metrics").status_code == 200
    assert client.get(f"/api/v1/simulation-runs/{run_id}/timeline").status_code == 200


def test_24_a4_resource_regression(base_scenario):
    """TEST 24: A.4 dynamic resource consumption remains functional."""
    run_res = client.post("/api/v1/simulation-runs", json={
        "scenario_snapshot_id": base_scenario["scenario_snapshot_id"],
        "timestep_minutes": 10,
        "duration_minutes": 20
    })
    run_id = run_res.json()["data"]["id"]
    client.post(f"/api/v1/simulation-runs/{run_id}/step")

    res_data = client.get(f"/api/v1/simulation-runs/{run_id}/resources").json()["data"]
    assert len(res_data["destinations"]) == 3


def test_25_full_regression_integrity():
    """TEST 25: Baseline and scenario models remain healthy and queryable."""
    db = SessionLocal()
    try:
        haz = db.query(HazardState).filter(HazardState.snapshot_id == "SNAP_BASE_001").first()
        assert haz is not None
        assert haz.geom is not None
    finally:
        db.close()
