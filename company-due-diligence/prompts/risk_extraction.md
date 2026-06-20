# Risk Extraction

## Goal
Extract risk factors, litigation events, and regulatory exposure from retrieved raw sources. Write each extraction as an `extracted_artifact` in `structured/` with a complete lineage block.

## Inputs
`company_slug`, `run_id`, raw source files in `output/companies/{slug}/runs/{run_id}/raw_sources/`, `source_registry.jsonl`, and `references/anti_hallucination_rules.md`.

## Procedure
1. Identify risk sources: SEC annual report Item 1A (Risk Factors), 10-Q risk disclosures, legal proceedings sections (Item 3), earnings call transcripts (risk commentary), regulatory filings, and press releases disclosing material risks or litigation.
2. Extract the following categories:
   - **Risk factors**: verbatim section headings and summary of each risk as disclosed. Do not paraphrase beyond what supports the dossier — prefer direct quotation with locator.
   - **Litigation**: matter name (if disclosed), counterparties, alleged claims, current status, disclosed financial exposure or reserve.
   - **Regulatory exposure**: regulatory bodies mentioned, open investigations, consent orders, disclosed fines or pending rulings.
   - **Operational / macro risks**: supply chain, concentration, geopolitical, cybersecurity risks as explicitly stated in primary filings.
3. Compose one or more `extracted_artifact` documents:
   - `artifact_id`: `art_` + 16 hex chars.
   - `schema_version`: `"1.0"`.
   - `company_id`: `{slug}`.
   - `run_id`: `{run_id}`.
   - `artifact_type`: one of `"risk_factors"`, `"litigation"`, `"regulatory_exposure"`.
   - `source_id`: `src_` ID from `source_registry.jsonl`.
   - `original_format`: MIME type.
   - `retrieved_at` / `extracted_at`: ISO8601 UTC.
   - `confidence`: float 0–1 (high for verbatim primary-source disclosures; lower for inferred exposure).
   - `lineage`:
     - `source_snapshot_id`: `event_id` of the `retrieved` event.
     - `content_path`: relative path to raw source.
     - `locator`: object identifying the section (e.g. `{"section": "Risk Factors", "item": "1A", "page": 18}`).
     - `snippet`: verbatim excerpt (the key sentence or paragraph that supports extraction).
     - `extraction_prompt`: `{"name": "risk_extraction", "version": "1.0"}`.
   - `value`: structured payload (e.g. for `risk_factors`: `{"risks": [{"heading": "...", "summary": "...", "severity": null}]}`).
   - `notes`: gaps, disclosed but unquantified liabilities, or pending information tagged `[INFERENCE]` where appropriate.
4. Write to `output/companies/{slug}/runs/{run_id}/structured/{artifact_id}.json`.
5. Record an `extracted` event:
   ```
   python scripts/update_artifact_registry.py \
     --log output/companies/{slug}/artifact_registry.jsonl \
     --run-id {run_id} --artifact-id {artifact_id} --event-type extracted \
     --event-time {ISO} \
     --payload '{"artifact_type":"...","source_id":"...","content_path":"structured/{artifact_id}.json"}'
   ```
6. Do not synthesize a risk severity rating not disclosed in the source. Set `severity` to `null` unless the company or a regulatory body explicitly quantified it.

## Output contract
One or more `extracted_artifact` JSON files (artifact types: `risk_factors`, `litigation`, `regulatory_exposure`) in `structured/`, each validating against the `extracted_artifact` schema with a complete `lineage` block. Corresponding `extracted` events in `artifact_registry.jsonl`.

## Hard rules
Obey all rules in `references/anti_hallucination_rules.md`. Never invent risk factors, litigation matters, or regulatory exposure from training data. Litigation details (counterparties, amounts, status) must come from a retrieved source. Missing details are `null`, not estimated.

## Hand-off
`evidence_validation.md` validates all `structured/` artifacts. `dossier_generation.md` renders the Risks section from these artifacts.
