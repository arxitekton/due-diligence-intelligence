"""Wikidata entity-enrichment connector (keyless, CC0).

Pure JSON parse core (offline-testable) + injectable fetcher over the
SSRF-guarded ``cdd.extract.fetch.get``. Uses the Wikidata Action API
(``wbsearchentities`` for name → entity resolution, ``wbgetentities`` for
claims). Structured Wikidata is CC0 — store/redistribute freely. Complements
GLEIF for entity disambiguation (e.g. cross-checking the LEI, official website).
source_class: knowledge_graph (Tier-3 signal — crowd-sourced; verify before
asserting as fact).
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any, cast
from urllib.parse import urlencode

WIKIDATA_API_URL = "https://www.wikidata.org/w/api.php"

# Curated due-diligence properties → readable field names. Q-id-valued fields
# (country/industry/parent/legal_form) hold Wikidata item refs, not labels.
DD_PROPERTIES: dict[str, str] = {
    "P1278": "lei",
    "P856": "official_website",
    "P17": "country",
    "P452": "industry",
    "P749": "parent_organization",
    "P571": "inception",
    "P946": "isin",
    "P414": "stock_exchange",
    "P1320": "opencorporates_id",
    "P1454": "legal_form",
}


def _default_fetcher(url: str) -> bytes:
    from cdd.extract.fetch import get

    content, _ = get(url)
    return content


# ---------------------------------------------------------------------------
# Entity search (wbsearchentities)
# ---------------------------------------------------------------------------


def parse_search(data: bytes) -> list[dict[str, Any]]:
    """Parse a ``wbsearchentities`` response into ``{id,label,description,url}``."""
    raw: Any = json.loads(data.decode("utf-8"))
    payload: dict[str, Any] = cast("dict[str, Any]", raw) if isinstance(raw, dict) else {}
    search_raw = payload.get("search")
    search: list[Any] = cast("list[Any]", search_raw) if isinstance(search_raw, list) else []
    hits: list[dict[str, Any]] = []
    for h in search:
        if not isinstance(h, dict):
            continue
        h_d: dict[str, Any] = cast("dict[str, Any]", h)
        display_raw = h_d.get("display")
        display: dict[str, Any] = (
            cast("dict[str, Any]", display_raw) if isinstance(display_raw, dict) else {}
        )

        def _disp(field: str, disp: dict[str, Any] = display) -> str:
            obj = disp.get(field)
            if isinstance(obj, dict):
                return str(cast("dict[str, Any]", obj).get("value", ""))
            return ""

        hits.append(
            {
                "id": str(h_d.get("id", "")),
                "label": str(h_d.get("label") or _disp("label")),
                "description": str(h_d.get("description") or _disp("description")),
                "url": str(h_d.get("url", "")),
            }
        )
    return hits


def search_entities(
    name: str, *, limit: int = 5, fetcher: Callable[[str], bytes] | None = None
) -> list[dict[str, Any]]:
    """Search Wikidata for entities matching ``name`` (English labels)."""
    query = urlencode(
        {
            "action": "wbsearchentities",
            "search": name,
            "language": "en",
            "format": "json",
            "limit": limit,
        }
    )
    fetch = fetcher or _default_fetcher
    return parse_search(fetch(f"{WIKIDATA_API_URL}?{query}"))


# ---------------------------------------------------------------------------
# Entity facts (wbgetentities claims)
# ---------------------------------------------------------------------------


def _claim_value(mainsnak: dict[str, Any]) -> Any:
    """Decode a single claim mainsnak to a scalar across Wikidata value types."""
    if mainsnak.get("snaktype") != "value":
        return None
    dv = mainsnak.get("datavalue")
    dv = cast("dict[str, Any]", dv) if isinstance(dv, dict) else {}
    dtype = dv.get("type")
    val = dv.get("value")
    if dtype == "wikibase-entityid" and isinstance(val, dict):
        return cast("dict[str, Any]", val).get("id")
    if dtype == "string":
        return val
    if dtype == "time" and isinstance(val, dict):
        return cast("dict[str, Any]", val).get("time")
    if dtype == "quantity" and isinstance(val, dict):
        return cast("dict[str, Any]", val).get("amount")
    if dtype == "monolingualtext" and isinstance(val, dict):
        return cast("dict[str, Any]", val).get("text")
    return None  # globecoordinate / unknown → skip


def parse_entity_facts(data: bytes, qid: str) -> dict[str, Any]:
    """Parse ``wbgetentities`` claims for ``qid`` into curated DD fields.

    Returns ``{"qid": qid, "facts": {field: [values...]}}`` for the properties in
    ``DD_PROPERTIES`` that are present. Q-id-valued fields hold Wikidata item refs.
    """
    raw: Any = json.loads(data.decode("utf-8"))
    payload: dict[str, Any] = cast("dict[str, Any]", raw) if isinstance(raw, dict) else {}
    entities = payload.get("entities")
    entities = cast("dict[str, Any]", entities) if isinstance(entities, dict) else {}
    entity = entities.get(qid)
    entity = cast("dict[str, Any]", entity) if isinstance(entity, dict) else {}
    claims = entity.get("claims")
    claims = cast("dict[str, Any]", claims) if isinstance(claims, dict) else {}

    facts: dict[str, list[Any]] = {}
    for pid, field in DD_PROPERTIES.items():
        statements = claims.get(pid)
        if not isinstance(statements, list):
            continue
        values: list[Any] = []
        for st in cast("list[Any]", statements):
            if not isinstance(st, dict):
                continue
            mainsnak = cast("dict[str, Any]", st).get("mainsnak")
            if not isinstance(mainsnak, dict):
                continue
            v = _claim_value(cast("dict[str, Any]", mainsnak))
            if v is not None:
                values.append(v)
        if values:
            facts[field] = values
    return {"qid": qid, "facts": facts}


def get_entity_facts(
    qid: str, *, fetcher: Callable[[str], bytes] | None = None
) -> dict[str, Any]:
    """Fetch + parse curated DD facts for a Wikidata entity (e.g. ``Q102673``)."""
    query = urlencode(
        {"action": "wbgetentities", "ids": qid, "props": "claims", "format": "json"}
    )
    fetch = fetcher or _default_fetcher
    return parse_entity_facts(fetch(f"{WIKIDATA_API_URL}?{query}"), qid)
