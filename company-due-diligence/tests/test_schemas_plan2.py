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


def _financial() -> dict:
    return {
        "artifact_id": "art_00000000000000f1",
        "schema_version": "1",
        "company_id": "acme-corp",
        "run_id": "20260620T183000Z-a1b2c3",
        "source_id": "src_0123456789abcdef",
        "lineage": {
            "source_snapshot_id": "snap_0001",
            "content_path": "raw_artifacts/10k.pdf",
            "locator": {"page": 52, "table": "income_statement"},
            "snippet": "Total revenue 1,234",
            "extraction_prompt": {"name": "financial_extraction", "version": "1"},
        },
        "source_context": {
            "document_title": "FY2025 10-K",
            "section_path": ["Item 8", "Consolidated Statements of Operations"],
            "source_native_statement_name": "Consolidated Statements of Operations",
            "table_id": "income_statement",
            "page": 52,
        },
        "periods": [{
            "period_id": "FY2025",
            "source_native_label": "Year Ended Dec 31, 2025",
            "period_start": "2025-01-01", "period_end": "2025-12-31",
            "as_of_date": None, "period_type": "FY",
            "fiscal_year": 2025, "fiscal_quarter": None,
            "currency_reported": "USD", "unit_scale": "millions",
            "decimals": 0, "restated": False,
        }],
        "line_items": [{
            "line_item_id": "li_revenue",
            "source_native_label": "Total revenue",
            "source_native_path": ["Revenues", "Total revenue"],
            "scope": "consolidated",
            "row_order": 1, "column_ref": "FY2025",
            "value_raw": "1,234", "value_numeric": 1234.0,
            "sign_convention": "positive",
            "footnote_refs": [],
            "cell_locator": {"row": 1, "col": "FY2025", "header_path": ["FY2025"]},
            "normalized_candidate": {"taxonomy_key": "revenue", "confidence": 0.95},
        }],
        "footnotes": [],
        "normalization": None,
        "notes": None,
    }


def test_financial_artifact_valid():
    assert validate(_financial(), "financial_artifact").ok


def test_financial_requires_period_currency_unit():
    doc = _financial()
    del doc["periods"][0]["currency_reported"]
    assert not validate(doc, "financial_artifact").ok


def _product() -> dict:
    return {
        "artifact_id": "art_00000000000000p1",
        "schema_version": "1",
        "company_id": "acme-corp",
        "run_id": "20260620T183000Z-a1b2c3",
        "source_id": "src_0123456789abcdef",
        "lineage": {
            "source_snapshot_id": "snap_0002",
            "content_path": "raw_sources/products.html",
            "locator": {"section": "products"},
            "snippet": "Acme Cloud Platform",
            "extraction_prompt": {"name": "product_extraction", "version": "1"},
        },
        "source_context": {
            "document_title": "Products", "section_path": ["Products"],
            "source_native_statement_name": None, "table_id": None, "page": None,
        },
        "entities": [{
            "entity_id": "ent_platform",
            "entity_type": "platform",
            "source_native_name": "Acme Cloud Platform",
            "aliases": ["ACP"],
            "source_native_category_path": ["Platforms"],
            "parent_entity_id": None,
            "display_order": 1,
            "description_quote": "Our flagship platform.",
            "lifecycle_status": "ga",
            "geography_scope": ["global"],
            "pricing_observations": [{
                "price_raw": "$99/mo", "currency_reported": "USD",
                "billing_interval": "monthly", "locator": {"section": "pricing"},
            }],
            "attributes": [{
                "name_native": "SLA", "value_native": "99.9%", "locator": {"section": "sla"},
            }],
            "normalized_candidate": {"family": "cloud_platform", "confidence": 0.9},
        }],
        "notes": None,
    }


def test_product_artifact_valid():
    assert validate(_product(), "product_artifact").ok


def test_company_dossier_valid_minimal():
    dossier = {
        "run_id": "20260620T183000Z-a1b2c3", "company_id": "acme-corp",
        "research_date": "2026-06-20T18:30:00Z",
        "retrieval_window": {"from": "2026-06-01T00:00:00Z", "to": "2026-06-20T18:30:00Z"},
        "counts": {
            "sources_discovered": 10, "sources_used": 8,
            "sources_changed": 2, "sources_unavailable": 1,
        },
        "known_gaps": ["No audited FY2025 financials located"],
        "confidence_summary": "medium",
        "sections": [{"key": "executive_summary", "title": "Executive Summary",
                      "claims": [{"text": "Acme is a SaaS company.", "kind": "fact",
                                  "citations": ["art_0123456789abcdef"]}]}],
    }
    assert validate(dossier, "company_dossier").ok


def test_data_quality_report_valid():
    dqr = {
        "run_id": "20260620T183000Z-a1b2c3", "company_id": "acme-corp",
        "generated_at": "2026-06-20T18:30:00Z", "passed": True,
        "gates": [{
            "name": "schemas_valid", "passed": True,
            "detail": "all structured artifacts validate",
        }],
        "conflicts": [], "stale_sources": [], "low_confidence": [], "missing_source_classes": [],
    }
    assert validate(dqr, "data_quality_report").ok
