#!/usr/bin/env python3
"""CLI: append an artifact event to an artifact_registry.jsonl log."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cdd.registry import append_event, next_event_id  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Append an artifact registry event.")
    parser.add_argument("--log", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--artifact-id", required=True)
    parser.add_argument("--event-type", required=True,
                        choices=["extracted", "validated", "superseded", "unavailable"])
    parser.add_argument("--event-time", required=True)
    parser.add_argument("--payload", default="{}")
    args = parser.parse_args()

    log = Path(args.log)
    event = {
        "event_id": next_event_id(log),
        "event_time": args.event_time,
        "run_id": args.run_id,
        "entity_type": "artifact",
        "entity_id": args.artifact_id,
        "event_type": args.event_type,
        "payload": json.loads(args.payload),
    }
    append_event(log, event, schema_name="artifact_registry")
    print(event["event_id"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
