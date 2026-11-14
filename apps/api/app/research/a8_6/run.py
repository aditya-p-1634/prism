"""Command-line entry point for the A.8.6 readiness gate."""

import argparse
import json

from app.research.a8_6.readiness import evaluate_a86_readiness


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate PRISM A.8.6 terrain experiment readiness")
    parser.add_argument("--data-dir", default="data/research")
    parser.add_argument("--gauge-zero-elevation-m", type=float)
    parser.add_argument("--southern-fabdem")
    parser.add_argument("--nrsc-metadata")
    parser.add_argument("--hydrodynamic-connectivity")
    args = parser.parse_args()
    report = evaluate_a86_readiness(
        data_dir=args.data_dir,
        gauge_zero_elevation_m=args.gauge_zero_elevation_m,
        southern_fabdem_path=args.southern_fabdem,
        nrsc_metadata_path=args.nrsc_metadata,
        hydrodynamic_connectivity_path=args.hydrodynamic_connectivity,
    )
    print(json.dumps(report.to_dict(), indent=2))
    return 0 if report.ready else 2


if __name__ == "__main__":
    raise SystemExit(main())
