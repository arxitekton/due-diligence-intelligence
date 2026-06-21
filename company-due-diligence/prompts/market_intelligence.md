# Market Intelligence

## Goal
Extract competitor, partnership, customer, and market information from retrieved raw sources. Write each extraction as an `extracted_artifact` in `structured/` with a complete lineage block.

## Inputs
`company_slug`, `run_id`, raw source files in `output/companies/{slug}/runs/{run_id}/raw_sources/`, `source_registry.jsonl`, and `references/anti_hallucination_rules.md`.

## Procedure
1. Identify market-intelligence sources: company IR decks, SEC annual/quarterly reports (competitive landscape sections, customer disclosures), press releases, official partnership announcements. Apply `references/source_priority_rules.md` — secondary sources (news, analyst reports) supplement primary but do not override.
2. Extract the following categories (each becomes one or more artifacts):
   - **Competitors**: name, basis of competition, any market-share figures explicitly stated in source. Never infer competitors from general knowledge.
   - **Strategic partnerships**: partner name, nature of partnership, announcement date or period, source citation.
   - **Key customers / customer segments**: named customers (if publicly disclosed), customer count or segment descriptions, revenue concentration data if disclosed.
   - **Markets**: geographic markets, vertical markets, addressable market estimates (only if stated in source with citation).
3. For each extracted group, compose an `extracted_artifact` document:
   - `artifact_id`: `art_` + 16 hex chars.
   - `schema_version`: `"1.0"`.
   - `company_id`: `{slug}`.
   - `run_id`: `{run_id}`.
   - `artifact_type`: one of `"competitors"`, `"partnerships"`, `"customers"`, `"markets"`.
   - `source_id`: `src_` ID from `source_registry.jsonl`.
   - `original_format`: MIME type.
   - `retrieved_at` / `extracted_at`: ISO8601 UTC.
   - `confidence`: float 0–1 (lower for secondary sources or qualitative estimates).
   - `lineage`:
     - `source_snapshot_id`: `event_id` of the `retrieved` event.
     - `content_path`: relative path to raw source.
     - `locator`: object identifying section (e.g. `{"section": "Competition", "page": 12}`).
     - `snippet`: verbatim excerpt.
     - `extraction_prompt`: `{"name": "market_intelligence", "version": "1.0"}`.
   - `value`: structured payload appropriate to the artifact type.
   - `notes`: data gaps, contested claims, or `null`.
4. Write to `output/companies/{slug}/runs/{run_id}/structured/{artifact_id}.json`.
5. Record an `extracted` event:
   ```
   python scripts/update_artifact_registry.py \
     --log output/companies/{slug}/artifact_registry.jsonl \
     --run-id {run_id} --artifact-id {artifact_id} --event-type extracted \
     --event-time {ISO} \
     --payload '{"artifact_type":"...","source_id":"...","content_path":"structured/{artifact_id}.json"}'
   ```
6. Conflicting competitor lists or market-size figures across sources must be recorded as a `conflict_set` in `notes`, not silently resolved.

## Output contract
One or more `extracted_artifact` JSON files in `structured/` (artifact types: `competitors`, `partnerships`, `customers`, `markets`), each validating against the `extracted_artifact` schema with a complete `lineage` block. Corresponding `extracted` events in `artifact_registry.jsonl`.

## Hard rules
Obey all rules in `references/anti_hallucination_rules.md`. Never name competitors, customers, or partners from training-data memory — only from retrieved sources. Market-size figures must cite the source document and original wording. Inferences must be tagged `[INFERENCE]`.

## Hand-off
`evidence_validation.md` validates all `structured/` artifacts. `dossier_generation.md` renders the Customers & Markets, Competitors, and Partnerships sections from these artifacts.
