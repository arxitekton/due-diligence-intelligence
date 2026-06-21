# Company Due Diligence

## Purpose

A reusable, refreshable, versioned **research corpus system** for company due-diligence and
market-intelligence work. Each execution produces an immutable run directory containing raw
sources, extracted artifacts, validated structured records, and a dossier — all with full
provenance lineage. Re-runs detect, classify, and log what changed since the previous run.
The system is designed for repeated use over a company's lifecycle, not one-shot report
generation: registries accumulate cross-run history, `latest/` always points to the current
best version, and tombstones prevent silent source drops.

---

## Installation

```bash
# Core package (scripts + validation)
uv venv && uv pip install -e ".[dev]"

# Optional extraction stack (PDF, HTML, EDGAR)
uv pip install -e ".[extract]"
```

Activate as a Claude Code skill (symlinks into `~/.claude/skills/`):

```bash
python scripts/install_skill.py   # lands in P3.7
```

---

## Usage Examples

### 7-Step Workflow

| Step | Script / Prompt |
|------|----------------|
| 1. Create run | `scripts/create_run.py` |
| 2. Discover sources | `prompts/source_discovery.md` → `scripts/update_source_registry.py` |
| 3. Retrieve & hash | agent retrieval → `scripts/compute_hashes.py` |
| 4. Extract & register | `prompts/{evidence,product,financial,...}_extraction.md` → `scripts/update_artifact_registry.py` |
| 5. Validate | `scripts/validate_outputs.py` |
| 6. Compare runs | `scripts/compare_runs.py` + `scripts/generate_change_log.py` |
| 7. Dossier | `prompts/dossier_generation.md` |

### Create a run

```bash
python scripts/create_run.py \
  --company "Acme Analytics" \
  --mode full_refresh
# → run_id: 20260621T120000Z-f3e2d1   company_slug: acme-analytics
# (create_run accepts --company, --mode, --root, --token; richer inputs such as
#  website/ticker/exchange are provided to the agent as research context, not CLI flags.)
```

### Validate outputs

```bash
python scripts/validate_outputs.py \
  --company-id acme-analytics \
  --run-id 20260621T120000Z-f3e2d1 \
  --mode full_refresh \
  --now 2026-06-21T12:00:00Z
```

---

## Run Modes

| Mode | Description |
|------|-------------|
| `full_refresh` | Rediscover and re-retrieve all sources; full extraction pipeline |
| `incremental_refresh` | Retrieve only changed or new sources (hash-gated); update affected artifacts |
| `source_discovery_only` | Discover and register sources; no retrieval or extraction |
| `source_retrieval_only` | Retrieve and hash registered sources; no extraction |
| `extraction_only` | (Re-)extract from already-retrieved raw sources |
| `validation_only` | Run all 8 fatal gates against an existing run directory |
| `dossier_only` | Regenerate dossier from current validated artifacts; no upstream steps |
| `compare_runs` | Diff two run directories; emit change log |

---

## Output Structure

```
output/companies/{slug}/
├── runs/{run_id}/
│   ├── raw_sources/              # verbatim downloaded files (HTML, PDF, JSON)
│   ├── raw_artifacts/            # raw extraction outputs before structuring
│   ├── extracted_tables/         # source-native tables preserved verbatim
│   ├── structured/               # schema-validated artifacts (one JSON each),
│   │   ├── *.json                #   plus source_inventory.json (derived) and
│   │   └── _merged.json          #   _merged.json (merge output; skipped as non-artifact)
│   ├── reports/                  # reserved for agent-authored intermediate reports
│   ├── logs/
│   ├── run_manifest.json         # this run's manifest (incl. reproducibility block)
│   ├── final_dossier.md          # rendered dossier (run-dir root, not reports/)
│   ├── final_dossier.json        # machine-readable dossier (validates company_dossier)
│   ├── change_log.md             # cross-run diff (compare_runs → generate_change_log)
│   ├── data_quality_report.md    # validate_outputs gate results (human-readable)
│   └── data_quality_report.json  # validate_outputs report (machine-readable)
├── source_registry.jsonl         # append-only source event log (all runs)
├── artifact_registry.jsonl       # append-only artifact event log (all runs)
├── manifest.json                 # derived company-level current-state index
├── latest/                       # flat COPIES of the last validated run's published
│                                 #   files (final_dossier.*, data_quality_report.*,
│                                 #   change_log.md, source_inventory.json, run_manifest.json)
└── history/{run_id}.json         # one published-run record per run
```

---

## Refresh Strategy

