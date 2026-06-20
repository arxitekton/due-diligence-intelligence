import json
from datetime import UTC, datetime
from pathlib import Path

from cdd.manifest import build_manifest
from cdd.paths import OutputPaths


def _seed_source_log(paths: OutputPaths) -> None:
    paths.company_dir.mkdir(parents=True, exist_ok=True)
    events = [
        {"event_id": "evt_000001", "event_time": "2026-06-01T00:00:00Z",
         "run_id": "r1", "entity_type": "source", "entity_id": "src_0000000000000001",
         "event_type": "retrieved", "payload": {}},
        {"event_id": "evt_000002", "event_time": "2026-06-20T00:00:00Z",
         "run_id": "r2", "entity_type": "source", "entity_id": "src_0000000000000002",
         "event_type": "unavailable", "payload": {}},
    ]
    paths.source_registry.write_text(
        "\n".join(json.dumps(e, sort_keys=True) for e in events) + "\n", encoding="utf-8"
    )


def test_build_manifest_writes_atomic_current_state(tmp_path: Path):
    paths = OutputPaths(root=tmp_path, company_slug="acme-corp", run_id="r2")
    _seed_source_log(paths)
    paths.artifact_registry.write_text("", encoding="utf-8")

    out = build_manifest(paths, now=datetime(2026, 6, 20, 18, 30, tzinfo=UTC))
    assert out == paths.manifest
    manifest = json.loads(paths.manifest.read_text())

    assert manifest["company_id"] == "acme-corp"
    assert manifest["generated_at"] == "2026-06-20T18:30:00Z"
    assert manifest["source_count"] == 2
    assert manifest["sources_active"] == 1
    assert manifest["sources_unavailable"] == 1
    assert "src_0000000000000001" in manifest["sources"]
