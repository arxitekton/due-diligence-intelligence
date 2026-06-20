#!/usr/bin/env python3
"""CLI: merge financial artifacts from a run directory into a single consolidated JSON."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cdd.artifacts import artifact_kind, iter_structured  # noqa: E402
from cdd.merge import merge_financials  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Merge financial artifacts in a run directory.")
    parser.add_argument("--run-dir", required=True, help="Path to the run directory.")
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    financials: list[dict[str, object]] = []
    for _path, doc in iter_structured(run_dir):
        if artifact_kind(doc) == "financial":
            financials.append(doc)

    result = merge_financials(financials)

    out_path = run_dir / "structured" / "_merged.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    conflicts: list[object] = result.get("conflicts", [])  # type: ignore[assignment]
    print(f"conflicts={len(conflicts)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
