"""PRISM V2 — Temporal Simulation Engine (E5 - Phase A.3)
======================================================
Deterministic Fixed-Timestep Simulation with Dynamic In-Transit Movement,
Route Invalidation, Real-time Rerouting, and Exception Recovery.

CORE INVARIANTS:
1. Model Time != Wall-Clock Time (Fixed discrete timesteps).
2. Storage bounded: Live simulation branch with compact event logs (NO full-db snapshots per tick).
3. Baseline SNAP_BASE_001 is 100% immutable (Rejects baseline simulation runs).
4. Strictly deterministic: Same inputs produce identical event sequences and states.
5. Evacuation lifecycle transitions governed strictly by EvacuationStateMachine.
6. CP-SAT reallocation only triggered on material planning infeasibility for non-moving groups.
7. ARRIVED and SHELTERED groups are protected from unnecessary replanning.
"""

import uuid
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
import shapely

from app.models.entities import (
    Scenario, StateSnapshot, HazardState, HazardPrediction, RedZone,
    Habitation, Household, RelocationGroup, RelocationAllocation, Destination,
    CapacityState, RoadNode, RoadSegment, RoutePlan,
    SimulationRun, SimulationEvent, SimulationAllocationProgress, SimulationResourceState
)
from app.engines.e3_destination_capacity.resource_manager import DynamicResourceManager
from app.models.enums import (
    SimulationStatusEnum, SimulationEventTypeEnum, EvacuationStateEnum,
    OperationalStatusEnum, AllocationStatusEnum
)
from app.engines.e1_hazard.service import HazardEngineE1
from app.engines.e4_route_relocation.service import RouteAndRelocationEngineE4
from app.engines.e5_simulation.service import SimulationEngineE5
from app.engines.e5_simulation.state_machine import EvacuationStateMachine
from app.gis.spatial import to_shapely, to_geojson_str, intersects


MAX_SIMULATION_TICKS: int = 200


