import pytest

from cdd.extract.sanctions import (
    OFFICIAL_LISTS,
    fetch_and_screen,
    parse_sdn_csv,
    screen_name,
)

# Minimal OFAC SDN.CSV-style fixture (real format: ent_num,SDN_Name,SDN_Type,Program,...)
_SDN = (
    b'1,"BAD ACTOR LLC","entity","RUSSIA-EO14024","-0-","-0-","-0-","-0-","-0-","-0-","-0-","aka GOOD FRONT"\n'  # noqa: E501
    b'2,"ACME ANALYTICS","entity","UKRAINE-EO13662","-0-","-0-","-0-","-0-","-0-","-0-","-0-","-0-"\n'  # noqa: E501
)


def test_parse_sdn_csv():
    rows = parse_sdn_csv(_SDN)
    assert len(rows) == 2
    assert rows[0]["list"] == "OFAC-SDN"
    assert rows[0]["entry_id"] == "1"
    assert rows[0]["name"] == "BAD ACTOR LLC"
    assert rows[0]["program"] == "RUSSIA-EO14024"
    assert rows[1]["remarks"] is None  # "-0-" → None


def test_screen_name_exact_and_partial():
    rows = parse_sdn_csv(_SDN)
    exact = screen_name("Acme Analytics", rows)
    assert len(exact) == 1 and exact[0]["match_type"] == "exact"
    assert exact[0]["program"] == "UKRAINE-EO13662"
    partial = screen_name("Bad Actor", rows)
    assert len(partial) == 1 and partial[0]["match_type"] == "partial"
    assert screen_name("Totally Unrelated Inc", rows) == []


def test_parser_extracts_aliases_from_remarks():
    # OFAC encodes alternate names as "aka …" inside Remarks. The parser must
    # surface them so alias-only listings are screenable (false-negative guard).
    rows = parse_sdn_csv(_SDN)
    assert rows[0]["aliases"] == ["GOOD FRONT"]


def test_alias_matching_hits_front_name():
    # An entity listed only under an alias/front name must still match.
    rows = parse_sdn_csv(_SDN)
    hits = screen_name("Good Front", rows)
    assert len(hits) == 1
    assert hits[0]["name"] == "BAD ACTOR LLC"
    assert hits[0]["match_type"] == "exact"  # normalized alias equals query


def test_single_token_query_does_not_flood_partials():
    # A lone generic token must NOT produce token-subset "partial" candidates.
    rows = parse_sdn_csv(_SDN)
    assert screen_name("Acme", rows) == []   # no exact "acme"; partial suppressed
    assert screen_name("Bad", rows) == []    # single token → no partial flood
    # but a genuine single-token exact match still fires:
    one = parse_sdn_csv(b'9,"GAZPROM","entity","RUSSIA-EO14024","-0-","-0-","-0-","-0-","-0-","-0-","-0-","-0-"\n')  # noqa: E501
    assert len(screen_name("Gazprom", one)) == 1


def test_official_lists_has_core_lists():
    assert "OFAC-SDN" in OFFICIAL_LISTS
    assert OFFICIAL_LISTS["OFAC-SDN"].startswith("https://")


def test_fetch_and_screen_with_injected_fetcher():
    captured = {}

    def fake_fetcher(url: str) -> bytes:
        captured["url"] = url
        return _SDN

    hits = fetch_and_screen("Bad Actor LLC", list_id="OFAC-SDN", fetcher=fake_fetcher)
    assert captured["url"] == OFFICIAL_LISTS["OFAC-SDN"]
    assert len(hits) == 1 and hits[0]["list"] == "OFAC-SDN"


def test_fetch_and_screen_unknown_list():
    with pytest.raises(ValueError):
        fetch_and_screen("x", list_id="NOPE", fetcher=lambda u: b"")


_UN_XML = (
    b'<?xml version="1.0" encoding="UTF-8"?>'
    b"<CONSOLIDATED_LIST><INDIVIDUALS>"
    b"<INDIVIDUAL><DATAID>1</DATAID><FIRST_NAME>Jane</FIRST_NAME>"
    b"<SECOND_NAME>Doe</SECOND_NAME><UN_LIST_TYPE>Al-Qaida</UN_LIST_TYPE>"
    b"<INDIVIDUAL_ALIAS><ALIAS_NAME>J. Doe</ALIAS_NAME></INDIVIDUAL_ALIAS>"
    b"</INDIVIDUAL></INDIVIDUALS>"
    b"<ENTITIES><ENTITY><DATAID>2</DATAID>"
    b"<FIRST_NAME>Bad Actor LLC</FIRST_NAME><UN_LIST_TYPE>Al-Qaida</UN_LIST_TYPE>"
    b"</ENTITY></ENTITIES></CONSOLIDATED_LIST>"
)

