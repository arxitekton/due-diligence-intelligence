"""GLEIF LEI reference-data lookup (CC0, no auth).

Pure JSON parsing core (offline-testable) + an injectable fetcher defaulting to
the SSRF-guarded ``cdd.extract.fetch.get``. License: CC0 1.0 — extracted data
may be stored and redistributed freely. source_class: lei_registry.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any
from urllib.parse import urlencode

GLEIF_SEARCH_URL = "https://api.gleif.org/api/v1/lei-records"


def parse_lei_records(data: bytes) -> list[dict[str, Any]]:
    """Parse a GLEIF lei-records JSON-API response into flat record dicts."""
    payload: Any = json.loads(data.decode("utf-8"))
    records: list[dict[str, Any]] = []
    for item in payload.get("data", []):
        attrs: dict[str, Any] = item.get("attributes", {})
        entity: dict[str, Any] = attrs.get("entity", {})
        legal_name_obj: dict[str, Any] = entity.get("legalName") or {}
        legal_name: str = legal_name_obj.get("name", "")
        legal_address_obj: dict[str, Any] = entity.get("legalAddress") or {}
        country: str = legal_address_obj.get("country", "")
        records.append(
            {
                "lei": attrs.get("lei", ""),
                "legal_name": legal_name,
                "country": country,
                "status": entity.get("status", ""),
            }
        )
    return records


def _default_fetcher(url: str) -> bytes:
    from cdd.extract.fetch import get

    content, _ = get(url)
    return content


def search_by_name(
    name: str, *, fetcher: Callable[[str], bytes] | None = None
) -> list[dict[str, Any]]:
    """Search GLEIF for LEI records whose legal name matches ``name``."""
    query = urlencode({"filter[entity.legalName]": name})
    url = f"{GLEIF_SEARCH_URL}?{query}"
    fetch = fetcher or _default_fetcher
    return parse_lei_records(fetch(url))
