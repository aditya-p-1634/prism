"""
PRISM Phase A.6 — Hybrid Hazard Prediction Package
"""

from app.engines.e1_hazard.prediction.pipeline import HazardPredictionPipeline, PredictionSafetyException
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
    DomainConstraintValidator,
    ValidationResult
)
from app.engines.e1_hazard.prediction.uncertainty import UncertaintyEstimator
from app.engines.e1_hazard.prediction.features import FeatureExtractor, FEATURE_NAMES

__all__ = [
    "HazardPredictionPipeline",
    "PredictionSafetyException",
    "PersistenceBaselineModel",
    "LinearTrendBaselineModel",
    "AutoregressiveRidgeModel",
    "compute_regression_metrics",
    "InputQualityValidator",
    "DomainOfValidityChecker",
    "PhysicalPlausibilityValidator",
    "DomainConstraintValidator",
    "ValidationResult",
    "UncertaintyEstimator",
    "FeatureExtractor",
    "FEATURE_NAMES",
]
