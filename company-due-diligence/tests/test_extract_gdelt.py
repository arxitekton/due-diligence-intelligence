import pytest

from cdd.extract import ExtractorUnavailable
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


def test_parse_articles_non_dict_top_level():
    """Non-dict top-level (e.g. null) must return [] without raising."""
    assert parse_articles(b"null") == []


def test_parse_articles_non_dict_item():
    """Non-dict items inside 'articles' must be skipped gracefully."""
    assert parse_articles(b'{"articles":[null]}') == []


def test_parse_articles_rate_limit_body_raises():
    """A non-JSON throttle/error body (GDELT's 1-req/5s limit) surfaces a clear
    ExtractorUnavailable, not an opaque JSONDecodeError, and is not mistaken for
    an empty result set."""
    body = b"Please limit requests to one every 5 seconds or contact ...\n\n"
    with pytest.raises(ExtractorUnavailable):
        parse_articles(body)
