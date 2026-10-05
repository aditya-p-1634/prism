"""PRISM Phase A.8.5 — CLI Runner & Research Harness Orchestrator.

CLI entry point:
    python -m app.research.a8_5.run [--data-dir PATH] [options]

Executes the complete Terrain & Historical Flood Validation Harness:
1. Builds cryptographic data provenance manifest.
2. Performs spatial & geometry QA.
3. Constructs and characterizes the three NRSC source-derived masks.
4. Executes GCC hotspot point spatial consistency testing.
5. Performs FABDEM terrain characterization at GCC points.
6. Evaluates FABDEM elevation distributions inside vs outside NRSC masks.
7. Conducts Nandambakkam CheckDam station spatial and distance analysis.
8. Executes flooded-road cross-check.
9. Executes water stagnation cross-check.
10. Strictly enforces prohibition of pseudo-IoU.
11. Evaluates evidence to derive validation readiness decision.
12. Exports all artifacts (JSON, Markdown, CSVs).
Exits non-zero on data integrity failure.
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Any

from app.research.a8_5.constants import (
    DEFAULT_DATA_DIR,
    DEFAULT_FILES,
    MASK_A,
    MASK_B,
    MASK_C,
    VALIDATION_NOT_READY,
)
from app.research.a8_5.decision import evaluate_validation_readiness
from app.research.a8_5.gcc_analysis import run_gcc_point_validation
from app.research.a8_5.manifest import build_data_manifest
from app.research.a8_5.nandambakkam_analysis import run_nandambakkam_analysis
from app.research.a8_5.nrsc_analysis import (
    load_and_split_nrsc_masks,
    run_nrsc_class_sensitivity_analysis,
)
from app.research.a8_5.report import export_artifacts
from app.research.a8_5.road_analysis import run_road_cross_check
from app.research.a8_5.spatial_qa import validate_gdf_spatial_qa
from app.research.a8_5.stagnation_analysis import run_stagnation_cross_check
from app.research.a8_5.terrain_analysis import (
    run_gcc_terrain_characterization,
    run_nrsc_mask_terrain_distributions,
)


def resolve_file_path(data_dir: str, arg_val: str | None, default_key: str) -> str:
    """Resolve file path prioritizing explicit CLI argument over default filename in data_dir."""
    if arg_val:
        return os.path.abspath(arg_val)
    filename = DEFAULT_FILES[default_key]
    return os.path.abspath(os.path.join(data_dir, filename))


def run_a8_5_harness(
    data_dir: str = DEFAULT_DATA_DIR,
    custom_paths: dict[str, str] | None = None,
    output_dir: str = "docs/research/artifacts",
    report_markdown_path: str = "docs/research/A8_5_TERRAIN_FLOOD_VALIDATION.md",
) -> dict[str, Any]:
    """Execute complete validation harness and export all reports and artifacts."""
    print("=" * 80)
    print("  PRISM PHASE A.8.5 — TERRAIN & HISTORICAL FLOOD VALIDATION HARNESS")
    print("=" * 80)

    # 1. Resolve dataset file paths
    resolved_paths: dict[str, str] = {}
    for key in DEFAULT_FILES:
        c_path = custom_paths.get(key) if custom_paths else None
        resolved_paths[key] = resolve_file_path(data_dir, c_path, key)
        print(f"  [{key.upper()}] -> {resolved_paths[key]}")

    # Check existence
    missing_files = [k for k, p in resolved_paths.items() if not os.path.exists(p)]
    if missing_files:
        print(f"\n[ERROR] Missing required research files: {missing_files}", file=sys.stderr)
        raise FileNotFoundError(f"Missing required research files: {missing_files}")

    # 2. Data Provenance Manifest (Objective 1)
    print("\n[Step 1] Generating Cryptographic Data Provenance Manifest...")
    manifest = build_data_manifest(data_dir=data_dir, custom_paths=resolved_paths)
    print(f"  Manifest generated for {len(manifest['datasets'])} datasets.")

    # 3. Spatial & Geometry QA (Objective 9)
    print("\n[Step 2] Executing Spatial & Geometry QA Validation...")
    masks = load_and_split_nrsc_masks(resolved_paths["nrsc_kml"])
    spatial_qa_results: dict[str, Any] = {
        "nrsc_raw": validate_gdf_spatial_qa(masks["RAW_FULL"], "NRSC_2015_INUNDATION"),
        MASK_A: validate_gdf_spatial_qa(masks[MASK_A], MASK_A),
        MASK_B: validate_gdf_spatial_qa(masks[MASK_B], MASK_B),
        MASK_C: validate_gdf_spatial_qa(masks[MASK_C], MASK_C),
    }

    # QA on other vector layers
    import geopandas as gpd
    for vk, kml_name in [
        ("gcc_hotspots", resolved_paths["gcc_kml"]),
        ("kancheepuram_hotspots", resolved_paths["kancheepuram_kml"]),
        ("tiruvallur_hotspots", resolved_paths["tiruvallur_kml"]),
        ("chennai_stagnation", resolved_paths["stagnation_kml"]),
        ("road_network", resolved_paths["roads_kml"]),
    ]:
        gdf_v = gpd.read_file(kml_name)
        spatial_qa_results[vk] = validate_gdf_spatial_qa(gdf_v, vk)
        print(f"  QA: {vk} -> Valid: {spatial_qa_results[vk]['valid_count']}, Coordinates Sane: {spatial_qa_results[vk]['coordinates_sane']}")

    # 4. NRSC Class Sensitivity (Objective 2)
    print("\n[Step 3] Analyzing NRSC Class Sensitivity (Masks A, B, C)...")
    nrsc_results = run_nrsc_class_sensitivity_analysis(resolved_paths["nrsc_kml"])
    print(f"  Mask A ({MASK_A}): {nrsc_results['masks'][MASK_A]['feature_count']} features, Area: {nrsc_results['masks'][MASK_A]['area_sq_km']} km²")
    print(f"  Mask B ({MASK_B}): {nrsc_results['masks'][MASK_B]['feature_count']} features, Area: {nrsc_results['masks'][MASK_B]['area_sq_km']} km²")
    print(f"  Mask C ({MASK_C}): {nrsc_results['masks'][MASK_C]['feature_count']} features, Area: {nrsc_results['masks'][MASK_C]['area_sq_km']} km²")

    # 5. GCC Point Validation (Objective 3)
    print("\n[Step 4] Executing GCC Hotspot Point Validation & Stratification...")
    gcc_results = run_gcc_point_validation(resolved_paths["gcc_kml"], masks)
    for mname in [MASK_A, MASK_B, MASK_C]:
        p_stat = gcc_results["overall_mask_performance"][mname]
        print(f"  {mname} -> Inside: {p_stat['inside_count']}/{p_stat['total_points']} ({p_stat['hit_rate_pct']}%)")

    # 6. FABDEM Terrain Characterization at GCC Hotspots (Objective 4)
    print("\n[Step 5] Sampling FABDEM Terrain at GCC Hotspots...")
    terrain_gcc = run_gcc_terrain_characterization(
        resolved_paths["fabdem"], gcc_results["point_records"]
    )
    print(f"  Valid DEM samples: {terrain_gcc['sampled_valid_count']}/{terrain_gcc['total_points']} "
          f"(Out-of-tile southern points: {terrain_gcc['out_of_tile_count']})")
    print(f"  Overall Elevation: Mean={terrain_gcc['overall_terrain_stats']['mean']}m, "
          f"Median={terrain_gcc['overall_terrain_stats']['median']}m, Range=[{terrain_gcc['overall_terrain_stats']['min']}m, {terrain_gcc['overall_terrain_stats']['max']}m]")

    # 7. NRSC Mask Terrain Distributions (Objective 5)
    print("\n[Step 6] Evaluating FABDEM Distributions Inside vs Outside NRSC Masks...")
    nrsc_terrain = run_nrsc_mask_terrain_distributions(
        resolved_paths["fabdem"], masks
    )
    for mname in [MASK_A, MASK_B, MASK_C]:
        d = nrsc_terrain["mask_terrain_distributions"][mname]
        print(f"  {mname} Inside Mean Elev: {d['inside_mask']['mean']}m vs Outside Study Area Mean: {d['outside_mask_study_area']['mean']}m")

    # 8. Nandambakkam Station Context (Objective 6)
    print("\n[Step 7] Analyzing Pilot Telemetry Station (Nandambakkam CheckDam)...")
    nand_results = run_nandambakkam_analysis(
        resolved_paths["fabdem"], masks, resolved_paths["gcc_kml"]
    )
    print(f"  Station Elevation: {nand_results['fabdem_elevation_m']} m")
    print(f"  Nearest Mask A Distance: {nand_results['nrsc_mask_proximity'][MASK_A]['nearest_distance_meters']} m")
    print(f"  Nearby GCC Hotspots: 500m={nand_results['gcc_hotspots_ring_counts']['within_500m']}, "
          f"1000m={nand_results['gcc_hotspots_ring_counts']['within_1000m']}, 2000m={nand_results['gcc_hotspots_ring_counts']['within_2000m']}")

    # 9. Flooded Road Cross-Check (Objective 7)
    print("\n[Step 8] Performing Flooded Road Network Cross-Check...")
    road_results = run_road_cross_check(resolved_paths["roads_kml"], masks)
    comp_rd = road_results["mask_comparisons"][MASK_C]
    print(f"  Flooded Roads Intersecting Composite: {comp_rd['flooded_roads_intersecting_mask']}/{comp_rd['flooded_road_features']} "
          f"({round(comp_rd['flooded_intersection_rate']*100, 2)}%)")

    # 10. Water Stagnation Cross-Check (Objective 8)
    print("\n[Step 9] Performing Water Stagnation Cross-Check...")
    stag_results = run_stagnation_cross_check(resolved_paths["stagnation_kml"], masks)
    comp_st = stag_results["mask_comparisons"][MASK_C]
    print(f"  Stagnation Points Intersecting Composite: {comp_st['inside_count']}/{comp_st['total_stagnation_points']} "
          f"({comp_st['hit_rate_pct']}%)")

    # 11. Validation Readiness Decision (Objectives 10 & 11)
    print("\n[Step 10] Synthesizing Validation Readiness Decision (Strictly No Pseudo-IoU)...")
    decision_results = evaluate_validation_readiness(
        manifest_summary=manifest,
        spatial_qa_summary=spatial_qa_results,
        nrsc_summary=nrsc_results,
        gcc_summary=gcc_results,
        terrain_summary=terrain_gcc,
        nandambakkam_summary=nand_results,
        road_summary=road_results,
        stagnation_summary=stag_results,
        prism_prediction_mask_present=False,
    )
    print(f"  Final Decision Status: >>> {decision_results['validation_status']} <<<")
    print(f"  Rationale: {decision_results['scientific_rationale']}")

    # 12. Export Reports and Artifacts (Objective 12)
    print("\n[Step 11] Exporting Reports and Artifacts...")
    full_output = {
        "manifest": manifest,
        "spatial_qa": spatial_qa_results,
        "nrsc": nrsc_results,
        "gcc": gcc_results,
        "terrain_gcc": terrain_gcc,
        "nrsc_terrain": nrsc_terrain,
        "nandambakkam": nand_results,
        "roads": road_results,
        "stagnation": stag_results,
        "decision": decision_results,
    }

    artifacts = export_artifacts(
        full_output, output_dir=output_dir, report_markdown_path=report_markdown_path
    )
    for art_k, art_path in artifacts.items():
        print(f"  Exported: [{art_k}] -> {art_path}")

    print("\n" + "=" * 80)
    print("  A.8.5 VALIDATION HARNESS EXECUTION COMPLETE")
    print(f"  FINAL STATUS: {decision_results['validation_status']}")
    print("=" * 80)

    if decision_results["validation_status"] == VALIDATION_NOT_READY:
        sys.exit(1)

    return full_output


def main() -> None:
    """CLI runner entry point."""
    parser = argparse.ArgumentParser(
        description="PRISM Phase A.8.5 — Terrain & Historical Flood Validation Harness"
    )
    parser.add_argument(
        "--data-dir",
        default=DEFAULT_DATA_DIR,
        help="Directory containing research datasets (default: data/research)",
    )
    parser.add_argument("--fabdem", help="Path to N13E080_FABDEM_V1-2.tif")
    parser.add_argument("--nrsc", help="Path to NRSC flood inundation KML")
    parser.add_argument("--gcc", help="Path to GCC flood hotspots KML")
    parser.add_argument("--kancheepuram", help="Path to Kancheepuram hotspots KML")
    parser.add_argument("--tiruvallur", help="Path to Tiruvallur hotspots KML")
    parser.add_argument("--stagnation", help="Path to Chennai water stagnation KML")
    parser.add_argument("--roads", help="Path to Chennai road network KML")
    parser.add_argument("--reference-pdf", help="Path to NRSC/ISRO reference PDF")
    parser.add_argument(
        "--output-dir",
        default="docs/research/artifacts",
        help="Directory to save report artifacts (default: docs/research/artifacts)",
    )
    parser.add_argument(
        "--report-markdown",
        default="docs/research/A8_5_TERRAIN_FLOOD_VALIDATION.md",
        help="Path for final Markdown research report",
    )

    args = parser.parse_args()

    custom_paths = {
        "fabdem": args.fabdem,
        "nrsc_kml": args.nrsc,
        "gcc_kml": args.gcc,
        "kancheepuram_kml": args.kancheepuram,
        "tiruvallur_kml": args.tiruvallur,
        "stagnation_kml": args.stagnation,
        "roads_kml": args.roads,
        "reference_pdf": args.reference_pdf,
    }

    try:
        run_a8_5_harness(
            data_dir=args.data_dir,
            custom_paths=custom_paths,
            output_dir=args.output_dir,
            report_markdown_path=args.report_markdown,
        )
    except Exception as e:
        print(f"\n[FATAL] A.8.5 Harness failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
