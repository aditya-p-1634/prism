"""
PRISM Phase A.6 — Prediction Uncertainty & Interval Estimation
=============================================================
Provides honest, statistically grounded prediction intervals based on empirical
residual standard error from the chronological validation split.

Critical Safety Rules:
1. Never fabricates arbitrary confidence percentages (e.g. 85% or 95% 'accuracy').
2. Explicitly exposes empirical coverage evaluated on the held-out validation partition.
3. Explicitly flags that intervals are PROTOTYPE-calibrated on synthetic data and NOT
   certified for operational life-safety deployment.
4. Marks status as NOT_CALIBRATED if validation sample size is insufficient (<30 samples).
"""

from typing import Tuple, Dict, Any, Optional
import math
import numpy as np


class UncertaintyEstimator:
    """
    Computes empirical prediction intervals using sample standard deviation of
    residuals from the chronological validation partition.
    """

    MIN_VALIDATION_SAMPLES = 30

    def __init__(
        self,
        validation_rmse: float = 0.040,
        sample_count: int = 86,
        empirical_coverage: Optional[float] = None,
        confidence_level: float = 0.95
    ):
        self.validation_rmse = max(0.0001, float(validation_rmse))
        self.sample_count = int(sample_count)
        self.empirical_coverage = float(empirical_coverage) if empirical_coverage is not None else None
        self.confidence_level = confidence_level
        self.z_score = 1.96 if confidence_level == 0.95 else 1.645
        self.is_calibrated = self.sample_count >= self.MIN_VALIDATION_SAMPLES

    @classmethod
    def fit_from_residuals(
        cls,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        confidence_level: float = 0.95
    ) -> "UncertaintyEstimator":
        """
        Calibrates residual standard error and calculates exact empirical coverage
        on a validation partition.
        """
        n = len(y_true)
        if n == 0:
            return cls(validation_rmse=0.05, sample_count=0, empirical_coverage=None, confidence_level=confidence_level)

        residuals = y_true - y_pred
        rmse = float(np.sqrt(np.mean(residuals ** 2)))
        z = 1.96 if confidence_level == 0.95 else 1.645

        # Calculate empirical coverage: proportion of validation points inside +/- z * rmse
        inside_interval = np.abs(residuals) <= (z * rmse)
        coverage = float(np.mean(inside_interval))

        return cls(
            validation_rmse=rmse,
            sample_count=n,
            empirical_coverage=round(coverage, 4),
            confidence_level=confidence_level
        )

    def compute_bounds(
        self,
        predicted_value: float,
        horizon_minutes: float,
        horizon_rmse_override: Optional[float] = None
    ) -> Tuple[Optional[float], Optional[float], float, Dict[str, Any]]:
        """
        Calculates lower and upper prediction bounds.
        If a horizon-specific RMSE override is available from multi-horizon validation,
        it is used directly; otherwise error scales weakly with lead time.
        """
        if not self.is_calibrated:
            metadata = {
                "method": "UNAVAILABLE",
                "calibration_status": "NOT_CALIBRATED",
                "sample_count": self.sample_count,
                "is_operationally_calibrated": False,
                "advisory": "Validation sample count is insufficient (< 30) for statistical interval estimation."
            }
            return None, None, 0.0, metadata

        base_rmse = horizon_rmse_override if horizon_rmse_override is not None else self.validation_rmse
        lead_factor = math.sqrt(1.0 + 0.05 * (horizon_minutes / 10.0))
        scaled_sigma = round(base_rmse * lead_factor, 4)
        margin = round(self.z_score * scaled_sigma, 4)

        lower_bound = round(predicted_value - margin, 3)
        upper_bound = round(predicted_value + margin, 3)
        interval_width = round(2.0 * margin, 4)

        metadata = {
            "method": "EMPIRICAL_RESIDUAL_NORMAL_INTERVAL",
            "calibration_status": "CALIBRATED_PROTOTYPE",
            "is_operationally_calibrated": False,
            "nominal_confidence_level": self.confidence_level,
            "empirical_coverage_val": self.empirical_coverage,
            "validation_sample_count": self.sample_count,
            "base_rmse": round(base_rmse, 4),
            "lead_time_factor": round(lead_factor, 3),
            "scaled_sigma": scaled_sigma,
            "interval_width_m": interval_width,
            "calibration_dataset": "DEMO / PROTOTYPE SYNTHETIC VAYU CATCHMENT",
            "disclaimer": "Prototype statistical interval; does NOT guarantee 95% real-world coverage."
        }
        return lower_bound, upper_bound, scaled_sigma, metadata
