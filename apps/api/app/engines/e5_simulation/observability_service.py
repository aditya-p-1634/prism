"""
PRISM Phase A.5 — Simulation Observability & Operational Metrics Service

This service provides read-only operational observability, metrics computation,
and chronological timeline inspection for simulation runs.

Guarantees:
- Read-only: Performs ZERO mutations on any database tables or baseline snapshots.
- Deterministic: Output metrics, summaries, and timeline ordering are 100% reproducible.
- Authoritative Sources: Derives metrics from authoritative A.1-A.4 tables
  (SimulationRun, RelocationAllocation, SimulationAllocationProgress,
   SimulationResourceState, CapacityState, RoadSegment, SimulationEvent).
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.entities import (
    SimulationRun,
    SimulationEvent,
    RelocationAllocation,
    SimulationAllocationProgress,
    SimulationResourceState,
    CapacityState,
    Destination,
    DestinationResource,
    RoadSegment,
)
from app.models.enums import (
    EvacuationStateEnum,
    SimulationEventTypeEnum,
    SimulationStatusEnum,
    ResourceStatusEnum,
    ResourceCategoryEnum,
    AllocationStatusEnum,
)
from app.schemas.simulation import (
    ConsolidatedSimulationStateDTO,
    SimulationPopulationStateDTO,
    SimulationInfrastructureStateDTO,
    SimulationPlanningStateDTO,
    DestinationResourceSummaryDTO,
    ResourceStateDTO,
    SimulationTimelineEventDTO,
    SimulationTimelineResponseDTO,
    SimulationOperationalMetricsDTO,
)


class SimulationObservabilityService:
    """Read-only operational observability and metrics service."""

    IMPORTANT_EVENT_TYPES = {
        SimulationEventTypeEnum.ROAD_BLOCKED,
        SimulationEventTypeEnum.ROUTE_INVALIDATED,
        SimulationEventTypeEnum.ROUTE_REPLANNED,
        SimulationEventTypeEnum.REROUTE_FAILED,
        SimulationEventTypeEnum.REALLOCATION_TRIGGERED,
        SimulationEventTypeEnum.REALLOCATION_COMPLETED,
        SimulationEventTypeEnum.RESOURCE_WARNING,
        SimulationEventTypeEnum.RESOURCE_EXHAUSTED,
        SimulationEventTypeEnum.DESTINATION_INFEASIBLE,
        SimulationEventTypeEnum.DESTINATION_CAPACITY_CHANGED,
        SimulationEventTypeEnum.SIMULATION_COMPLETED,
        SimulationEventTypeEnum.SIMULATION_FAILED,
        SimulationEventTypeEnum.SIMULATION_CANCELLED,
    }

    @staticmethod
    def generate_event_summary(event: SimulationEvent) -> str:
        """
        Generates a concise, deterministic, factual human-readable explanation
        strictly from the event type and structured event payload.
        """
        details = event.details or {}
        etype = event.event_type
        entity_id = event.entity_id or "unknown"

        if etype == SimulationEventTypeEnum.ROAD_BLOCKED:
            code = details.get("segment_code") or entity_id
            return f"Road {code} became blocked."

        if etype == SimulationEventTypeEnum.ROAD_REOPENED:
            code = details.get("segment_code") or entity_id
            return f"Road {code} reopened."

        if etype == SimulationEventTypeEnum.ROUTE_INVALIDATED:
            return f"Route for allocation {entity_id} became invalid."

        if etype == SimulationEventTypeEnum.ROUTE_REPLANNED:
            time_info = ""
            if "new_travel_time_min" in details:
                time_info = f" (travel time {details['new_travel_time_min']:.1f}min)"
            return f"Allocation {entity_id} was assigned a new feasible route{time_info}."

        if etype == SimulationEventTypeEnum.REROUTE_FAILED:
            fallback = details.get("transitioned_to", "STUCK")
            return f"Reroute failed for allocation {entity_id}; group transitioned to {fallback}."

        if etype == SimulationEventTypeEnum.ARRIVAL:
            return f"Allocation {entity_id} reached its destination."

        if etype == SimulationEventTypeEnum.SHELTERED:
            return f"Allocation {entity_id} admitted and sheltered inside destination facility."

        if etype == SimulationEventTypeEnum.EVACUATION_STATE_CHANGED:
            from_st = details.get("from_state", "UNKNOWN")
            to_st = details.get("to_state", "UNKNOWN")
            return f"Allocation {entity_id} changed evacuation state from {from_st} to {to_st}."

        if etype == SimulationEventTypeEnum.MOVEMENT_PROGRESSED:
            ratio = details.get("progress_ratio")
            pct_str = f" ({ratio * 100:.0f}%)" if ratio is not None else ""
            return f"Allocation {entity_id} advanced transit progress{pct_str}."

        if etype == SimulationEventTypeEnum.HAZARD_EXPANDED:
            rf = details.get("rainfall_multiplier_delta", 0.0)
            rv = details.get("river_level_delta_m", 0.0)
            return f"Hazard expanded (rainfall delta: +{rf:.2f}, river level: +{rv:.2f}m)."

        if etype == SimulationEventTypeEnum.REALLOCATION_TRIGGERED:
            count = details.get("affected_allocations_count", 0)
            return f"CP-SAT reallocation triggered for {count} infeasible allocations."

        if etype == SimulationEventTypeEnum.REALLOCATION_COMPLETED:
            count = details.get("reallocated_count", 0)
            return f"CP-SAT reallocation completed for {count} allocations."

        if etype == SimulationEventTypeEnum.RESOURCE_CONSUMED:
            dest = details.get("destination_code") or entity_id
            return f"Resources consumed at destination {dest}."

        if etype == SimulationEventTypeEnum.RESOURCE_WARNING:
            dest = details.get("destination_code") or entity_id
            res_type = details.get("resource_type", "resource")
            return f"Destination {dest} became resource-constrained ({res_type})."

        if etype == SimulationEventTypeEnum.RESOURCE_EXHAUSTED:
            dest = details.get("destination_code") or entity_id
            res_type = details.get("resource_type", "resource")
            return f"Destination {dest} exhausted {res_type}."

        if etype == SimulationEventTypeEnum.DESTINATION_CAPACITY_CHANGED:
            dest = details.get("destination_code") or entity_id
            eff_cap = details.get("effective_capacity", 0)
            return f"Destination {dest} effective capacity changed to {eff_cap}."

        if etype == SimulationEventTypeEnum.DESTINATION_INFEASIBLE:
            dest = details.get("destination_code") or entity_id
            return f"Destination {dest} can no longer accommodate the affected uncommitted demand."

        if etype == SimulationEventTypeEnum.SIMULATION_STARTED:
            scenario = details.get("scenario_code", "")
            sc_str = f" for scenario {scenario}" if scenario else ""
            return f"Simulation started{sc_str}."

        if etype == SimulationEventTypeEnum.SIMULATION_TICK:
            return f"Simulation advanced to tick {event.tick_index} ({event.simulation_time_min:.1f} min)."

        if etype == SimulationEventTypeEnum.SIMULATION_PAUSED:
            return "Simulation paused by operator."

        if etype == SimulationEventTypeEnum.SIMULATION_RESUMED:
            return "Simulation resumed by operator."

        if etype == SimulationEventTypeEnum.SIMULATION_COMPLETED:
            total_ticks = details.get("total_ticks", event.tick_index)
            return f"Simulation completed successfully ({total_ticks} ticks)."

        if etype == SimulationEventTypeEnum.SIMULATION_FAILED:
            err = details.get("error", "Unknown error")
            return f"Simulation failed: {err}."

        if etype == SimulationEventTypeEnum.SIMULATION_CANCELLED:
            return "Simulation cancelled by operator."

        return f"{etype.value} event on {event.entity_type or 'simulation'} {entity_id}."

    @classmethod
    def to_timeline_event_dto(cls, event: SimulationEvent) -> SimulationTimelineEventDTO:
        """Converts SimulationEvent model to SimulationTimelineEventDTO with human-readable summary."""
        return SimulationTimelineEventDTO(
            id=event.id,
            simulation_run_id=event.simulation_run_id,
            simulation_time_min=event.simulation_time_min,
            tick_index=event.tick_index,
            event_type=event.event_type,
            entity_type=event.entity_type,
            entity_id=event.entity_id,
            summary=cls.generate_event_summary(event),
            details=event.details or {},
            created_at=event.created_at,
        )

    @classmethod
    def get_simulation_timeline(
        cls,
        db: Session,
        run_id: str,
        limit: int = 50,
        offset: int = 0,
        event_type: Optional[SimulationEventTypeEnum] = None,
    ) -> SimulationTimelineResponseDTO:
        """
        Retrieves chronological simulation event history with deterministic ordering
        and human-readable summaries.
        """
        run = db.query(SimulationRun).filter(SimulationRun.id == run_id).first()
        if not run:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"SIMULATION_RUN_NOT_FOUND: Simulation run '{run_id}' not found.",
            )

        query = db.query(SimulationEvent).filter(SimulationEvent.simulation_run_id == run_id)
        if event_type:
            query = query.filter(SimulationEvent.event_type == event_type)

        # Deterministic chronological sort order
        query = query.order_by(
            SimulationEvent.simulation_time_min.asc(),
            SimulationEvent.tick_index.asc(),
            SimulationEvent.created_at.asc(),
            SimulationEvent.id.asc(),
        )

        total_events = query.count()
        events = query.offset(offset).limit(limit).all()

        dtos = [cls.to_timeline_event_dto(e) for e in events]

        return SimulationTimelineResponseDTO(
            run_id=run_id,
            total_events=total_events,
            returned_events=len(dtos),
            limit=limit,
            offset=offset,
            events=dtos,
        )

    @classmethod
    def get_consolidated_state(cls, db: Session, run_id: str) -> ConsolidatedSimulationStateDTO:
        """
        Produces a consolidated read-only snapshot of current simulation state,
        including population, infrastructure, resource, and planning metrics.
        """
        run = db.query(SimulationRun).filter(SimulationRun.id == run_id).first()
        if not run:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"SIMULATION_RUN_NOT_FOUND: Simulation run '{run_id}' not found.",
            )

        snapshot_id = run.scenario_snapshot_id

        # 1. Progress Calculation
        if run.duration_minutes == 0:
            progress_pct = 100.0
        else:
            progress_pct = min(100.0, round((run.current_simulation_time / run.duration_minutes) * 100, 2))

        # 2. Population & Evacuation State Analysis
        allocations = (
            db.query(RelocationAllocation)
            .filter(RelocationAllocation.snapshot_id == snapshot_id)
            .order_by(RelocationAllocation.id.asc())
            .all()
        )

        counts_by_state = {s.value: 0 for s in EvacuationStateEnum}
        allocation_counts_by_state = {s.value: 0 for s in EvacuationStateEnum}

        for alloc in allocations:
            state_key = alloc.evacuation_state.value if alloc.evacuation_state else EvacuationStateEnum.PLANNED.value
            if state_key in counts_by_state:
                counts_by_state[state_key] += alloc.assigned_capacity_count
                allocation_counts_by_state[state_key] += 1

        total_pop = sum(counts_by_state.values())

        population_dto = SimulationPopulationStateDTO(
            total_population=total_pop,
            affected_population=total_pop,
            counts_by_state=counts_by_state,
            allocation_counts_by_state=allocation_counts_by_state,
            planned_population=counts_by_state.get(EvacuationStateEnum.PLANNED.value, 0),
            in_transit_population=counts_by_state.get(EvacuationStateEnum.IN_TRANSIT.value, 0),
            arrived_population=counts_by_state.get(EvacuationStateEnum.ARRIVED.value, 0),
            sheltered_population=counts_by_state.get(EvacuationStateEnum.SHELTERED.value, 0),
            stuck_population=counts_by_state.get(EvacuationStateEnum.STUCK.value, 0),
            route_blocked_population=counts_by_state.get(EvacuationStateEnum.ROUTE_BLOCKED.value, 0),
            assistance_required_population=counts_by_state.get(EvacuationStateEnum.REQUIRES_ASSISTANCE.value, 0),
            no_response_population=counts_by_state.get(EvacuationStateEnum.NO_RESPONSE.value, 0),
        )

        # 3. Infrastructure & Routes Analysis
        all_roads = db.query(RoadSegment).all()
        total_roads = len(all_roads)
        closed_codes_list = run.parameters.get("closed_road_segments", [])
        blocked_codes = sorted(list(set(closed_codes_list)))
        blocked_roads_count = len(blocked_codes)
        open_roads_count = max(0, total_roads - blocked_roads_count)

        progress_records = (
            db.query(SimulationAllocationProgress)
            .filter(SimulationAllocationProgress.simulation_run_id == run.id)
            .all()
        )
        prog_map = {p.allocation_id: p for p in progress_records}

        reroute_count_sum = sum(p.reroute_count for p in progress_records)
        invalidated_count = run.summary_metrics.get("routes_invalidated", sum(1 for p in progress_records if p.is_blocked))

        active_routes_count = sum(
            1
            for a in allocations
            if a.evacuation_state in [EvacuationStateEnum.IN_TRANSIT, EvacuationStateEnum.MOVING]
            and not (a.id in prog_map and prog_map[a.id].is_blocked)
        )

        failed_reroutes = sum(
            1
            for a in allocations
            if a.evacuation_state in [EvacuationStateEnum.STUCK, EvacuationStateEnum.REQUIRES_ASSISTANCE]
        )

        infrastructure_dto = SimulationInfrastructureStateDTO(
            blocked_roads_count=blocked_roads_count,
            open_roads_count=open_roads_count,
            blocked_road_codes=blocked_codes,
            invalidated_routes_count=invalidated_count,
            active_routes_count=active_routes_count,
            reroute_counts=reroute_count_sum,
            failed_reroutes=failed_reroutes,
        )

        # 4. Resources Analysis
        destinations = db.query(Destination).order_by(Destination.code.asc()).all()
        res_states = (
            db.query(SimulationResourceState)
            .filter(SimulationResourceState.simulation_run_id == run.id)
            .order_by(SimulationResourceState.destination_id.asc(), SimulationResourceState.resource_type.asc())
            .all()
        )
        cap_states = (
            db.query(CapacityState)
            .filter(CapacityState.snapshot_id == snapshot_id)
            .order_by(CapacityState.destination_id.asc())
            .all()
        )
        cap_map = {cs.destination_id: cs for cs in cap_states}

        dest_summaries: List[DestinationResourceSummaryDTO] = []
        for d in destinations:
            d_states = [s for s in res_states if s.destination_id == d.id]
            d_allocs = [a for a in allocations if a.destination_id == d.id]

            sheltered_pop = sum(
                a.assigned_capacity_count
                for a in d_allocs
                if a.evacuation_state in [EvacuationStateEnum.ARRIVED, EvacuationStateEnum.SHELTERED]
            )
            uncommitted_demand = sum(
                a.assigned_capacity_count
                for a in d_allocs
                if a.evacuation_state
                in [
                    EvacuationStateEnum.PLANNED,
                    EvacuationStateEnum.NOTIFIED,
                    EvacuationStateEnum.ACKNOWLEDGED,
                    EvacuationStateEnum.EVACUATION_ORDERED,
                ]
            )

            cap_st = cap_map.get(d.id)
            effective_cap = cap_st.effective_capacity if cap_st else 0
            rem_cap = cap_st.remaining_capacity if cap_st else 0
            bottleneck = cap_st.bottleneck_resource if cap_st else "SHELTER"
            is_safe = cap_st.is_safe if cap_st else True
            is_feasible = is_safe and (rem_cap >= uncommitted_demand)

            resource_dtos = [
                ResourceStateDTO(
                    id=s.id,
                    destination_id=s.destination_id,
                    resource_category=s.resource_category,
                    resource_type=s.resource_type.value,
                    total_quantity=s.total_quantity,
                    consumed_quantity=s.consumed_quantity,
                    remaining_quantity=s.remaining_quantity,
                    unit=s.unit,
                    supportable_population=s.supportable_population,
                    status=s.status,
                )
                for s in d_states
            ]

            dest_summaries.append(
                DestinationResourceSummaryDTO(
                    destination_id=d.id,
                    destination_code=d.code,
                    destination_name=d.name,
                    is_safe=is_safe,
                    is_feasible=is_feasible,
                    effective_capacity=effective_cap,
                    occupied_population=sheltered_pop,
                    effective_remaining_capacity=rem_cap,
                    uncommitted_planned_demand=uncommitted_demand,
                    bottleneck_resource=bottleneck,
                    resources=resource_dtos,
                )
            )

        # 5. Planning Analysis
        unmet_allocs = [
            a
            for a in allocations
            if a.allocation_status == AllocationStatusEnum.UNMET or a.destination_id is None
        ]
        unmet_count = len(unmet_allocs)
        unmet_pop = sum(a.assigned_capacity_count for a in unmet_allocs)

        reallocation_count = run.summary_metrics.get(
            "reallocations_completed",
            run.summary_metrics.get("reallocations_triggered", 0),
        )
        infeasible_dest_count = sum(1 for ds in dest_summaries if not ds.is_feasible)

        planning_dto = SimulationPlanningStateDTO(
            allocation_count=len(allocations),
            unmet_demand_count=unmet_count,
            unmet_demand_population=unmet_pop,
            reallocation_count=reallocation_count,
            infeasible_destinations_count=infeasible_dest_count,
        )

        # 6. Events & Timeline Highlights
        all_events_ordered = (
            db.query(SimulationEvent)
            .filter(SimulationEvent.simulation_run_id == run.id)
            .order_by(
                SimulationEvent.simulation_time_min.asc(),
                SimulationEvent.tick_index.asc(),
                SimulationEvent.created_at.asc(),
                SimulationEvent.id.asc(),
            )
            .all()
        )

        event_counts_by_type: Dict[str, int] = {}
        for ev in all_events_ordered:
            etype_str = ev.event_type.value if hasattr(ev.event_type, "value") else str(ev.event_type)
            event_counts_by_type[etype_str] = event_counts_by_type.get(etype_str, 0) + 1

        recent_events = [cls.to_timeline_event_dto(e) for e in all_events_ordered[-10:]]

        # Latest important event
        latest_important_event: Optional[SimulationTimelineEventDTO] = None
        for ev in reversed(all_events_ordered):
            if ev.event_type in cls.IMPORTANT_EVENT_TYPES:
                latest_important_event = cls.to_timeline_event_dto(ev)
                break

        return ConsolidatedSimulationStateDTO(
            run_id=run.id,
            scenario_id=run.scenario_id,
            snapshot_id=snapshot_id,
            status=run.status,
            current_simulation_time=run.current_simulation_time,
            current_tick=run.ticks_completed,
            total_ticks=run.total_ticks,
            timestep_minutes=run.timestep_minutes,
            duration_minutes=run.duration_minutes,
            progress_percentage=progress_pct,
            population=population_dto,
            infrastructure=infrastructure_dto,
            resources=dest_summaries,
            planning=planning_dto,
            recent_events=recent_events,
            event_counts_by_type=event_counts_by_type,
            latest_important_event=latest_important_event,
        )

    @classmethod
    def get_operational_metrics(cls, db: Session, run_id: str) -> SimulationOperationalMetricsDTO:
        """
        Derives operational metrics from authoritative simulation models.
        Strictly deterministic, read-only.
        """
        state = cls.get_consolidated_state(db, run_id)

        # Capacity aggregations
        shelter_states = [r for ds in state.resources for r in ds.resources if r.resource_type == ResourceCategoryEnum.SHELTER.value]
        if shelter_states:
            total_physical_capacity = int(sum(r.total_quantity for r in shelter_states))
        else:
            base_shelters = (
                db.query(DestinationResource)
                .filter(
                    DestinationResource.snapshot_id == "SNAP_BASE_001",
                    DestinationResource.resource_type == ResourceCategoryEnum.SHELTER,
                )
                .all()
            )
            total_physical_capacity = int(sum(r.quantity for r in base_shelters))


        total_effective_capacity = sum(ds.effective_capacity for ds in state.resources)
        total_occupied_capacity = sum(ds.occupied_population for ds in state.resources)
        total_remaining_capacity = sum(ds.effective_remaining_capacity for ds in state.resources)

        overall_occupancy_pct = (
            round((total_occupied_capacity / total_effective_capacity) * 100, 2)
            if total_effective_capacity > 0
            else 0.0
        )

        # Water consumed liters
        water_consumed = 0.0
        destinations_constrained = 0
        destinations_exhausted = 0
        for ds in state.resources:
            has_constrained = False
            has_exhausted = False
            for r in ds.resources:
                if r.resource_type == ResourceCategoryEnum.WATER.value:
                    water_consumed += r.consumed_quantity
                if r.status == ResourceStatusEnum.CONSTRAINED:
                    has_constrained = True
                elif r.status == ResourceStatusEnum.EXHAUSTED:
                    has_exhausted = True
            if has_constrained:
                destinations_constrained += 1
            if has_exhausted:
                destinations_exhausted += 1

        total_events = sum(state.event_counts_by_type.values())

        return SimulationOperationalMetricsDTO(
            run_id=state.run_id,
            snapshot_id=state.snapshot_id,
            status=state.status,
            current_simulation_time=state.current_simulation_time,
            ticks_completed=state.current_tick,
            total_ticks=state.total_ticks,
            progress_pct=state.progress_percentage,
            total_population=state.population.total_population,
            sheltered_population=state.population.sheltered_population,
            in_transit_population=state.population.in_transit_population,
            stuck_population=state.population.stuck_population,
            route_blocked_population=state.population.route_blocked_population,
            assistance_required_population=state.population.assistance_required_population,
            planned_population=state.population.planned_population,
            population_by_state=state.population.counts_by_state,
            allocations_by_state=state.population.allocation_counts_by_state,
            blocked_roads_count=state.infrastructure.blocked_roads_count,
            active_routes_count=state.infrastructure.active_routes_count,
            invalidated_routes_count=state.infrastructure.invalidated_routes_count,
            reroute_count=state.infrastructure.reroute_counts,
            failed_reroute_count=state.infrastructure.failed_reroutes,
            total_physical_capacity=total_physical_capacity,
            total_effective_capacity=total_effective_capacity,
            total_occupied_capacity=total_occupied_capacity,
            total_remaining_capacity=total_remaining_capacity,
            overall_occupancy_pct=overall_occupancy_pct,
            total_water_consumed_liters=round(water_consumed, 2),
            destinations_constrained_count=destinations_constrained,
            destinations_exhausted_count=destinations_exhausted,
            destinations_infeasible_count=state.planning.infeasible_destinations_count,
            unmet_demand_count=state.planning.unmet_demand_count,
            unmet_demand_population=state.planning.unmet_demand_population,
            total_events_recorded=total_events,
            counts_by_event_type=state.event_counts_by_type,
        )
