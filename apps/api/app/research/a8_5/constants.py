"""PRISM A.8.5 Constants and Controlled Vocabulary.

Enforces scientific boundaries, coordinate systems, and terminology.
"""

from typing import Final

# Scientific terminology (controlled vocabulary)
TERM_HISTORICAL_REFERENCE: Final[str] = "Historical reference layer"
TERM_OBSERVED_POINT: Final[str] = "Observed point evidence"
TERM_SOURCE_DERIVED_MASK: Final[str] = "NRSC source-derived inundation mask"
TERM_TERRAIN_CHAR: Final[str] = "Terrain characterization"
TERM_SPATIAL_CONSISTENCY: Final[str] = "Spatial consistency analysis"
TERM_RESEARCH_PROTOTYPE: Final[str] = "Research prototype"

# Mask Identifiers
MASK_A: Final[str] = "NRSC_PIXELVALUE_1"
MASK_B: Final[str] = "NRSC_PIXELVALUE_13"
MASK_C: Final[str] = "NRSC_NONZERO_COMPOSITE"

# Nandambakkam CheckDam Station
NANDAMBAKKAM_STATION_CODE: Final[str] = "NANDAMBAKKAM_CHECKDAM"
NANDAMBAKKAM_RIVER: Final[str] = "Adyar"
NANDAMBAKKAM_LAT: Final[float] = 13.01611111
NANDAMBAKKAM_LON: Final[float] = 80.18277778
NANDAMBAKKAM_RADIUS_RINGS: Final[list[int]] = [250, 500, 1000, 2000]  # meters

# Coordinate Reference Systems
SOURCE_CRS: Final[str] = "EPSG:4326"
# WGS 84 / UTM zone 44N (covers 78°E to 84°E in Northern Hemisphere including Chennai at ~80.2°E)
METRIC_CRS: Final[str] = "EPSG:32644"
METRIC_CRS_JUSTIFICATION: Final[str] = (
    "EPSG:32644 (WGS 84 / UTM zone 44N) was chosen because Chennai (approx 80.2°E, 13.0°N) "
    "lies centrally within UTM Zone 44N (78°E - 84°E). It preserves conformal angles and provides "
    "accurate metric distances (meters) and areas (square meters) with minimal distortion (<0.1%)."
)

# Standard GCC inundation categories (normalized)
GCC_CATEGORY_LESS_2FT: Final[str] = "<2 ft"
GCC_CATEGORY_2_TO_3FT: Final[str] = "2–3 ft"
GCC_CATEGORY_3_TO_5FT: Final[str] = "3–5 ft"
GCC_CATEGORY_ABOVE_5FT: Final[str] = ">5 ft"

# Decision Status Enums
VALIDATION_READY: Final[str] = "READY_FOR_TERRAIN_EXPERIMENT"
VALIDATION_CONDITIONAL: Final[str] = "CONDITIONAL_TERRAIN_EXPERIMENT"
VALIDATION_NOT_READY: Final[str] = "NOT_READY"

# Expected Default Research Files
DEFAULT_DATA_DIR: Final[str] = "data/research"
DEFAULT_FILES: Final[dict[str, str]] = {
    "fabdem": "N13E080_FABDEM_V1-2.tif",
    "nrsc_kml": "7cb3cecf-a95a-4786-8032-9c7417655d24.kml",
    "gcc_kml": "31523c86-0ad1-42f5-b4d1-297daa4bbcd6.kml",
    "kancheepuram_kml": "3746a11e-620f-40e4-94a1-21ea8fe2a35e.kml",
    "tiruvallur_kml": "d8d3ac1d-b486-4446-bc76-3dff0af8cbdb.kml",
    "stagnation_kml": "db3840ff-9f33-43a3-b826-2f9dae1bcb78.kml",
    "roads_kml": "46d6c279-ae09-43a8-8691-7a5386f69e3a.kml",
    "reference_pdf": "Adayar &Cooum Rivers.pdf",
}
