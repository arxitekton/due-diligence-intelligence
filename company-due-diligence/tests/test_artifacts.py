import json
from pathlib import Path

from cdd.artifacts import (
    artifact_kind,
    iter_structured,
    lineage_ok,
    referenced_source_ids,
)

_GOOD_LINEAGE = {
    "source_snapshot_id": "snap_1",
    "content_path": "raw_sources/x.html",
    "locator": {"section": "leadership"},
    "snippet": "Jane Doe, CEO",
    "extraction_prompt": {"name": "evidence_extraction", "version": "1"},
}


def _doc(**over: object) -> dict:  # type: ignore[type-arg]
    base = {"source_id": "src_0123456789abcdef", "lineage": dict(_GOOD_LINEAGE),
            "artifact_type": "leadership", "value": {}}
    base.update(over)
    return base


def test_iter_structured_yields_sorted(tmp_path: Path):
    sdir = tmp_path / "structured"
    sdir.mkdir(parents=True)
    (sdir / "b.json").write_text(json.dumps(_doc()), encoding="utf-8")
    (sdir / "a.json").write_text(json.dumps(_doc()), encoding="utf-8")
    names = [p.name for p, _ in iter_structured(tmp_path)]
    assert names == ["a.json", "b.json"]


def test_iter_structured_missing_dir(tmp_path: Path):
    assert list(iter_structured(tmp_path)) == []


def test_artifact_kind():
    assert artifact_kind({"line_items": [], "periods": []}) == "financial"
    assert artifact_kind({"entities": []}) == "product"
    assert artifact_kind({"value": {}}) == "extracted"


def test_lineage_ok_true():
    assert lineage_ok(_doc()) is True


def test_lineage_ok_false_on_empty_locator():
    assert lineage_ok(_doc(lineage={**_GOOD_LINEAGE, "locator": {}})) is False


def test_lineage_ok_false_on_missing_key():
    bad = dict(_GOOD_LINEAGE)
    del bad["snippet"]
    assert lineage_ok(_doc(lineage=bad)) is False


def test_lineage_ok_false_when_no_lineage():
    assert lineage_ok({"value": {}}) is False


def test_referenced_source_ids():
    assert referenced_source_ids(_doc()) == {"src_0123456789abcdef"}
    assert referenced_source_ids({"value": {}}) == set()
