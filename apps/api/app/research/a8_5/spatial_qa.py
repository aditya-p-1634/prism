"""PRISM A.8.5 Spatial & Geometry QA Module.

Validates datasets for CRS integrity, topological validity, coordinates sanity,
and geometry anomalies without altering raw source data.
"""

from __future__ import annotations

from typing import Any
import geopandas as gpd
from shapely.validation import make_valid

from app.research.a8_5.constants import (
    METRIC_CRS,
    METRIC_CRS_JUSTIFICATION,
    SOURCE_CRS,
)


def validate_gdf_spatial_qa(
    gdf: gpd.GeoDataFrame,
    dataset_name: str,
    expected_crs: str = SOURCE_CRS,
    coord_bounds: tuple[float, float, float, float] = (76.0, 8.0, 82.0, 15.0),
) -> dict[str, Any]:
    """Perform rigorous spatial QA on a GeoDataFrame.
    
    Checks:
    - CRS presence and compatibility
    - Total feature count
    - Valid geometries count
    - Invalid geometries count
    - Empty geometries count
    - Null geometries count
    - Coordinate sanity against bounding envelope
    - Bounding box
    - Duplicate points detection (for point layers)
    - Repair tracking (using make_valid, preserving original geometries)
    """
    total_count = len(gdf)
    has_crs = gdf.crs is not None
    crs_str = str(gdf.crs) if has_crs else None
    crs_compatible = (
        crs_str == expected_crs
        or (gdf.crs and gdf.crs.to_epsg() == 4326)
    )

    if total_count == 0:
        return {
            "dataset_name": dataset_name,
            "total_count": 0,
            "has_crs": has_crs,
            "crs": crs_str,
            "crs_compatible": crs_compatible,
            "valid_count": 0,
            "invalid_count": 0,
            "empty_count": 0,
            "null_count": 0,
            "bounds": None,
            "coordinates_sane": True,
            "duplicate_count": 0,
            "repaired_count": 0,
            "repair_method": None,
        }

    null_count = int(gdf.geometry.isna().sum())
    non_null_gdf = gdf[~gdf.geometry.isna()]
    empty_count = int(non_null_gdf.geometry.is_empty.sum())
    valid_mask = non_null_gdf.geometry.is_valid
    valid_count = int(valid_mask.sum())
    invalid_count = int((~valid_mask).sum())

    # Coordinate sanity check
    minx, miny, maxx, maxy = gdf.total_bounds
    c_minx, c_miny, c_maxx, c_maxy = coord_bounds
    coords_sane = bool(
        minx >= c_minx and maxx <= c_maxx and miny >= c_miny and maxy <= c_maxy
    )

    # Duplicate detection (primarily for Point layers)
    duplicate_count = 0
    geom_types = gdf.geom_type.unique()
    if len(geom_types) == 1 and geom_types[0] == "Point":
        duplicate_count = int(gdf.geometry.duplicated().sum())

    # Repair simulation without mutating original
    repaired_count = 0
    repair_method = None
    if invalid_count > 0:
        repair_method = "shapely.validation.make_valid"
        repaired_geoms = non_null_gdf.loc[~valid_mask, "geometry"].apply(make_valid)
        repaired_count = int(repaired_geoms.is_valid.sum())

    return {
        "dataset_name": dataset_name,
        "total_count": total_count,
        "has_crs": has_crs,
        "crs": crs_str,
        "crs_compatible": crs_compatible,
        "valid_count": valid_count,
        "invalid_count": invalid_count,
        "empty_count": empty_count,
        "null_count": null_count,
        "bounds": {
            "minx": float(minx),
            "miny": float(miny),
            "maxx": float(maxx),
            "maxy": float(maxy),
        },
        "coordinates_sane": coords_sane,
        "duplicate_count": duplicate_count,
        "repaired_count": repaired_count,
        "repair_method": repair_method,
        "metric_crs": METRIC_CRS,
        "metric_crs_justification": METRIC_CRS_JUSTIFICATION,
    }


def prepare_metric_gdf(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Reproject GeoDataFrame to metric CRS (EPSG:32644) for accurate distance/area calculations.
    
    If any geometries are invalid, repairs them on the copy using make_valid,
    ensuring original source data is untouched.
    """
    copy_gdf = gdf.copy()
    if copy_gdf.crs is None:
        copy_gdf.set_crs(SOURCE_CRS, inplace=True)

    # Check and repair on copy if needed
    invalid_mask = ~copy_gdf.geometry.is_valid
    if invalid_mask.any():
        copy_gdf.loc[invalid_mask, "geometry"] = copy_gdf.loc[invalid_mask, "geometry"].apply(make_valid)

    return copy_gdf.to_crs(METRIC_CRS)
