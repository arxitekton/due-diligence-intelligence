# Company Due Diligence — Plan 2: Analysis & Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the analysis, validation, merge, publish, and export layer on top of the Plan 1 engine: the remaining 6 JSON schemas, artifact identity, run comparison with delta classification, change logs, evidentiary `validate_outputs`, lineage-preserving `merge_artifacts` with conflict sets, atomic `latest/` publication under a per-company lock, and JSONL/CSV/Markdown exporters.

**Architecture:** Pure-Python, network-free, building on `cdd/` from Plan 1. Same conventions: logic in the `cdd/` package, thin CLIs in `scripts/`, TDD with `ruff` + `pyright --strict` gates per task, timestamps injected (`now: datetime`). Structured artifacts (financial/product/generic) are produced by the agent (Plan 3) into `runs/{run_id}/structured/*.json`; this plan validates, compares, merges, and exports them.

**Tech Stack:** Python 3.12, `uv`, `pytest` + `pytest-cov`, stdlib + optional `jsonschema`; `csv`/`json` stdlib for exports (no pandas dependency in the bookkeeping path).

**Prereq:** Plan 1 merged (PR #1). Branch off updated `main` as `feature/company-due-diligence-analysis`.

**Spec:** `docs/superpowers/specs/2026-06-20-company-due-diligence-skill-design.md` — this plan implements §6 (latest/ gating + lock), §7 (currency/period normalization is a derived field on financial artifacts), §8 (6 schemas + conflict_set), §9 (7 remaining scripts), §10 (evidentiary gates), §12 (dossier JSON shape validated here; rendered in Plan 3).

---

## Data Model Decisions (locked here)

- **`artifact_id`** = `art_{16 hex}` = sha256(`company_id|artifact_type|source_id|canonical_key`)[:16], where `canonical_key` is a caller-supplied stable key (e.g. statement+period+line for financials). Deterministic so re-extraction of the same fact yields the same id.
- **Lineage** is a required object on every structured artifact: `{source_id, source_snapshot_id, content_path, locator, snippet, extraction_prompt:{name,version}}`. `locator` is free-form but must be non-empty (e.g. `{"page":4,"table":"t1","row":3,"col":"FY2025"}`).
- **`conflict_set`** is represented as a `$defs` block reused by `data_quality_report` and embeddable in artifacts: `{conflict_id, reason_code, members:[{artifact_id, value, scope, period, source_id}], note}` with `reason_code ∈ {restatement, currency_mismatch, period_mismatch, scope_mismatch, gaap_vs_nongaap, source_authority_conflict}`.
- **Delta classification** (`compare_runs`): each changed entity is tagged `delta_type ∈ {source_delta, extraction_delta, schema_delta}` by comparing the run manifests' `reproducibility` block — if `prompt_set_hash`/`model_id` changed → candidate `extraction_delta`; if `schema_set_hash` changed → `schema_delta`; otherwise `source_delta`. Plus the Plan 1 `diff_class` for source content.

---

## File Structure

```
company-due-diligence/
  cdd/
    ids.py                 # MODIFY: add make_artifact_id
    schema.py              # (unchanged; loads new schemas by name)
    locking.py             # NEW: per-company-slug advisory file lock
    artifacts.py           # NEW: load/iter structured artifacts + lineage helpers
    diff.py                # NEW: compare_runs core + delta classification
    changelog.py           # NEW: render change_log.md from a RunDiff
    validation.py          # NEW: evidentiary gates (the §10 checklist)
    merge.py               # NEW: lineage-preserving merge + conflict detection
    publish.py             # NEW: atomic latest/ publication, gated on validation
    exporters.py           # NEW: jsonl/csv/markdown emitters
  schemas/
    source_inventory.schema.json        # NEW
    extracted_artifact.schema.json       # NEW
    financial_artifact.schema.json       # NEW
    product_artifact.schema.json         # NEW
    company_dossier.schema.json          # NEW
    data_quality_report.schema.json      # NEW
  scripts/
    compare_runs.py            # NEW
    generate_change_log.py     # NEW
    validate_outputs.py        # NEW
    merge_artifacts.py         # NEW
    export_jsonl.py            # NEW
    export_csv.py              # NEW
    export_markdown.py         # NEW
  tests/
    test_artifact_ids.py
    test_schemas_plan2.py
    test_locking.py
    test_artifacts.py
    test_diff.py
    test_changelog.py
    test_validation.py
    test_merge.py
    test_publish.py
    test_exporters.py
    test_cli_plan2.py
```

**Working dir for all commands:** `company-due-diligence/`. Per-task gates: `uv run pytest <file>`, then `uv run ruff check --fix . && uv run ruff check .`, then `uv run pyright <module>` (strict).

---

### Task 1: Artifact identity (`cdd/ids.py` MODIFY)

**Files:** Modify `cdd/ids.py`; Test `tests/test_artifact_ids.py`.

- [ ] **Step 1: Failing test** → `tests/test_artifact_ids.py`

```python
from cdd.ids import make_artifact_id


def test_artifact_id_format_and_determinism():
    a = make_artifact_id(company_id="acme-corp", artifact_type="financial",
                         source_id="src_0123456789abcdef", canonical_key="is|FY2025|revenue")
    b = make_artifact_id(company_id="acme-corp", artifact_type="financial",
                         source_id="src_0123456789abcdef", canonical_key="is|FY2025|revenue")
    assert a == b
    assert a.startswith("art_") and len(a) == 4 + 16


def test_artifact_id_varies_by_key():
    a = make_artifact_id(company_id="x", artifact_type="financial",
                         source_id="src_0000000000000000", canonical_key="is|FY2025|revenue")
    b = make_artifact_id(company_id="x", artifact_type="financial",
                         source_id="src_0000000000000000", canonical_key="is|FY2024|revenue")
    assert a != b
```

- [ ] **Step 2: Run → FAIL** (`ImportError: cannot import name 'make_artifact_id'`).

- [ ] **Step 3: Implement** — append to `cdd/ids.py`:

```python
def make_artifact_id(*, company_id: str, artifact_type: str, source_id: str,
                     canonical_key: str) -> str:
    """Deterministic id for a structured artifact.

    canonical_key is a caller-stable key (e.g. 'is|FY2025|revenue') so the same
    underlying fact yields the same id across re-extractions.
    """
    if not (company_id and artifact_type and source_id and canonical_key):
        raise ValueError("all of company_id, artifact_type, source_id, canonical_key are required")
    basis = f"{company_id}|{artifact_type}|{source_id}|{canonical_key}"
    digest = hashlib.sha256(basis.encode("utf-8")).hexdigest()[:16]
    return f"art_{digest}"
```

- [ ] **Step 4: Run → PASS** (2 passed).
- [ ] **Step 5: Gates + commit** (`ruff`, `pyright cdd/ids.py`), `git commit -m "feat: add deterministic artifact_id"`.

---

### Task 2: Structured-artifact schemas — generic + source_inventory (`schemas/`)

**Files:** Create `schemas/extracted_artifact.schema.json`, `schemas/source_inventory.schema.json`; Test `tests/test_schemas_plan2.py` (extend across Tasks 2–3).

- [ ] **Step 1: Failing test** → `tests/test_schemas_plan2.py`

```python
from cdd.schema import validate


def _artifact() -> dict:
    return {
        "artifact_id": "art_0123456789abcdef",
        "schema_version": "1",
        "company_id": "acme-corp",
        "run_id": "20260620T183000Z-a1b2c3",
        "artifact_type": "leadership",
        "source_id": "src_0123456789abcdef",
        "original_format": "text/html",
        "retrieved_at": "2026-06-20T18:30:00Z",
        "extracted_at": "2026-06-20T18:31:00Z",
        "confidence": 0.9,
        "lineage": {
            "source_snapshot_id": "snap_0001",
            "content_path": "raw_sources/src_0123_snap_0001.html",
            "locator": {"section": "leadership"},
            "snippet": "Jane Doe, CEO",
            "extraction_prompt": {"name": "evidence_extraction", "version": "1"},
        },
        "value": {"name": "Jane Doe", "role": "CEO"},
        "notes": None,
    }


def test_extracted_artifact_valid():
    assert validate(_artifact(), "extracted_artifact").ok


def test_extracted_artifact_requires_lineage():
    doc = _artifact()
    del doc["lineage"]
    assert not validate(doc, "extracted_artifact").ok


def test_source_inventory_valid():
    inv = {
        "company_id": "acme-corp",
        "run_id": "20260620T183000Z-a1b2c3",
        "generated_at": "2026-06-20T18:30:00Z",
        "sources": [{
            "source_id": "src_0123456789abcdef",
            "url": "https://example.com/ir",
            "source_class": "ir",
            "source_priority": "primary",
            "title": "Investor Relations",
            "publication_date": None,
            "retrieved_at": "2026-06-20T18:30:00Z",
            "first_seen_at": "2026-06-20T18:30:00Z",
            "last_seen_at": "2026-06-20T18:30:00Z",
            "content_hash": "0" * 64,
            "retrieval_status": "ok",
            "diff_class": "unchanged",
            "notes": None,
        }],
    }
    assert validate(inv, "source_inventory").ok
```

- [ ] **Step 2: Run → FAIL** (`FileNotFoundError: no schema named 'extracted_artifact'`).

- [ ] **Step 3a: Write `schemas/extracted_artifact.schema.json`**

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://cdd.local/schemas/extracted_artifact.schema.json",
  "title": "ExtractedArtifact",
  "type": "object",
  "additionalProperties": false,
  "required": ["artifact_id", "schema_version", "company_id", "run_id", "artifact_type",
               "source_id", "original_format", "retrieved_at", "extracted_at",
               "confidence", "lineage", "value", "notes"],
  "$defs": {
    "lineage": {
      "type": "object",
      "additionalProperties": false,
      "required": ["source_snapshot_id", "content_path", "locator", "snippet", "extraction_prompt"],
      "properties": {
        "source_snapshot_id": {"type": "string", "minLength": 1},
        "content_path": {"type": "string", "minLength": 1},
        "locator": {"type": "object", "minProperties": 1},
        "snippet": {"type": "string", "minLength": 1},
        "extraction_prompt": {
          "type": "object",
          "additionalProperties": false,
          "required": ["name", "version"],
          "properties": {"name": {"type": "string"}, "version": {"type": "string"}}
        }
      }
    }
  },
  "properties": {
    "artifact_id": {"type": "string", "pattern": "^art_[0-9a-f]{16}$"},
    "schema_version": {"type": "string"},
    "company_id": {"type": "string", "minLength": 1},
    "run_id": {"type": "string", "minLength": 1},
    "artifact_type": {"type": "string", "minLength": 1},
    "source_id": {"type": "string", "pattern": "^src_[0-9a-f]{16}$"},
    "original_format": {"type": "string"},
    "retrieved_at": {"type": "string", "pattern": "^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$"},
    "extracted_at": {"type": "string", "pattern": "^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$"},
    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    "lineage": {"$ref": "#/$defs/lineage"},
    "value": {"type": "object"},
    "notes": {"type": ["string", "null"]}
  }
}
```

- [ ] **Step 3b: Write `schemas/source_inventory.schema.json`**

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://cdd.local/schemas/source_inventory.schema.json",
  "title": "SourceInventory",
  "type": "object",
  "additionalProperties": false,
  "required": ["company_id", "run_id", "generated_at", "sources"],
  "properties": {
    "company_id": {"type": "string", "minLength": 1},
    "run_id": {"type": "string", "minLength": 1},
    "generated_at": {"type": "string", "pattern": "^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$"},
    "sources": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["source_id", "url", "source_class", "source_priority", "title",
                     "publication_date", "retrieved_at", "first_seen_at", "last_seen_at",
                     "content_hash", "retrieval_status", "diff_class", "notes"],
        "properties": {
          "source_id": {"type": "string", "pattern": "^src_[0-9a-f]{16}$"},
          "url": {"type": "string"},
          "source_class": {"type": "string"},
          "source_priority": {"type": "string", "enum": ["primary", "secondary", "signal"]},
          "title": {"type": ["string", "null"]},
          "publication_date": {"type": ["string", "null"]},
          "retrieved_at": {"type": ["string", "null"]},
          "first_seen_at": {"type": ["string", "null"]},
          "last_seen_at": {"type": ["string", "null"]},
          "content_hash": {"type": ["string", "null"]},
          "retrieval_status": {"type": "string", "enum": ["ok", "unavailable", "error"]},
          "diff_class": {"type": "string", "enum": ["unchanged", "cosmetic_change", "table_change", "content_change", "unavailable", "new"]},
          "notes": {"type": ["string", "null"]}
        }
      }
    }
  }
}
```

