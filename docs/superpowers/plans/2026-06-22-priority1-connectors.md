# Priority-1 Connectors Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the Priority-1 open data sources from `company-due-diligence/references/open_data_sources.md` §5 into `cdd/extract/`: multi-list sanctions parsers (EU FSF, UK FCDO, BIS CSL, UN Consolidated), GLEIF LEI, UK Companies House, and GDELT adverse-media.

**Architecture:** Follow the established `cdd/extract/` pattern exactly — a **pure parse core** (stdlib only, fully offline-testable from byte fixtures) plus a thin network wrapper that takes an **injectable `fetcher`** defaulting to the SSRF-guarded `cdd.extract.fetch.get`. Sanctions work extends the existing `sanctions.py` (new parsers + a dispatcher in `fetch_and_screen`, reusing the existing `screen_name` matcher and normalized entry shape). The three non-sanctions sources get focused new modules. All heavy deps stay optional (`extract` extra); absence yields `ExtractorUnavailable`, never an import error.

**Tech Stack:** Python 3.12, stdlib `csv`/`json`/`io`, `defusedxml` (new, for safe UN XML parsing), `httpx` (existing, via `fetch.get`), pytest with injected fake fetchers.

**Normalized sanctions entry shape (unchanged, all parsers emit this):**
```python
{"list": str, "entry_id": str, "name": str, "type": str, "program": str,
 "remarks": str | None, "aliases": list[str]}
```

**Format-confirmation rule:** Live list/API schemas drift. Fixtures below reflect the documented formats as of 2026-06. Each connector task ends with a **live smoke-test acceptance step** (network, run manually) that confirms ≥1 known record parses; if a header/element name differs from the fixture, update the constant + fixture and re-run. Unit tests stay offline.

---

## File Structure

- **Modify** `cdd/extract/sanctions.py` — add `parse_eu_csv`, `parse_uk_fcdo_csv`, `parse_bis_csl_json`, `parse_un_xml`; add `LIST_METADATA`; update `OFFICIAL_LISTS` (retire dead OFSI URL → FCDO; add BIS, UN); replace the `NotImplementedError` branch in `fetch_and_screen` with a parser dispatch.
- **Create** `cdd/extract/gleif.py` — GLEIF LEI lookup (CC0).
- **Create** `cdd/extract/companies_house.py` — UK Companies House search/profile (OGL, free key via env).
- **Create** `cdd/extract/gdelt.py` — GDELT DOC 2.0 adverse-media search (open).
- **Modify** `cdd/extract/__init__.py` — extend `capabilities()` with new backends.
- **Modify** `pyproject.toml` — add `defusedxml>=0.7` to the `extract` extra.
- **Modify** `company-due-diligence/references/source_priority_rules.md` — add the 7 new `source_class` values.
- **Create** tests: `tests/test_extract_gleif.py`, `tests/test_extract_companies_house.py`, `tests/test_extract_gdelt.py`; extend `tests/test_extract_sanctions.py`.

---

## Task 1: Add `defusedxml` dep + extend `LIST_METADATA` / `OFFICIAL_LISTS`

**Files:**
- Modify: `pyproject.toml` (the `extract` extra)
- Modify: `cdd/extract/sanctions.py` (top-of-module constants)
- Test: `tests/test_extract_sanctions.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_extract_sanctions.py`:
```python
def test_official_lists_has_all_priority1_lists():
    from cdd.extract.sanctions import OFFICIAL_LISTS, LIST_METADATA
    for lid in ("OFAC-SDN", "EU-CONSOLIDATED", "UK-FCDO", "BIS-CSL", "UN-CONSOLIDATED"):
        assert lid in OFFICIAL_LISTS and OFFICIAL_LISTS[lid].startswith("https://")
        assert lid in LIST_METADATA
    # Dead OFSI list must be retired (withdrawn 2026-01-28).
    assert "UK-OFSI" not in OFFICIAL_LISTS
    # UN is ingest-to-screen only.
    assert LIST_METADATA["UN-CONSOLIDATED"]["retention_policy"] == "session_only"
    assert LIST_METADATA["OFAC-SDN"]["retention_policy"] == "indefinite"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd company-due-diligence && pytest tests/test_extract_sanctions.py::test_official_lists_has_all_priority1_lists -v`
