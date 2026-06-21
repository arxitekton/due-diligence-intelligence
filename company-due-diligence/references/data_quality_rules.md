# Data Quality Rules

## Fatal Gates

The `validate_outputs` script runs 8 fatal gates. A run fails if any gate returns `passed: false`. Failed runs must not be published to `latest/`. Fix the underlying issue and re-run validation (use `validation_only` mode) before proceeding to dossier generation.

### 1. `schemas_valid`
Every structured artifact file in the run directory must validate against its registered JSON Schema. This includes `financial_artifact`, `product_artifact`, `extracted_artifact`, and `source_inventory`. In strict modes (`full_refresh`, `incremental_refresh`, `validation_only`, `dossier_only`, `compare_runs`), validation must use the real jsonschema library; a degraded pass (library absent) is treated as a failure. A single schema violation in any artifact fails the gate.

### 2. `referential_integrity`
All cross-document references must resolve within the run. Two checks:
- Every artifact's `source_id` must appear in the `source_inventory.sources` array for this run.
- Every `artifact_id` cited in `final_dossier.json` claims must exist in the artifact set for this run.

Dangling references indicate a partially executed run (e.g., an artifact was written but its source was not inventoried, or the dossier cites an artifact from a prior run that was not re-extracted). Fix by completing the run or by rebuilding the dossier from current-run artifacts only.

### 3. `lineage_complete`
Every artifact must pass the `lineage_ok` check: all four lineage fields (`source_snapshot_id`, `content_path`, `locator`, `snippet`) must be non-empty, and `extraction_prompt.name` and `extraction_prompt.version` must be present. Additionally, every dossier claim of kind `fact` or `evidence` must have at least one entry in its `citations` array. An uncited fact or evidence claim is a lineage violation.

### 4. `id_integrity`
`artifact_id` values must be unique across the run. Duplicate IDs indicate a collision in ID generation or an artifact written twice (e.g., a retry that produced two outputs for the same extraction). Deduplication must happen before validation, not after.

### 5. `financial_usability`
Every `financial_artifact` must meet usability requirements for downstream analysis:
- Every `line_item.scope` must be non-null (one of `consolidated`, `segment`, `subsidiary`, `non_gaap`).
- Every `line_item.cell_locator` must be a non-empty object.
- Every `line_item.column_ref` must reference a `period_id` that exists in the artifact's `periods` array, and that period must have non-empty `currency_reported` and `unit_scale` fields.
- No duplicate `(scope, period_id, line_item_id)` tuples within a single artifact.

A financial artifact that fails usability is structurally unusable for any numeric analysis and must be corrected at the extraction phase.

### 6. `manifest_closure`
Every path listed in `run_manifest.output_paths` must exist on disk. A missing file indicates an incomplete run (a step declared it would write a file but did not). Content-hash recomputation is not yet enforced by this gate; existence is the current check. The manifest itself is not required to be present; if absent, the gate passes vacuously (no paths to check).

### 7. `refresh_semantics`
Applies only to `incremental_refresh` mode. Every source that was `active` or `reappeared` in the source registry at the start of the run must appear in the current run's `source_inventory`. If a known-active source is absent without a corresponding `unavailable` marker in the inventory, the gate fails with "silently dropped" detail. This catches cases where discovery drift has caused previously tracked sources to be quietly omitted. Not applicable to other modes (passes vacuously).

### 8. `conflict_visibility`
All financial conflicts detected by `merge_financials` must appear in `data_quality_report.conflicts`. The gate itself passes by construction once conflicts are surfaced — the act of surfacing them is the gate's requirement. If `merge_financials` raises an exception (typically because `financial_usability` has already failed), the gate degrades gracefully and notes the skip; the financial_usability failure will independently fail the run.

---

## Non-Fatal Flags

These are recorded in the `data_quality_report` but do not block a run. They must be reviewed before accepting the dossier as authoritative.

**Stale sources** (`stale_sources` array): sources whose `last_seen_at` timestamp is older than `stale_after_days` (default 180 days). A stale primary source may mean the company's disclosures have changed since the last retrieval. Consider triggering an `incremental_refresh` targeting the stale sources.

**Low-confidence extractions** (`low_confidence` array): artifacts whose top-level `confidence` field is below the `low_confidence_threshold` (default 0.5). These extractions are structurally valid but the extraction model assigned low confidence to its own output. Review the source snippet and consider re-extraction with a more targeted prompt.

**Missing source classes** (`missing_source_classes` array): source classes specified in `expected_primary_classes` that are absent from the current run's inventory. This flag is only raised when the caller provides an expected class list. A missing `sec_filing_10k` for a US public company is a significant gap; a missing `github_repo` for a company with no known public OSS activity may be expected. `sanctions_list` and `export_control_list` are **expected primary source classes for every run** that includes a sanctions screening step — their absence must be flagged as a `missing_source_classes` non-fatal warning. Any dossier claim about sanctions or export-control status must cite an artifact from a `sanctions_list` or `export_control_list` source; "no match" results must record the lists screened and their as-of dates.

---

## Confidence Scoring Guidance

Confidence scores are set by the extraction agent, not computed by the validation layer. Use this guidance for consistent scoring:

- **0.9–1.0:** Value extracted from a well-structured table in a primary source (e.g., income statement in a 10-K). The field maps directly to a schema field with no ambiguity.
- **0.7–0.9:** Value extracted from a primary source but requires minor interpretation (e.g., inferring period boundaries from fiscal quarter labels, or disambiguating a consolidated vs. segment line item from context).
- **0.5–0.7:** Value extracted from a secondary source, or from a primary source where the relevant passage is ambiguous or partially obscured (e.g., a figure mentioned in the MD&A narrative rather than in a table).
- **0.3–0.5:** Value extracted from a signal source, or the extraction required significant inference from context (e.g., deriving a product tier's feature set from a comparison table with ambiguous formatting).
- **< 0.3:** Extraction is speculative. Consider omitting the artifact or flagging it as inference rather than evidence.

---

## Staleness Thresholds

| Source class | Flag as stale after |
|---|---|
| `earnings_release`, `earnings_transcript` | 95 days (one quarter) |
| `sec_filing_*`, `annual_report` | 370 days (one fiscal year plus buffer) |
| `investor_relations`, `company_website` | 180 days (default) |
| `product_page`, `pricing_page` | 90 days (high volatility) |
| `job_posting` | 30 days (ephemeral) |
| `press_release` | 90 days |
| `financial_media`, `analyst_report` | 180 days |
| `github_repo`, `developer_docs` | 180 days |

The default `stale_after_days=180` applies to classes not listed above unless overridden in the `validate_run` call.
