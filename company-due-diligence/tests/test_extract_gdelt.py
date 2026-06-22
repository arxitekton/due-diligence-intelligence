from cdd.extract.gdelt import GDELT_DOC_URL, parse_articles, search_adverse_media

_GDELT_JSON = (
    b'{"articles":[{"url":"https://news.example/x","title":"Firm probed",'
    b'"seendate":"20260615T120000Z","domain":"news.example","language":"English"}]}'
)


def test_parse_articles():
    arts = parse_articles(_GDELT_JSON)
    assert arts == [{
        "url": "https://news.example/x", "title": "Firm probed",
        "seendate": "20260615T120000Z", "domain": "news.example",
        "language": "English",
    }]


def test_parse_articles_empty_on_blank():
    assert parse_articles(b"") == []
    assert parse_articles(b"{}") == []


def test_search_adverse_media_injected_fetcher():
    captured = {}

    def fake(url: str) -> bytes:
        captured["url"] = url
        return _GDELT_JSON

    arts = search_adverse_media('"Bad Actor LLC" (fraud OR sanctions)', fetcher=fake)
    assert arts[0]["domain"] == "news.example"
    assert captured["url"].startswith(GDELT_DOC_URL)
    assert "mode=artlist" in captured["url"] and "format=json" in captured["url"]
