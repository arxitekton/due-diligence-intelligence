# Financial Extraction

## Goal
Extract financial statements and line-item data from retrieved raw sources, preserving the company's native tables, line-item labels, and reporting periods before any normalization. Write each extraction as a `financial_artifact` in `structured/` with a complete lineage block.

## Inputs
`company_slug`, `run_id`, raw source files in `output/companies/{slug}/runs/{run_id}/raw_sources/`, `source_registry.jsonl`, and `references/financial_extraction_rules.md`.

## Procedure
1. Identify financial sources (SEC 10-K/10-Q/20-F/annual reports, earnings releases, investor presentations) from `source_registry.jsonl`. Prioritize EDGAR filings per `references/source_priority_rules.md`.
2. For PDF sources, optionally use the `cdd.extract.pdf_tables` tool if available to extract structured table data; otherwise extract from the raw text representation.
3. **Preserve native tables and line items FIRST.** Record the company's exact statement names (`source_native_statement_name`), column headers (period labels), and row labels (line-item names) verbatim. Do not rename, aggregate, or map to a standard taxonomy (e.g. XBRL tags) at this stage — normalization is a derived candidate only.
4. For each financial statement or table, compose a `financial_artifact` JSON document following `references/financial_extraction_rules.md`:
   - `artifact_id`: generate a new `art_` prefixed 16-hex-char ID.
   - `schema_version`: `"1.0"`.
   - `company_id`: `{slug}`.
   - `run_id`: `{run_id}`.
   - `source_id`: the `src_` ID from `source_registry.jsonl`.
   - `lineage`:
     - `source_snapshot_id`: `event_id` of the `retrieved` event.
     - `content_path`: relative path to the raw source file.
     - `locator`: object identifying the table (e.g. `{"page": 42, "table_id": "income_statement", "section": "Consolidated Statements of Operations"}`).
     - `snippet`: verbatim excerpt of the table header or first rows.
     - `extraction_prompt`: `{"name": "financial_extraction", "version": "1.0"}`.
   - `source_context`: `{"document_title": "...", "section_path": [...], "source_native_statement_name": "...", "table_id": "...", "page": ...}`.
   - `periods`: array of period objects; each must include `period_id`, `source_native_label`, `period_start`, `period_end`, `as_of_date`, `period_type`, `fiscal_year`, `fiscal_quarter`, `currency_reported`, `unit_scale`, `decimals`, `restated`.
   - `line_items`: array; each must include `line_item_id`, `source_native_label`, `scope`, `column_ref` (pointing to a `period_id`), `value`, `cell_locator` (non-empty object identifying the cell), and `is_derived` flag.
   - `footnotes`: array of footnote objects (may be empty).
   - `normalization`: object describing any XBRL/IFRS/US-GAAP mapping applied; mark as `[DERIVED]` if present.
   - `notes`: caveats, restatement warnings, or `null`.
5. Write the document to `output/companies/{slug}/runs/{run_id}/structured/{artifact_id}.json`.
6. Record an `extracted` event:
   ```
   python scripts/update_artifact_registry.py \
     --log output/companies/{slug}/artifact_registry.jsonl \
     --run-id {run_id} --artifact-id {artifact_id} --event-type extracted \
     --event-time {ISO} \
     --payload '{"artifact_type":"financial","source_id":"...","content_path":"structured/{artifact_id}.json"}'
   ```
7. For conflicting values across sources for the same period/line-item, record a `conflict_set`; do NOT silently pick one.

## Output contract
One or more `financial_artifact` JSON files in `structured/`, each validating against the `financial_artifact` schema with a complete `lineage` block and all required `periods` / `line_items` fields. Corresponding `extracted` events in `artifact_registry.jsonl`.

## Hard rules
Follow all rules in `references/financial_extraction_rules.md`. Native line-item names and period labels are authoritative; normalization is always secondary and must be marked `[DERIVED]`. Never invent figures, periods, or restated values not present in the source (see `references/anti_hallucination_rules.md`). Every `line_item` must have a non-empty `cell_locator` and a non-null `scope`.

## Hand-off
`evidence_validation.md` validates all `structured/` artifacts (including the 8 fatal gates; `financial_usability` specifically checks `cell_locator`, `scope`, `column_ref`, and `currency_reported`). `scripts/merge_artifacts.py` merges financial artifacts and surfaces conflicts. `dossier_generation.md` renders the Financials section from validated artifacts.
