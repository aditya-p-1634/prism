# PRISM — Engineering Reconciliation & Ground-Truth Specifications

This document serves as the authoritative technical reconciliation between the PRISM master specification documents, the implementation in `apps/api` and `apps/web`, and the verified SQLite database state.

---

## 1. Relocation Population Semantics: 53 Hazard-Affected vs 93 Modeled Allocation

### The Two Populations
* **Total Modeled Planning Universe ($N = 93$):** 28 households across all 4 habitations in the Vayu River Basin study area:
  - `HAB_01` (Riverside Lowlands): 8 households, 26 people.
  - `HAB_02` (Terrace Settlement): 8 households, 27 people.
  - `HAB_03` (Plateau Village): 6 households, 20 people.
  - `HAB_04` (Hillside Edge): 6 households, 20 people.
* **Scenario Hazard-Affected Relocation Demand ($N = 53$):** 16 households across the two inundated habitations under `MONSOON_SURGE_01`:
  - `HAB_01`: 8 households, 26 people (inundated at baseline).
  - `HAB_02`: 8 households, 27 people (newly inundated under +20% rainfall surge and +0.50m river stage).
* **Unaffected Basin Population ($N = 40$):** 12 households residing outside the flood zone:
  - `HAB_03`: 6 households, 20 people.
  - `HAB_04`: 6 households, 20 people.

### Why All 93 People Appear in Modeled Allocations (Model A Architecture)
PRISM operates as a regional disaster decision-support platform rather than an isolated single-site solver:
1. **Baseline State:** Central shelter `DEST_01` (effective capacity 150) had sufficient headroom to accommodate the entire 93-person basin population via direct bridge access (`BRIDGE_01`).
2. **Scenario State (`MONSOON_SURGE_01`):**
   - Direct river crossing `BRIDGE_01` collapses (`CLOSED`).
   - `DEST_02` effective capacity drops from 60 to 45 due to a potable water bottleneck.
   - Inundated households in `HAB_01` and `HAB_02` receive critical emergency priority scores ($P \ge 75$, `IMMEDIATE` priority class).
   - To prevent catastrophic crowding and respect secondary bypass viability, the Engine 4 (E4) CP-SAT solver re-optimizes the entire regional allocation matrix.
3. **The "73 Reassigned" Metric:**
   - 73 people (`HAB_01`: 26, `HAB_02`: 27, `HAB_04`: 20) are shifted away from `DEST_01` to `DEST_03` (46 people) and `DEST_02` (27 people).
   - 20 people (`HAB_03`) remain allocated to `DEST_01`.
   - Total accommodated across all three shelters: $46 + 27 + 20 = 93$ people.
   - Total unmet demand: **0**.
   - All 53 hazard-affected individuals are safely accommodated in the optimal available facilities.

---

## 2. Safe Routing Algorithm: Dijkstra vs A*

* **Active Implementation:** Engine 4 (`RouteAndRelocationEngineE4`) invokes NetworkX's weighted shortest path:
  ```python
  path_node_ids = nx.shortest_path(G, source=start_node.id, target=end_node.id, weight="weight")
  ```
* **Algorithm Ground Truth:** In NetworkX, `nx.shortest_path` with a non-negative edge weight parameter executes **Dijkstra's algorithm**.
* **Edge Weights:** Compound non-negative cost function:
  $$\text{Cost} = 0.45 \cdot \text{Time}_{\text{norm}} + 0.35 \cdot \text{HazardRisk} + 0.10 \cdot \text{Uncertainty} + 0.10 \cdot \text{AccessPenalty}$$
* **Reconciliation with Master Drafts:** Early master design drafts mentioned A* as an algorithmic candidate. In the current verified prototype, Dijkstra's algorithm is the active, deterministic, and optimal routing algorithm. A* with Euclidean/Manhattan distance heuristics remains a recognized architectural scaling option for large national-scale road graphs, but is not the active implementation.

---

## 3. Audit Trail Semantics & Governance

