"""A.8.6 terrain-research readiness gate.

This package is intentionally isolated from the operational E1-E6 engines and
does not write PRISM database state. It refuses to run a terrain experiment
until the documented scientific prerequisites are explicitly supplied.
"""

from app.research.a8_6.readiness import (
    A86ReadinessReport,
    ResearchReadinessError,
    evaluate_a86_readiness,
    require_a86_readiness,
)

__all__ = [
    "A86ReadinessReport",
    "ResearchReadinessError",
    "evaluate_a86_readiness",
    "require_a86_readiness",
]
