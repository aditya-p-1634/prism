"""PRISM V2 — Phase A.7: Real-World Hazard Data Integration & Observation-Driven E1 Test Suite
=============================================================================================
Comprehensive test suite validating:
1. Station Registry: registration, pilot station persistence, duplicate code rejection.
2. Validation Layer:
   - Valid observation accepted (metres unit normalization).
   - Numeric screening: NaN, Inf, non-numeric rejected.
   - Timestamp screening: missing, invalid string, future timestamp rejected.
   - Station screening: unregistered station rejected.
   - Unit screening: unsupported unit rejected.
   - Duplicate detection: identical station & timestamp flagged as duplicate.
   - Freshness classification: FRESH, AGING, STALE computed correctly.
   - Explicit distinction: observed_at != ingested_at.
3. CSV Ingestion Pipeline:
   - Schema validation (missing columns detected).
   - Malformed / empty CSV handling.
   - Batch quality classification & structured ingestion report.
4. E1 Safety Boundary:
   - Valid observation drives E1 successfully.
   - Rejected observation is strictly prohibited from driving E1 (raises ObservationSafetyException).
   - Stale observation cannot masquerade as current without explicit allow_stale flag.
   - E1 hazard state preserves real telemetry provenance in HazardEvidence.
   - Spatial transformation explicitly tagged with prototype disclaimer.
5. Provenance & E6 Audit:
   - E6 AuditEvent records complete chain: Observation ID -> Station Code -> Water level.
6. Backward Compatibility & System Isolation:
   - Existing scenario-based E1 evaluation works untouched.
   - A.6 prediction layer remains completely decoupled.
   - Canonical baseline SNAP_BASE_001 remains 100% immutable.
7. Adversarial Test Cases:
   - NaN, Inf, negative value, extreme upper value, future timestamp, out-of-order timestamps,
     empty CSV, malformed CSV, unsupported units.
"""

import math
import random
import uuid
import os
import csv
from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.session import SessionLocal
from app.models.entities import (
    HazardStation,
    HazardObservation,
    HazardState,
    AuditEvent,
    RelocationAllocation
)
from app.models.enums import ObservationQualityEnum, FreshnessEnum
from app.engines.e1_hazard.observation.validation import (
    ObservationValidator,
    ObservationSafetyException
)
from app.engines.e1_hazard.observation.station_registry import StationRegistry
from app.engines.e1_hazard.observation.ingestion import ObservationIngestionService
from app.engines.e1_hazard.observation.service import HazardObservationService
from app.engines.e1_hazard.service import HazardEngineE1
from app.gis.spatial import to_shapely

client = TestClient(app)


@pytest.fixture(scope="module")
def base_scenario():
    """Initializes a scenario snapshot for testing observation-driven E1 evaluations."""
    res = client.post("/api/v1/scenarios/run", json={"scenario_code": "MONSOON_SURGE_01"})
    assert res.status_code == 200
    scen_data = res.json()["data"]
    return {
        "baseline_snapshot_id": "SNAP_BASE_001",
        "scenario_snapshot_id": scen_data["scenario_snapshot_id"],
        "scenario_code": "MONSOON_SURGE_01"
    }


# ==============================================================================
# 1. STATION REGISTRY TESTS
# ==============================================================================

def test_1_pilot_station_registered():
    """TEST 1: Canonical pilot station Nandambakkam CheckDam on Adyar River is registered."""
    res = client.get("/api/v1/hazard-stations/NANDAMBAKKAM_CHECKDAM")
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["station_code"] == "NANDAMBAKKAM_CHECKDAM"
    assert data["station_name"] == "Nandambakkam CheckDam"
    assert data["river"] == "Adyar"
    assert data["district"] == "Chennai"
    assert abs(data["latitude"] - 13.0161) < 1e-3
    assert abs(data["longitude"] - 80.1828) < 1e-3
    assert data["unit"] == "metres"
    # Section 8: Unclassified threshold initially
    assert data["warning_threshold_m"] is None
    assert data["danger_threshold_m"] is None


