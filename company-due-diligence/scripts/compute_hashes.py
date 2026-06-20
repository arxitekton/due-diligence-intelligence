#!/usr/bin/env python3
"""CLI: compute raw + canonical hashes for a file."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cdd.hashing import hash_content  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Compute dual content hashes.")
    parser.add_argument("--file", required=True)
    parser.add_argument("--mime", required=True)
    args = parser.parse_args()

    raw = Path(args.file).read_bytes()
    h = hash_content(raw, args.mime)
    print(json.dumps({
        "raw_hash": h.raw_hash,
        "canonical_hash": h.canonical_hash,
        "profile_id": h.profile_id,
        "profile_version": h.profile_version,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