* **Ground Truth Model:** Stored in relational table `audit_events` in SQLite (`AuditEvent` model).
* **Enforcement:**
  - The API exposes only `GET /audit/events`. There are no `UPDATE`, `PATCH`, or `DELETE` endpoints.
  - The service layer only performs inserts (`db.add(audit)`) upon authority actions or scenario runs.
  - Captures `user_id`, `action_type`, `entity_type`, `entity_id`, structured `before_state` JSON, structured `after_state` JSON, `justification`, and UTC timestamp.
* **Claim Discipline:** The system provides **structured operational audit records with before/after state diffs**. It does not claim cryptographic tamper evidence, Merkle trees, or blockchain hash chaining.

---

## 4. Computational Coordinate Reference System (CRS)

* **Synthetic Basin Geometry Extent:**
  - Longitude: $77.10^\circ\text{E}$ to $77.30^\circ\text{E}$
  - Latitude: $28.50^\circ\text{N}$ to $28.70^\circ\text{N}$
* **UTM Zone 43N (EPSG:32643) Verification:**
  - Universal Transverse Mercator (UTM) Zone 43 covers $72.0^\circ\text{E}$ to $78.0^\circ\text{E}$ North of the equator (central meridian $75.0^\circ\text{E}$).
  - The study area coordinates ($77.10^\circ - 77.30^\circ\text{E}$) fall strictly within Zone 43.
  - Therefore, **EPSG:32643 (WGS 84 / UTM zone 43N)** is the mathematically and cartographically exact projected planar coordinate reference system for metric calculations in this geographic zone.
* **Storage & Serialization:** All geometries are stored and transmitted as GeoJSON in **EPSG:4326 (WGS 84)**. Planar buffering and distance calculations project to metric coordinates before evaluation.

---

## 5. Evacuation Lifecycle State Machine (Phase A.2): Plan vs State Separation

### Architectural Core Principle: PLAN ≠ STATE
A critical gap identified in early prototypes was equating a relocation allocation with actual evacuation:
* **The Planning Decision (`allocation_status`):** An allocation (e.g. `H1 -> DEST_02`, status `RECOMMENDED` or `OVERRIDDEN`) represents PRISM's mathematical optimization recommendation. It answers: *"Where should this group go, and along which safe route?"*
* **The Operational Execution State (`evacuation_state`):** Tracks the real-world operational lifecycle of the household or group. It answers: *"What has physically happened to this population group?"*
* **Invariance:** Allocating or reallocating a group does **not** mean they have physically departed, moved, or arrived. All allocations initialize to `PLANNED`.

### Canonical State Progression
```
PLANNED ➔ NOTIFIED ➔ ACKNOWLEDGED ➔ EVACUATION_ORDERED ➔ MOVING ➔ IN_TRANSIT ➔ ARRIVED ➔ SHELTERED
```

### Operational Exception States (Non-Terminal)
Disaster evacuations encounter real-world friction. The following operational exception states are explicitly non-terminal:
1. **`NO_RESPONSE`:** Alert dispatched, but no confirmation received. Can transition to `NOTIFIED` (retry), `EVACUATION_ORDERED` (mandatory order), or `REQUIRES_ASSISTANCE` (welfare check).
2. **`ROUTE_BLOCKED`:** Movement obstructed by sudden inundation or obstacle. Recovers to `IN_TRANSIT` once rerouted or cleared, or escalates to `REQUIRES_ASSISTANCE`.
3. **`STUCK`:** Mechanical or terrain immobilization in transit. Recovers to `IN_TRANSIT` or `ARRIVED` following towing/clearance assistance.
4. **`REQUIRES_ASSISTANCE`:** Mobility, medical, or logistical support needed. Can transition back to `MOVING`, `IN_TRANSIT`, `ARRIVED`, or directly `SHELTERED` once emergency support reaches the group.

### Snapshot Isolation & Immutability
* State transitions are strictly scoped to the allocation's `snapshot_id`.
* The canonical baseline snapshot `SNAP_BASE_001` is protected by Invariant 6 (`BASELINE_IMMUTABLE`). No state transitions may be performed directly on baseline allocations.
* Operators must create or select a scenario branch (where `is_immutable=False`) to record operational evacuation state updates.

---

