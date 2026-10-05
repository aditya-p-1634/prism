"""
PRISM Phase A.6 — Hazard Prediction Schemas
===========================================
Pydantic DTO models for A.6 hybrid hazard predictions, evaluations, and benchmarks.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field


class HazardPredictionCreateDTO(BaseModel):
    current_stage_m: float = Field(..., description="Current river stage at monitoring gauge in meters.")
    lag1_stage_m: Optional[float] = Field(None, description="Antecedent river stage 1 step prior in meters.")
    rainfall_rate_mmh: float = Field(0.0, ge=0.0, description="Current precipitation intensity in mm/hr.")
    rolling_rain_30m: Optional[float] = Field(None, ge=0.0, description="30-minute rolling average rainfall in mm/hr.")
    horizon_minutes: float = Field(30.0, gt=0.0, le=360.0, description="Forecast horizon in minutes (up to 360 min).")
    model_type: str = Field(
        "AUTOREGRESSIVE_RIDGE",
        description="Model identifier: AUTOREGRESSIVE_RIDGE, PERSISTENCE_BASELINE, LINEAR_TREND_BASELINE, or BEST_BASELINE."
    )
    simulation_run_id: Optional[str] = Field(None, description="Optional associated simulation run ID.")
    snapshot_id: Optional[str] = Field(None, description="Optional associated state snapshot ID.")
    source_time_min: float = Field(0.0, ge=0.0, description="Source simulation time in minutes.")


class HazardPredictionEvaluateDTO(BaseModel):
    actual_value: float = Field(..., description="Actual observed river stage in meters for residual evaluation.")


class HazardPredictionResponseDTO(BaseModel):
    id: str
    simulation_run_id: Optional[str] = None
    snapshot_id: Optional[str] = None
    hazard_type: str
    target_metric: str
    source_time_min: float
    target_time_min: float
    horizon_minutes: float
    predicted_value: float
    raw_model_value: float
    lower_bound: float
    upper_bound: float
    uncertainty_metric: float
    confidence: Optional[float] = None
    model_name: str
    model_version: str
    method: str
    validation_status: str
    validation_reason: Optional[str] = None
    lifecycle_state: Optional[str] = "VALIDATED"
    feature_provenance: Dict[str, Any] = Field(default_factory=dict)
    domain_alerts: List[Dict[str, Any]] = Field(default_factory=list)
    actual_value: Optional[float] = None
    evaluation_error: Optional[float] = None
    created_at: Optional[datetime] = None


class ModelBenchmarkMetricsDTO(BaseModel):
    chronological_splits: Dict[str, Any]
    validation_metrics: Dict[str, float]
    test_evaluation_benchmark: Dict[str, Dict[str, Any]]
    benchmark_comparison: Optional[Dict[str, Any]] = None
    multi_horizon_benchmarks: Optional[Dict[str, Any]] = None
    dataset_notice: str
