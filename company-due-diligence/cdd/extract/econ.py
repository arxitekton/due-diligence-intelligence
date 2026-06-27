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
from urllib.parse import urlencode

from cdd.extract import ExtractorUnavailable

BLS_SERIES_URL = "https://api.bls.gov/publicAPI/v1/timeseries/data/"
WORLD_BANK_URL = "https://api.worldbank.org/v2"
EUROSTAT_BASE_URL = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data"


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


# ---------------------------------------------------------------------------
# Eurostat — JSON-stat 2.0 (keyless, EC reuse / CC BY-equivalent)
# ---------------------------------------------------------------------------


def parse_eurostat(data: bytes) -> list[dict[str, Any]]:
    """Decode a Eurostat JSON-stat 2.0 response into normalized observations.

    JSON-stat stores values as a flat ``{index: number}`` map. The flat index is
    decoded against the dimension order (``id``) and per-dimension category counts
    (``size``) using row-major strides (the LAST dimension varies fastest), then
    each coordinate is mapped back to its category code via
    ``dimension[dim].category.index`` (which is code→position, so we invert it).
    Only present values appear in ``value`` (gaps are simply absent).
    """
    raw: Any = json.loads(data.decode("utf-8"))
    payload: dict[str, Any] = cast("dict[str, Any]", raw) if isinstance(raw, dict) else {}
    value_raw = payload.get("value")
    value: dict[str, Any] = (
        cast("dict[str, Any]", value_raw) if isinstance(value_raw, dict) else {}
    )
    ids_raw = payload.get("id")
    ids: list[Any] = cast("list[Any]", ids_raw) if isinstance(ids_raw, list) else []
    size_raw = payload.get("size")
    size: list[Any] = cast("list[Any]", size_raw) if isinstance(size_raw, list) else []
    dims_raw = payload.get("dimension")
    dims: dict[str, Any] = (
        cast("dict[str, Any]", dims_raw) if isinstance(dims_raw, dict) else {}
    )
    if not value or len(ids) != len(size) or not size:
        return []
    label = str(payload.get("label", ""))
    sizes = [int(s) for s in size]

    # Invert each dimension's code→position index to position→code.
    pos_to_code: dict[str, dict[int, str]] = {}
    for dim in ids:
        dim_name = str(dim)
        dim_obj = dims.get(dim_name)
        dim_obj = cast("dict[str, Any]", dim_obj) if isinstance(dim_obj, dict) else {}
        cat = dim_obj.get("category")
        cat = cast("dict[str, Any]", cat) if isinstance(cat, dict) else {}
        idx = cat.get("index")
        idx = cast("dict[str, Any]", idx) if isinstance(idx, dict) else {}
        pos_to_code[dim_name] = {int(p): str(code) for code, p in idx.items()}

    # Row-major strides: stride[i] = product of sizes to the right of i.
    n = len(sizes)
    strides = [1] * n
    for i in range(n - 2, -1, -1):
        strides[i] = strides[i + 1] * sizes[i + 1]

    obs: list[dict[str, Any]] = []
    for k_str, v in value.items():
        try:
            flat = int(k_str)
        except (TypeError, ValueError):
            continue
        coords: dict[str, str] = {}
        for i, dim in enumerate(ids):
            dim_name = str(dim)
            pos = (flat // strides[i]) % sizes[i] if sizes[i] else 0
            coords[dim_name] = pos_to_code.get(dim_name, {}).get(pos, "")
        obs.append(
            {
                "source": "EUROSTAT",
                "series": coords.get("na_item") or "",
                "area": coords.get("geo"),
                "period": coords.get("time"),
                "value": _to_float(v),
                "label": label,
                "dims": coords,
            }
        )
    return obs


def fetch_eurostat(
    dataset: str,
    *,
    params: dict[str, Any] | None = None,
    fetcher: Callable[[str], bytes] | None = None,
) -> list[dict[str, Any]]:
    """Fetch a Eurostat dataset (e.g. ``nama_10_gdp``) and decode it.

    ``params`` are Eurostat dimension filters, e.g.
    ``{"na_item": "B1GQ", "unit": "CP_MEUR", "geo": ["DE", "FR"], "time": "2023"}``;
    list values (repeated dimensions like multiple geos) are expanded.
    """
    query: dict[str, Any] = dict(params or {})
    query.setdefault("format", "JSON")
    url = f"{EUROSTAT_BASE_URL}/{dataset}?{urlencode(query, doseq=True)}"
    fetch = fetcher or _default_fetcher
    return parse_eurostat(fetch(url))
