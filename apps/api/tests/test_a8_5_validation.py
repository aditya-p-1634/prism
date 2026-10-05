"""PRISM Phase A.8.5 — Unit Test Suite.

Covers the 20 required validation points:
1. CRS validation
2. Geometry validation
3. NRSC pixelvalue preservation
4. pixelvalue=1 mask
5. pixelvalue=13 mask
6. composite nonzero mask
7. GCC point-in-polygon
8. Inundation-category stratification
9. FABDEM sampling
10. NoData handling
11. Nandambakkam coordinate analysis
12. Distance calculations
13. Road cross-check
14. Stagnation cross-check
15. Area calculated in projected CRS
16. Source files are never modified
17. Deterministic output
18. Provenance manifest generation
19. No IoU emitted without prediction mask
20. Final validation status is evidence-derived
"""

from __future__ import annotations

import os
import tempfile
import pytest
import geopandas as gpd
from shapely.geometry import Point, Polygon

from app.research.a8_5.constants import (
    GCC_CATEGORY_2_TO_3FT,
    GCC_CATEGORY_3_TO_5FT,
    GCC_CATEGORY_ABOVE_5FT,
    GCC_CATEGORY_LESS_2FT,
    MASK_A,
    MASK_B,
    MASK_C,
    METRIC_CRS,
    NANDAMBAKKAM_LAT,
    NANDAMBAKKAM_LON,
    SOURCE_CRS,
    VALIDATION_CONDITIONAL,
    VALIDATION_NOT_READY,
    VALIDATION_READY,
)
from app.research.a8_5.decision import evaluate_validation_readiness
from app.research.a8_5.gcc_analysis import normalize_gcc_category, run_gcc_point_validation
from app.research.a8_5.manifest import build_data_manifest, compute_sha256
from app.research.a8_5.nandambakkam_analysis import run_nandambakkam_analysis
from app.research.a8_5.nrsc_analysis import (
    analyze_nrsc_mask,
    load_and_split_nrsc_masks,
    run_nrsc_class_sensitivity_analysis,
)
from app.research.a8_5.road_analysis import run_road_cross_check
from app.research.a8_5.spatial_qa import prepare_metric_gdf, validate_gdf_spatial_qa
from app.research.a8_5.stagnation_analysis import run_stagnation_cross_check
from app.research.a8_5.terrain_analysis import (
    calculate_distribution_stats,
    run_gcc_terrain_characterization,
    sample_fabdem_at_points,
)

# Relative or absolute path to test datasets
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
DATA_DIR = os.path.join(REPO_ROOT, "data", "research")
FABDEM_PATH = os.path.join(DATA_DIR, "N13E080_FABDEM_V1-2.tif")
NRSC_PATH = os.path.join(DATA_DIR, "7cb3cecf-a95a-4786-8032-9c7417655d24.kml")
GCC_PATH = os.path.join(DATA_DIR, "31523c86-0ad1-42f5-b4d1-297daa4bbcd6.kml")
ROADS_PATH = os.path.join(DATA_DIR, "46d6c279-ae09-43a8-8691-7a5386f69e3a.kml")
STAGNATION_PATH = os.path.join(DATA_DIR, "db3840ff-9f33-43a3-b826-2f9dae1bcb78.kml")


# ==============================================================================
# TEST 1: CRS Validation
# ==============================================================================
def test_01_crs_validation():
    """Verify all vector layers declare EPSG:4326 and spatial QA flags CRS correctly."""
    gdf = gpd.read_file(GCC_PATH)
    qa = validate_gdf_spatial_qa(gdf, "test_gcc", expected_crs=SOURCE_CRS)
    assert qa["has_crs"] is True
    assert qa["crs_compatible"] is True
    assert "4326" in str(qa["crs"])


# ==============================================================================
# TEST 2: Geometry Validation
# ==============================================================================
def test_02_geometry_validation():
    """Verify geometric validity checking detects valid and invalid geometries."""
    # Test on real NRSC dataset
    masks = load_and_split_nrsc_masks(NRSC_PATH)
    raw = masks["RAW_FULL"]
    qa = validate_gdf_spatial_qa(raw, "nrsc_raw")
    assert qa["total_count"] == len(raw)
    assert qa["valid_count"] + qa["invalid_count"] == len(raw)
    assert qa["empty_count"] == 0
    assert qa["null_count"] == 0


