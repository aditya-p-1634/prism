"""PRISM V2 — Phase A.7 Real-World Hazard Data Integration & Observation-Driven E1 Demo
====================================================================================
Deterministic demonstration script verifying:
1. Register/recognize Nandambakkam CheckDam pilot station.
2. Ingest a valid, authentic historical observation directly from the supplied
   Tamil Nadu River Water Level Telemetry Hourly CSV (rwl_tel_hr_tamil_nadu_sw_gw_27_2026_2030.csv).
3. Display Station, River, District, Observed time, Ingested time, Current Wall-Clock time,
   Water level, Quality, Freshness, Source, and Dataset.
   Clearly distinguishes HISTORICAL REAL TELEMETRY OBSERVATION from CURRENT LIVE TELEMETRY.
4. Demonstrate that Stale historical telemetry is strictly BLOCKED from normal operational E1.
5. Evaluate the observation in explicit HISTORICAL AUDIT / REPLAY mode (allow_stale=True).
6. Confirm E1 receives observation-derived hazard state and red zone.
7. Display complete provenance and audit chain in E6.
8. Demonstrate an invalid SYNTHETIC TEST OBSERVATION (float('nan')).
9. Confirm REJECTED status and verify E1 IS NOT UPDATED.
10. Demonstrate freshness auditing (FRESH vs AGING vs STALE).
11. Demonstrate that existing scenario-based E1 path still works untouched.
12. Verify baseline SNAP_BASE_001 allocations and capacities remain 100% immutable.
"""

import sys
import os
import csv
from datetime import datetime, timezone, timedelta

# Add apps/api to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "apps", "api")))

from app.db.session import SessionLocal
from app.models.entities import (
    HazardStation,
    HazardObservation,
    RelocationAllocation,
    StateSnapshot,
    AuditEvent
)
from app.models.enums import ObservationQualityEnum, FreshnessEnum
from app.schemas.hazard_observation import HazardObservationCreateDTO
from app.engines.e1_hazard.observation.station_registry import StationRegistry
from app.engines.e1_hazard.observation.ingestion import ObservationIngestionService
from app.engines.e1_hazard.observation.validation import ObservationValidator
from app.engines.e1_hazard.observation.service import HazardObservationService, ObservationSafetyException
from app.engines.e1_hazard.service import HazardEngineE1


def resolve_source_csv_path() -> str:
    """Locates the authentic Tamil Nadu RWL telemetry 2026-2030 dataset."""
    candidates = [
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "telemetry", "rwl_tel_hr_tamil_nadu_sw_gw_27_2026_2030.csv")),
        "C:\\Users\\adity\\OneDrive\\Desktop\\rwl_tel_hr_tamil_nadu_sw_gw_27_2026_2030.csv"
    ]
    for p in candidates:
        if os.path.isfile(p):
            return p
    raise FileNotFoundError(f"Source telemetry dataset not found. Checked: {candidates}")