Expected: FAIL — `ImportError: cannot import name 'LIST_METADATA'`.

- [ ] **Step 3: Write minimal implementation**

In `cdd/extract/sanctions.py`, replace the `OFFICIAL_LISTS` dict (lines ~26-30) with:
```python
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
```

In `pyproject.toml`, add to the `extract` extra list:
```toml
  "defusedxml>=0.7",
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd company-due-diligence && pytest tests/test_extract_sanctions.py::test_official_lists_has_all_priority1_lists -v`
Expected: PASS. Also run the existing `test_official_lists_has_core_lists` — still PASS.

- [ ] **Step 5: Commit**

```bash
git add company-due-diligence/pyproject.toml company-due-diligence/cdd/extract/sanctions.py company-due-diligence/tests/test_extract_sanctions.py
git commit -m "feat(extract): register EU/UK-FCDO/BIS/UN sanctions lists + retention metadata"
```

---

## Task 2: UK FCDO CSV parser

**Files:**
- Modify: `cdd/extract/sanctions.py`
- Test: `tests/test_extract_sanctions.py`

UK Sanctions List CSV (FCDO) is header-based; each row is one name. Name parts are in `Name 1`…`Name 6`; rows for the same designation share a `Group ID`/`Unique ID`; an alias-type column marks `Primary name` vs `AKA`/`Alias`. The parser groups rows by id, takes the primary name as `name`, collects AKA rows + non-Latin names into `aliases`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_extract_sanctions.py`:
```python
_UK_FCDO_CSV = (
    "Unique ID,OFSI Group ID,Name 1,Name 2,Name 3,Name 4,Name 5,Name 6,"
    "Alias Type,Regime,Individual/Entity/Ship\r\n"
    "UKS0001,GRP1,Bad,,,Actor,LLC,,Primary name,Russia,Entity\r\n"
    "UKS0001,GRP1,Bad,,,Actor,Limited,,AKA,Russia,Entity\r\n"
    "UKS0002,GRP2,Jane,,,Doe,,,Primary name,Russia,Individual\r\n"
).encode("utf-8")

def test_parse_uk_fcdo_csv_groups_aliases():
    from cdd.extract.sanctions import parse_uk_fcdo_csv
    entries = parse_uk_fcdo_csv(_UK_FCDO_CSV)
    assert len(entries) == 2  # grouped by Unique ID
    e = next(x for x in entries if x["entry_id"] == "UKS0001")
    assert e["list"] == "UK-FCDO"
    assert e["name"] == "Bad Actor LLC"
    assert "Bad Actor Limited" in e["aliases"]
    assert e["type"] == "Entity"
    assert e["program"] == "Russia"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd company-due-diligence && pytest tests/test_extract_sanctions.py::test_parse_uk_fcdo_csv_groups_aliases -v`
Expected: FAIL — `ImportError: cannot import name 'parse_uk_fcdo_csv'`.

- [ ] **Step 3: Write minimal implementation**

Add to `cdd/extract/sanctions.py` (after `parse_sdn_csv`):
```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd company-due-diligence && pytest tests/test_extract_sanctions.py::test_parse_uk_fcdo_csv_groups_aliases -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add company-due-diligence/cdd/extract/sanctions.py company-due-diligence/tests/test_extract_sanctions.py
git commit -m "feat(extract): UK FCDO sanctions-list CSV parser"
```

---

## Task 3: EU FSF CSV parser

**Files:**
- Modify: `cdd/extract/sanctions.py`
- Test: `tests/test_extract_sanctions.py`

The EU Consolidated Financial Sanctions File CSV is **semicolon-delimited** with a header. Rows are name-aliases keyed by `Entity_LogicalId`; whole name is in `NameAlias_WholeName`; `Entity_SubjectType` is the type; `Entity_Regulation_Programme` the programme. Group by logical id; first row → name, rest → aliases.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_extract_sanctions.py`:
```python
_EU_CSV = (
    "Entity_LogicalId;NameAlias_WholeName;Entity_SubjectType;Entity_Regulation_Programme\r\n"
    "13;Bad Actor LLC;enterprise;RUS\r\n"
    "13;Bad Actor OOO;enterprise;RUS\r\n"
    "14;Jane Doe;person;RUS\r\n"
).encode("utf-8")

def test_parse_eu_csv_groups_by_logical_id():
    from cdd.extract.sanctions import parse_eu_csv
    entries = parse_eu_csv(_EU_CSV)
    assert len(entries) == 2
    e = next(x for x in entries if x["entry_id"] == "13")
    assert e["list"] == "EU-CONSOLIDATED"
    assert e["name"] == "Bad Actor LLC"
    assert "Bad Actor OOO" in e["aliases"]
    assert e["type"] == "enterprise"
    assert e["program"] == "RUS"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd company-due-diligence && pytest tests/test_extract_sanctions.py::test_parse_eu_csv_groups_by_logical_id -v`