## 6. Temporal Simulation Clock & In-Transit Dynamic Replanning (Phase A.3)

### Fixed-Timestep Simulation Architecture
Phase A.3 introduces a discrete model clock that advances in configurable timesteps ($\Delta t$, e.g. 5 minutes) across a bounded duration $T$ (e.g. 60 minutes):
* **Model Time vs Wall-Clock Time:** Simulation time $t \in [0, T]$ represents simulated operational time, decoupled from execution duration. Wall-clock execution executes deterministically in seconds.
* **Storage Boundedness (Anti-Bloat Strategy):** PRISM does **not** clone the full relational database graph at each timestep. Instead, each run operates on an isolated scenario branch, persists live simulation progress on `simulation_allocation_progress`, and emits compact, structured `simulation_events`.

### Deterministic Tick Execution Order
1. **Clock Progression:** Simulation clock advances by $\Delta t$; tick counter increments.
2. **Hazard Temporal Interpolation:** Current parameter progress ratio $\rho = \min(1.0, t / T)$ interpolates rainfall and river stage deltas towards the scenario targets.
3. **E1 Hazard Geometry Recomputation:** Deterministically evaluates `compute_expansion_factor()` and metric buffer dilation to compute current inundation extent. Emits `HAZARD_EXPANDED`.
4. **Road Network Safety:** Evaluates all segment geometries against current inundation and scenario closures. Emits `ROAD_BLOCKED` when newly cut off.
5. **In-Transit Movement & Blockage Detection:**
   - Evaluates active routes for `IN_TRANSIT` groups.
   - If blocked: automatically transitions `IN_TRANSIT ➔ ROUTE_BLOCKED` and emits `ROUTE_INVALIDATED`.
   - If safe: advances elapsed travel time. When elapsed time $\ge$ route duration, transitions `IN_TRANSIT ➔ ARRIVED ➔ SHELTERED` and emits `ARRIVAL`/`SHELTERED`.
6. **Dynamic E4 Route Replanning:**
   - Invokes E4 Dijkstra on the updated road graph for `ROUTE_BLOCKED` groups.
   - If a viable alternative route exists: updates route assignment, recovers `ROUTE_BLOCKED ➔ IN_TRANSIT`, and emits `ROUTE_REPLANNED`.
   - If no viable route exists: transitions `ROUTE_BLOCKED ➔ STUCK` (or `REQUIRES_ASSISTANCE`), safely immobilizing the group without crashing. Emits `REROUTE_FAILED`.
7. **Selective CP-SAT Reallocation:**
   - Reallocation is **never** executed blindly on every tick.
   - Only triggered if non-moving planned groups (`PLANNED`, `NOTIFIED`, `ACKNOWLEDGED`) have their assigned destination inundated or rendered completely inaccessible.
   - Already `ARRIVED` or `SHELTERED` populations are strictly protected from re-allocation.
8. **Atomic Persistence:** All events and status updates commit within a single database transaction with automatic rollback upon error.


---

## 7. Dynamic Resource Consumption & Capacity Depletion (Phase A.4)

### Purpose & Architectural Objective
Phase A.4 extends the discrete-time temporal simulation clock (from Phase A.3) so that destination facility resources and effective carrying capacities evolve dynamically over simulated time as evacuees arrive and occupy shelters.

The core causal chain is:
```
PEOPLE ARRIVE ➔ RESOURCES ARE CONSUMED ➔ REMAINING RESOURCE CHANGES ➔ EFFECTIVE CAPACITY CHANGES ➔ DESTINATION FEASIBILITY CHANGES ➔ REALLOCATION SELECTIVELY TRIGGERED
```

### Core Resource Categories
Phase A.4 natively models three foundational resource categories:
1. **`POPULATION_SPACE` (Capacity Constraint):** Physical accommodation space (e.g. beds/floorspace). Consumed directly by the currently occupied population at the destination.
2. **`WATER` (Consumable Resource):** Potable emergency water in liters. Consumed deterministically each timestep by sheltered individuals. Directly bounds the supportable population based on standard humanitarian reserve guidelines.
3. **`MEDICAL_CAPACITY` (Support-Capacity Constraint):** Medical oversight and treatment capacity (medics/stations). Utilized based on general occupants and vulnerable individuals requiring specialized assistance.