# ==============================================================================
# TEST 3: NRSC Pixelvalue Preservation
# ==============================================================================
def test_03_nrsc_pixelvalue_preservation():
    """Verify original pixelvalue field is strictly preserved in raw and mask subsets."""
    masks = load_and_split_nrsc_masks(NRSC_PATH)
    raw = masks["RAW_FULL"]
    assert "pixelvalue" in raw.columns
    # Ensure raw values contain 1, 13, and 0
    unique_vals = set(raw["pixelvalue"].unique())
    assert 1 in unique_vals
    assert 13 in unique_vals
    assert 0 in unique_vals
    assert raw["pixelvalue"].value_counts()[1] == 3392
    assert raw["pixelvalue"].value_counts()[13] == 607


# ==============================================================================
# TEST 4: Pixelvalue=1 Mask (Mask A)
# ==============================================================================
def test_04_pixelvalue_1_mask():
    """Verify NRSC_PIXELVALUE_1 contains only pixelvalue=1 features."""
    masks = load_and_split_nrsc_masks(NRSC_PATH)
    mask_a = masks[MASK_A]
    assert len(mask_a) == 3392
    assert (mask_a["pixelvalue"] == 1).all()
    analysis = analyze_nrsc_mask(mask_a, MASK_A, "pixelvalue == 1")
    assert analysis["feature_count"] == 3392
    assert analysis["area_sq_km"] > 0


# ==============================================================================
# TEST 5: Pixelvalue=13 Mask (Mask B)
# ==============================================================================
def test_05_pixelvalue_13_mask():
    """Verify NRSC_PIXELVALUE_13 contains only pixelvalue=13 features."""
    masks = load_and_split_nrsc_masks(NRSC_PATH)
    mask_b = masks[MASK_B]
    assert len(mask_b) == 607
    assert (mask_b["pixelvalue"] == 13).all()
    analysis = analyze_nrsc_mask(mask_b, MASK_B, "pixelvalue == 13")
    assert analysis["feature_count"] == 607
    assert analysis["area_sq_km"] > 0


# ==============================================================================
# TEST 6: Composite Nonzero Mask (Mask C)
# ==============================================================================
def test_06_composite_nonzero_mask():
    """Verify NRSC_NONZERO_COMPOSITE contains features with pixelvalue in {1, 13}."""
    masks = load_and_split_nrsc_masks(NRSC_PATH)
    mask_c = masks[MASK_C]
    assert len(mask_c) == 3392 + 607  # 3999 features (excluding 2 features with pixelvalue=0)
    assert set(mask_c["pixelvalue"].unique()) == {1, 13}


# ==============================================================================
# TEST 7: GCC Point-in-Polygon
# ==============================================================================
def test_07_gcc_point_in_polygon():
    """Verify point-in-polygon containment testing against all three masks."""
    masks = load_and_split_nrsc_masks(NRSC_PATH)
    gcc_results = run_gcc_point_validation(GCC_PATH, masks)
    assert gcc_results["total_gcc_points"] == 327

    p1 = gcc_results["overall_mask_performance"][MASK_A]
    p13 = gcc_results["overall_mask_performance"][MASK_B]
    pc = gcc_results["overall_mask_performance"][MASK_C]

    # Verify counts match observed empirical values
    assert p1["inside_count"] == 13
    assert p13["inside_count"] == 98
    assert pc["inside_count"] == 105
    assert pc["inside_count"] <= p1["inside_count"] + p13["inside_count"]
    assert p1["inside_count"] + p1["outside_count"] == 327


# ==============================================================================
# TEST 8: Inundation-Category Stratification
# ==============================================================================
def test_08_inundation_category_stratification():
    """Verify GCC hotspots stratify into four canonical categories."""
    assert normalize_gcc_category("Low Vulnerability less than 2 feet") == GCC_CATEGORY_LESS_2FT
    assert normalize_gcc_category("Medium Vulnerability\n2 to 3 Feet") == GCC_CATEGORY_2_TO_3FT
    assert normalize_gcc_category("High Vulnerability 3 to 5 Feet") == GCC_CATEGORY_3_TO_5FT
    assert normalize_gcc_category("Very High Vulnerability Above 5 Feet") == GCC_CATEGORY_ABOVE_5FT

    masks = load_and_split_nrsc_masks(NRSC_PATH)
    gcc_results = run_gcc_point_validation(GCC_PATH, masks)
    strat = gcc_results["stratified_by_category"][MASK_C]
    cat_totals = {item["category"]: item["total"] for item in strat}
    assert cat_totals[GCC_CATEGORY_LESS_2FT] == 202
    assert cat_totals[GCC_CATEGORY_2_TO_3FT] == 1
    assert cat_totals[GCC_CATEGORY_3_TO_5FT] == 86
    assert cat_totals[GCC_CATEGORY_ABOVE_5FT] == 38
    assert sum(cat_totals.values()) == 327


