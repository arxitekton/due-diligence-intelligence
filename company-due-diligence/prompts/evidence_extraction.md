# Evidence Extraction

## Goal
Extract generic structured facts (company identity, leadership, founding, headcount, legal entity details, mission/vision statements, and any facts that do not belong to the product, financial, corporate-structure, risk, market, or event specialist prompts) from retrieved raw sources. Write each fact as an `extracted_artifact` in `structured/` with a complete lineage block.

## Inputs
`company_slug`, `run_id`, raw source files in `output/companies/{slug}/runs/{run_id}/raw_sources/`, `source_registry.jsonl` (for `source_snapshot_id` lookups), and `references/anti_hallucination_rules.md`.

## Procedure
1. For each retrieved source (status `retrieved` in `source_registry.jsonl` for this run), read the raw file from `raw_sources/`.
2. Identify extractable facts: prefer primary sources (official site, SEC filings, press releases) over secondary. Apply `references/source_priority_rules.md` for conflict triage.
3. For each extracted fact or fact-group, compose an `extracted_artifact` JSON document:
   - `artifact_id`: generate a new `art_` prefixed 16-hex-char ID.
   - `schema_version`: `"1.0"`.
   - `company_id`: `{slug}`.
   - `run_id`: `{run_id}`.
   - `artifact_type`: a descriptive type string (e.g. `"company_identity"`, `"leadership"`, `"headcount"`).
   - `source_id`: the `src_` ID from `source_registry.jsonl`.
   - `original_format`: MIME type of the raw source.
   - `retrieved_at`: ISO8601 UTC timestamp from the `retrieved` registry event.
   - `extracted_at`: current ISO8601 UTC timestamp.
   - `confidence`: a float 0–1 reflecting extraction confidence.
   - `lineage`:
     - `source_snapshot_id`: the `event_id` of the `retrieved` event in `source_registry.jsonl`.
     - `content_path`: relative path to the raw source file (e.g. `raw_sources/{filename}`).
     - `locator`: an object identifying the specific location within the source (e.g. `{"page": 1, "section": "About"}` or `{"url_fragment": "#leadership"}`).
     - `snippet`: a verbatim text excerpt (≥1 non-whitespace char) from the source that supports this extraction.
     - `extraction_prompt`: `{"name": "evidence_extraction", "version": "1.0"}`.
   - `value`: the structured fact payload (object; schema is artifact-type-specific).
   - `notes`: any caveats, or `null`.
4. Write the document to `output/companies/{slug}/runs/{run_id}/structured/{artifact_id}.json`.
5. Record an `extracted` event in the artifact registry:
   ```
   python scripts/update_artifact_registry.py \
     --log output/companies/{slug}/artifact_registry.jsonl \
     --run-id {run_id} --artifact-id {artifact_id} --event-type extracted \
     --event-time {ISO} \
     --payload '{"artifact_type":"...","source_id":"...","content_path":"structured/{artifact_id}.json"}'
   ```
6. If conflicting values are found across sources for the same fact, do NOT silently pick one. Emit a `conflict_set` in `notes` listing each candidate with its `source_id` and value.

## Output contract
One or more `extracted_artifact` JSON files in `structured/`, each validating against the `extracted_artifact` schema with a complete `lineage` block (all five required fields). Corresponding `extracted` events in `artifact_registry.jsonl`.

## Hard rules
Obey all rules in `references/anti_hallucination_rules.md`: if a fact is absent from the source, set the field to `null` — never invent a value. Never copy from memory or training data. Separate extracted evidence from inference; tag inferences as `[INFERENCE]` in `notes`.

## Hand-off
`evidence_validation.md` validates all `structured/` artifacts. `dossier_generation.md` cites artifact IDs from this set.
