import base64

import pytest

from cdd.extract import ExtractorUnavailable
from cdd.extract.companies_house import (
    CH_SEARCH_URL,
    _basic_auth_header,
    parse_company_search,
    search_companies,
)

_CH_JSON = (
    b'{"items":[{"company_number":"01234567","title":"BAD ACTOR LLP",'
    b'"company_status":"active","address_snippet":"1 High St, London"}]}'
)


def test_parse_company_search():
    rows = parse_company_search(_CH_JSON)
    assert rows == [{
        "company_number": "01234567", "title": "BAD ACTOR LLP",
        "status": "active", "address": "1 High St, London",
    }]


def test_basic_auth_header_encodes_key_as_username():
    assert _basic_auth_header("KEY123") == "Basic " + base64.b64encode(b"KEY123:").decode()


def test_search_companies_injected_fetcher():
    captured = {}

    def fake(url: str, headers: dict[str, str]) -> bytes:
        captured["url"], captured["headers"] = url, headers
        return _CH_JSON

    rows = search_companies("Bad Actor", api_key="KEY123", fetcher=fake)
    assert rows[0]["company_number"] == "01234567"
    assert captured["url"].startswith(CH_SEARCH_URL)
    assert captured["headers"]["Authorization"].startswith("Basic ")


def test_search_companies_requires_key():
    with pytest.raises(ExtractorUnavailable):
        search_companies("x", api_key=None, fetcher=lambda u, h: b"{}")