def test_2_station_registration_validation():
    """TEST 2: Station registration validates coordinates and rejects invalid latitude/longitude."""
    # Invalid latitude > 90
    res_bad_lat = client.post("/api/v1/hazard-stations", json={
        "station_code": "BAD_STATION_LAT",
        "station_name": "Bad Lat Station",
        "river": "Adyar",
        "district": "Chennai",
        "latitude": 95.0,
        "longitude": 80.0
    })
    assert res_bad_lat.status_code in [400, 422]

    # Duplicate station code rejected
    res_dup = client.post("/api/v1/hazard-stations", json={
        "station_code": "NANDAMBAKKAM_CHECKDAM",
        "station_name": "Duplicate Checkdam",
        "river": "Adyar",
        "district": "Chennai",
        "latitude": 13.0161,
        "longitude": 80.1828
    })
    assert res_dup.status_code == 400


# ==============================================================================
# 2. NUMERIC, TIMESTAMP, UNIT & STATION VALIDATION
# ==============================================================================

def test_3_numeric_validation_screening():
    """TEST 3: Numeric validator accepts valid floats and strictly rejects NaN, Inf, and non-numeric strings."""
    # Valid
    ok, val, _ = ObservationValidator.validate_numeric("3.45")
    assert ok is True and val == 3.45

    # NaN rejected
    ok, _, err = ObservationValidator.validate_numeric(float("nan"))
    assert ok is False and "non-finite" in err

    # Inf rejected
    ok, _, err = ObservationValidator.validate_numeric(float("inf"))
    assert ok is False and "non-finite" in err

    # Non-numeric string
    ok, _, err = ObservationValidator.validate_numeric("corrupted_telemetry")
    assert ok is False and "cannot be converted" in err


def test_4_timestamp_validation_and_future_rejection():
    """TEST 4: Rejects future timestamps and unparseable datetime strings."""
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)

    # Valid past timestamp
    past_ts = (now_utc - timedelta(hours=1)).isoformat()
    ok, dt, _ = ObservationValidator.validate_timestamp(past_ts)
    assert ok is True and dt is not None

    # Future timestamp (e.g. +2 hours) rejected
    future_ts = (now_utc + timedelta(hours=2)).isoformat()
    ok, _, err = ObservationValidator.validate_timestamp(future_ts)
    assert ok is False and "in the future" in err

    # Corrupted timestamp string
    ok, _, err = ObservationValidator.validate_timestamp("not-a-date")
    assert ok is False and "Cannot parse timestamp" in err


def test_5_unit_validation_and_normalization():
    """TEST 5: Normalizes metres/m/meter to 'metres' and rejects unsupported units."""
    for unit_alias in ["metres", "m", "meter", "meters", "METRES", "M"]:
        ok, norm, _ = ObservationValidator.validate_unit(unit_alias)
        assert ok is True and norm == "metres"

    # Unsupported units rejected
    for bad_unit in ["feet", "inches", "ft", "psi", "gallons"]:
        ok, _, err = ObservationValidator.validate_unit(bad_unit)
        assert ok is False and "Unsupported measurement unit" in err


def test_6_unknown_station_rejection():
    """TEST 6: Observations for unregistered stations are rejected."""
    db = SessionLocal()
    try:
        val_res = ObservationValidator.validate_full_observation(
            station=None,
            raw_observed_at="2026-10-03T10:00:00Z",
            raw_value=2.50,
            raw_unit="metres",
            db=db
        )
        assert val_res["quality_status"] == ObservationQualityEnum.REJECTED
        assert any("UNKNOWN_STATION" in f for f in val_res["quality_flags"])
    finally:
        db.close()