Expected: FAIL — `ImportError: cannot import name 'parse_eu_csv'`.

- [ ] **Step 3: Write minimal implementation**

Add to `cdd/extract/sanctions.py`:
```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd company-due-diligence && pytest tests/test_extract_sanctions.py::test_parse_eu_csv_groups_by_logical_id -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add company-due-diligence/cdd/extract/sanctions.py company-due-diligence/tests/test_extract_sanctions.py
git commit -m "feat(extract): EU consolidated sanctions CSV parser"
```

---

## Task 4: BIS CSL JSON parser

**Files:**
- Modify: `cdd/extract/sanctions.py`
- Test: `tests/test_extract_sanctions.py`

The BIS Consolidated Screening List REST returns JSON `{"results": [ {...} ]}`. Each result has `id`, `name`, `alt_names` (list), `source` (e.g. "Entity List (EL) - Bureau of Industry and Security"), `programs` (list). Map `source`→`type`, `programs` joined→`program`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_extract_sanctions.py`:
```python
_BIS_JSON = (
    b'{"results":[{"id":"abc-1","name":"Bad Actor LLC",'
    b'"alt_names":["Bad Actor OOO"],"source":"Entity List (EL)",'
    b'"programs":["EAR"]},'
    b'{"id":"abc-2","name":"Jane Doe","alt_names":[],'
    b'"source":"Denied Persons List (DPL)","programs":["EAR"]}]}'
)

