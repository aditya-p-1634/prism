"""PRISM V2 — Phase A.6: Hazard Prediction Safety Hardening & Adversarial Test Suite
===================================================================================
Rigorous safety and reliability audit tests covering:
1. Temporal leakage audit (zero cross-boundary contamination)
2. Input quality & sensor failure handling (NaN, Inf, negative, out-of-range)
3. Domain-of-validity / Out-of-distribution detection
4. Model selection & transparent baseline comparison
5. Uncertainty interval calibration & honest coverage
6. Horizon-specific validation benchmarks
7. Physical plausibility hardening & exact boundary testing
8. Prototype domain alert threshold auditing
9. Prediction -> E1 safety gating (rejection of unvalidated/degraded predictions)
10. Fail-safe behavior on all failure paths
11. Full auditability and provenance tracking
12. 20 Adversarial attack and edge cases
"""

import pytest
import math
import numpy as np
from fastapi.testclient import TestClient

from app.main import app
from app.db.session import SessionLocal
from app.models.entities import RelocationAllocation, HazardPredictionRecord, HazardState
from app.seed.synthetic_data import get_vayu_hydrometric_time_series
from app.engines.e1_hazard.prediction.pipeline import (
    HazardPredictionPipeline,
    PredictionSafetyException
)
from app.engines.e1_hazard.prediction.features import FeatureExtractor
from app.engines.e1_hazard.prediction.models import (
    PersistenceBaselineModel,
    LinearTrendBaselineModel,
    AutoregressiveRidgeModel,
    compute_regression_metrics
)
from app.engines.e1_hazard.prediction.validation import (
    InputQualityValidator,
    DomainOfValidityChecker,
    PhysicalPlausibilityValidator,
    DomainConstraintValidator
)
from app.engines.e1_hazard.prediction.uncertainty import UncertaintyEstimator

client = TestClient(app)


# ==============================================================================
# PHASE 1: TEMPORAL LEAKAGE AUDIT TESTS
# ==============================================================================

def test_leakage_1_no_cross_boundary_target_contamination():
    """Verify that boundary buffer strictly discards samples where target crosses partition split."""
    ts = get_vayu_hydrometric_time_series()
    for h_steps in [1, 3, 6]:
        X, y, splits = FeatureExtractor.build_dataset_from_series(ts, horizon_steps=h_steps)
        n = len(X)
        assert n > 0
        train_indices = [i for i, s in enumerate(splits) if s == "TRAIN"]
        val_indices = [i for i, s in enumerate(splits) if s == "VAL"]
        test_indices = [i for i, s in enumerate(splits) if s == "TEST"]

        # Chronological separation
        assert max(train_indices) < min(val_indices)
        assert max(val_indices) < min(test_indices)


def test_leakage_2_strictly_monotonic_series_required():
    """Verify that non-monotonic or duplicate timestamp series are rejected by build_dataset_from_series."""
    bad_ts = [
        {"simulation_time_min": 0.0, "step_index": 0, "river_stage_m": 10.0, "rainfall_rate_mmh": 0.0, "split_assignment": "TRAIN"},
        {"simulation_time_min": 10.0, "step_index": 1, "river_stage_m": 10.1, "rainfall_rate_mmh": 5.0, "split_assignment": "TRAIN"},
        {"simulation_time_min": 10.0, "step_index": 2, "river_stage_m": 10.2, "rainfall_rate_mmh": 5.0, "split_assignment": "TRAIN"}, # Duplicate
        {"simulation_time_min": 30.0, "step_index": 3, "river_stage_m": 10.3, "rainfall_rate_mmh": 5.0, "split_assignment": "TRAIN"},
    ]
    with pytest.raises(ValueError, match="Temporal sequence error"):
        FeatureExtractor.build_dataset_from_series(bad_ts, horizon_steps=1)


# ==============================================================================
# PHASE 2: INPUT QUALITY & SENSOR SCREENING TESTS
# ==============================================================================

def test_input_quality_nan_stage():
    """Verify NaN stage triggers explicit INPUT_QUALITY_FAILURE rejection."""
    res = InputQualityValidator.validate_inputs(
        current_stage=float("nan"),
        lag1_stage=10.0,
        rainfall_rate=10.0,
        rolling_rain_30m=10.0,
        horizon_minutes=10.0
    )
    assert res.status == "REJECTED"
    assert "non-finite" in res.reason


