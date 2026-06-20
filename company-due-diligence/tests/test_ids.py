from datetime import UTC, datetime

from cdd.ids import make_run_id, normalize_company_id, source_id_for


def test_slug_lowercases_and_hyphenates():
    assert normalize_company_id("Acme Corp.") == "acme-corp"


def test_slug_strips_legal_suffixes_and_accents():
    assert normalize_company_id("Société Générale S.A.") == "societe-generale"


def test_slug_collapses_repeats_and_trims():
    assert normalize_company_id("  Foo   &   Bar, Inc.  ") == "foo-bar"


def test_slug_rejects_empty():
    import pytest

    with pytest.raises(ValueError):
        normalize_company_id("   ")


def test_run_id_has_stamp_and_token():
    dt = datetime(2026, 6, 20, 18, 30, 0, tzinfo=UTC)
    rid = make_run_id(dt, token="a1b2c3")
    assert rid == "20260620T183000Z-a1b2c3"


def test_source_id_is_stable_for_same_logical_source():
    a = source_id_for("https://Example.com/IR/?utm_source=x", source_class="ir")
    b = source_id_for("https://example.com/ir/", source_class="ir")
    assert a == b  # tracking params + case + trailing slash normalized away


def test_source_id_differs_by_source_class():
    a = source_id_for("https://example.com/pr", source_class="ir")
    b = source_id_for("https://example.com/pr", source_class="newswire")
    assert a != b  # same URL, different logical source
