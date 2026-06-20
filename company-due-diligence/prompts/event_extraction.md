# Event Extraction

## Goal
Extract time-stamped material events — M&A, funding rounds, leadership changes, product launches, and other recent developments — from retrieved raw sources. Write each extraction as an `extracted_artifact` in `structured/` with a complete lineage block.

## Inputs
`company_slug`, `run_id`, raw source files in `output/companies/{slug}/runs/{run_id}/raw_sources/`, `source_registry.jsonl`, and `references/anti_hallucination_rules.md`.

## Procedure
1. Identify event sources: SEC 8-K filings, press releases, IR announcements, earnings call transcripts, official newsroom pages. Apply `references/source_priority_rules.md` — primary disclosures take precedence over media coverage.
2. Extract the following event categories:
   - **M&A**: acquirer, target, deal value (if disclosed), deal type (acquisition, merger, divestiture), announced date, closed date (if known), deal status.
   - **Funding / capital raises**: round type (Series A–Z, IPO, follow-on, debt), amount raised, lead investors (if disclosed), announced date, post-money valuation (if disclosed).
   - **Leadership changes**: role, outgoing person, incoming person, effective date, reason (if disclosed).
   - **Product launches / major updates**: product name, launch date, key features (as described in source).
   - **Other material developments**: regulatory approvals, major contracts, partnerships (if not already in `market_intelligence.md`), restructurings.
3. Each event gets its own `extracted_artifact` document:
   - `artifact_id`: `art_` + 16 hex chars.
   - `schema_version`: `"1.0"`.
   - `company_id`: `{slug}`.
   - `run_id`: `{run_id}`.
   - `artifact_type`: one of `"ma_event"`, `"funding_event"`, `"leadership_change"`, `"product_launch"`, `"material_development"`.
   - `source_id`: `src_` ID from `source_registry.jsonl`.
   - `original_format`: MIME type.
   - `retrieved_at` / `extracted_at`: ISO8601 UTC.
   - `confidence`: float 0–1.
   - `lineage`:
     - `source_snapshot_id`: `event_id` of the `retrieved` event.
     - `content_path`: relative path to raw source.
     - `locator`: object identifying the announcement (e.g. `{"press_release_date": "2025-03-15", "headline": "...", "url_path": "/news/..."}`) or filing (e.g. `{"form": "8-K", "filing_date": "2025-03-15"}`).
     - `snippet`: verbatim excerpt announcing the event.
     - `extraction_prompt`: `{"name": "event_extraction", "version": "1.0"}`.
   - `value`: structured event payload; always include `event_date` (ISO8601 or partial date), `event_type`, and all disclosed specifics.
   - `notes`: status uncertainty, undisclosed amounts set to `null`, or `[INFERENCE]` for derived dates.
4. Write to `output/companies/{slug}/runs/{run_id}/structured/{artifact_id}.json`.
5. Record an `extracted` event:
   ```
   python scripts/update_artifact_registry.py \
     --log output/companies/{slug}/artifact_registry.jsonl \
     --run-id {run_id} --artifact-id {artifact_id} --event-type extracted \
     --event-time {ISO} \
     --payload '{"artifact_type":"...","source_id":"...","content_path":"structured/{artifact_id}.json"}'
   ```
6. For events reported differently across sources (e.g. differing deal values), record a `conflict_set` in `notes`.

## Output contract
One or more `extracted_artifact` JSON files (artifact types: `ma_event`, `funding_event`, `leadership_change`, `product_launch`, `material_development`) in `structured/`, each validating against the `extracted_artifact` schema with a complete `lineage` block. Corresponding `extracted` events in `artifact_registry.jsonl`.

## Hard rules
Obey all rules in `references/anti_hallucination_rules.md`. Never invent event dates, deal values, or participant names from training-data memory. Undisclosed figures are `null`. Partial dates (year-only, quarter) are acceptable and must be marked as such in `value.event_date_precision`.

## Hand-off
`evidence_validation.md` validates all `structured/` artifacts. `dossier_generation.md` renders the M&A/Funding, Leadership Changes, and Recent Developments sections from these artifacts. `run_comparison.md` surfaces event-delta across runs.
