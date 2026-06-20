from cdd.ids import make_artifact_id


def test_artifact_id_format_and_determinism():
    a = make_artifact_id(company_id="acme-corp", artifact_type="financial",
                         source_id="src_0123456789abcdef", canonical_key="is|FY2025|revenue")
    b = make_artifact_id(company_id="acme-corp", artifact_type="financial",
                         source_id="src_0123456789abcdef", canonical_key="is|FY2025|revenue")
    assert a == b
    assert a.startswith("art_") and len(a) == 4 + 16


def test_artifact_id_varies_by_key():
    a = make_artifact_id(company_id="x", artifact_type="financial",
                         source_id="src_0000000000000000", canonical_key="is|FY2025|revenue")
    b = make_artifact_id(company_id="x", artifact_type="financial",
                         source_id="src_0000000000000000", canonical_key="is|FY2024|revenue")
    assert a != b
