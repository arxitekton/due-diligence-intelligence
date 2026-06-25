"""GDELT DOC 2.0 adverse-media search connector (open, no auth).

Pure JSON parsing core + injectable fetcher. GDELT grants unlimited reuse and
redistribution with citation. source_class: adverse_media_event (Tier-3 signal
— never cite as authoritative for financial facts; record retrieved_at).
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any, cast
from urllib.parse import urlencode

from cdd.extract import ExtractorUnavailable

GDELT_DOC_URL = "https://api.gdeltproject.org/api/v2/doc/doc"


def parse_articles(data: bytes) -> list[dict[str, Any]]:
    """Parse a GDELT DOC artlist JSON response into article dicts.

    Returns [] for empty/blank bodies (GDELT returns an empty body for
    zero-result queries). GDELT also throttles to ~1 request / 5s and answers
    over-limit or malformed-query requests with a PLAIN-TEXT body (HTTP 429 or
    200), not JSON — those are surfaced as ``ExtractorUnavailable`` so the caller
    sees a real rate-limit/error signal instead of an opaque JSON decode failure
    (and never mistakes throttling for "no adverse media found").
    """
    text = data.decode("utf-8").strip()
    if not text:
        return []
    try:
        raw: Any = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ExtractorUnavailable(
            "GDELT returned a non-JSON body (likely rate-limited — max ~1 req/5s — "
            f"or a query error): {text[:160]}"
        ) from exc
    payload: dict[str, Any] = cast(dict[str, Any], raw) if isinstance(raw, dict) else {}
    articles: list[dict[str, Any]] = []
    for a in payload.get("articles", []):
        if not isinstance(a, dict):
            continue
        a_d: dict[str, Any] = cast(dict[str, Any], a)
        articles.append(
            {
                "url": a_d.get("url", ""),
                "title": a_d.get("title", ""),
                "seendate": a_d.get("seendate", ""),
                "domain": a_d.get("domain", ""),
                "language": a_d.get("language", ""),
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
