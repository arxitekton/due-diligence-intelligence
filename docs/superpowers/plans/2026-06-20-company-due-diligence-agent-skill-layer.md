# Company Due Diligence — Plan 3: Agent Skill Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the Plan 1+2 engine into an activatable Claude Code skill: `SKILL.md` (progressive disclosure), the 13 orchestration prompts, the 8 references, runnable examples, optional Python extraction tools (EDGAR/PDF/HTML), a `README`, and an install path into `~/.claude/skills/`.

**Architecture:** The skill is agent-driven (Claude does discovery/retrieval/extraction guided by `prompts/*.md`); the Plan 1+2 `cdd` engine + CLIs do all deterministic bookkeeping. Extraction tools are *optional* (`extract` extra) Python helpers the agent may call for reliability on PDFs/EDGAR/HTML; everything degrades gracefully when they're absent. Content files (SKILL/prompts/references) are the deliverables — their "code" is their prose; correctness is enforced by a skill-integrity test plus per-file required-section acceptance criteria.

**Tech Stack:** Markdown + YAML frontmatter; Python 3.12 for extraction tools (`trafilatura`/`beautifulsoup4`/`lxml`, `pdfplumber`/`pymupdf`, `edgartools`, `httpx`), all under the `extract` optional-dependency group.

**Prereq:** Plans 1 & 2 merged. Branch `feature/company-due-diligence-skill-layer` off updated `main`.

**Spec:** implements §1 (purpose/activation), §2 (hybrid extraction tools), §11 (source priority + anti-hallucination as references), §12 (dossier rendering), §13 (prompts/references/examples/SKILL/README).

---

## File Structure

```
company-due-diligence/
  SKILL.md                                   # NEW (keystone, ~120 lines)
  README.md                                  # NEW
  prompts/
    research_orchestrator.md  source_discovery.md  source_retrieval.md
    evidence_extraction.md  product_extraction.md  financial_extraction.md
    corporate_structure_extraction.md  market_intelligence.md  risk_extraction.md
    event_extraction.md  evidence_validation.md  dossier_generation.md
    run_comparison.md                                                   # 13 files
  references/
    research_methodology.md  source_priority_rules.md  data_quality_rules.md
    anti_hallucination_rules.md  financial_extraction_rules.md
    product_extraction_rules.md  legal_and_tos.md  provenance_and_reproducibility.md  # 8 files
  examples/
    example_input.md  example_run_manifest.json  example_source_registry.jsonl
    example_artifact_registry.jsonl  example_output_structure.md          # 5 files
  cdd/extract/
    __init__.py        # graceful capability detection
    html_clean.py      # trafilatura/bs4 → main text + tables (optional deps)
    pdf_tables.py      # pdfplumber/pymupdf → text + tables (optional deps)
    edgar.py           # edgartools → filings list/fetch (optional deps)
    fetch.py           # httpx GET → bytes + retrieval metadata (optional deps)
  scripts/
    install_skill.py   # symlink company-due-diligence/ into ~/.claude/skills/
  tests/
    test_skill_integrity.py
    test_extract_html.py
    test_extract_pdf.py
    test_extract_capability.py
    test_install_skill.py
```

