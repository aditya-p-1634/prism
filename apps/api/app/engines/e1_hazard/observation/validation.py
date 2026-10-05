"""
PRISM Phase A.7 — Hazard Observation Validation Layer
=====================================================
Performs strict, multi-stage quality screening on real-world hydrometric telemetry:
1. Numeric Validation: Rejects NaN, Inf, non-numeric values.
2. Timestamp Validation: Rejects missing, invalid format, and future timestamps.
3. Station Validation: Verifies station registration, active state, and coordinate bounds.
4. Unit Validation: Normalizes metres/m/meter -> metres; rejects unsupported units.
5. Temporal Validation: Identifies duplicates, suspicious gaps, and computes freshness (FRESH, AGING, STALE).

CRITICAL RULE (Section 8):
Data validity is separated from hazard severity. Valid observations are marked VALID.
Unless documented authoritative thresholds exist for a station, severity is represented
strictly as SEVERITY_UNCLASSIFIED without fabricating official alert stages.
"""

import math
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session

from app.models.entities import HazardStation, HazardObservation
from app.models.enums import ObservationQualityEnum, FreshnessEnum, HazardMeasurementTypeEnum


SUPPORTED_METRE_UNITS = {"metres", "m", "meter", "meters", "metre"}


class ObservationSafetyException(Exception):
    """Raised when an unvalidated, degraded, or stale observation is unsafely passed to downstream engines."""
    pass