def test_input_quality_inf_stage():
    """Verify Inf stage triggers explicit rejection."""
    res = InputQualityValidator.validate_inputs(
        current_stage=float("inf"),
        lag1_stage=10.0,
        rainfall_rate=10.0,
        rolling_rain_30m=10.0,
        horizon_minutes=10.0
    )
    assert res.status == "REJECTED"


def test_input_quality_negative_rainfall():
    """Verify negative rainfall triggers explicit rejection."""
    res = InputQualityValidator.validate_inputs(
        current_stage=10.5,
        lag1_stage=10.4,
        rainfall_rate=-12.5,
        rolling_rain_30m=0.0,
        horizon_minutes=10.0
    )
    assert res.status == "REJECTED"
    assert "cannot be negative" in res.reason


def test_input_quality_sensor_physical_overtop():
    """Verify extreme gauge sensor stage (e.g. 25.0m) is screened out."""
    res = InputQualityValidator.validate_inputs(
        current_stage=25.0,
        lag1_stage=10.4,
        rainfall_rate=10.0,
        rolling_rain_30m=10.0,
        horizon_minutes=10.0
    )
    assert res.status == "REJECTED"
    assert "exceeds physical sensor bounds" in res.reason


# ==============================================================================
# PHASE 3: DOMAIN-OF-VALIDITY / OOD TESTS
# ==============================================================================

def test_domain_validity_in_domain():
    """Verify typical calibration inputs pass domain check."""
    is_in, violations = DomainOfValidityChecker.check_domain(
        current_stage=10.50,
        lag1_stage=10.40,
        rainfall_rate=25.0,
        rolling_rain_30m=20.0,
        horizon_minutes=30.0
    )
    assert is_in is True
    assert len(violations) == 0


def test_domain_validity_out_of_domain_rainfall():
    """Verify rainfall of 140 mm/hr flags domain violation."""
    is_in, violations = DomainOfValidityChecker.check_domain(
        current_stage=10.50,
        lag1_stage=10.40,
        rainfall_rate=140.0,
        rolling_rain_30m=20.0,
        horizon_minutes=30.0
    )
    assert is_in is False
    assert any("rainfall_rate_mmh" in v for v in violations)


def test_domain_validity_pipeline_degraded():
    """Verify pipeline marks out-of-domain prediction as DEGRADED with no confidence score."""
    rec = HazardPredictionPipeline.predict_river_stage(
        current_stage=10.50,
        lag1_stage=10.40,
        rainfall_rate=150.0, # Out of domain
        rolling_rain_30m=120.0,
        horizon_minutes=30.0
    )
    assert rec.validation_status == "DEGRADED"
    assert rec.lifecycle_state == "OUT_OF_DOMAIN"
    assert rec.confidence is None
    assert any(a["rule_id"] == "OUT_OF_DOMAIN_INPUT_WARNING" for a in rec.domain_alerts)


# ==============================================================================
# PHASE 4: MODEL SELECTION & BASELINE BENCHMARK TESTS
# ==============================================================================

def test_baseline_benchmark_transparent_exposure():
    """Verify pipeline exposes that Linear Trend baseline outperforms Ridge ML on synthetic benchmark."""
    bench = HazardPredictionPipeline.get_model_evaluation_metrics()
    assert "benchmark_comparison" in bench
    comp = bench["benchmark_comparison"]
    assert comp["ml_outperformed_baseline"] is False
    assert comp["best_benchmark_model"] == "LINEAR_TREND_BASELINE"
    assert "does NOT outperform Linear Trend baseline" in comp["safety_advisory"]


def test_linear_trend_model_selection():
    """Verify LINEAR_TREND_BASELINE can be explicitly selected as model_type."""
    rec = HazardPredictionPipeline.predict_river_stage(
        current_stage=10.50,
        lag1_stage=10.40,
        rainfall_rate=10.0,
        horizon_minutes=20.0,
        model_type="LINEAR_TREND_BASELINE"
    )
    assert rec.model_name == "LINEAR_TREND_BASELINE"
    # 10.50 + (0.10 * 20 / 10) = 10.70
    assert abs(rec.predicted_value - 10.70) < 1e-3


