"""Derive a per-run source_inventory.json from the company-level source registry."""

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, cast

from cdd.paths import OutputPaths
from cdd.registry import derive_source_state, read_events
from cdd.schema import validate
from cdd.timeutil import iso_utc

_RETRIEVAL_EVENTS = {"retrieved", "canonicalized"}
_VALID_PRIORITIES = {"primary", "secondary", "signal"}
_VALID_RETRIEVAL_STATUSES = {"ok", "unavailable", "error"}
_VALID_DIFF_CLASSES = {
    "unchanged",
    "cosmetic_change",
    "table_change",
    "content_change",
    "unavailable",
    "new",
}


def _atomic_write_json(target: Path, data: dict[str, Any]) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(target.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(data, indent=2, sort_keys=True) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, target)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def _merge_payloads(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Merge payload fields across all events, latest event_time wins per field."""
    # Sort by (event_time, event_id) so last assignment wins for each field
    sorted_evts = sorted(
        events,
        key=lambda e: (str(e.get("event_time", "")), str(e.get("event_id", ""))),
    )
    merged: dict[str, Any] = {}
    for evt in sorted_evts:
        payload = evt.get("payload", {})
        if isinstance(payload, dict):
            merged.update(cast("dict[str, Any]", payload))
    return merged


def _build_source_entry(
    source_id: str,
    run_events: list[dict[str, Any]],
    all_events: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build a single source entry for the inventory."""
    merged = _merge_payloads(run_events)

    # Determine the latest event by (event_time, event_id) for status inference
    latest_evt = max(
        run_events,
        key=lambda e: (str(e.get("event_time", "")), str(e.get("event_id", ""))),
    )
    latest_etype = str(latest_evt.get("event_type", ""))

    # retrieved_at: event_time of the latest retrieved/canonicalized event for this source
    # across ALL events (not just this run) for cross-run consistency — but spec says
    # "latest event of type in {retrieved, canonicalized} for this source"
    retrieval_evts = [
        e for e in all_events
        if str(e.get("entity_id", "")) == source_id
        and str(e.get("event_type", "")) in _RETRIEVAL_EVENTS
    ]
    retrieved_at: str | None = None
    if retrieval_evts:
        best = max(
            retrieval_evts,
            key=lambda e: (str(e.get("event_time", "")), str(e.get("event_id", ""))),
        )
        retrieved_at = str(best["event_time"])

    # source_priority
    raw_priority = str(merged.get("source_priority", ""))
    source_priority = raw_priority if raw_priority in _VALID_PRIORITIES else "secondary"

    # retrieval_status
    if latest_etype == "unavailable":
        retrieval_status = "unavailable"
    else:
        raw_status = str(merged.get("retrieval_status", ""))
        retrieval_status = raw_status if raw_status in _VALID_RETRIEVAL_STATUSES else "ok"

    # diff_class
    raw_diff = str(merged.get("diff_class", ""))
    diff_class = raw_diff if raw_diff in _VALID_DIFF_CLASSES else "new"

    return {
        "source_id": source_id,
        "url": str(merged.get("url", "")),
        "source_class": str(merged.get("source_class", "unknown")),
        "source_priority": source_priority,
        "title": merged.get("title") or None,
        "publication_date": merged.get("publication_date") or None,
        "retrieved_at": retrieved_at,
        "first_seen_at": None,  # populated from derive_source_state below
        "last_seen_at": None,
        "content_hash": merged.get("content_hash") or None,
        "retrieval_status": retrieval_status,
        "diff_class": diff_class,
        "notes": merged.get("notes") or None,
    }


def build_source_inventory(paths: OutputPaths, *, now: datetime) -> Path:
    """Derive a per-run source_inventory.json from the company-level source registry.

    Args:
        paths: OutputPaths for the current run.
        now: Current wall-clock time (for generated_at).

    Returns:
        Path to the written source_inventory.json.

    Raises:
        RuntimeError: If the produced document fails schema validation (internal bug).
    """
    log = paths.source_registry
    all_events = read_events(log)
    state = derive_source_state(log)  # company-level, all runs

    # Group events by source_id, filtered to this run
    run_events_by_source: dict[str, list[dict[str, Any]]] = {}
    for evt in all_events:
        if str(evt.get("run_id", "")) != paths.run_id:
            continue
        sid = str(evt.get("entity_id", ""))
        run_events_by_source.setdefault(sid, []).append(evt)

    source_entries: list[dict[str, Any]] = []
    for source_id in sorted(run_events_by_source):
        entry = _build_source_entry(
            source_id,
            run_events_by_source[source_id],
            all_events,
        )
        # Overlay first_seen_at / last_seen_at from full-history state
        src_state = state.get(source_id, {})
        entry["first_seen_at"] = src_state.get("first_seen_at") or None
        entry["last_seen_at"] = src_state.get("last_seen_at") or None
        source_entries.append(entry)

    doc: dict[str, Any] = {
        "company_id": paths.company_slug,
        "run_id": paths.run_id,
        "generated_at": iso_utc(now),
        "sources": source_entries,
    }

    result = validate(doc, "source_inventory")
    if not result.ok:
        raise RuntimeError(
            f"build_source_inventory produced invalid document: {result.errors}"
        )

    target = paths.run_subdir("structured") / "source_inventory.json"
    _atomic_write_json(target, doc)
    return target
