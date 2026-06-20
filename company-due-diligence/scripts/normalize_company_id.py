#!/usr/bin/env python3
"""CLI: print the normalized company slug."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cdd.ids import normalize_company_id  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Normalize a company name to a slug.")
    parser.add_argument("--company", required=True)
    args = parser.parse_args()
    print(normalize_company_id(args.company))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
