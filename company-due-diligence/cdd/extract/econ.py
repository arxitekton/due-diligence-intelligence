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
OECD_BASE_URL = "https://sdmx.oecd.org/public/rest/data"


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


# ---------------------------------------------------------------------------
# OECD — SDMX-JSON (keyless, CC BY 4.0 for content from 2024-07-01)
# ---------------------------------------------------------------------------


def parse_oecd(data: bytes) -> list[dict[str, Any]]:
    """Decode an OECD SDMX-JSON (``dimensionAtObservation=AllDimensions``) response.

    Observations are keyed by colon-separated dimension POSITIONS (e.g.
    ``"8:0:4:0:1:0:0:0:0:0"``); each position indexes into the matching
    ``structures[0].dimensions.observation[i].values`` list to recover the code.
    The observation array's first element is the numeric value. REF_AREA /
    MEASURE / TIME_PERIOD map to the normalized area / series / period fields.
    Enforce OECD's 60-downloads/hr limit at the call site; attribute (CC BY 4.0).
    """
    raw: Any = json.loads(data.decode("utf-8"))
    payload: dict[str, Any] = cast("dict[str, Any]", raw) if isinstance(raw, dict) else {}
    data_obj = payload.get("data")
    data_obj = cast("dict[str, Any]", data_obj) if isinstance(data_obj, dict) else {}
    structures_raw = data_obj.get("structures")
    structures: list[Any] = (
        cast("list[Any]", structures_raw) if isinstance(structures_raw, list) else []
    )
    datasets_raw = data_obj.get("dataSets")
    datasets: list[Any] = (
        cast("list[Any]", datasets_raw) if isinstance(datasets_raw, list) else []
    )
    if not structures or not datasets:
        return []
    s0 = cast("dict[str, Any]", structures[0]) if isinstance(structures[0], dict) else {}
    ds0 = cast("dict[str, Any]", datasets[0]) if isinstance(datasets[0], dict) else {}

    dims_obj = s0.get("dimensions")
    dims_obj = cast("dict[str, Any]", dims_obj) if isinstance(dims_obj, dict) else {}
    obsdims_raw = dims_obj.get("observation")
    obsdims: list[Any] = (
        cast("list[Any]", obsdims_raw) if isinstance(obsdims_raw, list) else []
    )
    # Per-dimension ordered value codes (position → code).
    dim_codes: list[tuple[str, list[str]]] = []
    for dim in obsdims:
        dim_d = cast("dict[str, Any]", dim) if isinstance(dim, dict) else {}
        vals_raw = dim_d.get("values")
        vals: list[Any] = cast("list[Any]", vals_raw) if isinstance(vals_raw, list) else []
        codes = [
            str(cast("dict[str, Any]", v).get("id", "")) if isinstance(v, dict) else ""
            for v in vals
        ]
        dim_codes.append((str(dim_d.get("id", "")), codes))

    observations = ds0.get("observations")
    observations = cast("dict[str, Any]", observations) if isinstance(observations, dict) else {}
    label = str(s0.get("name", ""))
    obs: list[dict[str, Any]] = []
    for key, arr in observations.items():
        positions = key.split(":")
        coords: dict[str, str] = {}
        for i, (dim_id, codes) in enumerate(dim_codes):
            if i >= len(positions):
                break
            try:
                pos = int(positions[i])
            except (TypeError, ValueError):
                continue
            coords[dim_id] = codes[pos] if 0 <= pos < len(codes) else ""
        value = cast("list[Any]", arr)[0] if isinstance(arr, list) and arr else None
        obs.append(
            {
                "source": "OECD",
                "series": coords.get("MEASURE", ""),
                "area": coords.get("REF_AREA"),
                "period": coords.get("TIME_PERIOD"),
                "value": _to_float(value),
                "label": label,
                "dims": coords,
            }
        )
    return obs


def fetch_oecd(
    dataflow: str,
    key: str = "all",
    *,
    params: dict[str, Any] | None = None,
    fetcher: Callable[[str], bytes] | None = None,
) -> list[dict[str, Any]]:
    """Fetch an OECD SDMX-JSON dataflow and decode it.

    ``dataflow`` is the full SDMX ref, e.g.
    ``"OECD.SDD.STES,DSD_STES@DF_CLI,4.1"`` (composite leading indicators).
    ``key`` filters dimensions positionally (``"all"`` = everything — constrain
    large flows, e.g. ``params={"lastNObservations": 1}`` or a ref-area key).
    """
    query: dict[str, Any] = {"format": "jsondata", "dimensionAtObservation": "AllDimensions"}
    query.update(params or {})
    url = f"{OECD_BASE_URL}/{dataflow}/{key}?{urlencode(query, doseq=True)}"
    fetch = fetcher or _default_fetcher
    return parse_oecd(fetch(url))
