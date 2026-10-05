"""
PRISM Phase A.6 — Hazard Prediction API Router
=============================================
Endpoints:
- POST /api/v1/hazard-predictions: Generate and persist a hybrid hazard prediction.
- GET  /api/v1/hazard-predictions/models/metrics: Benchmark evaluation of ML vs Baselines.
- GET  /api/v1/hazard-predictions/{prediction_id}: Retrieve single prediction by ID.
- POST /api/v1/hazard-predictions/{prediction_id}/evaluate: Evaluate prediction against ground-truth observation.
- GET  /api/v1/hazard-predictions: Query predictions by run or snapshot.
"""

import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.entities import HazardPredictionRecord, User
from app.models.enums import RoleEnum
from app.schemas.hazard_prediction import (
    HazardPredictionCreateDTO,
    HazardPredictionResponseDTO,
    HazardPredictionEvaluateDTO,
    ModelBenchmarkMetricsDTO
)
from app.schemas.envelope import ResponseEnvelope
from app.api.deps import require_role
from app.engines.e1_hazard.prediction.pipeline import HazardPredictionPipeline


router = APIRouter(prefix="/hazard-predictions", tags=["Hazard Intelligence & Prediction (E1 - A.6)"])


def _to_dto(rec: HazardPredictionRecord) -> HazardPredictionResponseDTO:
    return HazardPredictionResponseDTO(
        id=rec.id,
        simulation_run_id=rec.simulation_run_id,
        snapshot_id=rec.snapshot_id,
        hazard_type=rec.hazard_type,
        target_metric=rec.target_metric,
        source_time_min=rec.source_time_min,
        target_time_min=rec.target_time_min,
        horizon_minutes=rec.horizon_minutes,
        predicted_value=rec.predicted_value,
        raw_model_value=rec.raw_model_value,
        lower_bound=rec.lower_bound,
        upper_bound=rec.upper_bound,
        uncertainty_metric=rec.uncertainty_metric,
        confidence=rec.confidence,
        model_name=rec.model_name,
        model_version=rec.model_version,
        method=rec.method,
        validation_status=rec.validation_status,
        validation_reason=rec.validation_reason,
        lifecycle_state=getattr(rec, "lifecycle_state", rec.validation_status),
        feature_provenance=rec.feature_provenance or {},
        domain_alerts=rec.domain_alerts or [],
        actual_value=rec.actual_value,
        evaluation_error=rec.evaluation_error,
        created_at=rec.created_at
    )


@router.post("", response_model=ResponseEnvelope[HazardPredictionResponseDTO])
def create_hazard_prediction(
    payload: HazardPredictionCreateDTO,
    current_user: User = Depends(require_role([RoleEnum.AUTHORITY, RoleEnum.ADMIN, RoleEnum.DATA_OPERATOR])),
    db: Session = Depends(get_db)
):
    """
    Executes the hybrid hazard prediction pipeline:
    Features -> ML / Baseline Model -> Physical Gating -> Expert Rules -> Uncertainty.
    """
    lag1 = payload.lag1_stage_m if payload.lag1_stage_m is not None else payload.current_stage_m
    rolling_rain = payload.rolling_rain_30m if payload.rolling_rain_30m is not None else payload.rainfall_rate_mmh

    record = HazardPredictionPipeline.predict_river_stage(
        current_stage=payload.current_stage_m,
        lag1_stage=lag1,
        rainfall_rate=payload.rainfall_rate_mmh,
        rolling_rain_30m=rolling_rain,
        horizon_minutes=payload.horizon_minutes,
        model_type=payload.model_type,
        simulation_run_id=payload.simulation_run_id,
        snapshot_id=payload.snapshot_id,
        source_time_min=payload.source_time_min,
        db=db
    )

    return ResponseEnvelope[HazardPredictionResponseDTO](
        request_id=str(uuid.uuid4()),
        correlation_id=str(uuid.uuid4()),
        snapshot_id=record.snapshot_id or "NONE",
        data=_to_dto(record)
    )


