"""Strict readiness contract for the A.8.6 terrain experiment.

The A.8.5 evidence review identified prerequisites that are not present in the
repository: surveyed gauge-zero datum, the southern FABDEM tile, official
NRSC class semantics, and a hydrodynamic connectivity representation. This
module makes those boundaries executable instead of allowing a plausible but
scientifically unsupported model to run.
"""

from dataclasses import dataclass
from hashlib import sha256
import math
from pathlib import Path
from typing import Any, Optional

from app.research.a8_5.constants import DEFAULT_DATA_DIR, DEFAULT_FILES


class ResearchReadinessError(ValueError):
    """Raised when A.8.6 prerequisites are incomplete or unverifiable."""


@dataclass(frozen=True)
class A86ReadinessReport:
    status: str
    available_reference_files: tuple[str, ...]
    missing_reference_files: tuple[str, ...]
    blockers: tuple[str, ...]
    scientific_boundary: str

    @property
    def ready(self) -> bool:
        return self.status == "READY_FOR_TERRAIN_EXPERIMENT"

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "ready": self.ready,
            "available_reference_files": list(self.available_reference_files),
            "missing_reference_files": list(self.missing_reference_files),
            "blockers": list(self.blockers),
            "scientific_boundary": self.scientific_boundary,
        }


def _sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def evaluate_a86_readiness(
    data_dir: str | Path = DEFAULT_DATA_DIR,
    *,
    gauge_zero_elevation_m: Optional[float] = None,
    southern_fabdem_path: Optional[str | Path] = None,
    nrsc_metadata_path: Optional[str | Path] = None,
    hydrodynamic_connectivity_path: Optional[str | Path] = None,
) -> A86ReadinessReport:
    """Evaluate prerequisites without modifying files or operational state."""
    root = Path(data_dir)
    available: list[str] = []
    missing: list[str] = []
    for key, filename in DEFAULT_FILES.items():
        path = root / filename
        if path.is_file() and path.stat().st_size > 0:
            # Hashing is deliberately performed only for traceability; the
            # digest is not used to claim scientific validity.
            _sha256(path)
            available.append(key)
        else:
            missing.append(key)

    blockers: list[str] = []
    if gauge_zero_elevation_m is None:
        blockers.append("GAUGE_ZERO_DATUM_UNVERIFIED")
    elif isinstance(gauge_zero_elevation_m, bool) or not isinstance(gauge_zero_elevation_m, (int, float)):
        blockers.append("GAUGE_ZERO_DATUM_NOT_NUMERIC")
    elif not math.isfinite(float(gauge_zero_elevation_m)):
        blockers.append("GAUGE_ZERO_DATUM_NOT_FINITE")

    if not southern_fabdem_path or not Path(southern_fabdem_path).is_file():
        blockers.append("SOUTHERN_FABDEM_TILE_MISSING")
    if not nrsc_metadata_path or not Path(nrsc_metadata_path).is_file():
        blockers.append("NRSC_CLASS_METADATA_MISSING")
    if not hydrodynamic_connectivity_path or not Path(hydrodynamic_connectivity_path).is_file():
        blockers.append("HYDRODYNAMIC_CONNECTIVITY_MISSING")

    if missing:
        blockers.append("REFERENCE_DATASET_INCOMPLETE")

    status = "READY_FOR_TERRAIN_EXPERIMENT" if not blockers else "NOT_READY"
    return A86ReadinessReport(
        status=status,
        available_reference_files=tuple(sorted(available)),
        missing_reference_files=tuple(sorted(missing)),
        blockers=tuple(blockers),
        scientific_boundary=(
            "Readiness only. No gauge stage is converted to water-surface elevation, "
            "no global DEM bathtub threshold is inferred, and no output is connected "
            "to operational E1-E6 state."
        ),
    )


def require_a86_readiness(**kwargs: Any) -> A86ReadinessReport:
    report = evaluate_a86_readiness(**kwargs)
    if not report.ready:
        raise ResearchReadinessError(
            "A.8.6 terrain experiment is not scientifically ready: "
            + ", ".join(report.blockers)
        )
    return report
