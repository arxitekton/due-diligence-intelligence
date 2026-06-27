"""Economic-indicator connectors (BLS, World Bank).

Pure JSON parse core (offline-testable from byte fixtures) + injectable fetcher
defaulting to the SSRF-guarded ``cdd.extract.fetch.get``. Both sources are
keyless. Licences: BLS = US-gov public domain (redistributable); World Bank =
CC BY 4.0 (redistribute with attribution; clear third-party-sourced indicators).
source_class: economic_indicator.

Every parser emits the same normalized observation shape::

    {"source", "series", "area", "period", "value", "label"}

``value`` is a float or None (a reported gap). ``area`` is None for series that
are not geo-keyed (most BLS series).
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any, cast

from cdd.extract import ExtractorUnavailable

BLS_SERIES_URL = "https://api.bls.gov/publicAPI/v1/timeseries/data/"
WORLD_BANK_URL = "https://api.worldbank.org/v2"


def _to_float(value: Any) -> float | None:
    """Coerce a string/number to float; return None for blank/unparseable."""
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# US Bureau of Labor Statistics (BLS) — public API v1 (keyless)
# ---------------------------------------------------------------------------


def parse_bls(data: bytes) -> list[dict[str, Any]]:
    """Parse a BLS timeseries response into normalized observations.

    Raises ExtractorUnavailable if BLS reports a non-success status (e.g. the
    keyless daily-query limit) so the caller sees the real cause, not an empty
    result mistaken for "no data".
    """
    raw: Any = json.loads(data.decode("utf-8"))
    payload: dict[str, Any] = cast("dict[str, Any]", raw) if isinstance(raw, dict) else {}
    status = str(payload.get("status", ""))
    if status and status != "REQUEST_SUCCEEDED":
        raise ExtractorUnavailable(
            f"BLS request not successful ({status}): {payload.get('message')}"
        )
    results_raw = payload.get("Results")
    results: dict[str, Any] = (
        cast("dict[str, Any]", results_raw) if isinstance(results_raw, dict) else {}
    )
    series_raw = results.get("series")
    series_list: list[Any] = (
        cast("list[Any]", series_raw) if isinstance(series_raw, list) else []
    )
    obs: list[dict[str, Any]] = []
    for s in series_list:
        if not isinstance(s, dict):
            continue
        s_d: dict[str, Any] = cast("dict[str, Any]", s)
        sid = str(s_d.get("seriesID", ""))
        data_raw = s_d.get("data")
        data_list: list[Any] = cast("list[Any]", data_raw) if isinstance(data_raw, list) else []
        for d in data_list:
            if not isinstance(d, dict):
                continue
            d_d: dict[str, Any] = cast("dict[str, Any]", d)
            obs.append(
                {
                    "source": "BLS",
                    "series": sid,
                    "area": None,
                    "period": f"{d_d.get('year', '')}-{d_d.get('period', '')}",
                    "value": _to_float(d_d.get("value")),
                    "label": d_d.get("periodName"),
                }
            )
    return obs


def _default_fetcher(url: str) -> bytes:
    from cdd.extract.fetch import get

    content, _ = get(url)
    return content


def fetch_bls_series(
    series_id: str, *, fetcher: Callable[[str], bytes] | None = None
) -> list[dict[str, Any]]:
    """Fetch one BLS series (e.g. ``CUUR0000SA0`` = CPI-U) and parse it."""
    url = f"{BLS_SERIES_URL}{series_id}"
    fetch = fetcher or _default_fetcher
    return parse_bls(fetch(url))


# ---------------------------------------------------------------------------
# World Bank Open Data / WDI (keyless, CC BY 4.0)
# ---------------------------------------------------------------------------


def parse_world_bank(data: bytes) -> list[dict[str, Any]]:
    """Parse a World Bank indicator response into normalized observations.

    The API returns ``[<metadata>, [<observation>...]]``; the observation list
    is the SECOND element. A bare metadata object (error/empty) yields [].
    """
    raw: Any = json.loads(data.decode("utf-8"))
    if not isinstance(raw, list):
        return []
    raw_list: list[Any] = cast("list[Any]", raw)
    if len(raw_list) < 2 or not isinstance(raw_list[1], list):
        return []
    rows = cast("list[Any]", raw_list[1])
    obs: list[dict[str, Any]] = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        r_d: dict[str, Any] = cast("dict[str, Any]", r)
        ind_raw = r_d.get("indicator")
        indicator: dict[str, Any] = (
            cast("dict[str, Any]", ind_raw) if isinstance(ind_raw, dict) else {}
        )
        ctry_raw = r_d.get("country")
        country: dict[str, Any] = (
            cast("dict[str, Any]", ctry_raw) if isinstance(ctry_raw, dict) else {}
        )
        obs.append(
            {
                "source": "WORLD_BANK",
                "series": indicator.get("id", ""),
                "area": country.get("id", ""),
                "period": str(r_d.get("date", "")),
                "value": _to_float(r_d.get("value")),
                "label": indicator.get("value", ""),
            }
        )
    return obs


def fetch_world_bank(
    country: str,
    indicator: str,
    *,
    per_page: int = 100,
    fetcher: Callable[[str], bytes] | None = None,
) -> list[dict[str, Any]]:
    """Fetch a World Bank indicator series for a country (ISO2/ISO3 or 'all').

    Example: ``fetch_world_bank("US", "NY.GDP.MKTP.CD")`` → US GDP (current US$).
    """
    url = (
        f"{WORLD_BANK_URL}/country/{country}/indicator/{indicator}"
        f"?format=json&per_page={per_page}"
    )
    fetch = fetcher or _default_fetcher
    return parse_world_bank(fetch(url))
