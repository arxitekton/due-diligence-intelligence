# Source Discovery

## Goal
Enumerate candidate sources for the company across primary → secondary → signal tiers, recording each as a discovery event. Do NOT retrieve content yet.

## Inputs
company_id (slug), run_id, input parameters (name, website, ticker, country, industry, aliases), and `references/source_priority_rules.md`.

## Procedure
1. Build a search plan covering each source class in priority order (official site, IR, filings/EDGAR, registries, patents/trademarks, then secondary, then signal).
2. For each candidate, compute its logical `source_id` (URL + source_class) — the engine does this via `scripts/update_source_registry.py` from the URL+class you pass.
3. Record a `discovered` event per source:
   `python scripts/update_source_registry.py --log output/companies/{slug}/source_registry.jsonl --run-id {run_id} --source-id {src} --event-type discovered --event-time {ISO} --payload '{"url":"...","source_class":"...","source_priority":"...","title":"..."}'`
4. Stop when each tier is reasonably covered or the research focus is satisfied. Log gaps (classes with zero candidates).

## Output contract
Discovery events in `source_registry.jsonl` (schema `source_registry`). No artifacts yet.

## Hard rules
Prioritize per `references/source_priority_rules.md`. Respect `references/legal_and_tos.md`. Do not fabricate URLs — only record sources you actually located.

## Hand-off
`source_retrieval.md` consumes the discovered sources.