class TemporalSimulationEngine:
    """Deterministic discrete-time simulation engine for PRISM disaster response."""

    def __init__(self, db: Session):
        self.db = db
        self.e1 = HazardEngineE1()
        self.e4 = RouteAndRelocationEngineE4()
        self.e5 = SimulationEngineE5(db)

    def validate_simulation_inputs(
        self,
        timestep_minutes: float,
        duration_minutes: float
    ) -> int:
        """
        Validates simulation bounds. Returns expected tick count.
        Rejects invalid timesteps, negative durations, and excessive tick bounds.
        """
        if timestep_minutes is None or timestep_minutes <= 0.0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"INVALID_TIMESTEP: Timestep must be greater than 0. Received: {timestep_minutes}."
            )
        if duration_minutes is None or duration_minutes < 0.0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"INVALID_DURATION: Duration must be greater than or equal to 0. Received: {duration_minutes}."
            )

        if duration_minutes == 0.0:
            return 0

        ticks = int(duration_minutes // timestep_minutes)
        if (duration_minutes % timestep_minutes) > 0.0001:
            ticks += 1

        if ticks > MAX_SIMULATION_TICKS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"EXCESSIVE_SIMULATION_TICKS: Requested simulation produces {ticks} ticks, which exceeds the safety limit of {MAX_SIMULATION_TICKS}. Please increase timestep or reduce duration."
            )
        return ticks

    def create_simulation_run(
        self,
        scenario_code: str = "MONSOON_SURGE_01",
        scenario_snapshot_id: Optional[str] = None,
        timestep_minutes: float = 5.0,
        duration_minutes: float = 60.0,
        parameter_overrides: Optional[Dict[str, Any]] = None,
        auto_admit_shelter: bool = True
    ) -> SimulationRun:
        """
        Initializes an isolated simulation run on a mutable scenario branch.
        Enforces baseline immutability.
        """
        total_ticks = self.validate_simulation_inputs(timestep_minutes, duration_minutes)
        overrides = parameter_overrides or {}

        # 1. Determine scenario snapshot context
        if scenario_snapshot_id:
            snap = self.db.query(StateSnapshot).filter(StateSnapshot.id == scenario_snapshot_id).first()
            if not snap:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"SNAPSHOT_NOT_FOUND: Scenario snapshot '{scenario_snapshot_id}' not found."
                )
            if snap.is_immutable or snap.id == "SNAP_BASE_001":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"BASELINE_IMMUTABLE: Cannot run temporal simulation directly against canonical baseline snapshot '{snap.id}'. Create a scenario snapshot branch first."
                )
            scen_snap_id = snap.id
            scen = self.db.query(Scenario).filter(Scenario.id == snap.scenario_id).first() if snap.scenario_id else None
            scenario_id = scen.id if scen else None
            effective_params = (scen.parameters.copy() if scen and scen.parameters else {})
            effective_params.update(overrides)
        else:
            # Fork a fresh scenario snapshot branch from baseline
            scen = self.db.query(Scenario).filter(Scenario.code == scenario_code).first()
            if not scen:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"SCENARIO_NOT_FOUND: Scenario with code '{scenario_code}' not found."
                )
            scenario_id = scen.id
            effective_params = scen.parameters.copy() if scen.parameters else {}
            effective_params.update(overrides)

            # Execute baseline-to-scenario causal generation in E5
            scen_result = self.e5.execute_scenario(
                scenario_code=scenario_code,
                baseline_snapshot_id="SNAP_BASE_001",
                overrides=effective_params
            )
            scen_snap_id = scen_result["scenario_snapshot_id"]

        # 2. Persist SimulationRun
        run = SimulationRun(
            scenario_id=scenario_id,
            scenario_snapshot_id=scen_snap_id,
            status=SimulationStatusEnum.CREATED,
            timestep_minutes=timestep_minutes,
            duration_minutes=duration_minutes,
            current_simulation_time=0.0,
            ticks_completed=0,
            total_ticks=total_ticks,
            parameters=effective_params,
            summary_metrics={
                "events_count": 0,
                "routes_replanned": 0,
                "blocked_roads": 0,
                "arrivals": 0,
                "sheltered": 0,
                "stuck": 0,
                "auto_admit_shelter": auto_admit_shelter
            }
        )
        self.db.add(run)
        self.db.flush()

        # 3. Initialize progress trackers for any allocations in transit or planned
        allocs = self.db.query(RelocationAllocation).filter(
            RelocationAllocation.snapshot_id == scen_snap_id
        ).all()

        for a in allocs:
            route = self.db.query(RoutePlan).filter(RoutePlan.id == a.route_plan_id).first() if a.route_plan_id else None
            travel_time = route.total_time_min if route else 30.0
            prog = SimulationAllocationProgress(
                simulation_run_id=run.id,
                allocation_id=a.id,
                route_plan_id=a.route_plan_id,
                original_route_plan_id=a.route_plan_id,
                elapsed_time_min=0.0,
                total_travel_time_min=travel_time,
                progress_ratio=0.0,
                is_blocked=False,
                reroute_count=0
            )
            self.db.add(prog)

        # 4. Initialize dynamic simulation resource states (Phase A.4)
        DynamicResourceManager.initialize_simulation_resources(self.db, run)

        # 5. Record SIMULATION_STARTED event
        start_event = SimulationEvent(
            simulation_run_id=run.id,
            simulation_time_min=0.0,
            tick_index=0,
            event_type=SimulationEventTypeEnum.SIMULATION_STARTED,
            entity_type="SimulationRun",
            entity_id=run.id,
            details={
                "scenario_snapshot_id": scen_snap_id,
                "timestep_minutes": timestep_minutes,
                "duration_minutes": duration_minutes,
                "total_ticks": total_ticks,
                "parameters": effective_params
            }
        )
        self.db.add(start_event)
        self.db.commit()
        self.db.refresh(run)

        # If zero-duration, mark completed immediately
        if duration_minutes == 0.0:
            run.status = SimulationStatusEnum.COMPLETED
            comp_event = SimulationEvent(
                simulation_run_id=run.id,
                simulation_time_min=0.0,
                tick_index=0,
                event_type=SimulationEventTypeEnum.SIMULATION_COMPLETED,
                entity_type="SimulationRun",
                entity_id=run.id,
                details={"reason": "Zero-duration simulation completed immediately."}
            )
            self.db.add(comp_event)
            self.db.commit()
            self.db.refresh(run)

        return run

    def step_simulation(self, run_id: str) -> Dict[str, Any]:
        """
        Executes a single deterministic timestep of the simulation.
        Deterministic order:
        1. Advance clock
        2. Interpolate hazard parameters
        3. E1 hazard geometry recomputation
        4. Infrastructure/road safety check
        5. In-transit movement & blockage detection
        6. Dynamic E4 route replanning & recovery
        7. Infeasible planned allocation reallocation (CP-SAT only when required)
        8. Arrival and sheltered transitions
        9. Persist compact events & state update atomically
        """
        run = self.db.query(SimulationRun).filter(SimulationRun.id == run_id).first()
        if not run:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"SIMULATION_RUN_NOT_FOUND: Simulation run '{run_id}' not found."
            )

        if run.status in [SimulationStatusEnum.COMPLETED, SimulationStatusEnum.CANCELLED]:
            return {
                "run": run,
                "tick_index": run.ticks_completed,
                "simulation_time_min": run.current_simulation_time,
                "events_generated": [],
                "state_summary": {"status": run.status.value, "message": "Simulation already finished."}
            }

        events_generated: List[SimulationEvent] = []

        try:
            # ---------------------------------------------------------
            # STEP 1: Advance simulation clock
            # ---------------------------------------------------------
            was_paused = (run.status == SimulationStatusEnum.PAUSED)
            next_time = min(run.duration_minutes, run.current_simulation_time + run.timestep_minutes)
            tick_idx = run.ticks_completed + 1
            run.current_simulation_time = next_time
            run.ticks_completed = tick_idx
            if not was_paused:
                run.status = SimulationStatusEnum.RUNNING


            # ---------------------------------------------------------
            # STEP 2 & 3: Compute hazard state for the new simulation time
            # ---------------------------------------------------------
            progress_ratio = 1.0 if run.duration_minutes == 0 else min(1.0, next_time / run.duration_minutes)
            max_rainfall_delta = run.parameters.get("rainfall_multiplier_delta", 0.20)
            max_river_delta = run.parameters.get("river_level_delta_m", 0.50)

            cur_rainfall_delta = progress_ratio * max_rainfall_delta
            cur_river_delta = progress_ratio * max_river_delta

            baseline_hazard = self.db.query(HazardState).filter(HazardState.snapshot_id == "SNAP_BASE_001").first()
            base_flood_geom = to_shapely(baseline_hazard.geom)

            e1_res = self.e1.evaluate_hazard_state(
                study_area_id=baseline_hazard.study_area_id,
                snapshot_id=run.scenario_snapshot_id,
                base_flood_geom=base_flood_geom,
                rainfall_multiplier_delta=cur_rainfall_delta,
                river_level_current=10.0 + cur_river_delta,
                river_level_baseline=10.0
            )

            current_flood_geom = e1_res["current_geom"]

            # Update live HazardState in scenario snapshot branch
            scen_hazard = self.db.query(HazardState).filter(
                HazardState.snapshot_id == run.scenario_snapshot_id
            ).first()
            if scen_hazard:
                scen_hazard.geom = to_geojson_str(current_flood_geom)
                scen_hazard.severity = "HIGH" if (cur_rainfall_delta > 0.15 or cur_river_delta > 0.3) else "MEDIUM"

            # Check if hazard expanded significantly
            if cur_rainfall_delta > 0 or cur_river_delta > 0:
                h_event = SimulationEvent(
                    simulation_run_id=run.id,
                    simulation_time_min=next_time,
                    tick_index=tick_idx,
                    event_type=SimulationEventTypeEnum.HAZARD_EXPANDED,
                    entity_type="HazardState",
                    entity_id=scen_hazard.id if scen_hazard else run.scenario_snapshot_id,
                    details={
                        "rainfall_multiplier_delta": round(cur_rainfall_delta, 3),
                        "river_level_delta_m": round(cur_river_delta, 3),
                        "expansion_progress_pct": round(progress_ratio * 100, 1)
                    }
                )
                self.db.add(h_event)
                events_generated.append(h_event)

            # ---------------------------------------------------------
            # STEP 4: Infrastructure / Road Safety Evaluation
            # ---------------------------------------------------------
            habitations = self.db.query(Habitation).all()
            destinations = self.db.query(Destination).all()
            road_nodes = self.db.query(RoadNode).all()
            road_segments = self.db.query(RoadSegment).filter(
                RoadSegment.study_area_id == baseline_hazard.study_area_id
            ).all()

            closed_codes = run.parameters.get("closed_road_segments", ["BRIDGE_01"])

            eval_segments = []
            for s in road_segments:
                seg_geom = to_shapely(s.geom)
                is_submerged = intersects(seg_geom, current_flood_geom) if not s.is_bridge else False
                is_closed = (s.segment_code in closed_codes) or is_submerged or (s.operational_status == OperationalStatusEnum.CLOSED)

                if is_submerged and s.segment_code not in closed_codes:
                    closed_codes.append(s.segment_code)
                    r_event = SimulationEvent(
                        simulation_run_id=run.id,
                        simulation_time_min=next_time,
                        tick_index=tick_idx,
                        event_type=SimulationEventTypeEnum.ROAD_BLOCKED,
                        entity_type="RoadSegment",
                        entity_id=s.id,
                        details={
                            "segment_code": s.segment_code,
                            "reason": "Road segment inundated by flood expansion"
                        }
                    )
                    self.db.add(r_event)
                    events_generated.append(r_event)
                    run.summary_metrics["blocked_roads"] = run.summary_metrics.get("blocked_roads", 0) + 1

                cloned_s = RoadSegment(
                    id=s.id,
                    study_area_id=s.study_area_id,
                    segment_code=s.segment_code,
                    u_node_id=s.u_node_id,
                    v_node_id=s.v_node_id,
                    road_class=s.road_class,
                    length_meters=s.length_meters,
                    max_speed_kmh=s.max_speed_kmh,
                    geom=s.geom,
                    operational_status=OperationalStatusEnum.CLOSED if is_closed else OperationalStatusEnum.OPEN,
                    hazard_risk_score=1.0 if is_closed else s.hazard_risk_score,
                    is_bridge=s.is_bridge
                )
                eval_segments.append(cloned_s)

            # Update scenario parameters to track dynamic closed codes
            run.parameters["closed_road_segments"] = closed_codes

            # ---------------------------------------------------------
            # STEP 5 & 6: In-Transit Movement & Blockage Detection
            # ---------------------------------------------------------
            progress_records = self.db.query(SimulationAllocationProgress).filter(
                SimulationAllocationProgress.simulation_run_id == run.id
            ).all()
            prog_map = {p.allocation_id: p for p in progress_records}

            allocs = self.db.query(RelocationAllocation).filter(
                RelocationAllocation.snapshot_id == run.scenario_snapshot_id
            ).all()

            auto_admit = run.summary_metrics.get("auto_admit_shelter", True)

            for alloc in allocs:
                if alloc.evacuation_state != EvacuationStateEnum.IN_TRANSIT:
                    continue

                prog = prog_map.get(alloc.id)
                route = self.db.query(RoutePlan).filter(RoutePlan.id == alloc.route_plan_id).first() if alloc.route_plan_id else None

                # Check if current route passes through a blocked segment or intersects flood
                route_compromised = False
                compromised_reason = None
                if not route:
                    route_compromised = True
                    compromised_reason = "No active route plan assigned"
                else:
                    route_geom = to_shapely(route.geom)
                    for seg in eval_segments:
                        if seg.operational_status == OperationalStatusEnum.CLOSED:
                            if seg.segment_code in route.path_nodes or intersects(to_shapely(seg.geom), route_geom):
                                route_compromised = True
                                compromised_reason = f"Segment {seg.segment_code} is closed/inundated"
                                break

                # ---------------------------------------------------------
                # Case A: Route Blocked! Transition & Dynamic Reroute
                # ---------------------------------------------------------
                if route_compromised:
                    if prog:
                        prog.is_blocked = True

                    # IN_TRANSIT -> ROUTE_BLOCKED
                    EvacuationStateMachine.transition_state(
                        db=self.db,
                        allocation_id=alloc.id,
                        to_state=EvacuationStateEnum.ROUTE_BLOCKED,
                        justification=f"Route blocked at t={next_time:.1f}min: {compromised_reason}"
                    )

                    inv_event = SimulationEvent(
                        simulation_run_id=run.id,
                        simulation_time_min=next_time,
                        tick_index=tick_idx,
                        event_type=SimulationEventTypeEnum.ROUTE_INVALIDATED,
                        entity_type="RelocationAllocation",
                        entity_id=alloc.id,
                        details={
                            "route_plan_id": alloc.route_plan_id,
                            "reason": compromised_reason
                        }
                    )
                    self.db.add(inv_event)
                    events_generated.append(inv_event)

                    # Dynamic Reroute Attempt via E4
                    group = self.db.query(RelocationGroup).filter(RelocationGroup.id == alloc.group_id).first()
                    hab = self.db.query(Habitation).filter(Habitation.id == group.habitation_id).first() if group else None
                    dest = self.db.query(Destination).filter(Destination.id == alloc.destination_id).first() if alloc.destination_id else None

                    if hab and dest:
                        G, _ = self.e4.build_network_graph(road_nodes, eval_segments, current_flood_geom, current_flood_geom)
                        alt_route = self.e4.find_safe_route(G, hab, dest, road_nodes, run.scenario_snapshot_id)

                        if alt_route and alt_route.is_viable:
                            self.db.add(alt_route)
                            self.db.flush()
                            alloc.route_plan_id = alt_route.id
                            if prog:
                                prog.route_plan_id = alt_route.id
                                prog.total_travel_time_min = alt_route.total_time_min
                                prog.reroute_count += 1
                                prog.is_blocked = False

                            # ROUTE_BLOCKED -> IN_TRANSIT
                            EvacuationStateMachine.transition_state(
                                db=self.db,
                                allocation_id=alloc.id,
                                to_state=EvacuationStateEnum.IN_TRANSIT,
                                justification=f"Safe alternative route established via bypass (travel time {alt_route.total_time_min:.1f}min)"
                            )

                            replan_event = SimulationEvent(
                                simulation_run_id=run.id,
                                simulation_time_min=next_time,
                                tick_index=tick_idx,
                                event_type=SimulationEventTypeEnum.ROUTE_REPLANNED,
                                entity_type="RelocationAllocation",
                                entity_id=alloc.id,
                                details={
                                    "new_route_plan_id": alt_route.id,
                                    "new_travel_time_min": alt_route.total_time_min
                                }
                            )
                            self.db.add(replan_event)
                            events_generated.append(replan_event)
                            run.summary_metrics["routes_replanned"] = run.summary_metrics.get("routes_replanned", 0) + 1
                        else:
                            # Reroute failed: transition to STUCK (or REQUIRES_ASSISTANCE if special transit needed)
                            fallback_state = EvacuationStateEnum.REQUIRES_ASSISTANCE if (group and group.requires_special_transit) else EvacuationStateEnum.STUCK
                            EvacuationStateMachine.transition_state(
                                db=self.db,
                                allocation_id=alloc.id,
                                to_state=fallback_state,
                                justification=f"No viable alternative route to destination {dest.name}; group immobilized"
                            )

                            fail_event = SimulationEvent(
                                simulation_run_id=run.id,
                                simulation_time_min=next_time,
                                tick_index=tick_idx,
                                event_type=SimulationEventTypeEnum.REROUTE_FAILED,
                                entity_type="RelocationAllocation",
                                entity_id=alloc.id,
                                details={
                                    "destination_id": dest.id,
                                    "transitioned_to": fallback_state.value
                                }
                            )
                            self.db.add(fail_event)
                            events_generated.append(fail_event)
                            run.summary_metrics["stuck"] = run.summary_metrics.get("stuck", 0) + 1

                # ---------------------------------------------------------
                # Case B: Route is Safe, Advance Movement
                # ---------------------------------------------------------
                else:
                    if prog:
                        prog.elapsed_time_min += run.timestep_minutes
                        tt = max(1.0, prog.total_travel_time_min)
                        prog.progress_ratio = min(1.0, prog.elapsed_time_min / tt)

                        # Check for ARRIVAL
                        if prog.elapsed_time_min >= tt:
                            EvacuationStateMachine.transition_state(
                                db=self.db,
                                allocation_id=alloc.id,
                                to_state=EvacuationStateEnum.ARRIVED,
                                justification=f"Completed transit to destination facility at t={next_time:.1f}min"
                            )
                            arr_event = SimulationEvent(
                                simulation_run_id=run.id,
                                simulation_time_min=next_time,
                                tick_index=tick_idx,
                                event_type=SimulationEventTypeEnum.ARRIVAL,
                                entity_type="RelocationAllocation",
                                entity_id=alloc.id,
                                details={"destination_id": alloc.destination_id}
                            )
                            self.db.add(arr_event)
                            events_generated.append(arr_event)
                            run.summary_metrics["arrivals"] = run.summary_metrics.get("arrivals", 0) + 1

                            if auto_admit:
                                EvacuationStateMachine.transition_state(
                                    db=self.db,
                                    allocation_id=alloc.id,
                                    to_state=EvacuationStateEnum.SHELTERED,
                                    justification=f"Registered and sheltered inside facility at t={next_time:.1f}min"
                                )
                                shelt_event = SimulationEvent(
                                    simulation_run_id=run.id,
                                    simulation_time_min=next_time,
                                    tick_index=tick_idx,
                                    event_type=SimulationEventTypeEnum.SHELTERED,
                                    entity_type="RelocationAllocation",
                                    entity_id=alloc.id,
                                    details={"destination_id": alloc.destination_id}
                                )
                                self.db.add(shelt_event)
                                events_generated.append(shelt_event)
                                run.summary_metrics["sheltered"] = run.summary_metrics.get("sheltered", 0) + 1

            # ---------------------------------------------------------
            # STEP 7: Dynamic Resource Depletion & Carrying Capacity (Phase A.4)
            # ---------------------------------------------------------
            resource_eval = DynamicResourceManager.evaluate_tick_consumption_and_capacity(
                db=self.db,
                run=run,
                tick_index=tick_idx,
                simulation_time_min=next_time
            )
            for rev in resource_eval["events"]:
                self.db.add(rev)
                events_generated.append(rev)

            # ---------------------------------------------------------
            # STEP 8: Reallocate Infeasible Non-Moving Allocations
            # ---------------------------------------------------------
            infeasible_planned = []
            for alloc in allocs:
                if alloc.evacuation_state in [
                    EvacuationStateEnum.PLANNED, EvacuationStateEnum.NOTIFIED, EvacuationStateEnum.ACKNOWLEDGED
                ]:
                    # Check if destination or route is inundated
                    d = next((dest for dest in destinations if dest.id == alloc.destination_id), None)
                    if d:
                        dest_submerged = intersects(to_shapely(d.location_geom), current_flood_geom)
                        if dest_submerged:
                            infeasible_planned.append(alloc)

            # Add any allocations flagged by dynamic resource depletion (excess over remaining capacity)
            for c_alloc in resource_eval["candidate_reallocations"]:
                if c_alloc.id not in [a.id for a in infeasible_planned]:
                    infeasible_planned.append(c_alloc)

            if infeasible_planned:
                # Run CP-SAT solver specifically for these groups
                realloc_event = SimulationEvent(
                    simulation_run_id=run.id,
                    simulation_time_min=next_time,
                    tick_index=tick_idx,
                    event_type=SimulationEventTypeEnum.REALLOCATION_TRIGGERED,
                    entity_type="SimulationRun",
                    entity_id=run.id,
                    details={"affected_allocations_count": len(infeasible_planned)}
                )
                self.db.add(realloc_event)
                events_generated.append(realloc_event)

                # Reallocate using E4
                scen_capacities = {
                    c.destination_id: c for c in self.db.query(CapacityState).filter(
                        CapacityState.snapshot_id == run.scenario_snapshot_id
                    ).all()
                }
                # Reroute candidate generation
                G, _ = self.e4.build_network_graph(road_nodes, eval_segments, current_flood_geom, current_flood_geom)
                candidate_routes = {}
                for hab in habitations:
                    for d in destinations:
                        route = self.e4.find_safe_route(G, hab, d, road_nodes, run.scenario_snapshot_id)
                        if route:
                            self.db.add(route)
                            candidate_routes[(hab.id, d.id)] = route
                self.db.flush()

                realloc_groups = [
                    self.db.query(RelocationGroup).filter(RelocationGroup.id == a.group_id).first()
                    for a in infeasible_planned
                ]
                realloc_groups = [g for g in realloc_groups if g]

                new_allocs = self.e4.optimize_relocation(
                    groups=realloc_groups,
                    destinations=destinations,
                    capacity_states=scen_capacities,
                    candidate_routes=candidate_routes,
                    snapshot_id=run.scenario_snapshot_id
                )
                for na in new_allocs:
                    orig = next((oa for oa in infeasible_planned if oa.group_id == na.group_id), None)
                    if orig:
                        orig.destination_id = na.destination_id
                        orig.route_plan_id = na.route_plan_id
                        orig.allocation_status = na.allocation_status
                        orig.assigned_capacity_count = na.assigned_capacity_count
                        orig.reason_code = f"TEMPORAL_REALLOCATION_T_{tick_idx}"

                done_event = SimulationEvent(
                    simulation_run_id=run.id,
                    simulation_time_min=next_time,
                    tick_index=tick_idx,
                    event_type=SimulationEventTypeEnum.REALLOCATION_COMPLETED,
                    entity_type="SimulationRun",
                    entity_id=run.id,
                    details={"reallocated_count": len(new_allocs)}
                )
                self.db.add(done_event)
                events_generated.append(done_event)

            # ---------------------------------------------------------
            # STEP 8: Check Run Completion
            # ---------------------------------------------------------
            if run.current_simulation_time >= run.duration_minutes:
                run.status = SimulationStatusEnum.COMPLETED
                comp_event = SimulationEvent(
                    simulation_run_id=run.id,
                    simulation_time_min=next_time,
                    tick_index=tick_idx,
                    event_type=SimulationEventTypeEnum.SIMULATION_COMPLETED,
                    entity_type="SimulationRun",
                    entity_id=run.id,
                    details={
                        "total_ticks": run.ticks_completed,
                        "duration_minutes": run.duration_minutes,
                        "summary": run.summary_metrics
                    }
                )
                self.db.add(comp_event)
                events_generated.append(comp_event)

            run.summary_metrics["events_count"] = run.summary_metrics.get("events_count", 0) + len(events_generated)
            self.db.commit()
            self.db.refresh(run)

        except Exception as e:
            self.db.rollback()
            # Mark run failed
            try:
                run_failed = self.db.query(SimulationRun).filter(SimulationRun.id == run_id).first()
                if run_failed:
                    run_failed.status = SimulationStatusEnum.FAILED
                    err_event = SimulationEvent(
                        simulation_run_id=run_id,
                        simulation_time_min=run_failed.current_simulation_time,
                        tick_index=run_failed.ticks_completed,
                        event_type=SimulationEventTypeEnum.SIMULATION_FAILED,
                        entity_type="SimulationRun",
                        entity_id=run_id,
                        details={"error": str(e)}
                    )
                    self.db.add(err_event)
                    self.db.commit()
            except Exception:
                pass
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"SIMULATION_TICK_FAILED: Error executing simulation tick {run.ticks_completed + 1}: {str(e)}"
            )

        return {
            "run": run,
            "tick_index": tick_idx,
            "simulation_time_min": next_time,
            "events_generated": events_generated,
            "state_summary": {
                "status": run.status.value,
                "current_time_min": run.current_simulation_time,
                "ticks_completed": run.ticks_completed,
                "total_ticks": run.total_ticks,
                "events_in_tick": len(events_generated),
                "metrics": run.summary_metrics
            }
        }

    def run_simulation(
        self,
        run_id: str,
        max_steps: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Advances the simulation until completion or until max_steps is reached.
        """
        run = self.db.query(SimulationRun).filter(SimulationRun.id == run_id).first()
        if not run:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"SIMULATION_RUN_NOT_FOUND: Simulation run '{run_id}' not found."
            )

        all_events: List[SimulationEvent] = []
        steps_executed = 0

        while run.status not in [SimulationStatusEnum.COMPLETED, SimulationStatusEnum.FAILED, SimulationStatusEnum.CANCELLED]:
            if max_steps is not None and steps_executed >= max_steps:
                break
            res = self.step_simulation(run_id)
            all_events.extend(res["events_generated"])
            steps_executed += 1
            run = self.db.query(SimulationRun).filter(SimulationRun.id == run_id).first()

        return {
            "run": run,
            "steps_executed": steps_executed,
            "total_events_generated": len(all_events),
            "final_status": run.status.value,
            "current_simulation_time": run.current_simulation_time,
            "metrics": run.summary_metrics
        }

    def pause_simulation(self, run_id: str) -> SimulationRun:
        """Pauses a running or created simulation."""
        run = self.db.query(SimulationRun).filter(SimulationRun.id == run_id).first()
        if not run:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"SIMULATION_RUN_NOT_FOUND: Simulation run '{run_id}' not found."
            )
        if run.status in [SimulationStatusEnum.COMPLETED, SimulationStatusEnum.CANCELLED, SimulationStatusEnum.FAILED]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"INVALID_SIMULATION_STATE: Cannot pause simulation with status '{run.status.value}'."
            )
        if run.status == SimulationStatusEnum.PAUSED:
            return run

        if run.status in [SimulationStatusEnum.RUNNING, SimulationStatusEnum.CREATED]:
            run.status = SimulationStatusEnum.PAUSED
            pause_event = SimulationEvent(
                simulation_run_id=run.id,
                simulation_time_min=run.current_simulation_time,
                tick_index=run.ticks_completed,
                event_type=SimulationEventTypeEnum.SIMULATION_PAUSED,
                entity_type="SimulationRun",
                entity_id=run.id,
                details={"message": "Simulation paused by operator"}
            )
            self.db.add(pause_event)
            self.db.commit()
            self.db.refresh(run)
        return run

    def resume_simulation(self, run_id: str) -> SimulationRun:
        """Resumes a paused simulation."""
        run = self.db.query(SimulationRun).filter(SimulationRun.id == run_id).first()
        if not run:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"SIMULATION_RUN_NOT_FOUND: Simulation run '{run_id}' not found."
            )
        if run.status != SimulationStatusEnum.PAUSED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"INVALID_SIMULATION_STATE: Cannot resume simulation with status '{run.status.value}'. Must be in PAUSED state."
            )

        run.status = SimulationStatusEnum.RUNNING
        resume_event = SimulationEvent(
            simulation_run_id=run.id,
            simulation_time_min=run.current_simulation_time,
            tick_index=run.ticks_completed,
            event_type=SimulationEventTypeEnum.SIMULATION_RESUMED,
            entity_type="SimulationRun",
            entity_id=run.id,
            details={"message": "Simulation resumed by operator"}
        )
        self.db.add(resume_event)
        self.db.commit()
        self.db.refresh(run)
        return run

    def cancel_simulation(self, run_id: str) -> SimulationRun:
        """Cancels an active or paused simulation."""
        run = self.db.query(SimulationRun).filter(SimulationRun.id == run_id).first()
        if not run:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"SIMULATION_RUN_NOT_FOUND: Simulation run '{run_id}' not found."
            )
        if run.status in [SimulationStatusEnum.COMPLETED, SimulationStatusEnum.CANCELLED, SimulationStatusEnum.FAILED]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"INVALID_SIMULATION_STATE: Cannot cancel simulation with status '{run.status.value}'."
            )

        run.status = SimulationStatusEnum.CANCELLED
        cancel_event = SimulationEvent(
            simulation_run_id=run.id,
            simulation_time_min=run.current_simulation_time,
            tick_index=run.ticks_completed,
            event_type=SimulationEventTypeEnum.SIMULATION_CANCELLED,
            entity_type="SimulationRun",
            entity_id=run.id,
            details={"message": "Simulation cancelled by operator"}
        )
        self.db.add(cancel_event)
        self.db.commit()
        self.db.refresh(run)
        return run

