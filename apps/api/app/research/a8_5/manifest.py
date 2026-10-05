"""PRISM A.8.5 Data Provenance Manifest.

Generates an immutable, auditable provenance manifest for all research datasets:
- File metadata, SHA-256 hash
- Provider, acquisition context, CRS, geometry, feature count
- Temporal and event context
- Known limitations and caveats

Ensures research datasets are never modified, overwritten, or silently renamed.
"""

from __future__ import annotations

import hashlib
import os
from typing import Any

import geopandas as gpd
import rasterio

from app.research.a8_5.constants import DEFAULT_DATA_DIR, DEFAULT_FILES


def compute_sha256(filepath: str) -> str:
    """Calculate the SHA-256 cryptographic hash of a file deterministically."""
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            sha256.update(chunk)
    return sha256.hexdigest()


def inspect_vector_dataset(filepath: str) -> dict[str, Any]:
    """Inspect vector dataset properties without mutating the file."""
    gdf = gpd.read_file(filepath)
    geom_types = gdf.geom_type.value_counts().to_dict()
    bounds = [float(b) for b in gdf.total_bounds] if len(gdf) > 0 else []
    
    return {
        "crs": str(gdf.crs) if gdf.crs else "UNKNOWN",
        "feature_count": int(len(gdf)),
        "geometry_types": geom_types,
        "fields": [str(c) for c in gdf.columns if c != "geometry"],
        "bounding_box": {
            "minx": bounds[0] if bounds else None,
            "miny": bounds[1] if bounds else None,
            "maxx": bounds[2] if bounds else None,
            "maxy": bounds[3] if bounds else None,
        },
    }


def inspect_raster_dataset(filepath: str) -> dict[str, Any]:
    """Inspect raster dataset properties without mutating the file."""
    with rasterio.open(filepath) as src:
        bounds = src.bounds
        return {
            "crs": str(src.crs) if src.crs else "UNKNOWN",
            "dimensions": {"width": int(src.width), "height": int(src.height), "bands": int(src.count)},
            "resolution": [float(r) for r in src.res],
            "dtype": str(src.dtypes[0]),
            "nodata": float(src.nodata) if src.nodata is not None else None,
            "bounding_box": {
                "minx": float(bounds.left),
                "miny": float(bounds.bottom),
                "maxx": float(bounds.right),
                "maxy": float(bounds.top),
            },
        }


