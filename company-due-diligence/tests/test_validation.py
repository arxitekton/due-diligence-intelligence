import json
from datetime import datetime, timezone
from pathlib import Path

from cdd.paths import OutputPaths
from cdd.validation import validate_run

_LINEAGE = {
    "source_snapshot_id": "snap_1", "content_path": "raw_sources/x.html",
    "locator": {"section": "leadership"}, "snippet": "Jane Doe, CEO",
    "extraction_prompt": {"name": "evidence_extraction", "version": "1"},
}
_SID = "src_0123456789abcdef"
_AID = "art_00000000000000a1"


def _leadership() -> dict:
    return {
        "artifact_id": _AID, "schema_version": "1", "company_id": "acme-corp",
        "run_id": "20260620T183000Z-a1b2c3", "artifact_type": "leadership",
        "source_id": _SID, "original_format": "text/html",
        "retrieved_at": "2026-06-20T18:30:00Z", "extracted_at": "2026-06-20T18:31:00Z",
        "confidence": 0.9, "lineage": dict(_LINEAGE), "value": {"name": "Jane Doe"}, "notes": None,
    }


def _inventory() -> dict:
    return {
        "company_id": "acme-corp", "run_id": "20260620T183000Z-a1b2c3",
        "generated_at": "2026-06-20T18:30:00Z",
        "sources": [{
            "source_id": _SID, "url": "https://e/ir", "source_class": "ir",
            "source_priority": "primary", "title": None, "publication_date": None,
            "retrieved_at": "2026-06-20T18:30:00Z", "first_seen_at": "2026-06-20T18:30:00Z",
            "last_seen_at": "2026-06-20T18:30:00Z", "content_hash": "0" * 64,
            "retrieval_status": "ok", "diff_class": "unchanged", "notes": None,
        }],
    }


def _dossier(citation: str) -> dict:
    return {
        "run_id": "20260620T183000Z-a1b2c3", "company_id": "acme-corp",
        "research_date": "2026-06-20T18:30:00Z",
        "retrieval_window": {"from": "2026-06-01T00:00:00Z", "to": "2026-06-20T18:30:00Z"},
        "counts": {"sources_discovered": 1, "sources_used": 1, "sources_changed": 0, "sources_unavailable": 0},
        "known_gaps": [], "confidence_summary": "medium",
        "sections": [{"key": "executive_summary", "title": "Executive Summary",
                      "claims": [{"text": "Acme is a SaaS company.", "kind": "fact",
                                  "citations": [citation]}]}],
    }


def _build(tmp: Path, *, dossier: dict, artifacts: list[dict]) -> OutputPaths:
    paths = OutputPaths(root=tmp, company_slug="acme-corp", run_id="20260620T183000Z-a1b2c3")
    (paths.run_dir / "structured").mkdir(parents=True)
    for i, art in enumerate(artifacts):
        (paths.run_dir / "structured" / f"art_{i}.json").write_text(json.dumps(art), encoding="utf-8")
    (paths.run_dir / "structured" / "source_inventory.json").write_text(json.dumps(_inventory()), encoding="utf-8")
    (paths.run_dir / "final_dossier.json").write_text(json.dumps(dossier), encoding="utf-8")
    (paths.run_dir / "run_manifest.json").write_text(
        json.dumps({"run_id": "20260620T183000Z-a1b2c3", "company_id": "acme-corp", "output_paths": []}),
        encoding="utf-8")
    return paths


def _now() -> datetime:
    return datetime(2026, 6, 20, 18, 30, tzinfo=timezone.utc)


def _gate(report: dict, name: str) -> dict:
    return next(g for g in report["gates"] if g["name"] == name)


def test_valid_run_passes(tmp_path: Path):
    paths = _build(tmp_path, dossier=_dossier(_AID), artifacts=[_leadership()])
    report = validate_run(paths, mode="full_refresh", now=_now())
    assert report["passed"] is True, report["gates"]


def test_dangling_citation_fails_referential_integrity(tmp_path: Path):
    paths = _build(tmp_path, dossier=_dossier("art_ffffffffffffffff"), artifacts=[_leadership()])
    report = validate_run(paths, mode="full_refresh", now=_now())
    assert report["passed"] is False
    assert _gate(report, "referential_integrity")["passed"] is False


def test_uncited_fact_fails_lineage(tmp_path: Path):
    d = _dossier(_AID)
    d["sections"][0]["claims"][0]["citations"] = []
    paths = _build(tmp_path, dossier=d, artifacts=[_leadership()])
    report = validate_run(paths, mode="full_refresh", now=_now())
    assert report["passed"] is False
    assert _gate(report, "lineage_complete")["passed"] is False


def test_duplicate_artifact_id_fails_id_integrity(tmp_path: Path):
    paths = _build(tmp_path, dossier=_dossier(_AID), artifacts=[_leadership(), _leadership()])
    report = validate_run(paths, mode="full_refresh", now=_now())
    assert _gate(report, "id_integrity")["passed"] is False
