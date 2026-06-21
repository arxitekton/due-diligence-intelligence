# Source Discovery

## Goal
Enumerate candidate sources for the company across primary → secondary → signal tiers, recording each as a discovery event. Do NOT retrieve content yet.

## Inputs
company_id (slug), run_id, input parameters (name, website, ticker, country, industry, aliases), and `references/source_priority_rules.md`.

## Procedure
1. Build a search plan covering each source class in priority order (official site, IR, filings/EDGAR, registries, patents/trademarks, then secondary, then signal).
2. The logical `source_id` is `URL + source_class`. Don't compute it by hand — pass `--url` and `--source-class` and the script derives it (or print it explicitly with `python scripts/source_id.py --url ... --source-class ...`).
3. Record a `discovered` event per source (id derived from `--url`/`--source-class`):
   `python scripts/update_source_registry.py --log output/companies/{slug}/source_registry.jsonl --run-id {run_id} --url "..." --source-class "..." --event-type discovered --event-time {ISO} --payload '{"url":"...","source_class":"...","source_priority":"...","title":"..."}'`
4. Stop when each tier is reasonably covered or the research focus is satisfied. Log gaps (classes with zero candidates).

## Output contract
Discovery events in `source_registry.jsonl` (schema `source_registry`). No artifacts yet.

## Hard rules
Prioritize per `references/source_priority_rules.md`. Respect `references/legal_and_tos.md`. Do not fabricate URLs — only record sources you actually located.

## Hand-off
`source_retrieval.md` consumes the discovered sources.