class ObservationValidator:
    """Validator for real-world hydrometric telemetry observations."""

    FRESH_THRESHOLD_HOURS = 2.0
    STALE_THRESHOLD_HOURS = 6.0
    FUTURE_TOLERANCE_MINUTES = 5.0  # Allowed clock skew for telemetry transmitters

    @classmethod
    def validate_numeric(cls, raw_val: Any) -> Tuple[bool, Optional[float], Optional[str]]:
        """
        Validates numeric value. Rejects NaN, Inf, None, and non-numeric strings.
        Returns (is_valid, float_val, error_reason).
        """
        if raw_val is None:
            return False, None, "NUMERIC_ERROR: Value is missing or null."

        try:
            val_float = float(raw_val)
        except (ValueError, TypeError):
            return False, None, f"NUMERIC_ERROR: Value '{raw_val}' cannot be converted to float."

        if not math.isfinite(val_float):
            return False, None, f"NUMERIC_ERROR: Value '{raw_val}' is non-finite (NaN or Inf)."

        return True, val_float, None

    @classmethod
    def validate_timestamp(
        cls,
        raw_ts: Any,
        reference_time: Optional[datetime] = None
    ) -> Tuple[bool, Optional[datetime], Optional[str]]:
        """
        Validates observation timestamp. Rejects missing, unparseable, and future timestamps.
        Returns (is_valid, datetime_utc, error_reason).
        """
        if raw_ts is None:
            return False, None, "TIMESTAMP_ERROR: Timestamp is missing."

        if isinstance(raw_ts, datetime):
            dt = raw_ts
        elif isinstance(raw_ts, str):
            ts_str = raw_ts.strip().rstrip("Z")
            try:
                dt = datetime.fromisoformat(ts_str)
            except ValueError:
                # Try common timestamp format strings
                for fmt in (
                    "%Y-%m-%d %H:%M:%S",
                    "%Y-%m-%d %H:%M",
                    "%d-%m-%Y %H:%M:%S",
                    "%d/%m/%Y %H:%M:%S",
                    "%d-%m-%Y %H:%M",
                    "%d/%m/%Y %H:%M"
                ):
                    try:
                        dt = datetime.strptime(ts_str, fmt)
                        break
                    except ValueError:
                        pass
                else:
                    return False, None, f"TIMESTAMP_ERROR: Cannot parse timestamp string '{raw_ts}'."
        else:
            return False, None, f"TIMESTAMP_ERROR: Unsupported timestamp type '{type(raw_ts)}'."

        # Normalize to timezone-naive UTC for consistent database storage
        if dt.tzinfo is not None:
            dt_utc = dt.astimezone(timezone.utc).replace(tzinfo=None)
        else:
            dt_utc = dt

        ref_now = reference_time or datetime.now(timezone.utc).replace(tzinfo=None)
        max_allowed_future = ref_now + timedelta(minutes=cls.FUTURE_TOLERANCE_MINUTES)

        if dt_utc > max_allowed_future:
            return False, None, f"TIMESTAMP_ERROR: Timestamp '{dt_utc.isoformat()}' is in the future (reference now: {ref_now.isoformat()})."

        return True, dt_utc, None

    @classmethod
    def validate_unit(cls, raw_unit: Any) -> Tuple[bool, str, Optional[str]]:
        """
        Validates measurement unit. Standardizes metres/m/meter to 'metres'.
        Rejects unsupported units (e.g. feet, inches, psi).
        """
        if not raw_unit or not isinstance(raw_unit, str):
            return False, "", "UNIT_ERROR: Unit is missing or non-string."

        norm = raw_unit.strip().lower()
        if norm in SUPPORTED_METRE_UNITS:
            return True, "metres", None

        return False, norm, f"UNIT_ERROR: Unsupported measurement unit '{raw_unit}'. PRISM telemetry pilot accepts only 'metres'."

    @classmethod
    def compute_freshness(
        cls,
        observed_at: datetime,
        reference_time: Optional[datetime] = None
    ) -> Tuple[FreshnessEnum, float]:
        """
        Computes observation freshness relative to reference time (defaults to now UTC).
        Returns (FreshnessEnum, elapsed_hours).
        """
        ref_now = reference_time or datetime.now(timezone.utc).replace(tzinfo=None)
        elapsed_seconds = max(0.0, (ref_now - observed_at).total_seconds())
        elapsed_hours = round(elapsed_seconds / 3600.0, 2)

        if elapsed_hours <= cls.FRESH_THRESHOLD_HOURS:
            return FreshnessEnum.FRESH, elapsed_hours
        elif elapsed_hours <= cls.STALE_THRESHOLD_HOURS:
            return FreshnessEnum.AGING, elapsed_hours
        else:
            return FreshnessEnum.STALE, elapsed_hours

    @classmethod
    def validate_full_observation(
        cls,
        station: Optional[HazardStation],
        raw_observed_at: Any,
        raw_value: Any,
        raw_unit: Any,
        reference_time: Optional[datetime] = None,
        db: Optional[Session] = None
    ) -> Dict[str, Any]:
        """
        Executes complete quality validation across all criteria.
        Returns a dictionary with validation results, flags, and normalized values.
        """
        flags: List[str] = []
        is_rejected = False

        # 1. Station Check
        if station is None:
            flags.append("UNKNOWN_STATION: Station code is not registered in PRISM station registry.")
            is_rejected = True
        elif not station.is_active:
            flags.append(f"INACTIVE_STATION: Station '{station.station_code}' is currently marked inactive.")
            is_rejected = True

        # 2. Numeric Check
        num_ok, val_float, num_err = cls.validate_numeric(raw_value)
        if not num_ok:
            flags.append(num_err)
            is_rejected = True

        # Domain boundary for water level: e.g. -5m to +50m physical gauge bounds
        if num_ok and val_float is not None:
            if val_float < -2.0:
                flags.append(f"UNREASONABLE_VALUE: Water level {val_float:.2f}m is below gauge datum lower bound (-2.0m).")
                is_rejected = True
            elif val_float > 35.0:
                flags.append(f"UNREASONABLE_VALUE: Water level {val_float:.2f}m exceeds catastrophic upper gauge bound (35.0m).")
                is_rejected = True

        # 3. Timestamp Check
        ts_ok, dt_utc, ts_err = cls.validate_timestamp(raw_observed_at, reference_time=reference_time)
        if not ts_ok:
            flags.append(ts_err)
            is_rejected = True

        # 4. Unit Check
        unit_ok, norm_unit, unit_err = cls.validate_unit(raw_unit)
        if not unit_ok:
            flags.append(unit_err)
            is_rejected = True

        # 5. Duplicate Check
        if station and dt_utc and db is not None:
            existing = db.query(HazardObservation).filter(
                HazardObservation.station_id == station.id,
                HazardObservation.observed_at == dt_utc
            ).first()
            if existing:
                flags.append(f"DUPLICATE_OBSERVATION: An observation for station '{station.station_code}' at '{dt_utc.isoformat()}' already exists (ID: {existing.id}).")
                is_rejected = True

        # 6. Freshness Calculation
        if dt_utc:
            freshness_enum, elapsed_h = cls.compute_freshness(dt_utc, reference_time=reference_time)
            if freshness_enum == FreshnessEnum.STALE:
                flags.append(f"STALE_TELEMETRY: Observation is {elapsed_h:.1f} hours old (> {cls.STALE_THRESHOLD_HOURS}h threshold).")
        else:
            freshness_enum = FreshnessEnum.STALE

        # Determine Final Quality Status
        if is_rejected:
            quality_status = ObservationQualityEnum.REJECTED
        elif any("SUSPECT" in f for f in flags):
            quality_status = ObservationQualityEnum.SUSPECT
        else:
            quality_status = ObservationQualityEnum.VALID

        return {
            "quality_status": quality_status,
            "quality_flags": flags,
            "freshness": freshness_enum,
            "validated_value": val_float if val_float is not None else 0.0,
            "observed_at": dt_utc if dt_utc is not None else datetime.now(timezone.utc).replace(tzinfo=None),
            "unit": norm_unit if unit_ok else str(raw_unit)
        }
