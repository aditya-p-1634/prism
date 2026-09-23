import sys
import os

# Add apps/api to python path
current_dir = os.path.dirname(os.path.abspath(__file__))
api_dir = os.path.join(os.path.dirname(current_dir), "apps", "api")
if api_dir not in sys.path:
    sys.path.insert(0, api_dir)

from shapely.geometry import LineString
from app.db.session import SessionLocal, engine, Base
from app.core.security import hash_password
from app.models.entities import (
    User, StudyArea, Habitation, Household, Destination, DestinationResource,
    RoadNode, RoadSegment, Scenario, StateSnapshot, RelocationGroup, RelocationAllocation
)
from app.models.enums import RoleEnum, OperationalStatusEnum, ResourceCategoryEnum
from app.seed.synthetic_data import get_vayu_basin_fixtures
from app.engines.e1_hazard.service import HazardEngineE1
from app.engines.e2_people_priority.service import PeoplePriorityEngineE2
from app.engines.e3_destination_capacity.service import DestinationCapacityEngineE3
from app.engines.e4_route_relocation.service import RouteAndRelocationEngineE4
from app.engines.e6_integration.service import IntegrationBackboneE6
from app.gis.spatial import to_shapely, to_geojson_str

def seed_demo():
    print("=" * 60)
    print("PRISM: SEEDING CANONICAL VAYU RIVER BASIN DEMO WORLD")
    print("=" * 60)

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # Check if already seeded
        existing_area = db.query(StudyArea).filter(StudyArea.code == "STUDY_VAYU_01").first()
        if existing_area:
            print("Database already contains STUDY_VAYU_01. Cleaning before re-seeding...")
            Base.metadata.drop_all(bind=engine)
            Base.metadata.create_all(bind=engine)

        fixtures = get_vayu_basin_fixtures()
        e6 = IntegrationBackboneE6(db)

        # 1. Seed Users
        print("\n1. Seeding Demo Accounts (Admin, Authority, Operator, Viewer)...")
        users_data = [
            ("authority@prism.gov.in", "authority123", "Col. Rajesh Verma", RoleEnum.AUTHORITY),
            ("admin@prism.gov.in", "admin123", "Aditya Sharma (Lead Engineer)", RoleEnum.ADMIN),
            ("operator@prism.gov.in", "operator123", "Pooja Patel (GIS Field Lead)", RoleEnum.DATA_OPERATOR),
            ("viewer@prism.gov.in", "viewer123", "Observer / Jury Member", RoleEnum.VIEWER)
        ]
        for email, pwd, name, role in users_data:
            user = User(
                email=email,
                hashed_password=hash_password(pwd),
                full_name=name,
                role=role,
                is_active=True
            )
            db.add(user)
        db.flush()

        # 2. Seed Study Area
        print("2. Seeding Study Area: Vayu River Basin...")
        sa_data = fixtures["study_area"]
        study_area = StudyArea(
            code=sa_data["code"],
            name=sa_data["name"],
            boundary_geom=sa_data["boundary"],
            crs_code="EPSG:4326",
            computational_crs="EPSG:32643",
            timezone="Asia/Kolkata"
        )
        db.add(study_area)
        db.flush()

        # 3. Create Baseline Snapshot (SNAP_BASE_001)
        print("3. Initializing Baseline Snapshot: SNAP_BASE_001...")
        baseline_snapshot = StateSnapshot(
            id="SNAP_BASE_001",
            snapshot_type="BASELINE",
            label="Canonical Baseline Reality (Pre-Monsoon Flood)",
            is_immutable=True
        )
        db.add(baseline_snapshot)
        db.flush()

        # 4. Seed Habitations & Households
        print("4. Seeding Habitations and 28 Diverse Demographic Households...")
        habitations = []
        households = []
        hh_counter = 1

        for h_data in fixtures["habitations"]:
            hab = Habitation(
                study_area_id=study_area.id,
                code=h_data["code"],
                name=h_data["name"],
                settlement_type=h_data["settlement_type"],
                population_estimate=h_data["population_estimate"],
                geom=h_data["geom"],
                centroid_geom=h_data["centroid"],
                elevation_m=h_data["elevation_m"]
            )
            db.add(hab)
            db.flush()
            habitations.append(hab)

            # Generate demographic variations
            for i in range(h_data["household_count"]):
                elderly = 1 if (hh_counter % 3 == 0) else 0
                children = 2 if (hh_counter % 2 == 0) else 0
                mobility = 1 if (hh_counter in (2, 7, 14, 21)) else 0
                assistance = True if (mobility > 0 or elderly > 0 and children > 0) else False
                partial = True if (hh_counter in (5, 12, 19)) else False
                members = 2 + elderly + children

                hh = Household(
                    habitation_id=hab.id,
                    anonymized_code=f"HH_{hh_counter:03d}_{hab.code}",
                    member_count=members,
                    vulnerable_elderly=elderly,
                    vulnerable_children=children,
                    mobility_impaired=mobility,
                    assistance_required=assistance,
                    has_partial_data=partial
                )
                db.add(hh)
                households.append(hh)
                hh_counter += 1

        db.flush()

        # 5. Seed Destinations & Resources
        print("5. Seeding 3 Candidate Destinations with Multi-Resource Profiles...")
        destinations = []
        for d_data in fixtures["destinations"]:
            dest = Destination(
                study_area_id=study_area.id,
                code=d_data["code"],
                name=d_data["name"],
                facility_type=d_data["facility_type"],
                location_geom=d_data["location"],
                operational_status=OperationalStatusEnum.OPEN,
                suitability_score=90.0
            )
            db.add(dest)
            db.flush()
            destinations.append(dest)

            for r in d_data["resources"]:
                d_res = DestinationResource(
                    destination_id=dest.id,
                    snapshot_id=baseline_snapshot.id,
                    resource_type=ResourceCategoryEnum(r["type"]),
                    quantity=r["qty"],
                    unit=r["unit"],
                    supportable_population=r["supportable"],
                    is_critical=True
                )
                db.add(d_res)

        db.flush()

        # 6. Seed Road Network
        print("6. Seeding Road Network (15 Nodes, 18 Segments with BRIDGE_01)...")
        node_map = {}
        road_nodes = []
        for n_data in fixtures["nodes"]:
            node = RoadNode(
                study_area_id=study_area.id,
                node_code=n_data["code"],
                location_geom=to_geojson_str(n_data["pt"]),
                elevation_m=n_data["elev"]
            )
            db.add(node)
            db.flush()
            node_map[n_data["code"]] = node
            road_nodes.append(node)

        road_segments = []
        for seg_code, u_code, v_code, length, speed, is_bridge in fixtures["segments"]:
            u_pt = fixtures["nodes"][[n["code"] for n in fixtures["nodes"]].index(u_code)]["pt"]
            v_pt = fixtures["nodes"][[n["code"] for n in fixtures["nodes"]].index(v_code)]["pt"]
            line = LineString([u_pt, v_pt])

            seg = RoadSegment(
                study_area_id=study_area.id,
                segment_code=seg_code,
                u_node_id=node_map[u_code].id,
                v_node_id=node_map[v_code].id,
                road_class="BRIDGE" if is_bridge else "PRIMARY",
                length_meters=float(length),
                max_speed_kmh=float(speed),
                geom=to_geojson_str(line),
                operational_status=OperationalStatusEnum.OPEN,
                hazard_risk_score=0.05,
                is_bridge=is_bridge
            )
            db.add(seg)
            road_segments.append(seg)

        db.flush()

        # 7. Execute Baseline Causal Pipeline (E1 -> E2 -> E3 -> E4)
        print("7. Executing Baseline Causal Chain (E1 -> E2 -> E3 -> E4)...")
        e1 = HazardEngineE1()
        e2 = PeoplePriorityEngineE2()
        e3 = DestinationCapacityEngineE3()
        e4 = RouteAndRelocationEngineE4()

        # E1: Base Hazard & Prediction
        base_flood_geom = to_shapely(fixtures["base_flood"])
        e1_res = e1.evaluate_hazard_state(
            study_area_id=study_area.id,
            snapshot_id=baseline_snapshot.id,
            base_flood_geom=base_flood_geom,
            rainfall_multiplier_delta=0.0,
            river_level_current=10.0,
            river_level_baseline=10.0
        )
        db.add(e1_res["hazard_state"])
        db.add(e1_res["hazard_prediction"])
        db.add(e1_res["red_zone"])
        db.add(e1_res["evidence"])
        db.flush()

        # E2: Exposure & Priorities
        base_priorities = []
        for hab in habitations:
            exp = e2.evaluate_habitation_exposure(
                hab, e1_res["current_geom"], e1_res["predicted_geom"], baseline_snapshot.id
            )
            db.add(exp)
            hab_hh = [h for h in households if h.habitation_id == hab.id]
            for hh in hab_hh:
                vuln = e2.evaluate_household_vulnerability(hh, baseline_snapshot.id)
                db.add(vuln)
                prio = e2.compute_priority(hab, hh, exp, vuln, baseline_snapshot.id)
                db.add(prio)
                base_priorities.append(prio)
        db.flush()

        # E3: Destination Capacities & Bottlenecks
        base_caps = {}
        for d in destinations:
            res = db.query(DestinationResource).filter(
                DestinationResource.destination_id == d.id,
                DestinationResource.snapshot_id == baseline_snapshot.id
            ).all()
            d_up, cap_state = e3.evaluate_destination_safety_and_capacity(
                d, res, e1_res["current_geom"], e1_res["predicted_geom"], baseline_snapshot.id
            )
            db.add(cap_state)
            base_caps[d.id] = cap_state
        db.flush()

        # E4: Graph, Safe Routes & CP-SAT Allocation
        G, updated_segs = e4.build_network_graph(
            road_nodes, road_segments, e1_res["current_geom"], e1_res["predicted_geom"]
        )
        candidate_routes = {}
        for hab in habitations:
            for d in destinations:
                r_plan = e4.find_safe_route(G, hab, d, road_nodes, baseline_snapshot.id)
                if r_plan:
                    db.add(r_plan)
                    candidate_routes[(hab.id, d.id)] = r_plan
        db.flush()

        groups = []
        for p in base_priorities:
            hh = next(h for h in households if h.id == p.household_id)
            rg = RelocationGroup(
                habitation_id=p.habitation_id,
                household_id=p.household_id,
                snapshot_id=baseline_snapshot.id,
                group_size=hh.member_count,
                priority_score=p.priority_score,
                priority_class=p.priority_class,
                requires_special_transit=hh.mobility_impaired > 0
            )
            db.add(rg)
            groups.append(rg)
        db.flush()

        allocations = e4.optimize_relocation(
            groups, destinations, base_caps, candidate_routes, baseline_snapshot.id
        )
        for alloc in allocations:
            db.add(alloc)

        # 8. Register Canonical Scenario (MONSOON_SURGE_01)
        print("8. Registering Canonical Scenario: MONSOON_SURGE_01...")
        scenario = Scenario(
            code="MONSOON_SURGE_01",
            name="Severe Monsoon Flash Flood & Critical Infrastructure Failure",
            description="Compound disaster: 20% precipitation surge, +0.50m river rise, BRIDGE_01 collapse, D2 water capacity degradation.",
            parameters={
                "rainfall_multiplier_delta": 0.20,
                "river_level_delta_m": 0.50,
                "closed_road_segments": ["BRIDGE_01"],
                "resource_capacity_reductions": {
                    "DEST_02": {"WATER": 0.75}
                }
            }
        )
        db.add(scenario)

        db.commit()
        print("\n" + "=" * 60)
        print("SUCCESS! BASELINE WORLD INITIALIZED CLEANLY.")
        print(f"Study Area: {study_area.name} ({study_area.code})")
        print(f"Habitations: {len(habitations)} | Households: {len(households)}")
        print(f"Destinations: {len(destinations)} (D2 Bottleneck: WATER = 60 persons)")
        print(f"Road Network: {len(road_nodes)} nodes, {len(road_segments)} segments")
        print(f"Allocations Computed: {len(allocations)} groups assigned")
        print("Baseline Snapshot: SNAP_BASE_001 (IMMUTABLE)")
        print("=" * 60)

    except Exception as e:
        db.rollback()
        print(f"\nERROR DURING SEEDING: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    seed_demo()
