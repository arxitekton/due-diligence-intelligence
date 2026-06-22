"""GDELT DOC 2.0 adverse-media search connector (open, no auth).

Pure JSON parsing core + injectable fetcher. GDELT grants unlimited reuse and
redistribution with citation. source_class: adverse_media_event (Tier-3 signal
— never cite as authoritative for financial facts; record retrieved_at).
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any
from urllib.parse import urlencode

GDELT_DOC_URL = "https://api.gdeltproject.org/api/v2/doc/doc"


def parse_articles(data: bytes) -> list[dict[str, Any]]:
    """Parse a GDELT DOC artlist JSON response into article dicts.

    Returns [] for empty/blank bodies (GDELT returns an empty body for
    zero-result queries).
    """
    text = data.decode("utf-8").strip()
    if not text:
        return []
    payload: Any = json.loads(text)
    articles: list[dict[str, Any]] = []
    for a in payload.get("articles", []):
        articles.append(
            {
                "url": a.get("url", ""),
                "title": a.get("title", ""),
                "seendate": a.get("seendate", ""),
                "domain": a.get("domain", ""),
                "language": a.get("language", ""),
            }
        )
    return articles


def _default_fetcher(url: str) -> bytes:
    from cdd.extract.fetch import get

    content, _ = get(url)
    return content


def search_adverse_media(
    query: str,
    *,
    max_records: int = 50,
    fetcher: Callable[[str], bytes] | None = None,
) -> list[dict[str, Any]]:
    """Search GDELT for recent articles matching ``query`` (adverse-media signal)."""
    params = urlencode(
        {"query": query, "mode": "artlist", "format": "json", "maxrecords": max_records}
    )
    url = f"{GDELT_DOC_URL}?{params}"
    fetch = fetcher or _default_fetcher
    return parse_articles(fetch(url))