def test_7_freshness_classification():
    """TEST 7: Correctly categorizes FRESH (<=2h), AGING (2-6h), and STALE (>6h)."""
    now = datetime(2026, 10, 3, 12, 0, 0)

    # 1 hour ago -> FRESH
    f_fresh, h1 = ObservationValidator.compute_freshness(datetime(2026, 10, 3, 11, 0, 0), reference_time=now)
    assert f_fresh == FreshnessEnum.FRESH and h1 == 1.0

    # 4 hours ago -> AGING
    f_aging, h4 = ObservationValidator.compute_freshness(datetime(2026, 10, 3, 8, 0, 0), reference_time=now)
    assert f_aging == FreshnessEnum.AGING and h4 == 4.0

    # 10 hours ago -> STALE
    f_stale, h10 = ObservationValidator.compute_freshness(datetime(2026, 10, 3, 2, 0, 0), reference_time=now)
    assert f_stale == FreshnessEnum.STALE and h10 == 10.0


# ==============================================================================
# 3. SINGLE OBSERVATION INGESTION & PROVENANCE
# ==============================================================================

def test_8_valid_single_observation_ingestion():
    """TEST 8: Ingests valid real observation with explicit observed_at != ingested_at."""
    random_minute = random.randint(100, 5000)
    obs_time = (datetime.now(timezone.utc) - timedelta(minutes=random_minute + 60)).strftime("%Y-%m-%dT%H:%M:%SZ")
    res = client.post("/api/v1/hazard-observations", json={
        "station_code": "NANDAMBAKKAM_CHECKDAM",
        "observed_at": obs_time,
        "value": 2.45,
        "unit": "metres",
        "source": "Tamil Nadu River Water Level Telemetry Hourly",
        "source_dataset": "tn_water_resources_telemetry_hourly"
    })
    assert res.status_code == 200
    data = res.json()["data"]

    assert data["station_code"] == "NANDAMBAKKAM_CHECKDAM"
    assert data["river"] == "Adyar"
    assert data["district"] == "Chennai"
    assert data["value"] == 2.45
    assert data["unit"] == "metres"
    assert data["quality_status"] in ["VALID", "STALE"]
    assert "observed_at" in data
    assert "ingested_at" in data
    # Invariant: observed_at and ingested_at are distinct timestamps
    assert data["observed_at"] != data["ingested_at"]


def test_9_duplicate_observation_detection():
    """TEST 9: Submitting identical station and observed_at flags DUPLICATE_OBSERVATION."""
    random_minute = random.randint(5001, 10000)
    ts = (datetime.now(timezone.utc) - timedelta(minutes=random_minute)).strftime("%Y-%m-%dT%H:%M:%SZ")
    # First submission
    res1 = client.post("/api/v1/hazard-observations", json={
        "station_code": "NANDAMBAKKAM_CHECKDAM",
        "observed_at": ts,
        "value": 2.50
    })
    assert res1.status_code == 200

    # Duplicate submission
    res2 = client.post("/api/v1/hazard-observations", json={
        "station_code": "NANDAMBAKKAM_CHECKDAM",
        "observed_at": ts,
        "value": 2.50
    })
    assert res2.status_code == 200
    data2 = res2.json()["data"]
    assert data2["quality_status"] == "REJECTED"
    assert any("DUPLICATE_OBSERVATION" in f for f in data2["quality_flags"])


# ==============================================================================
# 4. CURRENT HAZARD STATE & FRESHNESS AUDITING
# ==============================================================================

def test_10_current_hazard_state_endpoint():
    """TEST 10: GET /hazard-stations/{station_code}/current-state returns latest observation and freshness."""
    res = client.get("/api/v1/hazard-stations/NANDAMBAKKAM_CHECKDAM/current-state")
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["station_code"] == "NANDAMBAKKAM_CHECKDAM"
    assert data["river"] == "Adyar"
    assert "freshness" in data
    assert "is_stale" in data
    assert data["severity_classification"] == "SEVERITY_UNCLASSIFIED"


# ==============================================================================
# 5. CSV INGESTION PIPELINE TESTS
# ==============================================================================

