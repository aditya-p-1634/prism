"""Normalize Tamil Nadu telemetry into a reproducible PRISM evaluation contract."""

import argparse
import csv
import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo


STATION_CODES = {
    "Kamuthi Bridge": "KAMUTHI_BRIDGE",
    "Nandambakkam CheckDam": "NANDAMBAKKAM_CHECKDAM",
    "Virudhachalam Anicut": "VIRUDHACHALAM_ANICUT",
    "Parthibanur Regulator": "PARTHIBANUR_REGULATOR",
}
TIME_FORMAT = "%d-%m-%Y %H:%M"


def normalize(input_paths: list[Path], input_timezone: str, station_filter: str | None = None) -> tuple[list[dict], dict]:
    source_zone = ZoneInfo(input_timezone)
    rows: list[dict] = []
    duplicate_keys = Counter()
    rejection_counts = Counter()
    source_files = []
    for path in input_paths:
        with path.open("rb") as source_handle:
            source_hash = __import__("hashlib").file_digest(source_handle, "sha256").hexdigest()
        source_files.append({"path": str(path), "sha256": source_hash})
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for source_row_number, raw in enumerate(reader, start=2):
                station_name = (raw.get("Station") or "").strip()
                station_code = STATION_CODES.get(station_name)
                if not station_code:
                    rejection_counts["UNKNOWN_STATION"] += 1
                    continue
                if station_filter and station_code != station_filter:
                    continue
                try:
                    local_time = datetime.strptime(raw["Data Acquisition Time"].strip(), TIME_FORMAT).replace(tzinfo=source_zone)
                    stage = float(raw["River Water Level Telemetry Hourly (meter)"].strip())
                    if stage < 0:
                        raise ValueError("negative stage")
                except (KeyError, ValueError):
                    rejection_counts["INVALID_ROW"] += 1
                    continue
                observed_at = local_time.astimezone(timezone.utc)
                key = (station_code, observed_at.isoformat())
                duplicate_keys[key] += 1
                rows.append({
                    "station_code": station_code,
                    "station_name": station_name,
                    "observed_at": observed_at.isoformat(),
                    "simulation_time_min": observed_at.timestamp() / 60.0,
                    "river_stage_m": stage,
                    "rainfall_rate_mmh": None,
                    "unit": "metres",
                    "source_file": str(path),
                    "source_row_number": source_row_number,
                    "source_timestamp": raw.get("Data Acquisition Time"),
                    "source_timezone_assumption": input_timezone,
                })
    rows.sort(key=lambda row: (row["station_code"], row["observed_at"]))
    duplicate_count = sum(count - 1 for count in duplicate_keys.values() if count > 1)
    station_summary = {}
    for code in sorted({row["station_code"] for row in rows}):
        station_rows = [row for row in rows if row["station_code"] == code]
        timestamps = [datetime.fromisoformat(row["observed_at"]) for row in station_rows]
        gaps = []
        for previous, current in zip(timestamps, timestamps[1:]):
            delta_hours = (current - previous).total_seconds() / 3600.0
            if delta_hours > 1.5:
                gaps.append({"from": previous.isoformat(), "to": current.isoformat(), "hours": round(delta_hours, 2)})
        station_summary[code] = {
            "rows": len(station_rows),
            "time_start": min(timestamps).isoformat(),
            "time_end": max(timestamps).isoformat(),
            "value_min": min(row["river_stage_m"] for row in station_rows),
            "value_max": max(row["river_stage_m"] for row in station_rows),
            "gaps_over_1_5_hours": len(gaps),
            "gap_examples": gaps[:10],
        }
    manifest = {
        "manifest_version": "phase15-v1",
        "input_timezone_assumption": input_timezone,
        "station_filter": station_filter,
        "source_files": source_files,
        "rows_emitted": len(rows),
        "duplicate_station_timestamp_rows": duplicate_count,
        "rejections": dict(rejection_counts),
        "station_summary": station_summary,
        "rainfall_join_status": "NOT_JOINED",
        "operational_claim_allowed": False,
        "limitations": [
            "The source timestamps do not include timezone metadata; the declared timezone assumption must be verified against the publisher.",
            "Rainfall is not present in this source and is intentionally not fabricated or imputed.",
            "River level is not discharge and no authoritative flood threshold is inferred.",
        ],
    }
    return rows, manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--input-timezone", default="Asia/Kolkata")
    parser.add_argument("--station")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    args = parser.parse_args()
    rows, manifest = normalize(args.inputs, args.input_timezone, args.station)
    root = Path(__file__).resolve().parents[1]
    for source in manifest["source_files"]:
        source["path"] = str(Path(source["path"]).resolve().relative_to(root))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()) if rows else ["station_code"])
        writer.writeheader()
        writer.writerows(rows)
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
