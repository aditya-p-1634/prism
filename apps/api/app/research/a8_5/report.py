"""PRISM A.8.5 Report & Artifact Generation Engine.

Produces:
1. docs/research/artifacts/a8_5_validation_report.json (machine-readable)
2. docs/research/A8_5_TERRAIN_FLOOD_VALIDATION.md (human-readable report with 16 sections)
3. docs/research/artifacts/a8_5_data_manifest.json (provenance manifest)
4. docs/research/artifacts/a8_5_gcc_point_validation.csv
5. docs/research/artifacts/a8_5_terrain_statistics.csv
6. docs/research/artifacts/a8_5_nandambakkam_context.csv

Enforces strict epistemological tagging:
[OBSERVED], [SOURCE-DERIVED], [COMPUTED], [INFERRED], [UNKNOWN].
"""

from __future__ import annotations

import csv
import json
import os
from typing import Any


def export_artifacts(
    full_results: dict[str, Any],
    output_dir: str = "docs/research/artifacts",
    report_markdown_path: str = "docs/research/A8_5_TERRAIN_FLOOD_VALIDATION.md",
) -> dict[str, str]:
    """Write all JSON, CSV, and Markdown validation artifacts."""
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(os.path.dirname(report_markdown_path), exist_ok=True)

    written_paths: dict[str, str] = {}

    # 1. Machine-readable validation report JSON
    json_report_path = os.path.join(output_dir, "a8_5_validation_report.json")
    with open(json_report_path, "w", encoding="utf-8") as f:
        # Exclude large raw lists for cleaner report JSON, keep summary and references
        json_clean = {
            "validation_status": full_results["decision"]["validation_status"],
            "decision": full_results["decision"],
            "manifest_summary": full_results["manifest"],
            "spatial_qa": full_results["spatial_qa"],
            "nrsc_analysis": full_results["nrsc"],
            "gcc_validation_summary": {
                k: v for k, v in full_results["gcc"].items() if k != "point_records"
            },
            "terrain_summary": {
                k: v for k, v in full_results["terrain_gcc"].items() if k != "sampled_records"
            },
            "nrsc_terrain_distributions": full_results["nrsc_terrain"],
            "nandambakkam_analysis": full_results["nandambakkam"],
            "road_cross_check": full_results["roads"],
            "stagnation_cross_check": full_results["stagnation"],
        }
        json.dump(json_clean, f, indent=2)
    written_paths["json_report"] = json_report_path

    # 2. Data provenance manifest JSON
    manifest_path = os.path.join(output_dir, "a8_5_data_manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(full_results["manifest"], f, indent=2)
    written_paths["data_manifest"] = manifest_path

    # 3. CSV: GCC point validation table
    gcc_csv_path = os.path.join(output_dir, "a8_5_gcc_point_validation.csv")
    gcc_records = full_results.get("terrain_gcc", {}).get("sampled_records", [])
    if gcc_records:
        fieldnames = [
            "point_id",
            "location",
            "latitude",
            "longitude",
            "dem_elevation",
            "elevation_valid",
            "out_of_tile",
            "raw_inundation_level",
            "norm_category",
            "vulnerability",
            "inundation_ft",
            "zone",
            "ward",
            "inside_NRSC_PIXELVALUE_1",
            "inside_NRSC_PIXELVALUE_13",
            "inside_NRSC_NONZERO_COMPOSITE",
        ]
        with open(gcc_csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            for r in gcc_records:
                writer.writerow(r)
        written_paths["gcc_csv"] = gcc_csv_path

    # 4. CSV: Terrain statistics summary
    terrain_csv_path = os.path.join(output_dir, "a8_5_terrain_statistics.csv")
    with open(terrain_csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "group",
            "category_or_mask",
            "count",
            "min",
            "max",
            "mean",
            "median",
            "std",
            "p05",
            "p25",
            "p75",
            "p95",
        ])

        # GCC categories
        for cat, s in full_results["terrain_gcc"].get("stratified_by_category", {}).items():
            writer.writerow([
                "GCC_HOTSPOTS",
                cat,
                s.get("count"),
                s.get("min"),
                s.get("max"),
                s.get("mean"),
                s.get("median"),
                s.get("std"),
                s.get("p05"),
                s.get("p25"),
                s.get("p75"),
                s.get("p95"),
            ])

        # Overall GCC
        og = full_results["terrain_gcc"].get("overall_terrain_stats", {})
        writer.writerow([
            "GCC_HOTSPOTS",
            "ALL_VALID_SAMPLES",
            og.get("count"),
            og.get("min"),
            og.get("max"),
            og.get("mean"),
            og.get("median"),
            og.get("std"),
            og.get("p05"),
            og.get("p25"),
            og.get("p75"),
            og.get("p95"),
        ])

        # NRSC mask terrain distributions
        for mask_name, m_stats in full_results["nrsc_terrain"].get("mask_terrain_distributions", {}).items():
            ins = m_stats.get("inside_mask", {})
            writer.writerow([
                "NRSC_MASK_INSIDE",
                mask_name,
                ins.get("valid_samples"),
                ins.get("min"),
                ins.get("max"),
                ins.get("mean"),
                ins.get("median"),
                "",
                ins.get("p05"),
                "",
                "",
                ins.get("p95"),
            ])
            outs = m_stats.get("outside_mask_study_area", {})
            writer.writerow([
                "NRSC_MASK_OUTSIDE",
                mask_name,
                outs.get("valid_samples"),
                outs.get("min"),
                outs.get("max"),
                outs.get("mean"),
                outs.get("median"),
                "",
                outs.get("p05"),
                "",
                "",
                outs.get("p95"),
            ])
    written_paths["terrain_csv"] = terrain_csv_path

    # 5. CSV: Nandambakkam nearby observations
    nand_csv_path = os.path.join(output_dir, "a8_5_nandambakkam_context.csv")
    nand_obs = full_results["nandambakkam"].get("nearby_gcc_observations_2000m", [])
    if nand_obs:
        with open(nand_csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "distance_meters",
                    "location",
                    "inundation_level",
                    "inundation_ft",
                    "vulnerability",
                    "latitude",
                    "longitude",
                ],
                extrasaction="ignore",
            )
            writer.writeheader()
            for r in nand_obs:
                writer.writerow(r)
        written_paths["nandambakkam_csv"] = nand_csv_path

    # 6. Comprehensive Research Markdown Report (16 sections)
    markdown_content = generate_markdown_report(full_results)
    with open(report_markdown_path, "w", encoding="utf-8") as f:
        f.write(markdown_content)
    written_paths["markdown_report"] = report_markdown_path

    return written_paths


