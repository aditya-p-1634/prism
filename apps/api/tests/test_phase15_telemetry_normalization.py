import csv
import importlib.util
from pathlib import Path


def _load_script():
    root = Path(__file__).resolve().parents[3]
    spec = importlib.util.spec_from_file_location("prepare_historical_telemetry", root / "scripts" / "prepare_historical_telemetry.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_normalization_declares_timezone_and_preserves_provenance(tmp_path):
    module = _load_script()
    source = tmp_path / "telemetry.csv"
    with source.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["Station", "Data Acquisition Time", "River Water Level Telemetry Hourly (meter)"])
        writer.writeheader()
        writer.writerow({"Station": "Nandambakkam CheckDam", "Data Acquisition Time": "01-01-2025 00:00", "River Water Level Telemetry Hourly (meter)": "3.25"})
    rows, manifest = module.normalize([source], "Asia/Kolkata")
    assert rows[0]["station_code"] == "NANDAMBAKKAM_CHECKDAM"
    assert rows[0]["observed_at"].endswith("+00:00")
    assert rows[0]["source_row_number"] == 2
    assert rows[0]["source_timezone_assumption"] == "Asia/Kolkata"
    assert manifest["rainfall_join_status"] == "NOT_JOINED"
    assert manifest["operational_claim_allowed"] is False
