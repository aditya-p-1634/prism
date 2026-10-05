"""
PRISM Phase A.6 — Baseline & ML Hydrometric Prediction Models
============================================================
Provides:
1. PersistenceBaselineModel: Classical hydrological benchmark (y_{t+h} = y_t)
2. LinearTrendBaselineModel: Linear extrapolation baseline
3. AutoregressiveRidgeModel: Transparent closed-form L2-regularized linear model
4. ModelEvaluator: Computes standard regression metrics (MAE, RMSE, R²)
"""

from typing import Dict, Any, Optional
import math
import numpy as np


def compute_regression_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
    """Computes MAE, RMSE, and R² metrics."""
    if len(y_true) == 0:
        return {"mae": 0.0, "rmse": 0.0, "r2": 0.0, "sample_count": 0}

    residuals = y_true - y_pred
    mae = float(np.mean(np.abs(residuals)))
    rmse = float(np.sqrt(np.mean(residuals ** 2)))

    ss_res = float(np.sum(residuals ** 2))
    ss_tot = float(np.sum((y_true - np.mean(y_true)) ** 2))
    r2 = float(1.0 - (ss_res / ss_tot)) if ss_tot > 1e-9 else 0.0

    return {
        "mae": round(mae, 4),
        "rmse": round(rmse, 4),
        "r2": round(r2, 4),
        "sample_count": len(y_true)
    }


class PersistenceBaselineModel:
    """Hydrological Persistence Baseline: future stage equals current stage."""
    name = "PERSISTENCE_BASELINE"
    version = "1.0.0"

    def predict(self, X: np.ndarray) -> np.ndarray:
        # Feature index 1 is current_stage_m
        return X[:, 1].copy()

    def predict_single(self, current_stage: float, horizon_minutes: float) -> float:
        if not math.isfinite(current_stage):
            raise ValueError("Input current_stage must be a finite numeric value.")
        return float(current_stage)


class LinearTrendBaselineModel:
    """Linear Extrapolation Baseline: extrapolates current rate of change."""
    name = "LINEAR_TREND_BASELINE"
    version = "1.0.0"

    def __init__(self, sample_interval_minutes: float = 10.0):
        self.sample_interval_minutes = float(sample_interval_minutes)

    def predict(self, X: np.ndarray) -> np.ndarray:
        # X[:, 1] is current_stage, X[:, 3] is stage_delta, X[:, 6] is horizon_minutes
        current_stage = X[:, 1]
        delta = X[:, 3]
        horizon = X[:, 6]
        steps = horizon / self.sample_interval_minutes
        return current_stage + (delta * steps)

    def predict_single(self, current_stage: float, lag1_stage: float, horizon_minutes: float) -> float:
        if not math.isfinite(current_stage) or not math.isfinite(lag1_stage):
            raise ValueError("Input stage values must be finite numbers.")
        delta = current_stage - lag1_stage
        steps = horizon_minutes / self.sample_interval_minutes
        return float(current_stage + (delta * steps))


class AutoregressiveRidgeModel:
    """
    Lightweight, interpretable closed-form Ridge Regression model.
    Minimizes ||Xw - y||² + λ||w||².
    Analytical solution: w = (X^T X + λ I)⁻¹ X^T y.
    """
    name = "AUTOREGRESSIVE_RIDGE"
    version = "1.0.0"

    def __init__(self, alpha: float = 0.1):
        self.alpha = float(alpha)
        self.weights: Optional[np.ndarray] = None
        self.feature_names: Optional[list] = None
        self.is_trained: bool = False
        self.validation_rmse: float = 0.05  # Default uncalibrated prior

    def fit(self, X_train: np.ndarray, y_train: np.ndarray, feature_names: Optional[list] = None) -> "AutoregressiveRidgeModel":
        """Fits ridge regression weights analytically using numpy."""
        if len(X_train) == 0:
            raise ValueError("Training dataset cannot be empty.")

        n_features = X_train.shape[1]
        XtX = np.dot(X_train.T, X_train)
        # Regularize all features except bias (index 0)
        reg_matrix = np.eye(n_features, dtype=np.float64) * self.alpha
        reg_matrix[0, 0] = 0.0

        Xty = np.dot(X_train.T, y_train)
        self.weights = np.linalg.solve(XtX + reg_matrix, Xty)
        self.feature_names = feature_names or []
        self.is_trained = True
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Computes predictions for batch feature matrix."""
        if not self.is_trained or self.weights is None:
            raise RuntimeError("Model must be trained before predicting.")
        return np.dot(X, self.weights)

    def predict_single(self, features: np.ndarray) -> float:
        """Computes prediction for a single feature vector."""
        if not self.is_trained or self.weights is None:
            raise RuntimeError("Model must be trained before predicting.")
        if not np.all(np.isfinite(features)):
            raise ValueError("Feature vector contains non-finite elements (NaN or Inf).")
        return float(np.dot(features, self.weights))

    def evaluate(self, X_test: np.ndarray, y_test: np.ndarray) -> Dict[str, float]:
        """Evaluates model performance against ground-truth targets."""
        preds = self.predict(X_test)
        return compute_regression_metrics(y_test, preds)
