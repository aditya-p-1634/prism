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

    # 2. Base Flood Polygons (Meandering River Channel Corridor)
    river_line = LineString([
        (77.135, 28.530),
        (77.155, 28.565),
        (77.168, 28.595),
        (77.178, 28.618),
        (77.180, 28.645),
        (77.185, 28.675),
        (77.190, 28.700)
    ])
    # Baseline river channel: buffer 180m
    base_flood_poly = river_line.buffer(0.0016)

    # 3. Habitations
    # HAB_01: Riverside Lowlands (Directly along riverbank, highly vulnerable)
    hab1_poly = Polygon([(77.166, 28.590), (77.173, 28.590), (77.173, 28.600), (77.166, 28.600), (77.166, 28.590)])
    # HAB_02: Terrace Settlement (Slightly elevated, dry at baseline, exposed under monsoon surge)
    hab2_poly = Polygon([(77.177, 28.604), (77.182, 28.604), (77.182, 28.610), (77.177, 28.610), (77.177, 28.604)])
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
        {"code": "N_HAB1", "pt": Point(77.170, 28.595), "elev": 8.0},
        {"code": "N_HAB2", "pt": Point(77.184, 28.606), "elev": 14.0},
        {"code": "N_HAB3", "pt": Point(77.158, 28.645), "elev": 23.0},
        {"code": "N_HAB4", "pt": Point(77.248, 28.565), "elev": 36.0},

        {"code": "N_DEST1", "pt": Point(77.160, 28.665), "elev": 25.0},
        {"code": "N_DEST2", "pt": Point(77.225, 28.625), "elev": 18.0},
        {"code": "N_DEST3", "pt": Point(77.250, 28.580), "elev": 30.0},

        {"code": "N_JUNC_SOUTH", "pt": Point(77.195, 28.580), "elev": 12.0},
        {"code": "N_BRIDGE_SOUTH", "pt": Point(77.182, 28.612), "elev": 11.0},
        {"code": "N_BRIDGE_NORTH", "pt": Point(77.174, 28.625), "elev": 16.0},
        {"code": "N_JUNC_NORTH", "pt": Point(77.170, 28.640), "elev": 20.0},

        {"code": "N_BYPASS_EAST_1", "pt": Point(77.220, 28.580), "elev": 22.0},
        {"code": "N_BYPASS_EAST_2", "pt": Point(77.235, 28.605), "elev": 24.0},
        {"code": "N_BYPASS_NORTH", "pt": Point(77.210, 28.650), "elev": 28.0},
        {"code": "N_WEST_CORRIDOR", "pt": Point(77.140, 28.620), "elev": 20.0}
    ]

    segments_data = [
        # HAB1 connects to Junction South & Bridge South
        ("SEG_H1_JUNC", "N_HAB1", "N_JUNC_SOUTH", 1800, 45, False),
        ("SEG_H1_BRS", "N_HAB1", "N_BRIDGE_SOUTH", 1400, 40, False),

        # HAB2 connects to Bridge South & Junction East
        ("SEG_H2_BRS", "N_HAB2", "N_BRIDGE_SOUTH", 800, 45, False),
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
            "name": "Vayu River Basin — Synthetic Demonstration Study Area",
            "boundary": to_geojson_str(study_area_poly)
        },
        "base_flood": to_geojson_str(base_flood_poly),
        "habitations": habitations_data,
        "destinations": destinations_data,
        "nodes": nodes_data,
        "segments": segments_data
    }


def get_vayu_hydrometric_time_series(
    hours: float = 72.0,
    interval_minutes: float = 10.0,
    base_river_stage_m: float = 10.00
) -> List[Dict[str, Any]]:
    """
    Generates a deterministic synthetic catchment hydrograph and rainfall time-series
    for the Vayu River Basin (CWC_GAUGE_01 and IMD_RAIN_01).

    Chronological Structure (72 hours @ 10-minute intervals = 432 steps):
    - Hours 0.0 to 18.0 (Steps 0 - 108): Baseline pre-monsoon dry conditions (~10.0m stage, 0-2 mm/hr rain).
    - Hours 18.0 to 36.0 (Steps 109 - 216): Severe convective precipitation burst (peaking at ~45 mm/hr at h=24).
      Catchment rainfall-runoff causes a steady surge on the rising limb.
    - Hours 36.0 to 48.0 (Steps 217 - 288): Peak flood stage cresting at ~11.55m (crossing alert stage 10.30m).
    - Hours 48.0 to 72.0 (Steps 289 - 431): Storm departs; exponential hydrograph drainage on the recession limb.

    Chronological Splitting (Time-series leakage prevention):
    - Steps 0 to 259 (60%): TRAINING window (earlier observations)
    - Steps 260 to 345 (20%): VALIDATION window (middle observations)
    - Steps 346 to 431 (20%): TEST window (latest observations)

    Explicitly labeled: DEMO / PROTOTYPE SYNTHETIC DATASET.
    """
    import math

    total_steps = int(hours * 60.0 / interval_minutes)
    records: List[Dict[str, Any]] = []

    for i in range(total_steps):
        t_min = i * interval_minutes
        h = t_min / 60.0

        # 1. Deterministic Rainfall (mm/hr)
        if h < 16.0:
            rain = round(1.2 * (math.sin(h * 0.3) ** 2), 2)
        elif 16.0 <= h < 34.0:
            # Gaussian storm hyetograph centered at h=24.0
            burst = 45.0 * math.exp(-((h - 24.0) ** 2) / (2.0 * (3.2 ** 2)))
            rain = round(burst + 1.5 * (math.sin(i * 0.4) ** 2), 2)
        else:
            rain = 0.0

        # 2. Deterministic River Stage (meters at CWC_GAUGE_01)
        if h < 30.0:
            # Rising limb: S-curve sigmoid growth towards peak
            surge = 1.55 / (1.0 + math.exp(-(h - 24.0) / 2.8))
        else:
            # Receding limb: Exponential catchment drainage
            surge = 1.55 * math.exp(-(h - 30.0) / 16.0)

        # Micro-variations emulating sensor telemetry precision
        noise = 0.008 * math.sin(i * 0.5)
        river_stage = round(base_river_stage_m + surge + noise, 3)

        records.append({
            "step_index": i,
            "simulation_time_min": t_min,
            "elapsed_hours": round(h, 2),
            "river_stage_m": river_stage,
            "rainfall_rate_mmh": rain,
            "rainfall_multiplier_delta": round(rain / 50.0, 3),
            "gauge_code": "CWC_GAUGE_01",
            "station_code": "IMD_RAIN_01",
            "split_assignment": "TRAIN" if i < 260 else ("VAL" if i < 346 else "TEST")
        })

    return records

