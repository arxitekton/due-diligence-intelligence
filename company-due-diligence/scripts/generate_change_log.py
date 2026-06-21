#!/usr/bin/env python3
"""CLI: generate a Markdown change log for a run pair."""

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cdd.changelog import render_change_log  # noqa: E402
from cdd.diff import compare_runs  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate change log between two runs.")
    parser.add_argument("--company-id", required=True)
    parser.add_argument("--from-run", required=True)
    parser.add_argument("--to-run", required=True)
    parser.add_argument("--now", required=True, help="ISO8601 UTC, e.g. 2026-06-20T18:30:00Z")
    parser.add_argument("--root", default="output")
    args = parser.parse_args()

    now = datetime.strptime(args.now, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    company_dir = Path(args.root) / "companies" / args.company_id
    diff = compare_runs(company_dir, args.from_run, args.to_run)
    md = render_change_log(diff, now=now)

    out_path = (
        Path(args.root) / "companies" / args.company_id / "runs" / args.to_run / "change_log.md"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(md, encoding="utf-8")
    print(str(out_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
