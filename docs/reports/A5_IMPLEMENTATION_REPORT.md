# PRISM V2 — Phase A.5 Implementation Report
## Simulation Observability & Operational Control

**Date:** October 2026  
**Status:** Completed & Fully Verified  
**Scope:** Surgical implementation of read-only simulation observability, operational metrics derivation, chronological timeline event inspection, and operational simulation lifecycle controls.

---

### 1. Inspected Architecture

Prior to implementing Phase A.5, the existing PRISM architecture and components were inspected:
- **E1 Hazard State:** Live hazard geometry recomputation via `HazardState` and `evaluate_hazard_state`.
- **E2 Population & Vulnerability:** `RelocationAllocation`, `RelocationGroup`, `PriorityRecord`, and `Household`.
- **E3 Capacity & Dynamic Resources (A.4):** `CapacityState`, `DestinationResource`, and `SimulationResourceState` tracking dynamic water/medical depletion and effective capacity bottlenecks.
- **E4 Routing & Optimization:** Dijkstra graph routing and selective Google OR-Tools CP-SAT reallocation.
- **E5 Temporal Simulation Engine (A.3):** `SimulationRun`, `SimulationEvent`, `SimulationAllocationProgress`, and `TemporalSimulationEngine` executing discrete deterministic timesteps.
- **Evacuation State Machine (A.2):** `EvacuationStateMachine` enforcing canonical state separation (`PLANNED`, `NOTIFIED`, `ACKNOWLEDGED`, `EVACUATION_ORDERED`, `MOVING`, `IN_TRANSIT`, `ARRIVED`, `SHELTERED`, `ROUTE_BLOCKED`, `STUCK`, `REQUIRES_ASSISTANCE`, `NO_RESPONSE`).
- **Baseline Immutability (A.1):** `SNAP_BASE_001` invariant protection preventing direct modification of canonical baseline snapshots.

---

### 2. Files Changed & Created

| File Path | Action | Description |
| :--- | :--- | :--- |
| `apps/api/app/models/enums.py` | Modified | Added `SIMULATION_RESUMED` and `SIMULATION_CANCELLED` to `SimulationEventTypeEnum`. |
| `apps/api/app/schemas/simulation.py` | Modified | Added DTO schemas: `ConsolidatedSimulationStateDTO`, `SimulationOperationalMetricsDTO`, `SimulationTimelineResponseDTO`, `SimulationTimelineEventDTO`, `SimulationPopulationStateDTO`, `SimulationInfrastructureStateDTO`, `SimulationPlanningStateDTO`. |
| `apps/api/app/engines/e5_simulation/observability_service.py` | Created | `SimulationObservabilityService` providing read-only consolidated state calculation, operational metrics derivation, deterministic chronological timeline paging, and factual human-readable event summaries. |
| `apps/api/app/engines/e5_simulation/temporal_engine.py` | Modified | Added lifecycle validation guardrails, status enforcement for COMPLETED/CANCELLED states, `resume_simulation()`, `cancel_simulation()`, and preserved PAUSED mode during single-step debugging. |
| `apps/api/app/api/v1/simulation.py` | Modified | Exposed endpoints: `GET /{run_id}/state`, `GET /{run_id}/metrics`, `GET /{run_id}/timeline`, `POST /{run_id}/resume`, `POST /{run_id}/cancel`. |
| `apps/web/src/lib/api.ts` | Modified | Added TypeScript API client wrappers: `getSimulationState`, `getSimulationMetrics`, `getSimulationTimeline`, `stepSimulation`, `pauseSimulation`, `resumeSimulation`, `cancelSimulation`, `getSimulationRun`. |
| `apps/api/tests/test_simulation_observability.py` | Created | Comprehensive automated test suite with 24 dedicated test cases verifying all A.5 requirements. |
| `scripts/verify_a5_observability_demo.py` | Created | End-to-end verification demonstration executing full create-step-pause-step-resume-complete-verify workflow. |
| `docs/master/PRISM_ENGINEERING_RECONCILIATION_NOTES.md` | Modified | Updated with Section 7 documenting A.5 observability architecture, metric sources, control semantics, and safety invariants. |
| `docs/reports/A5_IMPLEMENTATION_REPORT.md` | Created | Authoritative implementation report detailing architecture, tests, baseline verification, and metrics. |

---

### 3. API Changes

The following endpoints were added to `apps/api/app/api/v1/simulation.py`:

```http
GET  /api/v1/simulation-runs/{run_id}/state
GET  /api/v1/simulation-runs/{run_id}/metrics
GET  /api/v1/simulation-runs/{run_id}/timeline?limit=50&offset=0&event_type=...
POST /api/v1/simulation-runs/{run_id}/resume
POST /api/v1/simulation-runs/{run_id}/cancel
```