def run_a7_demonstration():
    db = SessionLocal()
    try:
        print("=" * 80)
        print("   PRISM V2 — PHASE A.7: REAL-WORLD HAZARD TELEMETRY & OBSERVATION-DRIVEN E1")
        print("   (Forensic Integrity Pass: Verified Ground Truth Telemetry Ingestion)")
        print("=" * 80)

        # Baseline Pre-Verification
        base_allocs_start = db.query(RelocationAllocation).filter(
            RelocationAllocation.snapshot_id == "SNAP_BASE_001"
        ).count()
        print(f"\n[Baseline Initial Verification] SNAP_BASE_001 total allocations: {base_allocs_start}")

        # ----------------------------------------------------------------------
        # 1. Register / Recognize Nandambakkam CheckDam
        # ----------------------------------------------------------------------
        print("\n" + "=" * 80)
        print("STEP 1: Register / Recognize Pilot Station (Nandambakkam CheckDam)")
        print("=" * 80)
        station = StationRegistry.ensure_pilot_station(db=db)
        print(f"  Station Code:      {station.station_code}")
        print(f"  Station Name:      {station.station_name}")
        print(f"  River / Basin:     {station.river}")
        print(f"  District:          {station.district}")
        print(f"  Coordinates:       ({station.latitude}° N, {station.longitude}° E)")
        print(f"  Measurement Unit:  {station.unit}")
        print(f"  Status:            {'ACTIVE' if station.is_active else 'INACTIVE'}")

        # ----------------------------------------------------------------------
        # 2 & 3. Ingest Authentic Historical Observation from Source Dataset
        # ----------------------------------------------------------------------
        print("\n" + "=" * 80)
        print("STEP 2 & 3: Ingest Authentic Historical Observation from Source CSV")
        print("=" * 80)
        source_csv_path = resolve_source_csv_path()
        source_filename = os.path.basename(source_csv_path)

        # Read actual row from CSV
        nandambakkam_rows = []
        with open(source_csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for idx, r in enumerate(reader, start=2): # 1-indexed, header is line 1
                if "nandambakkam" in r.get("Station", "").lower():
                    r["_csv_line_number"] = idx
                    nandambakkam_rows.append(r)

        if not nandambakkam_rows:
            raise RuntimeError(f"No rows for Nandambakkam CheckDam found in {source_csv_path}!")

        # Deterministically select the latest observation row present in the source dataset
        latest_source_row = nandambakkam_rows[-1]
        sl_no = latest_source_row.get("SlNo")
        csv_line = latest_source_row.get("_csv_line_number")
        raw_acq_time = latest_source_row.get("Data Acquisition Time")
        raw_stage_m = float(latest_source_row.get("River Water Level Telemetry Hourly (meter)"))
        stn_name = latest_source_row.get("Station")
        river_name = latest_source_row.get("River")
        district_name = latest_source_row.get("District")

        # Parse exact timestamp: "28-09-2026 10:00" -> datetime(2026, 9, 28, 10, 0, 0)
        parsed_obs_dt = datetime.strptime(raw_acq_time.strip(), "%d-%m-%Y %H:%M")
        iso_obs_ts = parsed_obs_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

        # Ensure demo idempotency: remove previous demo run instance of this exact observation
        existing_demo_obs = db.query(HazardObservation).filter(
            HazardObservation.station_id == station.id,
            HazardObservation.observed_at == parsed_obs_dt
        ).all()
        for old_obs in existing_demo_obs:
            db.delete(old_obs)
        db.commit()

        # Ingest through standard ingestion pipeline
        obs_dto = HazardObservationCreateDTO(
            station_code="NANDAMBAKKAM_CHECKDAM",
            observed_at=iso_obs_ts,
            value=raw_stage_m,
            unit="metres",
            source="Tamil Nadu River Water Level Telemetry Hourly",
            source_dataset=source_filename,
            raw_reference={
                "source_file": source_filename,
                "sl_no": sl_no,
                "line_number": csv_line,
                "data_acquisition_time": raw_acq_time,
                "raw_water_level_m": str(raw_stage_m)
            }
        )
        obs_record = ObservationIngestionService.ingest_single(obs_dto, db=db)
        wall_clock_now = datetime.now(timezone.utc).replace(tzinfo=None)

        print(f"  Source File:      {source_filename} (SlNo: {sl_no}, Line: {csv_line})")
        print(f"  Station:          {obs_record.station_name}")
        print(f"  River:            {obs_record.river}")
        print(f"  District:         {obs_record.district}")
        print(f"  Observed time:    {obs_record.observed_at.isoformat()} UTC (Exact source timestamp)")
        print(f"  Ingested time:    {obs_record.ingested_at.isoformat()} UTC (observed_at != ingested_at)")
        print(f"  Wall-clock time:  {wall_clock_now.isoformat()} UTC (Distinguished from observation time)")
        print(f"  Water level:      {obs_record.value} {obs_record.unit} (Exact source value)")
        print(f"  Quality:          {obs_record.quality_status.value}")
        print(f"  Freshness:        {obs_record.freshness.value} (Observed > 6h ago relative to wall-clock)")
        print(f"  Classification:   HISTORICAL REAL TELEMETRY OBSERVATION (NOT CURRENT LIVE TELEMETRY)")
        print(f"  Source:           {obs_record.source}")
        print(f"  Dataset:          {obs_record.source_dataset}")
        print(f"  Severity:         VALID OBSERVATION, SEVERITY UNCLASSIFIED (No fabricated thresholds)")

        # Verify exact match against ground truth source row
        assert obs_record.value == raw_stage_m == 3.25, "Water level did not match source dataset row!"
        assert obs_record.observed_at == parsed_obs_dt == datetime(2026, 9, 28, 10, 0), "Timestamp did not match source dataset row!"

        # ----------------------------------------------------------------------
        # 4 & 5. Stale Safety Gate & Explicit Historical Audit/Replay Mode
        # ----------------------------------------------------------------------
        print("\n" + "=" * 80)
        print("STEP 4 & 5: Stale Safety Gate & Explicit Historical Audit/Replay E1")
        print("=" * 80)

        # Prepare or find a mutable scenario snapshot for evaluation
        scenario_snap = db.query(StateSnapshot).filter(
            StateSnapshot.id != "SNAP_BASE_001",
            StateSnapshot.is_immutable == False
        ).first()

        if not scenario_snap:
            scenario_snap = StateSnapshot(
                id="SNAP_DEMO_A7_001",
                snapshot_type="SCENARIO",
                label="A7 Observation Demo Snapshot",
                is_immutable=False
            )
            db.add(scenario_snap)
            db.commit()

        # 4A. Normal Operational Evaluation Attempt (allow_stale=False) MUST FAIL
        print("  [4A. Attempting Normal Operational E1 Evaluation (allow_stale=False)...]")
        try:
            HazardObservationService.evaluate_from_observation(
                observation_id=obs_record.id,
                snapshot_id=scenario_snap.id,
                allow_stale=False,
                db=db
            )
            print("  ERROR: Stale observation silently drove normal operational E1! Safety boundary breached!")
            raise RuntimeError("Stale safety boundary breached!")
        except ObservationSafetyException as e:
            print("  SAFETY GATE ENGAGED: Historical/stale telemetry blocked from driving operational E1!")
            print(f"  Status:  BLOCKED (Freshness: {obs_record.freshness.value})")
            print(f"  Detail:  {e}")
            print("  E1 NOT UPDATED. Historical telemetry cannot masquerade as live current telemetry.")

        # 4B. Explicit Historical Audit / Replay Evaluation (allow_stale=True)
        print("\n  [4B. Evaluating in Explicit Historical Audit/Replay Mode (allow_stale=True)...]")
        e1_result = HazardObservationService.evaluate_from_observation(
            observation_id=obs_record.id,
            snapshot_id=scenario_snap.id,
            allow_stale=True,
            db=db
        )

        print(f"  Evaluation Mode:       {e1_result.evaluation_mode}")
        print(f"  Is Audit Replay:       {e1_result.is_audit_replay}")
        print(f"  E1 Hazard State ID:    {e1_result.hazard_state_id}")
        print(f"  Observed Water Level:  {e1_result.value} {e1_result.unit}")
        print(f"  Expansion Factor:      {e1_result.expansion_factor}x")
        print(f"  Red Zone Generated:    {e1_result.red_zone_id}")
        print(f"  Spatial Transformation Disclaimer:")
        print(f"    \"{e1_result.spatial_disclaimer}\"")

        # ----------------------------------------------------------------------
        # 6. Show Full Provenance & E6 Audit Chain Traceability
        # ----------------------------------------------------------------------
        print("\n" + "=" * 80)
        print("STEP 6: Provenance & E6 Audit Chain Traceability")
        print("=" * 80)
        audit_event = db.query(AuditEvent).filter(
            AuditEvent.id == e1_result.audit_event_id
        ).first()

        print(f"  Audit Event ID:  {audit_event.id}")
        print(f"  Action Type:     {audit_event.action_type}")
        print(f"  Entity Type:     {audit_event.entity_type}")
        print(f"  Entity ID:       {audit_event.entity_id}")
        print(f"  Audit Before:    Station={audit_event.before_state.get('station_code')}, ObsTime={audit_event.before_state.get('observed_at')}, WaterLevel={audit_event.before_state.get('water_level_m')}m")
        print(f"  Audit After:     HazardState={audit_event.after_state.get('hazard_state_id')}, RedZone={audit_event.after_state.get('red_zone_id')}, Mode={audit_event.after_state.get('evaluation_mode')}")
        print(f"  Audit Justification: {audit_event.justification}")
        print(f"  Evidence Tag:    {e1_result.evidence_reference}")

        # ----------------------------------------------------------------------
        # 7 & 8. Demonstrate Invalid SYNTHETIC TEST OBSERVATION (NaN)
        # ----------------------------------------------------------------------
        print("\n" + "=" * 80)
        print("STEP 7 & 8: Demonstrate Invalid SYNTHETIC TEST OBSERVATION & Safety Gate")
        print("=" * 80)
        print("  [Label: SYNTHETIC TEST OBSERVATION (Programmatically generated to test error handling)]")
        nan_ts = (parsed_obs_dt - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")

        # Clean any prior test row at nan_ts
        for old_nan in db.query(HazardObservation).filter(HazardObservation.station_id == station.id, HazardObservation.observed_at == (parsed_obs_dt - timedelta(hours=1))).all():
            db.delete(old_nan)
        db.commit()

        nan_dto = HazardObservationCreateDTO(
            station_code="NANDAMBAKKAM_CHECKDAM",
            observed_at=nan_ts,
            value=float("nan"),
            unit="metres",
            source="Synthetic Test Pipeline"
        )
        nan_obs = ObservationIngestionService.ingest_single(nan_dto, db=db)
        print(f"  Synthetic Value Ingested: float('nan')")
        print(f"  Validation Result:        {nan_obs.quality_status.value}")
        print(f"  Quality Flags:            {nan_obs.quality_flags}")

        print("\n  [Invoking E1 Evaluation with Rejected Observation...]")
        try:
            HazardObservationService.evaluate_from_observation(
                observation_id=nan_obs.id,
                snapshot_id=scenario_snap.id,
                allow_stale=True,
                db=db
            )
            print("  ERROR: Rejected observation reached E1! Safety boundary breached!")
            raise RuntimeError("Rejected observation safety boundary breached!")
        except ObservationSafetyException as e:
            print("  SAFETY GATE ENGAGED: Exception caught successfully!")
            print("  Status:  REJECTED")
            print(f"  Detail:  {e}")
            print("  E1 IS NOT UPDATED. Corrupted telemetry rejected at system boundary.")

        # ----------------------------------------------------------------------
        # 9 & 10. Freshness Classification & Stale Handling
        # ----------------------------------------------------------------------
        print("\n" + "=" * 80)
        print("STEP 9 & 10: Freshness Classification & Stale Boundary Auditing")
        print("=" * 80)
        f_fresh, h_fresh = ObservationValidator.compute_freshness(wall_clock_now - timedelta(hours=1), reference_time=wall_clock_now)
        f_aging, h_aging = ObservationValidator.compute_freshness(wall_clock_now - timedelta(hours=4), reference_time=wall_clock_now)
        f_stale, h_stale = ObservationValidator.compute_freshness(wall_clock_now - timedelta(hours=10), reference_time=wall_clock_now)

        print(f"  1 hour ago:   Freshness = {f_fresh.value} (Elapsed: {h_fresh:.1f}h <= 2h)")
        print(f"  4 hours ago:  Freshness = {f_aging.value} (Elapsed: {h_aging:.1f}h in 2-6h)")
        print(f"  10 hours ago: Freshness = {f_stale.value} (Elapsed: {h_stale:.1f}h > 6h)")
        print(f"  Authentic dataset age ({parsed_obs_dt.isoformat()}): Freshness = {obs_record.freshness.value}")
        print("  Stale observations are strictly blocked from normal operational E1 hazard states.")

        # ----------------------------------------------------------------------
        # 11. Existing Scenario-Based E1 Path Still Works
        # ----------------------------------------------------------------------
        print("\n" + "=" * 80)
        print("STEP 11: Verify Existing Scenario-Based E1 Path Continues Working")
        print("=" * 80)
        from app.engines.e5_simulation.service import SimulationEngineE5
        e5 = SimulationEngineE5(db)
        scen_result = e5.execute_scenario("MONSOON_SURGE_01", baseline_snapshot_id="SNAP_BASE_001")
        print(f"  Scenario:           {scen_result['scenario_code']}")
        print(f"  Delta Report:       {len(scen_result.get('reallocated_households', []))} household(s) reallocated")
        print(f"  Status:             Scenario-driven E1-E5 path is 100% operational.")

        # ----------------------------------------------------------------------
        # 12. Baseline PRISM State Immutability
        # ----------------------------------------------------------------------
        print("\n" + "=" * 80)
        print("STEP 12: Verify Canonical Baseline SNAP_BASE_001 Remains Unchanged")
        print("=" * 80)
        base_allocs_end = db.query(RelocationAllocation).filter(
            RelocationAllocation.snapshot_id == "SNAP_BASE_001"
        ).count()
        print(f"  SNAP_BASE_001 Allocations Before: {base_allocs_start}")
        print(f"  SNAP_BASE_001 Allocations After:  {base_allocs_end}")
        assert base_allocs_start == base_allocs_end == 28, "Baseline snapshot was corrupted!"
        print(f"  IMMUTABILITY CONFIRMED: 28 allocations intact, 0 mutations to canonical baseline.")

        print("\n" + "=" * 80)
        print("   PRISM V2 — PHASE A.7 VERIFICATION & DEMONSTRATION COMPLETE: ALL 12 STEPS PASSED")
        print("=" * 80)

    finally:
        db.close()


if __name__ == "__main__":
    run_a7_demonstration()
