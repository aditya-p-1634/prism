"""
PRISM Phase A.7 — Hazard Station Registry Service
=================================================
Manages official telemetry monitoring stations.
Ensures station metadata is validated and registered before observations are accepted.
Pre-seeds and guarantees the target pilot station:
- Nandambakkam CheckDam on Adyar River (Chennai, Tamil Nadu).
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
import uuid

from app.models.entities import HazardStation
from app.models.enums import HazardMeasurementTypeEnum
from app.schemas.hazard_observation import HazardStationCreateDTO


class StationRegistry:
    """Registry manager for hydrometric telemetry stations."""

    PILOT_STATION_CODE = "NANDAMBAKKAM_CHECKDAM"
    PILOT_STATION_NAME = "Nandambakkam CheckDam"
    PILOT_RIVER = "Adyar"
    PILOT_DISTRICT = "Chennai"
    PILOT_STATE = "Tamil Nadu"
    PILOT_LATITUDE = 13.0161
    PILOT_LONGITUDE = 80.1828
    PILOT_SOURCE = "Tamil Nadu River Water Level Telemetry Hourly"
    PILOT_DATASET = "tn_water_resources_telemetry_hourly"

    @classmethod
    def register_station(cls, payload: HazardStationCreateDTO, db: Session) -> HazardStation:
        """Registers a new hazard telemetry monitoring station."""
        existing = db.query(HazardStation).filter(
            HazardStation.station_code == payload.station_code.strip().upper()
        ).first()
        if existing:
            raise ValueError(f"Station with code '{payload.station_code}' is already registered.")

        # Coordinate check
        if not (-90.0 <= payload.latitude <= 90.0):
            raise ValueError(f"Invalid latitude: {payload.latitude}. Must be between -90 and 90.")
        if not (-180.0 <= payload.longitude <= 180.0):
            raise ValueError(f"Invalid longitude: {payload.longitude}. Must be between -180 and 180.")

        station = HazardStation(
            id=str(uuid.uuid4()),
            station_code=payload.station_code.strip().upper(),
            station_name=payload.station_name.strip(),
            river=payload.river.strip(),
            district=payload.district.strip(),
            state=payload.state.strip(),
            latitude=float(payload.latitude),
            longitude=float(payload.longitude),
            hazard_type=HazardMeasurementTypeEnum(payload.hazard_type) if isinstance(payload.hazard_type, str) else payload.hazard_type,
            unit=payload.unit.strip().lower(),
            source=payload.source.strip(),
            source_dataset=payload.source_dataset.strip(),
            is_active=True,
            warning_threshold_m=payload.warning_threshold_m,
            danger_threshold_m=payload.danger_threshold_m,
            metadata_json=payload.metadata_json or {}
        )
        db.add(station)
        db.commit()
        db.refresh(station)
        return station

    @classmethod
    def get_by_code(cls, station_code: str, db: Session) -> Optional[HazardStation]:
        """Retrieves station by its unique station code or registered station name."""
        if not station_code:
            return None
        cleaned = station_code.strip()
        cleaned_upper = cleaned.upper()
        normalized_code = cleaned_upper.replace(" ", "_").replace("-", "_")
        return db.query(HazardStation).filter(
            (HazardStation.station_code == cleaned_upper) |
            (HazardStation.station_code == normalized_code) |
            (HazardStation.station_name.ilike(cleaned))
        ).first()

    @classmethod
    def get_by_id(cls, station_id: str, db: Session) -> Optional[HazardStation]:
        """Retrieves station by primary key ID."""
        return db.query(HazardStation).filter(HazardStation.id == station_id).first()

    @classmethod
    def list_stations(
        cls,
        hazard_type: Optional[str] = None,
        district: Optional[str] = None,
        is_active: Optional[bool] = None,
        db: Optional[Session] = None
    ) -> List[HazardStation]:
        """Lists registered telemetry stations with optional filtering."""
        if db is None:
            return []
        query = db.query(HazardStation)
        if hazard_type:
            query = query.filter(HazardStation.hazard_type == hazard_type)
        if district:
            query = query.filter(HazardStation.district == district)
        if is_active is not None:
            query = query.filter(HazardStation.is_active == is_active)
        return query.order_by(HazardStation.station_code.asc()).all()

    @classmethod
    def ensure_pilot_station(cls, db: Session) -> HazardStation:
        """
        Ensures the canonical pilot station Nandambakkam CheckDam on the Adyar River
        is registered in the database.
        """
        station = cls.get_by_code(cls.PILOT_STATION_CODE, db)
        if not station:
            station = HazardStation(
                id=str(uuid.uuid4()),
                station_code=cls.PILOT_STATION_CODE,
                station_name=cls.PILOT_STATION_NAME,
                river=cls.PILOT_RIVER,
                district=cls.PILOT_DISTRICT,
                state=cls.PILOT_STATE,
                latitude=cls.PILOT_LATITUDE,
                longitude=cls.PILOT_LONGITUDE,
                hazard_type=HazardMeasurementTypeEnum.RIVER_WATER_LEVEL,
                unit="metres",
                source=cls.PILOT_SOURCE,
                source_dataset=cls.PILOT_DATASET,
                is_active=True,
                warning_threshold_m=None,  # Explicitly unclassified; no fabricated thresholds
                danger_threshold_m=None,
                metadata_json={
                    "pilot_phase": "A.7",
                    "basin": "Adyar Basin",
                    "telemetry_interval": "1 hour",
                    "telemetry_type": "AUTOMATIC_WATER_LEVEL_RECORDER"
                }
            )
            db.add(station)
            db.commit()
            db.refresh(station)
        return station
