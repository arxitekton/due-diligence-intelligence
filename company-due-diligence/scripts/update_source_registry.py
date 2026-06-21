#!/usr/bin/env python3
"""CLI: append a source event to a source_registry.jsonl log."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cdd.ids import source_id_for  # noqa: E402
from cdd.registry import append_event, next_event_id  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Append a source registry event.")
    parser.add_argument("--log", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--source-id",
                        help="explicit source_id; or derive via --url + --source-class")
    parser.add_argument("--url", help="source URL (derives source_id with --source-class)")
    parser.add_argument("--source-class", help="source class (derives source_id with --url)")
    parser.add_argument("--event-type", required=True,
                        choices=["discovered", "retrieved", "canonicalized",
                                 "unavailable", "superseded", "validated"])
    parser.add_argument("--event-time", required=True)
    parser.add_argument("--payload", default="{}")
    args = parser.parse_args()

    source_id = args.source_id
    if not source_id:
        if not (args.url and args.source_class):
            parser.error("provide --source-id, or both --url and --source-class to derive it")
        source_id = source_id_for(args.url, args.source_class)

    log = Path(args.log)
    event = {
        "event_id": next_event_id(log),
        "event_time": args.event_time,
        "run_id": args.run_id,
        "entity_type": "source",
        "entity_id": source_id,
        "event_type": args.event_type,
        "payload": json.loads(args.payload),
    }
    append_event(log, event, schema_name="source_registry")
    print(event["event_id"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
