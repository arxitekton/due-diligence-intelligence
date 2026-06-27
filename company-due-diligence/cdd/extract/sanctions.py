"""Sanctions-screening helper using official public lists (OFAC SDN, EU, UK).

Pure core (name normalisation, CSV parsing, name matching) has no optional deps
and is fully testable offline. The network path is injectable and guards via the
SSRF-hardened ``cdd.extract.fetch.get`` when httpx is available.

Absence of httpx only prevents the *live-fetch* path; all parsing and matching
functions work regardless.
"""

from __future__ import annotations

import csv
import io
import json
import re
import string
from collections.abc import Callable
from typing import Any, cast

from cdd.extract import ExtractorUnavailable

# ---------------------------------------------------------------------------
# Public list catalogue
# ---------------------------------------------------------------------------

OFFICIAL_LISTS: dict[str, str] = {
    "OFAC-SDN": "https://www.treasury.gov/ofac/downloads/sdn.csv",
    "EU-CONSOLIDATED": "https://webgate.ec.europa.eu/fsd/fsf/public/files/csvFullSanctionsList/content?token=dG9rZW4tMjAxNw",
    # UK OFSI consolidated list was withdrawn 2026-01-28; FCDO is the successor.
    "UK-FCDO": "https://sanctionslist.fcdo.gov.uk/docs/UK-Sanctions-List.csv",
    "BIS-CSL": "https://data.trade.gov/downloadable_consolidated_screening_list/v1/consolidated.json",
    "UN-CONSOLIDATED": "https://scsanctions.un.org/resources/xml/en/consolidated.xml",
}

# Retention policy per list maps to references/legal_and_tos.md. Redistributable
# lists are "indefinite"; UN terms forbid redistribution → "session_only"
# (ingest-to-screen, do not warehouse). See references/open_data_sources.md §2a.
LIST_METADATA: dict[str, dict[str, str]] = {
    "OFAC-SDN": {"retention_policy": "indefinite", "license": "US-gov public domain"},
    "EU-CONSOLIDATED": {
        "retention_policy": "per_license",
        "license": "EC reuse (Decision 2011/833/EU)",
    },
    "UK-FCDO": {"retention_policy": "indefinite", "license": "OGL v3.0"},
    "BIS-CSL": {
        "retention_policy": "per_license",
        "license": "US-gov public domain / ITA Open Data",
    },
    "UN-CONSOLIDATED": {
        "retention_policy": "session_only",
        "license": "UN Terms of Use (no redistribution)",
    },
}

# OFAC uses this sentinel to represent a null / not-applicable field.
_OFAC_NULL = "-0-"

# Column order for the OFAC SDN.CSV format (no header row in the real file).
_SDN_COLUMNS = [
    "ent_num",
    "SDN_Name",
    "SDN_Type",
    "Program",
    "Title",
    "Call_Sign",
    "Vess_type",
    "Tonnage",
    "GRT",
    "Vess_flag",
    "Vess_owner",
    "Remarks",
]

# ---------------------------------------------------------------------------
# Name normalisation
# ---------------------------------------------------------------------------

_PUNCT_RE = re.compile(r"[" + re.escape(string.punctuation) + r"]+")
_WS_RE = re.compile(r"\s+")


def _normalize_name(name: str) -> str:
    """Casefold, strip punctuation, collapse whitespace.

    Deterministic — used for all comparisons so callers never need to worry
    about case, punctuation variants, or extra spaces.
    """
    lowered = name.casefold()
    no_punct = _PUNCT_RE.sub(" ", lowered)
    return _WS_RE.sub(" ", no_punct).strip()


# ---------------------------------------------------------------------------
# OFAC SDN CSV parser
# ---------------------------------------------------------------------------


def _null_to_none(value: str) -> str | None:
    """Return None when the field equals the OFAC null token, else the value."""
    stripped = value.strip()
    return None if stripped == _OFAC_NULL else stripped


