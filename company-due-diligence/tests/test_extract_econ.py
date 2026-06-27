import pytest

from cdd.extract import ExtractorUnavailable
from cdd.extract.econ import (
    BLS_SERIES_URL,
    WORLD_BANK_URL,
    fetch_bls_series,
    fetch_world_bank,
    parse_bls,
    parse_world_bank,
)

# Real-sampled BLS v1 shape (CUUR0000SA0 = CPI-U), trimmed to two observations.
_BLS_JSON = (
    b'{"status":"REQUEST_SUCCEEDED","responseTime":116,"message":[],"Results":{'
    b'"series":[{"seriesID":"CUUR0000SA0","data":['
    b'{"year":"2026","period":"M05","periodName":"May","value":"335.123","footnotes":[{}]},'
    b'{"year":"2026","period":"M04","periodName":"April","value":"333.020","footnotes":[{}]}'
    b"]}]}}"
)

# Real-sampled World Bank shape: [metadata, [observations]]; note value can be null.
_WB_JSON = (
    b'[{"page":1,"pages":33,"per_page":2,"total":66,"lastupdated":"2026-04-08"},'
    b'[{"indicator":{"id":"NY.GDP.MKTP.CD","value":"GDP (current US$)"},'
    b'"country":{"id":"US","value":"United States"},"countryiso3code":"USA",'
    b'"date":"2025","value":null},'
    b'{"indicator":{"id":"NY.GDP.MKTP.CD","value":"GDP (current US$)"},'
    b'"country":{"id":"US","value":"United States"},"countryiso3code":"USA",'
    b'"date":"2024","value":29184890000000.0}]]'
)


def test_parse_bls():
    obs = parse_bls(_BLS_JSON)
    assert len(obs) == 2
    assert obs[0] == {
        "source": "BLS", "series": "CUUR0000SA0", "area": None,
        "period": "2026-M05", "value": 335.123, "label": "May",
    }


def test_parse_bls_raises_on_failure_status():
    body = b'{"status":"REQUEST_NOT_PROCESSED","message":["daily threshold reached"],"Results":{}}'
    with pytest.raises(ExtractorUnavailable):
        parse_bls(body)


def test_parse_world_bank_keeps_null_value():
    obs = parse_world_bank(_WB_JSON)
    assert len(obs) == 2
    assert obs[0]["source"] == "WORLD_BANK"
    assert obs[0]["series"] == "NY.GDP.MKTP.CD"
    assert obs[0]["area"] == "US"
    assert obs[0]["period"] == "2025"
    assert obs[0]["value"] is None  # reported gap, preserved (not dropped)
    assert obs[1]["value"] == 29184890000000.0


def test_parse_world_bank_metadata_only_returns_empty():
    # An error/empty response is a bare metadata object, not the 2-element list.
    assert parse_world_bank(b'[{"message":[{"id":"120","value":"invalid"}]}]') == []


def test_fetch_bls_series_injected_fetcher():
    captured = {}

    def fake(url: str) -> bytes:
        captured["url"] = url
        return _BLS_JSON

    obs = fetch_bls_series("CUUR0000SA0", fetcher=fake)
    assert obs[0]["series"] == "CUUR0000SA0"
    assert captured["url"] == f"{BLS_SERIES_URL}CUUR0000SA0"


def test_fetch_world_bank_injected_fetcher():
    captured = {}

    def fake(url: str) -> bytes:
        captured["url"] = url
        return _WB_JSON

    obs = fetch_world_bank("US", "NY.GDP.MKTP.CD", fetcher=fake)
    assert obs[1]["value"] == 29184890000000.0
    assert captured["url"].startswith(f"{WORLD_BANK_URL}/country/US/indicator/NY.GDP.MKTP.CD")
    assert "format=json" in captured["url"]
