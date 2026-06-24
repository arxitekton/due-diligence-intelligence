from cdd.extract.gleif import GLEIF_SEARCH_URL, parse_lei_records, search_by_name

_GLEIF_JSON = (
    b'{"data":[{"attributes":{"lei":"5493001KJTIIGC8Y1R12",'
    b'"entity":{"legalName":{"name":"Bad Actor LLC"},'
    b'"legalAddress":{"country":"US"},"status":"ACTIVE"}}}]}'
)

def test_parse_lei_records():
    recs = parse_lei_records(_GLEIF_JSON)
    assert len(recs) == 1
    r = recs[0]
    assert r["lei"] == "5493001KJTIIGC8Y1R12"
    assert r["legal_name"] == "Bad Actor LLC"
    assert r["country"] == "US"
    assert r["status"] == "ACTIVE"

def test_search_by_name_uses_injected_fetcher():
    captured = {}
    def fake(url: str) -> bytes:
        captured["url"] = url
        return _GLEIF_JSON
    recs = search_by_name("Bad Actor LLC", fetcher=fake)
    assert recs[0]["lei"] == "5493001KJTIIGC8Y1R12"
    assert captured["url"].startswith(GLEIF_SEARCH_URL)
    assert "Bad+Actor+LLC" in captured["url"] or "Bad%20Actor%20LLC" in captured["url"]


def test_parse_lei_records_non_dict_top_level():
    """Bare array at top level must return [] without raising."""
    assert parse_lei_records(b"[]") == []


def test_parse_lei_records_non_dict_item():
    """Non-dict items inside 'data' must be skipped gracefully."""
    assert parse_lei_records(b'{"data":[null]}') == []
