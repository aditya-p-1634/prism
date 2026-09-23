import json
from typing import Dict, Any, List
from shapely.geometry import Polygon, Point, LineString
from app.gis.spatial import to_geojson_str

def get_vayu_basin_fixtures() -> Dict[str, Any]:
    """
    Generate deterministic synthetic fixtures for the canonical Vayu River Basin world.
    Centered at approx 77.20 E, 28.60 N (scale ~ 15km x 10km).
    """
    # 1. Study Area Polygon
    study_area_poly = Polygon([
        (77.10, 28.50),
        (77.30, 28.50),
        (77.30, 28.70),
        (77.10, 28.70),
        (77.10, 28.50)
    ])

    # 2. Base Flood Polygons (Meandering River Inundation Corridor)
    base_flood_poly = Polygon([
        (77.14, 28.55),
        (77.18, 28.59),
        (77.21, 28.62),
        (77.23, 28.67),
        (77.21, 28.67),
        (77.19, 28.63),
        (77.16, 28.60),
        (77.12, 28.56),
        (77.14, 28.55)
    ])

    # 3. Habitations
    # HAB_01: Riverside Lowlands (Directly along riverbank, highly vulnerable)
    hab1_poly = Polygon([(77.170, 28.590), (77.185, 28.590), (77.185, 28.600), (77.170, 28.600), (77.170, 28.590)])
    # HAB_02: Terrace Settlement (Slightly elevated, exposed under monsoon surge)
    hab2_poly = Polygon([(77.195, 28.610), (77.210, 28.610), (77.210, 28.620), (77.195, 28.620), (77.195, 28.610)])
    # HAB_03: Plateau Village (High ground across the river, accessed by Bridge 01)
    hab3_poly = Polygon([(77.150, 28.640), (77.165, 28.640), (77.165, 28.650), (77.150, 28.650), (77.150, 28.640)])
    # HAB_04: Hillside Edge (Safe high elevation zone)
    hab4_poly = Polygon([(77.240, 28.560), (77.255, 28.560), (77.255, 28.570), (77.240, 28.570), (77.240, 28.560)])

    habitations_data = [
        {
            "code": "HAB_01",
            "name": "Riverside Lowlands",
            "settlement_type": "LOWLAND_RIVERSIDE",
            "population_estimate": 110,
            "geom": to_geojson_str(hab1_poly),
            "centroid": to_geojson_str(hab1_poly.centroid),
            "elevation_m": 8.0,
            "household_count": 8
        },
        {
            "code": "HAB_02",
            "name": "Terrace Settlement",
            "settlement_type": "AGRICULTURAL_TERRACE",
            "population_estimate": 85,
            "geom": to_geojson_str(hab2_poly),
            "centroid": to_geojson_str(hab2_poly.centroid),
            "elevation_m": 14.0,
            "household_count": 8
        },
        {
            "code": "HAB_03",
            "name": "Plateau Village",
            "settlement_type": "PLATEAU_SETTLEMENT",
            "population_estimate": 70,
            "geom": to_geojson_str(hab3_poly),
            "centroid": to_geojson_str(hab3_poly.centroid),
            "elevation_m": 22.0,
            "household_count": 6
        },
        {
            "code": "HAB_04",
            "name": "Hillside Edge",
            "settlement_type": "ELEVATED_FOOTHILLS",
            "population_estimate": 45,
            "geom": to_geojson_str(hab4_poly),
            "centroid": to_geojson_str(hab4_poly.centroid),
            "elevation_m": 35.0,
            "household_count": 6
        }
    ]

    # 4. Destinations
    destinations_data = [
        {
            "code": "DEST_01",
            "name": "Vayu Community Center",
            "facility_type": "COMMUNITY_SHELTER",
            "location": to_geojson_str(Point(77.160, 28.665)),
            "resources": [
                {"type": "SHELTER", "qty": 160, "unit": "BEDS", "supportable": 160},
                {"type": "WATER", "qty": 3000, "unit": "LITERS", "supportable": 150},
                {"type": "FOOD", "qty": 500, "unit": "RATIONS", "supportable": 170},
                {"type": "HEALTHCARE", "qty": 4, "unit": "MEDICS", "supportable": 200},
                {"type": "SANITATION", "qty": 12, "unit": "TOILETS", "supportable": 150}
            ]
        },
        {
            "code": "DEST_02",
            "name": "District Senior Secondary School",
            "facility_type": "GOVERNMENT_SCHOOL",
            "location": to_geojson_str(Point(77.225, 28.625)),
            "resources": [
                {"type": "SHELTER", "qty": 120, "unit": "BEDS", "supportable": 120},
                {"type": "WATER", "qty": 1200, "unit": "LITERS", "supportable": 60}, # BOTTLENECK!
                {"type": "FOOD", "qty": 350, "unit": "RATIONS", "supportable": 110},
                {"type": "HEALTHCARE", "qty": 2, "unit": "MEDICS", "supportable": 100},
                {"type": "SANITATION", "qty": 8, "unit": "TOILETS", "supportable": 100}
            ]
        },
        {
            "code": "DEST_03",
            "name": "Hilltop Sports Complex",
            "facility_type": "SPORTS_FACILITY",
            "location": to_geojson_str(Point(77.250, 28.580)),
            "resources": [
                {"type": "SHELTER", "qty": 70, "unit": "BEDS", "supportable": 70},
                {"type": "WATER", "qty": 1600, "unit": "LITERS", "supportable": 80},
                {"type": "FOOD", "qty": 250, "unit": "RATIONS", "supportable": 80},
                {"type": "HEALTHCARE", "qty": 1, "unit": "MEDICS", "supportable": 50},
                {"type": "SANITATION", "qty": 6, "unit": "TOILETS", "supportable": 75}
            ]
        }
    ]

    # 5. Road Network Nodes & Segments
    # Connected graph connecting Habitations to Destinations across the river with BRIDGE_01
    nodes_data = [
        {"code": "N_HAB1", "pt": Point(77.178, 28.595), "elev": 9.0},
        {"code": "N_HAB2", "pt": Point(77.202, 28.615), "elev": 15.0},
        {"code": "N_HAB3", "pt": Point(77.158, 28.645), "elev": 23.0},
        {"code": "N_HAB4", "pt": Point(77.248, 28.565), "elev": 36.0},

        {"code": "N_DEST1", "pt": Point(77.160, 28.665), "elev": 25.0},
        {"code": "N_DEST2", "pt": Point(77.225, 28.625), "elev": 18.0},
        {"code": "N_DEST3", "pt": Point(77.250, 28.580), "elev": 30.0},

        {"code": "N_JUNC_SOUTH", "pt": Point(77.190, 28.580), "elev": 12.0},
        {"code": "N_BRIDGE_SOUTH", "pt": Point(77.185, 28.610), "elev": 11.0},
        {"code": "N_BRIDGE_NORTH", "pt": Point(77.175, 28.625), "elev": 16.0},
        {"code": "N_JUNC_NORTH", "pt": Point(77.170, 28.640), "elev": 20.0},

        {"code": "N_BYPASS_EAST_1", "pt": Point(77.220, 28.580), "elev": 22.0},
        {"code": "N_BYPASS_EAST_2", "pt": Point(77.235, 28.605), "elev": 24.0},
        {"code": "N_BYPASS_NORTH", "pt": Point(77.210, 28.650), "elev": 28.0},
        {"code": "N_WEST_CORRIDOR", "pt": Point(77.140, 28.620), "elev": 20.0}
    ]

    segments_data = [
        # HAB1 connects to Junction South & Bridge South
        ("SEG_H1_JUNC", "N_HAB1", "N_JUNC_SOUTH", 1800, 45, False),
        ("SEG_H1_BRS", "N_HAB1", "N_BRIDGE_SOUTH", 1600, 40, False),

        # HAB2 connects to Bridge South & Junction East
        ("SEG_H2_BRS", "N_HAB2", "N_BRIDGE_SOUTH", 2100, 45, False),
        ("SEG_H2_BYP2", "N_HAB2", "N_BYPASS_EAST_2", 2400, 50, False),
        ("SEG_H2_DEST2", "N_HAB2", "N_DEST2", 1500, 40, False),

        # Strategic Bridge: Bridge 01 across the flood channel
        ("BRIDGE_01", "N_BRIDGE_SOUTH", "N_BRIDGE_NORTH", 1200, 35, True),

        # North Corridor: Bridge North to Junc North and DEST1
        ("SEG_BRN_JN", "N_BRIDGE_NORTH", "N_JUNC_NORTH", 1500, 50, False),
        ("SEG_JN_D1", "N_JUNC_NORTH", "N_DEST1", 1700, 50, False),
        ("SEG_JN_H3", "N_JUNC_NORTH", "N_HAB3", 1100, 40, False),
        ("SEG_H3_D1", "N_HAB3", "N_DEST1", 1900, 45, False),

        # HAB4 connects to DEST3 and Bypass East
        ("SEG_H4_D3", "N_HAB4", "N_DEST3", 1400, 40, False),
        ("SEG_H4_JUNC", "N_HAB4", "N_JUNC_SOUTH", 4500, 55, False),
        ("SEG_D3_BYP1", "N_DEST3", "N_BYPASS_EAST_1", 2300, 45, False),

        # Alternative High Ground Bypass Corridor (remains open during monsoon surge)
        ("SEG_BYP1_BYP2", "N_BYPASS_EAST_1", "N_BYPASS_EAST_2", 2800, 60, False),
        ("SEG_BYP2_DEST2", "N_BYPASS_EAST_2", "N_DEST2", 2200, 50, False),
        ("SEG_DEST2_BYPN", "N_DEST2", "N_BYPASS_NORTH", 3100, 55, False),
        ("SEG_BYPN_D1", "N_BYPASS_NORTH", "N_DEST1", 4200, 60, False),

        # West Corridor link
        ("SEG_BRN_WEST", "N_BRIDGE_NORTH", "N_WEST_CORRIDOR", 3200, 45, False),
        ("SEG_WEST_H3", "N_WEST_CORRIDOR", "N_HAB3", 2600, 45, False)
    ]

    return {
        "study_area": {
            "code": "STUDY_VAYU_01",
            "name": "Vayu River Basin",
            "boundary": to_geojson_str(study_area_poly)
        },
        "base_flood": to_geojson_str(base_flood_poly),
        "habitations": habitations_data,
        "destinations": destinations_data,
        "nodes": nodes_data,
        "segments": segments_data
    }