def _clean_program(value: str) -> str:
    """Normalise the OFAC SDN Program field to a clean ``"A; B; C"`` string.

    OFAC packs multiple programmes as ``[A] [B] [C]``, but the SDN.csv export
    drops the OUTER brackets, leaving the field as ``A] [B] [C`` (single
    programmes have no brackets at all, e.g. ``CUBA``). Split on the ``] [``
    separator and strip any residual brackets so the field never leaks ``]``/``[``.
    """
    parts = [p.strip().strip("[]").strip() for p in value.split("] [")]
    return "; ".join(p for p in parts if p)


# OFAC encodes alternate names inside the free-text Remarks field as
# "a.k.a. 'NAME'", "aka NAME", "f.k.a. ...", "n.k.a. ...", separated by ';'.
# Screening that ignores these misses entities listed only under a front/alias
# name — a false negative, the worst failure mode for sanctions. Extract them.
_AKA_RE = re.compile(
    r"\b(?:a\.k\.a\.|aka|f\.k\.a\.|fka|n\.k\.a\.|nka)\b[\s:]*['\"]?([^;'\"]+?)['\"]?\s*(?:;|$)",
    re.IGNORECASE,
)


def _extract_aliases(remarks: str | None) -> list[str]:
    """Pull a.k.a./f.k.a./n.k.a. alternate names out of an OFAC Remarks string."""
    if not remarks:
        return []
    return [m.strip() for m in _AKA_RE.findall(remarks) if m.strip()]


def parse_sdn_csv(data: bytes) -> list[dict[str, Any]]:
    """Parse OFAC SDN.CSV bytes into a list of entry dicts.

    The real SDN.CSV has no header row; columns follow the fixed order defined
    in ``_SDN_COLUMNS``. Fields equal to ``"-0-"`` are treated as null (None).

    Args:
        data: Raw bytes of the OFAC SDN.CSV file.

    Returns:
        List of dicts with keys: list, entry_id, name, type, program, remarks.
    """
    text = data.decode("latin-1")  # OFAC files use latin-1 encoding
    reader = csv.reader(io.StringIO(text))
    entries: list[dict[str, Any]] = []
    for row in reader:
        if not row:
            continue
        # Pad short rows so index access is safe.
        padded = row + [""] * (len(_SDN_COLUMNS) - len(row))
        ent_num = padded[0].strip()
        sdn_name = padded[1].strip()
        sdn_type = _null_to_none(padded[2]) or ""
        program = _clean_program(padded[3].strip())
        remarks_raw = padded[11].strip() if len(padded) > 11 else ""
        remarks = _null_to_none(remarks_raw)

        entries.append(
            {
                "list": "OFAC-SDN",
                "entry_id": ent_num,
                "name": sdn_name,
                "type": sdn_type,
                "program": program,
                "remarks": remarks,
                "aliases": _extract_aliases(remarks),
            }
        )
    return entries


# ---------------------------------------------------------------------------
# UN Security Council Consolidated List XML parser
# ---------------------------------------------------------------------------


def _un_text(node: Any, tag: str) -> str:
    child = node.find(tag)
    return child.text.strip() if child is not None and child.text else ""


def _un_aliases(node: Any, alias_tag: str) -> list[str]:
    out: list[str] = []
    for alias in node.findall(alias_tag):
        name = _un_text(alias, "ALIAS_NAME")
        if name:
            out.append(name)
    return out


def parse_un_xml(data: bytes) -> list[dict[str, Any]]:
    """Parse the UN Security Council Consolidated List XML.

    Uses defusedxml (untrusted network XML). INGEST-TO-SCREEN ONLY: UN terms
    forbid redistribution — callers must honour LIST_METADATA session_only
    retention and not warehouse the raw bytes.
    """
    try:
        from defusedxml.ElementTree import fromstring
    except ImportError as exc:
        raise ExtractorUnavailable("defusedxml not installed") from exc
    root = fromstring(data)
    entries: list[dict[str, Any]] = []
    for node in root.iter("INDIVIDUAL"):
        name = _WS_RE.sub(
            " ",
            " ".join(
                p for p in (_un_text(node, "FIRST_NAME"), _un_text(node, "SECOND_NAME"),
                            _un_text(node, "THIRD_NAME")) if p
            ),
        ).strip()
        entries.append({
            "list": "UN-CONSOLIDATED", "entry_id": _un_text(node, "DATAID"),
            "name": name, "type": "individual", "program": _un_text(node, "UN_LIST_TYPE"),
            "remarks": None, "aliases": _un_aliases(node, "INDIVIDUAL_ALIAS"),
        })
    for node in root.iter("ENTITY"):
        entries.append({
            "list": "UN-CONSOLIDATED", "entry_id": _un_text(node, "DATAID"),
            "name": _un_text(node, "FIRST_NAME"), "type": "entity",
            "program": _un_text(node, "UN_LIST_TYPE"),
            "remarks": None, "aliases": _un_aliases(node, "ENTITY_ALIAS"),
        })
    return entries


