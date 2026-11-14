"""Phase 17: bounded integration of telemetry with historical spatial evidence.

This module deliberately does not create flood labels.  The telemetry period and
the historical spatial layers are different time periods, so the output is a
spatial/context audit rather than a supervised truth table.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import geopandas as gpd
from shapely.geometry import Point

from app.research.a8_5.constants import METRIC_CRS, SOURCE_CRS


def _load_vector(path: Path) -> gpd.GeoDataFrame:
    gdf = gpd.read_file(path)
    if gdf.crs is None:
        gdf = gdf.set_crs(SOURCE_CRS)
    return gdf


def _parse_telemetry_bounds(path: Path) -> tuple[str, str, int]:
    import csv

    values: list[datetime] = []
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            values.append(datetime.fromisoformat(row["observed_at"].replace("Z", "+00:00")))
    if not values:
        raise ValueError("canonical telemetry contains no rows")
    return min(values).isoformat(), max(values).isoformat(), len(values)


def build_spatial_event_evidence(
    canonical_telemetry_path: str | Path,
    gcc_path: str | Path,
    nrsc_path: str | Path,
    roads_path: str | Path,
    station_lon: float = 80.18277778,
    station_lat: float = 13.01611111,
    event_start: str = "2015-11-29",
    event_end: str = "2015-12-07",
) -> dict[str, Any]:
    """Summarize the safe, non-labeling relationship between source assets."""
    telemetry_start, telemetry_end, telemetry_rows = _parse_telemetry_bounds(Path(canonical_telemetry_path))
    station = gpd.GeoDataFrame(
        [{"station_code": "NANDAMBAKKAM_CHECKDAM"}],
        geometry=[Point(station_lon, station_lat)],
        crs=SOURCE_CRS,
    ).to_crs(METRIC_CRS)
    station_point = station.geometry.iloc[0]

    gcc = _load_vector(Path(gcc_path)).to_crs(METRIC_CRS)
    nrsc = _load_vector(Path(nrsc_path)).to_crs(METRIC_CRS)
    roads = _load_vector(Path(roads_path)).to_crs(METRIC_CRS)

    gcc_distance = gcc.geometry.distance(station_point)
    nrsc_contains = nrsc.geometry.intersects(station_point)
    road_status = roads["is_flooded"].astype(str).str.lower().value_counts().to_dict() if "is_flooded" in roads else {}

    return {
        "report_version": "phase17-v1",
        "evidence_type": "historical_spatial_context_audit",
        "telemetry": {
            "path": str(canonical_telemetry_path),
            "rows": telemetry_rows,
            "observed_start": telemetry_start,
            "observed_end": telemetry_end,
            "source_timezone_assumption": "Asia/Kolkata converted to UTC by Phase 15 adapter",
        },
        "historical_event": {
            "event_start": event_start,
            "event_end": event_end,
            "temporal_join_status": "NOT_JOINED",
            "reason": "Telemetry observations begin in 2021; spatial reference layers describe the 2015 event.",
        },
        "station": {
            "station_code": "NANDAMBAKKAM_CHECKDAM",
            "longitude": station_lon,
            "latitude": station_lat,
            "metric_crs": METRIC_CRS,
            "gcc_points_within_2km": int((gcc_distance <= 2000).sum()),
            "nearest_gcc_point_m": round(float(gcc_distance.min()), 2) if len(gcc) else None,
            "nrsc_features_intersecting_station": int(nrsc_contains.sum()),
        },
        "source_layers": {
            "gcc_point_count": len(gcc),
            "nrsc_feature_count": len(nrsc),
            "roads_feature_count": len(roads),
            "road_status_distribution": {str(k): int(v) for k, v in road_status.items()},
        },
        "interpretation": {
            "operational_claim_allowed": False,
            "can_train_supervised_flood_label": False,
            "safe_use": "contextual spatial consistency and provenance-aware research analysis",
            "not_established": [
                "telemetry-to-event temporal correspondence",
                "gauge threshold or absolute water-surface elevation",
                "polygon accuracy or survey-grade inundation truth",
                "road closure causality from stage observations",
            ],
        },
    }


def save_json(result: dict[str, Any], path: str | Path) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