# ==============================================================================
# TEST 9: FABDEM Sampling
# ==============================================================================
def test_09_fabdem_sampling():
    """Verify FABDEM raster sampling at GCC point coordinates."""
    masks = load_and_split_nrsc_masks(NRSC_PATH)
    gcc_results = run_gcc_point_validation(GCC_PATH, masks)
    terrain_res = run_gcc_terrain_characterization(FABDEM_PATH, gcc_results["point_records"])
    assert terrain_res["total_points"] == 327
    assert terrain_res["sampled_valid_count"] == 233
    assert terrain_res["overall_terrain_stats"]["min"] is not None
    assert terrain_res["overall_terrain_stats"]["mean"] > 0


# ==============================================================================
# TEST 10: NoData Handling
# ==============================================================================
def test_10_nodata_and_out_of_bounds_handling():
    """Verify NoData and out-of-bounds coordinates are handled gracefully without raising exceptions."""
    test_points = [
        {"point_id": 1, "latitude": 13.016, "longitude": 80.182, "norm_category": "<2 ft"},  # Valid in Chennai
        {"point_id": 2, "latitude": 12.500, "longitude": 80.182, "norm_category": "<2 ft"},  # South of tile (out-of-bounds)
        {"point_id": 3, "latitude": 0.000, "longitude": 0.000, "norm_category": "<2 ft"},    # Null Island
    ]
    sampled = sample_fabdem_at_points(FABDEM_PATH, test_points)
    assert len(sampled) == 3
    assert sampled[0]["elevation_valid"] is True
    assert sampled[0]["dem_elevation"] is not None
    assert sampled[1]["elevation_valid"] is False
    assert sampled[1]["dem_elevation"] is None
    assert sampled[1]["out_of_tile"] is True
    assert sampled[2]["elevation_valid"] is False


# ==============================================================================
# TEST 11: Nandambakkam Coordinate Analysis
# ==============================================================================
def test_11_nandambakkam_coordinate_analysis():
    """Verify Nandambakkam CheckDam station coordinates and elevation."""
    masks = load_and_split_nrsc_masks(NRSC_PATH)
    nand = run_nandambakkam_analysis(FABDEM_PATH, masks, GCC_PATH)
    assert nand["coordinates"]["latitude"] == NANDAMBAKKAM_LAT
    assert nand["coordinates"]["longitude"] == NANDAMBAKKAM_LON
    assert nand["fabdem_elevation_m"] == pytest.approx(5.1, abs=0.1)


# ==============================================================================
# TEST 12: Distance Calculations
# ==============================================================================
def test_12_distance_calculations():
    """Verify distance to nearest NRSC mask in metric CRS is calculated correctly."""
    masks = load_and_split_nrsc_masks(NRSC_PATH)
    nand = run_nandambakkam_analysis(FABDEM_PATH, masks, GCC_PATH)
    # Mask A is within ~15 m of the checkdam river channel
    d1 = nand["nrsc_mask_proximity"][MASK_A]["nearest_distance_meters"]
    assert 10.0 <= d1 <= 20.0
    # Nearby GCC points within concentric distance rings
    rings = nand["gcc_hotspots_ring_counts"]
    assert rings["within_250m"] == 0
    assert rings["within_500m"] == 1
    assert rings["within_1000m"] == 5
    assert rings["within_2000m"] == 10


# ==============================================================================
# TEST 13: Road Cross-Check
# ==============================================================================
def test_13_road_cross_check():
    """Verify flooded road network cross-check computes intersection metrics."""
    masks = load_and_split_nrsc_masks(NRSC_PATH)
    road_res = run_road_cross_check(ROADS_PATH, masks)
    assert road_res["total_roads"] == 7894
    assert road_res["class_breakdown"]["is_flooded_1"] == 7884
    assert road_res["class_breakdown"]["is_flooded_0"] == 10
    c_mask = road_res["mask_comparisons"][MASK_C]
    assert c_mask["flooded_roads_intersecting_mask"] > 0
    assert c_mask["flooded_intersection_rate"] > 0.4


