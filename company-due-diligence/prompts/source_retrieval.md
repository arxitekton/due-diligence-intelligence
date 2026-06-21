# Source Retrieval

## Goal
Fetch raw content for every source in `discovered` status, save bytes to `raw_sources/`, compute dual hashes, determine `diff_class`, and record `retrieved` / `canonicalized` / `unavailable` events in the source registry. Do NOT extract structured data yet.

## Inputs
`company_slug`, `run_id`, `source_registry.jsonl` (containing `discovered` events from `source_discovery.md`), and `references/legal_and_tos.md`.

## Procedure
1. Read `output/companies/{slug}/source_registry.jsonl` and collect all source IDs with status `discovered` (no subsequent `retrieved` or `unavailable` event in this run).
2. For each source, determine fetch method:
   - Web pages / HTML / JSON: agent web fetch.
   - SEC EDGAR filings: optional `cdd.extract.edgar` tool if available; otherwise agent web fetch.
   - PDFs: agent web fetch (binary).
   - Record `unavailable` if a source cannot be reached after reasonable retry:
     ```
     python scripts/update_source_registry.py \
       --log output/companies/{slug}/source_registry.jsonl \
       --run-id {run_id} --source-id {src} --event-type unavailable \
       --event-time {ISO} --payload '{"reason":"..."}'
     ```
3. Save raw bytes to `output/companies/{slug}/runs/{run_id}/raw_sources/{source_filename}`. Use a deterministic filename derived from `source_id` + extension (e.g. `{src_hex}.html`).
4. Compute hashes immediately after saving:
   ```
   python scripts/compute_hashes.py \
     --file output/companies/{slug}/runs/{run_id}/raw_sources/{source_filename} \
     --mime {mime_type}
   ```
   Note the `raw_hash`, `canonical_hash`, and `profile_id` returned.
5. Record `retrieved` event:
   ```
   python scripts/update_source_registry.py \
     --log output/companies/{slug}/source_registry.jsonl \
     --run-id {run_id} --source-id {src} --event-type retrieved \
     --event-time {ISO} \
     --payload '{"raw_hash":"...","content_path":"raw_sources/{filename}","mime_type":"...","byte_size":...}'
   ```
6. Record `canonicalized` event (includes `diff_class` relative to prior canonical hash if one exists in the registry):
   ```
   python scripts/update_source_registry.py \
     --log output/companies/{slug}/source_registry.jsonl \
     --run-id {run_id} --source-id {src} --event-type canonicalized \
     --event-time {ISO} \
     --payload '{"canonical_hash":"...","profile_id":"...","diff_class":"..."}'
   ```
   `diff_class` values: `new` (no prior), `unchanged`, `minor_change`, `major_change`.
7. After all sources are processed, log a retrieval summary: counts by status (`retrieved`, `unavailable`) and `diff_class`.

## Output contract
- Raw files in `output/companies/{slug}/runs/{run_id}/raw_sources/`.
- `retrieved`, `canonicalized`, and/or `unavailable` events appended to `source_registry.jsonl` (schema `source_registry`).
- No structured artifacts or extractions.

## Hard rules
Respect all constraints in `references/legal_and_tos.md` (robots.txt, rate limits, no login-walled content without authorization). Scripts never hit the network — only the agent fetches content. Do not fabricate content hashes.

## Hand-off
Extraction prompts (`evidence_extraction.md`, `product_extraction.md`, `financial_extraction.md`, `corporate_structure_extraction.md`, `market_intelligence.md`, `risk_extraction.md`, `event_extraction.md`) consume the `raw_sources/` files and the `source_registry.jsonl` to resolve `source_snapshot_id` for lineage.
