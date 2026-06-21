from cdd.merge import merge_financials, merge_products


def _fin(*, artifact_id: str, source_id: str, value: float, currency: str = "USD",
         restated: bool = False, taxonomy: str = "revenue") -> dict:
    return {
        "artifact_id": artifact_id, "schema_version": "1", "company_id": "acme-corp",
        "run_id": "20260620T183000Z-a1b2c3", "source_id": source_id,
        "lineage": {"source_snapshot_id": "snap_1", "content_path": "p.pdf",
                    "locator": {"page": 1}, "snippet": "x",
                    "extraction_prompt": {"name": "financial_extraction", "version": "1"}},
        "source_context": {"document_title": "10-K", "section_path": [],
                           "source_native_statement_name": "IS", "table_id": "is", "page": 1},
        "periods": [{"period_id": "FY2025", "source_native_label": "FY2025",
                     "period_start": "2025-01-01", "period_end": "2025-12-31", "as_of_date": None,
                     "period_type": "FY", "fiscal_year": 2025, "fiscal_quarter": None,
                     "currency_reported": currency, "unit_scale": "millions", "decimals": 0,
                     "restated": restated}],
        "line_items": [{"line_item_id": "li_rev", "source_native_label": "Total revenue",
                        "source_native_path": [], "scope": "consolidated", "row_order": 1,
                        "column_ref": "FY2025", "value_raw": str(value), "value_numeric": value,
                        "sign_convention": "positive", "footnote_refs": [],
                        "cell_locator": {"row": 1, "col": "FY2025", "header_path": ["FY2025"]},
                        "normalized_candidate": {"taxonomy_key": taxonomy, "confidence": 0.95}}],
        "footnotes": [], "normalization": None, "notes": None,
    }


def test_agreeing_sources_merge_no_conflict():
    res = merge_financials([
        _fin(artifact_id="art_0000000000000a01", source_id="src_0000000000000001", value=1234.0),
        _fin(artifact_id="art_0000000000000a02", source_id="src_0000000000000002", value=1234.0),
    ])
    assert res["conflicts"] == []
    assert len(res["merged"]) == 1
    assert {m["source_id"] for m in res["merged"][0]["members"]} == {"src_0000000000000001", "src_0000000000000002"}  # noqa: E501


def test_value_disagreement_emits_source_authority_conflict():
    res = merge_financials([
        _fin(artifact_id="art_0000000000000a01", source_id="src_0000000000000001", value=1234.0),
        _fin(artifact_id="art_0000000000000a02", source_id="src_0000000000000002", value=1300.0),
    ])
    assert res["merged"] == []
    assert len(res["conflicts"]) == 1
    assert res["conflicts"][0]["reason_code"] == "source_authority_conflict"
    assert len(res["conflicts"][0]["members"]) == 2


def test_currency_disagreement_emits_currency_mismatch():
    res = merge_financials([
        _fin(artifact_id="art_0000000000000a01", source_id="src_0000000000000001", value=1234.0, currency="USD"),  # noqa: E501
        _fin(artifact_id="art_0000000000000a02", source_id="src_0000000000000002", value=1234.0, currency="EUR"),  # noqa: E501
    ])
    assert res["conflicts"][0]["reason_code"] == "currency_mismatch"


def test_restatement_conflict():
    res = merge_financials([
        _fin(artifact_id="art_0000000000000a01", source_id="src_0000000000000001", value=1234.0, restated=False),  # noqa: E501
        _fin(artifact_id="art_0000000000000a02", source_id="src_0000000000000002", value=1234.0, restated=True),  # noqa: E501
    ])
    assert res["conflicts"][0]["reason_code"] == "restatement"


def _prod(
    *,
    artifact_id: str,
    source_id: str,
    family: str = "cloud_platform",
    entity_type: str = "platform",
    name: str = "Acme Cloud",
    lifecycle: str = "ga",
) -> dict:  # type: ignore[type-arg]
    return {
        "artifact_id": artifact_id,
        "schema_version": "1",
        "company_id": "acme-corp",
        "run_id": "20260620T183000Z-a1b2c3",
        "source_id": source_id,
        "lineage": {
            "source_snapshot_id": "s",
            "content_path": "p.html",
            "locator": {"section": "products"},
            "snippet": "x",
            "extraction_prompt": {"name": "product_extraction", "version": "1"},
        },
        "source_context": {
            "document_title": "Products",
            "section_path": [],
            "source_native_statement_name": None,
            "table_id": None,
            "page": None,
        },
        "entities": [
            {
                "entity_id": "ent_1",
                "entity_type": entity_type,
                "source_native_name": name,
                "aliases": [],
                "source_native_category_path": [],
                "parent_entity_id": None,
                "display_order": 1,
                "description_quote": None,
                "lifecycle_status": lifecycle,
                "geography_scope": [],
                "pricing_observations": [],
                "attributes": [],
                "normalized_candidate": {"family": family, "confidence": 0.9},
            }
        ],
        "notes": None,
    }


def test_products_merge_when_lifecycle_agrees() -> None:
    res = merge_products([
        _prod(artifact_id="art_0000000000000b01", source_id="src_0000000000000001"),
        _prod(artifact_id="art_0000000000000b02", source_id="src_0000000000000002"),
    ])
    assert res["conflicts"] == []
    assert len(res["merged"]) == 1
    assert {m["source_id"] for m in res["merged"][0]["members"]} == {
        "src_0000000000000001",
        "src_0000000000000002",
    }


def test_products_conflict_on_lifecycle_disagreement() -> None:
    res = merge_products([
        _prod(
            artifact_id="art_0000000000000b01",
            source_id="src_0000000000000001",
            lifecycle="ga",
        ),
        _prod(
            artifact_id="art_0000000000000b02",
            source_id="src_0000000000000002",
            lifecycle="deprecated",
        ),
    ])
    assert res["merged"] == []
    assert len(res["conflicts"]) == 1
    assert res["conflicts"][0]["reason_code"] == "source_authority_conflict"