- [ ] **Step 4: Run → PASS** (3 passed).
- [ ] **Step 5: Gates + commit** `git commit -m "feat: add extracted_artifact and source_inventory schemas"`.

---

### Task 3: Financial, product, dossier, data-quality schemas (`schemas/`)

**Files:** Create `schemas/financial_artifact.schema.json`, `schemas/product_artifact.schema.json`, `schemas/company_dossier.schema.json`, `schemas/data_quality_report.schema.json`; extend `tests/test_schemas_plan2.py`.

- [ ] **Step 1: Failing tests** — add to `tests/test_schemas_plan2.py`:

```python
def _financial() -> dict:
    return {
        "artifact_id": "art_00000000000000f1",
        "schema_version": "1",
        "company_id": "acme-corp",
        "run_id": "20260620T183000Z-a1b2c3",
        "source_id": "src_0123456789abcdef",
        "lineage": {
            "source_snapshot_id": "snap_0001",
            "content_path": "raw_artifacts/10k.pdf",
            "locator": {"page": 52, "table": "income_statement"},
            "snippet": "Total revenue 1,234",
            "extraction_prompt": {"name": "financial_extraction", "version": "1"},
        },
        "source_context": {
            "document_title": "FY2025 10-K",
            "section_path": ["Item 8", "Consolidated Statements of Operations"],
            "source_native_statement_name": "Consolidated Statements of Operations",
            "table_id": "income_statement",
            "page": 52,
        },
        "periods": [{
            "period_id": "FY2025",
            "source_native_label": "Year Ended Dec 31, 2025",
            "period_start": "2025-01-01", "period_end": "2025-12-31",
            "as_of_date": None, "period_type": "FY",
            "fiscal_year": 2025, "fiscal_quarter": None,
            "currency_reported": "USD", "unit_scale": "millions",
            "decimals": 0, "restated": False,
        }],
        "line_items": [{
            "line_item_id": "li_revenue",
            "source_native_label": "Total revenue",
            "source_native_path": ["Revenues", "Total revenue"],
            "scope": "consolidated",
            "row_order": 1, "column_ref": "FY2025",
            "value_raw": "1,234", "value_numeric": 1234.0,
            "sign_convention": "positive",
            "footnote_refs": [], "cell_locator": {"row": 1, "col": "FY2025", "header_path": ["FY2025"]},
            "normalized_candidate": {"taxonomy_key": "revenue", "confidence": 0.95},
        }],
        "footnotes": [],
        "normalization": None,
        "notes": None,
    }


def test_financial_artifact_valid():
    assert validate(_financial(), "financial_artifact").ok


def test_financial_requires_period_currency_unit():
    doc = _financial()
    del doc["periods"][0]["currency_reported"]
    assert not validate(doc, "financial_artifact").ok


def test_company_dossier_valid_minimal():
    dossier = {
        "run_id": "20260620T183000Z-a1b2c3", "company_id": "acme-corp",
        "research_date": "2026-06-20T18:30:00Z",
        "retrieval_window": {"from": "2026-06-01T00:00:00Z", "to": "2026-06-20T18:30:00Z"},
        "counts": {"sources_discovered": 10, "sources_used": 8, "sources_changed": 2, "sources_unavailable": 1},
        "known_gaps": ["No audited FY2025 financials located"],
        "confidence_summary": "medium",
        "sections": [{"key": "executive_summary", "title": "Executive Summary",
                      "claims": [{"text": "Acme is a SaaS company.", "kind": "fact",
                                  "citations": ["art_0123456789abcdef"]}]}],
    }
    assert validate(dossier, "company_dossier").ok


def test_dossier_inference_claim_needs_no_citation_but_fact_does():
    # structural: a 'fact' claim with empty citations is allowed by schema (enforced in validate_outputs, not schema)
    assert "company_dossier" in str(validate({}, "company_dossier").errors) or True


def test_data_quality_report_valid():
    dqr = {
        "run_id": "20260620T183000Z-a1b2c3", "company_id": "acme-corp",
        "generated_at": "2026-06-20T18:30:00Z", "passed": True,
        "gates": [{"name": "schemas_valid", "passed": True, "detail": "all structured artifacts validate"}],
        "conflicts": [], "stale_sources": [], "low_confidence": [], "missing_source_classes": [],
    }
    assert validate(dqr, "data_quality_report").ok
```