# ==============================================================================
# TEST 14: Stagnation Cross-Check
# ==============================================================================
def test_14_stagnation_cross_check():
    """Verify water stagnation points cross-check computes hit rates."""
    masks = load_and_split_nrsc_masks(NRSC_PATH)
    stag_res = run_stagnation_cross_check(STAGNATION_PATH, masks)
    assert stag_res["total_stagnation_points"] == 753
    # Mask 13 hit rate should be substantially higher than Mask 1
    hit_1 = stag_res["mask_comparisons"][MASK_A]["inside_count"]
    hit_13 = stag_res["mask_comparisons"][MASK_B]["inside_count"]
    assert hit_13 > hit_1
    assert hit_13 == 202
    assert hit_1 == 21


# ==============================================================================
# TEST 15: Area Calculated in Projected Metric CRS
# ==============================================================================
def test_15_area_calculated_in_projected_crs():
    """Verify areas are strictly calculated in metric EPSG:32644 (not geographic degrees)."""
    masks = load_and_split_nrsc_masks(NRSC_PATH)
    mask_c = masks[MASK_C]
    clean_metric = prepare_metric_gdf(mask_c)
    assert clean_metric.crs.to_string() == METRIC_CRS
    area_sq_m = float(clean_metric.geometry.area.sum())
    # 316.5 km² = 3.16e8 m²
    assert 300_000_000 <= area_sq_m <= 350_000_000
    # Geographic degree squared would be < 0.1 sq degrees!
    assert area_sq_m > 1_000_000


# ==============================================================================
# TEST 16: Source Files are Never Modified
# ==============================================================================
def test_16_source_files_never_modified():
    """Verify source files hashes remain identical before and after harness execution."""
    pre_hash = compute_sha256(NRSC_PATH)
    # Perform various loading and splitting operations
    masks = load_and_split_nrsc_masks(NRSC_PATH)
    _ = analyze_nrsc_mask(masks[MASK_C], MASK_C, "test")
    post_hash = compute_sha256(NRSC_PATH)
    assert pre_hash == post_hash


# ==============================================================================
# TEST 17: Deterministic Output
# ==============================================================================
def test_17_deterministic_output():
    """Verify multiple executions produce bitwise identical statistics."""
    stats1 = calculate_distribution_stats([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0])
    stats2 = calculate_distribution_stats([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0])
    assert stats1 == stats2


# ==============================================================================
# TEST 18: Provenance Manifest Generation
# ==============================================================================
def test_18_provenance_manifest_generation():
    """Verify data provenance manifest generates entries for all 8 research files."""
    manifest = build_data_manifest(DATA_DIR)
    assert len(manifest["datasets"]) == 8
    for key, item in manifest["datasets"].items():
        assert item["status"] == "AVAILABLE"
        assert item["sha256"] is not None
        assert len(item["sha256"]) == 64


# ==============================================================================
# TEST 19: No IoU Emitted Without Prediction Mask
# ==============================================================================
def test_19_no_iou_emitted_without_prediction_mask():
    """Verify IoU is strictly prohibited when no PRISM prediction mask exists."""
    manifest = build_data_manifest(DATA_DIR)
    masks = load_and_split_nrsc_masks(NRSC_PATH)
    qa = {MASK_C: validate_gdf_spatial_qa(masks[MASK_C], MASK_C)}
    nrsc_res = run_nrsc_class_sensitivity_analysis(NRSC_PATH)
    gcc_res = run_gcc_point_validation(GCC_PATH, masks)
    terrain_res = run_gcc_terrain_characterization(FABDEM_PATH, gcc_res["point_records"])
    nand_res = run_nandambakkam_analysis(FABDEM_PATH, masks, GCC_PATH)
    road_res = run_road_cross_check(ROADS_PATH, masks)
    stag_res = run_stagnation_cross_check(STAGNATION_PATH, masks)

    decision = evaluate_validation_readiness(
        manifest_summary=manifest,
        spatial_qa_summary=qa,
        nrsc_summary=nrsc_res,
        gcc_summary=gcc_res,
        terrain_summary=terrain_res,
        nandambakkam_summary=nand_res,
        road_summary=road_res,
        stagnation_summary=stag_res,
        prism_prediction_mask_present=False,
    )

    # IoU must not appear in metrics
    dec_str = str(decision).lower()
    assert "iou" not in decision or decision.get("iou") is None
    assert "DO NOT report IoU" in " ".join(decision["prohibited_actions"])


