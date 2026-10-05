"""PRISM A.8.5 GCC Hotspot Point Validation Module.

Implements Objective 3:
- Tests 327 GCC flood hotspot points against NRSC masks:
    NRSC_PIXELVALUE_1
    NRSC_PIXELVALUE_13
    NRSC_NONZERO_COMPOSITE
- Stratifies by municipal inundation category:
    <2 ft, 2–3 ft, 3–5 ft, >5 ft
- Preserves raw point coordinates, categories, and attributes.
- Governed by controlled vocabulary: "Spatial consistency analysis" (NOT accuracy/ground truth).
"""

from __future__ import annotations

from typing import Any
import geopandas as gpd

from app.research.a8_5.constants import (
    GCC_CATEGORY_2_TO_3FT,
    GCC_CATEGORY_3_TO_5FT,
    GCC_CATEGORY_ABOVE_5FT,
    GCC_CATEGORY_LESS_2FT,
    MASK_A,
    MASK_B,
    MASK_C,
    SOURCE_CRS,
    TERM_OBSERVED_POINT,
    TERM_SPATIAL_CONSISTENCY,
)


def normalize_gcc_category(raw_val: str | None) -> str:
    """Normalize GCC inundation level string into standard stratified category."""
    if not raw_val:
        return "UNKNOWN"
    s = raw_val.strip().replace("\n", " ").lower()
    if "less than 2" in s or "<2" in s or "less 2" in s:
        return GCC_CATEGORY_LESS_2FT
    elif "2 to 3" in s or "2-3" in s:
        return GCC_CATEGORY_2_TO_3FT
    elif "3 to 5" in s or "3-5" in s:
        return GCC_CATEGORY_3_TO_5FT
    elif "above 5" in s or ">5" in s or "greater than 5" in s:
        return GCC_CATEGORY_ABOVE_5FT
    return raw_val.strip()


def run_gcc_point_validation(
    gcc_kml_path: str,
    nrsc_masks: dict[str, gpd.GeoDataFrame],
) -> dict[str, Any]:
    """Perform spatial consistency analysis comparing GCC points to NRSC inundation masks."""
    gcc_gdf = gpd.read_file(gcc_kml_path)
    if gcc_gdf.crs is None:
        gcc_gdf.set_crs(SOURCE_CRS, inplace=True)

    total_gcc_points = len(gcc_gdf)
    gcc_gdf["norm_category"] = gcc_gdf["inundation_level"].apply(normalize_gcc_category)

    # Perform point-in-polygon tests using spatial joins
    # Make sure we use a clean index
    gcc_clean = gcc_gdf.reset_index(drop=True).copy()

    # Pre-index mask matches
    mask_matches: dict[str, set[int]] = {}
    for mask_name in [MASK_A, MASK_B, MASK_C]:
        mask_gdf = nrsc_masks[mask_name]
        join = gpd.sjoin(gcc_clean, mask_gdf, predicate="intersects", how="inner")
        mask_matches[mask_name] = set(join.index.unique())

    # Build per-point audit records
    point_records: list[dict[str, Any]] = []
    for idx, row in gcc_clean.iterrows():
        in_a = idx in mask_matches[MASK_A]
        in_b = idx in mask_matches[MASK_B]
        in_c = idx in mask_matches[MASK_C]

        geom = row.geometry
        point_records.append({
            "point_id": int(idx),
            "location": str(row.get("location", "")),
            "latitude": float(geom.y),
            "longitude": float(geom.x),
            "raw_inundation_level": str(row.get("inundation_level", "")),
            "norm_category": row["norm_category"],
            "vulnerability": str(row.get("vulnerability", "")),
            "inundation_ft": str(row.get("inundation_ft", "")),
            "zone": str(row.get("zone", "")),
            "ward": str(row.get("ward", "")),
            f"inside_{MASK_A}": in_a,
            f"inside_{MASK_B}": in_b,
            f"inside_{MASK_C}": in_c,
        })

    # Overall mask hit rates
    overall_stats: dict[str, dict[str, Any]] = {}
    for mask_name in [MASK_A, MASK_B, MASK_C]:
        inside_cnt = len(mask_matches[mask_name])
        outside_cnt = total_gcc_points - inside_cnt
        hit_rate = inside_cnt / total_gcc_points if total_gcc_points > 0 else 0.0
        overall_stats[mask_name] = {
            "total_points": total_gcc_points,
            "inside_count": inside_cnt,
            "outside_count": outside_cnt,
            "hit_rate": round(hit_rate, 4),
            "hit_rate_pct": round(hit_rate * 100.0, 2),
        }

    # Stratified analysis by inundation category
    ordered_categories = [
        GCC_CATEGORY_LESS_2FT,
        GCC_CATEGORY_2_TO_3FT,
        GCC_CATEGORY_3_TO_5FT,
        GCC_CATEGORY_ABOVE_5FT,
    ]

    stratified_stats: dict[str, list[dict[str, Any]]] = {}
    for mask_name in [MASK_A, MASK_B, MASK_C]:
        cat_list: list[dict[str, Any]] = []
        for cat in ordered_categories:
            cat_points = [p for p in point_records if p["norm_category"] == cat]
            cat_total = len(cat_points)
            cat_inside = sum(1 for p in cat_points if p[f"inside_{mask_name}"])
            cat_outside = cat_total - cat_inside
            cat_hit_rate = cat_inside / cat_total if cat_total > 0 else 0.0

            cat_list.append({
                "category": cat,
                "total": cat_total,
                "inside": cat_inside,
                "outside": cat_outside,
                "hit_rate": round(cat_hit_rate, 4),
                "hit_rate_pct": round(cat_hit_rate * 100.0, 2),
            })
        stratified_stats[mask_name] = cat_list

    return {
        "analysis_type": TERM_SPATIAL_CONSISTENCY,
        "evidence_type": TERM_OBSERVED_POINT,
        "total_gcc_points": total_gcc_points,
        "overall_mask_performance": overall_stats,
        "stratified_by_category": stratified_stats,
        "point_records": point_records,
        "scientific_interpretation": (
            "This spatial consistency test measures agreement between municipal point incident reports "
            "and remote-sensing derived inundation polygons. It is NOT a ground-truth accuracy benchmark, "
            "because GCC points represent localized reporting centroids while NRSC polygons capture contiguous "
            "inundated footprints."
        ),
    }
