import pytest
from shapely.geometry import Point, Polygon
from app.engines.e1_hazard.service import HazardEngineE1
from app.engines.e2_people_priority.service import PeoplePriorityEngineE2
from app.engines.e3_destination_capacity.service import DestinationCapacityEngineE3
from app.engines.e4_route_relocation.service import RouteAndRelocationEngineE4
from app.models.entities import (
    Habitation, Household, Destination, DestinationResource, CapacityState,
    RelocationGroup, RoutePlan
)
from app.models.enums import ResourceCategoryEnum, PriorityClassEnum, OperationalStatusEnum
from app.gis.spatial import to_geojson_str

def test_e1_hazard_expansion_determinism():
    """Verify E1 expansion factor is deterministic, clamped, and monotonically responsive."""
    e1 = HazardEngineE1(reference_change_m=2.0, max_expansion_factor=2.5)

    exp_baseline = e1.compute_expansion_factor(
        rainfall_multiplier_delta=0.0,
        river_level_current=10.0,
        river_level_baseline=10.0,
        valid_persistent_obs_count=5
    )
    assert exp_baseline == 1.10 # 1.0 + 0 + 0 + 0.10*1.0

    exp_monsoon = e1.compute_expansion_factor(
        rainfall_multiplier_delta=0.20,
        river_level_current=10.50, # delta = 0.50 -> 0.50/2.0 = 0.25 -> 0.30*0.25 = 0.075
        river_level_baseline=10.0,
        valid_persistent_obs_count=5
    )
    assert exp_monsoon > exp_baseline
    assert exp_monsoon <= 2.5

def test_e2_priority_monotonicity():
    """
    Mandatory invariant: Holding all other inputs constant,
    increasing current or future exposure must not decrease priority.
    """
    e2 = PeoplePriorityEngineE2()
    hab = Habitation(
        id="HAB_TEST",
        code="H_TEST",
        name="Test Village",
        settlement_type="LOWLAND",
        population_estimate=50,
        geom=to_geojson_str(Polygon([(0,0), (1,0), (1,1), (0,1), (0,0)])),
        centroid_geom=to_geojson_str(Point(0.5, 0.5)),
        elevation_m=10.0
    )
    hh = Household(
        id="HH_TEST",
        habitation_id=hab.id,
        anonymized_code="HH_01",
        member_count=4,
        vulnerable_elderly=1,
        vulnerable_children=1,
        mobility_impaired=1,
        assistance_required=True,
        has_partial_data=False
    )
    vuln = e2.evaluate_household_vulnerability(hh, snapshot_id="SNAP_TEST")

    # Low exposure
    exp_low = e2.evaluate_habitation_exposure(
        hab,
        current_hazard_geom=Polygon([(10,10), (11,10), (11,11), (10,11), (10,10)]),
        predicted_hazard_geom=Polygon([(10,10), (11,10), (11,11), (10,11), (10,10)]),
        snapshot_id="SNAP_TEST"
    )
    prio_low = e2.compute_priority(hab, hh, exp_low, vuln, snapshot_id="SNAP_TEST")

    # High exposure (direct inundation)
    exp_high = e2.evaluate_habitation_exposure(
        hab,
        current_hazard_geom=Polygon([(0,0), (2,0), (2,2), (0,2), (0,0)]),
        predicted_hazard_geom=Polygon([(0,0), (2,0), (2,2), (0,2), (0,0)]),
        snapshot_id="SNAP_TEST"
    )
    prio_high = e2.compute_priority(hab, hh, exp_high, vuln, snapshot_id="SNAP_TEST")

    # Invariant assertion
    assert prio_high.priority_score >= prio_low.priority_score
    assert prio_high.priority_class == PriorityClassEnum.IMMEDIATE

