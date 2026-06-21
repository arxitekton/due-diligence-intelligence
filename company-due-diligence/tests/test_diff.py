import json
from pathlib import Path

from cdd.diff import RunDiff, compare_runs


def _src(sid: str, h: str, status: str = "ok", diff: str = "unchanged") -> dict:
    return {
        "source_id": sid, "url": "https://e/x", "source_class": "ir",
        "source_priority": "primary", "title": None, "publication_date": None,
        "retrieved_at": None, "first_seen_at": None, "last_seen_at": None,
        "content_hash": h, "retrieval_status": status, "diff_class": diff, "notes": None,
    }


def _repro(prompt: str = "p0", schema: str = "s0", model: str = "m0") -> dict:
    return {"prompt_set_hash": prompt, "schema_set_hash": schema, "model_id": model,
            "tool_versions": {}, "normalizer_profile_versions": {}, "locale": "en-US"}


def _write_run(company_dir: Path, run_id: str, sources: list[dict], repro: dict) -> None:
    run = company_dir / "runs" / run_id
    (run / "structured").mkdir(parents=True)
    (run / "structured" / "source_inventory.json").write_text(
        json.dumps({"company_id": "acme-corp", "run_id": run_id,
                    "generated_at": "2026-06-20T18:30:00Z", "sources": sources}),
        encoding="utf-8")
    (run / "run_manifest.json").write_text(json.dumps({"reproducibility": repro}), encoding="utf-8")


def test_compare_added_changed_removed_unavailable(tmp_path: Path):
    cdir = tmp_path / "companies" / "acme-corp"
    _write_run(cdir, "runA", [_src("src_0000000000000001", "h1"),
                              _src("src_0000000000000003", "h3")], _repro())
    _write_run(cdir, "runB", [_src("src_0000000000000001", "h1b", diff="content_change"),
                              _src("src_0000000000000002", "h2"),
                              _src("src_0000000000000003", "h3", status="unavailable")], _repro())
    d = compare_runs(cdir, "runA", "runB")
    assert isinstance(d, RunDiff)
    assert d.sources_added == ["src_0000000000000002"]
    assert d.sources_removed == []
    assert d.sources_changed == [
        {"source_id": "src_0000000000000001", "diff_class": "content_change"}
    ]
    assert d.sources_unavailable == ["src_0000000000000003"]
    assert d.delta_type == "source_delta"


def test_delta_type_extraction_when_prompt_changes(tmp_path: Path):
    cdir = tmp_path / "companies" / "acme-corp"
    _write_run(cdir, "runA", [_src("src_0000000000000001", "h1")], _repro(prompt="p0"))
    _write_run(
        cdir,
        "runB",
        [_src("src_0000000000000001", "h1b", diff="content_change")],
        _repro(prompt="p1"),
    )
    assert compare_runs(cdir, "runA", "runB").delta_type == "extraction_delta"


def test_delta_type_schema_when_schema_changes(tmp_path: Path):
    cdir = tmp_path / "companies" / "acme-corp"
    _write_run(cdir, "runA", [_src("src_0000000000000001", "h1")], _repro(schema="s0"))
    _write_run(cdir, "runB", [_src("src_0000000000000001", "h1")], _repro(schema="s1"))
    assert compare_runs(cdir, "runA", "runB").delta_type == "schema_delta"


def test_missing_inventory_raises(tmp_path: Path):
    import pytest

    cdir = tmp_path / "companies" / "acme-corp"
    with pytest.raises(FileNotFoundError):
        compare_runs(cdir, "runA", "runB")


def test_changed_and_unavailable_not_double_counted(tmp_path: Path):
    """Fix 8: a source whose hash changed AND is unavailable in to_run must appear
    only in sources_unavailable, not in sources_changed."""
    cdir = tmp_path / "companies" / "acme-corp"
    sid = "src_0000000000000001"
    _write_run(cdir, "runA", [_src(sid, "old_hash")], _repro())
    _write_run(
        cdir,
        "runB",
        [_src(sid, "new_hash", status="unavailable", diff="content_change")],
        _repro(),
    )
    d = compare_runs(cdir, "runA", "runB")
    assert sid in d.sources_unavailable
    changed_ids = [s["source_id"] for s in d.sources_changed]
    assert sid not in changed_ids, (
        f"{sid} must not appear in sources_changed when it is also unavailable"
    )
