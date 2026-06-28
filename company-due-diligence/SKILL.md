---
name: company-due-diligence
description: Exhaustive, refreshable, versioned company due-diligence and market-intelligence research. Use when asked to research/profile a company, build a due-diligence dossier, track what changed since a prior run, or extract a company's products, financials, corporate structure, competitors, risks, or recent developments from primary sources. Triggers on "due diligence", "company profile/dossier", "market intelligence", "research <company>", or refresh/compare requests. For in-depth, cited research that warrants preserved evidence — not quick one-paragraph company blurbs or live price quotes.
---

# Company Due Diligence

A research **corpus** system, not a one-shot report. Discover → preserve evidence → extract artifacts → structure → validate → generate dossier. Every run is versioned and reproducible; re-runs detect and record what changed.

## When to activate
Activate when the user asks to research/profile/do due-diligence on a company, refresh an existing dossier, or compare runs. Inputs: company name (required); optional website, country, industry, ticker/exchange, legal name, subsidiaries/brands, research focus, run mode.

## Run modes
`full_refresh` · `incremental_refresh` · `source_discovery_only` · `source_retrieval_only` · `extraction_only` · `validation_only` · `dossier_only` · `compare_runs`.

## Workflow
Run-relative paths below are under `output/companies/{company_slug}/`.

1. **Create run** — `python scripts/create_run.py --company "<NAME>" --mode <MODE>`. Note the `run_id` + `company_slug`.
2. **Discover** — follow `prompts/source_discovery.md`; prioritize sources per `references/source_priority_rules.md`. Record each as a registry event (`scripts/update_source_registry.py`).
3. **Retrieve & preserve** — save raw bytes to `runs/{run_id}/raw_sources/`; hash with `scripts/compute_hashes.py` (raw + canonical → `diff_class`). Respect `references/legal_and_tos.md`.
4. **Extract** — per `prompts/{evidence,product,financial,corporate_structure,risk,event}_extraction.md`, `prompts/market_intelligence.md`, and `prompts/sanctions_screening.md` (REQUIRED for `full_refresh`/`incremental_refresh`; run after corporate-structure extraction so the entity graph is available); preserve source-native tables/taxonomies/line-items FIRST. Write structured artifacts (with full lineage) to `runs/{run_id}/structured/`; record `scripts/update_artifact_registry.py`.
5. **Build source inventory** — `python scripts/build_source_inventory.py --company-id <slug> --run-id <id> --now <ISO>` (derived from the registry; required by validation & compare_runs; writes `structured/source_inventory.json`).
6. **Validate** — `python scripts/validate_outputs.py --company-id <slug> --run-id <id> --mode <MODE> --now <T>` (evidentiary gates). Fix or flag before publishing.
7. **Compare (re-runs)** — `scripts/compare_runs.py` + `scripts/generate_change_log.py`.
8. **Dossier** — follow `prompts/dossier_generation.md`; render `final_dossier.{md,json}` from CURRENT validated artifacts only. Publish to `latest/` only after validation passes.

## Hard rules
- **Never invent data.** Missing → `null`/`unknown`. See `references/anti_hallucination_rules.md`.
- **Cite everything.** Every dossier claim cites `artifact_id`(+locator) or is tagged `[INFERENCE]`. Separate facts / extracted evidence / analysis.
- **Preserve originals before normalizing** — raw tables, native product taxonomies, native financial line items.
- **Never resolve conflicts silently** — emit a `conflict_set`.
- **Never overwrite prior runs.** Only `latest/`, registries, indexes, manifests update.
- **Scripts never hit the network**; the agent (you) does retrieval. Optional extraction tools under the `extract` extra add reliability for PDFs/EDGAR/HTML and provide source connectors: multi-list sanctions screening (OFAC/EU/UK-FCDO/BIS/UN — UN is ingest-to-screen only), GLEIF LEI (`cdd.extract.gleif`), UK Companies House (`cdd.extract.companies_house`), GDELT adverse-media (`cdd.extract.gdelt`), economic indicators (`cdd.extract.econ` — BLS, World Bank, Eurostat, OECD), Wikidata entity enrichment (`cdd.extract.wikidata`), and open national company registries (`cdd.extract.registries` — NO/CZ/FI/EE). See `references/open_data_sources.md`.
- **Sanctions:** a hit requires an exact official list entry — record list name, programme, entry_id, matched entity, match_type, and the list's as-of date. "No match" must state which lists were screened + as-of dates; never render as "clean" or "not sanctioned." Rescreen every run.

## Detailed guidance
Prompts: [orchestrator](prompts/research_orchestrator.md) · [discovery](prompts/source_discovery.md) · [retrieval](prompts/source_retrieval.md) · [evidence](prompts/evidence_extraction.md) · [product](prompts/product_extraction.md) · [financial](prompts/financial_extraction.md) · [corporate structure](prompts/corporate_structure_extraction.md) · [market intel](prompts/market_intelligence.md) · [risk](prompts/risk_extraction.md) · [events](prompts/event_extraction.md) · [sanctions](prompts/sanctions_screening.md) · [validation](prompts/evidence_validation.md) · [dossier](prompts/dossier_generation.md) · [run comparison](prompts/run_comparison.md).
References: [methodology](references/research_methodology.md) · [source priority](references/source_priority_rules.md) · [data quality](references/data_quality_rules.md) · [anti-hallucination](references/anti_hallucination_rules.md) · [sanctions rules](references/sanctions_screening_rules.md) · [financial rules](references/financial_extraction_rules.md) · [product rules](references/product_extraction_rules.md) · [legal/ToS](references/legal_and_tos.md) · [provenance](references/provenance_and_reproducibility.md) · [open data sources](references/open_data_sources.md).