### Dynamic Consumption & Bottleneck Formulation
At each simulation tick $t$:
* **Physical Occupancy:** Resources are consumed **only** by populations with `evacuation_state in [ARRIVED, SHELTERED]`. Groups in planning or movement phases (`PLANNED`, `NOTIFIED`, `ACKNOWLEDGED`, `MOVING`, `IN_TRANSIT`) do not consume shelter reserves.
* **Deterministic Water Consumption:**
  $$\Delta \text{Water} = \text{Sheltered Population} \times \text{Water Consumption Rate per Person per Tick}$$
  $$\text{Remaining Water} = \max(0.0, \text{Total Water} - \text{Accumulated Consumption})$$
* **Water-Supported Population:**
  $$\text{Cap}_{\text{water}} = \left\lfloor \frac{\text{Remaining Water}}{\text{Water Requirement per Person}} \right\rfloor$$
  *(Defaulting to 20.0 L/person emergency reserve matching SPHERE humanitarian standards).*
* **Multi-Resource Bottleneck & Effective Capacity:**
  $$\text{Effective Capacity} = \min(\text{Cap}_{\text{physical}}, \text{Cap}_{\text{water}}, \text{Cap}_{\text{medical}})$$
  $$\text{Effective Remaining Capacity} = \max(0, \text{Effective Capacity} - \text{Sheltered Population})$$
  * Invariant: Effective capacity cannot exceed physical shelter capacity ($\text{Cap}_{\text{physical}}$).
  * Invariant: Remaining capacity cannot become negative.
  * Invariant: Consumed water and medical capacities cannot become negative.

### Resource Status Lifecycle
Each resource category is tracked per destination via `SimulationResourceState` and transitions across three explicit operational levels:
* **`NORMAL`:** Resource safely available above the warning threshold.
* **`CONSTRAINED`:** Remaining quantity is below the configured warning threshold ratio (e.g. $\le 25\%$ of initial reserve). Emits `RESOURCE_WARNING`.
* **`EXHAUSTED`:** Remaining quantity is $0.0$ or supportable population is $0$. Emits `RESOURCE_EXHAUSTED`.

### Destination Feasibility & Selective CP-SAT Trigger
* **No Blind CP-SAT Execution:** CP-SAT integer optimization is **never** executed every tick.
* **Feasibility Criterion:** Destination $D$ remains **feasible** as long as $\text{Effective Remaining Capacity} \ge \text{Uncommitted Planned Demand}$.
* **Infeasibility Detection:** If resource depletion reduces effective remaining capacity below uncommitted planned demand (or if a facility is inundated/closed):
  1. Emits `DESTINATION_INFEASIBLE` and `REALLOCATION_TRIGGERED`.
  2. Identifies the excess uncommitted planned allocations (`PLANNED`, `NOTIFIED`, `ACKNOWLEDGED`).
  3. **Strict Non-Eviction Invariant:** Populations already `ARRIVED` or `SHELTERED` are physical facts and are **never** evicted or reallocated.
  4. CP-SAT solver is selectively invoked to reallocate only the uncommitted groups to alternative safe facilities with remaining headroom.
  5. If all available destinations are exhausted, excess demand transitions to `AllocationStatusEnum.UNMET` with explicit audit justification.
  6. Emits `REALLOCATION_COMPLETED`.

### Storage Boundedness & Isolation
* Dynamic resource states are represented by normalized `SimulationResourceState` records (9 rows total per run: 3 destinations $\times$ 3 resource types).
* Rows are updated in-place each tick; no database-bloating snapshot cloning occurs.
* Canonical baseline `SNAP_BASE_001` remains strictly immutable.
* Simulation runs are completely isolated within their respective scenario snapshot branches.

### Scientific & Operational Limitations
Phase A.4 is a **deterministic resource simulation prototype**.
It is explicitly **NOT**:
* Scientifically calibrated real-world metabolic, epidemiological, or disaster consumption models.
* Real-time telemetry from smart meters, IoT water tanks, or medical logistics systems.
* A replacement for operational field stock management.
Parameters are configurable prototype constants designed to test decision-support logic under simulated stress.

