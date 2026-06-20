# Design Spec — `company-due-diligence` Claude Code Skill

- **Date:** 2026-06-20
- **Status:** Approved (design); pending implementation plan
- **Authors:** Claude (Opus 4.8) + independent Codex critique (consensus)
- **Repo home:** this repository (`due-diligence-intelligence`)

---

## 1. Purpose & Non-Goals

### Purpose
A **reusable, refreshable, versioned research system** for exhaustive company due diligence and market intelligence, packaged as a Claude Code Skill.

It is a **research-corpus extraction, evidence-management, change-tracking, and dossier-generation system** — not a one-shot report generator. Every run is reproducible, every claim is traceable to a preserved source snapshot, and re-runs detect and record what changed.

### Core methodology
`Discover → preserve original evidence → extract artifacts → structure later → validate → generate dossier.`

Schema **emerges from sources**. The company's real structure is preserved in source-native terminology, tables, hierarchies, segment names, financial line items, geography definitions, product taxonomies, and reporting structures. Normalization is a separate, derived, non-destructive layer.

### Non-Goals
- Not a live monitoring/alerting service (it is run-on-demand, refreshable).
- Not an investment recommendation engine — it separates facts/evidence from analysis and never asserts unsupported conclusions.
- Bookkeeping scripts never make network calls.

---

## 2. Architecture — Hybrid

| Layer | Responsibility |
|---|---|
| **Claude agent (primary)** | Discovery, search strategy, retrieval of arbitrary / JS-rendered sources, and all *semantic* extraction & reasoning. Driven by `prompts/*.md`. |
| **Python extraction tools (deterministic, where reliable)** | SEC EDGAR (`edgartools`), PDF + table extraction (`pdfplumber` / `pymupdf`), HTML→text (`trafilatura` + `beautifulsoup4` + `lxml`), HTTP fetch (`httpx`), tabular handling (`pandas`). |
| **Python bookkeeping (always deterministic, NO network)** | run_id/folders, dual hashing + canonicalization, registry event append, run diffs, schema validation, exports, manifest/index derivation, concurrency-safe finalize. |

**Rationale:** the agent handles breadth and messy real-world sources; Python provides determinism and reliability for structured artifacts (especially financial tables) and for all auditability bookkeeping. Bookkeeping is decoupled from the network so it is portable, testable, and API-key-free.

### Packaging & dependencies
- Built in **this repo** at `company-due-diligence/`, versioned in git.
- Installed by **symlink** into `~/.claude/skills/company-due-diligence/` so it activates as a skill.
- `output/` is gitignored.
- `uv`-managed venv. **stdlib-only bookkeeping core** (runs with zero install) + optional **extras** for the extraction stack. Scripts **degrade gracefully** when an extra is absent (and `validate_outputs` records degraded capability rather than silently passing — see §10).

---

## 3. Identity & Versioning Model

- **`company_slug`** — produced by `normalize_company_id` (deterministic, stable across runs; collisions guarded by validation).
- **`source_id`** — a **stable logical source** keyed by normalized URL + `source_class`. **NOT keyed by content_hash.** (Hash-keying would both collapse the same press release across IR/EDGAR/newswire into one source, and split a single source into many across content versions.)
- **`source_snapshot_id`** — one retrieval event of a source at a point in time; carries its own `raw_hash`, `canonical_hash`, and HTTP/retrieval metadata.
- **`run_id`** = `{YYYYMMDDTHHMMSSZ}-{short token}`.
- **Reproducibility pins in `run_manifest.json`:** prompt-set hash, schema-set hash, model id, tool/extractor versions, normalizer-profile versions, search queries + result ranks, locale.

This versioning is what lets `compare_runs` classify every diff as **`source_delta` vs `extraction_delta` vs `schema_delta`** — without it, editing a prompt or changing model behavior would masquerade as a real change in the company.

---

## 4. Evidence & Provenance Model

