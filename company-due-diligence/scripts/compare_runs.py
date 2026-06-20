#!/usr/bin/env python3
"""CLI: compare two runs for a company and print the diff as JSON."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cdd.diff import compare_runs  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare two due-diligence runs.")
    parser.add_argument("--company-id", required=True)
    parser.add_argument("--from-run", required=True)
    parser.add_argument("--to-run", required=True)
    parser.add_argument("--root", default="output")
    args = parser.parse_args()

    company_dir = Path(args.root) / "companies" / args.company_id
    diff = compare_runs(company_dir, args.from_run, args.to_run)
    print(json.dumps(diff.as_dict(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