def test_parse_un_xml_individuals_and_entities():
    from cdd.extract.sanctions import parse_un_xml
    entries = parse_un_xml(_UN_XML)
    ind = next(e for e in entries if e["entry_id"] == "1")
    assert ind["list"] == "UN-CONSOLIDATED"
    assert ind["name"] == "Jane Doe"
    assert "J. Doe" in ind["aliases"]
    assert ind["type"] == "individual"
    assert ind["program"] == "Al-Qaida"
    ent = next(e for e in entries if e["entry_id"] == "2")
    assert ent["name"] == "Bad Actor LLC"
    assert ent["type"] == "entity"


_BIS_JSON = (
    b'{"results":[{"id":"abc-1","name":"Bad Actor LLC",'
    b'"alt_names":["Bad Actor OOO"],"source":"Entity List (EL)",'
    b'"programs":["EAR"]},'
    b'{"id":"abc-2","name":"Jane Doe","alt_names":[],'
    b'"source":"Denied Persons List (DPL)","programs":["EAR"]}]}'
)

def test_parse_bis_csl_json():
    from cdd.extract.sanctions import parse_bis_csl_json
    entries = parse_bis_csl_json(_BIS_JSON)
    assert len(entries) == 2
    e = entries[0]
    assert e["list"] == "BIS-CSL"
    assert e["entry_id"] == "abc-1"
    assert e["name"] == "Bad Actor LLC"
    assert e["aliases"] == ["Bad Actor OOO"]
    assert e["type"] == "Entity List (EL)"
    assert e["program"] == "EAR"


_EU_CSV = (
    "Entity_LogicalId;NameAlias_WholeName;Entity_SubjectType;Entity_Regulation_Programme\r\n"
    "13;Bad Actor LLC;enterprise;RUS\r\n"
    "13;Bad Actor OOO;enterprise;RUS\r\n"
    "14;Jane Doe;person;RUS\r\n"
).encode("utf-8")

def test_parse_eu_csv_groups_by_logical_id():
    from cdd.extract.sanctions import parse_eu_csv
    entries = parse_eu_csv(_EU_CSV)
    assert len(entries) == 2
    e = next(x for x in entries if x["entry_id"] == "13")
    assert e["list"] == "EU-CONSOLIDATED"
    assert e["name"] == "Bad Actor LLC"
    assert "Bad Actor OOO" in e["aliases"]
    assert e["type"] == "enterprise"
    assert e["program"] == "RUS"


_UK_FCDO_CSV = (
    "Unique ID,OFSI Group ID,Name 1,Name 2,Name 3,Name 4,Name 5,Name 6,"
    "Alias Type,Regime,Individual/Entity/Ship\r\n"
    "UKS0001,GRP1,Bad,,,Actor,LLC,,Primary name,Russia,Entity\r\n"
    "UKS0001,GRP1,Bad,,,Actor,Limited,,AKA,Russia,Entity\r\n"
    "UKS0002,GRP2,Jane,,,Doe,,,Primary name,Russia,Individual\r\n"
).encode("utf-8")

def test_parse_uk_fcdo_csv_groups_aliases():
    from cdd.extract.sanctions import parse_uk_fcdo_csv
    entries = parse_uk_fcdo_csv(_UK_FCDO_CSV)
    assert len(entries) == 2  # grouped by Unique ID
    e = next(x for x in entries if x["entry_id"] == "UKS0001")
    assert e["list"] == "UK-FCDO"
    assert e["name"] == "Bad Actor LLC"
    assert "Bad Actor Limited" in e["aliases"]
    assert e["type"] == "Entity"
    assert e["program"] == "Russia"


def test_official_lists_has_all_priority1_lists():
    from cdd.extract.sanctions import OFFICIAL_LISTS, LIST_METADATA
    for lid in ("OFAC-SDN", "EU-CONSOLIDATED", "UK-FCDO", "BIS-CSL", "UN-CONSOLIDATED"):
        assert lid in OFFICIAL_LISTS and OFFICIAL_LISTS[lid].startswith("https://")
        assert lid in LIST_METADATA
    # Dead OFSI list must be retired (withdrawn 2026-01-28).
    assert "UK-OFSI" not in OFFICIAL_LISTS
    # UN is ingest-to-screen only.
    assert LIST_METADATA["UN-CONSOLIDATED"]["retention_policy"] == "session_only"
    assert LIST_METADATA["OFAC-SDN"]["retention_policy"] == "indefinite"
