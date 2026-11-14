from pathlib import Path

from app.research.a17_spatial_event_evidence import build_spatial_event_evidence


ROOT = Path(__file__).resolve().parents[3]


def test_phase17_keeps_2015_event_and_2021_telemetry_separate():
    result = build_spatial_event_evidence(
        ROOT / "data/derived/nandambakkam_telemetry_canonical.csv",
        ROOT / "data/research/31523c86-0ad1-42f5-b4d1-297daa4bbcd6.kml",
        ROOT / "data/research/7cb3cecf-a95a-4786-8032-9c7417655d24.kml",
        ROOT / "data/research/46d6c279-ae09-43a8-8691-7a5386f69e3a.kml",
    )
    assert result["historical_event"]["temporal_join_status"] == "NOT_JOINED"
    assert result["telemetry"]["rows"] > 1000
    assert result["station"]["gcc_points_within_2km"] >= 0
    assert result["interpretation"]["operational_claim_allowed"] is False
    assert result["interpretation"]["can_train_supervised_flood_label"] is False
