from pathlib import Path

import pytest

from app.research.a8_6.readiness import (
    ResearchReadinessError,
    evaluate_a86_readiness,
    require_a86_readiness,
)


def test_a86_readiness_refuses_unverified_experiment():
    report = evaluate_a86_readiness(data_dir=Path(__file__).parents[3] / "data" / "research")
    assert report.ready is False
    assert report.status == "NOT_READY"
    assert "GAUGE_ZERO_DATUM_UNVERIFIED" in report.blockers
    assert "SOUTHERN_FABDEM_TILE_MISSING" in report.blockers
    assert "NRSC_CLASS_METADATA_MISSING" in report.blockers
    assert "HYDRODYNAMIC_CONNECTIVITY_MISSING" in report.blockers


def test_a86_require_gate_raises_instead_of_running_unsafe_model(tmp_path):
    with pytest.raises(ResearchReadinessError, match="not scientifically ready"):
        require_a86_readiness(data_dir=tmp_path)


def test_a86_readiness_is_read_only(tmp_path):
    before = sorted(p.name for p in tmp_path.iterdir())
    report = evaluate_a86_readiness(data_dir=tmp_path)
    after = sorted(p.name for p in tmp_path.iterdir())
    assert before == after
    assert report.to_dict()["ready"] is False


def test_a86_rejects_non_finite_gauge_datum(tmp_path):
    report = evaluate_a86_readiness(data_dir=tmp_path, gauge_zero_elevation_m=float("nan"))
    assert "GAUGE_ZERO_DATUM_NOT_FINITE" in report.blockers