### Dual hashing + versioned canonicalization
- `raw_hash` over immutable raw bytes (preserved verbatim in `raw_sources/`).
- `canonical_hash` over a **versioned, MIME-aware canonical form**:
  - **HTML:** strip `script`/`style`/comments/nonces/session attrs/cache-busters/volatile boilerplate; normalize Unicode + whitespace; hash visible text and tables separately.
  - **JSON/API:** recursive key sort; normalize numeric/string formatting; drop volatile paths (`timestamp`, `requestId`, `csrf`, `session`, tracking).
  - **PDF/Text:** normalize line breaks, de-hyphenation, repeated headers/footers, page numbers; hash page text and tables separately.
  - **URLs:** normalize scheme/host case, trailing slashes, query-param order; drop tracking params by explicit rule only.
- Each snapshot records `normalization_profile_id` + `normalization_profile_version` + `ignored_fragments`.
- **`diff_class` ∈ `{unchanged, cosmetic_change, table_change, content_change, unavailable}`** — eliminates false deltas (timestamps/ads/CSRF) that would otherwise poison `incremental_refresh` and `compare_runs`.

### Sub-artifact lineage (first-class)
Every **structured value** and every **dossier claim** resolves to:
`source_snapshot_id` + file path + **cell/row/page/span locator** + exact snippet/cell text + extraction-prompt name & version.

`source_id + artifact_id` alone is too coarse for diligence defensibility; lineage must reach the cell/quote level.

---

## 5. Registries — Append-Only Event Logs

- `source_registry.jsonl` and `artifact_registry.jsonl` are **append-only event streams**, never mutated in place (fits "never overwrite prior runs").
- Event shape: `event_id, event_time, run_id, entity_type, entity_id, event_type, payload`, where
  `event_type ∈ {discovered, retrieved, canonicalized, unavailable, extracted, validated, superseded}`.
- Derived current-state views regenerated at run close (and never the primary record):
  - `first_seen_at` / `last_seen_at` / `unavailable` / `reappeared` status per source.
  - `source_index.json`, `artifact_index.json`, `manifest.json`.

---

## 6. Output Layout

```
output/
  companies/
    {company_slug}/
      source_registry.jsonl        # append-only event log
      artifact_registry.jsonl      # append-only event log
      manifest.json                # derived current-state index
      runs/
        {run_id}/
          run_manifest.json
          raw_sources/             # immutable raw bytes
          raw_artifacts/           # raw extracted (pre-normalization) tables/docs
          extracted_tables/        # source-native tables preserved verbatim
          structured/              # validated structured artifacts (w/ lineage)
          reports/
          logs/
          data_quality_report.md
          change_log.md
          final_dossier.md
          final_dossier.json
      latest/                      # published ONLY after validation passes
      history/
```

**Never overwrite previous run outputs.** Only `latest/`, registries, indexes, and manifests are updated.

### Concurrency-safe finalization
- Per-`company_slug` single-writer lock.
- Temp-file writes + atomic rename for shared files (registries, `manifest.json`, indexes).
- `latest/` is published only after the run passes validation and `run_manifest.json` is complete.

---

## 7. Run Modes & Refresh Semantics

Eight modes: `full_refresh`, `incremental_refresh`, `source_discovery_only`, `source_retrieval_only`, `extraction_only`, `validation_only`, `dossier_only`, `compare_runs`.

### Refresh behavior
On every re-run: new `run_id`; reuse existing registries; detect new / changed / unavailable sources via `diff_class`; append new evidence; preserve historical evidence; generate `change_log.md`; regenerate dossier only from **current validated artifacts** (unless `dossier_only`).

### `incremental_refresh` is policy-driven (not purely hash-driven)
- Rediscovery cadence defined **per source class**.
- **Tombstones** required for sources that disappear — the corpus cannot silently shrink; a removed source emits an `unavailable` event.
- Forced periodic `full_refresh` checkpoints to counter agent-driven discovery drift.

---

## 8. Schemas (`schemas/*.schema.json`)

Nine specified schemas: `run_manifest`, `source_registry`, `artifact_registry`, `source_inventory`, `extracted_artifact`, `financial_artifact`, `product_artifact`, `company_dossier`, `data_quality_report`. Enrichments:

### `financial_artifact`
- **Identity/lineage:** `artifact_id, run_id, company_slug, source_id, source_snapshot_id, raw_hash, canonical_hash, extraction_prompt{name,version}`.
- **`source_context`:** `document_title, section_path[], source_native_statement_name, table_id, page`.
- **`periods[]`:** `period_id, source_native_label, period_start, period_end, as_of_date, period_type(FY|Q|TTM|LTM|YTD), fiscal_year, fiscal_quarter, currency_reported, unit_scale(ones|thousands|millions), decimals, restated`.
- **`line_items[]`:** `line_item_id, source_native_label, source_native_path[], scope(consolidated|segment|subsidiary|non_gaap), row_order, column_ref, value_raw, value_numeric, sign_convention, footnote_refs[], cell_locator{row,col,header_path}, normalized_candidate{taxonomy_key,confidence}`.
- **`footnotes[]`:** `footnote_id, text, locator`.

### `product_artifact`
- Same identity/lineage + `source_context`, then `entities[]`: `entity_id, entity_type(product|service|tier|bundle|feature), source_native_name, aliases[], source_native_category_path[], parent_entity_id, display_order, description_quote, lifecycle_status, geography_scope[], pricing_observations[]{price_raw,currency_reported,billing_interval,locator}, attributes[]{name_native,value_native,locator}, normalized_candidate{family,confidence}`.

**Rule:** source-native fields are primary; `normalized_candidate` is optional, derived, and non-destructive.

### New: `conflict_set` object
Explicit object with reason codes: `restatement, currency_mismatch, period_mismatch, scope_mismatch, gaap_vs_nongaap, source_authority_conflict`. Conflicting data is preserved and flagged, **never silently merged or resolved.**

### Derived normalization layer (separate)
Currency/period normalization (FX source + date, unit scaling, fiscal→calendar mapping) lives in a derived layer and never overwrites source-native artifacts. Every normalized metric traces back to `source_id, artifact_id, run_id, page_or_section, retrieved_at, extracted_at, confidence`.

### Source authority metadata
Each source carries `source_class, issuer_affiliated, regulatory_status` for conflict-handling trust weighting.

---

## 9. Scripts (`scripts/*.py`, CLI-runnable)

| Script | Role |
|---|---|
| `create_run.py` | Generate `run_id`, create run folder tree, seed `run_manifest.json`. |
| `normalize_company_id.py` | Deterministic `company_slug`. |
| `compute_hashes.py` | Dual hashing + versioned canonicalization profiles → `diff_class`. |
| `update_source_registry.py` | Append source events to the log. |
| `update_artifact_registry.py` | Append artifact events to the log. |
| `compare_runs.py` | Diff two runs; classify `source_delta / extraction_delta / schema_delta` + `diff_class`. |
| `generate_change_log.py` | Render `change_log.md` from diffs. |
| `validate_outputs.py` | Evidentiary quality gates (see §10). |
| `merge_artifacts.py` | Lineage-preserving merge; emits `conflict_set`, never collapses distinct provenance. |
| `export_jsonl.py` / `export_csv.py` / `export_markdown.py` | Exports, with safe-export modes (PII/sensitivity-aware). |
| `build_manifest.py` | Derive current-state `manifest.json` + indexes from event logs. |

stdlib-only core; extraction extras optional with graceful degradation.

`run_manifest.json` schema (minimum): `run_id, company_id, company_name, started_at, completed_at, mode, input_parameters{}, sources_discovered, sources_retrieved, sources_new, sources_changed, sources_unavailable, artifacts_extracted, schemas_validated, output_paths[], warnings[], errors[]` — plus the reproducibility pins from §3.

---

## 10. Quality Gates — Evidentiary (`validate_outputs.py`)

Fails (not warns) on:
- Schema invalid. **Full structural validation is required** for `full_refresh`/`incremental_refresh`/`validation_only`/`dossier_only`/`compare_runs`; structural-only fallback is acceptable **only** in discovery/retrieval phases, and degraded capability is recorded in the manifest.
- Manifest closure broken: a referenced file is missing, or a recorded hash fails to recompute.
- Referential integrity broken: a dossier citation that does not resolve to an artifact; an artifact that does not resolve to a source snapshot + physical file.
- Lineage incomplete: a structured value without a locator; a non-`[INFERENCE]` claim without ≥1 citation.
- ID integrity: duplicate `run_id`/`source_id`/`artifact_id`/`event_id`; conflicting `company_slug` normalization within a company's history.
- Refresh semantics: `incremental_refresh` silently dropping a known source (missing → must emit `unavailable`/tombstone).
- Financial usability: a numeric fact missing period label, currency, unit scale, scope, or cell/footnote locator; duplicate line items (same scope+period+locator).
- Conflict visibility: colliding normalized candidates with differing source-native value/scope/period not represented as an explicit `conflict_set`.
- `latest/` published before validation passed.

