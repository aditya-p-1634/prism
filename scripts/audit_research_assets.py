"""Audit existing PRISM research assets without interpreting them as truth."""

import argparse
import csv
import hashlib
import json
import math
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime
from pathlib import Path


TIME_FORMAT = "%d-%m-%Y %H:%M"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def audit_csv(path: Path) -> dict:
    rows = 0
    stations = Counter()
    timestamps = []
    values = []
    missing_values = 0
    invalid_values = 0
    duplicates = Counter()
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"Station", "Data Acquisition Time", "River Water Level Telemetry Hourly (meter)"}
        missing_columns = sorted(required - set(reader.fieldnames or []))
        if missing_columns:
            return {"asset_type": "TELEMETRY_CSV", "status": "INVALID_SCHEMA", "missing_columns": missing_columns}
        for row in reader:
            rows += 1
            station = (row.get("Station") or "").strip()
            timestamp = (row.get("Data Acquisition Time") or "").strip()
            stations[station] += 1
            duplicates[(station, timestamp)] += 1
            try:
                timestamps.append(datetime.strptime(timestamp, TIME_FORMAT))
            except ValueError:
                invalid_values += 1
            raw_value = (row.get("River Water Level Telemetry Hourly (meter)") or "").strip()
            if not raw_value:
                missing_values += 1
                continue
            try:
                value = float(raw_value)
                if not math.isfinite(value):
                    raise ValueError
                values.append(value)
            except ValueError:
                invalid_values += 1
    return {
        "asset_type": "HISTORICAL_TELEMETRY",
        "status": "PRESENT_SCHEMA_VALIDATED",
        "sha256": sha256(path),
        "rows": rows,
        "stations": dict(stations),
        "time_start": min(timestamps).isoformat() if timestamps else None,
        "time_end": max(timestamps).isoformat() if timestamps else None,
        "missing_values": missing_values,
        "invalid_values_or_timestamps": invalid_values,
        "duplicate_station_timestamp_rows": sum(count - 1 for count in duplicates.values() if count > 1),
        "value_min": min(values) if values else None,
        "value_max": max(values) if values else None,
        "source_measurement_unit": "meter",
        "operational_claim_allowed": False,
        "limitations": [
            "Historical file presence does not prove licensing or live-feed availability.",
            "River-level values are not discharge and do not establish flood thresholds.",
            "Zero-gauge and vertical-datum metadata require independent verification.",
        ],
    }


def audit_kml(path: Path) -> dict:
    root = ET.parse(path).getroot()
    placemarks = root.findall(".//{*}Placemark")
    return {
        "asset_type": "KML",
        "status": "PRESENT_XML_VALIDATED",
        "sha256": sha256(path),
        "placemark_count": len(placemarks),
        "operational_claim_allowed": False,
        "limitations": [
            "Geometry presence does not establish survey-grade ground truth.",
            "Source license and semantic meaning of every attribute require provenance review.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    assets = []
    for path in sorted((root / "data" / "telemetry").glob("*.csv")):
        assets.append({"path": str(path.relative_to(root)), **audit_csv(path)})
    for path in sorted((root / "data" / "research").glob("*.kml")):
        assets.append({"path": str(path.relative_to(root)), **audit_kml(path)})
    assets.append({
        "path": "data/research/N13E080_FABDEM_V1-2.tif",
        "asset_type": "DEM",
        "status": "PRESENT_MANIFESTED",
        "sha256": sha256(root / "data" / "research" / "N13E080_FABDEM_V1-2.tif"),
        "operational_claim_allowed": False,
        "limitations": ["Only the available tile is covered; vertical datum and spatial adequacy require study-area verification."],
    })
    report = {
        "report_version": "phase14-v1",
        "generated_by": "scripts/audit_research_assets.py",
        "source_policy": "Presence, schema, integrity, and temporal coverage are audited; authenticity, licensing, datum, and operational validity are not inferred.",
        "assets": assets,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