def test_parse_bis_csl_json():
    from cdd.extract.sanctions import parse_bis_csl_json
    entries = parse_bis_csl_json(_BIS_JSON)
    assert len(entries) == 2
    e = entries[0]
    assert e["list"] == "BIS-CSL"
    assert e["entry_id"] == "abc-1"
    assert e["name"] == "Bad Actor LLC"
    assert e["aliases"] == ["Bad Actor OOO"]
    assert e["type"] == "Entity List (EL)"
    assert e["program"] == "EAR"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd company-due-diligence && pytest tests/test_extract_sanctions.py::test_parse_bis_csl_json -v`
Expected: FAIL — `ImportError: cannot import name 'parse_bis_csl_json'`.

- [ ] **Step 3: Write minimal implementation**

Add `import json` near the top imports of `cdd/extract/sanctions.py` (alongside `csv`, `io`). Then add:
```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd company-due-diligence && pytest tests/test_extract_sanctions.py::test_parse_bis_csl_json -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add company-due-diligence/cdd/extract/sanctions.py company-due-diligence/tests/test_extract_sanctions.py
git commit -m "feat(extract): BIS Consolidated Screening List JSON parser"
```

---

## Task 5: UN Consolidated XML parser (defused)

**Files:**
- Modify: `cdd/extract/sanctions.py`
- Test: `tests/test_extract_sanctions.py`

UN XML has `<INDIVIDUALS><INDIVIDUAL>` and `<ENTITIES><ENTITY>` nodes. Individual name parts are `FIRST_NAME`/`SECOND_NAME`/`THIRD_NAME`; entities use `FIRST_NAME` for the whole name. `DATAID` is the id; `UN_LIST_TYPE` the programme; aliases in `INDIVIDUAL_ALIAS/ALIAS_NAME` or `ENTITY_ALIAS/ALIAS_NAME`. Parse with `defusedxml` (untrusted network XML → never use stdlib ElementTree directly).

- [ ] **Step 1: Write the failing test**

Add to `tests/test_extract_sanctions.py`:
```python
_UN_XML = (
    b'<?xml version="1.0" encoding="UTF-8"?>'
    b"<CONSOLIDATED_LIST><INDIVIDUALS>"
    b"<INDIVIDUAL><DATAID>1</DATAID><FIRST_NAME>Jane</FIRST_NAME>"
    b"<SECOND_NAME>Doe</SECOND_NAME><UN_LIST_TYPE>Al-Qaida</UN_LIST_TYPE>"
    b"<INDIVIDUAL_ALIAS><ALIAS_NAME>J. Doe</ALIAS_NAME></INDIVIDUAL_ALIAS>"
    b"</INDIVIDUAL></INDIVIDUALS>"
    b"<ENTITIES><ENTITY><DATAID>2</DATAID>"
    b"<FIRST_NAME>Bad Actor LLC</FIRST_NAME><UN_LIST_TYPE>Al-Qaida</UN_LIST_TYPE>"
    b"</ENTITY></ENTITIES></CONSOLIDATED_LIST>"
)

def test_parse_un_xml_individuals_and_entities():
    from cdd.extract.sanctions import parse_un_xml
    entries = parse_un_xml(_UN_XML)
    ind = next(e for e in entries if e["entry_id"] == "1")
    assert ind["list"] == "UN-CONSOLIDATED"
    assert ind["name"] == "Jane Doe"
    assert "J. Doe" in ind["aliases"]
    assert ind["type"] == "individual"
    assert ind["program"] == "Al-Qaida"
    ent = next(e for e in entries if e["entry_id"] == "2")
    assert ent["name"] == "Bad Actor LLC"
    assert ent["type"] == "entity"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd company-due-diligence && pytest tests/test_extract_sanctions.py::test_parse_un_xml_individuals_and_entities -v`
Expected: FAIL — `ImportError: cannot import name 'parse_un_xml'`.

- [ ] **Step 3: Write minimal implementation**

Add to `cdd/extract/sanctions.py`:
```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd company-due-diligence && pip install defusedxml >/dev/null 2>&1; pytest tests/test_extract_sanctions.py::test_parse_un_xml_individuals_and_entities -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add company-due-diligence/cdd/extract/sanctions.py company-due-diligence/tests/test_extract_sanctions.py
git commit -m "feat(extract): UN consolidated list XML parser (defused, session-only)"
```

---

## Task 6: Dispatch `fetch_and_screen` across all lists

**Files:**
- Modify: `cdd/extract/sanctions.py:226-280` (the `fetch_and_screen` body)
- Test: `tests/test_extract_sanctions.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_extract_sanctions.py`:
```python
def test_fetch_and_screen_dispatches_uk_fcdo():
    from cdd.extract.sanctions import fetch_and_screen, OFFICIAL_LISTS
    captured = {}
    def fake(url: str) -> bytes:
        captured["url"] = url
        return _UK_FCDO_CSV
    hits = fetch_and_screen("Bad Actor LLC", list_id="UK-FCDO", fetcher=fake)
    assert captured["url"] == OFFICIAL_LISTS["UK-FCDO"]
    assert len(hits) == 1 and hits[0]["list"] == "UK-FCDO"