Also reported (non-fatal): stale sources, low-confidence extractions, missing source classes.

---

## 11. Anti-Hallucination & Source Priority

- **Never invent missing data;** use `null`/`unknown`.
- **Three-way separation:** facts vs extracted evidence vs analysis.
- Every dossier claim **cites** `source_id`+`artifact_id`(+locator) or is tagged **`[INFERENCE]`**.
- Do not infer ownership, revenue, customers, or financial metrics without explicit evidence.
- Conflicts preserved & flagged (`conflict_set`), never silently resolved.

**Source priority tiers** (documented in `references/source_priority_rules.md`):
- **Primary:** official sites, product pages, annual/quarterly reports, 10-K/10-Q/20-F, IR, earnings releases & call transcripts, exchange & regulatory filings, company registries, government records, patents, trademarks, court filings.
- **Secondary:** reputable financial media, industry/analyst reports, press releases, conference materials, customer case studies, partner pages.
- **Signal:** job postings, developer/API docs, app stores, GitHub/OSS, technical blogs, pricing pages, documentation portals.

---

## 12. Final Dossier

Sections: Executive Summary, Company Identity, Source Coverage, Corporate Structure, Ownership / Legal Entities, Products & Services, Technology / IP, Customers & Markets, Financials, Competitors, Partnerships, M&A / Funding, Risks, Recent Developments, Data Quality Notes, Change Summary Since Previous Run, Appendix: Source Inventory, Appendix: Raw Tables, Appendix: Extracted Artifacts.

Run header on every dossier: `run_id`, research date, retrieval window, # sources discovered, # sources used, # changed, # unavailable, known gaps, confidence summary.

---

## 13. Prompts & References

### `prompts/*.md` (13)
`research_orchestrator, source_discovery, source_retrieval, evidence_extraction, product_extraction, financial_extraction, corporate_structure_extraction, market_intelligence, risk_extraction, event_extraction, evidence_validation, dossier_generation, run_comparison`.

### `references/*.md` (6 specified + 2 production-critical additions)
Specified: `research_methodology, source_priority_rules, data_quality_rules, anti_hallucination_rules, financial_extraction_rules, product_extraction_rules`.
**Added (Codex gap analysis):** `legal_and_tos.md` (per-source `access_basis, license_or_terms_ref, robots_observed, retention_policy, export_restrictions`) and `provenance_and_reproducibility.md`. Artifacts carry `sensitivity_class` / `pii_present`; `export_*` honor safe-export modes.

### `examples/`
`example_input.md, example_run_manifest.json, example_source_registry.jsonl, example_artifact_registry.jsonl, example_output_structure.md`.

### `SKILL.md`
Concise (~120 lines), progressive disclosure: YAML frontmatter (name + description), activation triggers, high-level workflow, hard rules, links to prompts/references. `README.md` covers purpose, install, usage, run modes, output structure, refresh strategy, data-quality rules, limitations, recommended workflow, examples.

---

## 14. Consensus Record (Claude × Codex)

Base architecture (mine) held: hybrid retrieval, in-repo + symlink packaging, uv stdlib-core + extras, append-oriented evidence, three-way anti-hallucination separation.

Codex deltas **adopted**:
1. Dual-hash + versioned canonicalization with `diff_class`.
2. Sub-artifact (cell/quote-level) lineage as first-class.
3. Source-drift vs extractor-drift separation via prompt/schema/model versioning + `compare_runs` delta-type classification.
4. `source_id` keyed by **logical source**, not content_hash.
5. Registries as **append-only event logs** with derived current-state views.
6. Concurrency-safe finalization (lock + atomic rename + gated `latest/`).
7. Evidentiary validation (not structural-only).
8. Production gaps closed: legal/ToS/licensing, PII/sensitivity, conflict_set reconciliation, derived currency/period normalization, source-authority metadata.

---

## 15. Open Decisions (default, can revisit)
- Legal/ToS + PII layer **included in v1** (default; user may defer).
- Event-log registries accepted despite added derived-view complexity.