# ---------------------------------------------------------------------------
# BIS Consolidated Screening List JSON parser
# ---------------------------------------------------------------------------


def parse_bis_csl_json(data: bytes) -> list[dict[str, Any]]:
    """Parse the BIS Consolidated Screening List JSON into normalized entries."""
    raw: Any = json.loads(data.decode("utf-8"))
    payload: dict[str, Any] = cast(dict[str, Any], raw) if isinstance(raw, dict) else {}
    results: list[Any] = cast(list[Any], payload.get("results", []))
    entries: list[dict[str, Any]] = []
    for item in results:
        r: dict[str, Any] = cast(dict[str, Any], item) if isinstance(item, dict) else {}
        alt: list[Any] = cast(list[Any], r.get("alt_names") or [])
        programs: list[Any] = cast(list[Any], r.get("programs") or [])
        entries.append(
            {
                "list": "BIS-CSL",
                "entry_id": str(r.get("id", "")).strip(),
                "name": str(r.get("name", "")).strip(),
                "type": str(r.get("source", "")).strip(),
                "program": "; ".join(str(p) for p in programs),
                "remarks": None,
                "aliases": [str(a).strip() for a in alt if str(a).strip()],
            }
        )
    return entries


# ---------------------------------------------------------------------------
# EU Consolidated Financial Sanctions File CSV parser
# ---------------------------------------------------------------------------


def parse_eu_csv(data: bytes) -> list[dict[str, Any]]:
    """Parse the EU Consolidated Financial Sanctions File (semicolon CSV).

    The live "csvFullSanctionsList" export is a denormalized flat file: each row
    is one name-alias (``Naal_*``) block joined with the entity/address/birth/etc.
    blocks, so several columns (notably ``Entity_logical_id``) appear MORE THAN
    ONCE. ``csv.DictReader`` collapses duplicate headers to the last occurrence
    (often empty on a name row), so we index positionally by the FIRST occurrence
    instead. Rows sharing ``Entity_logical_id`` form one designation; the first
    non-empty ``Naal_wholename`` is the primary name, the rest are aliases. Rows
    with an empty name field (address/birth/ID sub-records) are skipped.
    """
    text = data.decode("utf-8-sig")
    rows = list(csv.reader(io.StringIO(text), delimiter=";"))
    if not rows:
        return []
    header = rows[0]

    def _idx(name: str) -> int | None:
        try:
            return header.index(name)  # first occurrence
        except ValueError:
            return None

    i_eid, i_name = _idx("Entity_logical_id"), _idx("Naal_wholename")
    i_sub, i_prog = _idx("Subject_type"), _idx("Programme")
    if i_eid is None or i_name is None:
        return []

    def _cell(row: list[str], i: int | None) -> str:
        return row[i].strip() if i is not None and i < len(row) else ""

    grouped: dict[str, dict[str, Any]] = {}
    for row in rows[1:]:
        eid, whole = _cell(row, i_eid), _cell(row, i_name)
        if not eid or not whole:
            continue
        entry = grouped.get(eid)
        if entry is None:
            grouped[eid] = {
                "list": "EU-CONSOLIDATED",
                "entry_id": eid,
                "name": whole,
                "type": _cell(row, i_sub),
                "program": _cell(row, i_prog),
                "remarks": None,
                "aliases": cast(list[Any], []),
            }
        else:
            entry["aliases"].append(whole)
    return list(grouped.values())


