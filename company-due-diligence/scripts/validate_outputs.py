#!/usr/bin/env python3
"""CLI: run evidentiary validation gates on a completed run."""

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cdd.paths import OutputPaths  # noqa: E402
from cdd.validation import validate_run  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a due-diligence run's outputs.")
    parser.add_argument("--company-id", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--mode", required=True)
    parser.add_argument("--now", required=True, help="ISO8601 UTC, e.g. 2026-06-20T18:30:00Z")
    parser.add_argument("--root", default="output")
    args = parser.parse_args()

    now = datetime.strptime(args.now, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    paths = OutputPaths(root=Path(args.root), company_slug=args.company_id, run_id=args.run_id)
    report = validate_run(paths, mode=args.mode, now=now)

    # Write JSON report
    json_path = paths.run_dir / "data_quality_report.json"
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    # Write Markdown report
    md_lines = ["# Data Quality Report", ""]
    passed_val: object = report["passed"]
    md_lines.append(f"**passed:** {passed_val}")
    md_lines.append("")
    gates: list[dict[str, object]] = report.get("gates", [])  # type: ignore[assignment]
    for gate in gates:
        name: str = str(gate.get("name", ""))
        gate_passed: bool = bool(gate.get("passed", False))
        detail: str = str(gate.get("detail", ""))
        status = "PASS" if gate_passed else "FAIL"
        md_lines.append(f"- {name}: {status} — {detail}")

    md_path = paths.run_dir / "data_quality_report.md"
    md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    print("PASS" if report["passed"] else "FAIL")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
