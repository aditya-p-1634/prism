"""PRISM A.8.5 Flooded Road Network Cross-Check Module.

Implements Objective 7:
- Spatially evaluates the Chennai 2015 road network (7894 features) against NRSC masks:
    NRSC_PIXELVALUE_1
    NRSC_PIXELVALUE_13
    NRSC_NONZERO_COMPOSITE
- Preserves raw `is_flooded` attribute (7884 flooded vs 10 non-flooded).
- Calculates feature intersections and intersection rates stratified by `is_flooded` class.
- Governed by controlled vocabulary: "Spatial consistency analysis" (NOT ground truth).
"""

from __future__ import annotations

from typing import Any
import geopandas as gpd

from app.research.a8_5.constants import (
    MASK_A,
    MASK_B,
    MASK_C,
    SOURCE_CRS,
    TERM_HISTORICAL_REFERENCE,
    TERM_SPATIAL_CONSISTENCY,
)


def run_road_cross_check(
    roads_kml_path: str,
    nrsc_masks: dict[str, gpd.GeoDataFrame],
) -> dict[str, Any]:
    """Perform spatial consistency cross-check between roads and NRSC inundation masks."""
    roads_gdf = gpd.read_file(roads_kml_path)
    if roads_gdf.crs is None:
        roads_gdf.set_crs(SOURCE_CRS, inplace=True)

    total_roads = len(roads_gdf)
    flooded_mask = roads_gdf["is_flooded"] == 1
    non_flooded_mask = roads_gdf["is_flooded"] == 0

    total_flooded = int(flooded_mask.sum())
    total_non_flooded = int(non_flooded_mask.sum())

    roads_clean = roads_gdf.reset_index(drop=True)

    mask_results: dict[str, dict[str, Any]] = {}

    for mask_name in [MASK_A, MASK_B, MASK_C]:
        mask_gdf = nrsc_masks[mask_name]

        # Spatial join to find intersecting roads
        joined = gpd.sjoin(roads_clean, mask_gdf, predicate="intersects", how="inner")
        intersecting_indices = set(joined.index.unique())

        flooded_intersecting = sum(1 for idx in intersecting_indices if flooded_mask.iloc[idx])
        flooded_outside = total_flooded - flooded_intersecting

        non_flooded_intersecting = sum(1 for idx in intersecting_indices if non_flooded_mask.iloc[idx])
        non_flooded_outside = total_non_flooded - non_flooded_intersecting

        flooded_rate = (flooded_intersecting / total_flooded) if total_flooded > 0 else 0.0
        non_flooded_rate = (non_flooded_intersecting / total_non_flooded) if total_non_flooded > 0 else 0.0
        overall_rate = (len(intersecting_indices) / total_roads) if total_roads > 0 else 0.0

        mask_results[mask_name] = {
            "total_road_features": total_roads,
            "flooded_road_features": total_flooded,
            "non_flooded_road_features": total_non_flooded,
            "flooded_roads_intersecting_mask": flooded_intersecting,
            "flooded_roads_outside_mask": flooded_outside,
            "non_flooded_roads_intersecting_mask": non_flooded_intersecting,
            "non_flooded_roads_outside_mask": non_flooded_outside,
            "flooded_intersection_rate": round(flooded_rate, 4),
            "non_flooded_intersection_rate": round(non_flooded_rate, 4),
            "overall_intersection_rate": round(overall_rate, 4),
        }

    return {
        "analysis_type": TERM_SPATIAL_CONSISTENCY,
        "dataset_role": TERM_HISTORICAL_REFERENCE,
        "total_roads": total_roads,
        "class_breakdown": {
            "is_flooded_1": total_flooded,
            "is_flooded_0": total_non_flooded,
        },
        "mask_comparisons": mask_results,
        "scientific_interpretation": (
            "Cross-dataset consistency check only. The road dataset exhibits extreme class imbalance "
            "(7,884 flooded vs 10 non-flooded), reflecting emergency tagging biased towards disrupted links. "
            "It cannot serve as an independent negative control or balanced ground truth."
        ),
    }