All existing endpoints were preserved:
- `POST /api/v1/simulation-runs` (creation)
- `GET /api/v1/simulation-runs/{run_id}` (retrieval)
- `POST /api/v1/simulation-runs/{run_id}/step` (advances exactly one deterministic tick)
- `POST /api/v1/simulation-runs/{run_id}/run` (continuous stepping up to max_steps or completion)
- `POST /api/v1/simulation-runs/{run_id}/pause` (pauses simulation)
- `GET /api/v1/simulation-runs/{run_id}/events` (raw events list)
- `GET /api/v1/simulation-runs/{run_id}/resources` (per-destination resource breakdown)

---

### 4. Observability Model & Metric Sources

To avoid state drift and redundant in-memory shadow models, all metrics are derived strictly from authoritative sources:

| Metric Category | Target DTO Field | Authoritative Source of Truth |
| :--- | :--- | :--- |
| **Progress & Clock** | `current_tick`, `current_simulation_time`, `progress_percentage` | `SimulationRun.ticks_completed`, `SimulationRun.current_simulation_time`, `SimulationRun.duration_minutes` |
| **Population Lifecycle** | `counts_by_state`, `allocation_counts_by_state`, headcounts by state | Aggregated directly from `RelocationAllocation` records filtered by `run.scenario_snapshot_id` and grouped by `EvacuationStateEnum`. |
| **Infrastructure & Routes** | `blocked_roads_count`, `blocked_road_codes` | `run.parameters['closed_road_segments']` and `RoadSegment` table. |
| **Routing Progress** | `active_routes_count`, `reroute_counts`, `invalidated_routes_count` | `SimulationAllocationProgress` (sum of `reroute_count`, `is_blocked`) and `RelocationAllocation`. |
| **Capacity & Resources** | `total_effective_capacity`, `total_occupied_capacity`, `total_remaining_capacity`, `total_water_consumed_liters`, `bottleneck_resource` | `CapacityState` filtered by `run.scenario_snapshot_id` and `SimulationResourceState` filtered by `run.id`. |
| **Physical Capacity** | `total_physical_capacity` | `DestinationResource` filtered by `snapshot_id == SNAP_BASE_001` where `resource_type == SHELTER` (or `SimulationResourceState`). |
| **Planning State** | `unmet_demand_count`, `unmet_demand_population`, `reallocation_count`, `infeasible_destinations_count` | `RelocationAllocation.allocation_status == UNMET` and `CapacityState.is_safe == False` / `remaining_capacity <= 0`. |
| **Event Timeline** | `total_events`, `event_counts_by_type`, `latest_important_event` | `SimulationEvent` table filtered by `run.id`. |

---

### 5. Event & Timeline Semantics

Timeline events are sorted deterministically using stable tuple comparison:
$$\text{Order} = (\text{simulation\_time\_min} \uparrow, \text{tick\_index} \uparrow, \text{created\_at} \uparrow, \text{id} \uparrow)$$

Deterministic, factual human-readable explanations are generated dynamically:
- `ROAD_BLOCKED`: `"Road {code} became blocked."`
- `ROUTE_INVALIDATED`: `"Route for allocation {id} became invalid."`
- `ROUTE_REPLANNED`: `"Allocation {id} was assigned a new feasible route (travel time {time}min)."`
- `REROUTE_FAILED`: `"Reroute failed for allocation {id}; group transitioned to {fallback}."`
- `RESOURCE_WARNING`: `"Destination {code} became resource-constrained ({resource})."`
- `DESTINATION_INFEASIBLE`: `"Destination {code} can no longer accommodate the affected uncommitted demand."`
- `ARRIVAL`: `"Allocation {id} reached its destination."`
- `SHELTERED`: `"Allocation {id} admitted and sheltered inside destination facility."`
- `EVACUATION_STATE_CHANGED`: `"Allocation {id} changed evacuation state from {from_state} to {to_state}."`
- `SIMULATION_COMPLETED`: `"Simulation completed successfully ({ticks} ticks)."`

---

### 6. Control Semantics & Status State Machine

The control path strictly enforces the following status rules:
- `CREATED`: Can start or single-step.
- `RUNNING`: Can pause; can step; completes naturally when time reaches duration.
- `PAUSED`: Can resume; can single-step (status remains `PAUSED` across single-step inspection until resumed or completed).
- `COMPLETED`: Terminal state; no further mutations. Stepping is an idempotent no-op (no tick/time advancement); calling pause, resume, or cancel returns HTTP 400 (`INVALID_SIMULATION_STATE`).
- `CANCELLED`: Terminal state; no further mutations. Calling pause, resume, or cancel returns HTTP 400.
- `FAILED`: Terminal state; no further mutations.

---

### 7. Automated Test Suite & Results

All 24 test requirements from Section 13 were implemented in `apps/api/tests/test_simulation_observability.py`:

