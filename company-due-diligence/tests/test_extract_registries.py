from cdd.extract.registries import (
    ARES_URL,
    ARIREGISTER_URL,
    BRREG_URL,
    PRH_URL,
    lookup_ares,
    parse_ares,
    parse_ariregister,
    parse_brreg,
    parse_prh,
    search_ariregister,
    search_brreg,
    search_prh,
)

# --- Real-sampled fixtures (trimmed) ---------------------------------------

_BRREG_JSON = (
    b'{"_embedded":{"enheter":[{"organisasjonsnummer":"923609016","navn":"EQUINOR ASA",'
    b'"organisasjonsform":{"kode":"ASA"},"konkurs":false,'
    b'"forretningsadresse":{"land":"Norge","postnummer":"4035","poststed":"STAVANGER",'
    b'"adresse":["Forusbeen 50"]}}]}}'
)

_ARES_JSON = (
    b'{"ico":"45274649","obchodniJmeno":"\xc4\x8cEZ, a. s.",'
    b'"sidlo":{"textovaAdresa":"Duhov\xc3\xa1 1444/2, Michle, 14000 Praha 4"}}'
)

_PRH_JSON = (
    b'{"totalResults":1,"companies":[{"businessId":{"value":"0112038-9"},'
    b'"names":[{"name":"OLD NAME OY","endDate":"2020-01-01"},'
    b'{"name":"Nokia Oyj","version":1}],"tradeRegisterStatus":"2"}]}'
)

_EE_JSON = (
    b'{"status":"OK","data":[{"company_id":9000439617,"reg_code":17449106,'
    b'"name":"Bolt App Services AS","status":"R",'
    b'"legal_address":"Harju maakond, Tallinn, Vana-L\xc3\xb5una tn 15","zip_code":"10134",'
    b'"url":"https://ariregister.rik.ee/est/company/17449106/Bolt-App-Services-AS"}]}'
)


def test_parse_brreg():
    rows = parse_brreg(_BRREG_JSON)
    assert rows == [{
        "source": "BRREG", "jurisdiction": "NO", "reg_number": "923609016",
        "name": "EQUINOR ASA", "status": "active",
        "address": "Forusbeen 50, 4035 STAVANGER, Norge", "url": None,
    }]


def test_parse_ares():
    rows = parse_ares(_ARES_JSON)
    assert rows[0]["jurisdiction"] == "CZ"
    assert rows[0]["reg_number"] == "45274649"
    assert rows[0]["name"] == "ČEZ, a. s."
    assert rows[0]["address"].startswith("Duhová 1444/2")


def test_parse_ares_empty_on_no_ico():
    assert parse_ares(b'{"kod":404}') == []


def test_parse_prh_picks_current_name():
    rows = parse_prh(_PRH_JSON)
    assert rows[0]["reg_number"] == "0112038-9"
    assert rows[0]["name"] == "Nokia Oyj"  # the entry without an endDate, not "OLD NAME OY"
    assert rows[0]["status"] == "2"


def test_parse_ariregister():
    rows = parse_ariregister(_EE_JSON)
    assert rows[0]["reg_number"] == "17449106"  # int coerced to str
    assert rows[0]["name"] == "Bolt App Services AS"
    assert rows[0]["status"] == "R"
    assert rows[0]["address"].endswith("10134")
    assert rows[0]["url"].startswith("https://ariregister.rik.ee")


def test_parsers_empty_on_garbage():
    for fn in (parse_brreg, parse_ares, parse_prh, parse_ariregister):
        assert fn(b"{}") == []
        assert fn(b"null") == []


def test_search_brreg_injected_fetcher():
    captured = {}

    def fake(url: str) -> bytes:
        captured["url"] = url
        return _BRREG_JSON

    rows = search_brreg("Equinor", fetcher=fake)
    assert rows[0]["reg_number"] == "923609016"
    assert captured["url"].startswith(BRREG_URL) and "navn=Equinor" in captured["url"]


def test_lookup_ares_injected_fetcher():
    captured = {}

    def fake(url: str) -> bytes:
        captured["url"] = url
        return _ARES_JSON

    rows = lookup_ares("45274649", fetcher=fake)
    assert rows[0]["name"] == "ČEZ, a. s."
    assert captured["url"] == f"{ARES_URL}/45274649"


def test_search_prh_and_ariregister_urls():
    captured = {}

    def fake_prh(url: str) -> bytes:
        captured["prh"] = url
        return _PRH_JSON

    def fake_ee(url: str) -> bytes:
        captured["ee"] = url
        return _EE_JSON

    assert search_prh("Nokia", fetcher=fake_prh)[0]["name"] == "Nokia Oyj"
    assert captured["prh"].startswith(PRH_URL) and "name=Nokia" in captured["prh"]
    assert search_ariregister("Bolt", fetcher=fake_ee)[0]["status"] == "R"
    assert captured["ee"].startswith(ARIREGISTER_URL) and "q=Bolt" in captured["ee"]