---

## 7. Simulation Observability & Operational Control (Phase A.5)

### Core Architectural Principle
> **"A.5 does not introduce new disaster intelligence. It exposes and controls the state produced by the existing simulation engine."**

Phase A.5 provides read-only observability, derived operational metrics, chronological timeline inspection, and deterministic operational controls on top of the existing A.1–A.4 architecture.

### Observability Architecture
* **Strict Read-Only Invariant:** Observability APIs (`GET /state`, `GET /metrics`, `GET /timeline`) perform **zero mutations** on database tables, snapshots, or engine state.
* **No Redundant State Representations:** A.5 does not maintain duplicated in-memory counters or shadow state caches.
* **Derived Metric Ownership:**
  - *Population & Evacuation Headcounts:* Derived directly from `RelocationAllocation` queried by `run.scenario_snapshot_id` grouped by `EvacuationStateEnum`.
  - *Infrastructure & Routes:* Derived from `SimulationAllocationProgress`, `RoadSegment`, and `run.parameters['closed_road_segments']`.
  - *Destination Capacity & Resources:* Derived directly from `SimulationResourceState` and `CapacityState` for the active run and snapshot.
  - *Planning Metrics:* Derived from `RelocationAllocation` status (`AllocationStatusEnum.UNMET`) and `SimulationRun.summary_metrics`.
  - *Events:* Derived from relational table `simulation_events`.

### Chronological Timeline & Factual Summaries
* **Deterministic Stable Ordering:** Events are ordered by `(simulation_time_min ASC, tick_index ASC, created_at ASC, id ASC)`.
* **Factual Human-Readable Explanations:** Generated deterministically from structured event payloads without inventing external facts or hallucinating state changes:
  - `ROAD_BLOCKED`: *"Road {code} became blocked."*
  - `ROUTE_INVALIDATED`: *"Route for allocation {id} became invalid."*
  - `ROUTE_REPLANNED`: *"Allocation {id} was assigned a new feasible route (travel time {time}min)."*
  - `REROUTE_FAILED`: *"Reroute failed for allocation {id}; group transitioned to {fallback}."*
  - `RESOURCE_WARNING`: *"Destination {code} became resource-constrained ({resource})."*
  - `DESTINATION_INFEASIBLE`: *"Destination {code} can no longer accommodate the affected uncommitted demand."*
  - `ARRIVAL`: *"Allocation {id} reached its destination."*
  - `SHELTERED`: *"Allocation {id} admitted and sheltered inside destination facility."*
  - `EVACUATION_STATE_CHANGED`: *"Allocation {id} changed evacuation state from {from_state} to {to_state}."*
  - `SIMULATION_COMPLETED`: *"Simulation completed successfully ({ticks} ticks)."*

### Operational Control Semantics & Status State Machine
A.5 controls reuse the single, deterministic A.3 temporal simulation engine without background schedulers, threads, or wall-clock timing:
* **Lifecycle Rules:**
  - `CREATED`: Can start or single-step.
  - `RUNNING`: Can pause; can step according to engine semantics; completes naturally when clock reaches duration.
  - `PAUSED`: Can resume; can single-step one tick (preserving paused status during inspection).
  - `COMPLETED`: Terminal state; no further mutations or clock advancement. Stepping is a no-op; pausing, resuming, or cancelling rejects with HTTP 400 (`INVALID_SIMULATION_STATE`).
  - `CANCELLED`: Terminal state; no further mutations or clock advancement. Rejects mutation with HTTP 400.
  - `FAILED`: Terminal state; no further mutations.

### API Surface
* `GET /api/v1/simulation-runs/{run_id}/state`: Consolidated operational state snapshot (read-only).
* `GET /api/v1/simulation-runs/{run_id}/metrics`: Aggregated operational metrics (read-only).
* `GET /api/v1/simulation-runs/{run_id}/timeline`: Paginated chronological event history with deterministic summaries (read-only).
* `POST /api/v1/simulation-runs/{run_id}/pause`: Pauses active simulation.
* `POST /api/v1/simulation-runs/{run_id}/resume`: Resumes paused simulation.
* `POST /api/v1/simulation-runs/{run_id}/step`: Deterministically advances simulation by exactly one tick.
* `POST /api/v1/simulation-runs/{run_id}/cancel`: Cancels simulation.

