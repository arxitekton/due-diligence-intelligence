# Company Due Diligence — Plan 1: Foundations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the deterministic, network-free Python engine + JSON schemas that underpin the `company-due-diligence` skill: stable identity, run lifecycle, dual-hash canonicalization, append-only event-log registries, and derived manifests — all schema-validated and TDD-covered.

**Architecture:** Shared logic lives in an importable `cdd/` package; the spec-required `scripts/*.py` are thin CLI wrappers over it. Registries are append-only JSONL event logs; current-state views (`manifest.json`, indexes) are *derived* and regenerated, never mutated in place. All code here is deterministic and makes no network calls.

**Tech Stack:** Python 3.12, `uv`, `pytest` + `pytest-cov`, stdlib-only core (`hashlib`, `json`, `argparse`, `pathlib`, `datetime`, `csv`, `re`, `unicodedata`), optional `jsonschema` (graceful fallback). `ruff` + `pyright` for quality gates.

**Spec:** `docs/superpowers/specs/2026-06-20-company-due-diligence-skill-design.md` (§2–§6, §8–§9 are in scope for this plan; §7, §10–§13 land in Plans 2–3).

**Determinism note:** Timestamps are an explicit input to every function that needs one (`now: datetime`), never read from the clock inside library code. CLI wrappers inject `datetime.now(timezone.utc)`. This keeps the library pure and tests reproducible.

---

## File Structure

```
company-due-diligence/
  pyproject.toml                     # uv project, deps, ruff/pytest config
  .gitignore                         # ignores output/
  cdd/
    __init__.py
    timeutil.py                      # UTC iso helpers (pure)
    ids.py                           # normalize_company_id, run_id
    paths.py                         # output tree path resolver
    runlifecycle.py                  # create_run: folders + seed run_manifest
    canonicalize.py                  # MIME-aware canonicalization profiles
    hashing.py                       # dual hash + diff_class
    schema.py                        # schema loader + validate (jsonschema-optional)
    registry.py                      # append events + read log + derive state
    manifest.py                      # build derived manifest + indexes
  schemas/
    run_manifest.schema.json
    source_registry.schema.json
    artifact_registry.schema.json
    source_inventory.schema.json
    extracted_artifact.schema.json
    financial_artifact.schema.json
    product_artifact.schema.json
    company_dossier.schema.json
    data_quality_report.schema.json
  scripts/
    normalize_company_id.py
    create_run.py
    compute_hashes.py
    update_source_registry.py
    update_artifact_registry.py
    build_manifest.py
  tests/
    conftest.py
    test_timeutil.py
    test_ids.py
    test_paths.py
    test_runlifecycle.py
    test_canonicalize.py
    test_hashing.py
    test_schema.py
    test_registry.py
    test_manifest.py
    test_cli.py
```

**Working directory for all commands:** `company-due-diligence/`. Create it first (Task 0). All `git add` paths below are relative to repo root.

---

### Task 0: Project scaffold

**Files:**
- Create: `company-due-diligence/pyproject.toml`
- Create: `company-due-diligence/.gitignore`
- Create: `company-due-diligence/cdd/__init__.py`
- Create: `company-due-diligence/tests/conftest.py`

- [ ] **Step 1: Create the package directories**

Run (from repo root):
```bash
mkdir -p company-due-diligence/cdd company-due-diligence/schemas company-due-diligence/scripts company-due-diligence/tests
```

- [ ] **Step 2: Write `company-due-diligence/pyproject.toml`**

```toml
[project]
name = "company-due-diligence"
version = "0.1.0"
description = "Deterministic engine for the company-due-diligence Claude Code skill"
requires-python = ">=3.12"
dependencies = []

[project.optional-dependencies]
validate = ["jsonschema>=4.21"]
extract = [
  "httpx>=0.27",
  "trafilatura>=1.8",
  "beautifulsoup4>=4.12",
  "lxml>=5.2",
  "pdfplumber>=0.11",
  "pymupdf>=1.24",
  "pandas>=2.2",
  "edgartools>=2.27",
]
dev = ["pytest>=8.2", "pytest-cov>=5.0", "ruff>=0.5", "pyright>=1.1", "jsonschema>=4.21"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-q"
pythonpath = ["."]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B"]

[tool.pyright]
include = ["cdd", "scripts"]
typeCheckingMode = "strict"
```

- [ ] **Step 3: Write `company-due-diligence/.gitignore`**

```gitignore
output/
.venv/
__pycache__/
*.pyc
.pytest_cache/
.ruff_cache/
```

- [ ] **Step 4: Write `company-due-diligence/cdd/__init__.py`**

```python
"""Deterministic, network-free core for the company-due-diligence skill."""

__all__ = ["__version__"]
__version__ = "0.1.0"
```

- [ ] **Step 5: Write `company-due-diligence/tests/conftest.py`**

```python
"""Shared pytest fixtures."""

from datetime import datetime, timezone

import pytest


@pytest.fixture
def fixed_now() -> datetime:
    """A fixed UTC instant for reproducible tests."""
    return datetime(2026, 6, 20, 18, 30, 0, tzinfo=timezone.utc)
```

- [ ] **Step 6: Set up the venv and verify pytest runs**

Run (from `company-due-diligence/`):
```bash
cd company-due-diligence
uv venv && uv pip install -e ".[dev]"
uv run pytest
```
Expected: pytest collects 0 tests and exits 0 (`no tests ran`).

- [ ] **Step 7: Commit**

```bash
git add company-due-diligence/pyproject.toml company-due-diligence/.gitignore company-due-diligence/cdd/__init__.py company-due-diligence/tests/conftest.py
git commit -m "chore: scaffold company-due-diligence engine project"
```

---

### Task 1: Time helpers (`cdd/timeutil.py`)

**Files:**
- Create: `company-due-diligence/cdd/timeutil.py`
- Test: `company-due-diligence/tests/test_timeutil.py`

- [ ] **Step 1: Write the failing test**

```python
from datetime import datetime, timezone

from cdd.timeutil import iso_utc, compact_stamp


def test_iso_utc_formats_with_z_suffix():
    dt = datetime(2026, 6, 20, 18, 30, 0, tzinfo=timezone.utc)
    assert iso_utc(dt) == "2026-06-20T18:30:00Z"


def test_compact_stamp_is_run_id_safe():
    dt = datetime(2026, 6, 20, 18, 30, 0, tzinfo=timezone.utc)
    assert compact_stamp(dt) == "20260620T183000Z"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_timeutil.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'cdd.timeutil'`

- [ ] **Step 3: Write minimal implementation**

`company-due-diligence/cdd/timeutil.py`:
```python
"""Pure UTC time formatting helpers (no clock reads)."""

from datetime import datetime, timezone


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def iso_utc(dt: datetime) -> str:
    """RFC3339 UTC, second precision, 'Z' suffix."""
    return _as_utc(dt).strftime("%Y-%m-%dT%H:%M:%SZ")


def compact_stamp(dt: datetime) -> str:
    """Compact UTC stamp suitable for run_id prefixes."""
    return _as_utc(dt).strftime("%Y%m%dT%H%M%SZ")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_timeutil.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add company-due-diligence/cdd/timeutil.py company-due-diligence/tests/test_timeutil.py
git commit -m "feat: add UTC time formatting helpers"
```