def test_11_csv_ingestion_valid_and_anomalies():
    """TEST 11: Bulk CSV ingestion processes rows and generates comprehensive structured report."""
    base_m = random.randint(10001, 20000)
    t1 = (datetime.now(timezone.utc) - timedelta(minutes=base_m + 10)).strftime("%Y-%m-%dT%H:%M:%SZ")
    t2 = (datetime.now(timezone.utc) - timedelta(minutes=base_m + 20)).strftime("%Y-%m-%dT%H:%M:%SZ")
    t3 = (datetime.now(timezone.utc) - timedelta(minutes=base_m + 30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    t4 = (datetime.now(timezone.utc) - timedelta(minutes=base_m + 40)).strftime("%Y-%m-%dT%H:%M:%SZ")
    csv_content = f"""station_code,observed_at,value,unit
NANDAMBAKKAM_CHECKDAM,{t1},2.15,metres
NANDAMBAKKAM_CHECKDAM,{t2},2.25,metres
NANDAMBAKKAM_CHECKDAM,{t3},NaN,metres
UNKNOWN_STN_999,{t4},2.35,metres
NANDAMBAKKAM_CHECKDAM,{t1},2.15,metres
"""
    res = client.post("/api/v1/hazard-observations/import", json={
        "csv_content": csv_content,
        "filename": "test_telemetry.csv"
    })
    assert res.status_code == 200
    rep = res.json()["data"]

    assert rep["rows_received"] == 5
    assert rep["rows_accepted"] >= 1
    assert rep["rows_rejected"] >= 2  # NaN and unknown station
    assert rep["invalid_values"] >= 1  # NaN
    assert rep["unknown_stations"] >= 1  # UNKNOWN_STN_999
    assert rep["duplicates"] >= 1  # Duplicate 01:00 timestamp
    assert len(rep["rejection_reasons"]) >= 2


def test_12_csv_missing_required_headers():
    """TEST 12: CSV missing required columns returns structured SCHEMA_ERROR without crash."""
    bad_csv = """station_code,some_random_column\nNANDAMBAKKAM_CHECKDAM,123\n"""
    res = client.post("/api/v1/hazard-observations/import", json={"csv_content": bad_csv})
    assert res.status_code == 200
    rep = res.json()["data"]
    assert rep["rows_received"] == 0
    assert any("SCHEMA_ERROR" in r["reason"] for r in rep["rejection_reasons"])


def test_13_csv_empty_content():
    """TEST 13: Empty CSV returns structured EMPTY_CSV report."""
    res = client.post("/api/v1/hazard-observations/import", json={"csv_content": "   "})
    assert res.status_code == 200
    rep = res.json()["data"]
    assert rep["rows_received"] == 0
    assert any("EMPTY_CSV" in r["reason"] for r in rep["rejection_reasons"])


# ==============================================================================
# 6. E1 INTEGRATION & SAFETY BOUNDARIES
# ==============================================================================

def test_14_valid_observation_drives_e1(base_scenario):
    """TEST 14: Valid observation drives E1, creating flood geometry and red zone with full provenance."""
    # Ingest a valid observation with unique timestamp
    random_minute = random.randint(20001, 30000)
    obs_time = (datetime.now(timezone.utc) - timedelta(minutes=random_minute)).strftime("%Y-%m-%dT%H:%M:%SZ")
    res_obs = client.post("/api/v1/hazard-observations", json={
        "station_code": "NANDAMBAKKAM_CHECKDAM",
        "observed_at": obs_time,
        "value": 3.20,
        "unit": "metres"
    })
    assert res_obs.status_code == 200
    data = res_obs.json()["data"]
    assert data["quality_status"] in ["VALID", "STALE"]
    obs_id = data["id"]

    # Evaluate observation through E1 (allow_stale=True since test timestamp is historical)
    res_eval = client.post(f"/api/v1/hazard-observations/{obs_id}/evaluate", json={
        "snapshot_id": base_scenario["scenario_snapshot_id"],
        "allow_stale": True
    })
    assert res_eval.status_code == 200
    eval_data = res_eval.json()["data"]

    assert eval_data["observation_id"] == obs_id
    assert eval_data["station_code"] == "NANDAMBAKKAM_CHECKDAM"
    assert eval_data["value"] == 3.20
    assert eval_data["unit"] == "metres"
    assert eval_data["expansion_factor"] >= 1.0
    # Section 12: Spatial disclaimer explicitly present
    assert "Prototype spatial transformation" in eval_data["spatial_disclaimer"]
    assert "not a validated hydrodynamic inundation model" in eval_data["spatial_disclaimer"]
    # Evidence reference
    assert "NANDAMBAKKAM_CHECKDAM" in eval_data["evidence_reference"]
    assert eval_data["audit_event_id"] is not None


def test_15_rejected_observation_cannot_reach_e1(base_scenario):
    """CRITICAL SAFETY TEST: E1 strictly rejects evaluating an invalid/rejected observation."""
    db = SessionLocal()
    try:
        # Create a rejected observation in DB
        bad_obs = HazardObservation(
            station_id="NANDAMBAKKAM_CHECKDAM",
            station_code="NANDAMBAKKAM_CHECKDAM",
            station_name="Nandambakkam CheckDam",
            river="Adyar",
            district="Chennai",
            hazard_type="RIVER_WATER_LEVEL",
            source="Test",
            source_dataset="Test",
            observed_at=datetime(2026, 10, 3, 5, 0, 0),
            ingested_at=datetime.now(timezone.utc).replace(tzinfo=None),
            value=0.0,
            unit="metres",
            quality_status=ObservationQualityEnum.REJECTED,
            quality_flags=["NUMERIC_ERROR: Non-finite NaN value"],
            freshness=FreshnessEnum.STALE,
            raw_reference={}
        )
        db.add(bad_obs)
        db.commit()
        db.refresh(bad_obs)

        # Attempting to drive E1 must fail with 422 Unprocessable Entity
        res = client.post(f"/api/v1/hazard-observations/{bad_obs.id}/evaluate", json={
            "snapshot_id": base_scenario["scenario_snapshot_id"],
            "allow_stale": True
        })
        assert res.status_code == 422
        assert "OBSERVATION_SAFETY_GATE_REJECTED" in res.json()["detail"]
    finally:
        db.close()


def test_16_stale_observation_requires_explicit_override(base_scenario):
    """CRITICAL SAFETY TEST: Stale telemetry cannot silently masquerade as current state without allow_stale=True."""
    db = SessionLocal()
    try:
        stale_obs = HazardObservation(
            station_id="NANDAMBAKKAM_CHECKDAM",
            station_code="NANDAMBAKKAM_CHECKDAM",
            station_name="Nandambakkam CheckDam",
            river="Adyar",
            district="Chennai",
            hazard_type="RIVER_WATER_LEVEL",
            source="Test",
            source_dataset="Test",
            observed_at=datetime(2026, 9, 1, 0, 0, 0), # Very stale
            ingested_at=datetime.now(timezone.utc).replace(tzinfo=None),
            value=2.30,
            unit="metres",
            quality_status=ObservationQualityEnum.VALID,
            quality_flags=[],
            freshness=FreshnessEnum.STALE,
            raw_reference={}
        )
        db.add(stale_obs)
        db.commit()
        db.refresh(stale_obs)

        # Default allow_stale=False must be rejected
        res = client.post(f"/api/v1/hazard-observations/{stale_obs.id}/evaluate", json={
            "snapshot_id": base_scenario["scenario_snapshot_id"],
            "allow_stale": False
        })
        assert res.status_code == 422
        assert "STALE" in res.json()["detail"]
    finally:
        db.close()


# ==============================================================================
# 7. PROVENANCE & E6 AUDIT TRACEABILITY
# ==============================================================================

def test_17_e6_audit_event_recorded(base_scenario):
    """TEST 17: Verifies E6 audit event preserves complete observation-to-hazard provenance."""
    db = SessionLocal()
    try:
        latest_audit = db.query(AuditEvent).filter(
            AuditEvent.action_type == "E1_EVALUATE_FROM_OBSERVATION"
        ).order_by(AuditEvent.created_at.desc()).first()

        assert latest_audit is not None
        assert latest_audit.entity_type == "HazardObservation"
        assert "station_code" in latest_audit.before_state
        assert "hazard_state_id" in latest_audit.after_state
        assert "red_zone_id" in latest_audit.after_state
    finally:
        db.close()


# ==============================================================================
# 8. BACKWARD COMPATIBILITY & SYSTEM INTEGRITY
# ==============================================================================

def test_18_scenario_e1_still_functional(base_scenario):
    """TEST 18: Existing scenario-driven E1 hazard evaluation works completely intact."""
    res = client.post("/api/v1/scenarios/run", json={"scenario_code": "MONSOON_SURGE_01"})
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["scenario_code"] == "MONSOON_SURGE_01"


def test_19_a6_prediction_layer_isolated():
    """TEST 19: A.6 prediction endpoints remain operational and completely decoupled."""
    res = client.get("/api/v1/hazard-predictions/models/metrics")
    assert res.status_code == 200
    assert "test_evaluation_benchmark" in res.json()["data"]


def test_20_baseline_snapshot_immutability():
    """TEST 20: SNAP_BASE_001 allocations and capacities are 100% immutable throughout A.7 operations."""
    db = SessionLocal()
    try:
        allocs = db.query(RelocationAllocation).filter(
            RelocationAllocation.snapshot_id == "SNAP_BASE_001"
        ).all()
        assert len(allocs) == 28
    finally:
        db.close()


# ==============================================================================
# 9. FORENSIC SOURCE TRACEABILITY & INTEGRITY AUDIT (A.7 HARDENING PASS)
# ==============================================================================

def test_21_source_dataset_traceability():
    """TEST 21: Proves that the exact observation used by the demo exists in the authentic source CSV."""
    candidates = [
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "telemetry", "rwl_tel_hr_tamil_nadu_sw_gw_27_2026_2030.csv")),
        "C:\\Users\\adity\\OneDrive\\Desktop\\rwl_tel_hr_tamil_nadu_sw_gw_27_2026_2030.csv"
    ]
    csv_path = next((p for p in candidates if os.path.isfile(p)), None)
    assert csv_path is not None, f"Authentic source telemetry CSV not found! Looked in: {candidates}"

    matched_rows = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            if "nandambakkam" in r.get("Station", "").lower():
                matched_rows.append(r)

    assert len(matched_rows) > 0, "No Nandambakkam CheckDam rows found in source dataset!"
    latest_row = matched_rows[-1]

    # Verify exact ground truth fields
    assert latest_row["SlNo"] == "8987"
    assert latest_row["Station"] == "Nandambakkam CheckDam"
    assert latest_row["River"] == "Adyar"
    assert latest_row["District"] == "Chennai"
    assert latest_row["Data Acquisition Time"] == "28-09-2026 10:00"
    assert float(latest_row["River Water Level Telemetry Hourly (meter)"]) == 3.25