@router.get("/models/metrics", response_model=ResponseEnvelope[ModelBenchmarkMetricsDTO])
def get_model_benchmark_metrics():
    """
    Returns benchmark evaluation metrics comparing the ML Autoregressive Ridge model
    against the deterministic Persistence and Linear Trend baselines on the held-out test split.
    """
    metrics = HazardPredictionPipeline.get_model_evaluation_metrics()
    dto = ModelBenchmarkMetricsDTO(
        chronological_splits=metrics["chronological_splits"],
        validation_metrics=metrics["validation_metrics"],
        test_evaluation_benchmark=metrics["test_evaluation_benchmark"],
        benchmark_comparison=metrics.get("benchmark_comparison"),
        multi_horizon_benchmarks=metrics.get("multi_horizon_benchmarks"),
        dataset_notice=metrics["dataset_notice"]
    )
    return ResponseEnvelope[ModelBenchmarkMetricsDTO](
        request_id=str(uuid.uuid4()),
        correlation_id=str(uuid.uuid4()),
        snapshot_id="MODEL_BENCHMARK",
        data=dto
    )


@router.get("/{prediction_id}", response_model=ResponseEnvelope[HazardPredictionResponseDTO])
def get_hazard_prediction(
    prediction_id: str,
    db: Session = Depends(get_db)
):
    """Retrieves a single hazard prediction by ID."""
    rec = db.query(HazardPredictionRecord).filter(HazardPredictionRecord.id == prediction_id).first()
    if not rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"HAZARD_PREDICTION_NOT_FOUND: Prediction '{prediction_id}' not found."
        )

    return ResponseEnvelope[HazardPredictionResponseDTO](
        request_id=str(uuid.uuid4()),
        correlation_id=str(uuid.uuid4()),
        snapshot_id=rec.snapshot_id or "NONE",
        data=_to_dto(rec)
    )


@router.post("/{prediction_id}/evaluate", response_model=ResponseEnvelope[HazardPredictionResponseDTO])
def evaluate_hazard_prediction(
    prediction_id: str,
    payload: HazardPredictionEvaluateDTO,
    current_user: User = Depends(require_role([RoleEnum.AUTHORITY, RoleEnum.ADMIN, RoleEnum.DATA_OPERATOR])),
    db: Session = Depends(get_db)
):
    """
    Evaluates a stored prediction against a later ground-truth observation,
    computing the evaluation residual error.
    """
    try:
        updated = HazardPredictionPipeline.evaluate_prediction_against_observation(
            prediction_id=prediction_id,
            actual_value=payload.actual_value,
            db=db
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    return ResponseEnvelope[HazardPredictionResponseDTO](
        request_id=str(uuid.uuid4()),
        correlation_id=str(uuid.uuid4()),
        snapshot_id=updated.snapshot_id or "NONE",
        data=_to_dto(updated)
    )


@router.get("", response_model=ResponseEnvelope[List[HazardPredictionResponseDTO]])
def list_hazard_predictions(
    simulation_run_id: Optional[str] = Query(None),
    snapshot_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    """Lists hazard predictions with optional filtering."""
    query = db.query(HazardPredictionRecord)
    if simulation_run_id:
        query = query.filter(HazardPredictionRecord.simulation_run_id == simulation_run_id)
    if snapshot_id:
        query = query.filter(HazardPredictionRecord.snapshot_id == snapshot_id)

    records = query.order_by(HazardPredictionRecord.created_at.desc()).limit(limit).all()

    return ResponseEnvelope[List[HazardPredictionResponseDTO]](
        request_id=str(uuid.uuid4()),
        correlation_id=str(uuid.uuid4()),
        snapshot_id=snapshot_id or "MULTIPLE",
        data=[_to_dto(r) for r in records]
    )