def build_data_manifest(data_dir: str = DEFAULT_DATA_DIR, custom_paths: dict[str, str] | None = None) -> dict[str, Any]:
    """Build the comprehensive provenance manifest for all 8 research files."""
    paths = dict(DEFAULT_FILES)
    if custom_paths:
        paths.update({k: v for k, v in custom_paths.items() if v})

    datasets: dict[str, Any] = {}

    for key, filename in paths.items():
        # Check if filename is an absolute path or relative to data_dir
        if os.path.isabs(filename):
            full_path = filename
            basename = os.path.basename(filename)
        else:
            full_path = os.path.join(data_dir, filename)
            basename = filename

        if not os.path.exists(full_path):
            datasets[key] = {
                "filename": basename,
                "path": full_path,
                "status": "MISSING",
                "sha256": None,
                "error": f"File not found at {full_path}",
            }
            continue

        file_size = os.path.getsize(full_path)
        sha256_hash = compute_sha256(full_path)

        meta: dict[str, Any] = {
            "filename": basename,
            "path": os.path.abspath(full_path),
            "status": "AVAILABLE",
            "sha256": sha256_hash,
            "file_size_bytes": file_size,
        }

        # Detailed dataset context
        if key == "fabdem":
            raster_meta = inspect_raster_dataset(full_path)
            meta.update(raster_meta)
            meta.update({
                "source_provider": "University of Bristol / FATHOM (FABDEM v1-2)",
                "acquisition_provenance": (
                    "FABDEM v1-2 (Forest and Buildings removed Copernicus DEM). "
                    "Global bare-earth DEM correcting Copernicus GLO-30 DSM via machine learning."
                ),
                "geometry_type": "Raster / GeoTIFF",
                "feature_count": raster_meta["dimensions"]["width"] * raster_meta["dimensions"]["height"],
                "relevant_fields": ["elevation (meters above WGS84/EGM96)"],
                "temporal_event_context": "Static baseline terrain representation (derived from 2011-2015 satellite imagery).",
                "known_limitations": (
                    "1. Approximately 30 m spatial resolution obscures narrow channels, roadside ditches, and micro-embankments. "
                    "2. Tile N13E080 covers 13.0°N to 14.0°N; southern Chennai (Velachery, Madipakkam, Tambaram, Pallikaranai) "
                    "falls south of 13.0°N in tile N12E080 (not present in dataset). "
                    "3. Vertical accuracy is typically ±1-2 m, which can lead to significant error in low-gradient coastal floodplains."
                ),
            })
        elif key == "nrsc_kml":
            vec_meta = inspect_vector_dataset(full_path)
            meta.update(vec_meta)
            meta.update({
                "source_provider": "National Remote Sensing Centre (NRSC) / Indian Space Research Organisation (ISRO)",
                "acquisition_provenance": (
                    "Vectorized flood inundation zone polygons derived from satellite radar/optical observations and "
                    "hydrodynamic simulation of the Adyar and Cooum river basins for the Dec 2015 Chennai flood disaster."
                ),
                "relevant_fields": ["id", "area", "perimeter", "pixelvalue", "geometry"],
                "temporal_event_context": "Peak Chennai flood event, November 29 – December 07, 2015.",
                "known_limitations": (
                    "1. Official NRSC reference report explicitly states that no downstream discharge data was available, "
                    "so hydrodynamic simulation could not be calibrated against field discharge. "
                    "2. Public metadata does not document the semantic distinction between pixelvalue=1 and pixelvalue=13. "
                    "3. Polygons represent a composite satellite/model view, NOT verified ground truth."
                ),
            })
        elif key == "gcc_kml":
            vec_meta = inspect_vector_dataset(full_path)
            meta.update(vec_meta)
            meta.update({
                "source_provider": "Greater Chennai Corporation (GCC)",
                "acquisition_provenance": (
                    "Municipal flood hotspot survey compiled by GCC disaster management teams during and immediately "
                    "following the December 2015 Chennai floods."
                ),
                "relevant_fields": ["location", "inundation_level", "vulnerability", "inundation_ft", "latitude", "longitude", "zone", "ward"],
                "temporal_event_context": "December 2015 Chennai flood event municipal relief records.",
                "known_limitations": (
                    "1. Point observations typically represent road intersections or municipal landmarks, not entire inundated footprints. "
                    "2. Depth categories (<2ft, 2-3ft, 3-5ft, >5ft) are qualitative municipal triage bins, not survey-grade stage readings. "
                    "3. Reporting density is uneven across GCC administrative zones."
                ),
            })
        elif key == "kancheepuram_kml":
            vec_meta = inspect_vector_dataset(full_path)
            meta.update(vec_meta)
            meta.update({
                "source_provider": "Tamil Nadu District Administration (Kancheepuram District)",
                "acquisition_provenance": "District disaster management relief hotspot inventory with taluka and escape routes.",
                "relevant_fields": ["sl_no_", "taluka", "vulnerability", "details", "inundation", "escape_route", "distance"],
                "temporal_event_context": "2015 Chennai & Peri-urban flood event.",
                "known_limitations": "Qualitative vulnerability classifications; rural/peri-urban focus outside GCC boundary.",
            })
        elif key == "tiruvallur_kml":
            vec_meta = inspect_vector_dataset(full_path)
            meta.update(vec_meta)
            meta.update({
                "source_provider": "Tamil Nadu District Administration (Tiruvallur District)",
                "acquisition_provenance": "District disaster management flood hotspot inventory for northern peri-urban fringe.",
                "relevant_fields": ["sl", "name_municipality", "details", "vulnerability", "name_region"],
                "temporal_event_context": "2015 Chennai & Peri-urban flood event.",
                "known_limitations": "Qualitative classifications; spatial points represent settlements rather than surveyed inundation depths.",
            })
        elif key == "stagnation_kml":
            vec_meta = inspect_vector_dataset(full_path)
            meta.update(vec_meta)
            meta.update({
                "source_provider": "Greater Chennai Corporation / Smart City Initiative",
                "acquisition_provenance": "Catalog of persistent urban water stagnation and drainage bottleneck locations.",
                "relevant_fields": ["ZONE", "DIVISION", "LAT", "LONG_"],
                "temporal_event_context": "Historical monsoon drainage congestion records.",
                "known_limitations": "Captures local micro-drainage failures and ponding, which may be independent of riverine overflow.",
            })
        elif key == "roads_kml":
            vec_meta = inspect_vector_dataset(full_path)
            meta.update(vec_meta)
            meta.update({
                "source_provider": "OpenStreetMap / Disaster GIS Volunteer Community (Chennai 2015)",
                "acquisition_provenance": "Vector road network tagged during the 2015 emergency response with flood disruption status.",
                "relevant_fields": ["class", "oneway", "osm_id", "type", "is_flooded", "area", "length"],
                "temporal_event_context": "Emergency response period, December 2015.",
                "known_limitations": (
                    "1. Severe class imbalance (7884 flooded vs 10 non-flooded segments). "
                    "2. Lacks depth, velocity, or inundation duration information. "
                    "3. Crowdsourced volunteer compilation subject to uneven reporting."
                ),
            })
        elif key == "reference_pdf":
            meta.update({
                "crs": "N/A (Document)",
                "geometry_type": "Technical Report / PDF",
                "feature_count": 8,  # pages
                "relevant_fields": ["hydrological modeling", "basin setup", "peak discharge", "velocity head"],
                "source_provider": "National Remote Sensing Centre (NRSC) / Indian Space Research Organisation (ISRO)",
                "acquisition_provenance": (
                    "Technical report: 'Hydrological Simulation Study of Flood Disaster in Adyar and Cooum Rivers, Tamilnadu', "
                    "Version 1.2, dated 07 December 2015."
                ),
                "temporal_event_context": "Adyar and Cooum basin simulations for flood disaster November 21 - December 08, 2015.",
                "known_limitations": (
                    "Document explicitly confirms no field rainfall or downstream discharge calibration data existed "
                    "during the event, validating that model output is an uncalibrated simulation."
                ),
            })

        datasets[key] = meta

    return {
        "manifest_version": "A.8.5.1",
        "description": "PRISM A.8.5 Terrain & Historical Flood Validation Research Manifest",
        "generated_by": "PRISM A.8.5 Provenance Engine",
        "datasets": datasets,
    }