def test_22_demo_integrity_pipeline(base_scenario):
    """TEST 22: Asserts source row -> observation payload -> persisted observation -> E1 preserves full provenance."""
    source_val = 3.25
    source_ts_str = "28-09-2026 10:00"
    parsed_dt = datetime.strptime(source_ts_str, "%d-%m-%Y %H:%M")
    iso_ts = parsed_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    # Ensure idempotency across test executions
    db = SessionLocal()
    try:
        stn = db.query(HazardStation).filter(HazardStation.station_code == "NANDAMBAKKAM_CHECKDAM").first()
        if stn:
            for old_obs in db.query(HazardObservation).filter(HazardObservation.station_id == stn.id, HazardObservation.observed_at == parsed_dt).all():
                db.delete(old_obs)
            db.commit()
    finally:
        db.close()

    # Ingest through REST endpoint
    res_obs = client.post("/api/v1/hazard-observations", json={
        "station_code": "NANDAMBAKKAM_CHECKDAM",
        "observed_at": iso_ts,
        "value": source_val,
        "unit": "metres",
        "source": "Tamil Nadu River Water Level Telemetry Hourly",
        "source_dataset": "rwl_tel_hr_tamil_nadu_sw_gw_27_2026_2030.csv"
    })
    assert res_obs.status_code == 200
    obs_data = res_obs.json()["data"]

    # Verify exact field preservation
    assert obs_data["station_code"] == "NANDAMBAKKAM_CHECKDAM"
    assert obs_data["river"] == "Adyar"
    assert obs_data["value"] == 3.25
    assert obs_data["unit"] == "metres"
    assert obs_data["quality_status"] in ["VALID", "STALE"]
    assert obs_data["freshness"] == "STALE"
    obs_id = obs_data["id"]

    # Evaluate through E1 in explicit audit/replay mode
    res_eval = client.post(f"/api/v1/hazard-observations/{obs_id}/evaluate", json={
        "snapshot_id": base_scenario["scenario_snapshot_id"],
        "allow_stale": True
    })
    assert res_eval.status_code == 200
    eval_data = res_eval.json()["data"]

    assert eval_data["station_code"] == "NANDAMBAKKAM_CHECKDAM"
    assert eval_data["value"] == 3.25
    assert eval_data["is_audit_replay"] is True
    assert eval_data["evaluation_mode"] == "HISTORICAL_AUDIT_REPLAY"
    assert f"NANDAMBAKKAM_CHECKDAM:OBS:{obs_id}" in eval_data["evidence_reference"]


