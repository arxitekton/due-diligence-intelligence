"""Append-only JSONL event logs + derived current-state views.

The log file is the source of truth and is never mutated in place; state is
always recomputed from the full event stream.
"""

import json
import os
import re
from pathlib import Path
from typing import Any

from cdd.schema import validate

_EVENT_NUM = re.compile(r"^evt_(\d+)$")


def read_events(log: Path) -> list[dict[str, Any]]:
    if not Path(log).exists():
        return []
    events: list[dict[str, Any]] = []
    for line in Path(log).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            events.append(dict[str, Any](json.loads(line)))
    return events


def next_event_id(log: Path) -> str:
    highest = 0
    for e in read_events(log):
        m = _EVENT_NUM.match(str(e.get("event_id", "")))
        if m:
            highest = max(highest, int(m.group(1)))
    return f"evt_{highest + 1:06d}"


def append_event(log: Path, event: dict[str, Any], *, schema_name: str) -> None:
    result = validate(event, schema_name)
    if not result.ok:
        raise ValueError(f"invalid {schema_name} event: {result.errors}")
    log = Path(log)
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, sort_keys=True) + "\n")
        fh.flush()
        os.fsync(fh.fileno())


_ACTIVE = {"discovered", "retrieved", "canonicalized", "extracted", "validated"}


def derive_source_state(log: Path) -> dict[str, dict[str, Any]]:
    state: dict[str, dict[str, Any]] = {}
    # Status must reflect the latest event by event_time, not file/append order,
    # so backfilled or out-of-order events resolve deterministically. event_time
    # is RFC3339 UTC ("...Z"), so lexical sort == chronological; event_id breaks ties.
    events = sorted(
        read_events(log),
        key=lambda e: (str(e["event_time"]), str(e["event_id"])),
    )
    for e in events:
        eid = str(e["entity_id"])
        when = str(e["event_time"])
        etype = str(e["event_type"])
        s: dict[str, Any] = state.setdefault(
            eid,
            {
                "entity_id": eid,
                "first_seen_at": when,
                "last_seen_at": when,
                "status": "active",
                "_was_unavailable": False,
            },
        )
        s["first_seen_at"] = min(str(s["first_seen_at"]), when)
        s["last_seen_at"] = max(str(s["last_seen_at"]), when)
        if etype == "unavailable":
            s["status"] = "unavailable"
            s["_was_unavailable"] = True
        elif etype in _ACTIVE:
            s["status"] = "reappeared" if s["_was_unavailable"] else "active"
        elif etype == "superseded":
            s["status"] = "superseded"
    for s in state.values():
        s.pop("_was_unavailable", None)
    return state
