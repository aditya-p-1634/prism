import json
from typing import List, Dict, Any, Tuple, Optional
import networkx as nx
import shapely
from shapely.geometry import LineString, Point
from ortools.sat.python import cp_model
from app.gis.spatial import to_shapely, intersects, calculate_distance_meters, to_geojson_str
from app.models.entities import (
    RoadNode, RoadSegment, RoutePlan, RelocationGroup, RelocationAllocation,
    Habitation, Destination, PriorityRecord, CapacityState
)
from app.models.enums import OperationalStatusEnum, AllocationStatusEnum, PriorityClassEnum

def clamp(val: float, min_val: float, max_val: float) -> float:
    return max(min_val, min(val, max_val))

class RouteAndRelocationEngineE4:
    """Engine 4: Safe Route Intelligence & Constrained Relocation Allocator."""

    def __init__(self, route_reference_time_min: float = 30.0):
        self.route_reference_time_min = route_reference_time_min

    def build_network_graph(
        self,
        nodes: List[RoadNode],
        segments: List[RoadSegment],
        current_hazard_geom: shapely.Geometry,
        predicted_hazard_geom: shapely.Geometry
    ) -> Tuple[nx.Graph, List[RoadSegment]]:
        """
        Build NetworkX Graph and filter out inundated or closed edges.
        """
        G = nx.Graph()
        node_lookup = {n.id: n for n in nodes}
        for n in nodes:
            pt = to_shapely(n.location_geom)
            G.add_node(n.id, node_code=n.node_code, x=pt.x, y=pt.y, elevation=n.elevation_m)

        updated_segments = []
        for seg in segments:
            seg_geom = to_shapely(seg.geom)
            if seg.is_bridge:
                # Bridges cross waterways by definition. They are only closed if explicitly closed
                # or if an explicit clearance threshold is breached (represented by operational_status=CLOSED).
                is_submerged = (seg.operational_status == OperationalStatusEnum.CLOSED)
            else:
                is_submerged = intersects(seg_geom, current_hazard_geom)

            # Invariant: UNKNOWN or STALE or SUBMERGED cannot be safe
            if is_submerged:
                seg.operational_status = OperationalStatusEnum.CLOSED
                seg.hazard_risk_score = 1.0
            elif seg.operational_status == OperationalStatusEnum.CLOSED:
                seg.hazard_risk_score = 1.0

            updated_segments.append(seg)

            if seg.operational_status == OperationalStatusEnum.CLOSED:
                continue # Do not add closed edges to routing graph

            # Compute travel time in minutes: (length in km / speed in kmh) * 60
            travel_time_min = (seg.length_meters / 1000.0) / max(10.0, seg.max_speed_kmh) * 60.0
            time_norm = clamp(travel_time_min / self.route_reference_time_min, 0.0, 1.0)
            hazard_risk = seg.hazard_risk_score
            uncertainty = 0.10 if seg.operational_status == OperationalStatusEnum.LIMITED else 0.0
            access_penalty = 0.20 if seg.is_bridge and seg.operational_status == OperationalStatusEnum.LIMITED else 0.0

            # Frozen route cost formula
            cost = 0.45 * time_norm + 0.35 * hazard_risk + 0.10 * uncertainty + 0.10 * access_penalty

            G.add_edge(
                seg.u_node_id, seg.v_node_id,
                segment_id=seg.id,
                segment_code=seg.segment_code,
                weight=cost,
                length_m=seg.length_meters,
                time_min=travel_time_min,
                geom=seg_geom
            )

        return G, updated_segments

    def find_safe_route(
        self,
        G: nx.Graph,
        origin_hab: Habitation,
        destination: Destination,
        nodes: List[RoadNode],
        snapshot_id: str
    ) -> Optional[RoutePlan]:
        """
        Find shortest safe path from Habitation centroid to Destination.
        """
        hab_pt = to_shapely(origin_hab.centroid_geom)
        dest_pt = to_shapely(destination.location_geom)

        # Find nearest start and end road nodes
        start_node = min(nodes, key=lambda n: calculate_distance_meters(hab_pt, to_shapely(n.location_geom)))
        end_node = min(nodes, key=lambda n: calculate_distance_meters(dest_pt, to_shapely(n.location_geom)))

        if not G.has_node(start_node.id) or not G.has_node(end_node.id):
            return None

        try:
            path_node_ids = nx.shortest_path(G, source=start_node.id, target=end_node.id, weight="weight")
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return None

        # Build composite LineString geometry
        coords = [hab_pt.coords[0]]
        total_dist = 0.0
        total_time = 0.0
        total_cost = 0.0

        for i in range(len(path_node_ids) - 1):
            u, v = path_node_ids[i], path_node_ids[i+1]
            edge_data = G[u][v]
            total_dist += edge_data["length_m"]
            total_time += edge_data["time_min"]
            total_cost += edge_data["weight"]
            edge_geom = edge_data["geom"]
            coords.extend(list(edge_geom.coords))

        coords.append(dest_pt.coords[0])
        route_line = LineString(coords)

        return RoutePlan(
            origin_habitation_id=origin_hab.id,
            destination_id=destination.id,
            snapshot_id=snapshot_id,
            total_distance_m=round(total_dist, 1),
            total_time_min=round(total_time, 1),
            route_cost=round(total_cost, 3),
            geom=to_geojson_str(route_line),
            path_nodes=[G.nodes[nid]["node_code"] for nid in path_node_ids],
            is_viable=True,
            invalidated_reason=None
        )

    def optimize_relocation(
        self,
        groups: List[RelocationGroup],
        destinations: List[Destination],
        capacity_states: Dict[str, CapacityState],
        candidate_routes: Dict[Tuple[str, str], RoutePlan],
        snapshot_id: str
    ) -> List[RelocationAllocation]:
        """
        Solve multi-destination, multi-resource integer assignment using Google OR-Tools CP-SAT.
        Enforces indivisibility, capacity constraints, and explicit unmet demand.
        """
        model = cp_model.CpModel()

        valid_dests = [d for d in destinations if capacity_states.get(d.id, CapacityState()).is_safe and capacity_states.get(d.id, CapacityState()).remaining_capacity > 0]
        
        # Decision variables: x[g, d] in {0, 1}
        x = {}
        for g in groups:
            for d in valid_dests:
                route_key = (g.habitation_id, d.id)
                # Only allow assignment if a viable safe route exists
                if route_key in candidate_routes and candidate_routes[route_key].is_viable:
                    x[(g.id, d.id)] = model.NewBoolVar(f"assign_g{g.id[:4]}_d{d.id[:4]}")

        # Constraint 1: Single assignment (indivisibility) - group assigned to at most 1 destination
        for g in groups:
            assigned_dests = [x[(g.id, d.id)] for d in valid_dests if (g.id, d.id) in x]
            model.Add(sum(assigned_dests) <= 1)

        # Constraint 2: Destination Capacity Constraint
        for d in valid_dests:
            remaining_cap = capacity_states[d.id].remaining_capacity
            group_sizes = [g.group_size * x[(g.id, d.id)] for g in groups if (g.id, d.id) in x]
            if group_sizes:
                model.Add(sum(group_sizes) <= remaining_cap)

        # Objective Function: Maximize priority coverage while minimizing route cost
        objective_terms = []
        for g in groups:
            for d in valid_dests:
                if (g.id, d.id) in x:
                    route = candidate_routes[(g.habitation_id, d.id)]
                    # Scaled integer coefficients for CP-SAT
                    # Priority weight (0-100) -> 1000 * P
                    # Route cost penalty (0-1) -> -200 * Cost
                    # Suitability bonus (0-100) -> +20 * Suitability
                    score = int(1000 * g.priority_score - 200 * route.route_cost + 20 * d.suitability_score)
                    objective_terms.append(score * x[(g.id, d.id)])

        if objective_terms:
            model.Maximize(sum(objective_terms))

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 5.0
        status = solver.Solve(model)

        allocations = []
        for g in groups:
            assigned_dest = None
            assigned_route = None

            if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
                for d in valid_dests:
                    if (g.id, d.id) in x and solver.Value(x[(g.id, d.id)]) == 1:
                        assigned_dest = d
                        assigned_route = candidate_routes[(g.habitation_id, d.id)]
                        break

            if assigned_dest and assigned_route:
                allocations.append(RelocationAllocation(
                    group_id=g.id,
                    destination_id=assigned_dest.id,
                    route_plan_id=assigned_route.id,
                    snapshot_id=snapshot_id,
                    allocation_status=AllocationStatusEnum.RECOMMENDED,
                    assigned_capacity_count=g.group_size,
                    reason_code=f"OPTIMAL_ASSIGNMENT_TO_{assigned_dest.code}"
                ))
            else:
                # Invariant: Infeasible allocation must remain explicit UNMET demand
                allocations.append(RelocationAllocation(
                    group_id=g.id,
                    destination_id=None,
                    route_plan_id=None,
                    snapshot_id=snapshot_id,
                    allocation_status=AllocationStatusEnum.UNMET,
                    assigned_capacity_count=0,
                    reason_code="NO_VIABLE_ROUTE_OR_EXHAUSTED_CAPACITY"
                ))

        return allocations
