import json
from datetime import UTC, datetime
from pathlib import Path

from cdd.paths import OutputPaths
from cdd.validation import validate_run

_FIN_SID = "src_0123456789abcdef"
_FIN_AID_1 = "art_00000000000000f1"
_FIN_AID_2 = "art_00000000000000f2"


def _financial_lineage() -> dict:
    return {
        "source_snapshot_id": "snap_0001",
        "content_path": "raw_artifacts/10k.pdf",
        "locator": {"page": 52, "table": "income_statement"},
        "snippet": "Total revenue 1,234",
        "extraction_prompt": {"name": "financial_extraction", "version": "1"},
    }


def _financial(
    artifact_id: str = _FIN_AID_1,
    value_numeric: float = 1234.0,
    include_currency: bool = True,
) -> dict:
    period: dict = {
        "period_id": "FY2025",
        "source_native_label": "Year Ended Dec 31, 2025",
        "period_start": "2025-01-01",
        "period_end": "2025-12-31",
        "as_of_date": None,
        "period_type": "FY",
        "fiscal_year": 2025,
        "fiscal_quarter": None,
        "unit_scale": "millions",
        "decimals": 0,
        "restated": False,
    }
    if include_currency:
        period["currency_reported"] = "USD"
    return {
        "artifact_id": artifact_id,
        "schema_version": "1",
        "company_id": "acme-corp",
        "run_id": "20260620T183000Z-a1b2c3",
        "source_id": _FIN_SID,
        "lineage": _financial_lineage(),
        "source_context": {
            "document_title": "FY2025 10-K",
            "section_path": ["Item 8", "Consolidated Statements of Operations"],
            "source_native_statement_name": "Consolidated Statements of Operations",
            "table_id": "income_statement",
            "page": 52,
        },
        "periods": [period],
        "line_items": [{
            "line_item_id": "li_revenue",
            "source_native_label": "Total revenue",
            "source_native_path": ["Revenues", "Total revenue"],
            "scope": "consolidated",
            "row_order": 1,
            "column_ref": "FY2025",
            "value_raw": str(value_numeric),
            "value_numeric": value_numeric,
            "sign_convention": "positive",
            "footnote_refs": [],
            "cell_locator": {"row": 1, "col": "FY2025", "header_path": ["FY2025"]},
            "normalized_candidate": {"taxonomy_key": "revenue", "confidence": 0.95},
        }],
        "footnotes": [],
        "normalization": None,
        "notes": None,
    }

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
        "counts": {"sources_discovered": 1, "sources_used": 1,
                   "sources_changed": 0, "sources_unavailable": 0},
        "known_gaps": [], "confidence_summary": "medium",
        "sections": [{"key": "executive_summary", "title": "Executive Summary",
                      "claims": [{"text": "Acme is a SaaS company.", "kind": "fact",
                                  "citations": [citation]}]}],
    }


def _build(tmp: Path, *, dossier: dict, artifacts: list[dict]) -> OutputPaths:
    paths = OutputPaths(root=tmp, company_slug="acme-corp", run_id="20260620T183000Z-a1b2c3")
    (paths.run_dir / "structured").mkdir(parents=True)
    structured = paths.run_dir / "structured"
    for i, art in enumerate(artifacts):
        (structured / f"art_{i}.json").write_text(json.dumps(art), encoding="utf-8")
    (structured / "source_inventory.json").write_text(
        json.dumps(_inventory()), encoding="utf-8")
    (paths.run_dir / "final_dossier.json").write_text(
        json.dumps(dossier), encoding="utf-8")
    (paths.run_dir / "run_manifest.json").write_text(
        json.dumps({"run_id": "20260620T183000Z-a1b2c3", "company_id": "acme-corp",
                    "output_paths": []}),
        encoding="utf-8")
    return paths


def _now() -> datetime:
    return datetime(2026, 6, 20, 18, 30, tzinfo=UTC)


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


# ---------------------------------------------------------------------------
# C1: financial_usability gate coverage
# ---------------------------------------------------------------------------

