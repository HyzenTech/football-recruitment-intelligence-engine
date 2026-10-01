"""Check local review JSON without modifying the pack or certifying judgments."""

import argparse
import json
from pathlib import Path

from football_recruitment.evaluation.review import check_reviews
from football_recruitment.ingestion.storage import strict_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack-dir", type=Path, required=True)
    parser.add_argument(
        "--results", type=Path, help="Separate edited JSON; defaults to pack template"
    )
    args = parser.parse_args()
    try:
        evidence = strict_json((args.pack_dir / "MODEL_EVIDENCE.json").read_bytes())
        results = strict_json((args.results or args.pack_dir / "REVIEW_RESULTS.json").read_bytes())
        report = check_reviews(evidence, results)
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(json.dumps({"error": str(error), "valid_structure": False}))
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))
    return 0 if report["valid_structure"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