def test_fetch_and_screen_dispatches_bis_and_un():
    from cdd.extract.sanctions import fetch_and_screen
    bis = fetch_and_screen("Bad Actor LLC", list_id="BIS-CSL", fetcher=lambda u: _BIS_JSON)
    assert bis and bis[0]["list"] == "BIS-CSL"
    un = fetch_and_screen("Bad Actor LLC", list_id="UN-CONSOLIDATED", fetcher=lambda u: _UN_XML)
    assert un and un[0]["list"] == "UN-CONSOLIDATED"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd company-due-diligence && pytest tests/test_extract_sanctions.py::test_fetch_and_screen_dispatches_uk_fcdo tests/test_extract_sanctions.py::test_fetch_and_screen_dispatches_bis_and_un -v`
Expected: FAIL — `NotImplementedError` for non-OFAC lists.

- [ ] **Step 3: Write minimal implementation**

In `cdd/extract/sanctions.py`, add a parser registry above `fetch_and_screen`:
```python
_PARSERS: dict[str, Callable[[bytes], list[dict[str, Any]]]] = {
    "OFAC-SDN": parse_sdn_csv,
    "UK-FCDO": parse_uk_fcdo_csv,
    "EU-CONSOLIDATED": parse_eu_csv,
    "BIS-CSL": parse_bis_csl_json,
    "UN-CONSOLIDATED": parse_un_xml,
}
```
Then in `fetch_and_screen`, **delete** the block:
```python
    if list_id != "OFAC-SDN":
        raise NotImplementedError(
            f"Parsing for {list_id!r} is not yet implemented. "
            "Only OFAC-SDN parsing ships in this release."
        )
```
and replace the tail `entries = parse_sdn_csv(raw)` with:
```python
    raw = fetcher(url)
    parser = _PARSERS[list_id]
    entries = parser(raw)
    return screen_name(query, entries)
```
Update the `fetch_and_screen` docstring: drop the "Only OFAC-SDN" note and the `NotImplementedError` line; note all lists in `_PARSERS` are supported and that `UN-CONSOLIDATED` is session-only.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd company-due-diligence && pytest tests/test_extract_sanctions.py -v`
Expected: ALL PASS (including the original OFAC dispatch test).

- [ ] **Step 5: Commit**

```bash
git add company-due-diligence/cdd/extract/sanctions.py company-due-diligence/tests/test_extract_sanctions.py
git commit -m "feat(extract): dispatch fetch_and_screen across OFAC/EU/UK/BIS/UN"
```

- [ ] **Step 6 (acceptance, manual/network): live smoke test**

```bash
cd company-due-diligence && export CDD_HTTP_USER_AGENT="DueDiligence ops@example.com"
python -c "from cdd.extract.sanctions import fetch_and_screen as f; print('UK', len(f('Putin', list_id='UK-FCDO'))); print('EU', len(f('Putin', list_id='EU-CONSOLIDATED'))); print('BIS', len(f('Huawei', list_id='BIS-CSL'))); print('UN', len(f('Taliban', list_id='UN-CONSOLIDATED')))"
```
Expected: each prints a non-zero count. If a parser returns 0 against live data, the live header/element names differ from the fixture — inspect a raw sample, update the column/tag constants + fixture, and re-run Tasks 2-5's unit tests.

---

## Task 7: GLEIF LEI connector

**Files:**
- Create: `cdd/extract/gleif.py`
- Test: `tests/test_extract_gleif.py`

GLEIF REST `https://api.gleif.org/api/v1/lei-records?filter[entity.legalName]=NAME` returns JSON-API `{"data":[{"attributes":{"lei":..,"entity":{"legalName":{"name":..},"legalAddress":{"country":..},"status":..}}}]}`. CC0, no auth.

- [ ] **Step 1: Write the failing test**

