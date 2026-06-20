#!/usr/bin/env python3
"""CLI: create a new run (folders + seeded run_manifest.json)."""

import argparse
import json
import secrets
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cdd.runlifecycle import create_run  # noqa: E402

_MODES = [
    "full_refresh", "incremental_refresh", "source_discovery_only",
    "source_retrieval_only", "extraction_only", "validation_only",
    "dossier_only", "compare_runs",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a due-diligence run.")
    parser.add_argument("--company", required=True)
    parser.add_argument("--mode", required=True, choices=_MODES)
    parser.add_argument("--root", default="output")
    parser.add_argument("--token", default=None, help="4-12 lowercase alnum; random if omitted")
    args = parser.parse_args()

    token = args.token or secrets.token_hex(3)
    paths = create_run(
        root=Path(args.root), company_name=args.company, mode=args.mode,
        now=datetime.now(UTC), token=token,
        input_parameters={"company_name": args.company, "mode": args.mode},
    )
    print(json.dumps({
        "company_slug": paths.company_slug,
        "run_id": paths.run_id,
        "run_dir": str(paths.run_dir),
        "run_manifest": str(paths.run_dir / "run_manifest.json"),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
