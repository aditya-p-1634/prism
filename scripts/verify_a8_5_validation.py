"""PRISM Phase A.8.5 — Terrain & Historical Flood Validation Demonstration.
========================================================================
Verification script fulfilling all A.8.5 demo requirements:
1. Loads all 8 research datasets (FABDEM, NRSC, GCC, Kancheepuram, Tiruvallur, Stagnation, Roads, PDF).
2. Validates provenance and SHA-256 cryptographic checksums.
3. Validates CRS (EPSG:4326) and topological validity.
4. Builds the three explicitly named NRSC masks (Mask 1, Mask 13, Composite).
5. Runs GCC hotspot point-in-polygon validation and category stratification.
6. Samples FABDEM terrain elevation and computes distributions.
7. Analyzes Nandambakkam CheckDam station context and strict scientific boundaries.
8. Cross-checks flooded road network segments.
9. Cross-checks water stagnation incident points.
10. Prints the evidence-derived validation readiness decision.
11. Writes all JSON, Markdown, and CSV artifacts.
12. Exits non-zero on data-integrity failure. Does not silently skip missing datasets.
"""

from __future__ import annotations

import os
import sys

# Ensure apps/api is on sys.path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
API_DIR = os.path.join(REPO_ROOT, "apps", "api")
if API_DIR not in sys.path:
    sys.path.insert(0, API_DIR)

from app.research.a8_5.constants import (
    DEFAULT_FILES,
    MASK_A,
    MASK_B,
    MASK_C,
    VALIDATION_NOT_READY,
)
from app.research.a8_5.run import run_a8_5_harness


def main() -> None:
    print("=" * 80)
    print("  PRISM PHASE A.8.5 VERIFICATION DEMONSTRATION")
    print("  Terrain & Historical Flood Validation Harness")
    print("=" * 80)

    # Locate research directory
    data_dir = os.path.join(REPO_ROOT, "data", "research")
    if not os.path.exists(data_dir):
        print(f"[FATAL] Research data directory not found: {data_dir}", file=sys.stderr)
        sys.exit(1)

    # Verify no datasets are missing upfront
    missing = []
    for key, fname in DEFAULT_FILES.items():
        fpath = os.path.join(data_dir, fname)
        if not os.path.exists(fpath):
            missing.append((key, fname, fpath))

    if missing:
        print(f"[FATAL] Cannot run verification: {len(missing)} dataset(s) missing!", file=sys.stderr)
        for k, fn, fp in missing:
            print(f"  - Missing {k}: {fn} ({fp})", file=sys.stderr)
        sys.exit(1)

    print(f"[OK] All {len(DEFAULT_FILES)} research datasets present in {data_dir}.")

    # Output artifact locations
    output_dir = os.path.join(REPO_ROOT, "docs", "research", "artifacts")
    report_markdown = os.path.join(REPO_ROOT, "docs", "research", "A8_5_TERRAIN_FLOOD_VALIDATION.md")

    # Run the comprehensive harness
    results = run_a8_5_harness(
        data_dir=data_dir,
        output_dir=output_dir,
        report_markdown_path=report_markdown,
    )

    decision = results["decision"]
    status = decision["validation_status"]

    print("\n" + "=" * 80)
    print(f"  VERIFICATION STATUS: {status}")
    print("=" * 80)
    print("  Evidence Highlights:")
    print(f"  - NRSC Mask 1 (pixelvalue=1):    {results['nrsc']['masks'][MASK_A]['feature_count']} features, Area: {results['nrsc']['masks'][MASK_A]['area_sq_km']} km²")
    print(f"  - NRSC Mask 13 (pixelvalue=13):  {results['nrsc']['masks'][MASK_B]['feature_count']} features, Area: {results['nrsc']['masks'][MASK_B]['area_sq_km']} km²")
    print(f"  - NRSC Composite (pixelvalue 1,13): {results['nrsc']['masks'][MASK_C]['feature_count']} features, Area: {results['nrsc']['masks'][MASK_C]['area_sq_km']} km²")
    print(f"  - GCC Points Inside Mask 1:      {results['gcc']['overall_mask_performance'][MASK_A]['inside_count']}/327 ({results['gcc']['overall_mask_performance'][MASK_A]['hit_rate_pct']}%)")
    print(f"  - GCC Points Inside Mask 13:     {results['gcc']['overall_mask_performance'][MASK_B]['inside_count']}/327 ({results['gcc']['overall_mask_performance'][MASK_B]['hit_rate_pct']}%)")
    print(f"  - GCC Points Inside Composite:   {results['gcc']['overall_mask_performance'][MASK_C]['inside_count']}/327 ({results['gcc']['overall_mask_performance'][MASK_C]['hit_rate_pct']}%)")
    print(f"  - Nandambakkam Station Elev:     {results['nandambakkam']['fabdem_elevation_m']} m")
    print(f"  - Nandambakkam -> Mask A Dist:   {results['nandambakkam']['nrsc_mask_proximity'][MASK_A]['nearest_distance_meters']} m")
    print(f"  - Nandambakkam 2km GCC Count:    {len(results['nandambakkam']['nearby_gcc_observations_2000m'])} points")
    print(f"  - Flooded Roads Composite Hit:   {results['roads']['mask_comparisons'][MASK_C]['flooded_roads_intersecting_mask']}/7884 ({results['roads']['mask_comparisons'][MASK_C]['flooded_intersection_rate']*100:.2f}%)")
    print(f"  - Stagnation Composite Hit:      {results['stagnation']['mask_comparisons'][MASK_C]['inside_count']}/753 ({results['stagnation']['mask_comparisons'][MASK_C]['hit_rate_pct']}%)")
    print(f"  - Prediction Mask Present:       {decision['evidence_checklist']['prediction_mask_present']['passed']}")
    print(f"  - IoU Reported:                  STRICTLY NONE (Prohibited without prediction mask)")
    print("=" * 80)

    if status == VALIDATION_NOT_READY:
        print("[FAIL] Validation status NOT_READY indicates integrity failure.", file=sys.stderr)
        sys.exit(1)

    print("\n[SUCCESS] A.8.5 verification demo passed all assertions successfully.")


if __name__ == "__main__":
    main()