Create `tests/test_extract_gleif.py`:
```python
from cdd.extract.gleif import parse_lei_records, search_by_name, GLEIF_SEARCH_URL

_GLEIF_JSON = (
    b'{"data":[{"attributes":{"lei":"5493001KJTIIGC8Y1R12",'
    b'"entity":{"legalName":{"name":"Bad Actor LLC"},'
    b'"legalAddress":{"country":"US"},"status":"ACTIVE"}}}]}'
)

def test_parse_lei_records():
    recs = parse_lei_records(_GLEIF_JSON)
    assert len(recs) == 1
    r = recs[0]
    assert r["lei"] == "5493001KJTIIGC8Y1R12"
    assert r["legal_name"] == "Bad Actor LLC"
    assert r["country"] == "US"
    assert r["status"] == "ACTIVE"

def test_search_by_name_uses_injected_fetcher():
    captured = {}
    def fake(url: str) -> bytes:
        captured["url"] = url
        return _GLEIF_JSON
    recs = search_by_name("Bad Actor LLC", fetcher=fake)
    assert recs[0]["lei"] == "5493001KJTIIGC8Y1R12"
    assert captured["url"].startswith(GLEIF_SEARCH_URL)
    assert "Bad+Actor+LLC" in captured["url"] or "Bad%20Actor%20LLC" in captured["url"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd company-due-diligence && pytest tests/test_extract_gleif.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'cdd.extract.gleif'`.

- [ ] **Step 3: Write minimal implementation**

Create `cdd/extract/gleif.py`:
```python
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
    payload = json.loads(data.decode("utf-8"))
    records: list[dict[str, Any]] = []
    for item in payload.get("data", []):
        attrs = item.get("attributes", {})
        entity = attrs.get("entity", {})
        legal_name = (entity.get("legalName") or {}).get("name", "")
        country = (entity.get("legalAddress") or {}).get("country", "")
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd company-due-diligence && pytest tests/test_extract_gleif.py -v`
Expected: PASS. (urlencode produces `filter%5Bentity.legalName%5D=Bad+Actor+LLC` → the `Bad+Actor+LLC` assertion holds.)

- [ ] **Step 5: Commit**

```bash
git add company-due-diligence/cdd/extract/gleif.py company-due-diligence/tests/test_extract_gleif.py
git commit -m "feat(extract): GLEIF LEI lookup connector (CC0)"
```

---

## Task 8: UK Companies House connector

**Files:**
- Create: `cdd/extract/companies_house.py`
- Test: `tests/test_extract_companies_house.py`

Companies House Search API `https://api.company-information.service.gov.uk/search/companies?q=NAME` returns `{"items":[{"company_number":..,"title":..,"company_status":..,"address_snippet":..}]}`. Auth = HTTP Basic with the API key as username (empty password). Key from `CDD_COMPANIES_HOUSE_KEY` env. OGL, redistributable.

- [ ] **Step 1: Write the failing test**

Create `tests/test_extract_companies_house.py`:
```python
import base64
import pytest
from cdd.extract.companies_house import (
    parse_company_search, search_companies, _basic_auth_header, CH_SEARCH_URL,
)
from cdd.extract import ExtractorUnavailable

_CH_JSON = (
    b'{"items":[{"company_number":"01234567","title":"BAD ACTOR LLP",'
    b'"company_status":"active","address_snippet":"1 High St, London"}]}'
)

def test_parse_company_search():
    rows = parse_company_search(_CH_JSON)
    assert rows == [{
        "company_number": "01234567", "title": "BAD ACTOR LLP",
        "status": "active", "address": "1 High St, London",
    }]

def test_basic_auth_header_encodes_key_as_username():
    assert _basic_auth_header("KEY123") == "Basic " + base64.b64encode(b"KEY123:").decode()

def test_search_companies_injected_fetcher():
    captured = {}
    def fake(url: str, headers: dict[str, str]) -> bytes:
        captured["url"], captured["headers"] = url, headers
        return _CH_JSON
    rows = search_companies("Bad Actor", api_key="KEY123", fetcher=fake)
    assert rows[0]["company_number"] == "01234567"
    assert captured["url"].startswith(CH_SEARCH_URL)
    assert captured["headers"]["Authorization"].startswith("Basic ")

def test_search_companies_requires_key():
    with pytest.raises(ExtractorUnavailable):
        search_companies("x", api_key=None, fetcher=lambda u, h: b"{}")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd company-due-diligence && pytest tests/test_extract_companies_house.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'cdd.extract.companies_house'`.