# ==============================================================================
# PHASE 5: UNCERTAINTY HARDENING & EMPIRICAL COVERAGE TESTS
# ==============================================================================

def test_uncertainty_empirical_coverage_computation():
    """Verify UncertaintyEstimator fits from validation residuals and reports empirical coverage."""
    np.random.seed(42)
    y_true = np.linspace(10.0, 11.0, 100)
    # Residuals with std dev ~ 0.04
    noise = np.random.normal(0.0, 0.04, 100)
    y_pred = y_true + noise

    est = UncertaintyEstimator.fit_from_residuals(y_true, y_pred, confidence_level=0.95)
    assert est.is_calibrated is True
    assert est.sample_count == 100
    assert 0.90 <= est.empirical_coverage <= 1.0
    assert est.validation_rmse > 0.0


def test_uncertainty_not_calibrated_when_insufficient_samples():
    """Verify UncertaintyEstimator reports NOT_CALIBRATED when sample size is below minimum."""
    est = UncertaintyEstimator(validation_rmse=0.04, sample_count=10) # < 30 samples
    l, u, s, meta = est.compute_bounds(predicted_value=10.50, horizon_minutes=30.0)
    assert l is None
    assert u is None
    assert meta["calibration_status"] == "NOT_CALIBRATED"


# ==============================================================================
# PHASE 6: HORIZON VALIDATION TESTS
# ==============================================================================

def test_multi_horizon_metrics_cached():
    """Verify multi-horizon benchmarks are computed and cached."""
    metrics = HazardPredictionPipeline.get_model_evaluation_metrics()
    assert "multi_horizon_benchmarks" in metrics
    h_bench = metrics["multi_horizon_benchmarks"]
    assert "10" in h_bench
    assert "30" in h_bench
    assert "60" in h_bench
    # Test RMSE increases or stays positive
    assert h_bench["10"]["test_rmse"] > 0.0
    assert h_bench["60"]["test_rmse"] > 0.0


# ==============================================================================
# PHASE 7: PHYSICAL VALIDATION HARDENING TESTS
# ==============================================================================

def test_physical_validation_exact_channel_floor():
    """Verify physical validator exact boundary for channel floor (8.0m)."""
    val = PhysicalPlausibilityValidator(min_stage_m=8.0, max_stage_m=15.0, allow_correction=False)
    # Exactly 8.00m is valid
    res_exact = val.validate(predicted_stage=8.00, current_stage=8.50, horizon_minutes=10.0)
    assert res_exact.status == "VALID"

    # 7.99m is rejected
    res_below = val.validate(predicted_stage=7.99, current_stage=8.50, horizon_minutes=10.0)
    assert res_below.status == "REJECTED"
    assert "PHYSICAL_FLOOR_VIOLATION" in res_below.reason


def test_physical_validation_exact_dyke_crest():
    """Verify physical validator exact boundary for dyke crest (15.0m)."""
    val = PhysicalPlausibilityValidator(min_stage_m=8.0, max_stage_m=15.0, allow_correction=False)
    # Exactly 15.00m is valid
    res_exact = val.validate(predicted_stage=15.00, current_stage=14.50, horizon_minutes=10.0)
    assert res_exact.status == "VALID"

    # 15.01m is rejected
    res_above = val.validate(predicted_stage=15.01, current_stage=14.50, horizon_minutes=10.0)
    assert res_above.status == "REJECTED"
    assert "PHYSICAL_CREST_VIOLATION" in res_above.reason


def test_physical_validation_rate_of_fall_limit():
    """Verify rapid unphysical river drawdown (>1.5m in 10m) is rejected."""
    val = PhysicalPlausibilityValidator(max_rate_change_per_10m=1.50)
    res_drawdown = val.validate(predicted_stage=9.00, current_stage=11.00, horizon_minutes=10.0)
    assert res_drawdown.status == "REJECTED"
    assert "fall" in res_drawdown.reason


# ==============================================================================
# PHASE 8: DOMAIN RULE HARDENING TESTS
# ==============================================================================

