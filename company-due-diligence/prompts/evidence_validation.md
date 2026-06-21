# Evidence Validation

## Goal
Run the 8 fatal evidentiary gates against all structured artifacts in the current run, read and interpret the resulting data-quality report, remediate fixable failures, and flag any remaining failures before the dossier is generated.

## Inputs
`company_slug`, `run_id`, all `structured/` artifacts, `source_registry.jsonl`, `artifact_registry.jsonl`, `run_manifest.json`, and `references/data_quality_rules.md`.

## Procedure
1. Run the validation script:
   ```
   python scripts/validate_outputs.py \
     --company-id {slug} \
     --run-id {run_id} \
     --mode {mode} \
     --now {ISO8601_UTC} \
     --root output
   ```
   The script writes two files:
   - `output/companies/{slug}/runs/{run_id}/data_quality_report.json` (machine-readable, validates against `data_quality_report` schema)
   - `output/companies/{slug}/runs/{run_id}/data_quality_report.md` (human-readable gate summary)
   It exits with code 0 (PASS) or 1 (FAIL).

2. Read `data_quality_report.json` and review the 8 fatal gates:
   - `schemas_valid`: every artifact in `structured/` must validate against its schema (`extracted_artifact`, `financial_artifact`, or `product_artifact`).
   - `referential_integrity`: every artifact's `source_id` must appear in the source inventory; every dossier citation must reference a known `artifact_id`.
   - `lineage_complete`: every artifact must have a complete `lineage` block (all 5 required fields populated); every dossier fact/evidence claim must cite ≥1 artifact.
   - `id_integrity`: no duplicate `artifact_id` values across the run.
   - `financial_usability`: every `financial_artifact` line item must have non-empty `cell_locator`, non-null `scope`, and a `column_ref` pointing to a period with `currency_reported` and `unit_scale`.
   - `manifest_closure`: every path in `run_manifest.output_paths` must exist on disk.
   - `refresh_semantics`: in `incremental_refresh` mode, no previously-active source may be silently dropped.
   - `conflict_visibility`: all financial conflicts are surfaced (passes by construction once conflicts are in the report).

3. For each FAIL gate, attempt remediation:
   - `schemas_valid` failure → fix the malformed artifact in `structured/` and re-run validation.
   - `lineage_complete` failure → add the missing lineage field or citation to the artifact.
   - `id_integrity` failure → resolve duplicate artifact IDs (assign a new unique ID to the duplicate and update the artifact registry).
   - `financial_usability` failure → add or correct the identified field in the financial artifact.
   - `referential_integrity` failure (dossier) → at this stage the dossier has not yet been generated; note the missing citation for `dossier_generation.md` to handle.

4. Re-run `validate_outputs.py` after each remediation cycle until PASS or until the failure is confirmed un-remediable (document why in `data_quality_report.md`).

5. Also review non-fatal reporters in the report:
   - `stale_sources`: sources with `last_seen_at` older than 180 days — note in dossier Data Quality section.
   - `low_confidence`: artifacts with confidence < 0.5 — flag in dossier.
   - `missing_source_classes`: expected primary source classes absent — note as gaps.

6. Record a `validated` event for each artifact that passes:
   ```
   python scripts/update_artifact_registry.py \
     --log output/companies/{slug}/artifact_registry.jsonl \
     --run-id {run_id} --artifact-id {artifact_id} --event-type validated \
     --event-time {ISO} \
     --payload '{"gate":"all_passed"}'
   ```

## Output contract
`data_quality_report.json` and `data_quality_report.md` written to the run directory, validating against the `data_quality_report` schema. Final state: PASS (all 8 fatal gates passed) or documented FAIL with remediation notes.

## Hard rules
Follow all rules in `references/data_quality_rules.md`. Never proceed to dossier generation if validation returns FAIL. Never manually edit `data_quality_report.json` to change gate status — fix the underlying artifact, then re-run validation. Never silently drop failing artifacts to achieve PASS.

## Hand-off
`dossier_generation.md` proceeds only after validation returns PASS. `run_comparison.md` may also use `data_quality_report.json` to qualify the change log.
