import json
from datetime import UTC, datetime
from pathlib import Path

from cdd.inventory import build_source_inventory
from cdd.paths import OutputPaths
from cdd.registry import append_event
from cdd.schema import validate

RUN = "20260620T183000Z-a1b2c3"
SID = "src_0123456789abcdef"


def _evt(eid, etype, when, run_id=RUN, payload=None):
    return {"event_id": eid, "event_time": when, "run_id": run_id,
            "entity_type": "source", "entity_id": SID, "event_type": etype,
            "payload": payload or {}}


def _paths(tmp: Path) -> OutputPaths:
    return OutputPaths(root=tmp, company_slug="acme-corp", run_id=RUN)


def _now() -> datetime:
    return datetime(2026, 6, 20, 18, 30, tzinfo=UTC)


def test_build_inventory_from_registry(tmp_path: Path):
    paths = _paths(tmp_path)
    log = paths.source_registry
    append_event(log, _evt("evt_000001", "discovered", "2026-06-20T18:00:00Z",
                 payload={"url": "https://acme/ir", "source_class": "ir",
                          "source_priority": "primary", "title": "IR"}),
                 schema_name="source_registry")
    append_event(log, _evt("evt_000002", "retrieved", "2026-06-20T18:10:00Z",
                 payload={"content_hash": "0" * 64, "diff_class": "new"}),
                 schema_name="source_registry")
    out = build_source_inventory(paths, now=_now())
    assert out == paths.run_subdir("structured") / "source_inventory.json"
    inv = json.loads(out.read_text())
    assert validate(inv, "source_inventory").ok, validate(inv, "source_inventory").errors
    assert inv["company_id"] == "acme-corp" and inv["run_id"] == RUN
    assert len(inv["sources"]) == 1
    s = inv["sources"][0]
    assert s["source_id"] == SID and s["url"] == "https://acme/ir"
    assert s["source_priority"] == "primary" and s["retrieval_status"] == "ok"
    assert s["retrieved_at"] == "2026-06-20T18:10:00Z"
    assert s["content_hash"] == "0" * 64


def test_unavailable_status_and_missing_registry(tmp_path: Path):
    paths = _paths(tmp_path)
    append_event(paths.source_registry, _evt("evt_000001", "unavailable",
                 "2026-06-20T18:20:00Z", payload={"url": "https://x", "source_class": "ir",
                 "source_priority": "secondary"}), schema_name="source_registry")
    inv = json.loads(build_source_inventory(paths, now=_now()).read_text())
    assert inv["sources"][0]["retrieval_status"] == "unavailable"
    # missing registry → empty inventory, still valid
    empty = OutputPaths(root=tmp_path / "none", company_slug="x", run_id=RUN)
    inv2 = json.loads(build_source_inventory(empty, now=_now()).read_text())
    assert inv2["sources"] == [] and validate(inv2, "source_inventory").ok


def test_excludes_sources_not_in_this_run(tmp_path: Path):
    paths = _paths(tmp_path)
    append_event(paths.source_registry, _evt(
                 "evt_000001", "discovered", "2026-06-01T00:00:00Z", run_id="OLDRUN",
                 payload={"url": "https://old", "source_class": "ir",
                          "source_priority": "primary"}),
                 schema_name="source_registry")
    inv = json.loads(build_source_inventory(paths, now=_now()).read_text())
    assert inv["sources"] == []  # source only touched in OLDRUN, not this run