# ---------------------------------------------------------------------------
# UK FCDO sanctions list CSV parser
# ---------------------------------------------------------------------------

_UK_NAME_COLS = ["Name 1", "Name 2", "Name 3", "Name 4", "Name 5", "Name 6"]


def _join_name_parts(row: dict[str, str], cols: list[str]) -> str:
    """Join present, non-empty name-part columns into one whole name."""
    parts = [row.get(c, "").strip() for c in cols]
    return _WS_RE.sub(" ", " ".join(p for p in parts if p)).strip()


def parse_uk_fcdo_csv(data: bytes) -> list[dict[str, Any]]:
    """Parse the UK Sanctions List (FCDO) CSV into normalized entry dicts.

    Rows sharing a ``Unique ID`` form one designation; the ``Primary name`` row
    supplies ``name``, ``AKA``/alias rows and non-Latin names become ``aliases``.
    Successor to the OFSI consolidated list (withdrawn 2026-01-28).
    """
    text = data.decode("utf-8-sig")  # FCDO CSV is UTF-8, may carry a BOM
    # The live file opens with a "Report Date: <date>" preamble line ABOVE the
    # header, which would otherwise be read as the header. Skip any preamble up
    # to the real header row (the first line naming the "Unique ID" column).
    lines = text.splitlines()
    start = next((i for i, ln in enumerate(lines) if "Unique ID" in ln), 0)
    reader = csv.DictReader(io.StringIO("\n".join(lines[start:])))
    grouped: dict[str, dict[str, Any]] = {}
    for row in reader:
        uid = (row.get("Unique ID") or row.get("OFSI Group ID") or "").strip()
        if not uid:
            continue
        whole = _join_name_parts(row, _UK_NAME_COLS)
        # "Name type" distinguishes the primary name from AKAs/aliases.
        name_type = (row.get("Name type") or "").strip().casefold()
        entry = grouped.get(uid)
        if entry is None:
            new_entry: dict[str, Any] = {
                "list": "UK-FCDO",
                "entry_id": uid,
                "name": "",
                "type": (row.get("Type of entity") or row.get("Designation Type") or "").strip(),
                "program": (row.get("Regime Name") or "").strip(),
                "remarks": None,
                "aliases": cast(list[Any], []),
            }
            grouped[uid] = new_entry
            entry = new_entry
        if "primary" in name_type and not entry["name"]:
            entry["name"] = whole
        elif whole:
            entry["aliases"].append(whole)
    # If a group had no explicit primary row, promote the first alias to name.
    for entry in grouped.values():
        if not entry["name"] and entry["aliases"]:
            entry["name"] = entry["aliases"].pop(0)
    return list(grouped.values())


# ---------------------------------------------------------------------------
# Name matcher
# ---------------------------------------------------------------------------


def screen_name(
    query: str,
    entries: list[dict[str, Any]],
    *,
    aliases_field: str = "aliases",
) -> list[dict[str, Any]]:
    """Screen a query name against a list of sanction entries.

    Match strategy (no fuzzy/edit-distance — avoids false confidence):
    - ``exact``: normalized query equals normalized entry name (or alias).
    - ``partial``: every token in the normalized query appears as a token in the
      normalized entry name (or alias). Token membership is checked against the
      *token set* of each candidate, so "Bad Actor" matches "Bad Actor LLC"
      ({"bad","actor"} ⊆ {"bad","actor","llc"}) but not "Actor Bad Corp"
      (same tokens, different order — still matches, which is intentional for
      multi-word legal names where word order may vary).

    Exact matches are preferred: if a name matches exactly, it is returned with
    ``match_type="exact"`` and the partial check is skipped for that entry.

    Args:
        query: The name to screen.
        entries: Parsed sanction list rows (from ``parse_sdn_csv`` or similar).
        aliases_field: Key in each entry dict whose value is a list of alias
            strings. Defaults to ``"aliases"``; absent/empty → no alias check.

    Returns:
        Subset of entries that match, each augmented with ``match_type``.
        Order follows input order; deterministic.
    """
    norm_query = _normalize_name(query)
    query_tokens = set(norm_query.split())
    # Guardrail: a single-token query (e.g. "Acme", "Gazprom") would token-subset
    # match every entry containing that common token, flooding results with
    # unrelated designees. Single-token queries only produce EXACT matches; partial
    # (token-subset) matching requires >=2 query tokens so it can't fire on a lone
    # generic word. Avoids false-positive "candidates" resting solely on agent
    # discipline. (Exact single-token matches, e.g. a one-word legal name, still fire.)
    partial_eligible = len(query_tokens) >= 2

    results: list[dict[str, Any]] = []
    for entry in entries:
        candidates: list[str] = [entry.get("name", "")]
        raw_aliases: object = entry.get(aliases_field, [])
        if isinstance(raw_aliases, list):
            for alias in cast(list[str], raw_aliases):
                candidates.append(alias)

        match_type: str | None = None
        for candidate in candidates:
            norm_candidate = _normalize_name(candidate)
            if norm_candidate == norm_query:
                match_type = "exact"
                break
            candidate_tokens = set(norm_candidate.split())
            if partial_eligible and query_tokens.issubset(candidate_tokens):
                # Don't break — an exact match on a later alias should win.
                match_type = "partial"

        if match_type is not None:
            results.append({**entry, "match_type": match_type})

    return results


