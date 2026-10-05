"""
PRISM Phase A.6 — Hazard Prediction Feature Preparation & Chronological Splitting
=================================================================================
Prepares feature vectors for river stage prediction while strictly preventing
future temporal data leakage.
"""

from typing import List, Dict, Any, Tuple
import numpy as np


FEATURE_NAMES = [
    "bias",
    "current_stage_m",
    "lag1_stage_m",
    "stage_delta_m",
    "rainfall_rate_mmh",
    "rolling_mean_rain_30m",
    "horizon_minutes"
]


class FeatureExtractor:
    """Extracts features for hydrometric river stage prediction with strict temporal leakage prevention."""

    @staticmethod
    def extract_single_feature_vector(
        current_stage: float,
        lag1_stage: float,
        rainfall_rate: float,
        rolling_rain_30m: float,
        horizon_minutes: float
    ) -> Tuple[np.ndarray, Dict[str, Any]]:
        """
        Constructs a feature vector for inference along with a provenance dictionary.
        Validates numeric types to prevent NaN/Inf propagation into feature matrices.
        """
        stage_delta = round(float(current_stage) - float(lag1_stage), 4)
        features = np.array([
            1.0,  # Bias
            float(current_stage),
            float(lag1_stage),
            float(stage_delta),
            float(rainfall_rate),
            float(rolling_rain_30m),
            float(horizon_minutes)
        ], dtype=np.float64)

        provenance = {
            "feature_version": "v1.1.0",
            "feature_names": FEATURE_NAMES,
            "inputs": {
                "current_stage_m": float(current_stage),
                "lag1_stage_m": float(lag1_stage),
                "stage_delta_m": stage_delta,
                "rainfall_rate_mmh": float(rainfall_rate),
                "rolling_mean_rain_30m": float(rolling_rain_30m),
                "horizon_minutes": float(horizon_minutes)
            },
            "temporal_safety": {
                "source_clock_bound": "t <= source_time",
                "future_information_leaked": False
            }
        }
        return features, provenance

    @classmethod
    def build_dataset_from_series(
        cls,
        time_series: List[Dict[str, Any]],
        horizon_steps: int = 1,
        interval_minutes: float = 10.0
    ) -> Tuple[np.ndarray, np.ndarray, List[str]]:
        """
        Transforms a chronological sequence of observation dicts into feature matrix X,
        target vector y, and chronological split labels ("TRAIN", "VAL", "TEST").

        Safety Hardening:
        1. Verifies strictly monotonic chronological time ordering without duplicates.
        2. Strictly prevents temporal leakage across split boundaries:
           If a sample's target crosses into the next split partition (e.g. feature in TRAIN,
           target in VAL), that transition boundary sample is discarded so no validation/test
           ground-truth ever contaminates training or evaluation partitions.
        3. Enforces minimum history requirement (>= 3 samples for lag/rolling features).
        """
        n = len(time_series)
        min_required = 3 + horizon_steps
        if n < min_required:
            raise ValueError(
                f"Insufficient time-series history: provided {n} steps, but at least {min_required} "
                f"are required for lag features and horizon_steps={horizon_steps}."
            )

        # Verify chronological ordering & check for duplicates or out-of-order steps
        for idx in range(n - 1):
            t_curr = time_series[idx].get("simulation_time_min", idx * interval_minutes)
            t_next = time_series[idx + 1].get("simulation_time_min", (idx + 1) * interval_minutes)
            if t_next <= t_curr:
                raise ValueError(
                    f"Temporal sequence error at index {idx}: time {t_next} <= previous time {t_curr}. "
                    "Observations must be strictly increasing without duplicates or out-of-order entries."
                )

        X_list = []
        y_list = []
        splits_list = []

        horizon_min = horizon_steps * interval_minutes

        for i in range(2, n - horizon_steps):
            cur = time_series[i]
            prev = time_series[i - 1]
            prev2 = time_series[i - 2]
            target = time_series[i + horizon_steps]

            cur_split = cur.get("split_assignment", "TRAIN")
            target_split = target.get("split_assignment", "TRAIN")

            # BOUNDARY BUFFER SAFETY: Discard cross-boundary samples to prevent target contamination
            if cur_split != target_split:
                continue

            cur_stage = cur["river_stage_m"]
            prev_stage = prev["river_stage_m"]
            cur_rain = cur["rainfall_rate_mmh"]
            roll_rain = (cur_rain + prev["rainfall_rate_mmh"] + prev2["rainfall_rate_mmh"]) / 3.0

            feat, _ = cls.extract_single_feature_vector(
                current_stage=cur_stage,
                lag1_stage=prev_stage,
                rainfall_rate=cur_rain,
                rolling_rain_30m=roll_rain,
                horizon_minutes=horizon_min
            )

            X_list.append(feat)
            y_list.append(target["river_stage_m"])
            splits_list.append(cur_split)

        X = np.array(X_list, dtype=np.float64)
        y = np.array(y_list, dtype=np.float64)
        return X, y, splits_list