def test_e3_dynamic_bottleneck_capacity():
    """Verify effective capacity strictly equals the minimum critical resource supportable population."""
    e3 = DestinationCapacityEngineE3()
    dest = Destination(
        id="DEST_TEST",
        study_area_id="SA_TEST",
        code="D_TEST",
        name="Test School",
        facility_type="SCHOOL",
        location_geom=to_geojson_str(Point(5.0, 5.0)),
        operational_status=OperationalStatusEnum.OPEN,
        suitability_score=90.0
    )
    resources = [
        DestinationResource(
            id="R1", destination_id=dest.id, snapshot_id="SNAP_TEST",
            resource_type=ResourceCategoryEnum.SHELTER, quantity=150, unit="BEDS",
            supportable_population=150, is_critical=True
        ),
        DestinationResource(
            id="R2", destination_id=dest.id, snapshot_id="SNAP_TEST",
            resource_type=ResourceCategoryEnum.WATER, quantity=600, unit="LITERS",
            supportable_population=40, is_critical=True # BOTTLENECK!
        ),
        DestinationResource(
            id="R3", destination_id=dest.id, snapshot_id="SNAP_TEST",
            resource_type=ResourceCategoryEnum.FOOD, quantity=200, unit="RATIONS",
            supportable_population=100, is_critical=True
        )
    ]

    safe_flood = Polygon([(0,0), (1,0), (1,1), (0,1), (0,0)])
    dest_up, cap_state = e3.evaluate_destination_safety_and_capacity(
        dest, resources, safe_flood, safe_flood, snapshot_id="SNAP_TEST", occupied_capacity=10
    )

    assert cap_state.effective_capacity == 40
    assert cap_state.remaining_capacity == 30
    assert cap_state.bottleneck_resource == "WATER"
    assert cap_state.is_safe == True

def test_e4_cpsat_solver_respects_capacity_and_unmet_demand():
    """Verify CP-SAT allocator never exceeds capacity and outputs explicit UNMET demand."""
    e4 = RouteAndRelocationEngineE4()

    dest = Destination(
        id="D1", study_area_id="SA1", code="D1", name="Shelter 1",
        facility_type="CENTER", location_geom=to_geojson_str(Point(1,1)),
        operational_status=OperationalStatusEnum.OPEN, suitability_score=90.0
    )
    caps = {
        "D1": CapacityState(
            id="C1", destination_id="D1", snapshot_id="SNAP1",
            effective_capacity=10, occupied_capacity=0, remaining_capacity=10, # Only 10 seats
            bottleneck_resource="SHELTER", is_safe=True
        )
    }
    # 3 groups of size 5 = 15 total demand > 10 capacity!
    groups = [
        RelocationGroup(id="G1", habitation_id="H1", household_id="HH1", snapshot_id="SNAP1", group_size=5, priority_score=95.0, priority_class=PriorityClassEnum.IMMEDIATE),
        RelocationGroup(id="G2", habitation_id="H1", household_id="HH2", snapshot_id="SNAP1", group_size=5, priority_score=80.0, priority_class=PriorityClassEnum.IMMEDIATE),
        RelocationGroup(id="G3", habitation_id="H1", household_id="HH3", snapshot_id="SNAP1", group_size=5, priority_score=40.0, priority_class=PriorityClassEnum.MEDIUM_TERM)
    ]
    route = RoutePlan(
        id="R1", origin_habitation_id="H1", destination_id="D1", snapshot_id="SNAP1",
        total_distance_m=1000, total_time_min=10, route_cost=0.2,
        geom=to_geojson_str(Point(0,0)), path_nodes=["N1", "N2"], is_viable=True
    )
    candidate_routes = {("H1", "D1"): route}

    allocations = e4.optimize_relocation(groups, [dest], caps, candidate_routes, snapshot_id="SNAP1")

    # Invariant assertions:
    # 1. Total assigned people <= remaining capacity (10)
    assigned_count = sum(a.assigned_capacity_count for a in allocations if a.destination_id == "D1")
    assert assigned_count <= 10

    # 2. Exactly one group must be left unmet
    unmet = [a for a in allocations if a.destination_id is None]
    assert len(unmet) == 1
    assert unmet[0].reason_code == "NO_VIABLE_ROUTE_OR_EXHAUSTED_CAPACITY"

    # 3. High priority groups (G1 and G2) should be prioritized over lowest priority group (G3)
    g3_alloc = next(a for a in allocations if a.group_id == "G3")
    assert g3_alloc.destination_id is None
