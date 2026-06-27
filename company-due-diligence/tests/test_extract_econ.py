import pytest

from cdd.extract import ExtractorUnavailable
from cdd.extract.econ import (
    BLS_SERIES_URL,
    EUROSTAT_BASE_URL,
    OECD_BASE_URL,
    WORLD_BANK_URL,
    fetch_bls_series,
    fetch_eurostat,
    fetch_oecd,
    fetch_world_bank,
    parse_bls,
    parse_eurostat,
    parse_oecd,
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


# Real-sampled Eurostat JSON-stat 2.0 (nama_10_gdp, B1GQ/CP_MEUR, DE+FR x 2022+2023).
# Exercises the flat-index → (geo, time) row-major decode. dims order [freq,unit,
# na_item,geo,time], size [1,1,1,2,2] → index 3 = geo=FR(1), time=2023(1).
_EUROSTAT_JSON = (
    b'{"version":"2.0","class":"dataset","label":"GDP","source":"ESTAT",'
    b'"value":{"0":3989390.0,"1":4219310.0,"2":2653997.2,"3":2833826.4},'
    b'"id":["freq","unit","na_item","geo","time"],"size":[1,1,1,2,2],'
    b'"dimension":{'
    b'"freq":{"category":{"index":{"A":0}}},'
    b'"unit":{"category":{"index":{"CP_MEUR":0}}},'
    b'"na_item":{"category":{"index":{"B1GQ":0}}},'
    b'"geo":{"category":{"index":{"DE":0,"FR":1}}},'
    b'"time":{"category":{"index":{"2022":0,"2023":1}}}}}'
)


def test_parse_eurostat_decodes_jsonstat_indices():
    obs = parse_eurostat(_EUROSTAT_JSON)
    assert len(obs) == 4
    de22 = next(o for o in obs if o["area"] == "DE" and o["period"] == "2022")
    assert de22["value"] == 3989390.0 and de22["series"] == "B1GQ" and de22["source"] == "EUROSTAT"
    fr23 = next(o for o in obs if o["area"] == "FR" and o["period"] == "2023")
    assert fr23["value"] == 2833826.4  # last flat index decodes to FR/2023
    assert fr23["dims"]["unit"] == "CP_MEUR"


def test_parse_eurostat_empty_on_garbage():
    assert parse_eurostat(b"{}") == []
    assert parse_eurostat(b"null") == []


def test_fetch_eurostat_expands_list_params():
    captured = {}

    def fake(url: str) -> bytes:
        captured["url"] = url
        return _EUROSTAT_JSON

    obs = fetch_eurostat(
        "nama_10_gdp", params={"na_item": "B1GQ", "geo": ["DE", "FR"]}, fetcher=fake
    )
    assert len(obs) == 4
    assert captured["url"].startswith(f"{EUROSTAT_BASE_URL}/nama_10_gdp")
    assert "geo=DE" in captured["url"] and "geo=FR" in captured["url"]  # list expanded
    assert "format=JSON" in captured["url"]


# Real-shaped OECD SDMX-JSON (AllDimensions): observations keyed by colon-joined
# dimension positions; structures[0].dimensions.observation gives the code lists.
# 3 dims [REF_AREA, MEASURE, TIME_PERIOD] → key "1:0:0" = FRA / LI / 2026-Q1.
_OECD_JSON = (
    b'{"data":{"dataSets":[{"observations":{'
    b'"0:0:0":[101.5,0],"1:0:0":[99.2,0]}}],'
    b'"structures":[{"name":"Composite leading indicators","dimensions":{"observation":['
    b'{"id":"REF_AREA","values":[{"id":"USA","name":"United States"},'
    b'{"id":"FRA","name":"France"}]},'
    b'{"id":"MEASURE","values":[{"id":"LI","name":"CLI"}]},'
    b'{"id":"TIME_PERIOD","values":[{"id":"2026-Q1","name":"2026-Q1"}]}]}}]}}'
)


def test_parse_oecd_decodes_positional_keys():
    obs = parse_oecd(_OECD_JSON)
    assert len(obs) == 2
    usa = next(o for o in obs if o["area"] == "USA")
    assert usa["source"] == "OECD" and usa["series"] == "LI"
    assert usa["period"] == "2026-Q1" and usa["value"] == 101.5
    fra = next(o for o in obs if o["area"] == "FRA")
    assert fra["value"] == 99.2


def test_parse_oecd_empty_on_garbage():
    assert parse_oecd(b"{}") == []
    assert parse_oecd(b'{"data":{}}') == []


def test_fetch_oecd_builds_sdmx_url():
    captured = {}

    def fake(url: str) -> bytes:
        captured["url"] = url
        return _OECD_JSON

    obs = fetch_oecd(
        "OECD.SDD.STES,DSD_STES@DF_CLI,4.1", params={"lastNObservations": 1}, fetcher=fake
    )
    assert len(obs) == 2
    assert captured["url"].startswith(f"{OECD_BASE_URL}/OECD.SDD.STES,DSD_STES@DF_CLI,4.1/all")
    assert "dimensionAtObservation=AllDimensions" in captured["url"]
    assert "lastNObservations=1" in captured["url"]