### Baseline & Scenario Safety
* The canonical baseline `SNAP_BASE_001` is strictly read-only and immutable.
* All simulation runs, events, resource states, and allocations remain isolated within their specific scenario snapshot branches.

---

## 8. Hybrid Hazard Prediction Layer (Phase A.6)

### Core Architectural Principle
> **"A.6 introduces scientifically defensible, transparent predictive intelligence for hazard forecasting. It explicitly rejects black-box fake AI, arbitrary weightings, and uncalibrated confidence numbers."**

Phase A.6 establishes the hybrid prediction architecture connecting hydrometric time-series observations to future hazard state projection and E1 spatial red-zone evaluation.

### Prediction Target & Hydrometric Grounding
* **Target Metric:** Future river stage in meters ($Y_{t+h}$, `target_metric="RIVER_STAGE_M"`) at Central Water Commission gauge `CWC_GAUGE_01` in the Vayu River Basin.
* **Justification:**
  - Metric unit consistency with CWC river gauge telemetry.
  - Transparent physical meaning with clear hydrometric limits (baseline 10.0m, warning alert 10.30m, critical flood stage 11.0m).
  - Direct consumption by `HazardEngineE1.evaluate_hazard_state` / `evaluate_from_prediction` to project spatial inundation polygons.
* **Forecast Horizons:** Configurable lead times $h \in [10, 360]$ minutes (e.g. 10m, 30m, 60m).

### Features & Time-Series Leakage Prevention
* **Feature Vector $\mathbf{x}_t$:**
  $$[1.0 \text{ (bias)}, y_t, y_{t-1}, (y_t - y_{t-1}), r_t, \bar{r}_{30\text{m}}, h]$$
* **Chronological Splitting (No Future Leakage):**
  - Observations are strictly partitioned chronologically without random shuffling:
    - **Training Window:** Steps $0 \dots 259$ (Hours $0.0 \dots 43.2$, 60%)
    - **Validation Window:** Steps $260 \dots 345$ (Hours $43.3 \dots 57.5$, 20%)
    - **Test Window:** Steps $346 \dots 431$ (Hours $57.6 \dots 72.0$, 20%)

### Prediction Models: Transparent Baselines & Closed-Form ML
1. **Persistence Baseline:** $\hat{y}_{t+h} = y_t$. Classical hydrological benchmark.
2. **Linear Trend Baseline:** $\hat{y}_{t+h} = y_t + \frac{h}{\Delta t} (y_t - y_{t-1})$. Extrapolates current rate of change.
3. **Autoregressive Ridge Regression (ML):**
   - Closed-form L2-regularized linear model solved analytically via NumPy:
     $$\mathbf{w} = (\mathbf{X}^T \mathbf{X} + \lambda \mathbf{I})^{-1} \mathbf{X}^T \mathbf{y}, \quad \lambda = 0.1$$
   - Highly interpretable, zero bloated ML dependencies, runs deterministically on CPU.
4. **Benchmark Evaluation:** Evaluated on held-out test split using standard regression metrics:
   $$\text{MAE} = \frac{1}{N} \sum |y_i - \hat{y}_i|, \quad \text{RMSE} = \sqrt{\frac{1}{N}\sum (y_i - \hat{y}_i)^2}, \quad R^2 = 1 - \frac{\sum (y_i - \hat{y}_i)^2}{\sum (y_i - \bar{y})^2}$$

### Physical Plausibility & Domain Constraints
Every prediction passes through sequential validation gating before acceptance:
* **Physical Hydraulic Boundaries:**
  - Riverbed floor minimum: $8.0$m.
  - Dyke crest maximum: $15.0$m.
  - Maximum rate of rise: $1.5$m / 10 minutes.
  - Status returned: `VALID`, `CORRECTED` (clamped to physical bounds with audit reason), or `REJECTED`.
