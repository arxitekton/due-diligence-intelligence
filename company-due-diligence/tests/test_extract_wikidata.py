from cdd.extract.wikidata import (
    WIKIDATA_API_URL,
    get_entity_facts,
    parse_entity_facts,
    parse_search,
    search_entities,
)

# Real-sampled wbsearchentities shape (Gazprom = Q102673), label/description in display.*
_SEARCH_JSON = (
    b'{"search":[{"id":"Q102673","title":"Q102673","url":"//www.wikidata.org/wiki/Q102673",'
    b'"display":{"label":{"value":"Gazprom","language":"en"},'
    b'"description":{"value":"Russian oil and gas company","language":"en"}}}]}'
)

# Real-sampled wbgetentities claims: P17 (item), P856 (url), P571 (time), P1278 (LEI string).
_CLAIMS_JSON = (
    b'{"entities":{"Q102673":{"claims":{'
    b'"P17":[{"mainsnak":{"snaktype":"value","datatype":"wikibase-item",'
    b'"datavalue":{"type":"wikibase-entityid","value":{"entity-type":"item","id":"Q159"}}}}],'
    b'"P856":[{"mainsnak":{"snaktype":"value","datatype":"url",'
    b'"datavalue":{"type":"string","value":"https://www.gazprom.ru/"}}}],'
    b'"P571":[{"mainsnak":{"snaktype":"value","datatype":"time",'
    b'"datavalue":{"type":"time","value":{"time":"+1989-01-01T00:00:00Z","precision":9}}}}],'
    b'"P1278":[{"mainsnak":{"snaktype":"value","datatype":"external-id",'
    b'"datavalue":{"type":"string","value":"2534008CWQ1G8CXEU523"}}}]}}}}'
)


def test_parse_search_reads_display_label():
    hits = parse_search(_SEARCH_JSON)
    assert hits == [{
        "id": "Q102673", "label": "Gazprom",
        "description": "Russian oil and gas company",
        "url": "//www.wikidata.org/wiki/Q102673",
    }]


def test_parse_search_empty_on_garbage():
    assert parse_search(b"{}") == []
    assert parse_search(b"null") == []


def test_parse_entity_facts_decodes_value_types():
    out = parse_entity_facts(_CLAIMS_JSON, "Q102673")
    assert out["qid"] == "Q102673"
    f = out["facts"]
    assert f["country"] == ["Q159"]                       # wikibase-entityid → id
    assert f["official_website"] == ["https://www.gazprom.ru/"]  # url/string
    assert f["inception"] == ["+1989-01-01T00:00:00Z"]    # time → time string
    assert f["lei"] == ["2534008CWQ1G8CXEU523"]           # external-id/string


def test_parse_entity_facts_missing_entity_returns_empty_facts():
    assert parse_entity_facts(b'{"entities":{}}', "Q999")["facts"] == {}


def test_search_entities_injected_fetcher():
    captured = {}

    def fake(url: str) -> bytes:
        captured["url"] = url
        return _SEARCH_JSON

    hits = search_entities("Gazprom", fetcher=fake)
    assert hits[0]["id"] == "Q102673"
    assert captured["url"].startswith(WIKIDATA_API_URL)
    assert "action=wbsearchentities" in captured["url"] and "search=Gazprom" in captured["url"]


def test_get_entity_facts_injected_fetcher():
    captured = {}

    def fake(url: str) -> bytes:
        captured["url"] = url
        return _CLAIMS_JSON

    out = get_entity_facts("Q102673", fetcher=fake)
    assert out["facts"]["lei"] == ["2534008CWQ1G8CXEU523"]
    assert "action=wbgetentities" in captured["url"] and "ids=Q102673" in captured["url"]
