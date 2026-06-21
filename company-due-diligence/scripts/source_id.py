#!/usr/bin/env python3
"""CLI: print the deterministic logical source_id for a URL + source class.

The source_id is keyed by the normalized URL plus the source_class, so the same
logical source is stable across runs (and distinct classes of the same URL stay
separate). Use this when registering sources, or let
``update_source_registry.py --url ... --source-class ...`` derive it for you.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cdd.ids import source_id_for  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compute a logical source_id (URL + source_class)."
    )
    parser.add_argument("--url", required=True)
    parser.add_argument("--source-class", required=True)
    args = parser.parse_args()
    print(source_id_for(args.url, args.source_class))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
