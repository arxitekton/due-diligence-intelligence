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