- [ ] **Step 3: Write minimal implementation**

Create `cdd/extract/companies_house.py`:
```python
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
    payload = json.loads(data.decode("utf-8"))
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
    from cdd.extract.fetch import get

    import httpx  # type: ignore[import-untyped]

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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd company-due-diligence && pytest tests/test_extract_companies_house.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add company-due-diligence/cdd/extract/companies_house.py company-due-diligence/tests/test_extract_companies_house.py
git commit -m "feat(extract): UK Companies House search connector (OGL, keyed)"
```

---

## Task 9: GDELT adverse-media connector

**Files:**
- Create: `cdd/extract/gdelt.py`
- Test: `tests/test_extract_gdelt.py`

GDELT DOC 2.0 API `https://api.gdeltproject.org/api/v2/doc/doc?query=NAME&mode=artlist&format=json` returns `{"articles":[{"url":..,"title":..,"seendate":..,"domain":..,"language":..}]}`. Open, no auth. Used for adverse-media signals (source_class: adverse_media_event).

- [ ] **Step 1: Write the failing test**

Create `tests/test_extract_gdelt.py`:
```python
from cdd.extract.gdelt import parse_articles, search_adverse_media, GDELT_DOC_URL

_GDELT_JSON = (
    b'{"articles":[{"url":"https://news.example/x","title":"Firm probed",'
    b'"seendate":"20260615T120000Z","domain":"news.example","language":"English"}]}'
)

def test_parse_articles():
    arts = parse_articles(_GDELT_JSON)
    assert arts == [{
        "url": "https://news.example/x", "title": "Firm probed",
        "seendate": "20260615T120000Z", "domain": "news.example",
        "language": "English",
    }]

def test_parse_articles_empty_on_blank():
    assert parse_articles(b"") == []
    assert parse_articles(b"{}") == []

def test_search_adverse_media_injected_fetcher():
    captured = {}
    def fake(url: str) -> bytes:
        captured["url"] = url
        return _GDELT_JSON
    arts = search_adverse_media('"Bad Actor LLC" (fraud OR sanctions)', fetcher=fake)
    assert arts[0]["domain"] == "news.example"
    assert captured["url"].startswith(GDELT_DOC_URL)
    assert "mode=artlist" in captured["url"] and "format=json" in captured["url"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd company-due-diligence && pytest tests/test_extract_gdelt.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'cdd.extract.gdelt'`.

- [ ] **Step 3: Write minimal implementation**

Create `cdd/extract/gdelt.py`:
```python
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
    payload = json.loads(text)
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd company-due-diligence && pytest tests/test_extract_gdelt.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add company-due-diligence/cdd/extract/gdelt.py company-due-diligence/tests/test_extract_gdelt.py
git commit -m "feat(extract): GDELT adverse-media search connector (open)"
```

---

## Task 10: Wire `capabilities()` + new `source_class` values

**Files:**
- Modify: `cdd/extract/__init__.py:19-29` (`capabilities`)
- Modify: `company-due-diligence/references/source_priority_rules.md`
- Test: `tests/test_extract_capability.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_extract_capability.py`:
```python
def test_capabilities_reports_new_backends():
    from cdd.extract import capabilities
    caps = capabilities()
    for key in ("gleif", "companies_house", "gdelt", "sanctions_xml"):
        assert key in caps and isinstance(caps[key], bool)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd company-due-diligence && pytest tests/test_extract_capability.py::test_capabilities_reports_new_backends -v`
Expected: FAIL — KeyError / assertion on missing keys.

- [ ] **Step 3: Write minimal implementation**

In `cdd/extract/__init__.py`, extend the `capabilities()` return dict with:
```python
        "gleif": _have("httpx"),
        "companies_house": _have("httpx"),
        "gdelt": _have("httpx"),
        "sanctions_xml": _have("defusedxml"),
```

