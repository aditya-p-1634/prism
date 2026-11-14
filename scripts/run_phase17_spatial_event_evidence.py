"""Generate the Phase 17 spatial/event evidence audit."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/api"))
from app.research.a17_spatial_event_evidence import build_spatial_event_evidence, save_json


def main() -> None:
    result = build_spatial_event_evidence(
        ROOT / "data/derived/nandambakkam_telemetry_canonical.csv",
        ROOT / "data/research/31523c86-0ad1-42f5-b4d1-297daa4bbcd6.kml",
        ROOT / "data/research/7cb3cecf-a95a-4786-8032-9c7417655d24.kml",
        ROOT / "data/research/46d6c279-ae09-43a8-8691-7a5386f69e3a.kml",
    )
    output = ROOT / "docs/research/artifacts/phase17_spatial_event_evidence.json"
    save_json(result, output)
    print(f"wrote {output}")
    print(f"temporal_join_status={result['historical_event']['temporal_join_status']}")
    print(f"gcc_points_within_2km={result['station']['gcc_points_within_2km']}")
    print(f"nrsc_features_intersecting_station={result['station']['nrsc_features_intersecting_station']}")


if __name__ == "__main__":
    main()