---

### Task 2: Identity (`cdd/ids.py`) — `normalize_company_id` + `run_id`

**Files:**
- Create: `company-due-diligence/cdd/ids.py`
- Test: `company-due-diligence/tests/test_ids.py`

- [ ] **Step 1: Write the failing test**

```python
from datetime import datetime, timezone

from cdd.ids import normalize_company_id, make_run_id, source_id_for


def test_slug_lowercases_and_hyphenates():
    assert normalize_company_id("Acme Corp.") == "acme-corp"


def test_slug_strips_legal_suffixes_and_accents():
    assert normalize_company_id("Société Générale S.A.") == "societe-generale"


def test_slug_collapses_repeats_and_trims():
    assert normalize_company_id("  Foo   &   Bar, Inc.  ") == "foo-bar"


def test_slug_rejects_empty():
    import pytest

    with pytest.raises(ValueError):
        normalize_company_id("   ")


def test_run_id_has_stamp_and_token():
    dt = datetime(2026, 6, 20, 18, 30, 0, tzinfo=timezone.utc)
    rid = make_run_id(dt, token="a1b2c3")
    assert rid == "20260620T183000Z-a1b2c3"


def test_source_id_is_stable_for_same_logical_source():
    a = source_id_for("https://Example.com/IR/?utm_source=x", source_class="ir")
    b = source_id_for("https://example.com/ir/", source_class="ir")
    assert a == b  # tracking params + case + trailing slash normalized away


def test_source_id_differs_by_source_class():
    a = source_id_for("https://example.com/pr", source_class="ir")
    b = source_id_for("https://example.com/pr", source_class="newswire")
    assert a != b  # same URL, different logical source
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ids.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'cdd.ids'`

- [ ] **Step 3: Write minimal implementation**

`company-due-diligence/cdd/ids.py`:
```python
"""Stable identity: company slug, run_id, and logical source_id."""

import hashlib
import re
import unicodedata
from datetime import datetime
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

from cdd.timeutil import compact_stamp

_LEGAL_SUFFIXES = {
    "inc", "incorporated", "corp", "corporation", "co", "company", "ltd",
    "limited", "llc", "llp", "plc", "sa", "ag", "gmbh", "nv", "bv", "spa",
    "pty", "kk", "oyj", "ab", "as",
}
_TRACKING_PREFIXES = ("utm_", "fbclid", "gclid", "mc_", "ref", "_ga")


def normalize_company_id(name: str) -> str:
    """Deterministic, stable slug for a company name."""
    decomposed = unicodedata.normalize("NFKD", name)
    ascii_name = decomposed.encode("ascii", "ignore").decode("ascii").lower()
    tokens = re.split(r"[^a-z0-9]+", ascii_name)
    kept = [t for t in tokens if t and t not in _LEGAL_SUFFIXES]
    slug = "-".join(kept)
    if not slug:
        raise ValueError(f"company name produced empty slug: {name!r}")
    return slug


def make_run_id(now: datetime, token: str) -> str:
    """run_id = {compact UTC stamp}-{short token}."""
    if not re.fullmatch(r"[0-9a-z]{4,12}", token):
        raise ValueError(f"token must be 4-12 lowercase alnum chars: {token!r}")
    return f"{compact_stamp(now)}-{token}"


def _normalize_url(url: str) -> str:
    parts = urlsplit(url.strip())
    scheme = parts.scheme.lower() or "https"
    netloc = parts.netloc.lower()
    path = parts.path.rstrip("/") or "/"
    query_pairs = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if not k.lower().startswith(_TRACKING_PREFIXES)
    ]
    query = urlencode(sorted(query_pairs))
    return urlunsplit((scheme, netloc, path, query, ""))


def source_id_for(url: str, source_class: str) -> str:
    """Stable id for a logical source = normalized URL + source_class."""
    if not source_class:
        raise ValueError("source_class is required")
    basis = f"{source_class.lower()}|{_normalize_url(url)}"
    digest = hashlib.sha256(basis.encode("utf-8")).hexdigest()[:16]
    return f"src_{digest}"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_ids.py -v`
Expected: PASS (7 passed)

- [ ] **Step 5: Commit**

```bash
git add company-due-diligence/cdd/ids.py company-due-diligence/tests/test_ids.py
git commit -m "feat: add company slug, run_id, and logical source_id"
```

---

### Task 3: Output path resolver (`cdd/paths.py`)

**Files:**
- Create: `company-due-diligence/cdd/paths.py`
- Test: `company-due-diligence/tests/test_paths.py`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path

from cdd.paths import OutputPaths

RUN_SUBDIRS = [
    "raw_sources", "raw_artifacts", "extracted_tables",
    "structured", "reports", "logs",
]


def test_company_dir_layout(tmp_path: Path):
    p = OutputPaths(root=tmp_path, company_slug="acme-corp", run_id="20260620T183000Z-a1")
    assert p.company_dir == tmp_path / "companies" / "acme-corp"
    assert p.source_registry == p.company_dir / "source_registry.jsonl"
    assert p.artifact_registry == p.company_dir / "artifact_registry.jsonl"
    assert p.manifest == p.company_dir / "manifest.json"


def test_run_dir_and_subdirs(tmp_path: Path):
    p = OutputPaths(root=tmp_path, company_slug="acme-corp", run_id="20260620T183000Z-a1")
    assert p.run_dir == p.company_dir / "runs" / "20260620T183000Z-a1"
    for sub in RUN_SUBDIRS:
        assert p.run_subdir(sub) == p.run_dir / sub


def test_run_subdir_rejects_unknown(tmp_path: Path):
    import pytest

    p = OutputPaths(root=tmp_path, company_slug="acme-corp", run_id="r1")
    with pytest.raises(ValueError):
        p.run_subdir("nope")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_paths.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'cdd.paths'`

- [ ] **Step 3: Write minimal implementation**

`company-due-diligence/cdd/paths.py`:
```python
"""Resolver for the deterministic output tree (no I/O)."""

from dataclasses import dataclass
from pathlib import Path

RUN_SUBDIRS = (
    "raw_sources",
    "raw_artifacts",
    "extracted_tables",
    "structured",
    "reports",
    "logs",
)


