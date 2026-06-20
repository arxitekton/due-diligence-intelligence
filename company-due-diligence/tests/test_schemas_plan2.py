from cdd.schema import validate


def _artifact() -> dict:
    return {
        "artifact_id": "art_0123456789abcdef",
        "schema_version": "1",
        "company_id": "acme-corp",
        "run_id": "20260620T183000Z-a1b2c3",
        "artifact_type": "leadership",
        "source_id": "src_0123456789abcdef",
        "original_format": "text/html",
        "retrieved_at": "2026-06-20T18:30:00Z",
        "extracted_at": "2026-06-20T18:31:00Z",
        "confidence": 0.9,
        "lineage": {
            "source_snapshot_id": "snap_0001",
            "content_path": "raw_sources/src_0123_snap_0001.html",
            "locator": {"section": "leadership"},
            "snippet": "Jane Doe, CEO",
            "extraction_prompt": {"name": "evidence_extraction", "version": "1"},
        },
        "value": {"name": "Jane Doe", "role": "CEO"},
        "notes": None,
    }


def test_extracted_artifact_valid():
    assert validate(_artifact(), "extracted_artifact").ok


def test_extracted_artifact_requires_lineage():
    doc = _artifact()
    del doc["lineage"]
    assert not validate(doc, "extracted_artifact").ok


def test_source_inventory_valid():
    inv = {
        "company_id": "acme-corp",
        "run_id": "20260620T183000Z-a1b2c3",
        "generated_at": "2026-06-20T18:30:00Z",
        "sources": [{
            "source_id": "src_0123456789abcdef",
            "url": "https://example.com/ir",
            "source_class": "ir",
            "source_priority": "primary",
            "title": "Investor Relations",
            "publication_date": None,
            "retrieved_at": "2026-06-20T18:30:00Z",
            "first_seen_at": "2026-06-20T18:30:00Z",
            "last_seen_at": "2026-06-20T18:30:00Z",
            "content_hash": "0" * 64,
            "retrieval_status": "ok",
            "diff_class": "unchanged",
            "notes": None,
        }],
    }
    assert validate(inv, "source_inventory").ok
