"""Run Phase 10 validation against an explicitly supplied hydrometric CSV."""

import argparse
import json
from pathlib import Path

from app.research.a10_validation import evaluate_hydrometric_series, load_hydrometric_csv


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_path", type=Path)
    parser.add_argument("--dataset-id", required=True)
    parser.add_argument("--source-url")
    parser.add_argument("--verified", action="store_true", help="Declare that the supplied manifest was independently verified")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    rows = load_hydrometric_csv(args.csv_path)
    report = evaluate_hydrometric_series(
        rows,
        source_manifest={
            "dataset_id": args.dataset_id,
            "source_url": args.source_url,
            "verified": args.verified,
        },
    )
    rendered = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