# ==============================================================================
# TEST 20: Final Validation Status is Evidence-Derived
# ==============================================================================
def test_20_final_validation_status_evidence_derived():
    """Verify validation status reflects empirical evidence (CONDITIONAL due to unverified datum)."""
    manifest = build_data_manifest(DATA_DIR)
    masks = load_and_split_nrsc_masks(NRSC_PATH)
    qa = {MASK_C: validate_gdf_spatial_qa(masks[MASK_C], MASK_C)}
    nrsc_res = run_nrsc_class_sensitivity_analysis(NRSC_PATH)
    gcc_res = run_gcc_point_validation(GCC_PATH, masks)
    terrain_res = run_gcc_terrain_characterization(FABDEM_PATH, gcc_res["point_records"])
    nand_res = run_nandambakkam_analysis(FABDEM_PATH, masks, GCC_PATH)
    road_res = run_road_cross_check(ROADS_PATH, masks)
    stag_res = run_stagnation_cross_check(STAGNATION_PATH, masks)

    # Realistic scenario: gauge datum is unverified -> CONDITIONAL_TERRAIN_EXPERIMENT
    decision = evaluate_validation_readiness(
        manifest_summary=manifest,
        spatial_qa_summary=qa,
        nrsc_summary=nrsc_res,
        gcc_summary=gcc_res,
        terrain_summary=terrain_res,
        nandambakkam_summary=nand_res,
        road_summary=road_res,
        stagnation_summary=stag_res,
        prism_prediction_mask_present=False,
    )
    assert decision["validation_status"] == VALIDATION_CONDITIONAL

    # Simulated missing data scenario -> NOT_READY
    bad_manifest = {"datasets": {"fabdem": {"status": "MISSING"}}}
    bad_decision = evaluate_validation_readiness(
        manifest_summary=bad_manifest,
        spatial_qa_summary=qa,
        nrsc_summary=nrsc_res,
        gcc_summary=gcc_res,
        terrain_summary=terrain_res,
        nandambakkam_summary=nand_res,
        road_summary=road_res,
        stagnation_summary=stag_res,
        prism_prediction_mask_present=False,
    )
    assert bad_decision["validation_status"] == VALIDATION_NOT_READY

    # Regression guard: Verify generated report rejects old overstrong semantic claims
    from app.research.a8_5.report import generate_markdown_report
    from app.research.a8_5.terrain_analysis import run_nrsc_mask_terrain_distributions
    nrsc_terrain = run_nrsc_mask_terrain_distributions(FABDEM_PATH, masks)
    full_output = {
        "manifest": manifest,
        "spatial_qa": qa,
        "nrsc": nrsc_res,
        "gcc": gcc_res,
        "terrain_gcc": terrain_res,
        "nrsc_terrain": nrsc_terrain,
        "nandambakkam": nand_res,
        "roads": road_res,
        "stagnation": stag_res,
        "decision": decision,
    }
    markdown_report = generate_markdown_report(full_output)

    # 1. Reject old overstrong semantic claims
    assert "Mask 13 represents urban flood corridors in metropolitan Chennai" not in markdown_report
    assert "Mask 1 captures broad regional water bodies" not in markdown_report
    assert "flat-plane elevation slicing is physically invalid" not in markdown_report
    assert "Flat-plane elevation slicing is proven scientifically invalid" not in markdown_report

    # 2. Confirm required corrected scientific wording is present
    corrected_wording_1 = (
        "Mask 13 shows substantially greater spatial consistency with the available urban GCC flood-hotspot "
        "and water-stagnation observations than Mask 1. The semantic meaning of source pixelvalue 1 versus 13 "
        "remains unresolved because the public source metadata does not define these classes."
    )
    corrected_wording_2 = (
        "The observed elevation distributions demonstrate substantial overlap between historical inundation "
        "and surrounding terrain; therefore a single global DEM elevation threshold is not considered "
        "scientifically defensible for this study area."
    )
    assert corrected_wording_1 in markdown_report
    assert corrected_wording_2 in markdown_report
