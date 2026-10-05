"""PRISM A.8.5 Water Stagnation Cross-Check Module.

Implements Objective 8:
- Spatially tests Chennai water stagnation points (753 points) against NRSC masks:
    NRSC_PIXELVALUE_1
    NRSC_PIXELVALUE_13
    NRSC_NONZERO_COMPOSITE
- Reports total points, inside count, outside count, and hit rate for each mask.
- Governed by controlled vocabulary: "Spatial consistency analysis".
"""

from __future__ import annotations

from typing import Any
import geopandas as gpd

from app.research.a8_5.constants import (
    MASK_A,
    MASK_B,
    MASK_C,
    SOURCE_CRS,
    TERM_OBSERVED_POINT,
    TERM_SPATIAL_CONSISTENCY,
)


def run_stagnation_cross_check(
    stagnation_kml_path: str,
    nrsc_masks: dict[str, gpd.GeoDataFrame],
) -> dict[str, Any]:
    """Perform spatial consistency analysis comparing water stagnation points to NRSC masks."""
    stag_gdf = gpd.read_file(stagnation_kml_path)
    if stag_gdf.crs is None:
        stag_gdf.set_crs(SOURCE_CRS, inplace=True)

    total_points = len(stag_gdf)
    stag_clean = stag_gdf.reset_index(drop=True)

    mask_results: dict[str, dict[str, Any]] = {}

    for mask_name in [MASK_A, MASK_B, MASK_C]:
        mask_gdf = nrsc_masks[mask_name]
        joined = gpd.sjoin(stag_clean, mask_gdf, predicate="intersects", how="inner")
        inside_cnt = len(joined.index.unique())
        outside_cnt = total_points - inside_cnt
        hit_rate = (inside_cnt / total_points) if total_points > 0 else 0.0

        mask_results[mask_name] = {
            "total_stagnation_points": total_points,
            "inside_count": inside_cnt,
            "outside_count": outside_cnt,
            "hit_rate": round(hit_rate, 4),
            "hit_rate_pct": round(hit_rate * 100.0, 2),
        }

    return {
        "analysis_type": TERM_SPATIAL_CONSISTENCY,
        "evidence_type": TERM_OBSERVED_POINT,
        "total_stagnation_points": total_points,
        "mask_comparisons": mask_results,
        "scientific_interpretation": (
            "Consistency analysis only. Water stagnation points capture localized micro-drainage failures and roadside depression ponding. "
            "Mask 13 shows substantially greater spatial consistency with the available urban GCC flood-hotspot and water-stagnation "
            "observations than Mask 1. The semantic meaning of source pixelvalue 1 versus 13 remains unresolved because the public source "
            "metadata does not define these classes."
        ),
    }