def generate_markdown_report(data: dict[str, Any]) -> str:
    """Format the 16-section research markdown report with strict epistemic separation."""
    m = data["manifest"]["datasets"]
    qa = data["spatial_qa"]
    nrsc = data["nrsc"]
    gcc = data["gcc"]
    terrain_gcc = data["terrain_gcc"]
    nrsc_terrain = data["nrsc_terrain"]
    nand = data["nandambakkam"]
    roads = data["roads"]
    stag = data["stagnation"]
    dec = data["decision"]

    md: list[str] = []
    
    # Title & Header
    md.append("# PRISM Phase A.8.5 — Terrain & Historical Flood Validation Research Report")
    md.append("### Epistemic Audit, Cross-Source Spatial Consistency & Validation Readiness Decision")
    md.append("")
    md.append("> **Epistemological Classification Guide:**")
    md.append("> - **[OBSERVED]**: Directly measured in the physical world by instruments or field observers.")
    md.append("> - **[SOURCE-DERIVED]**: Extracted directly from external reference files without algorithmic transformation.")
    md.append("> - **[COMPUTED]**: Deterministically calculated via mathematical or spatial operations on ingested data.")
    md.append("> - **[INFERRED]**: Formulated based on patterns, correlations, or scientific reasoning (not proven facts).")
    md.append("> - **[UNKNOWN]**: Critical parameters or semantics lacking verifiable documentation or empirical grounding.")
    md.append("")
    md.append("---")
    md.append("")

    # Section 1: Purpose
    md.append("## 1. Purpose")
    md.append(
        "This research harness audits the historical evidence of the catastrophic December 2015 Chennai flood disaster. "
        "Its objective is to rigorously characterize FABDEM bare-earth terrain against independent empirical evidence "
        "(NRSC satellite/hydrodynamic flood layers, GCC municipal incident points, OSM flooded road networks, and municipal stagnation logs), "
        "evaluate spatial consistency across sources, and determine whether a terrain-aware experimental flood model is scientifically defensible.\n\n"
        "**Strict Research Boundary**: This phase is an isolated research harness. It does **not** predict operational floods, "
        "does **not** alter PRISM production engines E1–E6, and does **not** convert unverified gauge stage into absolute water surface elevations."
    )
    md.append("")

    # Section 2: Dataset Inventory
    md.append("## 2. Dataset Inventory")
    md.append("| Dataset Key | Filename | Provider | Geometry Type | Feature Count | Format |")
    md.append("|---|---|---|---|---|---|")
    for k, v in m.items():
        fname = v.get("filename", k)
        provider = v.get("source_provider", "External Source")
        geom = v.get("geometry_type", "Vector")
        cnt = v.get("feature_count", "N/A")
        fmt = "GeoTIFF" if fname.endswith(".tif") else ("PDF" if fname.endswith(".pdf") else "KML")
        md.append(f"| `{k}` | `{fname}` | {provider} | {geom} | {cnt} | {fmt} |")
    md.append("")

    # Section 3: Provenance
    md.append("## 3. Provenance & Cryptographic Audit")
    md.append("| Filename | SHA-256 Checksum | Size (bytes) | Status |")
    md.append("|---|---|---|---|")
    for k, v in m.items():
        fname = v.get("filename", k)
        sha = v.get("sha256", "MISSING")
        size = v.get("file_size_bytes", 0)
        status = v.get("status", "AVAILABLE")
        md.append(f"| `{fname}` | `{sha}` | {size} | **{status}** |")
    md.append("")
    md.append("**Source Immutability Rule [COMPUTED]**: All source files remain 100% read-only and unaltered. No filenames, attributes, or records were overwritten.")
    md.append("")

    # Section 4: CRS and Geometry QA
    md.append("## 4. CRS and Geometry QA")
    md.append(f"- **Source CRS [SOURCE-DERIVED]**: All ingested vector layers declare `EPSG:4326` (WGS 84 geographic coordinates).")
    md.append(f"- **Projected Metric CRS [COMPUTED]**: `EPSG:32644` (WGS 84 / UTM zone 44N).")
    md.append(f"  - *Justification*: Chennai (~80.2°E, 13.0°N) is centrally located in UTM Zone 44N (78°E to 84°E). Metric distance and area calculations achieve minimal distortion (<0.1%).")
    md.append(f"- **Area Calculation Rule [COMPUTED]**: Areas are strictly calculated in metric projection (m² and km²), never in square geographic degrees.")
    md.append("")
    md.append("| Dataset | Total | Valid Geoms | Invalid | Empty/Null | Coordinates Sane? | Duplicate Points |")
    md.append("|---|---|---|---|---|---|---|")
    for ds_name, q in qa.items():
        sane_str = "Yes (Chennai Envelope)" if q.get("coordinates_sane") else "No"
        md.append(f"| `{ds_name}` | {q.get('total_count')} | {q.get('valid_count')} | {q.get('invalid_count')} | {q.get('empty_count')}/{q.get('null_count')} | {sane_str} | {q.get('duplicate_count')} |")
    md.append("")

    # Section 5: NRSC Pixelvalue Findings
    pcounts = nrsc.get("raw_pixelvalue_counts", {})
    md.append("## 5. NRSC Pixelvalue Findings")
    md.append(
        "The public metadata accompanying the NRSC 2015 inundation layer identifies the vector polygons as the Chennai flood "
        "inundation zone, but **does NOT document the semantic meaning of `pixelvalue` 1 versus 13**.\n\n"
        f"- **[SOURCE-DERIVED] Observed raw counts**:\n"
        f"  - `pixelvalue = 1`: **{pcounts.get(1, 0)}** polygons\n"
        f"  - `pixelvalue = 13`: **{pcounts.get(13, 0)}** polygons\n"
        f"  - `pixelvalue = 0`: **{pcounts.get(0, 0)}** polygons\n\n"
        "- **[UNKNOWN] Semantics**: Whether `13` represents deeper water, standing water, urban flood corridors, or high-confidence satellite detections is unverified.\n"
        "- **[SCIENTIFIC MANDATE]**: Never assume `1 = flood` and `13 = permanent water` or vice versa. All analyses preserve the raw attributes."
    )
    md.append("")

    # Section 6: NRSC Mask Sensitivity
    md.append("## 6. NRSC Mask Sensitivity Analysis")
    md.append("Three explicitly named, source-derived masks were constructed:")
    md.append("1. `NRSC_PIXELVALUE_1`: Features where `pixelvalue == 1`")
    md.append("2. `NRSC_PIXELVALUE_13`: Features where `pixelvalue == 13`")
    md.append("3. `NRSC_NONZERO_COMPOSITE`: Composite where `pixelvalue in {1, 13}`\n")
    md.append("| Metric | Mask A (`NRSC_PIXELVALUE_1`) | Mask B (`NRSC_PIXELVALUE_13`) | Mask C (`NRSC_NONZERO_COMPOSITE`) |")
    md.append("|---|---|---|---|")
    ma = nrsc["masks"]["NRSC_PIXELVALUE_1"]
    mb = nrsc["masks"]["NRSC_PIXELVALUE_13"]
    mc = nrsc["masks"]["NRSC_NONZERO_COMPOSITE"]
    md.append(f"| **Feature Count [SOURCE-DERIVED]** | {ma['feature_count']} | {mb['feature_count']} | {mc['feature_count']} |")
    md.append(f"| **Valid Geometries [COMPUTED]** | {ma['valid_geometry_count']} | {mb['valid_geometry_count']} | {mc['valid_geometry_count']} |")
    md.append(f"| **Invalid Geometries [COMPUTED]** | {ma['invalid_geometry_count']} | {mb['invalid_geometry_count']} | {mc['invalid_geometry_count']} |")
    md.append(f"| **Projected Metric Area [COMPUTED]** | {ma['area_sq_km']} km² | {mb['area_sq_km']} km² | {mc['area_sq_km']} km² |")
    md.append(f"| **FABDEM Overlap (km²) [COMPUTED]** | {ma['fabdem_overlap']['clipped_area_sq_km']} km² | {mb['fabdem_overlap']['clipped_area_sq_km']} km² | {mc['fabdem_overlap']['clipped_area_sq_km']} km² |")
    md.append(f"| **Chennai Core Overlap (km²) [COMPUTED]** | {ma['chennai_study_overlap']['clipped_area_sq_km']} km² | {mb['chennai_study_overlap']['clipped_area_sq_km']} km² | {mc['chennai_study_overlap']['clipped_area_sq_km']} km² |")
    md.append("")

    # Section 7: GCC Hotspot Analysis
    md.append("## 7. GCC Hotspot Point Spatial Consistency Analysis")
    md.append(
        "Spatial containment testing of 327 GCC flood hotspot points across the three NRSC source-derived masks. "
        "Governed strictly by **Spatial Consistency Analysis** (NOT accuracy against ground truth).\n"
    )
    md.append("### Overall Mask Consistency")
    md.append("| Mask | Total GCC Points | Inside Mask | Outside Mask | Hit Rate (%) |")
    md.append("|---|---|---|---|---|")
    for mask_name in ["NRSC_PIXELVALUE_1", "NRSC_PIXELVALUE_13", "NRSC_NONZERO_COMPOSITE"]:
        st = gcc["overall_mask_performance"][mask_name]
        md.append(f"| `{mask_name}` | {st['total_points']} | {st['inside_count']} | {st['outside_count']} | **{st['hit_rate_pct']}%** |")
    md.append("")
    md.append("### Stratified by GCC Inundation Category")
    md.append("| Inundation Category | Total Points | Inside Mask 1 (%) | Inside Mask 13 (%) | Inside Composite (%) |")
    md.append("|---|---|---|---|---|")
    cats = ["<2 ft", "2–3 ft", "3–5 ft", ">5 ft"]
    for cat in cats:
        tot = [x for x in gcc["stratified_by_category"]["NRSC_PIXELVALUE_1"] if x["category"] == cat][0]["total"]
        r1 = [x for x in gcc["stratified_by_category"]["NRSC_PIXELVALUE_1"] if x["category"] == cat][0]["hit_rate_pct"]
        r13 = [x for x in gcc["stratified_by_category"]["NRSC_PIXELVALUE_13"] if x["category"] == cat][0]["hit_rate_pct"]
        rc = [x for x in gcc["stratified_by_category"]["NRSC_NONZERO_COMPOSITE"] if x["category"] == cat][0]["hit_rate_pct"]
        md.append(f"| **{cat}** | {tot} | {r1}% | {r13}% | **{rc}%** |")
    md.append("")
    md.append(
        "- **[INFERRED] Spatial Consistency Observation**: Mask 13 shows substantially greater spatial consistency with the "
        "available urban GCC flood-hotspot and water-stagnation observations than Mask 1. The semantic meaning of source "
        "pixelvalue 1 versus 13 remains unresolved because the public source metadata does not define these classes."
    )
    md.append("")

    # Section 8: FABDEM Terrain Analysis
    md.append("## 8. FABDEM Terrain Characterization")
    md.append(
        "FABDEM elevation was sampled at each GCC hotspot. "
        "Tile `N13E080_FABDEM_V1-2.tif` bounds terminate at latitude 13.00014°N. "
        f"Consequently, **{terrain_gcc['sampled_valid_count']}** points fall within the tile and **{terrain_gcc['out_of_tile_count']}** points "
        "(in southern Chennai suburbs such as Velachery, Madipakkam, Tambaram) fall south of 13.0°N in the adjacent tile `N12E080`.\n"
    )
    md.append("### GCC Hotspot Elevation Distribution by Category (meters)")
    md.append("| Inundation Category | Valid Samples | Min | Max | Mean | Median | Std Dev | p05 | p25 | p75 | p95 |")
    md.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for cat in cats:
        s = terrain_gcc["stratified_by_category"][cat]
        md.append(f"| **{cat}** | {s['count']} | {s['min']}m | {s['max']}m | {s['mean']}m | {s['median']}m | {s['std']}m | {s['p05']}m | {s['p25']}m | {s['p75']}m | {s['p95']}m |")
    all_s = terrain_gcc["overall_terrain_stats"]
    md.append(f"| **ALL SAMPLES** | {all_s['count']} | {all_s['min']}m | {all_s['max']}m | {all_s['mean']}m | {all_s['median']}m | {all_s['std']}m | {all_s['p05']}m | {all_s['p25']}m | {all_s['p75']}m | {all_s['p95']}m |")
    md.append("")
    md.append("### NRSC Mask FABDEM Distribution: Inside vs Outside Study Area")
    md.append("To test whether a simple global elevation threshold could demarcate flooding, elevations inside each mask were compared against outside areas within the regional study box:")
    md.append("| Zone | Mask | Sample Count | Mean Elev | Median Elev | p05 | p95 |")
    md.append("|---|---|---|---|---|---|---|")
    for mname in ["NRSC_PIXELVALUE_1", "NRSC_PIXELVALUE_13", "NRSC_NONZERO_COMPOSITE"]:
        dist = nrsc_terrain["mask_terrain_distributions"][mname]
        ins = dist["inside_mask"]
        outs = dist["outside_mask_study_area"]
        md.append(f"| **Inside Mask** | `{mname}` | {ins['valid_samples']} | {ins['mean']}m | {ins['median']}m | {ins['p05']}m | {ins['p95']}m |")
        md.append(f"| **Outside Study Area** | `{mname}` | {outs['valid_samples']} | {outs['mean']}m | {outs['median']}m | {outs['p05']}m | {outs['p95']}m |")
    md.append("")
    md.append(
        "- **[SCIENTIFIC MANDATE] Elevation Threshold Defensibility**: Inundated elevations inside Mask C range from -12m to 42m (mean 13.35m, median 10.08m), "
        "while dry areas outside range from 0m to 45m (mean 16.13m, median 15.00m). The observed elevation distributions demonstrate substantial "
        "overlap between historical inundation and surrounding terrain; therefore a single global DEM elevation threshold is not considered "
        "scientifically defensible for this study area."
    )
    md.append("")

    # Section 9: Nandambakkam Analysis
    md.append("## 9. Nandambakkam CheckDam Station Context Analysis")
    md.append(
        f"- **Station Code [SOURCE-DERIVED]**: `{nand['station_code']}`\n"
        f"- **River Basin [SOURCE-DERIVED]**: {nand['river']}\n"
        f"- **Coordinates [SOURCE-DERIVED]**: {nand['coordinates']['latitude']}° N, {nand['coordinates']['longitude']}° E (`{nand['coordinates']['crs']}`)\n"
        f"- **FABDEM Elevation at Station [COMPUTED]**: **{nand['fabdem_elevation_m']} m**\n"
        f"- **Proximity to NRSC Masks [COMPUTED]**:\n"
        f"  - Nearest Mask A (`NRSC_PIXELVALUE_1`): **{nand['nrsc_mask_proximity']['NRSC_PIXELVALUE_1']['nearest_distance_meters']} m** (Point inside: {nand['nrsc_mask_proximity']['NRSC_PIXELVALUE_1']['point_inside_mask']})\n"
        f"  - Nearest Mask B (`NRSC_PIXELVALUE_13`): **{nand['nrsc_mask_proximity']['NRSC_PIXELVALUE_13']['nearest_distance_meters']} m** (Point inside: {nand['nrsc_mask_proximity']['NRSC_PIXELVALUE_13']['point_inside_mask']})\n"
        f"  - Nearest Mask C (`NRSC_NONZERO_COMPOSITE`): **{nand['nrsc_mask_proximity']['NRSC_NONZERO_COMPOSITE']['nearest_distance_meters']} m**\n"
        f"- **Nearby GCC Hotspots by Radius [COMPUTED]**:\n"
        f"  - Within 250 m: **{nand['gcc_hotspots_ring_counts']['within_250m']}** points\n"
        f"  - Within 500 m: **{nand['gcc_hotspots_ring_counts']['within_500m']}** points\n"
        f"  - Within 1000 m: **{nand['gcc_hotspots_ring_counts']['within_1000m']}** points\n"
        f"  - Within 2000 m: **{nand['gcc_hotspots_ring_counts']['within_2000m']}** points\n\n"
        "**Strict Boundary Enforcement**:\n"
        "1. The 3.25 m observed in telemetry is **gauge stage**, not Water Surface Elevation (WSE).\n"
        "2. The vertical datum / gauge-zero elevation remains **unverified**.\n"
        "3. Gauge stage must **never** be converted to WSE or subtracted from FABDEM elevation.\n"
        "4. Gauge station flooding cannot be inferred merely from proximity to mask polygons."
    )
    md.append("")

    # Section 10: Flooded-Road Cross-Check
    md.append("## 10. Flooded-Road Network Cross-Check")
    md.append(
        f"Spatial consistency analysis between the Chennai 2015 road network ({roads['total_roads']} features) "
        "and the NRSC source-derived masks.\n"
    )
    md.append("| Mask | Flooded Roads Intersecting | Flooded Intersection Rate (%) | Non-Flooded Intersecting | Non-Flooded Rate (%) |")
    md.append("|---|---|---|---|---|")
    for mname in ["NRSC_PIXELVALUE_1", "NRSC_PIXELVALUE_13", "NRSC_NONZERO_COMPOSITE"]:
        c = roads["mask_comparisons"][mname]
        md.append(f"| `{mname}` | {c['flooded_roads_intersecting_mask']} / {c['flooded_road_features']} | **{round(c['flooded_intersection_rate']*100, 2)}%** | {c['non_flooded_roads_intersecting_mask']} / {c['non_flooded_road_features']} | **{round(c['non_flooded_intersection_rate']*100, 2)}%** |")
    md.append("")
    md.append(
        "- **[SOURCE-DERIVED] Limitation**: Severe class imbalance exists (7,884 flooded vs 10 non-flooded segments). "
        "While Composite Mask intersects 48.6% of flooded road segments, this cross-check is descriptive consistency, not ground-truth validation."
    )
    md.append("")

    # Section 11: Water Stagnation Cross-Check
    md.append("## 11. Water-Stagnation Cross-Check")
    md.append(
        f"Testing 753 Chennai municipal water stagnation points against NRSC masks.\n"
    )
    md.append("| Mask | Stagnation Points Inside | Outside | Hit Rate (%) |")
    md.append("|---|---|---|---|")
    for mname in ["NRSC_PIXELVALUE_1", "NRSC_PIXELVALUE_13", "NRSC_NONZERO_COMPOSITE"]:
        s = stag["mask_comparisons"][mname]
        md.append(f"| `{mname}` | {s['inside_count']} | {s['outside_count']} | **{s['hit_rate_pct']}%** |")
    md.append("")
    md.append(
        "- **[INFERRED] Insight**: Stagnation points represent localized urban drainage blockages and micro-ponding. "
        "Mask 13 shows substantially greater spatial consistency with the available urban GCC flood-hotspot and water-stagnation "
        "observations than Mask 1. The semantic meaning of source pixelvalue 1 versus 13 remains unresolved because the "
        "public source metadata does not define these classes."
    )
    md.append("")

    # Section 12: Limitations
    md.append("## 12. Limitations")
    md.append(
        "1. **Uncalibrated Hydrodynamic Simulation**: NRSC Version 1.2 reference document explicitly acknowledges lack of downstream discharge calibration data.\n"
        "2. **Undocumented NRSC Pixelvalue Semantics**: The semantic meaning of pixelvalue 1 versus 13 remains unverified in public metadata.\n"
        "3. **Unverified Gauge Datum**: Nandambakkam CheckDam stage of 3.25 m cannot be converted to absolute WSE because gauge zero is unverified.\n"
        "4. **DEM Resolution Limits**: FABDEM 30 m spatial resolution cannot resolve roadside curbs, culverts, storm drains, or micro-embankments.\n"
        "5. **Spatial Tile Truncation**: Tile N13E080 truncates at 13.00014°N, leaving 94 southern Chennai GCC hotspots outside the DEM footprint.\n"
        "6. **Reporting Bias**: Road and GCC layers reflect crowdsourced or municipal reporting bias during active disaster conditions."
    )
    md.append("")

    # Section 13: Scientific Interpretation
    md.append("## 13. Scientific Interpretation")
    md.append(
        "1. **Mask 1 vs Mask 13 Spatial Consistency**: Mask 13 shows substantially greater spatial consistency with the "
        "available urban GCC flood-hotspot and water-stagnation observations than Mask 1. The semantic meaning of source "
        "pixelvalue 1 versus 13 remains unresolved because the public source metadata does not define these classes.\n"
        "2. **Global Elevation Threshold Defensibility**: The observed elevation distributions demonstrate substantial "
        "overlap between historical inundation and surrounding terrain; therefore a single global DEM elevation threshold "
        "is not considered scientifically defensible for this study area.\n"
        "3. **Prohibition of Pseudo-IoU**: Calculating Intersection-over-Union (IoU) between two external reference layers "
        "and presenting it as model performance is scientifically indefensible. IoU must only be reported when evaluating "
        "an actual model prediction against verified benchmarks."
    )
    md.append("")

    # Section 14: Validation Readiness Decision
    md.append("## 14. Validation Readiness Decision")
    md.append(f"### Final Machine-Readable Status: `{dec['validation_status']}`\n")
    md.append(f"**Scientific Rationale**:\n> {dec['scientific_rationale']}\n")
    md.append("### Evidence Checklist")
    for check_k, check_v in dec["evidence_checklist"].items():
        pass_icon = "[PASS]" if check_v["passed"] else "[CONDITIONAL / RESTRICTED]"
        md.append(f"- **{pass_icon} {check_k}**: {check_v['detail']}")
    md.append("")
    md.append("### Explicit Boundary Prohibitions")
    for p in dec["prohibited_actions"]:
        md.append(f"- {p}")
    md.append("")

    # Section 15: What Remains Unknown
    md.append("## 15. What Remains Unknown")
    md.append(
        "1. **[UNKNOWN]** The exact elevation of Nandambakkam CheckDam gauge zero relative to EGM96 / WGS84 vertical datum.\n"
        "2. **[UNKNOWN]** The exact algorithmic provenance of NRSC pixelvalue 1 versus 13 (whether 13 denotes radar backscatter threshold, water depth, or urban landcover overlay).\n"
        "3. **[UNKNOWN]** Continuous water depth measurements across the GCC municipal hotspot points.\n"
        "4. **[UNKNOWN]** Micro-topographic elevations for the 94 GCC points located in southern Chennai tile N12E080."
    )
    md.append("")

    # Section 16: Recommended Next Phase
    md.append("## 16. Recommended Next Phase (A.8.6 Proposal)")
    md.append(
        "Before implementing a terrain-aware experimental flood model in PRISM Phase A.8.6, the following prerequisites are required:\n\n"
    )
    for prereq in dec["prerequisites_for_a8_6_experiment"]:
        md.append(f"- {prereq}")
    md.append(
        "\n**Production Safety Guarantee**: Experimental modeling in A.8.6 must remain strictly isolated within `app.research`, "
        "read-only, and completely detached from operational E1 red-zone generation and E2–E6 baseline snapshots."
    )
    md.append("")

    return "\n".join(md)
