from pathlib import Path
import subprocess
import sys


def test_research_asset_audit_reports_existing_telemetry_without_operational_claim():
    root = Path(__file__).resolve().parents[3]
    output = root / "docs" / "research" / "artifacts" / "phase14_test_asset_audit.json"
    script = root / "scripts" / "audit_research_assets.py"
    result = subprocess.run(
        [sys.executable, str(script), "--root", str(root), "--output", str(output)],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "HISTORICAL_TELEMETRY" in result.stdout
    assert output.exists()
    output.unlink()
