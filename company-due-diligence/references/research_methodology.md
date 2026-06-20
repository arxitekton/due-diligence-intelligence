# Research Methodology

## Overview

The research loop has six phases. They map to CRISP-DM and must be executed in order. Skipping a phase in a mode where it is required is a fatal error; skipping it in a mode where it is explicitly not required is correct behaviour (the mode contract specifies which phases are active).

```
Discover → Preserve → Extract → Structure → Validate → Dossier
```

---

## Phase Descriptions

### 1. Discover
Enumerate sources for the target company using the tiers defined in `source_priority_rules.md`. Start with primary sources (investor relations, SEC EDGAR, company registry), then secondary (financial media, industry reports), then signal (job boards, GitHub). Record each discovered source as a `source_added` event in the source registry before fetching. Do not fetch before recording; the registry is the ground truth for what was attempted.

**CRISP-DM mapping:** Business Understanding (scoping the evidence landscape) + Data Understanding (cataloguing available data).

### 2. Preserve (Retrieve)
Fetch the raw bytes of each discovered source and write to `runs/{run_id}/raw_sources/`. Immediately compute dual content hashes (raw + canonical). Classify `diff_class` by comparing against the prior run's hashes stored in the source registry. Record a `source_retrieved` or `source_unavailable` event. Never alter the raw bytes; normalization happens later.

**CRISP-DM mapping:** Data Understanding (capturing the raw data record).

### 3. Extract
Run extraction prompts over the preserved content to produce structured artifacts (`financial_artifact`, `product_artifact`, `extracted_artifact`). Preserve source-native representations first — do not normalize during extraction. Every artifact must carry full lineage (`source_snapshot_id`, `content_path`, `locator`, `snippet`, `extraction_prompt.name+version`). Record each artifact via `scripts/update_artifact_registry.py`.

**CRISP-DM mapping:** Data Preparation (parsing and structuring raw evidence).

### 4. Structure
Merge extracted artifacts into dossier-ready data structures. Detect conflicts and emit `conflict_set` entries. Apply normalization as a separate derived layer (FX conversion, unit scaling, fiscal-to-calendar mapping) without overwriting source-native fields. Write `source_inventory.json` for the run.

**CRISP-DM mapping:** Data Preparation (integration and transformation).

### 5. Validate
Run `scripts/validate_outputs.py`. All 8 fatal gates must pass before publishing. Fix gate failures before proceeding; do not suppress or bypass. Non-fatal flags (stale sources, low-confidence extractions, missing source classes) are recorded but do not block the run. See `data_quality_rules.md` for gate definitions.

**CRISP-DM mapping:** Evaluation (quality assurance before deployment).

### 6. Dossier
Generate `final_dossier.{md,json}` from currently validated artifacts only. Every claim must be typed (`fact`, `evidence`, or `inference`) and cite at least one `artifact_id` (for `fact` and `evidence` claims) or carry the `[INFERENCE]` tag. Publish to `latest/` only after the gate report shows `passed: true`. See `anti_hallucination_rules.md` for claim discipline.

**CRISP-DM mapping:** Deployment (delivering the research product).

---

## Run Modes

| Mode | Phases active | Typical use |
|---|---|---|
| `full_refresh` | All 6 | First run for a company; periodic deep refresh (quarterly or after forced checkpoint) |
| `incremental_refresh` | Discover → Preserve → Extract → Structure → Validate → Dossier | Routine update; skips unchanged sources (diff_class = unchanged) |
| `source_discovery_only` | Discover | Audit what sources exist before committing to retrieval |
| `source_retrieval_only` | Preserve | Re-fetch already-discovered sources (e.g. after a transient failure) |
| `extraction_only` | Extract + Structure | Re-run extraction with a new prompt or model version without re-fetching |
| `validation_only` | Validate | Re-validate existing artifacts after a schema or prompt fix |
| `dossier_only` | Dossier | Regenerate the dossier from validated artifacts without re-running any upstream phase |
| `compare_runs` | — (post-run analysis) | Diff two existing runs to classify delta_type and produce a change log |

For `extraction_only`, `validation_only`, and `dossier_only`, the existing `raw_sources/` and registry state from a prior run provide the input. The reproducibility block must pin the model_id and prompt_set_hash used.

---

## Rediscovery Cadence per Source Class

| Source class | Recommended cadence | Notes |
|---|---|---|
| `sec_filing_*` | Within 2 business days of filing date | EDGAR RSS feed is the trigger |
| `annual_report`, `exchange_filing` | Within 5 business days of publication | Check IR page and exchange |
| `earnings_release`, `earnings_transcript` | Within 24 hours of earnings date | Time-sensitive; trigger incremental_refresh |
| `investor_relations` | Monthly | IR pages change silently |
| `company_website`, `product_page` | Monthly | Product taxonomy and pricing drift |
| `press_release` | Weekly | High churn; use RSS or PR wire feeds |
| `financial_media`, `analyst_report` | Weekly | Coverage events drive refresh timing |
| `job_posting` | Weekly | Ephemeral; point-in-time signal only |
| `pricing_page` | Monthly | High volatility; always note retrieved_at |
| `github_repo` | Monthly | Tag and release activity is the signal |
| `documentation_portal`, `developer_docs` | Quarterly | Slower churn than product pages |

---

## Forced Full-Refresh Checkpoints

Incremental runs accumulate discovery drift over time: sources that were never found in the original discovery pass remain absent indefinitely, and the agent's prior run state biases subsequent discovery. Schedule forced `full_refresh` runs at these checkpoints regardless of whether incremental runs are passing:

- Every 90 days (quarterly) for active monitoring subjects.
- Immediately after any material corporate event: M&A announcement, IPO, SPAC transaction, significant restructuring, CEO change, restatement announcement.
- After any schema_set_hash or prompt_set_hash change (a `schema_delta` or `extraction_delta` in `compare_runs` output indicates this is needed).
- When `missing_source_classes` in the data quality report names a primary-tier class absent for two consecutive runs.

The forced full_refresh resets the source discovery baseline and eliminates accumulated drift.
