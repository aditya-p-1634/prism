"""PRISM V2 — Dynamic Resource Manager (E3 - Phase A.4)
=====================================================
Deterministic Resource Consumption, Dynamic Carrying Capacity,
Destination Feasibility, and Selective CP-SAT Reallocation.

CORE INVARIANTS:
1. Resource categories: POPULATION_SPACE (shelter space constraint), WATER (consumable), MEDICAL_CAPACITY (support constraint).
2. Effective capacity is minimum supportable population across critical resources.
3. Effective capacity cannot exceed physical population capacity.
4. Effective remaining capacity cannot become negative.
5. Water and medical quantities never become negative.
6. Only ARRIVED and SHELTERED populations consume shelter resources.
7. Uncommitted planned allocations (PLANNED, NOTIFIED, ACKNOWLEDGED) do not consume physical resources.
8. ARRIVED and SHELTERED groups are NEVER automatically evicted or reallocated.
9. CP-SAT is selectively triggered ONLY when uncommitted planned demand exceeds remaining capacity.
10. All operations are strictly deterministic and isolated to mutable scenario/simulation branches.
"""

import math
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session

from app.models.entities import (
    Destination, DestinationResource, CapacityState, RelocationAllocation,
    RelocationGroup, SimulationRun, SimulationEvent, SimulationResourceState
)
from app.models.enums import (
    ResourceCategoryEnum, ResourceStatusEnum, SimulationEventTypeEnum,
    EvacuationStateEnum, OperationalStatusEnum
)