In `company-due-diligence/references/source_priority_rules.md`, append a new subsection after the per-class table:
```markdown
### New source classes (open-data catalog connectors)

| `source_class` | `source_priority` | Typical `original_format` | `issuer_affiliated` | `regulatory_status` |
|---|---|---|---|---|
| `lei_registry` | primary | JSON (API) | no | government/registrar |
| `ubo_register` | primary | CSV, JSON | no | government |
| `pep_list` | primary | CSV, JSON | no | government/curated |
| `adverse_media_event` | signal | JSON | no | not filed |
| `economic_indicator` | secondary | JSON, SDMX | no | government |
| `trade_statistics` | secondary | JSON, CSV | no | government |
| `knowledge_graph` | signal | JSON, RDF | no | not filed |

These back the connectors in `cdd/extract/` (GLEIF → `lei_registry`, GDELT →
`adverse_media_event`, etc.); see `references/open_data_sources.md`.
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd company-due-diligence && pytest tests/test_extract_capability.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add company-due-diligence/cdd/extract/__init__.py company-due-diligence/references/source_priority_rules.md company-due-diligence/tests/test_extract_capability.py
git commit -m "feat(extract): capability probes + new source_class values for connectors"
```

---

## Task 11: Full gate + docs sync

**Files:**
- Modify: `company-due-diligence/SKILL.md` (the Hard rules / extraction note referencing optional tools)
- Modify: `company-due-diligence/references/open_data_sources.md` (mark wired connectors)

- [ ] **Step 1: Run the full quality gate**

Run:
```bash
cd company-due-diligence && pip install -e ".[extract,dev]" >/dev/null 2>&1
pytest -q && ruff check . && pyright
```
Expected: all tests pass, ruff clean, pyright 0 errors. Fix any failures before proceeding (do not edit tests to pass).

- [ ] **Step 2: Sync docs**

In `references/open_data_sources.md` §5, mark the now-wired connectors (OFAC + **EU/UK-FCDO/BIS/UN sanctions**, **GLEIF**, **Companies House**, **GDELT**) with a "✓ wired (`cdd/extract/...`)" note. In `SKILL.md`, update the extraction-tools sentence to mention the sanctions multi-list + GLEIF/Companies House/GDELT connectors are available under the `extract` extra.

- [ ] **Step 3: Commit**

```bash
git add company-due-diligence/SKILL.md company-due-diligence/references/open_data_sources.md
git commit -m "docs: mark Priority-1 connectors wired; sync SKILL extraction note"
```

---

## Self-Review

**Spec coverage (catalog §5 Priority 1):**
- (1) Sanctions multi-list — EU FSF (Task 3), UK FCDO replacing dead OFSI (Tasks 1-2), BIS CSL (Task 4), UN session-only (Tasks 1,5), dispatch (Task 6). ✓
- (2) GLEIF — Task 7. ✓
- (3) Companies House — Task 8. ✓
- (4) GDELT — Task 9. ✓
- 7 new `source_class` values — Task 10. ✓
- Retention discipline (UN session_only) — `LIST_METADATA` Task 1, honoured in Task 5 docstring. ✓

**Placeholder scan:** none — every code step has full code; every test has assertions; commands have expected output.

**Type consistency:** all sanctions parsers emit the same 7-key normalized dict consumed by the unchanged `screen_name`. `_PARSERS` (Task 6) references only functions defined in Tasks 1-5 (`parse_sdn_csv` pre-exists, `parse_uk_fcdo_csv`/`parse_eu_csv`/`parse_bis_csl_json`/`parse_un_xml` from Tasks 2-5). `GLEIF_SEARCH_URL`, `CH_SEARCH_URL`, `GDELT_DOC_URL`, `_basic_auth_header` names match between their tests and modules. The Companies House `Fetcher` is `(url, headers)->bytes` (2-arg) consistently in test fake and `_default_fetcher`; GLEIF/GDELT fetchers are `(url)->bytes` (1-arg) consistently.

**Format-confirmation risk:** Tasks 2-5 fixtures reflect documented 2026-06 schemas; Task 6 Step 6 is the live smoke test that catches schema drift. Flagged in the header rule.