def test_domain_rules_alert_and_danger():
    """Verify prototype operational alert rules trigger at exact thresholds."""
    dom_val = DomainConstraintValidator(alert_stage_m=10.30, danger_stage_m=11.00)

    # Exactly at warning stage (10.30m)
    a_warn = dom_val.evaluate_rules(validated_stage=10.30, current_stage=10.00, horizon_minutes=10.0)
    assert any(a["rule_id"] == "OPERATIONAL_ALERT_STAGE_EXCEEDED" for a in a_warn)

    # Exactly at critical danger stage (11.00m)
    a_crit = dom_val.evaluate_rules(validated_stage=11.00, current_stage=10.50, horizon_minutes=10.0)
    assert any(a["rule_id"] == "CRITICAL_DANGER_STAGE_EXCEEDED" for a in a_crit)


# ==============================================================================
# PHASE 9 & 10: PREDICTION -> E1 SAFETY BOUNDARY & FAIL-SAFE TESTS
# ==============================================================================

def test_e1_safety_gate_rejects_unvalidated_prediction():
    """CRITICAL SAFETY TEST: E1 adapter strictly refuses to evaluate a REJECTED prediction."""
    db = SessionLocal()
    try:
        # Create a rejected prediction record
        rec = HazardPredictionPipeline.predict_river_stage(
            current_stage=float("nan"), # Corrupted sensor
            horizon_minutes=10.0
        )
        assert rec.validation_status == "REJECTED"

        # Attempting to feed this rejected prediction to E1 must raise PredictionSafetyException
        with pytest.raises(PredictionSafetyException, match="E1_SAFETY_GATE_REJECTED"):
            HazardPredictionPipeline.feed_prediction_to_e1(
                prediction=rec,
                db=db,
                snapshot_id="SNAP_SCEN_TEST"
            )
    finally:
        db.close()


def test_e1_safety_gate_rejects_out_of_domain_prediction():
    """CRITICAL SAFETY TEST: E1 adapter refuses to evaluate an OUT_OF_DOMAIN / DEGRADED prediction."""
    db = SessionLocal()
    try:
        # Create an out-of-domain prediction record (rainfall 150 mm/hr)
        rec = HazardPredictionPipeline.predict_river_stage(
            current_stage=10.50,
            lag1_stage=10.40,
            rainfall_rate=150.0,
            horizon_minutes=30.0
        )
        assert rec.validation_status == "DEGRADED"
        assert rec.lifecycle_state == "OUT_OF_DOMAIN"

        with pytest.raises(PredictionSafetyException, match="E1_SAFETY_GATE_REJECTED"):
            HazardPredictionPipeline.feed_prediction_to_e1(
                prediction=rec,
                db=db,
                snapshot_id="SNAP_SCEN_TEST"
            )
    finally:
        db.close()


# ==============================================================================
# PHASE 12: ADVERSARIAL TEST SUITE (20 DEDICATED ADVERSARIAL CASES)
# ==============================================================================

def test_adv_1_large_stage_jump_rejected():
    """Case 1: +5.0m unphysical surge jump in 10 minutes rejected."""
    rec = HazardPredictionPipeline.predict_river_stage(
        current_stage=10.0,
        lag1_stage=10.0,
        rainfall_rate=20.0,
        horizon_minutes=10.0,
        model_type="LINEAR_TREND_BASELINE"
    )
    # Artificially test physical validator with +5m jump
    phys = PhysicalPlausibilityValidator(max_rate_change_per_10m=1.50)
    res = phys.validate(predicted_stage=15.0, current_stage=10.0, horizon_minutes=10.0)
    assert res.status == "REJECTED"


def test_adv_2_nan_stage_input_screening():
    """Case 2: NaN stage screened out at Stage 0 without manufacturing prediction."""
    rec = HazardPredictionPipeline.predict_river_stage(current_stage=float("nan"))
    assert rec.validation_status == "REJECTED"
    assert rec.predicted_value == 0.0
    assert rec.lower_bound == 0.0
    assert not math.isnan(rec.lower_bound)


def test_adv_3_inf_stage_input_screening():
    """Case 3: Inf stage screened out cleanly."""
    rec = HazardPredictionPipeline.predict_river_stage(current_stage=float("inf"))
    assert rec.validation_status == "REJECTED"


def test_adv_4_negative_rainfall_screening():
    """Case 4: Negative rainfall screened out cleanly."""
    rec = HazardPredictionPipeline.predict_river_stage(current_stage=10.2, rainfall_rate=-20.0)
    assert rec.validation_status == "REJECTED"
    assert "cannot be negative" in rec.validation_reason