def _build_financial(
    tmp: Path,
    *,
    artifacts: list[dict],
    dossier: dict | None = None,
) -> OutputPaths:
    """Build a run with financial artifacts (no dossier citation required)."""
    paths = OutputPaths(root=tmp, company_slug="acme-corp", run_id="20260620T183000Z-a1b2c3")
    (paths.run_dir / "structured").mkdir(parents=True)
    structured = paths.run_dir / "structured"
    for i, art in enumerate(artifacts):
        (structured / f"fin_{i}.json").write_text(json.dumps(art), encoding="utf-8")
    inv = _inventory()
    (structured / "source_inventory.json").write_text(json.dumps(inv), encoding="utf-8")
    # Minimal dossier with no claims so lineage/ref gates stay clean
    dos = dossier or {
        "run_id": "20260620T183000Z-a1b2c3", "company_id": "acme-corp",
        "research_date": "2026-06-20T18:30:00Z",
        "retrieval_window": {"from": "2026-06-01T00:00:00Z", "to": "2026-06-20T18:30:00Z"},
        "counts": {"sources_discovered": 1, "sources_used": 1,
                   "sources_changed": 0, "sources_unavailable": 0},
        "known_gaps": [], "confidence_summary": "medium",
        "sections": [],
    }
    (paths.run_dir / "final_dossier.json").write_text(json.dumps(dos), encoding="utf-8")
    (paths.run_dir / "run_manifest.json").write_text(
        json.dumps({"run_id": "20260620T183000Z-a1b2c3", "company_id": "acme-corp",
                    "output_paths": []}),
        encoding="utf-8",
    )
    return paths


def test_financial_usability_fails_on_missing_currency(tmp_path: Path):
    art = _financial(include_currency=False)
    paths = _build_financial(tmp_path, artifacts=[art])
    report = validate_run(paths, mode="full_refresh", now=_now())
    assert report["passed"] is False
    assert _gate(report, "financial_usability")["passed"] is False


def test_financial_usability_passes_on_valid_financial(tmp_path: Path):
    art = _financial()
    # Dossier cites the financial artifact so referential_integrity passes too
    dos = {
        "run_id": "20260620T183000Z-a1b2c3", "company_id": "acme-corp",
        "research_date": "2026-06-20T18:30:00Z",
        "retrieval_window": {"from": "2026-06-01T00:00:00Z", "to": "2026-06-20T18:30:00Z"},
        "counts": {"sources_discovered": 1, "sources_used": 1,
                   "sources_changed": 0, "sources_unavailable": 0},
        "known_gaps": [], "confidence_summary": "medium",
        "sections": [{"key": "financials", "title": "Financials",
                      "claims": [{"text": "Revenue 1234M.",
                                  "kind": "fact",
                                  "citations": [_FIN_AID_1]}]}],
    }
    paths = _build_financial(tmp_path, artifacts=[art], dossier=dos)
    report = validate_run(paths, mode="full_refresh", now=_now())
    assert _gate(report, "financial_usability")["passed"] is True
    assert report["passed"] is True


# ---------------------------------------------------------------------------
# C4/C2: manifest_closure is now FATAL
# ---------------------------------------------------------------------------

