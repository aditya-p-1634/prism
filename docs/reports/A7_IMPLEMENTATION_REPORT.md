# PRISM V2 — Phase A.7 Implementation Report
## Real-World Hazard Data Integration & Observation-Driven E1

### Executive Summary
Phase A.7 establishes a safe, auditable, observation-driven hazard intake layer for PRISM. It integrates real hydrometric telemetry from the **Tamil Nadu River Water Level Telemetry Hourly** dataset, centered on pilot station **Nandambakkam CheckDam** on the **Adyar River** in **Chennai**.

Crucially, A.7 enforces a strict boundary between **OBSERVATION** ("what the sensor measured at time $T$") and **PREDICTION** ("what the model predicts at future time $T+h$"). A.6's experimental ML prediction layer remains isolated and decoupled. Furthermore, A.7 implements zero fabricated safety thresholds: observations are classified as `VALID OBSERVATION, SEVERITY UNCLASSIFIED` unless authoritative, published flood stages are established.

---

### Core Architectural Contracts & Invariants

```
REAL TELEMETRY (CSV / Gauge Stream)
        ↓
INGESTION LAYER (StationRegistry, ObservationIngestionService)
        ↓
QUALITY VALIDATION (ObservationValidator: Numeric, Timestamp, Station, Unit, Duplicate, Freshness)
        ↓
PERSISTENT OBSERVATION RECORD (HazardObservation: observed_at != ingested_at)
        ↓
CURRENT HAZARD STATE (Latest Valid Observation, Freshness: FRESH / AGING / STALE)
        ↓
E1 HAZARD ENGINE (evaluate_from_observation with Safety Gate & Prototype Spatial Transformation)
        ↓
E2 Vulnerability → E3 Capacity → E4 Routing / Relocation → E5 Temporal Simulation → E6 Audit
```

#### Key Architectural Decisions:
1. **Timestamp Separation Invariant:**
   `observed_at != ingested_at`
   - `observed_at`: Exact UTC timestamp when the physical sensor measured water level at the station.
   - `ingested_at`: Exact UTC timestamp when PRISM validated and persisted the record.
2. **Observation vs Prediction Distinction:**
   Telemetry observations are empirical ground truth measurements. They are never converted into predictions or blended with model forecasts.
3. **No Fabricated Safety Thresholds:**
   Prototype flood thresholds from A.6 are not assigned to Nandambakkam CheckDam. Valid observations without authoritative danger levels are explicitly marked `SEVERITY_UNCLASSIFIED`.
4. **Prototype Spatial Transformation Disclaimer:**
   A single river gauge measurement does not produce a hydrodynamic flood inundation map. Any polygon expansion for demonstration purposes is labeled:
   > *"Prototype spatial transformation — not a validated hydrodynamic inundation model."*
5. **Real vs Synthetic Boundary:**
   - **Real / Observed:** River water level, station metadata, timestamp, source, quality status.
   - **Synthetic / Prototype:** Study area households, population, shelters, road network, evacuation capacity.
   Demo and documentation explicitly note: *"Real telemetry driving a controlled PRISM prototype environment."*
6. **E1 Safety Boundary:**
   Observations marked `REJECTED` or `STALE` (without explicit `allow_stale=True` audit flag) raise `ObservationSafetyException` and **NEVER** reach E1. Previous observations are never masqueraded as fresh telemetry.
7. **Canonical Baseline Immutability:**
   Baseline snapshot `SNAP_BASE_001` (28 allocations) is 100% immutable throughout all A.7 operations.

---

### Station Registry & Pilot Station Specification

