"""
PRISM Phase A.7 — Hazard Observation Ingestion Service & CSV Pipeline
======================================================================
Implements safe, auditable ingestion of real hydrometric telemetry:
1. Single Observation Ingestion with full provenance tracking.
2. Controlled CSV Ingestion Pipeline:
   CSV -> Parse -> Schema validation -> Timestamp validation -> Station validation ->
   Unit validation -> Quality classification -> Persist -> Return structured ingestion report.

Critical Invariant:
observed_at != ingested_at
observed_at: when the physical sensor measured the water level.
ingested_at: when PRISM received, validated, and persisted the record.
"""

import csv
import io
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session

from app.models.entities import HazardStation, HazardObservation
from app.models.enums import ObservationQualityEnum, FreshnessEnum
from app.schemas.hazard_observation import (
    HazardObservationCreateDTO,
    CsvIngestionReportDTO
)
from app.engines.e1_hazard.observation.station_registry import StationRegistry
from app.engines.e1_hazard.observation.validation import ObservationValidator


class ObservationIngestionService:
    """Service handling telemetry observation ingestion and CSV batch processing."""

    @classmethod
    def ingest_single(
        cls,
        payload: HazardObservationCreateDTO,
        db: Session,
        reference_time: Optional[datetime] = None
    ) -> HazardObservation:
        """
        Validates and ingests a single telemetry observation into the persistent store.
        """
        station = StationRegistry.get_by_code(payload.station_code, db)

        val_res = ObservationValidator.validate_full_observation(
            station=station,
            raw_observed_at=payload.observed_at,
            raw_value=payload.value,
            raw_unit=payload.unit,
            reference_time=reference_time,
            db=db
        )

        station_id = station.id if station else str(uuid.uuid4())
        station_name = station.station_name if station else f"UNKNOWN_STATION_{payload.station_code}"
        river = station.river if station else "UNKNOWN"
        district = station.district if station else "UNKNOWN"
        hazard_type = station.hazard_type if station else "RIVER_WATER_LEVEL"
        source = payload.source or (station.source if station else "UNKNOWN_SOURCE")
        source_dataset = payload.source_dataset or (station.source_dataset if station else "UNKNOWN_DATASET")
        lat = station.latitude if station else None
        lon = station.longitude if station else None

        now_utc = datetime.now(timezone.utc).replace(tzinfo=None)

        observation = HazardObservation(
            id=str(uuid.uuid4()),
            station_id=station_id,
            station_code=payload.station_code.strip().upper(),
            station_name=station_name,
            river=river,
            district=district,
            hazard_type=hazard_type,
            source=source,
            source_dataset=source_dataset,
            observed_at=val_res["observed_at"],
            ingested_at=now_utc,
            value=val_res["validated_value"],
            unit=val_res["unit"],
            latitude=lat,
            longitude=lon,
            quality_status=val_res["quality_status"],
            quality_flags=val_res["quality_flags"],
            freshness=val_res["freshness"],
            raw_reference=payload.raw_reference or {"input": "single_api_payload"}
        )

        db.add(observation)
        db.commit()
        db.refresh(observation)
        return observation

    @classmethod
    def ingest_csv(
        cls,
        csv_content: str,
        filename: str,
        db: Session,
        reference_time: Optional[datetime] = None
    ) -> CsvIngestionReportDTO:
        """
        Processes and validates batch telemetry observations from a CSV stream.
        Generates an auditable, structured ingestion report containing counts,
        rejection reasons, and ingested IDs.
        """
        if not csv_content or not csv_content.strip():
            return CsvIngestionReportDTO(
                rows_received=0,
                rows_accepted=0,
                rows_suspect=0,
                rows_rejected=0,
                duplicates=0,
                invalid_timestamps=0,
                invalid_values=0,
                unknown_stations=0,
                rejection_reasons=[{"row_index": 0, "reason": "EMPTY_CSV: The provided CSV content is empty."}],
                ingested_observation_ids=[]
            )

        f = io.StringIO(csv_content.strip())
        reader = csv.DictReader(f)

        # Map original fieldnames by their lowercase trimmed names
        field_map = {fn.strip().lower(): fn for fn in (reader.fieldnames or [])}
        headers = list(field_map.keys())

        code_header = next((c for c in ("station_id", "station_code", "station") if c in headers), None)
        time_header = next((c for c in ("observed_at", "timestamp", "datetime", "date_time", "time", "data acquisition time") if c in headers), None)
        val_header = next((c for c in ("value", "water_level", "river_stage_m", "water_level_m", "stage_m", "river water level telemetry hourly (meter)") if c in headers), None)

        if not code_header or not time_header or not val_header:
            missing = []
            if not code_header: missing.append("station_id/station_code/station")
            if not time_header: missing.append("observed_at/timestamp/data acquisition time")
            if not val_header: missing.append("value/water_level/river water level telemetry hourly (meter)")
            return CsvIngestionReportDTO(
                rows_received=0,
                rows_accepted=0,
                rows_suspect=0,
                rows_rejected=0,
                duplicates=0,
                invalid_timestamps=0,
                invalid_values=0,
                unknown_stations=0,
                rejection_reasons=[{
                    "row_index": 0,
                    "reason": f"SCHEMA_ERROR: Missing required columns: {', '.join(missing)}. Headers found: {reader.fieldnames}"
                }],
                ingested_observation_ids=[]
            )

        orig_code_col = field_map[code_header]
        orig_time_col = field_map[time_header]
        orig_val_col = field_map[val_header]
        orig_unit_col = field_map.get("unit")
        orig_source_col = field_map.get("source") or field_map.get("agency")
        orig_dataset_col = field_map.get("source_dataset") or field_map.get("dataset")

        rows_received = 0
        rows_accepted = 0
        rows_suspect = 0
        rows_rejected = 0
        duplicates = 0
        invalid_timestamps = 0
        invalid_values = 0
        unknown_stations = 0
        rejection_reasons: List[Dict[str, Any]] = []
        ingested_ids: List[str] = []

        now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
        seen_in_batch = set()

        for idx, row in enumerate(reader, start=1):
            rows_received += 1
            raw_code = (row.get(orig_code_col) or "").strip()
            raw_ts = (row.get(orig_time_col) or "").strip()
            raw_val = (row.get(orig_val_col) or "").strip()
            raw_unit = (row.get(orig_unit_col) or "metres").strip() if orig_unit_col else "metres"
            raw_source = (row.get(orig_source_col) or "Tamil Nadu River Water Level Telemetry Hourly").strip() if orig_source_col else "Tamil Nadu River Water Level Telemetry Hourly"
            raw_dataset = (row.get(orig_dataset_col) or filename or "rwl_tel_hr_tamil_nadu_sw_gw_27_2026_2030.csv").strip()

            station = StationRegistry.get_by_code(raw_code, db)

            val_res = ObservationValidator.validate_full_observation(
                station=station,
                raw_observed_at=raw_ts,
                raw_value=raw_val,
                raw_unit=raw_unit,
                reference_time=reference_time,
                db=db
            )

            # In-batch duplicate detection
            batch_key = (raw_code, val_res["observed_at"])
            if batch_key in seen_in_batch:
                val_res["quality_status"] = ObservationQualityEnum.REJECTED
                val_res["quality_flags"].append("IN_BATCH_DUPLICATE: Identical observation timestamp already seen in this CSV batch.")

            seen_in_batch.add(batch_key)

            # Categorize metrics
            is_dup = any("DUPLICATE" in f for f in val_res["quality_flags"])
            is_ts_err = any("TIMESTAMP_ERROR" in f for f in val_res["quality_flags"])
            is_val_err = any("NUMERIC_ERROR" in f or "UNREASONABLE" in f for f in val_res["quality_flags"])
            is_unk_stn = any("UNKNOWN_STATION" in f for f in val_res["quality_flags"])

            if is_dup:
                duplicates += 1
            if is_ts_err:
                invalid_timestamps += 1
            if is_val_err:
                invalid_values += 1
            if is_unk_stn:
                unknown_stations += 1

            if val_res["quality_status"] == ObservationQualityEnum.REJECTED:
                rows_rejected += 1
                rejection_reasons.append({
                    "row_index": idx,
                    "station_code": raw_code,
                    "reasons": val_res["quality_flags"],
                    "raw_data": row
                })
            elif val_res["quality_status"] == ObservationQualityEnum.SUSPECT:
                rows_suspect += 1
            else:
                rows_accepted += 1

            # Persist observation record (preserving raw row reference for full auditability)
            station_id = station.id if station else str(uuid.uuid4())
            station_name = station.station_name if station else f"UNKNOWN_{raw_code}"
            river = station.river if station else "UNKNOWN"
            district = station.district if station else "UNKNOWN"
            hazard_type = station.hazard_type if station else "RIVER_WATER_LEVEL"
            src = raw_source or (station.source if station else "CSV_INGEST")
            src_ds = raw_dataset or (station.source_dataset if station else filename)
            lat = station.latitude if station else None
            lon = station.longitude if station else None

            obs = HazardObservation(
                id=str(uuid.uuid4()),
                station_id=station_id,
                station_code=raw_code,
                station_name=station_name,
                river=river,
                district=district,
                hazard_type=hazard_type,
                source=src,
                source_dataset=src_ds,
                observed_at=val_res["observed_at"],
                ingested_at=now_utc,
                value=val_res["validated_value"],
                unit=val_res["unit"],
                latitude=lat,
                longitude=lon,
                quality_status=val_res["quality_status"],
                quality_flags=val_res["quality_flags"],
                freshness=val_res["freshness"],
                raw_reference={"file": filename, "row_index": idx, "raw_row": row}
            )
            db.add(obs)
            ingested_ids.append(obs.id)

        db.commit()

        return CsvIngestionReportDTO(
            rows_received=rows_received,
            rows_accepted=rows_accepted,
            rows_suspect=rows_suspect,
            rows_rejected=rows_rejected,
            duplicates=duplicates,
            invalid_timestamps=invalid_timestamps,
            invalid_values=invalid_values,
            unknown_stations=unknown_stations,
            rejection_reasons=rejection_reasons,
            ingested_observation_ids=ingested_ids
        )
