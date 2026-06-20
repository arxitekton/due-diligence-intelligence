from datetime import UTC, datetime
from pathlib import Path

from cdd.registry import append_event, derive_source_state, next_event_id, read_events


def _evt(eid: str, etype: str, when: datetime, entity_id="src_0123456789abcdef") -> dict:
    return {
        "event_id": eid,
        "event_time": when.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "run_id": "20260620T183000Z-a1",
        "entity_type": "source",
        "entity_id": entity_id,
        "event_type": etype,
        "payload": {},
    }


def test_append_and_read_roundtrip(tmp_path: Path, fixed_now: datetime):
    log = tmp_path / "source_registry.jsonl"
    append_event(log, _evt("evt_1", "discovered", fixed_now), schema_name="source_registry")
    append_event(log, _evt("evt_2", "retrieved", fixed_now), schema_name="source_registry")
    events = read_events(log)
    assert [e["event_id"] for e in events] == ["evt_1", "evt_2"]


def test_append_rejects_invalid_event(tmp_path: Path, fixed_now: datetime):
    import pytest

    log = tmp_path / "source_registry.jsonl"
    bad = _evt("evt_1", "not_a_type", fixed_now)
    with pytest.raises(ValueError):
        append_event(log, bad, schema_name="source_registry")
    assert not log.exists() or log.read_text() == ""


def test_next_event_id_is_sequential(tmp_path: Path, fixed_now: datetime):
    log = tmp_path / "source_registry.jsonl"
    assert next_event_id(log) == "evt_000001"
    append_event(log, _evt("evt_000001", "discovered", fixed_now), schema_name="source_registry")
    assert next_event_id(log) == "evt_000002"


def test_derive_source_state_tracks_first_last_and_status(tmp_path: Path):
    log = tmp_path / "source_registry.jsonl"
    t1 = datetime(2026, 6, 1, 0, 0, 0, tzinfo=UTC)
    t2 = datetime(2026, 6, 20, 0, 0, 0, tzinfo=UTC)
    append_event(log, _evt("evt_000001", "discovered", t1), schema_name="source_registry")
    append_event(log, _evt("evt_000002", "retrieved", t2), schema_name="source_registry")
    state = derive_source_state(log)
    s = state["src_0123456789abcdef"]
    assert s["first_seen_at"] == "2026-06-01T00:00:00Z"
    assert s["last_seen_at"] == "2026-06-20T00:00:00Z"
    assert s["status"] == "active"


def test_derive_marks_unavailable_then_reappeared(tmp_path: Path):
    log = tmp_path / "source_registry.jsonl"
    t1 = datetime(2026, 6, 1, tzinfo=UTC)
    t2 = datetime(2026, 6, 10, tzinfo=UTC)
    t3 = datetime(2026, 6, 20, tzinfo=UTC)
    append_event(log, _evt("evt_000001", "retrieved", t1), schema_name="source_registry")
    append_event(log, _evt("evt_000002", "unavailable", t2), schema_name="source_registry")
    append_event(log, _evt("evt_000003", "retrieved", t3), schema_name="source_registry")
    s = derive_source_state(log)["src_0123456789abcdef"]
    assert s["status"] == "reappeared"


def test_derive_status_respects_event_time_not_append_order(tmp_path: Path):
    # Events appended out of chronological order must still resolve status by
    # event_time: the later "retrieved" (t2) wins over the earlier "unavailable" (t1).
    log = tmp_path / "source_registry.jsonl"
    t1 = datetime(2026, 6, 1, tzinfo=UTC)
    t2 = datetime(2026, 6, 20, tzinfo=UTC)
    append_event(log, _evt("evt_000001", "retrieved", t2), schema_name="source_registry")
    append_event(log, _evt("evt_000002", "unavailable", t1), schema_name="source_registry")
    s = derive_source_state(log)["src_0123456789abcdef"]
    assert s["status"] == "reappeared"
    assert s["first_seen_at"] == "2026-06-01T00:00:00Z"
    assert s["last_seen_at"] == "2026-06-20T00:00:00Z"


def test_append_rejects_malformed_event_time(tmp_path: Path):
    import pytest

    log = tmp_path / "source_registry.jsonl"
    bad = {
        "event_id": "evt_000001",
        "event_time": "NOT-A-DATE",
        "run_id": "20260620T183000Z-a1",
        "entity_type": "source",
        "entity_id": "src_0123456789abcdef",
        "event_type": "retrieved",
        "payload": {},
    }
    with pytest.raises(ValueError):
        append_event(log, bad, schema_name="source_registry")