* **Domain Alert Rules:**
  - `OPERATIONAL_ALERT_STAGE_EXCEEDED`: Triggered when predicted stage $\ge 10.30$m.
  - `CRITICAL_DANGER_STAGE_EXCEEDED`: Triggered when predicted stage $\ge 11.00$m.
  - `RAPID_FLASH_SURGE_DETECTED`: Triggered when rate of rise $\ge 0.50$m/10min.

### Honest Uncertainty Representation
* Rather than fabricating arbitrary confidence percentages (e.g. 0.95), uncertainty intervals $[\hat{y} - 1.96 \cdot s, \hat{y} + 1.96 \cdot s]$ are calibrated from the empirical residual standard error $s = \text{RMSE}_{\text{val}}$ computed on the chronological validation partition.
* Uncertainty expands appropriately with longer lead time horizons.

### E1 Integration Adapter
* Clean modular coupling via `HazardEngineE1.evaluate_from_prediction`.
* Consumes validated predicted river level and projected rainfall delta to compute live flood polygon buffering, expansion factors, and red zones.
* Scenario-driven and baseline execution remain completely intact.

### Synthetic Data Warning
> **DEMO / PROTOTYPE NOTICE:** Current hydrometric data is a mathematically calibrated synthetic hydrograph representing typical monsoon catchment response in the Vayu River Basin prototype world. It does not represent real-world operational gauge telemetry.

---

## Phase A.7 Architecture: Real-World Hazard Data Integration & Observation-Driven E1

### Core Mission & Engineering Principle
Phase A.7 integrates empirical hydrometric telemetry into PRISM, piloted using the **Tamil Nadu River Water Level Telemetry Hourly** dataset at **Nandambakkam CheckDam** on the **Adyar River** in **Chennai**.

**Fundamental Axiom:**
> **"Observation is NOT Prediction."**
> - **Observation:** "The sensor measured $X$ metres at historical/present time $T$." (Empirical ground truth)
> - **Prediction:** "A model projects $X$ metres at future time $T+h$." (Inferential hypothesis)
> PRISM strictly avoids silently transforming observations into predictions or blending them into ML forecasting pipelines.

### Real vs Synthetic System Boundary
* **REAL / OBSERVED:**
  - River water level telemetry
  - Station metadata (Nandambakkam CheckDam, Adyar River, Chennai, 13.0161°N, 80.1828°E)
  - Observation timestamps
  - Provenance source datasets
  - Data quality classifications (`VALID`, `SUSPECT`, `REJECTED`, `MISSING`, `STALE`)
* **SYNTHETIC / PROTOTYPE:**
  - Study area habitations, households, and demographics
  - Evacuation shelters, capacities, and resource consumption rates
  - Road network and bridge structures
  - Relocation assignments and CP-SAT optimization schedules
  - Prototype hazard geometry bufferings

### Key Engineering Guardrails
1. **Timestamp Separation:** `observed_at != ingested_at` is enforced as an invariant across all models, DTOs, and storage tables.
2. **Zero Fabricated Thresholds:** No prototype flood warning/critical levels are invented for Nandambakkam CheckDam. Observations are explicitly classified as `VALID OBSERVATION, SEVERITY UNCLASSIFIED` unless authoritative CWC/PWD danger stages are registered.
3. **E1 Safety Boundary:** Observations marked `REJECTED` or `STALE` (without explicit audit override `allow_stale=True`) raise `ObservationSafetyException` and are strictly blocked from driving E1.
4. **Spatial Transformation Disclaimer:** Single gauge water level does not constitute hydrodynamic inundation. Evaluated states carry the mandatory label:
   *"Prototype spatial transformation — not a validated hydrodynamic inundation model."*
5. **E6 Provenance Traceability:** Every observation-driven E1 hazard state logs an `AuditEvent` recording `Station Code`, `Observation ID`, `Water Level`, `Hazard State ID`, and `Red Zone ID`.
6. **Backward Compatibility:** Canonical baseline `SNAP_BASE_001` remains 100% immutable (28 allocations, 0 mutations). Existing scenario-driven E1 path continues working without regression.