- **Station Code:** `NANDAMBAKKAM_CHECKDAM`
- **Station Name:** Nandambakkam CheckDam
- **River / Basin:** Adyar River
- **District / State:** Chennai, Tamil Nadu
- **Coordinates:** `13.0161° N, 80.1828° E` (Latitude `13.01611111`, Longitude `80.18277778`)
- **Hazard Type:** `RIVER_WATER_LEVEL`
- **Measurement Unit:** `metres` (normalized from `meter`)
- **Primary Source:** Tamil Nadu River Water Level Telemetry Hourly dataset (`rwl_tel_hr_tamil_nadu_sw_gw_27_2026_2030.csv`)
- **Exact Source Row:** SlNo `8987` (Line `8988`)
- **Exact Source Timestamp:** `28-09-2026 10:00` (`2026-09-28T10:00:00Z` UTC)
- **Exact Water Level:** `3.25` metres
- **Quality Status:** `VALID` (uncorrupted physical sensor telemetry)
- **Freshness Classification:** `STALE` (>6 hours elapsed relative to current wall-clock)
- **Data Category:** `HISTORICAL REAL TELEMETRY OBSERVATION` (NOT `CURRENT LIVE TELEMETRY`)

---

### Real vs Synthetic Terminology Standard

PRISM enforces strict semantic boundaries across all logs, DTOs, and documentation:
1. **REAL HISTORICAL TELEMETRY:** Actual row originating from the supplied Tamil Nadu dataset (`rwl_tel_hr_tamil_nadu_sw_gw_27_2026_2030.csv`).
2. **SYNTHETIC TEST OBSERVATION:** Programmatically generated value (e.g. `NaN`, boundary edge values) used strictly in automated test suites and error-handling demos.
3. **CURRENT LIVE TELEMETRY:** Must **NEVER** be claimed unless an active live streaming feed is connected. A.7 currently ingests validated real historical telemetry.

---

### Stale Observation Safety Audit

PRISM enforces a dual-mode safety boundary on telemetry freshness:
- **Normal Operation (`allow_stale=False`, default):**
  If `freshness == STALE`, E1 evaluation is strictly **BLOCKED** at the system boundary. The service raises `ObservationSafetyException` and returns HTTP `422 Unprocessable Entity`. **E1 IS NOT UPDATED.** Stale telemetry cannot silently masquerade as current operational hazard state.
- **Historical Audit / Replay Mode (`allow_stale=True`):**
  Permits evaluation solely for retrospective audit analysis and historical scenario replay. The resulting hazard state is permanently tagged with:
  - `is_audit_replay: True`
  - `evaluation_mode: "HISTORICAL_AUDIT_REPLAY"`
  - E6 AuditEvent recording `evaluation_mode` and `is_audit_replay`.

---

### Quality Validation Engine

Validation screens every incoming telemetry record across six dimensions:
1. **Numeric Screening:** Rejects `NaN`, `+Inf`, `-Inf`, and non-numeric strings (`quality_status="REJECTED"`).
2. **Timestamp Screening:** Validates ISO-8601 and regional formats (`%d-%m-%Y %H:%M`), enforces past/current timestamps, and strictly rejects future timestamps.
3. **Station Registry Validation:** Checks station against registered database entities. Unregistered stations are rejected.
4. **Unit Screening & Normalization:** Validates against `metres` (`m`, `meter`, `metres`); unsupported units (feet, psi, etc.) are rejected.
5. **Duplicate Detection:** Checks if an observation for the same station code and `observed_at` timestamp already exists. Flagged as `DUPLICATE_OBSERVATION` (`quality_status="REJECTED"`).
6. **Freshness Auditing:**
   - $\le 2$ hours: `FRESH`
   - $2 - 6$ hours: `AGING`
   - $> 6$ hours: `STALE` (requires explicit `allow_stale=True` override to evaluate in E1 for audit replay).

---

### Database Schema Updates (SQLite)

Two new persistent models added to SQLite database `prism.db`:

