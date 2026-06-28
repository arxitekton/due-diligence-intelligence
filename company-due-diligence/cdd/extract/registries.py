"""Open national company-registry connectors (keyless).

Pure JSON parse core (offline-testable) + injectable fetcher over the
SSRF-guarded ``cdd.extract.fetch.get``. Each registry is a separate official
open API; all are keyless. Every parser emits the same normalized record::

    {"source", "jurisdiction", "reg_number", "name", "status", "address", "url"}

Registries (source_class: company_registry, Tier-1 primary):
- ``BRREG``      NO — Brønnøysund Enhetsregisteret (open REST, NLOD)
- ``ARES``       CZ — Registr ekonomických subjektů (open REST)
- ``PRH``        FI — PRH/YTJ Business Information System (avoindata, CC BY 4.0)
- ``ARIREGISTER`` EE — e-Business Register (open REST)

These complement GLEIF / Companies House / SEC EDGAR with EU/Nordic coverage.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any, cast
from urllib.parse import quote, urlencode

BRREG_URL = "https://data.brreg.no/enhetsregisteret/api/enheter"
ARES_URL = "https://ares.gov.cz/ekonomicke-subjekty-v-be/rest/ekonomicke-subjekty"
PRH_URL = "https://avoindata.prh.fi/opendata-ytj-api/v3/companies"
ARIREGISTER_URL = "https://ariregister.rik.ee/est/api/autocomplete"


def _d(x: Any) -> dict[str, Any]:
    return cast("dict[str, Any]", x) if isinstance(x, dict) else {}


def _l(x: Any) -> list[Any]:
    return cast("list[Any]", x) if isinstance(x, list) else []


def _s(x: Any) -> str:
    return str(x) if x is not None else ""


def _join(*parts: str) -> str | None:
    """Join non-empty address segments with ', '; None if all empty."""
    return ", ".join(p for p in parts if p) or None


def _default_fetcher(url: str) -> bytes:
    from cdd.extract.fetch import get

    content, _ = get(url)
    return content


# ---------------------------------------------------------------------------
# Norway — Brønnøysund Enhetsregisteret
# ---------------------------------------------------------------------------


def parse_brreg(data: bytes) -> list[dict[str, Any]]:
    """Parse a Brønnøysund ``/enheter`` search response."""
    embedded = _d(_d(json.loads(data.decode("utf-8"))).get("_embedded"))
    out: list[dict[str, Any]] = []
    for raw in _l(embedded.get("enheter")):
        e = _d(raw)
        fa = _d(e.get("forretningsadresse"))
        street = " ".join(_s(a) for a in _l(fa.get("adresse")) if _s(a))
        postcity = " ".join(p for p in (_s(fa.get("postnummer")), _s(fa.get("poststed"))) if p)
        addr = _join(street, postcity, _s(fa.get("land")))
        out.append(
            {
                "source": "BRREG",
                "jurisdiction": "NO",
                "reg_number": _s(e.get("organisasjonsnummer")),
                "name": _s(e.get("navn")),
                "status": "bankrupt" if e.get("konkurs") is True else "active",
                "address": addr,
                "url": None,
            }
        )
    return out


def search_brreg(
    name: str, *, size: int = 10, fetcher: Callable[[str], bytes] | None = None
) -> list[dict[str, Any]]:
    """Search the Norwegian register by company name."""
    url = f"{BRREG_URL}?{urlencode({'navn': name, 'size': size})}"
    return parse_brreg((fetcher or _default_fetcher)(url))


# ---------------------------------------------------------------------------
# Czech Republic — ARES
# ---------------------------------------------------------------------------


def parse_ares(data: bytes) -> list[dict[str, Any]]:
    """Parse an ARES single-entity (by-IČO) response."""
    d = _d(json.loads(data.decode("utf-8")))
    if not d.get("ico"):
        return []
    return [
        {
            "source": "ARES",
            "jurisdiction": "CZ",
            "reg_number": _s(d.get("ico")),
            "name": _s(d.get("obchodniJmeno")),
            "status": None,
            "address": _s(_d(d.get("sidlo")).get("textovaAdresa")) or None,
            "url": None,
        }
    ]


def lookup_ares(ico: str, *, fetcher: Callable[[str], bytes] | None = None) -> list[dict[str, Any]]:
    """Look up a Czech entity by its IČO (registration number)."""
    url = f"{ARES_URL}/{quote(ico)}"
    return parse_ares((fetcher or _default_fetcher)(url))


# ---------------------------------------------------------------------------
# Finland — PRH / YTJ
# ---------------------------------------------------------------------------


def parse_prh(data: bytes) -> list[dict[str, Any]]:
    """Parse a PRH/YTJ ``/companies`` search response.

    A company carries several ``names`` entries (with version/endDate); the
    current name is the first without an ``endDate``, else the first listed.
    """
    out: list[dict[str, Any]] = []
    for raw in _l(_d(json.loads(data.decode("utf-8"))).get("companies")):
        c = _d(raw)
        names = [_d(n) for n in _l(c.get("names"))]
        current = [n for n in names if not n.get("endDate")]
        pick = current[0] if current else (names[0] if names else {})
        out.append(
            {
                "source": "PRH",
                "jurisdiction": "FI",
                "reg_number": _s(_d(c.get("businessId")).get("value")),
                "name": _s(pick.get("name")),
                "status": _s(c.get("tradeRegisterStatus")) or None,
                "address": None,
                "url": None,
            }
        )
    return out


def search_prh(
    name: str, *, fetcher: Callable[[str], bytes] | None = None
) -> list[dict[str, Any]]:
    """Search the Finnish business register by company name."""
    url = f"{PRH_URL}?{urlencode({'name': name})}"
    return parse_prh((fetcher or _default_fetcher)(url))


# ---------------------------------------------------------------------------
# Estonia — e-Business Register
# ---------------------------------------------------------------------------


def parse_ariregister(data: bytes) -> list[dict[str, Any]]:
    """Parse an Estonian e-Business Register autocomplete response."""
    out: list[dict[str, Any]] = []
    for raw in _l(_d(json.loads(data.decode("utf-8"))).get("data")):
        r = _d(raw)
        out.append(
            {
                "source": "ARIREGISTER",
                "jurisdiction": "EE",
                "reg_number": _s(r.get("reg_code")),
                "name": _s(r.get("name")),
                "status": _s(r.get("status")) or None,
                "address": _join(_s(r.get("legal_address")), _s(r.get("zip_code"))),
                "url": _s(r.get("url")) or None,
            }
        )
    return out


def search_ariregister(
    name: str, *, fetcher: Callable[[str], bytes] | None = None
) -> list[dict[str, Any]]:
    """Search the Estonian e-Business Register by company name."""
    url = f"{ARIREGISTER_URL}?{urlencode({'q': name})}"
    return parse_ariregister((fetcher or _default_fetcher)(url))