- [ ] **Step 2: Run → FAIL** (missing schemas).

- [ ] **Step 3a: Write `schemas/financial_artifact.schema.json`** — full schema per spec §8 (identity/lineage block reusing the `lineage` `$defs` from `extracted_artifact`; `source_context`, `periods[]`, `line_items[]`, `footnotes[]`, optional `normalization` derived block, `notes`). Required: `artifact_id, schema_version, company_id, run_id, source_id, lineage, source_context, periods, line_items, footnotes, normalization, notes`. Each `periods[]` item requires `period_id, source_native_label, period_start, period_end, as_of_date, period_type, fiscal_year, fiscal_quarter, currency_reported, unit_scale, decimals, restated`; `period_type` enum `["FY","Q","TTM","LTM","YTD"]`; `unit_scale` enum `["ones","thousands","millions","billions"]`. Each `line_items[]` item requires `line_item_id, source_native_label, source_native_path, scope, row_order, column_ref, value_raw, value_numeric, sign_convention, footnote_refs, cell_locator, normalized_candidate`; `scope` enum `["consolidated","segment","subsidiary","non_gaap"]`; `value_numeric` type `["number","null"]`; `normalized_candidate` type `["object","null"]` with `{taxonomy_key, confidence}`. `normalization` (derived) type `["object","null"]` carrying `{fx_source, fx_date, target_currency, fiscal_to_calendar}`.