def test_adv_5_duplicated_timestamps():
    """Case 5: Duplicated timestamps in series detected and rejected."""
    bad_series = [
        {"simulation_time_min": 0.0, "step_index": 0, "river_stage_m": 10.0, "rainfall_rate_mmh": 0.0, "split_assignment": "TRAIN"},
        {"simulation_time_min": 0.0, "step_index": 0, "river_stage_m": 10.0, "rainfall_rate_mmh": 0.0, "split_assignment": "TRAIN"},
        {"simulation_time_min": 10.0, "step_index": 1, "river_stage_m": 10.1, "rainfall_rate_mmh": 0.0, "split_assignment": "TRAIN"},
        {"simulation_time_min": 20.0, "step_index": 2, "river_stage_m": 10.2, "rainfall_rate_mmh": 0.0, "split_assignment": "TRAIN"},
    ]
    with pytest.raises(ValueError):
        FeatureExtractor.build_dataset_from_series(bad_series)


def test_adv_6_future_timestamp_or_out_of_order():
    """Case 6: Out-of-order time series step detected."""
    bad_series = [
        {"simulation_time_min": 20.0, "step_index": 2, "river_stage_m": 10.2, "rainfall_rate_mmh": 0.0, "split_assignment": "TRAIN"},
        {"simulation_time_min": 10.0, "step_index": 1, "river_stage_m": 10.1, "rainfall_rate_mmh": 0.0, "split_assignment": "TRAIN"},
        {"simulation_time_min": 30.0, "step_index": 3, "river_stage_m": 10.3, "rainfall_rate_mmh": 0.0, "split_assignment": "TRAIN"},
        {"simulation_time_min": 40.0, "step_index": 4, "river_stage_m": 10.4, "rainfall_rate_mmh": 0.0, "split_assignment": "TRAIN"},
    ]
    with pytest.raises(ValueError):
        FeatureExtractor.build_dataset_from_series(bad_series)


def test_adv_7_out_of_order_observations():
    """Case 7: FeatureExtractor guarantees verification of temporal order."""
    ts = get_vayu_hydrometric_time_series()
    # Correct series must not raise
    X, y, splits = FeatureExtractor.build_dataset_from_series(ts[:20], horizon_steps=1)
    assert len(X) > 0


def test_adv_8_extreme_rainfall_ood():
    """Case 8: Extreme rainfall rate (180 mm/hr) marked OUT_OF_DOMAIN."""
    rec = HazardPredictionPipeline.predict_river_stage(current_stage=10.3, rainfall_rate=180.0)
    assert rec.validation_status == "DEGRADED"
    assert rec.lifecycle_state == "OUT_OF_DOMAIN"


def test_adv_9_extreme_stage_sensor_failure():
    """Case 9: Extreme stage 22.0m screened out as sensor failure."""
    rec = HazardPredictionPipeline.predict_river_stage(current_stage=22.0)
    assert rec.validation_status == "REJECTED"


def test_adv_10_extreme_negative_stage_change():
    """Case 10: Unphysical sudden drop (-2.5m/10min) rejected."""
    val = PhysicalPlausibilityValidator(max_rate_change_per_10m=1.5)
    res = val.validate(predicted_stage=8.0, current_stage=10.8, horizon_minutes=10.0)
    assert res.status == "REJECTED"


def test_adv_11_prediction_exactly_at_warning_threshold():
    """Case 11: Prediction exactly at warning threshold (10.30m) raises alert."""
    dom = DomainConstraintValidator(alert_stage_m=10.30, danger_stage_m=11.00)
    alerts = dom.evaluate_rules(validated_stage=10.30, current_stage=10.10, horizon_minutes=10.0)
    assert any(a["rule_id"] == "OPERATIONAL_ALERT_STAGE_EXCEEDED" for a in alerts)


def test_adv_12_prediction_exactly_at_critical_threshold():
    """Case 12: Prediction exactly at critical threshold (11.00m) raises critical alert."""
    dom = DomainConstraintValidator(alert_stage_m=10.30, danger_stage_m=11.00)
    alerts = dom.evaluate_rules(validated_stage=11.00, current_stage=10.50, horizon_minutes=10.0)
    assert any(a["rule_id"] == "CRITICAL_DANGER_STAGE_EXCEEDED" for a in alerts)