def test_manifest_closure_fails_on_missing_output_path(tmp_path: Path):
    paths = _build(tmp_path, dossier=_dossier(_AID), artifacts=[_leadership()])
    # Overwrite manifest with a non-existent output_path
    manifest = {
        "run_id": "20260620T183000Z-a1b2c3",
        "company_id": "acme-corp",
        "output_paths": ["does/not/exist.json"],
    }
    (paths.run_dir / "run_manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    report = validate_run(paths, mode="full_refresh", now=_now())
    assert report["passed"] is False
    assert _gate(report, "manifest_closure")["passed"] is False


# ---------------------------------------------------------------------------
# C3: refresh_semantics is now FATAL and actually implemented
# ---------------------------------------------------------------------------

def test_refresh_semantics_fails_on_silent_drop(tmp_path: Path):
    paths = OutputPaths(root=tmp_path, company_slug="acme-corp", run_id="20260620T183000Z-a1b2c3")
    # Write a source_registry.jsonl with a retrieved event for a known source
    known_src = "src_aaaaaaaaaaaaaaaa"
    registry_dir = paths.company_dir
    registry_dir.mkdir(parents=True, exist_ok=True)
    event = {
        "event_id": "evt_000001",
        "event_time": "2026-06-19T10:00:00Z",
        "run_id": "20260619T100000Z-prev",
        "entity_type": "source",
        "entity_id": known_src,
        "event_type": "retrieved",
        "payload": {},
    }
    (registry_dir / "source_registry.jsonl").write_text(
        json.dumps(event) + "\n", encoding="utf-8"
    )
    # Build this run's inventory WITHOUT the known source (silent drop)
    inv = {
        "company_id": "acme-corp",
        "run_id": "20260620T183000Z-a1b2c3",
        "generated_at": "2026-06-20T18:30:00Z",
        "sources": [{
            "source_id": _SID, "url": "https://e/ir", "source_class": "ir",
            "source_priority": "primary", "title": None, "publication_date": None,
            "retrieved_at": "2026-06-20T18:30:00Z", "first_seen_at": "2026-06-20T18:30:00Z",
            "last_seen_at": "2026-06-20T18:30:00Z", "content_hash": "0" * 64,
            "retrieval_status": "ok", "diff_class": "unchanged", "notes": None,
        }],
    }
    (paths.run_dir / "structured").mkdir(parents=True, exist_ok=True)
    structured = paths.run_dir / "structured"
    art = _leadership()
    (structured / "art_0.json").write_text(json.dumps(art), encoding="utf-8")
    (structured / "source_inventory.json").write_text(json.dumps(inv), encoding="utf-8")
    dos = _dossier(_AID)
    (paths.run_dir / "final_dossier.json").write_text(json.dumps(dos), encoding="utf-8")
    (paths.run_dir / "run_manifest.json").write_text(
        json.dumps({"run_id": "20260620T183000Z-a1b2c3", "company_id": "acme-corp",
                    "output_paths": []}),
        encoding="utf-8",
    )
    report = validate_run(paths, mode="incremental_refresh", now=_now())
    assert report["passed"] is False
    assert _gate(report, "refresh_semantics")["passed"] is False


def test_refresh_semantics_not_applicable_in_full_refresh(tmp_path: Path):
    """refresh_semantics is not applicable in full_refresh; valid run still passes."""
    paths = _build(tmp_path, dossier=_dossier(_AID), artifacts=[_leadership()])
    report = validate_run(paths, mode="full_refresh", now=_now())
    assert report["passed"] is True
    g = _gate(report, "refresh_semantics")
    assert g["passed"] is True
    assert "not applicable" in g["detail"]


# ---------------------------------------------------------------------------
# C3/conflict_visibility: conflicts are surfaced in the report
# ---------------------------------------------------------------------------

def test_conflict_visibility_surfaces_conflicts(tmp_path: Path):
    # Two financial artifacts for same (scope, period, taxonomy_key) with different values
    art1 = _financial(artifact_id=_FIN_AID_1, value_numeric=1234.0)
    art2 = _financial(artifact_id=_FIN_AID_2, value_numeric=9999.0)
    paths = _build_financial(tmp_path, artifacts=[art1, art2])
    report = validate_run(paths, mode="full_refresh", now=_now())
    assert len(report["conflicts"]) > 0, "Expected conflicts to be surfaced"
    assert _gate(report, "conflict_visibility")["passed"] is True


# ---------------------------------------------------------------------------
# Fix 2: malformed dossier (sections not a list / claim is bare string)
# ---------------------------------------------------------------------------

def _build_with_dossier_raw(tmp: Path, dossier_raw: object) -> OutputPaths:
    """Build a run with an arbitrary (possibly malformed) dossier."""
    paths = OutputPaths(root=tmp, company_slug="acme-corp", run_id="20260620T183000Z-a1b2c3")
    (paths.run_dir / "structured").mkdir(parents=True)
    (paths.run_dir / "structured" / "source_inventory.json").write_text(
        json.dumps(_inventory()), encoding="utf-8"
    )
    structured = paths.run_dir / "structured"
    art = _leadership()
    (structured / "art_0.json").write_text(json.dumps(art), encoding="utf-8")
    (paths.run_dir / "final_dossier.json").write_text(
        json.dumps(dossier_raw), encoding="utf-8"
    )
    (paths.run_dir / "run_manifest.json").write_text(
        json.dumps({"run_id": "20260620T183000Z-a1b2c3", "company_id": "acme-corp",
                    "output_paths": []}),
        encoding="utf-8",
    )
    return paths


def test_malformed_dossier_sections_not_list_does_not_raise(tmp_path: Path):
    """Fix 2: dossier with sections as a string must not raise; report passes/fails gracefully."""
    dossier = {"sections": "notalist"}
    paths = _build_with_dossier_raw(tmp_path, dossier)
    report = validate_run(paths, mode="full_refresh", now=_now())
    assert isinstance(report["passed"], bool)


def test_malformed_dossier_claim_as_bare_string_does_not_raise(tmp_path: Path):
    """Fix 2: claims list containing a bare string must not raise."""
    dossier = {
        "sections": [{"key": "s1", "title": "S1", "claims": ["bare string claim"]}]
    }
    paths = _build_with_dossier_raw(tmp_path, dossier)
    report = validate_run(paths, mode="full_refresh", now=_now())
    assert isinstance(report["passed"], bool)


# ---------------------------------------------------------------------------
# Fix 6: conflict_visibility also surfaces product conflicts
# ---------------------------------------------------------------------------

def _product_artifact(
    artifact_id: str,
    source_id: str,
    lifecycle: str,
) -> dict:
    """Minimal product_artifact for conflict testing."""
    return {
        "artifact_id": artifact_id,
        "schema_version": "1",
        "company_id": "acme-corp",
        "run_id": "20260620T183000Z-a1b2c3",
        "source_id": source_id,
        "lineage": {
            "source_snapshot_id": "snap_1",
            "content_path": "raw_sources/products.html",
            "locator": {"section": "products"},
            "snippet": "Acme Cloud - GA",
            "extraction_prompt": {"name": "product_extraction", "version": "1"},
        },
        "source_context": {
            "document_title": "Products",
            "section_path": [],
            "source_native_statement_name": None,
            "table_id": None,
            "page": None,
        },
        "entities": [{
            "entity_id": "ent_1",
            "entity_type": "platform",
            "source_native_name": "Acme Cloud",
            "aliases": [],
            "source_native_category_path": [],
            "parent_entity_id": None,
            "display_order": 1,
            "description_quote": None,
            "lifecycle_status": lifecycle,
            "geography_scope": [],
            "pricing_observations": [],
            "attributes": [],
            "normalized_candidate": {"family": "cloud_platform", "confidence": 0.9},
        }],
        "notes": None,
    }


def _build_product_run(tmp: Path, artifacts: list[dict]) -> OutputPaths:
    paths = OutputPaths(root=tmp, company_slug="acme-corp", run_id="20260620T183000Z-a1b2c3")
    (paths.run_dir / "structured").mkdir(parents=True)
    structured = paths.run_dir / "structured"
    # Use a product source_id that matches the inventory
    inv = {
        "company_id": "acme-corp",
        "run_id": "20260620T183000Z-a1b2c3",
        "generated_at": "2026-06-20T18:30:00Z",
        "sources": [
            {
                "source_id": "src_0000000000000001",
                "url": "https://e/products",
                "source_class": "website",
                "source_priority": "primary",
                "title": None,
                "publication_date": None,
                "retrieved_at": "2026-06-20T18:30:00Z",
                "first_seen_at": "2026-06-20T18:30:00Z",
                "last_seen_at": "2026-06-20T18:30:00Z",
                "content_hash": "0" * 64,
                "retrieval_status": "ok",
                "diff_class": "unchanged",
                "notes": None,
            },
            {
                "source_id": "src_0000000000000002",
                "url": "https://e/products2",
                "source_class": "website",
                "source_priority": "primary",
                "title": None,
                "publication_date": None,
                "retrieved_at": "2026-06-20T18:30:00Z",
                "first_seen_at": "2026-06-20T18:30:00Z",
                "last_seen_at": "2026-06-20T18:30:00Z",
                "content_hash": "1" * 64,
                "retrieval_status": "ok",
                "diff_class": "unchanged",
                "notes": None,
            },
        ],
    }
    (structured / "source_inventory.json").write_text(json.dumps(inv), encoding="utf-8")
    for i, art in enumerate(artifacts):
        (structured / f"prod_{i}.json").write_text(json.dumps(art), encoding="utf-8")
    dos = {
        "run_id": "20260620T183000Z-a1b2c3", "company_id": "acme-corp",
        "research_date": "2026-06-20T18:30:00Z",
        "retrieval_window": {"from": "2026-06-01T00:00:00Z", "to": "2026-06-20T18:30:00Z"},
        "counts": {"sources_discovered": 2, "sources_used": 2,
                   "sources_changed": 0, "sources_unavailable": 0},
        "known_gaps": [], "confidence_summary": "medium",
        "sections": [],
    }
    (paths.run_dir / "final_dossier.json").write_text(json.dumps(dos), encoding="utf-8")
    (paths.run_dir / "run_manifest.json").write_text(
        json.dumps({"run_id": "20260620T183000Z-a1b2c3", "company_id": "acme-corp",
                    "output_paths": []}),
        encoding="utf-8",
    )
    return paths


def test_conflict_visibility_surfaces_product_conflicts(tmp_path: Path):
    """Fix 6: product lifecycle disagreement must appear in report['conflicts']."""
    art1 = _product_artifact(
        "art_0000000000000p01", "src_0000000000000001", lifecycle="ga"
    )
    art2 = _product_artifact(
        "art_0000000000000p02", "src_0000000000000002", lifecycle="deprecated"
    )
    paths = _build_product_run(tmp_path, [art1, art2])
    report = validate_run(paths, mode="full_refresh", now=_now())
    assert len(report["conflicts"]) > 0, "Expected product conflicts to be surfaced"
    assert _gate(report, "conflict_visibility")["passed"] is True
