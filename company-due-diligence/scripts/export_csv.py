#!/usr/bin/env python3
"""CLI: export a JSON array to CSV with explicit column order and optional redaction."""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cdd.exporters import export_csv  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Export JSON array to CSV.")
    parser.add_argument("--in", dest="input", required=True, help="Input JSON file (array).")
    parser.add_argument("--out", required=True, help="Output CSV file path.")
    parser.add_argument("--columns", required=True, help="Comma-separated column names.")
    parser.add_argument("--redact", default=None, help="Comma-separated field names to redact.")
    args = parser.parse_args()

    records: list[dict[str, Any]] = json.loads(Path(args.input).read_text(encoding="utf-8"))
    columns: list[str] = args.columns.split(",")
    redact: set[str] | None = set(args.redact.split(",")) if args.redact else None
    out_path = Path(args.out)
    export_csv(records, out_path, columns=columns, redact=redact)
    print(str(out_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