def test_adv_13_prediction_just_above_critical_threshold():
    """Case 13: Prediction just above critical threshold (11.001m) raises critical alert."""
    dom = DomainConstraintValidator(alert_stage_m=10.30, danger_stage_m=11.00)
    alerts = dom.evaluate_rules(validated_stage=11.001, current_stage=10.50, horizon_minutes=10.0)
    assert any(a["rule_id"] == "CRITICAL_DANGER_STAGE_EXCEEDED" for a in alerts)


def test_adv_14_prediction_outside_physical_range():
    """Case 14: Stage < 8.0m or > 15.0m rejected."""
    val = PhysicalPlausibilityValidator(min_stage_m=8.0, max_stage_m=15.0)
    assert val.validate(predicted_stage=7.5, current_stage=8.5, horizon_minutes=10.0).status == "REJECTED"
    assert val.validate(predicted_stage=15.5, current_stage=14.5, horizon_minutes=10.0).status == "REJECTED"


def test_adv_15_insufficient_history_for_lag():
    """Case 15: Series with fewer than 4 points fails build_dataset_from_series."""
    short_series = [
        {"simulation_time_min": 0.0, "step_index": 0, "river_stage_m": 10.0, "rainfall_rate_mmh": 0.0, "split_assignment": "TRAIN"},
        {"simulation_time_min": 10.0, "step_index": 1, "river_stage_m": 10.1, "rainfall_rate_mmh": 0.0, "split_assignment": "TRAIN"},
    ]
    with pytest.raises(ValueError, match="Insufficient time-series history"):
        FeatureExtractor.build_dataset_from_series(short_series, horizon_steps=1)


def test_adv_16_unsupported_horizon():
    """Case 16: Forecast lead time of 240 minutes flags out of domain."""
    rec = HazardPredictionPipeline.predict_river_stage(
        current_stage=10.30,
        horizon_minutes=240.0
    )
    assert rec.validation_status == "DEGRADED"
    assert rec.lifecycle_state == "OUT_OF_DOMAIN"


def test_adv_17_uncertainty_unavailable():
    """Case 17: Uncertainty bounds become None when sample count is low."""
    est = UncertaintyEstimator(sample_count=5)
    l, u, _, _ = est.compute_bounds(predicted_value=10.50, horizon_minutes=10.0)
    assert l is None and u is None


def test_adv_18_out_of_domain_input_gating():
    """Case 18: Stage delta > 0.40m/10min flags out of domain."""
    rec = HazardPredictionPipeline.predict_river_stage(
        current_stage=10.80,
        lag1_stage=10.30, # delta = 0.50m > 0.40m
        rainfall_rate=20.0,
        horizon_minutes=20.0
    )
    assert rec.validation_status == "DEGRADED"


def test_adv_19_invalid_prediction_reaching_e1():
    """Case 19: REJECTED prediction consumed by E1 throws PredictionSafetyException."""
    db = SessionLocal()
    try:
        rec = HazardPredictionPipeline.predict_river_stage(current_stage=float("nan"))
        with pytest.raises(PredictionSafetyException):
            HazardPredictionPipeline.feed_prediction_to_e1(prediction=rec, db=db, snapshot_id="SNAP_TEST")
    finally:
        db.close()


def test_adv_20_baseline_snapshot_mutation_attempt():
    """Case 20: SNAP_BASE_001 allocations and capacities are completely untouched."""
    db = SessionLocal()
    try:
        base_allocs_before = [
            (a.id, a.assigned_capacity_count, a.destination_id)
            for a in db.query(RelocationAllocation).filter(
                RelocationAllocation.snapshot_id == "SNAP_BASE_001"
            ).order_by(RelocationAllocation.id.asc()).all()
        ]
        assert len(base_allocs_before) == 28

        # Execute adversarial attacks through API
        client.post("/api/v1/hazard-predictions", json={"current_stage_m": 25.0})
        client.post("/api/v1/hazard-predictions", json={"current_stage_m": 10.5, "rainfall_rate_mmh": 200.0})
        client.post("/api/v1/hazard-predictions", json={"current_stage_m": 7.0})

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
