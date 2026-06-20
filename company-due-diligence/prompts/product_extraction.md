# Product Extraction

## Goal
Extract product and service information from retrieved raw sources, preserving the company's native product taxonomy before any normalization. Write each product artifact as a `product_artifact` in `structured/` with a complete lineage block.

## Inputs
`company_slug`, `run_id`, raw source files in `output/companies/{slug}/runs/{run_id}/raw_sources/`, `source_registry.jsonl`, and `references/product_extraction_rules.md`.

## Procedure
1. For each retrieved source likely to contain product information (official website product pages, IR decks, press releases, marketing materials), read the raw file from `raw_sources/`.
2. **Preserve the native taxonomy FIRST.** Record product names, categories, and sub-categories exactly as the company uses them — do not rename, collapse, or translate into a third-party taxonomy at this stage. Normalization is a derived candidate only; mark it clearly as `[DERIVED]` in the artifact if applied.
3. For each product or product-family grouping, compose a `product_artifact` JSON document following `references/product_extraction_rules.md`:
   - `artifact_id`: generate a new `art_` prefixed 16-hex-char ID.
   - `schema_version`: `"1.0"`.
   - `company_id`: `{slug}`.
   - `run_id`: `{run_id}`.
   - `source_id`: the `src_` ID from `source_registry.jsonl`.
   - `lineage`:
     - `source_snapshot_id`: `event_id` of the `retrieved` event.
     - `content_path`: relative path to the raw source file.
     - `locator`: object identifying product location within source (e.g. `{"url_path": "/products/cloud", "section": "Cloud Products"}`).
     - `snippet`: verbatim excerpt naming or describing the product.
     - `extraction_prompt`: `{"name": "product_extraction", "version": "1.0"}`.
   - `value`: the structured product payload; include at minimum `native_name`, `native_category`, `description`, `pricing_model` (if known), `target_segment` (if known). Normalization fields (e.g. `normalized_category`) must be tagged `[DERIVED]` in notes.
   - `confidence`: float 0–1.
   - `notes`: any taxonomy conflicts, ambiguities, or normalization rationale.
4. Write the document to `output/companies/{slug}/runs/{run_id}/structured/{artifact_id}.json`.
5. Record an `extracted` event:
   ```
   python scripts/update_artifact_registry.py \
     --log output/companies/{slug}/artifact_registry.jsonl \
     --run-id {run_id} --artifact-id {artifact_id} --event-type extracted \
     --event-time {ISO} \
     --payload '{"artifact_type":"product","source_id":"...","content_path":"structured/{artifact_id}.json"}'
   ```
6. If multiple sources describe the same product differently, record a `conflict_set` in `notes`; do NOT silently pick one.

## Output contract
One or more `product_artifact` JSON files in `structured/`, each validating against the `product_artifact` schema with a complete `lineage` block. Corresponding `extracted` events in `artifact_registry.jsonl`.

## Hard rules
Follow all rules in `references/product_extraction_rules.md`. Native taxonomy is authoritative; normalization is always secondary and must be marked `[DERIVED]`. Never invent product names, pricing, or features not present in the source (see `references/anti_hallucination_rules.md`).

## Hand-off
`evidence_validation.md` validates all `structured/` artifacts. `dossier_generation.md` renders the Products & Services section from these artifacts. `scripts/merge_artifacts.py` merges product artifacts for conflict surfacing.