**Per-task gates:** `uv run pytest <file>`, `ruff`, `pyright` (extraction tools may need `# type: ignore[import-untyped]` on optional libs and `validator: Any`-style localization like Plan 1's schema.py).

---

### Task 1: SKILL.md (keystone) + integrity test

**Files:** Create `SKILL.md`; Test `tests/test_skill_integrity.py`.

- [ ] **Step 1: Write failing test** → `tests/test_skill_integrity.py`

```python
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "SKILL.md"


def _frontmatter(text: str) -> dict[str, str]:
    m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    assert m, "SKILL.md must start with YAML frontmatter"
    fm: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip()
    return fm


def test_skill_has_name_and_description():
    fm = _frontmatter(SKILL.read_text())
    assert fm.get("name") == "company-due-diligence"
    assert 20 <= len(fm.get("description", "")) <= 1024


def test_skill_links_resolve():
    text = SKILL.read_text()
    for rel in re.findall(r"\]\((prompts/[^)]+|references/[^)]+)\)", text):
        assert (ROOT / rel).exists(), f"SKILL.md links missing file: {rel}"


def test_skill_is_concise():
    assert len(SKILL.read_text().splitlines()) <= 200, "SKILL.md should stay concise"
```

- [ ] **Step 2: Run → FAIL** (SKILL.md missing). *(Links test will fail until Tasks 2–3 land; mark it xfail-free by ordering — see note.)*

> Ordering note: `test_skill_links_resolve` requires prompts/references to exist. Implement Task 1's SKILL.md to link them, but run the **full** integrity suite only at the end of Task 3. For Task 1, run just `test_skill_has_name_and_description` and `test_skill_is_concise`.

- [ ] **Step 3: Write `SKILL.md`** (full content):

```markdown
---
name: company-due-diligence
description: Exhaustive, refreshable, versioned company due-diligence and market-intelligence research. Use when asked to research/profile a company, build a due-diligence dossier, track what changed since a prior run, or extract a company's products, financials, corporate structure, competitors, risks, or recent developments from primary sources. Triggers on "due diligence", "company profile/dossier", "market intelligence", "research <company>", or refresh/compare requests.
---

# Company Due Diligence

A research **corpus** system, not a one-shot report. Discover → preserve evidence → extract artifacts → structure → validate → generate dossier. Every run is versioned and reproducible; re-runs detect and record what changed.

## When to activate
Activate when the user asks to research/profile/do due-diligence on a company, refresh an existing dossier, or compare runs. Inputs: company name (required); optional website, country, industry, ticker/exchange, legal name, subsidiaries/brands, research focus, run mode.

## Run modes
`full_refresh` · `incremental_refresh` · `source_discovery_only` · `source_retrieval_only` · `extraction_only` · `validation_only` · `dossier_only` · `compare_runs`.

## Workflow
1. **Create run** — `python scripts/create_run.py --company "<NAME>" --mode <MODE>`. Note the `run_id` + `company_slug`.
2. **Discover** — follow `prompts/source_discovery.md`; prioritize sources per `references/source_priority_rules.md`. Record each as a registry event (`scripts/update_source_registry.py`).
3. **Retrieve & preserve** — save raw bytes to `runs/{run_id}/raw_sources/`; hash with `scripts/compute_hashes.py` (raw + canonical → `diff_class`). Respect `references/legal_and_tos.md`.
4. **Extract** — per `prompts/{evidence,product,financial,corporate_structure,risk,event}_extraction.md`; preserve source-native tables/taxonomies/line-items FIRST. Write structured artifacts (with full lineage) to `runs/{run_id}/structured/`; record `scripts/update_artifact_registry.py`.
5. **Validate** — `python scripts/validate_outputs.py --company-id <slug> --run-id <id> --mode <MODE> --now <T>` (evidentiary gates). Fix or flag before publishing.
6. **Compare (re-runs)** — `scripts/compare_runs.py` + `scripts/generate_change_log.py`.
7. **Dossier** — follow `prompts/dossier_generation.md`; render `final_dossier.{md,json}` from CURRENT validated artifacts only. Publish to `latest/` only after validation passes.

## Hard rules
- **Never invent data.** Missing → `null`/`unknown`. See `references/anti_hallucination_rules.md`.
- **Cite everything.** Every dossier claim cites `artifact_id`(+locator) or is tagged `[INFERENCE]`. Separate facts / extracted evidence / analysis.
- **Preserve originals before normalizing** — raw tables, native product taxonomies, native financial line items.
- **Never resolve conflicts silently** — emit a `conflict_set`.
- **Never overwrite prior runs.** Only `latest/`, registries, indexes, manifests update.
- **Scripts never hit the network**; the agent (you) does retrieval. Optional extraction tools under the `extract` extra add reliability for PDFs/EDGAR/HTML.

## Detailed guidance
Prompts: [orchestrator](prompts/research_orchestrator.md) · [discovery](prompts/source_discovery.md) · [retrieval](prompts/source_retrieval.md) · [evidence](prompts/evidence_extraction.md) · [product](prompts/product_extraction.md) · [financial](prompts/financial_extraction.md) · [corporate structure](prompts/corporate_structure_extraction.md) · [market intel](prompts/market_intelligence.md) · [risk](prompts/risk_extraction.md) · [events](prompts/event_extraction.md) · [validation](prompts/evidence_validation.md) · [dossier](prompts/dossier_generation.md) · [run comparison](prompts/run_comparison.md).
References: [methodology](references/research_methodology.md) · [source priority](references/source_priority_rules.md) · [data quality](references/data_quality_rules.md) · [anti-hallucination](references/anti_hallucination_rules.md) · [financial rules](references/financial_extraction_rules.md) · [product rules](references/product_extraction_rules.md) · [legal/ToS](references/legal_and_tos.md) · [provenance](references/provenance_and_reproducibility.md).
```

- [ ] **Step 4: Run** `uv run pytest tests/test_skill_integrity.py::test_skill_has_name_and_description tests/test_skill_integrity.py::test_skill_is_concise -v` → 2 passed.
- [ ] **Step 5: Commit** `git commit -m "feat: add SKILL.md keystone + integrity test"`.

---

### Task 2: References (8 files)

**Files:** Create the 8 `references/*.md`. (No new test; the link/integrity test in Task 1 covers existence; content acceptance below.)

Each reference must contain the listed sections. Author concise, authoritative prose (the user is an expert; no filler).

- [ ] **`source_priority_rules.md`** — the three tiers verbatim from spec §11 (Primary/Secondary/Signal lists), plus a rule table: for each `source_class`, its `source_priority`, typical `original_format`, and trust notes (`issuer_affiliated`, `regulatory_status`).
- [ ] **`research_methodology.md`** — the discover→preserve→extract→structure→validate→dossier loop; CRISP-DM phase mapping; when to use each run mode; rediscovery cadence per source class; forced `full_refresh` checkpoints.
- [ ] **`anti_hallucination_rules.md`** — null/unknown policy; fact vs evidence vs inference separation; the citation rule; "do not infer ownership/revenue/customers/financials without explicit evidence"; conflict-preservation (never silently resolve).
- [ ] **`data_quality_rules.md`** — the §10 gate checklist in prose (what fails a run vs what's flagged), confidence scoring guidance, staleness thresholds, missing-source-class expectations by industry.
- [ ] **`financial_extraction_rules.md`** — preserve native line items/periods/currency/units/scope/footnotes/page-refs FIRST; the `financial_artifact` field contract; normalization-as-derived-layer rules; restatement & GAAP/non-GAAP handling; the `conflict_set` reason codes.
- [ ] **`product_extraction_rules.md`** — preserve native product families/suites/modules/tiers/editions/APIs/pricing FIRST; the `product_artifact` field contract; lifecycle/geography handling.
- [ ] **`legal_and_tos.md`** — per-source `access_basis`, `license_or_terms_ref`, `robots_observed`, `retention_policy`, `export_restrictions`; PII/`sensitivity_class` handling; safe-export modes; "respect site ToS/robots; do not bypass paywalls or access controls."
- [ ] **`provenance_and_reproducibility.md`** — what the `run_manifest.reproducibility` block pins (prompt-set hash, model id, tool versions, normalizer profile versions, queries, locale); how `compare_runs` separates source/extraction/schema deltas; how to reproduce a run.

- [ ] **Commit** `git commit -m "docs: add 8 reference guides"`.

---

### Task 3: Prompts (13 files) + full integrity run

**Files:** Create the 13 `prompts/*.md`.

**Template (apply to every prompt):** each prompt file has `## Goal`, `## Inputs` (what context the agent has), `## Procedure` (numbered steps invoking the right `scripts/*.py` and writing to the right run subdirs), `## Output contract` (which schema the produced artifact must satisfy + required lineage), `## Hard rules` (link the relevant reference), `## Hand-off` (what the next prompt consumes).

- [ ] **`source_discovery.md`** (full worked example — use as the template for the rest):

```markdown
# Source Discovery

## Goal
Enumerate candidate sources for the company across primary → secondary → signal tiers, recording each as a discovery event. Do NOT retrieve content yet.

## Inputs
company_id (slug), run_id, input parameters (name, website, ticker, country, industry, aliases), and `references/source_priority_rules.md`.

## Procedure
1. Build a search plan covering each source class in priority order (official site, IR, filings/EDGAR, registries, patents/trademarks, then secondary, then signal).
2. For each candidate, compute its logical `source_id` (URL + source_class) — the engine does this via `scripts/update_source_registry.py` from the URL+class you pass.
3. Record a `discovered` event per source:
   `python scripts/update_source_registry.py --log output/companies/{slug}/source_registry.jsonl --run-id {run_id} --source-id {src} --event-type discovered --event-time {ISO} --payload '{"url":"...","source_class":"...","source_priority":"...","title":"..."}'`
4. Stop when each tier is reasonably covered or the research focus is satisfied. Log gaps (classes with zero candidates).

## Output contract
Discovery events in `source_registry.jsonl` (schema `source_registry`). No artifacts yet.

## Hard rules
Prioritize per `references/source_priority_rules.md`. Respect `references/legal_and_tos.md`. Do not fabricate URLs — only record sources you actually located.

## Hand-off
`source_retrieval.md` consumes the discovered sources.
```

- [ ] **`research_orchestrator.md`** — selects the sub-prompts to run for the given `mode`, sequences steps 1–7 of the SKILL workflow, and enforces the create-run → validate → publish ordering. Output: a run plan.
- [ ] **`source_retrieval.md`** — fetch raw bytes (agent via WebFetch, or `cdd.extract.fetch`/`edgar` when reliable), save to `raw_sources/`, `scripts/compute_hashes.py`, record `retrieved`/`canonicalized`/`unavailable` events with `diff_class`.
- [ ] **`evidence_extraction.md`** — generic facts → `extracted_artifact` with lineage.
- [ ] **`product_extraction.md`** — → `product_artifact`; preserve native taxonomy first (link `references/product_extraction_rules.md`).
- [ ] **`financial_extraction.md`** — → `financial_artifact`; preserve native tables/line-items/periods first (link `references/financial_extraction_rules.md`); normalization is a derived candidate only.
- [ ] **`corporate_structure_extraction.md`** — entities/ownership/subsidiaries/business units → `extracted_artifact` (artifact_type `corporate_structure`).
- [ ] **`market_intelligence.md`** — competitors/partnerships/customers/markets → artifacts.
- [ ] **`risk_extraction.md`** — risks/litigation/regulatory exposure → artifacts.
- [ ] **`event_extraction.md`** — M&A/funding/leadership changes/recent developments → time-stamped artifacts.
- [ ] **`evidence_validation.md`** — run `scripts/validate_outputs.py`; interpret the data-quality report; remediate or flag.
- [ ] **`dossier_generation.md`** — assemble the §12 sections + run header from CURRENT validated artifacts; every claim cited or `[INFERENCE]`; render `final_dossier.{md,json}` (json validates against `company_dossier`); then publish to `latest/` only if validation passed.
- [ ] **`run_comparison.md`** — `scripts/compare_runs.py` + `generate_change_log.py`; summarize source/extraction/schema deltas into the dossier's "Change Summary Since Previous Run".

- [ ] **Final step:** run the full integrity suite `uv run pytest tests/test_skill_integrity.py -v` → 3 passed (links now resolve). **Commit** `git commit -m "docs: add 13 orchestration prompts"`.

---

### Task 4: Examples (5 files)

**Files:** Create the 5 `examples/*` files.

- [ ] `example_input.md` — a filled-in input block (e.g. a real-ish SaaS company: name, website, ticker, industry, focus, mode).
- [ ] `example_run_manifest.json` — a completed `run_manifest` (must validate against the schema; reuse the Plan 1 test fixture, filled with realistic counts and a populated `reproducibility` block).
- [ ] `example_source_registry.jsonl` — 4–6 events (discovered/retrieved/canonicalized/unavailable) across source classes.
- [ ] `example_artifact_registry.jsonl` — 3–4 `extracted`/`validated` events.
- [ ] `example_output_structure.md` — annotated tree of `output/companies/{slug}/...` explaining each path.
- [ ] **Add to `tests/test_skill_integrity.py`:** a test that `examples/example_run_manifest.json` validates against `run_manifest` and each line of the two `.jsonl` files validates against its registry schema. Run → PASS.
- [ ] **Commit** `git commit -m "docs: add runnable examples + validation test"`.

---

### Task 5: Optional extraction tools (`cdd/extract/`)

**Files:** Create `cdd/extract/{__init__.py,html_clean.py,pdf_tables.py,edgar.py,fetch.py}`; Tests `tests/test_extract_capability.py`, `test_extract_html.py`, `test_extract_pdf.py`.

All optional-dep imports are lazy and guarded; absence yields a clear `ExtractorUnavailable` error, never a crash on import.

- [ ] **`__init__.py`** — `capabilities() -> dict[str, bool]` probing importability of trafilatura/bs4/pdfplumber/edgartools/httpx; `ExtractorUnavailable(RuntimeError)`.
- [ ] **`html_clean.py`** — `extract_main_text(html: bytes) -> str` and `extract_tables(html: bytes) -> list[list[list[str]]]` (bs4/lxml). TDD with an inline HTML fixture (no network).
- [ ] **`pdf_tables.py`** — `extract_text(pdf: bytes) -> str`, `extract_tables(pdf: bytes) -> list[...]` (pdfplumber). TDD with a tiny generated PDF fixture, or `pytest.importorskip("pdfplumber")` + skip if absent.
- [ ] **`edgar.py`** — `list_filings(ticker_or_cik, forms=("10-K","10-Q","20-F")) -> list[dict]`, `fetch_filing(accession) -> bytes`. Network-bound → tests use `pytest.importorskip` and are marked `@pytest.mark.network` / skipped by default; provide a recorded fixture path for the offline unit test of the parsing helper only.
- [ ] **`fetch.py`** — `get(url) -> tuple[bytes, dict]` returning bytes + retrieval metadata (status, content_type, final_url, retrieved_at) via httpx; respects a `user_agent` and timeout; **honors robots/ToS guidance from `references/legal_and_tos.md` is the agent's responsibility — the helper just fetches.** Network test skipped by default.
- [ ] **Tests:** `test_extract_capability.py` asserts `capabilities()` returns all-bool dict and never raises; `test_extract_html.py` extracts text+table from a fixture; `test_extract_pdf.py` importorskip. ~5 tests.
- [ ] **Gates:** optional libs are untyped → use `# type: ignore[import-untyped]` and localize to keep `pyright cdd/extract` clean (Plan 1 schema.py pattern). **Commit** `git commit -m "feat: add optional EDGAR/PDF/HTML extraction tools"`.

---

### Task 6: README.md

**Files:** Create `README.md`.

Sections (per spec §14): Purpose · Installation (`uv venv && uv pip install -e ".[dev]"`; optional `.[extract]`; `python scripts/install_skill.py`) · Usage examples (the 7-step workflow with real commands) · Run modes table · Output structure (the tree) · Refresh strategy (incremental vs full, tombstones, checkpoints) · Data-quality rules (link references) · Limitations (agent-driven retrieval; no paywalls; extraction-tool optionality) · Recommended workflow · Examples (point to `examples/`).

- [ ] **Commit** `git commit -m "docs: add README"`.

---

### Task 7: Install script + integrity

**Files:** Create `scripts/install_skill.py`; Test `tests/test_install_skill.py`.

`install_skill.py --skills-dir ~/.claude/skills [--force]` — creates a symlink `~/.claude/skills/company-due-diligence -> <repo>/company-due-diligence`. Idempotent; `--force` replaces an existing symlink (never deletes a real directory — refuse with a clear error).

- [ ] **Step 1: Failing test** — point `--skills-dir` at tmp; assert symlink created and resolves to the package; second run idempotent; a real dir at the target without `--force` → non-zero exit + message; with `--force` over a *symlink* → replaced; with `--force` over a *real dir* → refuses.
- [ ] **Step 2–4:** implement (stdlib `os.symlink`, `Path.is_symlink`). **Step 5: commit** `git commit -m "feat: add skill install/symlink script"`.

---

### Task 8: Quality gates

- [ ] `uv run pytest --cov=cdd --cov-report=term-missing` → all pass; coverage ≥ 80% on `cdd` (content files aren't coverage-bearing; extraction tools' network paths are skipped — assert the importable logic is covered).
- [ ] `uv run ruff check .` clean; `uv run pyright cdd scripts` → 0 errors.
- [ ] **Skill activation smoke (manual/documented):** `python scripts/install_skill.py --skills-dir ~/.claude/skills`; confirm `SKILL.md` frontmatter loads and all linked prompts/references resolve (the integrity test covers link resolution programmatically).
- [ ] **E2E narrative check:** dry-run the SKILL workflow on a small public company using the prompts + Plan 1/2 CLIs end-to-end; confirm a validated `final_dossier.{md,json}` is produced and published to `latest/`. (This is the true acceptance of the whole skill.)
- [ ] Commit fixups.

---

## Self-Review

- **Spec §1** (purpose/activation/inputs/modes): SKILL.md Task 1. ✓
- **Spec §2** (hybrid; optional extraction tools, graceful degradation): Task 5. ✓
- **Spec §11** (source priority tiers + anti-hallucination): references Task 2. ✓
- **Spec §12** (dossier sections + run header rendering): `dossier_generation.md` Task 3 (validated against `company_dossier` from Plan 2). ✓
- **Spec §13** (SKILL/prompts/references/examples/README): Tasks 1–4, 6. ✓
- **Install into ~/.claude/skills** (decision from brainstorming): Task 7. ✓
- **Placeholder posture:** SKILL.md and one reference + one prompt are written in full; the remaining references/prompts are specified by required-sections + a programmatic integrity/validation test (links resolve, example artifacts validate). This is the defensible approach for prose deliverables — flagged explicitly, not silent. The *engine* contracts they invoke are already fully tested by Plans 1–2.
- **Type consistency:** extraction tools return plain `bytes`/`str`/`list`/`dict` consumed by the agent, not by `cdd` bookkeeping (no coupling); `ExtractorUnavailable` raised consistently; install script touches only symlinks.

---

## Series complete
After Plan 3 merges, the `company-due-diligence` skill is fully realized: deterministic engine (Plan 1) + analysis/validation/publish/export (Plan 2) + agent skill layer (Plan 3). Recommended order: merge PR #1 (Plan 1) → execute Plan 2 → execute Plan 3.
