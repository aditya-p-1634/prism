"""PRISM Phase A.8.5 — Terrain & Historical Flood Validation Research Package.

This package provides an isolated, read-only scientific validation harness:
1. Data provenance manifest generation (SHA-256 auditing)
2. Spatial and geometry QA
3. NRSC class sensitivity analysis (Masks A, B, C)
4. GCC point validation and inundation-category stratification
5. FABDEM terrain characterization at GCC hotspots
6. NRSC mask elevation distributions (inside vs outside study area)
7. Nandambakkam CheckDam station spatial & distance analysis
8. Flooded road network cross-check
9. Water stagnation point cross-check
10. Strict prohibition of pseudo-IoU
11. Evidence-derived validation readiness decision
12. Comprehensive research report and artifact generation

This package strictly preserves scientific boundaries:
- Does NOT convert gauge stage to absolute WSE.
- Does NOT apply DEM bathtub thresholds.
- Does NOT modify production decision logic (E1-E6).
"""

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
    NANDAMBAKKAM_STATION_CODE,
    SOURCE_CRS,
    VALIDATION_CONDITIONAL,
    VALIDATION_NOT_READY,
    VALIDATION_READY,
)
from importlib import import_module


_LAZY_EXPORTS = {
    "evaluate_validation_readiness": ("decision", "evaluate_validation_readiness"),
    "run_gcc_point_validation": ("gcc_analysis", "run_gcc_point_validation"),
    "build_data_manifest": ("manifest", "build_data_manifest"),
    "compute_sha256": ("manifest", "compute_sha256"),
    "run_nandambakkam_analysis": ("nandambakkam_analysis", "run_nandambakkam_analysis"),
    "analyze_nrsc_mask": ("nrsc_analysis", "analyze_nrsc_mask"),
    "load_and_split_nrsc_masks": ("nrsc_analysis", "load_and_split_nrsc_masks"),
    "run_nrsc_class_sensitivity_analysis": ("nrsc_analysis", "run_nrsc_class_sensitivity_analysis"),
    "export_artifacts": ("report", "export_artifacts"),
    "run_road_cross_check": ("road_analysis", "run_road_cross_check"),
    "run_a8_5_harness": ("run", "run_a8_5_harness"),
    "prepare_metric_gdf": ("spatial_qa", "prepare_metric_gdf"),
    "validate_gdf_spatial_qa": ("spatial_qa", "validate_gdf_spatial_qa"),
    "run_stagnation_cross_check": ("stagnation_analysis", "run_stagnation_cross_check"),
    "calculate_distribution_stats": ("terrain_analysis", "calculate_distribution_stats"),
    "run_gcc_terrain_characterization": ("terrain_analysis", "run_gcc_terrain_characterization"),
    "run_nrsc_mask_terrain_distributions": ("terrain_analysis", "run_nrsc_mask_terrain_distributions"),
    "sample_fabdem_at_points": ("terrain_analysis", "sample_fabdem_at_points"),
}


def __getattr__(name: str):
    """Load optional geospatial dependencies only when a feature is used."""
    target = _LAZY_EXPORTS.get(name)
    if target is None:
        raise AttributeError(name)
    module_name, attribute_name = target
    value = getattr(import_module(f"app.research.a8_5.{module_name}"), attribute_name)
    globals()[name] = value
    return value

__all__ = [
    "MASK_A",
    "MASK_B",
    "MASK_C",
    "SOURCE_CRS",
    "METRIC_CRS",
    "NANDAMBAKKAM_LAT",
    "NANDAMBAKKAM_LON",
    "NANDAMBAKKAM_STATION_CODE",
    "GCC_CATEGORY_LESS_2FT",
    "GCC_CATEGORY_2_TO_3FT",
    "GCC_CATEGORY_3_TO_5FT",
    "GCC_CATEGORY_ABOVE_5FT",
    "VALIDATION_READY",
    "VALIDATION_CONDITIONAL",
    "VALIDATION_NOT_READY",
    "build_data_manifest",
    "compute_sha256",
    "validate_gdf_spatial_qa",
    "prepare_metric_gdf",
    "load_and_split_nrsc_masks",
    "analyze_nrsc_mask",
    "run_nrsc_class_sensitivity_analysis",
    "run_gcc_point_validation",
    "sample_fabdem_at_points",
    "calculate_distribution_stats",
    "run_gcc_terrain_characterization",
    "run_nrsc_mask_terrain_distributions",
    "run_nandambakkam_analysis",
    "run_road_cross_check",
    "run_stagnation_cross_check",
    "evaluate_validation_readiness",
    "export_artifacts",
    "run_a8_5_harness",
]