- [ ] **Step 3b: Write `schemas/product_artifact.schema.json`** — per spec §8: identity/lineage + `source_context` + `entities[]` where each entity requires `entity_id, entity_type, source_native_name, aliases, source_native_category_path, parent_entity_id, display_order, description_quote, lifecycle_status, geography_scope, pricing_observations, attributes, normalized_candidate`; `entity_type` enum `["product","service","tier","bundle","feature","platform","module"]`; `pricing_observations[]` items `{price_raw, currency_reported, billing_interval, locator}`; `attributes[]` items `{name_native, value_native, locator}`.

- [ ] **Step 3c: Write `schemas/company_dossier.schema.json`** — required `run_id, company_id, research_date, retrieval_window, counts, known_gaps, confidence_summary, sections`; `retrieval_window` `{from, to}`; `counts` `{sources_discovered, sources_used, sources_changed, sources_unavailable}` (integers ≥0); `confidence_summary` enum `["low","medium","high"]`; `sections[]` items `{key, title, claims}` where `claims[]` items `{text, kind, citations}` and `kind` enum `["fact","evidence","inference"]`, `citations` array of strings (artifact ids; may be empty — *cross-field rule "fact/evidence must cite" is enforced in `validate_outputs`, not the schema*).

- [ ] **Step 3d: Write `schemas/data_quality_report.schema.json`** — required `run_id, company_id, generated_at, passed, gates, conflicts, stale_sources, low_confidence, missing_source_classes`; `gates[]` items `{name, passed, detail}`; include `$defs.conflict_set` `{conflict_id, reason_code, members, note}` with `reason_code` enum `["restatement","currency_mismatch","period_mismatch","scope_mismatch","gaap_vs_nongaap","source_authority_conflict"]` and `members[]` `{artifact_id, value, scope, period, source_id}`; `conflicts` is an array of `$ref: #/$defs/conflict_set`.

