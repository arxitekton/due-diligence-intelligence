# Corporate Structure Extraction

## Goal
Extract entities, ownership relationships, subsidiaries, and business units from retrieved raw sources. Write each extraction as an `extracted_artifact` with `artifact_type` of `corporate_structure` in `structured/` with a complete lineage block.

## Inputs
`company_slug`, `run_id`, raw source files in `output/companies/{slug}/runs/{run_id}/raw_sources/`, `source_registry.jsonl`, and `references/anti_hallucination_rules.md`.

## Procedure
1. Identify corporate-structure sources: SEC annual report Exhibit 21 (subsidiaries list), company registration documents, registry filings (Companies House, state SOS, etc.), official IR/annual-report organizational charts.
   **Entity-resolution aids (optional, under the `extract` extra):** to confirm/normalise legal names and surface parent links before recording entities, `cdd.extract.gleif` (`search_by_name`) resolves names to LEI records (canonical legal name, jurisdiction, status, GLEIF L1/L2 parent), and `cdd.extract.wikidata` (`search_entities` → Q-id, then `get_entity_facts`) cross-checks LEI/ISIN, official website, country, industry, and `parent_organization`. Set `CDD_HTTP_USER_AGENT` first. GLEIF is regulator-curated (treat LEI/parent as reference-grade); Wikidata is `knowledge_graph` SIGNAL tier (crowd-sourced — verify against a primary source before asserting as fact). For direct national-registry verification, `cdd.extract.registries` looks up official open registers (Tier-1 `company_registry`): `search_brreg` (NO), `lookup_ares` (CZ, by IČO), `search_prh` (FI), `search_ariregister` (EE) → canonical name, registration number, status, address. These corroborate identity only; they do NOT establish ownership percentages.
2. For each source, extract:
   - **Legal entities**: registered name, jurisdiction, registration number (if available), entity type (corporation, LLC, Ltd, etc.), relationship to parent (wholly-owned subsidiary, partially-owned, affiliate, branch, division).
   - **Ownership stakes**: percentage ownership, direct vs. indirect, any known encumbrances.
   - **Business units / segments**: name as reported by the company, segment reporting classification.
   - **Known changes**: entity formations, dissolutions, or acquisitions within the reporting period (cross-reference `event_extraction.md` for M&A).
3. Compose one or more `extracted_artifact` documents:
   - `artifact_id`: generate a new `art_` prefixed 16-hex-char ID.
   - `schema_version`: `"1.0"`.
   - `company_id`: `{slug}`.
   - `run_id`: `{run_id}`.
   - `artifact_type`: `"corporate_structure"`.
   - `source_id`: the `src_` ID from `source_registry.jsonl`.
   - `original_format`: MIME type of the raw source.
   - `retrieved_at` / `extracted_at`: ISO8601 UTC timestamps.
   - `confidence`: float 0–1 (lower if derived from secondary sources or partial disclosures).
   - `lineage`:
     - `source_snapshot_id`: `event_id` of the `retrieved` event.
     - `content_path`: relative path to the raw source file.
     - `locator`: object identifying location (e.g. `{"exhibit": "21", "page": 88}`).
     - `snippet`: verbatim excerpt listing subsidiaries or entities.
     - `extraction_prompt`: `{"name": "corporate_structure_extraction", "version": "1.0"}`.
   - `value`: structured payload, e.g.:
     ```json
     {
       "entities": [{"name": "...", "jurisdiction": "...", "entity_type": "...", "relationship": "...", "ownership_pct": null}],
       "segments": [{"name": "...", "description": "..."}]
     }
     ```
   - `notes`: gaps, partial disclosures, or inferred relationships tagged `[INFERENCE]`.
4. Write the document to `output/companies/{slug}/runs/{run_id}/structured/{artifact_id}.json`.
5. Record an `extracted` event:
   ```
   python scripts/update_artifact_registry.py \
     --log output/companies/{slug}/artifact_registry.jsonl \
     --run-id {run_id} --artifact-id {artifact_id} --event-type extracted \
     --event-time {ISO} \
     --payload '{"artifact_type":"corporate_structure","source_id":"...","content_path":"structured/{artifact_id}.json"}'
   ```
6. When ownership percentages are contested or absent, set to `null` and note the discrepancy — do not estimate.

## Output contract
One or more `extracted_artifact` JSON files (with `artifact_type: "corporate_structure"`) in `structured/`, each validating against the `extracted_artifact` schema with a complete `lineage` block. Corresponding `extracted` events in `artifact_registry.jsonl`.

## Hard rules
Obey all rules in `references/anti_hallucination_rules.md`. Never invent ownership percentages, jurisdiction registrations, or entity names not present in a retrieved source. Unknown fields must be `null`. Inferences must be tagged `[INFERENCE]` in `notes`. Entity-resolution helpers (`cdd.extract.gleif`, `cdd.extract.wikidata`) corroborate identity only — never source an ownership percentage from them, and treat Wikidata facts as signal-tier (verify against a filed source before asserting).

## Hand-off
`evidence_validation.md` validates all `structured/` artifacts. `dossier_generation.md` renders the Corporate Structure and Ownership/Legal Entities sections from these artifacts.
