# Dossier Generation

## Goal
Assemble the final due-diligence dossier from CURRENT validated artifacts only, render it as `final_dossier.md` and `final_dossier.json`, and publish to `latest/` if and only if validation has passed.

## Inputs
`company_slug`, `run_id`, all validated `structured/` artifacts, `data_quality_report.json` (must show `passed: true`), `source_registry.jsonl`, `artifact_registry.jsonl`, `change_log.md` (if this is a re-run), and `references/anti_hallucination_rules.md`.

## Procedure
1. **Pre-flight check** — confirm `data_quality_report.json` exists and `passed == true`. If not, abort and return the validation failure to the caller. Do not generate a dossier from a failed run.

2. **Build the run header** (included at the top of both output formats):
   - `run_id`, `research_date` (current ISO8601 UTC date), `retrieval_window` (earliest to latest `retrieved_at` across all artifacts).
   - Source counts: total discovered, retrieved, unavailable; counts by `source_class`.
   - Known gaps: source classes with zero retrieved sources; stale sources from `data_quality_report.json`.
   - Confidence summary: min/mean/max confidence across all artifacts; count of low-confidence artifacts.

3. **Assemble dossier sections** in this order, drawing exclusively from validated artifacts in `structured/`. Every claim must either cite at least one `artifact_id` or be tagged `[INFERENCE]`. Separate facts (directly supported by evidence), extracted evidence, and analysis/inference clearly.

   | # | Section | Primary artifact types |
   |---|---------|----------------------|
   | 1 | Executive Summary | all |
   | 2 | Company Identity | `company_identity`, `evidence_*` |
   | 3 | Source Coverage | run header + registry |
   | 4 | Corporate Structure | `corporate_structure` |
   | 5 | Ownership & Legal Entities | `corporate_structure` |
   | 6 | Products & Services | `product_artifact` |
   | 7 | Technology & IP | `extracted_artifact` (technology, patents) |
   | 8 | Customers & Markets | `customers`, `markets` |
   | 9 | Financials | `financial_artifact` |
   | 10 | Competitors | `competitors` |
   | 11 | Partnerships | `partnerships` |
   | 12 | M&A & Funding | `ma_event`, `funding_event` |
   | 13 | Risks | `risk_factors`, `litigation`, `regulatory_exposure` |
   | 14 | Recent Developments | `leadership_change`, `product_launch`, `material_development` |
   | 15 | Data Quality Notes | `data_quality_report.json` non-fatal reporters |
   | 16 | Change Summary Since Previous Run | `change_log.md` (if present) |
   | 17 | Appendices | source list, artifact index |

4. **Render `final_dossier.md`** — Markdown narrative with section headers. In-text citations use `[artifact_id]` format. Inferences are tagged `[INFERENCE]`.

5. **Render `final_dossier.json`** — must validate against the `company_dossier` schema. Structure:
   ```json
   {
     "run_id": "...",
     "company_id": "...",
     "generated_at": "...",
     "run_header": {...},
     "sections": [
       {
         "title": "...",
         "claims": [
           {"kind": "fact|evidence|inference", "text": "...", "citations": ["art_..."]}
         ]
       }
     ]
   }
   ```
   Claims of `kind: "fact"` or `kind: "evidence"` must have at least one citation. Claims of `kind: "inference"` may have an empty citations array but must be marked as such.

6. Write both files to `output/companies/{slug}/runs/{run_id}/`:
   - `final_dossier.md`
   - `final_dossier.json`

7. **Publish to `latest/`** — copy (or symlink) to `output/companies/{slug}/latest/` only after confirming `data_quality_report.json` shows `passed: true`:
   - `output/companies/{slug}/latest/final_dossier.md`
   - `output/companies/{slug}/latest/final_dossier.json`
   - `output/companies/{slug}/latest/run_manifest.json`
   - `output/companies/{slug}/latest/data_quality_report.json`

## Output contract
`final_dossier.md` and `final_dossier.json` in the run directory; `final_dossier.json` validates against the `company_dossier` schema. `latest/` updated only on PASS.

## Hard rules
Obey all rules in `references/anti_hallucination_rules.md`. Only draw from CURRENT run's validated artifacts — never from prior runs' artifacts or from training-data memory. Every factual claim cites an `artifact_id`. Missing information is represented as "Not disclosed" or "Data unavailable" — never fabricated. Separate facts / evidence / inference in every section. Never publish to `latest/` on a failed validation.

## Hand-off
The completed `final_dossier.md` and `final_dossier.json` are the primary deliverables returned to the user. `run_comparison.md` for the next re-run will compare against this run's artifacts.