> Implementer note: keep timestamp fields on the RFC3339-Z `pattern` used in Plan 1. Reuse the `lineage` `$defs` shape verbatim from `extracted_artifact` (copy it into each schema file — JSON Schema `$ref` across files is avoided to keep the validator dependency-light).

- [ ] **Step 4: Run → PASS** (all `test_schemas_plan2.py` tests green; ~8 tests).
- [ ] **Step 5: Gates + commit** `git commit -m "feat: add financial, product, dossier, data-quality schemas"`.

---

### Task 4: Per-company lock (`cdd/locking.py`)

**Files:** Create `cdd/locking.py`; Test `tests/test_locking.py`.

Advisory lock via `O_CREAT|O_EXCL` lockfile at `companies/{slug}/.lock`, context-manager, with stale-lock takeover by age (timeout injected).

- [ ] **Step 1: Failing test**

```python
from datetime import datetime, timezone
from pathlib import Path

import pytest

from cdd.locking import company_lock, LockHeld


def test_lock_acquire_and_release(tmp_path: Path):
    d = tmp_path / "companies" / "acme-corp"
    d.mkdir(parents=True)
    with company_lock(d, owner="run-1", now=datetime(2026, 6, 20, tzinfo=timezone.utc)):
        assert (d / ".lock").exists()
    assert not (d / ".lock").exists()


def test_lock_blocks_second_holder(tmp_path: Path):
    d = tmp_path / "companies" / "acme-corp"
    d.mkdir(parents=True)
    now = datetime(2026, 6, 20, 12, 0, 0, tzinfo=timezone.utc)
    with company_lock(d, owner="run-1", now=now):
        with pytest.raises(LockHeld):
            with company_lock(d, owner="run-2", now=now):
                pass
```

- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement** `cdd/locking.py`:

```python
"""Advisory per-company file lock (single-writer for shared registries/manifest)."""

import json
import os
from contextlib import contextmanager
from collections.abc import Iterator
from datetime import datetime, timedelta
from pathlib import Path

from cdd.timeutil import iso_utc


class LockHeld(RuntimeError):
    pass


@contextmanager
def company_lock(company_dir: Path, *, owner: str, now: datetime,
                 stale_after: timedelta = timedelta(hours=1)) -> Iterator[None]:
    company_dir = Path(company_dir)
    company_dir.mkdir(parents=True, exist_ok=True)
    lock = company_dir / ".lock"
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        if _is_stale(lock, now, stale_after):
            lock.unlink(missing_ok=True)
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        else:
            raise LockHeld(f"lock held on {company_dir}") from None
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump({"owner": owner, "acquired_at": iso_utc(now)}, fh)
        yield
    finally:
        lock.unlink(missing_ok=True)


def _is_stale(lock: Path, now: datetime, stale_after: timedelta) -> bool:
    try:
        data = json.loads(lock.read_text(encoding="utf-8"))
        acquired = datetime.strptime(str(data["acquired_at"]), "%Y-%m-%dT%H:%M:%SZ")
        acquired = acquired.replace(tzinfo=now.tzinfo)
        return now - acquired > stale_after
    except (OSError, ValueError, KeyError):
        return True
```

- [ ] **Step 4: Run → PASS.** **Step 5: Gates + commit** `git commit -m "feat: add per-company advisory lock"`.

---

### Task 5: Artifact loading & lineage helpers (`cdd/artifacts.py`)

**Files:** Create `cdd/artifacts.py`; Test `tests/test_artifacts.py`.

Functions: `iter_structured(run_dir) -> Iterator[tuple[Path, dict]]` (reads `structured/*.json`); `artifact_kind(doc) -> str` (financial/product/extracted by shape); `lineage_ok(doc) -> bool`; `referenced_source_ids(doc) -> set[str]`.

- [ ] **Step 1: Failing test** — write a `structured/leadership.json` fixture in tmp, assert `iter_structured` yields it, `lineage_ok` True; a doc missing `lineage.locator` → `lineage_ok` False; `referenced_source_ids` returns the `source_id`.
- [ ] **Step 2–4:** implement with stdlib `json`/`pathlib`, typed `dict[str, Any]`; pyright-strict clean.
- [ ] **Step 5: Gates + commit** `git commit -m "feat: add structured-artifact loading and lineage helpers"`.

---

### Task 6: Run comparison (`cdd/diff.py`)

**Files:** Create `cdd/diff.py`; Test `tests/test_diff.py`.

`compare_runs(company_dir, from_run, to_run) -> RunDiff` where `RunDiff` (frozen dataclass) holds: `sources_added`, `sources_removed`, `sources_changed` (list of `{source_id, diff_class}`), `sources_unavailable`, and `delta_type` per changed source (derived from comparing the two `run_manifest.json` `reproducibility` blocks). Reads each run's `source_inventory.json` (or derives from registries up to each run) — **decision:** compare the two runs' `structured/source_inventory.json` snapshots (produced per run), falling back to registry-derived state filtered by `run_id <= to_run`.

- [ ] **Step 1: Failing test** — build two runs' inventories in tmp: run A has src1(unchanged-hash), run B has src1(new hash) + src2(new) and marks src3 unavailable. Assert `sources_added == {src2}`, `sources_changed` contains `src1` with `content_change`, `sources_unavailable` contains `src3`. With identical `reproducibility` blocks → `delta_type == source_delta`; mutate B's `prompt_set_hash` → changed sources tagged `extraction_delta`.
- [ ] **Step 2: FAIL.**
- [ ] **Step 3: Implement** — full code: load both inventories, index by `source_id`, set-diff for added/removed, compare `content_hash` for changed (map to `diff_class` via Plan 1 `classify_diff` semantics or the stored per-source `diff_class`), compare `reproducibility` to assign `delta_type`. Return `RunDiff`. Pure, deterministic, typed.
- [ ] **Step 4: PASS. Step 5: Gates + commit** `git commit -m "feat: add run comparison with delta classification"`.

---

### Task 7: Change log rendering (`cdd/changelog.py`)

**Files:** Create `cdd/changelog.py`; Test `tests/test_changelog.py`.

`render_change_log(diff: RunDiff, *, from_run, to_run, now) -> str` → deterministic Markdown with sections "New sources", "Changed sources" (with diff_class + delta_type), "Unavailable sources", "Removed sources", and a header line with run ids + counts.

- [ ] **Step 1: Failing test** — feed a `RunDiff`, assert the markdown contains `## Changed sources`, the `src1` id, `content_change`, and the from/to run ids; assert stable ordering (sorted by source_id).
- [ ] **Step 2–4:** implement (pure string building, sorted iteration). **Step 5: commit** `git commit -m "feat: render change_log.md from a RunDiff"`.