# ---------------------------------------------------------------------------
# Network fetch + screen (optional httpx dep)
# ---------------------------------------------------------------------------


def _default_fetcher(url: str) -> bytes:
    """Thin wrapper over cdd.extract.fetch.get that returns content bytes only.

    Inherits the SSRF guard from ``assert_public_url`` called inside ``get``.
    Raises ExtractorUnavailable when httpx is absent.
    """
    from cdd.extract.fetch import get  # local import — keeps module importable

    content, _ = get(url)
    return content


_PARSERS: dict[str, Callable[[bytes], list[dict[str, Any]]]] = {
    "OFAC-SDN": parse_sdn_csv,
    "UK-FCDO": parse_uk_fcdo_csv,
    "EU-CONSOLIDATED": parse_eu_csv,
    "BIS-CSL": parse_bis_csl_json,
    "UN-CONSOLIDATED": parse_un_xml,
}


def fetch_and_screen(
    query: str,
    *,
    list_id: str = "OFAC-SDN",
    fetcher: Callable[[str], bytes] | None = None,
) -> list[dict[str, Any]]:
    """Fetch a sanctions list, parse it, and screen the query name.

    All lists in ``_PARSERS`` are supported: OFAC-SDN, EU-CONSOLIDATED,
    UK-FCDO, BIS-CSL, and UN-CONSOLIDATED. Note that UN-CONSOLIDATED is
    session-only per LIST_METADATA — callers must not warehouse the raw bytes.

    Args:
        query: Name to screen.
        list_id: Key into ``OFFICIAL_LISTS`` (default ``"OFAC-SDN"``).
        fetcher: Injectable ``(url) -> bytes`` callable. Defaults to a wrapper
            around ``cdd.extract.fetch.get`` which requires httpx and enforces
            the SSRF guard. Supply a fake for testing to avoid network I/O.

    Returns:
        List of matching entry dicts (see ``screen_name``).

    Raises:
        ValueError: ``list_id`` is not in ``OFFICIAL_LISTS``.
        ExtractorUnavailable: httpx is not installed and no ``fetcher`` was
            injected.
    """
    if list_id not in OFFICIAL_LISTS:
        raise ValueError(
            f"Unknown sanctions list {list_id!r}. "
            f"Available: {sorted(OFFICIAL_LISTS)}"
        )

    url = OFFICIAL_LISTS[list_id]

    if fetcher is None:
        # Guard: if httpx is absent the default fetcher will raise
        # ExtractorUnavailable at call time, which is the intended behaviour.
        try:
            import importlib.util

            if importlib.util.find_spec("httpx") is None:
                raise ExtractorUnavailable(
                    "httpx not installed; install it or supply a fetcher= argument"
                )
        except ExtractorUnavailable:
            raise
        fetcher = _default_fetcher

    raw = fetcher(url)
    parser = _PARSERS[list_id]
    entries = parser(raw)
    return screen_name(query, entries)
