"""UK Companies House search/profile connector (OGL v3.0, free API key).

Pure JSON parsing core + injectable fetcher. Auth is HTTP Basic with the API
key as the username and an empty password; key from the ``api_key`` arg or the
CDD_COMPANIES_HOUSE_KEY env var. License: OGL v3.0 — redistribute with
attribution; mind UK GDPR on officer/PSC personal data. source_class:
company_registry.
"""

from __future__ import annotations

import base64
import json
import os
from collections.abc import Callable
from typing import Any
from urllib.parse import urlencode

from cdd.extract import ExtractorUnavailable

CH_SEARCH_URL = "https://api.company-information.service.gov.uk/search/companies"

Fetcher = Callable[[str, dict[str, str]], bytes]


def parse_company_search(data: bytes) -> list[dict[str, Any]]:
    """Parse a Companies House company-search JSON response."""
    payload: Any = json.loads(data.decode("utf-8"))
    rows: list[dict[str, Any]] = []
    for item in payload.get("items", []):
        rows.append(
            {
                "company_number": item.get("company_number", ""),
                "title": item.get("title", ""),
                "status": item.get("company_status", ""),
                "address": item.get("address_snippet", ""),
            }
        )
    return rows


def _basic_auth_header(api_key: str) -> str:
    token = base64.b64encode(f"{api_key}:".encode()).decode()
    return f"Basic {token}"


def _default_fetcher(url: str, headers: dict[str, str]) -> bytes:
    import httpx  # type: ignore[import-untyped]

    from cdd.extract.fetch import get

    client = httpx.Client(follow_redirects=False, timeout=30.0, headers=headers)
    try:
        content, _ = get(url, client=client)
    finally:
        client.close()
    return content


def search_companies(
    query: str,
    *,
    api_key: str | None = None,
    fetcher: Fetcher | None = None,
) -> list[dict[str, Any]]:
    """Search Companies House for companies matching ``query``.

    Raises ExtractorUnavailable if no API key is available (arg or
    CDD_COMPANIES_HOUSE_KEY env).
    """
    key = api_key or os.environ.get("CDD_COMPANIES_HOUSE_KEY")
    if not key:
        raise ExtractorUnavailable(
            "Companies House API key required (api_key= or CDD_COMPANIES_HOUSE_KEY)"
        )
    url = f"{CH_SEARCH_URL}?{urlencode({'q': query})}"
    headers = {"Authorization": _basic_auth_header(key)}
    fetch = fetcher or _default_fetcher
    return parse_company_search(fetch(url, headers))