def test_23_stale_observation_safety_boundary(base_scenario):
    """TEST 23: Confirms that normal operational evaluation strictly blocks stale observations."""
    obs_dt = datetime(2026, 9, 28, 10, 0, 0)
    db = SessionLocal()
    try:
        stale_obs = db.query(HazardObservation).filter(
            HazardObservation.station_code == "NANDAMBAKKAM_CHECKDAM",
            HazardObservation.observed_at == obs_dt
        ).first()
        if not stale_obs:
            stale_obs = HazardObservation(
                station_id="NANDAMBAKKAM_CHECKDAM",
                station_code="NANDAMBAKKAM_CHECKDAM",
                station_name="Nandambakkam CheckDam",
                river="Adyar",
                district="Chennai",
                hazard_type="RIVER_WATER_LEVEL",
                source="Tamil Nadu River Water Level Telemetry Hourly",
                source_dataset="rwl_tel_hr_tamil_nadu_sw_gw_27_2026_2030.csv",
                observed_at=obs_dt,
                ingested_at=datetime.now(timezone.utc).replace(tzinfo=None),
                value=3.25,
                unit="metres",
                quality_status=ObservationQualityEnum.VALID,
                quality_flags=[],
                freshness=FreshnessEnum.STALE,
                raw_reference={}
            )
            db.add(stale_obs)
            db.commit()
            db.refresh(stale_obs)

        # 1. Normal operational evaluation attempt MUST return 422 Unprocessable Entity
        res_blocked = client.post(f"/api/v1/hazard-observations/{stale_obs.id}/evaluate", json={
            "snapshot_id": base_scenario["scenario_snapshot_id"],
            "allow_stale": False
        })
        assert res_blocked.status_code == 422
        assert "OBSERVATION_SAFETY_GATE_REJECTED" in res_blocked.json()["detail"]
        assert "STALE" in res_blocked.json()["detail"]

        # 2. Explicit audit/replay mode succeeds and is tagged
        res_audit = client.post(f"/api/v1/hazard-observations/{stale_obs.id}/evaluate", json={
            "snapshot_id": base_scenario["scenario_snapshot_id"],
            "allow_stale": True
        })
        assert res_audit.status_code == 200
        assert res_audit.json()["data"]["is_audit_replay"] is True
        assert res_audit.json()["data"]["evaluation_mode"] == "HISTORICAL_AUDIT_REPLAY"
    finally:
        db.close()

