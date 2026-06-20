# Provenance and Reproducibility

## What the Run Manifest Pins

Every run produces a `run_manifest.json` whose `reproducibility` block records all parameters that govern deterministic reproduction of the extraction and structuring results. A run is reproducible if and only if all fields in this block are non-null and the referenced artifacts are still available.

**`prompt_set_hash`** — SHA-256 (or equivalent) of the canonical serialization of the full prompt set used for all extraction steps in this run. If prompts change between runs, `prompt_set_hash` changes, and `compare_runs` will classify the delta as `extraction_delta`. A `null` value indicates the prompt set was not pinned; such a run is not reproducible.

**`schema_set_hash`** — SHA-256 of the canonical serialization of all JSON Schema files that governed validation in this run. Schema changes invalidate prior extraction results; `compare_runs` classifies a schema hash change as `schema_delta`. A `schema_delta` typically requires a `full_refresh` to re-extract under the new schema.

**`model_id`** — the exact model identifier used for all LLM extraction calls (e.g. `"claude-3-7-sonnet-20250219"`). Model version pinning is required for reproducibility; using a floating alias (e.g. `"claude-3-sonnet-latest"`) makes a run non-reproducible because the alias resolves to a different model over time.

**`tool_versions`** — a dict mapping each tool or library used during the run to its pinned version (e.g. `{"cdd": "0.4.1", "pdfplumber": "0.10.3", "trafilatura": "1.8.1"}`). Populated from the project's lock file (`uv.lock`) at run time. All tool versions must be pinned; floating versions make the run non-reproducible.

**`normalizer_profile_versions`** — a dict mapping each normalization profile (FX source, taxonomy mapping file, unit conversion table) to its version or hash. FX rates change daily; the FX source and date used must be recorded in the `financial_artifact.normalization` block AND referenced here for the run-level record.

**`locale`** — the locale setting governing number parsing, date parsing, and character encoding during the run (e.g. `"en-US"`). Locale affects parsing of numbers (decimal separator, thousand separator) and date formats. A run performed in a different locale may parse the same source differently.

**Search queries and result ranks** — the exact queries issued during the discovery phase and the result rank (position in the search result list) of each source that was selected must be recorded in the source registry events. This is part of provenance: knowing that a source was discovered at position 3 of a specific query allows the discovery step to be replicated. This information is stored in the source registry event log, not in the run manifest directly, but the run manifest's `run_id` links to the registry events.

---

## How `compare_runs` Separates Delta Types

`compare_runs` inspects the `reproducibility` blocks of two run manifests and the source inventories of both runs, then returns a `RunDiff` with a single `delta_type` classification:

**`source_delta`** — `prompt_set_hash`, `schema_set_hash`, and `model_id` are all identical between the two runs. Any differences in extracted artifacts are attributable to changes in the source content itself (new filings, updated pages, revised data). This is the expected delta type for a routine `incremental_refresh`. A `source_delta` with no changed sources indicates the world has not changed; a `source_delta` with many changed sources warrants review.

**`extraction_delta`** — `prompt_set_hash` or `model_id` has changed, but `schema_set_hash` is the same. Differences in extracted artifacts may be due to changes in the source content AND/OR changes in how the extraction model interprets the content. To isolate the extraction change from source change: run `extraction_only` mode on the same raw sources with the new prompt/model, then compare against the prior extraction.

**`schema_delta`** — `schema_set_hash` has changed. Schema changes may introduce, remove, or modify fields, which means artifacts from the two runs are not directly comparable field-by-field. A `schema_delta` requires manual review of the schema changelog to understand what changed, and typically necessitates a `full_refresh` to re-extract all artifacts under the new schema.

The classification is hierarchical: `schema_delta` takes priority over `extraction_delta`, which takes priority over `source_delta`. If `schema_set_hash` changed, it is always a `schema_delta` regardless of whether prompts also changed.

---

## Step-by-Step: Reproducing a Prior Run

To reproduce run `<run_id>` for company `<company_slug>`:

1. **Check out the pinned code version.** Retrieve the `tool_versions` dict from `run_manifest.reproducibility`. Install the exact versions using `uv sync` with the pinned `uv.lock` from the commit that produced the run, or manually pin each tool version listed.

2. **Restore the prompt set.** `prompt_set_hash` identifies the prompt set. If prompts are versioned in git, check out the commit whose prompt set hashes to this value. If prompts are stored externally, retrieve the version corresponding to the hash.

3. **Restore the schema set.** `schema_set_hash` identifies the schema version. Check out the commit or release tag whose schema files hash to this value. Verify by recomputing the hash over the schema directory.

4. **Confirm the model.** `model_id` must be the exact version used. If the model has been deprecated, exact reproduction may not be possible (record this as a provenance limitation).

5. **Restore the raw sources.** The raw bytes in `runs/<run_id>/raw_sources/` are the exact inputs to the extraction step. Do not re-fetch from the web; the live sources may have changed. Use the archived raw bytes.

6. **Restore the FX rates.** The `financial_artifact.normalization.fx_source` and `fx_date` fields identify the FX source and date. Retrieve the same rate from the same source for the same date. Many central bank rate feeds are archived; use the historical rate, not today's rate.

7. **Re-run extraction in `extraction_only` mode.** This skips discovery and retrieval and runs only the extraction and structuring steps over the archived raw sources:
   ```
   python scripts/validate_outputs.py --company-id <slug> --run-id <new_run_id> --mode extraction_only
   ```
   Use a new `run_id` for the reproduction attempt to avoid overwriting the original.

8. **Compare the reproduction against the original.** Run `compare_runs` between the original `run_id` and the new reproduction run. A `source_delta` with no differences in extracted artifacts confirms exact reproduction. Any difference with `extraction_delta` or `schema_delta` indicates a parameter mismatch; recheck steps 2–4.

9. **Record the reproduction attempt.** Add a note to the run manifest or the changelog documenting whether reproduction succeeded, any deviations (e.g. model deprecated, FX source unavailable for that date), and the new run_id of the reproduction attempt.

---

## Provenance Guarantees and Their Limits

The provenance system guarantees: given the same raw sources, the same prompt set, the same schema set, the same model version, the same tool versions, the same locale, and the same FX rates, the extraction and structuring output will be identical. It does not guarantee that the same output can be reproduced from a fresh web retrieval, because web sources change. The archive of raw sources in `runs/<run_id>/raw_sources/` is therefore a first-class research artifact that must not be deleted as long as the run's dossier is in use.

If raw sources are deleted, the run is no longer reproducible from its archived inputs. The dossier remains valid as a snapshot of what was true at retrieval time, but any challenge to the extraction requires re-retrieval and re-extraction, which is a new run, not a reproduction.