@dataclass(frozen=True)
class OutputPaths:
    root: Path
    company_slug: str
    run_id: str

    @property
    def company_dir(self) -> Path:
        return self.root / "companies" / self.company_slug

    @property
    def source_registry(self) -> Path:
        return self.company_dir / "source_registry.jsonl"

    @property
    def artifact_registry(self) -> Path:
        return self.company_dir / "artifact_registry.jsonl"

    @property
    def manifest(self) -> Path:
        return self.company_dir / "manifest.json"

    @property
    def latest_dir(self) -> Path:
        return self.company_dir / "latest"

    @property
    def history_dir(self) -> Path:
        return self.company_dir / "history"

    @property
    def run_dir(self) -> Path:
        return self.company_dir / "runs" / self.run_id

    def run_subdir(self, name: str) -> Path:
        if name not in RUN_SUBDIRS:
            raise ValueError(f"unknown run subdir: {name!r}")
        return self.run_dir / name
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_paths.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add company-due-diligence/cdd/paths.py company-due-diligence/tests/test_paths.py
git commit -m "feat: add output path resolver"
```

---

### Task 4: JSON schemas + validator (`schemas/*`, `cdd/schema.py`)

**Files:**
- Create: `company-due-diligence/schemas/run_manifest.schema.json`
- Create: `company-due-diligence/schemas/source_registry.schema.json`
- Create: `company-due-diligence/schemas/artifact_registry.schema.json`
- Create: `company-due-diligence/cdd/schema.py`
- Test: `company-due-diligence/tests/test_schema.py`

> The remaining six schemas (`source_inventory`, `extracted_artifact`, `financial_artifact`, `product_artifact`, `company_dossier`, `data_quality_report`) are authored in Plan 2 where their producers/consumers are built. This task delivers the three schemas the Foundations engine actually writes, plus the reusable validator.

- [ ] **Step 1: Write the failing test**

```python
from datetime import datetime, timezone

from cdd.schema import load_schema, validate, ValidationResult


def _valid_run_manifest() -> dict:
    return {
        "run_id": "20260620T183000Z-a1b2c3",
        "company_id": "acme-corp",
        "company_name": "Acme Corp.",
        "started_at": "2026-06-20T18:30:00Z",
        "completed_at": None,
        "mode": "full_refresh",
        "input_parameters": {"company_name": "Acme Corp."},
        "reproducibility": {
            "prompt_set_hash": "0" * 16,
            "schema_set_hash": "1" * 16,
            "model_id": "claude-opus-4-8",
            "tool_versions": {},
            "normalizer_profile_versions": {"html": "1"},
            "locale": "en-US",
        },
        "sources_discovered": 0,
        "sources_retrieved": 0,
        "sources_new": 0,
        "sources_changed": 0,
        "sources_unavailable": 0,
        "artifacts_extracted": 0,
        "schemas_validated": False,
        "output_paths": [],
        "warnings": [],
        "errors": [],
    }


def test_load_known_schema():
    schema = load_schema("run_manifest")
    assert schema["$id"].endswith("run_manifest.schema.json")


def test_valid_run_manifest_passes():
    result = validate(_valid_run_manifest(), "run_manifest")
    assert isinstance(result, ValidationResult)
    assert result.ok, result.errors


def test_bad_mode_fails():
    doc = _valid_run_manifest()
    doc["mode"] = "not_a_mode"
    result = validate(doc, "run_manifest")
    assert not result.ok
    assert any("mode" in e for e in result.errors)


def test_missing_required_field_fails():
    doc = _valid_run_manifest()
    del doc["run_id"]
    result = validate(doc, "run_manifest")
    assert not result.ok


def test_source_event_schema_roundtrip():
    event = {
        "event_id": "evt_0001",
        "event_time": "2026-06-20T18:30:00Z",
        "run_id": "20260620T183000Z-a1b2c3",
        "entity_type": "source",
        "entity_id": "src_0123456789abcdef",
        "event_type": "discovered",
        "payload": {"url": "https://example.com", "source_class": "ir"},
    }
    assert validate(event, "source_registry").ok
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_schema.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'cdd.schema'`

- [ ] **Step 3a: Write `company-due-diligence/schemas/run_manifest.schema.json`**

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://cdd.local/schemas/run_manifest.schema.json",
  "title": "RunManifest",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "run_id", "company_id", "company_name", "started_at", "completed_at",
    "mode", "input_parameters", "reproducibility", "sources_discovered",
    "sources_retrieved", "sources_new", "sources_changed", "sources_unavailable",
    "artifacts_extracted", "schemas_validated", "output_paths", "warnings", "errors"
  ],
  "properties": {
    "run_id": {"type": "string", "pattern": "^[0-9]{8}T[0-9]{6}Z-[0-9a-z]{4,12}$"},
    "company_id": {"type": "string", "minLength": 1},
    "company_name": {"type": "string", "minLength": 1},
    "started_at": {"type": "string", "format": "date-time"},
    "completed_at": {"type": ["string", "null"], "format": "date-time"},
    "mode": {
      "type": "string",
      "enum": [
        "full_refresh", "incremental_refresh", "source_discovery_only",
        "source_retrieval_only", "extraction_only", "validation_only",
        "dossier_only", "compare_runs"
      ]
    },
    "input_parameters": {"type": "object"},
    "reproducibility": {
      "type": "object",
      "additionalProperties": false,
      "required": ["prompt_set_hash", "schema_set_hash", "model_id",
                   "tool_versions", "normalizer_profile_versions", "locale"],
      "properties": {
        "prompt_set_hash": {"type": ["string", "null"]},
        "schema_set_hash": {"type": ["string", "null"]},
        "model_id": {"type": ["string", "null"]},
        "tool_versions": {"type": "object"},
        "normalizer_profile_versions": {"type": "object"},
        "locale": {"type": ["string", "null"]}
      }
    },
    "sources_discovered": {"type": "integer", "minimum": 0},
    "sources_retrieved": {"type": "integer", "minimum": 0},
    "sources_new": {"type": "integer", "minimum": 0},
    "sources_changed": {"type": "integer", "minimum": 0},
    "sources_unavailable": {"type": "integer", "minimum": 0},
    "artifacts_extracted": {"type": "integer", "minimum": 0},
    "schemas_validated": {"type": "boolean"},
    "output_paths": {"type": "array", "items": {"type": "string"}},
    "warnings": {"type": "array", "items": {"type": "string"}},
    "errors": {"type": "array", "items": {"type": "string"}}
  }
}
```

- [ ] **Step 3b: Write `company-due-diligence/schemas/source_registry.schema.json`**

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://cdd.local/schemas/source_registry.schema.json",
  "title": "SourceRegistryEvent",
  "type": "object",
  "additionalProperties": false,
  "required": ["event_id", "event_time", "run_id", "entity_type", "entity_id", "event_type", "payload"],
  "properties": {
    "event_id": {"type": "string", "minLength": 1},
    "event_time": {"type": "string", "format": "date-time"},
    "run_id": {"type": "string", "minLength": 1},
    "entity_type": {"type": "string", "const": "source"},
    "entity_id": {"type": "string", "pattern": "^src_[0-9a-f]{16}$"},
    "event_type": {
      "type": "string",
      "enum": ["discovered", "retrieved", "canonicalized", "unavailable", "superseded", "validated"]
    },
    "payload": {"type": "object"}
  }
}
```

- [ ] **Step 3c: Write `company-due-diligence/schemas/artifact_registry.schema.json`**

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://cdd.local/schemas/artifact_registry.schema.json",
  "title": "ArtifactRegistryEvent",
  "type": "object",
  "additionalProperties": false,
  "required": ["event_id", "event_time", "run_id", "entity_type", "entity_id", "event_type", "payload"],
  "properties": {
    "event_id": {"type": "string", "minLength": 1},
    "event_time": {"type": "string", "format": "date-time"},
    "run_id": {"type": "string", "minLength": 1},
    "entity_type": {"type": "string", "const": "artifact"},
    "entity_id": {"type": "string", "pattern": "^art_[0-9a-f]{16}$"},
    "event_type": {
      "type": "string",
      "enum": ["extracted", "validated", "superseded", "unavailable"]
    },
    "payload": {"type": "object"}
  }
}
```

- [ ] **Step 3d: Write `company-due-diligence/cdd/schema.py`**

```python
"""Schema loading + validation with optional jsonschema backend.

If jsonschema is installed, full validation runs. Otherwise a structural
fallback checks required keys and enum membership only, and `degraded` is
set so callers (and validate_outputs in Plan 2) can refuse to pass when
full validation is mandatory.
"""

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

_SCHEMA_DIR = Path(__file__).resolve().parent.parent / "schemas"


@dataclass
class ValidationResult:
    ok: bool
    errors: list[str] = field(default_factory=list)
    degraded: bool = False


@lru_cache(maxsize=None)
def load_schema(name: str) -> dict:
    path = _SCHEMA_DIR / f"{name}.schema.json"
    if not path.exists():
        raise FileNotFoundError(f"no schema named {name!r} at {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _structural_check(doc: object, schema: dict) -> list[str]:
    errors: list[str] = []
    if schema.get("type") == "object":
        if not isinstance(doc, dict):
            return [f"expected object, got {type(doc).__name__}"]
        for key in schema.get("required", []):
            if key not in doc:
                errors.append(f"missing required field: {key}")
        for key, subschema in schema.get("properties", {}).items():
            if key in doc and isinstance(subschema, dict) and "enum" in subschema:
                if doc[key] not in subschema["enum"]:
                    errors.append(f"{key}: {doc[key]!r} not in enum")
            if key in doc and isinstance(subschema, dict) and subschema.get("const") is not None:
                if doc[key] != subschema["const"]:
                    errors.append(f"{key}: {doc[key]!r} != const {subschema['const']!r}")
    return errors


def validate(doc: object, name: str) -> ValidationResult:
    schema = load_schema(name)
    try:
        import jsonschema  # type: ignore
    except ImportError:
        errors = _structural_check(doc, schema)
        return ValidationResult(ok=not errors, errors=errors, degraded=True)

    validator = jsonschema.Draft202012Validator(schema)
    errors = [f"{'/'.join(str(p) for p in e.path) or '<root>'}: {e.message}"
              for e in validator.iter_errors(doc)]
    return ValidationResult(ok=not errors, errors=errors, degraded=False)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_schema.py -v`
Expected: PASS (5 passed). (With `jsonschema` from the `dev` extra installed, validation is full, not degraded.)

- [ ] **Step 5: Commit**

```bash
git add company-due-diligence/schemas/run_manifest.schema.json company-due-diligence/schemas/source_registry.schema.json company-due-diligence/schemas/artifact_registry.schema.json company-due-diligence/cdd/schema.py company-due-diligence/tests/test_schema.py
git commit -m "feat: add core JSON schemas and optional-jsonschema validator"
```

---

### Task 5: Run lifecycle (`cdd/runlifecycle.py`)

**Files:**
- Create: `company-due-diligence/cdd/runlifecycle.py`
- Test: `company-due-diligence/tests/test_runlifecycle.py`

- [ ] **Step 1: Write the failing test**

```python
import json
from datetime import datetime, timezone
from pathlib import Path

from cdd.paths import OutputPaths, RUN_SUBDIRS
from cdd.runlifecycle import create_run
from cdd.schema import validate


def test_create_run_builds_tree_and_valid_manifest(tmp_path: Path, fixed_now: datetime):
    paths = create_run(
        root=tmp_path,
        company_name="Acme Corp.",
        mode="full_refresh",
        now=fixed_now,
        token="a1b2c3",
        input_parameters={"company_name": "Acme Corp."},
    )
    assert isinstance(paths, OutputPaths)
    assert paths.company_slug == "acme-corp"
    assert paths.run_dir.is_dir()
    for sub in RUN_SUBDIRS:
        assert paths.run_subdir(sub).is_dir()

    manifest_path = paths.run_dir / "run_manifest.json"
    assert manifest_path.is_file()
    manifest = json.loads(manifest_path.read_text())
    assert manifest["run_id"] == "20260620T183000Z-a1b2c3"
    assert manifest["company_id"] == "acme-corp"
    assert manifest["mode"] == "full_refresh"
    assert manifest["completed_at"] is None
    assert validate(manifest, "run_manifest").ok


def test_create_run_is_idempotent_for_existing_run(tmp_path: Path, fixed_now: datetime):
    import pytest

    create_run(root=tmp_path, company_name="Acme", mode="full_refresh",
               now=fixed_now, token="a1b2c3", input_parameters={})
    with pytest.raises(FileExistsError):
        create_run(root=tmp_path, company_name="Acme", mode="full_refresh",
                   now=fixed_now, token="a1b2c3", input_parameters={})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_runlifecycle.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'cdd.runlifecycle'`

- [ ] **Step 3: Write minimal implementation**

`company-due-diligence/cdd/runlifecycle.py`:
```python
"""Create a new run: folder tree + seeded run_manifest.json."""

import json
from datetime import datetime
from pathlib import Path

from cdd.ids import make_run_id, normalize_company_id
from cdd.paths import RUN_SUBDIRS, OutputPaths
from cdd.timeutil import iso_utc


def _seed_manifest(run_id: str, company_slug: str, company_name: str,
                   mode: str, now: datetime, input_parameters: dict) -> dict:
    return {
        "run_id": run_id,
        "company_id": company_slug,
        "company_name": company_name,
        "started_at": iso_utc(now),
        "completed_at": None,
        "mode": mode,
        "input_parameters": input_parameters,
        "reproducibility": {
            "prompt_set_hash": None,
            "schema_set_hash": None,
            "model_id": None,
            "tool_versions": {},
            "normalizer_profile_versions": {},
            "locale": None,
        },
        "sources_discovered": 0,
        "sources_retrieved": 0,
        "sources_new": 0,
        "sources_changed": 0,
        "sources_unavailable": 0,
        "artifacts_extracted": 0,
        "schemas_validated": False,
        "output_paths": [],
        "warnings": [],
        "errors": [],
    }


def create_run(*, root: Path, company_name: str, mode: str, now: datetime,
               token: str, input_parameters: dict) -> OutputPaths:
    company_slug = normalize_company_id(company_name)
    run_id = make_run_id(now, token)
    paths = OutputPaths(root=Path(root), company_slug=company_slug, run_id=run_id)

    if paths.run_dir.exists():
        raise FileExistsError(f"run already exists: {paths.run_dir}")

    paths.run_dir.mkdir(parents=True)
    for sub in RUN_SUBDIRS:
        paths.run_subdir(sub).mkdir()
    paths.company_dir.joinpath("runs").mkdir(exist_ok=True)

    manifest = _seed_manifest(run_id, company_slug, company_name, mode, now, input_parameters)
    (paths.run_dir / "run_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return paths
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_runlifecycle.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add company-due-diligence/cdd/runlifecycle.py company-due-diligence/tests/test_runlifecycle.py
git commit -m "feat: add run lifecycle (folder tree + seeded manifest)"
```

---

### Task 6: Canonicalization profiles (`cdd/canonicalize.py`)

**Files:**
- Create: `company-due-diligence/cdd/canonicalize.py`
- Test: `company-due-diligence/tests/test_canonicalize.py`

- [ ] **Step 1: Write the failing test**

```python
from cdd.canonicalize import canonicalize, PROFILE_VERSIONS


def test_html_strips_scripts_and_normalizes_whitespace():
    a = canonicalize(b"<html><body><script>x=1</script>Hello   World</body></html>", "text/html")
    b = canonicalize(b"<html><body>Hello World<!-- ad --></body></html>", "text/html")
    assert a.text == b.text == "Hello World"
    assert a.profile_id == "html"
    assert a.profile_version == PROFILE_VERSIONS["html"]


def test_json_sorts_keys_and_drops_volatile():
    a = canonicalize(b'{"b":1,"a":2,"timestamp":"now","requestId":"x"}', "application/json")
    b = canonicalize(b'{"a":2,"b":1,"timestamp":"later","requestId":"y"}', "application/json")
    assert a.text == b.text


def test_text_dehyphenates_and_strips_page_numbers():
    raw = b"This is a hy-\nphenated word.\n\f\n12\n"
    out = canonicalize(raw, "text/plain")
    assert "hyphenated word" in out.text
    assert "\n12\n" not in out.text


def test_unknown_mime_falls_back_to_text():
    out = canonicalize(b"  spaced   out  ", "application/octet-stream")
    assert out.text == "spaced out"
    assert out.profile_id == "text"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_canonicalize.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'cdd.canonicalize'`

- [ ] **Step 3: Write minimal implementation**

`company-due-diligence/cdd/canonicalize.py`:
```python
"""Versioned, MIME-aware canonicalization for stable change detection.

stdlib-only. HTML is reduced to visible text via a tag-stripping parser
(good enough for hashing; semantic extraction is the agent's job).
"""

import json
import re
import unicodedata
from dataclasses import dataclass
from html.parser import HTMLParser

PROFILE_VERSIONS = {"html": "1", "json": "1", "text": "1"}
_VOLATILE_JSON_KEYS = {"timestamp", "requestid", "csrf", "session", "nonce", "_ts"}


@dataclass(frozen=True)
class Canonical:
    text: str
    profile_id: str
    profile_version: str


def _norm_ws(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    return re.sub(r"\s+", " ", text).strip()


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: object) -> None:
        if tag in ("script", "style"):
            self._skip += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style") and self._skip:
            self._skip -= 1

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self.parts.append(data)


def _canon_html(raw: bytes) -> str:
    parser = _TextExtractor()
    parser.feed(raw.decode("utf-8", "replace"))
    return _norm_ws(" ".join(parser.parts))


def _strip_volatile(obj: object) -> object:
    if isinstance(obj, dict):
        return {k: _strip_volatile(v) for k, v in sorted(obj.items())
                if k.lower() not in _VOLATILE_JSON_KEYS}
    if isinstance(obj, list):
        return [_strip_volatile(v) for v in obj]
    return obj


def _canon_json(raw: bytes) -> str:
    data = json.loads(raw.decode("utf-8", "replace"))
    return json.dumps(_strip_volatile(data), sort_keys=True, separators=(",", ":"))


def _canon_text(raw: bytes) -> str:
    text = raw.decode("utf-8", "replace")
    text = re.sub(r"-\n", "", text)            # de-hyphenate across line breaks
    text = re.sub(r"\f", "\n", text)           # form feeds -> newlines
    text = re.sub(r"\n\s*\d+\s*\n", "\n", text)  # bare page-number lines
    return _norm_ws(text)


def canonicalize(raw: bytes, mime: str) -> Canonical:
    mime = (mime or "").split(";")[0].strip().lower()
    if mime in ("text/html", "application/xhtml+xml"):
        return Canonical(_canon_html(raw), "html", PROFILE_VERSIONS["html"])
    if mime in ("application/json", "text/json"):
        return Canonical(_canon_json(raw), "json", PROFILE_VERSIONS["json"])
    return Canonical(_canon_text(raw), "text", PROFILE_VERSIONS["text"])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_canonicalize.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add company-due-diligence/cdd/canonicalize.py company-due-diligence/tests/test_canonicalize.py
git commit -m "feat: add versioned MIME-aware canonicalization"
```

---

### Task 7: Dual hashing + diff_class (`cdd/hashing.py`)

**Files:**
- Create: `company-due-diligence/cdd/hashing.py`
- Test: `company-due-diligence/tests/test_hashing.py`

- [ ] **Step 1: Write the failing test**

```python
from cdd.hashing import hash_content, classify_diff


def test_hash_content_returns_raw_and_canonical():
    h = hash_content(b"<html><body>Hello   World</body></html>", "text/html")
    assert len(h.raw_hash) == 64 and len(h.canonical_hash) == 64
    assert h.profile_id == "html"


def test_canonical_hash_ignores_cosmetic_changes():
    a = hash_content(b"<body>Hello World<script>t=1</script></body>", "text/html")
    b = hash_content(b"<body>Hello   World<!-- x --></body>", "text/html")
    assert a.raw_hash != b.raw_hash
    assert a.canonical_hash == b.canonical_hash


def test_classify_unchanged():
    a = hash_content(b"<body>Hi</body>", "text/html")
    assert classify_diff(a, a) == "unchanged"


def test_classify_cosmetic_change():
    a = hash_content(b"<body>Hi<script>t=1</script></body>", "text/html")
    b = hash_content(b"<body>Hi</body>", "text/html")
    assert classify_diff(a, b) == "cosmetic_change"


def test_classify_content_change():
    a = hash_content(b"<body>Hi</body>", "text/html")
    b = hash_content(b"<body>Bye</body>", "text/html")
    assert classify_diff(a, b) == "content_change"


def test_classify_unavailable_when_new_is_none():
    a = hash_content(b"<body>Hi</body>", "text/html")
    assert classify_diff(a, None) == "unavailable"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_hashing.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'cdd.hashing'`

- [ ] **Step 3: Write minimal implementation**

`company-due-diligence/cdd/hashing.py`:
```python
"""Dual hashing (raw + canonical) and diff classification."""

import hashlib
from dataclasses import dataclass
from typing import Literal, Optional

from cdd.canonicalize import canonicalize

DiffClass = Literal["unchanged", "cosmetic_change", "table_change", "content_change", "unavailable"]


@dataclass(frozen=True)
class ContentHash:
    raw_hash: str
    canonical_hash: str
    profile_id: str
    profile_version: str


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def hash_content(raw: bytes, mime: str) -> ContentHash:
    canon = canonicalize(raw, mime)
    return ContentHash(
        raw_hash=_sha256(raw),
        canonical_hash=_sha256(canon.text.encode("utf-8")),
        profile_id=canon.profile_id,
        profile_version=canon.profile_version,
    )


def classify_diff(old: ContentHash, new: Optional[ContentHash]) -> DiffClass:
    if new is None:
        return "unavailable"
    if old.raw_hash == new.raw_hash:
        return "unchanged"
    if old.canonical_hash == new.canonical_hash:
        return "cosmetic_change"
    return "content_change"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_hashing.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add company-due-diligence/cdd/hashing.py company-due-diligence/tests/test_hashing.py
git commit -m "feat: add dual hashing and diff classification"
```

---

### Task 8: Event-log registry (`cdd/registry.py`)

**Files:**
- Create: `company-due-diligence/cdd/registry.py`
- Test: `company-due-diligence/tests/test_registry.py`

- [ ] **Step 1: Write the failing test**

```python
from datetime import datetime, timezone
from pathlib import Path

from cdd.registry import append_event, read_events, derive_source_state, next_event_id
from cdd.schema import validate


def _evt(eid: str, etype: str, when: datetime, entity_id="src_0123456789abcdef") -> dict:
    return {
        "event_id": eid,
        "event_time": when.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "run_id": "20260620T183000Z-a1",
        "entity_type": "source",
        "entity_id": entity_id,
        "event_type": etype,
        "payload": {},
    }


def test_append_and_read_roundtrip(tmp_path: Path, fixed_now: datetime):
    log = tmp_path / "source_registry.jsonl"
    append_event(log, _evt("evt_1", "discovered", fixed_now), schema_name="source_registry")
    append_event(log, _evt("evt_2", "retrieved", fixed_now), schema_name="source_registry")
    events = read_events(log)
    assert [e["event_id"] for e in events] == ["evt_1", "evt_2"]


def test_append_rejects_invalid_event(tmp_path: Path, fixed_now: datetime):
    import pytest

    log = tmp_path / "source_registry.jsonl"
    bad = _evt("evt_1", "not_a_type", fixed_now)
    with pytest.raises(ValueError):
        append_event(log, bad, schema_name="source_registry")
    assert not log.exists() or log.read_text() == ""


def test_next_event_id_is_sequential(tmp_path: Path, fixed_now: datetime):
    log = tmp_path / "source_registry.jsonl"
    assert next_event_id(log) == "evt_000001"
    append_event(log, _evt("evt_000001", "discovered", fixed_now), schema_name="source_registry")
    assert next_event_id(log) == "evt_000002"


def test_derive_source_state_tracks_first_last_and_status(tmp_path: Path):
    log = tmp_path / "source_registry.jsonl"
    t1 = datetime(2026, 6, 1, 0, 0, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 6, 20, 0, 0, 0, tzinfo=timezone.utc)
    append_event(log, _evt("evt_000001", "discovered", t1), schema_name="source_registry")
    append_event(log, _evt("evt_000002", "retrieved", t2), schema_name="source_registry")
    state = derive_source_state(log)
    s = state["src_0123456789abcdef"]
    assert s["first_seen_at"] == "2026-06-01T00:00:00Z"
    assert s["last_seen_at"] == "2026-06-20T00:00:00Z"
    assert s["status"] == "active"


def test_derive_marks_unavailable_then_reappeared(tmp_path: Path):
    log = tmp_path / "source_registry.jsonl"
    t1 = datetime(2026, 6, 1, tzinfo=timezone.utc)
    t2 = datetime(2026, 6, 10, tzinfo=timezone.utc)
    t3 = datetime(2026, 6, 20, tzinfo=timezone.utc)
    append_event(log, _evt("evt_000001", "retrieved", t1), schema_name="source_registry")
    append_event(log, _evt("evt_000002", "unavailable", t2), schema_name="source_registry")
    append_event(log, _evt("evt_000003", "retrieved", t3), schema_name="source_registry")
    s = derive_source_state(log)["src_0123456789abcdef"]
    assert s["status"] == "reappeared"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_registry.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'cdd.registry'`

- [ ] **Step 3: Write minimal implementation**

`company-due-diligence/cdd/registry.py`:
```python
"""Append-only JSONL event logs + derived current-state views.

The log file is the source of truth and is never mutated in place; state is
always recomputed from the full event stream.
"""

import json
import os
import re
import tempfile
from pathlib import Path

from cdd.schema import validate

_EVENT_NUM = re.compile(r"^evt_(\d+)$")


def read_events(log: Path) -> list[dict]:
    if not Path(log).exists():
        return []
    events: list[dict] = []
    for line in Path(log).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            events.append(json.loads(line))
    return events


def next_event_id(log: Path) -> str:
    highest = 0
    for e in read_events(log):
        m = _EVENT_NUM.match(str(e.get("event_id", "")))
        if m:
            highest = max(highest, int(m.group(1)))
    return f"evt_{highest + 1:06d}"


def append_event(log: Path, event: dict, *, schema_name: str) -> None:
    result = validate(event, schema_name)
    if not result.ok:
        raise ValueError(f"invalid {schema_name} event: {result.errors}")
    log = Path(log)
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, sort_keys=True) + "\n")
        fh.flush()
        os.fsync(fh.fileno())


_ACTIVE = {"discovered", "retrieved", "canonicalized", "extracted", "validated"}


def derive_source_state(log: Path) -> dict[str, dict]:
    state: dict[str, dict] = {}
    for e in read_events(log):
        eid = e["entity_id"]
        when = e["event_time"]
        etype = e["event_type"]
        s = state.setdefault(eid, {
            "entity_id": eid, "first_seen_at": when, "last_seen_at": when,
            "status": "active", "_was_unavailable": False,
        })
        s["first_seen_at"] = min(s["first_seen_at"], when)
        s["last_seen_at"] = max(s["last_seen_at"], when)
        if etype == "unavailable":
            s["status"] = "unavailable"
            s["_was_unavailable"] = True
        elif etype in _ACTIVE:
            s["status"] = "reappeared" if s["_was_unavailable"] else "active"
        elif etype == "superseded":
            s["status"] = "superseded"
    for s in state.values():
        s.pop("_was_unavailable", None)
    return state
```

> Note: `derive_artifact_state` (Plan 2) reuses this shape; the source/artifact event schemas are structurally identical, so `derive_source_state` works for artifact logs too — Plan 2 adds an artifact-specific wrapper only if divergence appears.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_registry.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add company-due-diligence/cdd/registry.py company-due-diligence/tests/test_registry.py
git commit -m "feat: add append-only event-log registry with derived state"
```

---

### Task 9: Derived manifest (`cdd/manifest.py`)

**Files:**
- Create: `company-due-diligence/cdd/manifest.py`
- Test: `company-due-diligence/tests/test_manifest.py`

- [ ] **Step 1: Write the failing test**

```python
import json
from datetime import datetime, timezone
from pathlib import Path

from cdd.manifest import build_manifest
from cdd.paths import OutputPaths


def _seed_source_log(paths: OutputPaths) -> None:
    paths.company_dir.mkdir(parents=True, exist_ok=True)
    events = [
        {"event_id": "evt_000001", "event_time": "2026-06-01T00:00:00Z",
         "run_id": "r1", "entity_type": "source", "entity_id": "src_0000000000000001",
         "event_type": "retrieved", "payload": {}},
        {"event_id": "evt_000002", "event_time": "2026-06-20T00:00:00Z",
         "run_id": "r2", "entity_type": "source", "entity_id": "src_0000000000000002",
         "event_type": "unavailable", "payload": {}},
    ]
    paths.source_registry.write_text(
        "\n".join(json.dumps(e, sort_keys=True) for e in events) + "\n", encoding="utf-8"
    )


def test_build_manifest_writes_atomic_current_state(tmp_path: Path):
    paths = OutputPaths(root=tmp_path, company_slug="acme-corp", run_id="r2")
    _seed_source_log(paths)
    paths.artifact_registry.write_text("", encoding="utf-8")

    out = build_manifest(paths, now=datetime(2026, 6, 20, 18, 30, tzinfo=timezone.utc))
    assert out == paths.manifest
    manifest = json.loads(paths.manifest.read_text())

    assert manifest["company_id"] == "acme-corp"
    assert manifest["generated_at"] == "2026-06-20T18:30:00Z"
    assert manifest["source_count"] == 2
    assert manifest["sources_active"] == 1
    assert manifest["sources_unavailable"] == 1
    assert "src_0000000000000001" in manifest["sources"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_manifest.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'cdd.manifest'`

- [ ] **Step 3: Write minimal implementation**

`company-due-diligence/cdd/manifest.py`:
```python
"""Derive the current-state manifest.json from event logs (atomic write)."""

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path

from cdd.paths import OutputPaths
from cdd.registry import derive_source_state
from cdd.timeutil import iso_utc


def _atomic_write_json(target: Path, data: dict) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(target.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(data, indent=2, sort_keys=True) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, target)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def build_manifest(paths: OutputPaths, *, now: datetime) -> Path:
    sources = derive_source_state(paths.source_registry)
    active = sum(1 for s in sources.values() if s["status"] in ("active", "reappeared"))
    unavailable = sum(1 for s in sources.values() if s["status"] == "unavailable")
    manifest = {
        "company_id": paths.company_slug,
        "generated_at": iso_utc(now),
        "source_count": len(sources),
        "sources_active": active,
        "sources_unavailable": unavailable,
        "sources": sources,
    }
    _atomic_write_json(paths.manifest, manifest)
    return paths.manifest
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_manifest.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add company-due-diligence/cdd/manifest.py company-due-diligence/tests/test_manifest.py
git commit -m "feat: derive current-state manifest from event logs"
```

---

### Task 10: CLI wrappers (`scripts/*.py`)

**Files:**
- Create: `company-due-diligence/scripts/normalize_company_id.py`
- Create: `company-due-diligence/scripts/create_run.py`
- Create: `company-due-diligence/scripts/compute_hashes.py`
- Create: `company-due-diligence/scripts/update_source_registry.py`
- Create: `company-due-diligence/scripts/update_artifact_registry.py`
- Create: `company-due-diligence/scripts/build_manifest.py`
- Test: `company-due-diligence/tests/test_cli.py`

- [ ] **Step 1: Write the failing test**

```python
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # company-due-diligence/


def _run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, *args], cwd=ROOT, capture_output=True, text=True
    )


def test_normalize_company_id_cli():
    r = _run(["scripts/normalize_company_id.py", "--company", "Acme Corp."])
    assert r.returncode == 0
    assert r.stdout.strip() == "acme-corp"


def test_create_run_cli_builds_tree(tmp_path: Path):
    r = _run(["scripts/create_run.py", "--company", "Acme Corp.",
              "--mode", "full_refresh", "--root", str(tmp_path), "--token", "a1b2c3"])
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    manifest = Path(out["run_manifest"])
    assert manifest.is_file()
    assert json.loads(manifest.read_text())["company_id"] == "acme-corp"


def test_compute_hashes_cli(tmp_path: Path):
    f = tmp_path / "page.html"
    f.write_bytes(b"<body>Hello   World<script>t=1</script></body>")
    r = _run(["scripts/compute_hashes.py", "--file", str(f), "--mime", "text/html"])
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert len(out["raw_hash"]) == 64
    assert out["profile_id"] == "html"


def test_update_source_registry_cli(tmp_path: Path):
    log = tmp_path / "source_registry.jsonl"
    r = _run(["scripts/update_source_registry.py", "--log", str(log),
              "--run-id", "20260620T183000Z-a1", "--source-id", "src_0123456789abcdef",
              "--event-type", "discovered", "--event-time", "2026-06-20T18:30:00Z",
              "--payload", '{"url":"https://example.com","source_class":"ir"}'])
    assert r.returncode == 0, r.stderr
    lines = log.read_text().strip().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["event_id"] == "evt_000001"


def test_build_manifest_cli(tmp_path: Path):
    company = tmp_path / "companies" / "acme-corp"
    company.mkdir(parents=True)
    (company / "source_registry.jsonl").write_text(
        json.dumps({"event_id": "evt_000001", "event_time": "2026-06-20T18:30:00Z",
                    "run_id": "r1", "entity_type": "source",
                    "entity_id": "src_0000000000000001", "event_type": "retrieved",
                    "payload": {}}, sort_keys=True) + "\n", encoding="utf-8")
    r = _run(["scripts/build_manifest.py", "--root", str(tmp_path),
              "--company-id", "acme-corp", "--now", "2026-06-20T18:30:00Z"])
    assert r.returncode == 0, r.stderr
    manifest = json.loads((company / "manifest.json").read_text())
    assert manifest["source_count"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli.py -v`
Expected: FAIL — scripts do not exist yet (non-zero return codes / `can't open file`).

- [ ] **Step 3a: Write `company-due-diligence/scripts/normalize_company_id.py`**

```python
#!/usr/bin/env python3
"""CLI: print the normalized company slug."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cdd.ids import normalize_company_id


def main() -> int:
    parser = argparse.ArgumentParser(description="Normalize a company name to a slug.")
    parser.add_argument("--company", required=True)
    args = parser.parse_args()
    print(normalize_company_id(args.company))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 3b: Write `company-due-diligence/scripts/create_run.py`**

```python
#!/usr/bin/env python3
"""CLI: create a new run (folders + seeded run_manifest.json)."""

import argparse
import json
import secrets
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cdd.runlifecycle import create_run

_MODES = [
    "full_refresh", "incremental_refresh", "source_discovery_only",
    "source_retrieval_only", "extraction_only", "validation_only",
    "dossier_only", "compare_runs",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a due-diligence run.")
    parser.add_argument("--company", required=True)
    parser.add_argument("--mode", required=True, choices=_MODES)
    parser.add_argument("--root", default="output")
    parser.add_argument("--token", default=None, help="4-12 lowercase alnum; random if omitted")
    args = parser.parse_args()

    token = args.token or secrets.token_hex(3)
    paths = create_run(
        root=Path(args.root), company_name=args.company, mode=args.mode,
        now=datetime.now(timezone.utc), token=token,
        input_parameters={"company_name": args.company, "mode": args.mode},
    )
    print(json.dumps({
        "company_slug": paths.company_slug,
        "run_id": paths.run_id,
        "run_dir": str(paths.run_dir),
        "run_manifest": str(paths.run_dir / "run_manifest.json"),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 3c: Write `company-due-diligence/scripts/compute_hashes.py`**

```python
#!/usr/bin/env python3
"""CLI: compute raw + canonical hashes for a file."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cdd.hashing import hash_content


def main() -> int:
    parser = argparse.ArgumentParser(description="Compute dual content hashes.")
    parser.add_argument("--file", required=True)
    parser.add_argument("--mime", required=True)
    args = parser.parse_args()

    raw = Path(args.file).read_bytes()
    h = hash_content(raw, args.mime)
    print(json.dumps({
        "raw_hash": h.raw_hash,
        "canonical_hash": h.canonical_hash,
        "profile_id": h.profile_id,
        "profile_version": h.profile_version,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 3d: Write `company-due-diligence/scripts/update_source_registry.py`**

```python
#!/usr/bin/env python3
"""CLI: append a source event to a source_registry.jsonl log."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cdd.registry import append_event, next_event_id


def main() -> int:
    parser = argparse.ArgumentParser(description="Append a source registry event.")
    parser.add_argument("--log", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--event-type", required=True,
                        choices=["discovered", "retrieved", "canonicalized",
                                 "unavailable", "superseded", "validated"])
    parser.add_argument("--event-time", required=True)
    parser.add_argument("--payload", default="{}")
    args = parser.parse_args()

    log = Path(args.log)
    event = {
        "event_id": next_event_id(log),
        "event_time": args.event_time,
        "run_id": args.run_id,
        "entity_type": "source",
        "entity_id": args.source_id,
        "event_type": args.event_type,
        "payload": json.loads(args.payload),
    }
    append_event(log, event, schema_name="source_registry")
    print(event["event_id"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 3e: Write `company-due-diligence/scripts/update_artifact_registry.py`**

```python
#!/usr/bin/env python3
"""CLI: append an artifact event to an artifact_registry.jsonl log."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cdd.registry import append_event, next_event_id


def main() -> int:
    parser = argparse.ArgumentParser(description="Append an artifact registry event.")
    parser.add_argument("--log", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--artifact-id", required=True)
    parser.add_argument("--event-type", required=True,
                        choices=["extracted", "validated", "superseded", "unavailable"])
    parser.add_argument("--event-time", required=True)
    parser.add_argument("--payload", default="{}")
    args = parser.parse_args()

    log = Path(args.log)
    event = {
        "event_id": next_event_id(log),
        "event_time": args.event_time,
        "run_id": args.run_id,
        "entity_type": "artifact",
        "entity_id": args.artifact_id,
        "event_type": args.event_type,
        "payload": json.loads(args.payload),
    }
    append_event(log, event, schema_name="artifact_registry")
    print(event["event_id"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 3f: Write `company-due-diligence/scripts/build_manifest.py`**

```python
#!/usr/bin/env python3
"""CLI: derive current-state manifest.json from event logs."""

import argparse
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cdd.manifest import build_manifest
from cdd.paths import OutputPaths


def main() -> int:
    parser = argparse.ArgumentParser(description="Build derived company manifest.")
    parser.add_argument("--root", default="output")
    parser.add_argument("--company-id", required=True)
    parser.add_argument("--now", required=True, help="ISO8601 UTC, e.g. 2026-06-20T18:30:00Z")
    args = parser.parse_args()

    now = datetime.strptime(args.now, "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=__import__("datetime").timezone.utc
    )
    paths = OutputPaths(root=Path(args.root), company_slug=args.company_id, run_id="_manifest")
    out = build_manifest(paths, now=now)
    print(str(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add company-due-diligence/scripts/ company-due-diligence/tests/test_cli.py
git commit -m "feat: add CLI wrappers for identity, run, hashing, registry, manifest"
```

---

### Task 11: Quality gates — full suite, coverage, lint, types

**Files:** none new (verification task)

- [ ] **Step 1: Run the full test suite with coverage**

Run (from `company-due-diligence/`): `uv run pytest --cov=cdd --cov-report=term-missing`
Expected: all tests PASS; `cdd` coverage ≥ 80% (the library modules are exercised directly by their unit tests).

- [ ] **Step 2: Run ruff**

Run: `uv run ruff check .`
Expected: no errors. Fix any reported issues, then re-run until clean.

- [ ] **Step 3: Run pyright**

Run: `uv run pyright`
Expected: 0 errors. Add/adjust type hints if pyright reports issues (note: `scripts/build_manifest.py` uses `timezone` via import inside `main` to keep the wrapper minimal — if pyright flags it, replace with a top-level `from datetime import timezone` import).

- [ ] **Step 4: Smoke-test the end-to-end deterministic flow**

Run:
```bash
uv run python scripts/create_run.py --company "Acme Corp." --mode full_refresh --root /tmp/cdd-smoke --token a1b2c3
uv run python scripts/update_source_registry.py --log /tmp/cdd-smoke/companies/acme-corp/source_registry.jsonl --run-id 20260620T183000Z-a1b2c3 --source-id src_0123456789abcdef --event-type discovered --event-time 2026-06-20T18:30:00Z --payload '{"url":"https://example.com","source_class":"ir"}'
uv run python scripts/build_manifest.py --root /tmp/cdd-smoke --company-id acme-corp --now 2026-06-20T18:30:00Z
cat /tmp/cdd-smoke/companies/acme-corp/manifest.json
```
Expected: manifest prints with `"source_count": 1` and the source under `"sources"`.

- [ ] **Step 5: Commit (if any lint/type fixes were made)**

```bash
git add company-due-diligence/
git commit -m "chore: satisfy ruff, pyright, and coverage gates for foundations"
```

---

## Self-Review

**1. Spec coverage (this plan's scope = spec §2–§6, §8–§9 foundations):**
- §2 hybrid/packaging/deps → Task 0 (`pyproject.toml` core + extras), CLIs are stdlib-only with `jsonschema` optional. ✓
- §3 identity & versioning (company_slug, logical source_id, run_id, reproducibility pins) → Tasks 2, 4 (manifest `reproducibility` block), 5. ✓
- §4 dual hashing + canonicalization + diff_class → Tasks 6, 7. ✓ (sub-artifact lineage fields land with the artifact schemas in Plan 2.)
- §5 append-only event logs + derived views → Tasks 8, 9. ✓
- §6 output layout + atomic writes → Tasks 3, 5, 9 (atomic write in `build_manifest`; full `latest/` gating is Plan 2 with `validate_outputs`). ✓
- §9 scripts: this plan delivers 6 of 13 (`normalize_company_id, create_run, compute_hashes, update_source_registry, update_artifact_registry, build_manifest`). Remaining 7 (`compare_runs, generate_change_log, validate_outputs, merge_artifacts, export_jsonl, export_csv, export_markdown`) are explicitly deferred to Plan 2. ✓ (documented gap, not silent.)
- §7 dossier, §10 evidentiary validation, §11 anti-hallucination, §12 dossier sections, §13 prompts/references → Plans 2–3. Out of scope here by design.

**2. Placeholder scan:** No TBD/TODO; every code step has complete, runnable code. ✓

**3. Type consistency:** `OutputPaths`, `ContentHash`, `Canonical`, `ValidationResult`, `DiffClass` used consistently across tasks. `append_event(log, event, *, schema_name=...)`, `next_event_id(log)`, `derive_source_state(log)`, `build_manifest(paths, *, now=...)`, `hash_content(raw, mime)`, `classify_diff(old, new)`, `create_run(*, root, company_name, mode, now, token, input_parameters)`, `normalize_company_id(name)`, `make_run_id(now, token)`, `source_id_for(url, source_class)` — signatures match between definition tasks and their callers (CLIs, manifest). ✓

---

## Follow-on Plans (not in this document)
- **Plan 2 — Analysis & Validation:** remaining 6 schemas; `compare_runs` (diff_class + source/extraction/schema delta classification); `generate_change_log`; `validate_outputs` (evidentiary gates, §10); `merge_artifacts` (+`conflict_set`); `export_jsonl/csv/markdown` (safe-export modes); `latest/` publish gating + per-company lock.
- **Plan 3 — Agent Skill Layer:** `SKILL.md`, `prompts/*` (13), `references/*` (6 + legal/provenance), `examples/*`, optional extraction tools (EDGAR/PDF/HTML), `README.md`, symlink/install into `~/.claude/skills/`.
