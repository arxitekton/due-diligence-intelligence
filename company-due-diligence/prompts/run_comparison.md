# Run Comparison

## Goal
Compare the current run against a prior run to identify what changed in sources, extracted artifacts, and schemas. Generate `change_log.md` and populate the "Change Summary Since Previous Run" section of the dossier.

## Inputs
`company_slug`, `from_run_id` (prior run), `to_run_id` (current run), both run directories under `output/companies/{slug}/runs/`, and `references/provenance_and_reproducibility.md`.

## Procedure
1. Identify the prior run to compare against:
   - If the user specifies `--from-run`, use that `run_id`.
   - Otherwise use the most recent prior run (check `output/companies/{slug}/history/` or `source_registry.jsonl` for prior `run_id` values).
   - If no prior run exists, skip comparison and note "First run — no prior run to compare".

2. Run the comparison script:
   ```
   python scripts/compare_runs.py \
     --company-id {slug} \
     --from-run {from_run_id} \
     --to-run {to_run_id} \
     --root output
   ```
   This outputs a JSON diff to stdout with three delta categories:
   - `source_delta`: sources added, removed, or changed (`diff_class` changed from prior `canonical_hash`).
   - `extraction_delta`: artifacts added, removed, superseded, or with changed `value`.
   - `schema_delta`: artifact types or schema versions that appeared or disappeared.

3. Generate the Markdown change log:
   ```
   python scripts/generate_change_log.py \
     --company-id {slug} \
     --from-run {from_run_id} \
     --to-run {to_run_id} \
     --now {ISO8601_UTC} \
     --root output
   ```
   This writes `output/companies/{slug}/runs/{to_run_id}/change_log.md` and prints the output path.

4. Read `change_log.md` and summarize the three delta categories for the dossier "Change Summary Since Previous Run" section:
   - **Source delta**: N sources added, M removed, K changed (list changed sources with their `diff_class`).
   - **Extraction delta**: N artifacts added (new data), M artifacts updated (value changed), K artifacts removed (source no longer available).
   - **Schema delta**: any new or removed artifact types; any schema version changes.

5. Flag high-signal changes explicitly:
   - Any financial line-item value change (amount, period, currency).
   - Any change in corporate structure (new/removed entities).
   - Any new M&A, funding, or leadership-change events.
   - Any source that was active in the prior run and is now `unavailable`.

6. If `data_quality_report.json` is available for both runs, compare `passed` status and notable gate results across runs; note any regressions or improvements.

## Output contract
`change_log.md` written to `output/companies/{slug}/runs/{to_run_id}/change_log.md`. An in-context structured summary of `source_delta`, `extraction_delta`, and `schema_delta` for use in `dossier_generation.md`.

## Hard rules
Follow all rules in `references/provenance_and_reproducibility.md`. Never modify prior run artifacts — comparison is read-only on `from_run`. Never overwrite `change_log.md` from a prior comparison — each run has its own. Report differences exactly as computed by `compare_runs.py`; do not editorialize or minimize changes.

## Hand-off
`dossier_generation.md` reads `change_log.md` to render the "Change Summary Since Previous Run" section (section 16).
