#!/usr/bin/env python3
"""CLI: derive current-state manifest.json from event logs."""

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cdd.manifest import build_manifest  # noqa: E402
from cdd.paths import OutputPaths  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Build derived company manifest.")
    parser.add_argument("--root", default="output")
    parser.add_argument("--company-id", required=True)
    parser.add_argument("--now", required=True, help="ISO8601 UTC, e.g. 2026-06-20T18:30:00Z")
    args = parser.parse_args()

    now = datetime.strptime(args.now, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    paths = OutputPaths(root=Path(args.root), company_slug=args.company_id, run_id="_manifest")
    out = build_manifest(paths, now=now)
    print(str(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