```text
tests/test_simulation_observability.py::test_1_current_state_endpoint PASSED
tests/test_simulation_observability.py::test_2_metrics_endpoint PASSED
tests/test_simulation_observability.py::test_3_timeline_endpoint PASSED
tests/test_simulation_observability.py::test_4_missing_run_returns_404 PASSED
tests/test_simulation_observability.py::test_5_deterministic_state_response PASSED
tests/test_simulation_observability.py::test_6_deterministic_metrics PASSED
tests/test_simulation_observability.py::test_7_chronological_event_ordering PASSED
tests/test_simulation_observability.py::test_8_event_summary_generation PASSED
tests/test_simulation_observability.py::test_9_running_to_paused PASSED
tests/test_simulation_observability.py::test_10_paused_to_running PASSED
tests/test_simulation_observability.py::test_11_paused_to_single_step PASSED
tests/test_simulation_observability.py::test_12_step_advances_exactly_one_tick PASSED
tests/test_simulation_observability.py::test_13_completed_simulation_cannot_step PASSED
tests/test_simulation_observability.py::test_14_cancelled_simulation_cannot_step PASSED
tests/test_simulation_observability.py::test_15_read_only_apis_do_not_mutate_state PASSED
tests/test_simulation_observability.py::test_16_baseline_remains_unchanged PASSED
tests/test_simulation_observability.py::test_17_evacuation_state_metrics_match_actual_state PASSED
tests/test_simulation_observability.py::test_18_resource_metrics_match_a4_state PASSED
tests/test_simulation_observability.py::test_19_route_infrastructure_metrics_match_existing_simulation_state PASSED
tests/test_simulation_observability.py::test_20_no_duplicate_simulation_loop PASSED
tests/test_simulation_observability.py::test_21_zero_duration_simulation_observability PASSED
tests/test_simulation_observability.py::test_22_completed_simulation_observability PASSED
tests/test_simulation_observability.py::test_23_event_counts_are_deterministic PASSED
tests/test_simulation_observability.py::test_24_invalid_lifecycle_operations_rejected PASSED
======================== 24 passed, 1 warning in 5.60s ========================
```

---

### 8. Full Backend Regression Results

The full test suite across the entire backend was executed:
- `test_authority_override.py` (A.1): **10/10 PASSED**
- `test_evacuation_state.py` (A.2): **15/15 PASSED**
- `test_temporal_simulation.py` (A.3): **28/28 PASSED**
- `test_dynamic_resources.py` (A.4): **31/31 PASSED**
- `test_simulation_observability.py` (A.5): **24/24 PASSED**
- `test_api.py` / `test_engines.py`: **12/12 PASSED**

**Overall Total:** **120 passed, 0 failed** in 20.39s.

---

### 9. Demonstration Verification Results

`scripts/verify_a5_observability_demo.py` executed successfully:
1. Created simulation run (`timestep=10.0m`, `duration=30.0m`, `total_ticks=3`).
2. Inspected initial consolidated state at $t=0$ min (`status=CREATED`, `progress=0.0%`).
3. Stepped to Tick 1 ($t=10$ min), verified event generation.
4. Inspected operational metrics (effective capacity, water consumption, in-transit population).
5. Inspected chronological timeline highlights and factual summaries.
6. Paused simulation (`status=PAUSED`, verified `SIMULATION_PAUSED` event).
7. Executed single step while paused ($t=20$ min, Tick 2), verified tick advanced while preserving paused mode.
8. Resumed simulation (`status=RUNNING`, verified `SIMULATION_RESUMED` event).
9. Advanced to completion ($t=30$ min, Tick 3), verified `status=COMPLETED`.
10. Inspected final state ($100\%$ progress, summary metrics, event counts by type).
11. Verified canonical baseline immutability: `SNAP_BASE_001` allocations remained exactly 28 before and after the demo.

---

### 10. Baseline Verification

The canonical baseline `SNAP_BASE_001` was verified before and after all test runs and demonstrations:
- Total allocations: **28**
- Destination `DEST_01`: Capacity 150, Occupied 93, Remaining 57
- Destination `DEST_02`: Capacity 60, Occupied 0, Remaining 60
- Destination `DEST_03`: Capacity 50, Occupied 0, Remaining 50
- Zero mutations occurred on `SNAP_BASE_001`.

---

### 11. Limitations & Intentionally Deferred Scope

- **Frontend Dashboard Polish:** A.5 intentionally provides the clean backend API surface and client wrappers in `apps/web/src/lib/api.ts`. Building a large visual dashboard is intentionally deferred to a dedicated UI sprint.
- **Asynchronous Execution:** No background workers (Celery/Redis/Kafka) or WebSocket push streams were introduced; simulation progression remains strictly discrete and synchronous.
- **Database Engine:** Implementation remains on SQLite as required.