**Full refresh** rediscovers and re-retrieves every source from scratch. Use for first runs,
forced checkpoints (at least every 6 months for active companies), or when source topology
may have changed significantly.

**Incremental refresh** retrieves only sources where `diff_class` indicates the content hash
has changed since last retrieval. Unmodified sources reuse prior raw files. Artifacts are
re-extracted only for sources that changed.

**Tombstones / no silent drops**: the `refresh_semantics` fatal gate enforces that every
source marked `active` or `reappeared` in the registry appears in the current run's
inventory. A source that was previously tracked and is now absent without an explicit
`unavailable` marker fails validation. This prevents discovery drift from silently eroding
coverage.

**Change classification** (`compare_runs`): each delta is classified as a source-level change
(new/dropped/unavailable source), extraction-level change (artifact content diff for the same
source), or schema-level change (field added/removed/type-changed in a structured record).
The output is a `change_log.md` with human-readable delta summaries and a machine-readable
diff payload.

---

## Data Quality Rules

Eight fatal gates run via `scripts/validate_outputs.py`. A run that fails any gate must not
be published to `latest/` or used to generate a dossier.

| Gate | Description |
|------|-------------|
| `schemas_valid` | Every structured artifact validates against its registered JSON Schema |
| `referential_integrity` | All `source_id` and `artifact_id` cross-references resolve within the run |
| `lineage_complete` | All five lineage fields (source_snapshot_id, content_path, snippet, locator, extraction_prompt) non-empty on every artifact; every `fact`/`evidence` claim cited |
| `id_integrity` | `artifact_id` values are unique across the run (no collision/retry duplicates) |
| `financial_usability` | Every `financial_artifact` line item has scope, cell_locator, valid period ref, no duplicate tuples |
| `manifest_closure` | Every path declared in `run_manifest.output_paths` exists on disk |
| `refresh_semantics` | (incremental only) No previously-active source silently absent from current inventory |
| `conflict_visibility` | Financial and product conflicts (`merge_financials` + `merge_products`) surfaced in `data_quality_report` |

Non-fatal flags (recorded but do not block): stale sources, low-confidence extractions
(<0.5), missing expected source classes.

Full rule definitions: [`references/data_quality_rules.md`](references/data_quality_rules.md)  
Anti-hallucination constraints: [`references/anti_hallucination_rules.md`](references/anti_hallucination_rules.md)

---

## Limitations

- **Agent-driven retrieval**: scripts never hit the network. The Claude Code agent performs
  all HTTP retrieval. Autonomous crawling requires an active agent session.
- **ToS / robots compliance**: retrieval follows [`references/legal_and_tos.md`](references/legal_and_tos.md).
  No paywall bypass; paywalled sources are logged as `unavailable`.
- **Extraction tools are optional**: the `[extract]` extra (PDF, HTML, EDGAR helpers)
  improves reliability but is not required. Without it, the agent performs extraction
  directly from raw content.
- **`manifest_closure` checks existence, not content hash**: the gate verifies that declared
  output paths exist on disk but does not recompute file hashes at validation time. This is a
  documented gap; hash recomputation is deferred to a future gate version.

---

## Recommended Workflow

### First run

1. `create_run.py --mode full_refresh` — note `run_id` and `company_slug`
2. Run `prompts/source_discovery.md`; register each source via `update_source_registry.py`
3. Retrieve raw files (agent); run `compute_hashes.py`
4. Run extraction prompts in order: evidence → product → financial → corporate structure → risk → events
5. Register each artifact via `update_artifact_registry.py`
6. `validate_outputs.py` — fix any fatal gate failures; re-run in `validation_only` mode
7. `prompts/dossier_generation.md` → render `final_dossier.{md,json}`

### Refresh run

1. `create_run.py --mode incremental_refresh`
2. Retrieve changed/new sources only; run `compute_hashes.py`
3. Re-extract artifacts for changed sources
4. `validate_outputs.py` — confirm `refresh_semantics` gate passes
5. `compare_runs.py` + `generate_change_log.py` to classify deltas
6. `prompts/dossier_generation.md` — render updated dossier from current-run artifacts only

---

## Examples

Working examples live in [`examples/`](examples/):

| File | Contents |
|------|----------|
| `example_input.md` | Annotated input spec for a first run |
| `example_output_structure.md` | Annotated `output/` directory tree |
| `example_source_registry.jsonl` | Sample source registry events |
| `example_artifact_registry.jsonl` | Sample artifact registry events |
| `example_run_manifest.json` | Sample run manifest |