class DynamicResourceManager:
    """Manages deterministic resource consumption and carrying capacity calculations."""

    RESOURCE_MAPPING = {
        "POPULATION_SPACE": ResourceCategoryEnum.SHELTER,
        "WATER": ResourceCategoryEnum.WATER,
        "MEDICAL_CAPACITY": ResourceCategoryEnum.HEALTHCARE,
    }

    REVERSE_MAPPING = {
        ResourceCategoryEnum.SHELTER: "POPULATION_SPACE",
        ResourceCategoryEnum.WATER: "WATER",
        ResourceCategoryEnum.HEALTHCARE: "MEDICAL_CAPACITY",
    }

    @classmethod
    def initialize_simulation_resources(
        cls,
        db: Session,
        run: SimulationRun
    ) -> List[SimulationResourceState]:
        """
        Initializes simulation-scoped resource state records for a SimulationRun.
        Creates 1 row per destination per resource category (3 destinations * 3 categories = 9 rows).
        """
        # Ensure clean state for this run
        existing = db.query(SimulationResourceState).filter(
            SimulationResourceState.simulation_run_id == run.id
        ).all()
        if existing:
            return existing

        destinations = db.query(Destination).all()
        created_states: List[SimulationResourceState] = []

        for d in destinations:
            # Query DestinationResource records for the scenario snapshot
            dest_res = db.query(DestinationResource).filter(
                DestinationResource.destination_id == d.id,
                DestinationResource.snapshot_id == run.scenario_snapshot_id
            ).all()

            res_by_type = {r.resource_type: r for r in dest_res}

            for cat_name, res_type in cls.RESOURCE_MAPPING.items():
                r = res_by_type.get(res_type)
                if r:
                    total_qty = float(r.quantity)
                    unit = r.unit
                    supportable = int(r.supportable_population)
                else:
                    # Deterministic safe fallbacks based on category
                    if cat_name == "POPULATION_SPACE":
                        total_qty = 100.0
                        unit = "BEDS"
                        supportable = 100
                    elif cat_name == "WATER":
                        total_qty = 2000.0
                        unit = "LITERS"
                        supportable = 100
                    else: # MEDICAL_CAPACITY
                        total_qty = 2.0
                        unit = "MEDICS"
                        supportable = 100

                state = SimulationResourceState(
                    simulation_run_id=run.id,
                    destination_id=d.id,
                    resource_category=cat_name,
                    resource_type=res_type,
                    total_quantity=total_qty,
                    consumed_quantity=0.0,
                    remaining_quantity=total_qty,
                    unit=unit,
                    supportable_population=supportable,
                    status=ResourceStatusEnum.NORMAL
                )
                db.add(state)
                created_states.append(state)

        db.flush()
        return created_states

    @classmethod
    def evaluate_tick_consumption_and_capacity(
        cls,
        db: Session,
        run: SimulationRun,
        tick_index: int,
        simulation_time_min: float
    ) -> Dict[str, Any]:
        """
        Calculates deterministic resource consumption for this tick, updates effective capacities,
        and identifies destination feasibility for uncommitted planned groups.
        """
        events: List[SimulationEvent] = []
        infeasible_dest_ids: List[str] = []
        candidate_reallocations: List[RelocationAllocation] = []

        # 1. Fetch simulation resource states for this run
        res_states = db.query(SimulationResourceState).filter(
            SimulationResourceState.simulation_run_id == run.id
        ).all()
        if not res_states:
            res_states = cls.initialize_simulation_resources(db, run)

        destinations = db.query(Destination).all()
        allocs = db.query(RelocationAllocation).filter(
            RelocationAllocation.snapshot_id == run.scenario_snapshot_id
        ).all()
        groups = db.query(RelocationGroup).filter(
            RelocationGroup.snapshot_id == run.scenario_snapshot_id
        ).all()
        group_map = {g.id: g for g in groups}

        cap_states = db.query(CapacityState).filter(
            CapacityState.snapshot_id == run.scenario_snapshot_id
        ).all()
        cap_state_map = {cs.destination_id: cs for cs in cap_states}

        # 2. Configurable Prototype Consumption Parameters
        params = run.parameters or {}
        # Water rate: liters per person per tick
        if "water_consumption_per_person_per_tick" in params:
            water_consumption_rate = float(params["water_consumption_per_person_per_tick"])
        else:
            water_rate_per_min = float(params.get("water_consumption_per_person_per_min", 0.1))
            water_consumption_rate = water_rate_per_min * run.timestep_minutes

        water_requirement_per_person = float(params.get("water_requirement_per_person", 20.0))
        warning_threshold_ratio = float(params.get("resource_warning_threshold_ratio", 0.25))
        medical_demand_rate_general = float(params.get("medical_demand_per_person", 1.0))
        medical_demand_rate_special = float(params.get("medical_demand_special_transit", 2.0))

        # 3. Process Each Destination
        destination_summaries: List[Dict[str, Any]] = []

        for d in destinations:
            dest_states = [s for s in res_states if s.destination_id == d.id]
            dest_allocs = [a for a in allocs if a.destination_id == d.id]

            # Physical population at destination (ARRIVED or SHELTERED)
            arrived_sheltered = [
                a for a in dest_allocs if a.evacuation_state in [
                    EvacuationStateEnum.ARRIVED, EvacuationStateEnum.SHELTERED
                ]
            ]
            sheltered_population = sum(a.assigned_capacity_count for a in arrived_sheltered)

            # Uncommitted planned allocations (PLANNED, NOTIFIED, ACKNOWLEDGED, EVACUATION_ORDERED)
            uncommitted_allocs = [
                a for a in dest_allocs if a.evacuation_state in [
                    EvacuationStateEnum.PLANNED, EvacuationStateEnum.NOTIFIED,
                    EvacuationStateEnum.ACKNOWLEDGED, EvacuationStateEnum.EVACUATION_ORDERED
                ]
            ]
            uncommitted_demand = sum(a.assigned_capacity_count for a in uncommitted_allocs)

            cap_st = cap_state_map.get(d.id)
            prev_effective_cap = cap_st.effective_capacity if cap_st else 0

            # ---------------------------------------------------------
            # A. Process WATER
            # ---------------------------------------------------------
            water_res = next((s for s in dest_states if s.resource_category == "WATER"), None)
            water_supportable = 0
            if water_res:
                water_consumed_this_tick = max(0.0, sheltered_population * water_consumption_rate)
                new_consumed = min(water_res.total_quantity, water_res.consumed_quantity + water_consumed_this_tick)
                new_remaining = max(0.0, water_res.total_quantity - new_consumed)

                water_res.consumed_quantity = round(new_consumed, 3)
                water_res.remaining_quantity = round(new_remaining, 3)

                if water_requirement_per_person > 0:
                    water_supportable = int(math.floor(new_remaining / water_requirement_per_person))
                else:
                    water_supportable = 0
                water_res.supportable_population = max(0, water_supportable)

                prev_status = water_res.status
                if new_remaining <= 0.0 or water_supportable == 0:
                    water_res.status = ResourceStatusEnum.EXHAUSTED
                elif new_remaining <= (water_res.total_quantity * warning_threshold_ratio):
                    water_res.status = ResourceStatusEnum.CONSTRAINED
                else:
                    water_res.status = ResourceStatusEnum.NORMAL

                # Events: RESOURCE_CONSUMED (if consumed > 0)
                if water_consumed_this_tick > 0:
                    events.append(SimulationEvent(
                        simulation_run_id=run.id,
                        simulation_time_min=simulation_time_min,
                        tick_index=tick_index,
                        event_type=SimulationEventTypeEnum.RESOURCE_CONSUMED,
                        entity_type="DestinationResource",
                        entity_id=water_res.id,
                        details={
                            "destination_code": d.code,
                            "resource_category": "WATER",
                            "consumed_this_tick": round(water_consumed_this_tick, 2),
                            "total_consumed": round(water_res.consumed_quantity, 2),
                            "remaining_quantity": round(water_res.remaining_quantity, 2),
                            "sheltered_population": sheltered_population
                        }
                    ))

                # Status Transition Events
                if water_res.status != prev_status:
                    if water_res.status == ResourceStatusEnum.CONSTRAINED:
                        events.append(SimulationEvent(
                            simulation_run_id=run.id,
                            simulation_time_min=simulation_time_min,
                            tick_index=tick_index,
                            event_type=SimulationEventTypeEnum.RESOURCE_WARNING,
                            entity_type="DestinationResource",
                            entity_id=water_res.id,
                            details={
                                "destination_code": d.code,
                                "resource_category": "WATER",
                                "status": ResourceStatusEnum.CONSTRAINED.value,
                                "remaining_quantity": round(water_res.remaining_quantity, 2),
                                "supportable_population": water_supportable
                            }
                        ))
                    elif water_res.status == ResourceStatusEnum.EXHAUSTED:
                        events.append(SimulationEvent(
                            simulation_run_id=run.id,
                            simulation_time_min=simulation_time_min,
                            tick_index=tick_index,
                            event_type=SimulationEventTypeEnum.RESOURCE_EXHAUSTED,
                            entity_type="DestinationResource",
                            entity_id=water_res.id,
                            details={
                                "destination_code": d.code,
                                "resource_category": "WATER",
                                "status": ResourceStatusEnum.EXHAUSTED.value,
                                "remaining_quantity": 0.0
                            }
                        ))

            # ---------------------------------------------------------
            # B. Process POPULATION_SPACE (Physical Shelter)
            # ---------------------------------------------------------
            shelter_res = next((s for s in dest_states if s.resource_category == "POPULATION_SPACE"), None)
            shelter_supportable = int(shelter_res.total_quantity) if shelter_res else 100
            if shelter_res:
                shelter_res.consumed_quantity = float(sheltered_population)
                shelter_res.remaining_quantity = max(0.0, shelter_res.total_quantity - float(sheltered_population))
                prev_status = shelter_res.status
                if shelter_res.remaining_quantity <= 0.0:
                    shelter_res.status = ResourceStatusEnum.EXHAUSTED
                elif shelter_res.remaining_quantity <= (shelter_res.total_quantity * warning_threshold_ratio):
                    shelter_res.status = ResourceStatusEnum.CONSTRAINED
                else:
                    shelter_res.status = ResourceStatusEnum.NORMAL

            # ---------------------------------------------------------
            # C. Process MEDICAL_CAPACITY (Healthcare Support)
            # ---------------------------------------------------------
            med_res = next((s for s in dest_states if s.resource_category == "MEDICAL_CAPACITY"), None)
            med_supportable = int(med_res.supportable_population) if med_res else 100
            if med_res:
                # Calculate committed medical demand from sheltered groups
                med_demand = 0.0
                for a in arrived_sheltered:
                    rg = group_map.get(a.group_id)
                    rate = medical_demand_rate_special if (rg and rg.requires_special_transit) else medical_demand_rate_general
                    med_demand += a.assigned_capacity_count * rate

                med_res.consumed_quantity = round(min(float(med_res.supportable_population), med_demand), 2)
                med_res.remaining_quantity = round(max(0.0, float(med_res.supportable_population) - med_demand), 2)
                prev_status = med_res.status
                if med_res.remaining_quantity <= 0.0:
                    med_res.status = ResourceStatusEnum.EXHAUSTED
                elif med_res.remaining_quantity <= (float(med_res.supportable_population) * warning_threshold_ratio):
                    med_res.status = ResourceStatusEnum.CONSTRAINED
                else:
                    med_res.status = ResourceStatusEnum.NORMAL

            # ---------------------------------------------------------
            # D. Dynamic Bottleneck & Effective Capacity Calculation
            # ---------------------------------------------------------
            physical_cap = shelter_supportable
            water_cap = water_supportable if water_res else physical_cap
            medical_cap = med_supportable

            # Core Invariant: effective_capacity = min(physical, water, medical)
            effective_cap = min(physical_cap, water_cap, medical_cap)
            # Invariant: cannot exceed physical capacity
            effective_cap = min(effective_cap, physical_cap)
            effective_cap = max(0, effective_cap)

            # Determine bottleneck resource
            if effective_cap == water_cap and water_cap < physical_cap:
                bottleneck = "WATER"
            elif effective_cap == medical_cap and medical_cap < physical_cap:
                bottleneck = "HEALTHCARE"
            else:
                bottleneck = "SHELTER"

            # Invariant: remaining capacity cannot become negative
            effective_remaining = max(0, effective_cap - sheltered_population)

            # Update snapshot CapacityState
            if cap_st:
                cap_st.effective_capacity = effective_cap
                cap_st.occupied_capacity = sheltered_population
                cap_st.remaining_capacity = effective_remaining
                cap_st.bottleneck_resource = bottleneck

                # Event: DESTINATION_CAPACITY_CHANGED
                if prev_effective_cap != effective_cap:
                    events.append(SimulationEvent(
                        simulation_run_id=run.id,
                        simulation_time_min=simulation_time_min,
                        tick_index=tick_index,
                        event_type=SimulationEventTypeEnum.DESTINATION_CAPACITY_CHANGED,
                        entity_type="CapacityState",
                        entity_id=cap_st.id,
                        details={
                            "destination_code": d.code,
                            "previous_effective_capacity": prev_effective_cap,
                            "new_effective_capacity": effective_cap,
                            "effective_remaining_capacity": effective_remaining,
                            "bottleneck_resource": bottleneck
                        }
                    ))

            # ---------------------------------------------------------
            # E. Destination Feasibility & Infeasibility Detection
            # ---------------------------------------------------------
            is_safe = cap_st.is_safe if cap_st else (d.operational_status == OperationalStatusEnum.OPEN)
            is_feasible = is_safe and (effective_remaining >= uncommitted_demand)

            if not is_feasible and uncommitted_demand > 0:
                infeasible_dest_ids.append(d.id)
                events.append(SimulationEvent(
                    simulation_run_id=run.id,
                    simulation_time_min=simulation_time_min,
                    tick_index=tick_index,
                    event_type=SimulationEventTypeEnum.DESTINATION_INFEASIBLE,
                    entity_type="Destination",
                    entity_id=d.id,
                    details={
                        "destination_code": d.code,
                        "effective_remaining_capacity": effective_remaining,
                        "uncommitted_planned_demand": uncommitted_demand,
                        "deficit": max(0, uncommitted_demand - effective_remaining),
                        "reason": "Exhausted/insufficient remaining capacity for uncommitted planned groups"
                    }
                ))

                # Identify uncommitted allocations that exceed remaining capacity
                # Invariant: Existing ARRIVED and SHELTERED groups are NEVER evicted!
                if not is_safe or effective_remaining == 0:
                    candidate_reallocations.extend(uncommitted_allocs)
                else:
                    excess = uncommitted_demand - effective_remaining
                    collected = 0
                    for a in uncommitted_allocs:
                        if collected < excess:
                            candidate_reallocations.append(a)
                            collected += a.assigned_capacity_count


            destination_summaries.append({
                "destination_id": d.id,
                "destination_code": d.code,
                "destination_name": d.name,
                "is_safe": is_safe,
                "is_feasible": is_feasible,
                "effective_capacity": effective_cap,
                "occupied_population": sheltered_population,
                "effective_remaining_capacity": effective_remaining,
                "uncommitted_planned_demand": uncommitted_demand,
                "bottleneck_resource": bottleneck
            })

        db.flush()

        return {
            "events": events,
            "infeasible_dest_ids": infeasible_dest_ids,
            "candidate_reallocations": candidate_reallocations,
            "destination_summaries": destination_summaries
        }
