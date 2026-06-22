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
    "EU-CONSOLIDATED": {"retention_policy": "per_license", "license": "EC reuse (Decision 2011/833/EU)"},
    "UK-FCDO": {"retention_policy": "indefinite", "license": "OGL v3.0"},
    "BIS-CSL": {"retention_policy": "per_license", "license": "US-gov public domain / ITA Open Data"},
    "UN-CONSOLIDATED": {"retention_policy": "session_only", "license": "UN Terms of Use (no redistribution)"},
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
        program = padded[3].strip()
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
    payload = json.loads(data.decode("utf-8"))
    results = payload.get("results", []) if isinstance(payload, dict) else []
    entries: list[dict[str, Any]] = []
    for r in results:
        alt = r.get("alt_names") or []
        programs = r.get("programs") or []
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

    Rows sharing ``Entity_LogicalId`` form one designation; the first
    ``NameAlias_WholeName`` is the primary name, the rest are aliases.
    """
    text = data.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text), delimiter=";")
    grouped: dict[str, dict[str, Any]] = {}
    for row in reader:
        lid = (row.get("Entity_LogicalId") or "").strip()
        whole = (row.get("NameAlias_WholeName") or "").strip()
        if not lid or not whole:
            continue
        entry = grouped.get(lid)
        if entry is None:
            grouped[lid] = {
                "list": "EU-CONSOLIDATED",
                "entry_id": lid,
                "name": whole,
                "type": (row.get("Entity_SubjectType") or "").strip(),
                "program": (row.get("Entity_Regulation_Programme") or "").strip(),
                "remarks": None,
                "aliases": [],
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
    reader = csv.DictReader(io.StringIO(text))
    grouped: dict[str, dict[str, Any]] = {}
    for row in reader:
        uid = (row.get("Unique ID") or row.get("OFSI Group ID") or "").strip()
        if not uid:
            continue
        whole = _join_name_parts(row, _UK_NAME_COLS)
        alias_type = (row.get("Alias Type") or "").strip().casefold()
        entry = grouped.get(uid)
        if entry is None:
            entry = {
                "list": "UK-FCDO",
                "entry_id": uid,
                "name": "",
                "type": (row.get("Individual/Entity/Ship") or "").strip(),
                "program": (row.get("Regime") or "").strip(),
                "remarks": None,
                "aliases": [],
            }
            grouped[uid] = entry
        if alias_type == "primary name" and not entry["name"]:
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


def fetch_and_screen(
    query: str,
    *,
    list_id: str = "OFAC-SDN",
    fetcher: Callable[[str], bytes] | None = None,
) -> list[dict[str, Any]]:
    """Fetch a sanctions list, parse it, and screen the query name.

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
        NotImplementedError: ``list_id`` is valid but has no parser yet.
        ExtractorUnavailable: httpx is not installed and no ``fetcher`` was
            injected.
    """
    if list_id not in OFFICIAL_LISTS:
        raise ValueError(
            f"Unknown sanctions list {list_id!r}. "
            f"Available: {sorted(OFFICIAL_LISTS)}"
        )

    if list_id != "OFAC-SDN":
        raise NotImplementedError(
            f"Parsing for {list_id!r} is not yet implemented. "
            "Only OFAC-SDN parsing ships in this release."
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
    entries = parse_sdn_csv(raw)
    return screen_name(query, entries)
