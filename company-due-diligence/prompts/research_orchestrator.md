# Research Orchestrator

## Goal
Select which sub-prompts to run for the given `mode`, sequence the 7-step workflow, and enforce the invariants that a run must be created before any work begins and that validation must pass before the dossier is published.

## Inputs
company name (required), optional website / ticker / country / industry / aliases, `mode` (one of: `full_refresh`, `incremental_refresh`, `source_discovery_only`, `source_retrieval_only`, `extraction_only`, `validation_only`, `dossier_only`, `compare_runs`).

## Procedure
1. **Create run** — always the first step regardless of mode:
   ```
   python scripts/create_run.py --company "<NAME>" --mode <MODE>
   ```
   Record the returned `run_id` and `company_slug`. Every subsequent script call uses these values.
2. **Build run plan** — map `mode` to the sub-prompts to execute:
   - `full_refresh`: steps 3–7 (discover → retrieve → all extractions → validate → compare → dossier)
   - `incremental_refresh`: steps 3–7 (same, but retrieval targets only changed/new sources)
   - `source_discovery_only`: step 3 only
   - `source_retrieval_only`: steps 3–4 (discover if no prior discovery, then retrieve)
   - `extraction_only`: steps 5–6 (extract from already-retrieved raw sources)
   - `validation_only`: step 7 only
   - `dossier_only`: steps 7–8 (validate then render dossier)
   - `compare_runs`: step 9 (compare + change log) after confirming both runs exist
3. **Discover** — invoke `source_discovery.md` to enumerate candidate sources.
4. **Retrieve** — invoke `source_retrieval.md` to fetch raw bytes and record hash events.
5. **Extract** — invoke the relevant extraction prompts in parallel where safe:
   - `evidence_extraction.md` (generic facts)
   - `product_extraction.md`
   - `financial_extraction.md`
   - `corporate_structure_extraction.md`
   - `market_intelligence.md`
   - `risk_extraction.md`
   - `event_extraction.md`
6. **Merge** (if financials or products present):
   ```
   python scripts/merge_artifacts.py --run-dir output/companies/{slug}/runs/{run_id}
   ```
   Surface any conflicts for downstream dossier use.
7. **Validate** — invoke `evidence_validation.md`. Block on FAIL before publishing.
8. **Compare** (re-runs only) — invoke `run_comparison.md` to produce `change_log.md`.
9. **Dossier** — invoke `dossier_generation.md` only after validation passes.

## Output contract
A run plan document (in-context) listing: `run_id`, `company_slug`, `mode`, ordered list of sub-prompts to execute, known gaps, and any mode-specific skips. No files are written by this prompt directly.

## Hard rules
- Never begin step 3 or later without a valid `run_id` from step 1.
- Never publish to `latest/` if validation returned FAIL.
- Follow `references/research_methodology.md` to determine research depth per mode.
- Respect `references/source_priority_rules.md` when sequencing discovery and retrieval.

## Hand-off
Each selected sub-prompt receives `run_id`, `company_slug`, and the input parameters.