#### `hazard_stations`
- `id` (VARCHAR(36), PK)
- `station_code` (VARCHAR(100), UNIQUE, INDEX)
- `station_name` (VARCHAR(255))
- `river` (VARCHAR(100), INDEX)
- `district` (VARCHAR(100))
- `state` (VARCHAR(100))
- `latitude` (FLOAT)
- `longitude` (FLOAT)
- `hazard_type` (VARCHAR(50)) — `RIVER_WATER_LEVEL`
- `unit` (VARCHAR(50)) — `metres`
- `source` (VARCHAR(255))
- `source_dataset` (VARCHAR(255))
- `is_active` (BOOLEAN)
- `warning_threshold_m` (FLOAT, NULLABLE)
- `danger_threshold_m` (FLOAT, NULLABLE)
- `metadata_json` (JSON)
- `created_at` (DATETIME)

#### `hazard_observations`
- `id` (VARCHAR(36), PK)
- `station_id` (VARCHAR(36), FK `hazard_stations.id`)
- `station_code` (VARCHAR(100), INDEX)
- `station_name` (VARCHAR(255))
- `river` (VARCHAR(100))
- `district` (VARCHAR(100))
- `hazard_type` (VARCHAR(50))
- `source` (VARCHAR(255))
- `source_dataset` (VARCHAR(255))
- `observed_at` (DATETIME, INDEX)
- `ingested_at` (DATETIME, INDEX)
- `value` (FLOAT)
- `unit` (VARCHAR(50))
- `quality_status` (VARCHAR(50), INDEX) — `VALID`, `SUSPECT`, `REJECTED`, `MISSING`, `STALE`
- `quality_flags` (JSON)
- `freshness` (VARCHAR(50)) — `FRESH`, `AGING`, `STALE`
- `raw_reference` (JSON)
- `created_at` (DATETIME)

---

### API Surface

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/hazard-stations` | Registers a new monitoring station with coordinate validation. |
| `GET` | `/api/v1/hazard-stations` | Lists registered hazard stations. |
| `GET` | `/api/v1/hazard-stations/{station_code}` | Retrieves station metadata. |
| `GET` | `/api/v1/hazard-stations/{station_code}/current-state` | Retrieves latest valid observation and freshness for a station. |
| `GET` | `/api/v1/hazard-stations/{station_code}/observations` | Historical observations query with pagination and status filter. |
| `POST` | `/api/v1/hazard-observations` | Ingests a single telemetry observation with quality validation. |
| `GET` | `/api/v1/hazard-observations` | Lists observations. |
| `GET` | `/api/v1/hazard-observations/latest` | Returns latest valid observations across all active stations. |
| `POST` | `/api/v1/hazard-observations/import` | Bulk CSV ingestion returning structured ingestion report. |
| `POST` | `/api/v1/hazard-observations/{observation_id}/evaluate` | Evaluates observation through E1 hazard engine with safety gates. |

---

### Test Suite & Verification Results

- **A.7 Dedicated Test Suite:** `apps/api/tests/test_hazard_observation_a7.py` (**23/23 PASSED**)
  - Validation screening: 7 tests
  - Ingestion, duplicate detection & current state: 3 tests
  - CSV parsing & schema errors: 3 tests
  - E1 safety boundary & evaluation: 3 tests
  - Provenance, backward compatibility & immutability: 4 tests
  - **Forensic source traceability (Test 21):** PASSED (proves exact match to SlNo 8987 in source CSV)
  - **Demo integrity pipeline (Test 22):** PASSED (preserves exact station, timestamp, value 3.25m, unit, source)
  - **Stale safety boundary audit (Test 23):** PASSED (proves operational blocking vs explicit audit replay tagging)
- **Full Backend Regression (A.1 to A.7):** **208/208 PASSED** in 24.31s.
- **Deterministic Verification Script:** `scripts/verify_a7_observation_demo.py` (All 12 steps PASSED).

---

### Non-Claims & Safety Declarations

1. **A.7 DOES NOT train or use machine learning models.**
2. **A.7 DOES NOT establish operational flood forecasting.**
3. **A.7 DOES NOT claim live real-time telemetry streaming.**
4. **A.7 DOES NOT claim that a single gauge produces a validated inundation map.**
5. **A.7 DOES NOT invent flood safety thresholds.**