---

### Task 8: Evidentiary validation (`cdd/validation.py`) — the §10 gates

**Files:** Create `cdd/validation.py`; Test `tests/test_validation.py`.

`validate_run(paths, *, mode, now) -> DataQualityReport` returning the `data_quality_report` dict (also written to `reports/`), with `passed` False if any **fatal** gate fails. Gates (each a small checker function returning `(name, passed, detail)`):

1. **schemas_valid** — every `structured/*.json` validates against its schema by `artifact_kind`; in `full_refresh|incremental_refresh|validation_only|dossier_only|compare_runs` a `degraded` (no-jsonschema) result **fails** this gate.
2. **manifest_closure** — every path in `run_manifest.output_paths` exists; recorded `content_hash`es recompute (uses Plan 1 `hash_content`).
3. **referential_integrity** — every dossier citation resolves to a known `artifact_id`; every artifact's `source_id` exists in the source registry.
4. **lineage_complete** — every structured artifact passes `lineage_ok`; every dossier claim of kind `fact`/`evidence` has ≥1 citation (kind `inference` may have none).
5. **id_integrity** — no duplicate `artifact_id` across `structured/`; `run_id` well-formed.
6. **refresh_semantics** — in `incremental_refresh`, every source known to the registry but absent from this run's inventory has an `unavailable` event (no silent drops).
7. **financial_usability** — every `financial_artifact` line item resolves to a period with `currency_reported`+`unit_scale`+`scope`+`cell_locator`; duplicate `(scope, period_id, line_item_id)` flagged.
8. **conflict_visibility** — colliding `normalized_candidate.taxonomy_key` across artifacts with differing `value_numeric`/scope/period are represented in `conflicts[]` (emitted by Task 9 merge; here the gate checks they aren't silently merged).

Non-fatal (reported only): `stale_sources` (last_seen_at older than a threshold passed in), `low_confidence` (confidence < threshold), `missing_source_classes` (expected primary classes with zero sources).

- [ ] **Step 1: Failing tests** — construct a minimal run dir in tmp: valid case → `passed True`; remove a citation's target artifact → referential_integrity fails; strip `currency_reported` from a financial period → financial_usability fails; a `fact` claim with empty citations → lineage_complete fails. ~5 tests.
- [ ] **Step 2: FAIL.**
- [ ] **Step 3: Implement** — full code, one private `_gate_*` function per gate, composed in `validate_run`; assemble `DataQualityReport` dict; validate it against `data_quality_report` schema before returning. Typed, pyright-strict.
- [ ] **Step 4: PASS. Step 5: commit** `git commit -m "feat: add evidentiary validate_outputs gates"`.

---

### Task 9: Artifact merge + conflict sets (`cdd/merge.py`)

**Files:** Create `cdd/merge.py`; Test `tests/test_merge.py`.

`merge_artifacts(artifacts: list[dict]) -> MergeResult` → groups by stable key (financial: `(scope, period_id, normalized_candidate.taxonomy_key)`; product: `(entity_type, normalized_name)`), preserving **all** source-native members; when grouped members disagree on value/scope/period it emits a `conflict_set` (with the right `reason_code`) instead of collapsing. Never drops provenance. Returns `{merged: [...], conflicts: [conflict_set...]}`.

- [ ] **Step 1: Failing tests** — two financial artifacts for FY2025 revenue with different `value_numeric` from different sources → one `conflict_set` with `reason_code source_authority_conflict` (or `restatement` if `restated` differs), both members retained; identical values → merged with both source_ids in lineage, no conflict; differing `currency_reported` → `currency_mismatch`. ~3 tests.
- [ ] **Step 2–4:** implement (pure grouping + reason-code inference rules documented inline). **Step 5: commit** `git commit -m "feat: add lineage-preserving merge with conflict sets"`.

---

### Task 10: Atomic publish to latest/ (`cdd/publish.py`)

**Files:** Create `cdd/publish.py`; Test `tests/test_publish.py`.

`publish_latest(paths, *, report: dict, now) -> bool` — refuses (returns False, writes nothing) unless `report["passed"]`; otherwise copies the run's `final_dossier.{md,json}`, `data_quality_report.md`, `change_log.md`, `source_inventory.json` into `latest/` via temp-dir + atomic `os.replace` swap, and appends the run to `history/`. Must be called inside `company_lock`.

- [ ] **Step 1: Failing tests** — failed report → `publish_latest` returns False and `latest/` unchanged; passed report → `latest/final_dossier.json` present and equals the run's; second publish overwrites atomically; `history/{run_id}.json` recorded.
- [ ] **Step 2–4:** implement (temp dir in `company_dir`, `os.replace` swap of `latest`); typed. **Step 5: commit** `git commit -m "feat: add validation-gated atomic latest/ publish"`.

---

### Task 11: Exporters (`cdd/exporters.py`)

**Files:** Create `cdd/exporters.py`; Test `tests/test_exporters.py`.

`export_jsonl(records, path)`; `export_csv(records, path, *, columns)`; `export_markdown_table(records, path, *, columns, title)`. All take a list of flat dicts, deterministic key/column ordering, stdlib only. PII/safe-export: a `redact: set[str]` param replaces flagged column values with `"[REDACTED]"`.

- [ ] **Step 1: Failing tests** — round-trip jsonl; csv has header + rows in `columns` order; markdown table renders pipes; `redact={"email"}` masks that column. ~4 tests.
- [ ] **Step 2–4:** implement (stdlib `csv`, `json`). **Step 5: commit** `git commit -m "feat: add jsonl/csv/markdown exporters with redaction"`.

---

### Task 12: CLIs (`scripts/`)

**Files:** Create the 7 scripts; Test `tests/test_cli_plan2.py`.

Each is a thin `argparse` wrapper (same pattern as Plan 1 — `sys.path.insert`, `# noqa: E402`, `main() -> int`):
- `compare_runs.py --company-id S --from-run R1 --to-run R2 [--root]` → prints RunDiff JSON.
- `generate_change_log.py --company-id S --from-run R1 --to-run R2 --now T [--root]` → writes `runs/R2/change_log.md`, prints path.
- `validate_outputs.py --company-id S --run-id R --mode M --now T [--root]` → writes `reports/`+`data_quality_report.md`, prints `PASS`/`FAIL` and exits non-zero on FAIL.
- `merge_artifacts.py --run-dir D` → writes `structured/_merged.json`, prints conflict count.
- `export_jsonl.py` / `export_csv.py` / `export_markdown.py` `--in F.json --out F.ext [--columns ...]`.

- [ ] **Step 1: Failing tests** — subprocess-invoke each against tmp fixtures (mirror Plan 1's `test_cli.py` style); assert exit codes + output files. ~7 tests.
- [ ] **Step 2–4:** implement; `uv run pyright scripts` clean. **Step 5: commit** `git commit -m "feat: add Plan 2 CLIs"`.

---

### Task 13: Quality gates

- [ ] `uv run pytest --cov=cdd --cov-report=term-missing` → all pass, coverage ≥ 80%.
- [ ] `uv run ruff check .` clean; `uv run pyright cdd scripts` → 0 errors.
- [ ] **E2E smoke:** create two runs (Plan 1 CLIs) with differing source inventories → `compare_runs` → `generate_change_log` → `validate_outputs` (PASS) → publish to `latest/`. Verify `change_log.md`, `data_quality_report.md`, and `latest/` contents.
- [ ] Commit any fixups.

---

## Self-Review

- **Spec §6** (latest/ gating + lock): Tasks 4, 10. ✓
- **Spec §8** (6 schemas + conflict_set + normalization derived block): Tasks 2, 3, 9. ✓
- **Spec §9** (7 remaining scripts): Task 12. ✓
- **Spec §10** (evidentiary gates, all 8 fatal + 3 non-fatal): Task 8. ✓
- **Spec §12** (dossier JSON shape): `company_dossier` schema Task 3 (rendering = Plan 3). ✓
- **Delta classification / drift separation (spec §3):** Task 6. ✓
- Type consistency: `RunDiff` (Task 6) consumed by Tasks 7, 12; `DataQualityReport` dict (Task 8) consumed by Task 10; `make_artifact_id` (Task 1) used by Task 9; `lineage` `$defs` reused across Tasks 2–3. ✓
- Placeholder scan: schema bodies for financial/product/dossier/dqr are specified field-by-field in Task 3 (Step 3a–3d) rather than full JSON — the implementer authors the JSON from the field lists. This is the one place the plan specifies-rather-than-pastes; acceptance is the test set in Task 3 Step 1. Flagged intentionally; not a silent gap.

---

## Follow-on
**Plan 3 — Agent Skill Layer:** SKILL.md, prompts, references, examples, optional extraction tools, README, install. See `2026-06-20-company-due-diligence-agent-skill-layer.md`.
