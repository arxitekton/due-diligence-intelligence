# Example Output Directory Structure

Annotated tree for a completed `full_refresh` run on Acme Analytics, Inc.
The company slug is `acme-analytics`; the run ID is `20260620T183000Z-a1b2c3`.

```
output/
└── companies/
    └── acme-analytics/                         # one directory per target company (slug)
        │
        ├── runs/
        │   └── 20260620T183000Z-a1b2c3/        # immutable directory per run; named by run_id
        │       ├── raw_sources/                 # verbatim downloaded source files (HTML, PDF, JSON)
        │       │   ├── src_4a7f3c9e2b1d8e6f.html
        │       │   └── src_9b3e7a1f5c2d6b0e.html
        │       ├── raw_artifacts/               # raw LLM extraction outputs before validation
        │       │   ├── art_1a2b3c4d5e6f7a8b.json
        │       │   └── art_2b3c4d5e6f7a8b9c.json
        │       ├── extracted_tables/            # tabular slices ready for merging (CSV or JSON)
        │       │   ├── financials.json
        │       │   └── management_team.json
        │       ├── structured/                  # merged + schema-validated structured records
        │       │   ├── company_profile.json     # core identity, legal name, ticker, industry
        │       │   ├── financials.json          # ARR, revenue, margins, burn — financial_artifact schema
        │       │   ├── management_team.json     # executives with tenure and prior exits
        │       │   └── competitors.json         # competitive landscape snapshot
        │       ├── reports/                     # human-readable outputs generated from structured/
        │       │   ├── final_dossier.md         # narrative summary for the analyst
        │       │   └── data_quality_report.md   # per-field coverage, confidence, and gap flags
        │       └── logs/
        │           ├── run.log                  # structured JSON log for the full run
        │           └── llm_traces.jsonl         # Langfuse-compatible LLM call traces
        │
        ├── final_dossier.md                     # symlink → latest run's final_dossier.md
        ├── final_dossier.json                   # structured equivalent of the dossier (for downstream tools)
        ├── change_log.md                        # human-readable diff across runs (new / changed / removed)
        ├── data_quality_report.md               # symlink → latest run's data_quality_report.md
        │
        ├── source_registry.jsonl                # append-only event log of all source events (all runs)
        ├── artifact_registry.jsonl              # append-only event log of all artifact events (all runs)
        ├── manifest.json                        # latest run_manifest (run_manifest schema)
        │
        ├── latest/                              # symlinks to every file in the most recent run
        │   ├── structured -> ../runs/20260620T183000Z-a1b2c3/structured/
        │   ├── reports    -> ../runs/20260620T183000Z-a1b2c3/reports/
        │   └── logs       -> ../runs/20260620T183000Z-a1b2c3/logs/
        │
        └── history/                             # lightweight index across all runs
            └── runs.json                        # array of {run_id, started_at, mode, artifacts_extracted}
```

## Notes

- `runs/` are **write-once** after a run completes; never mutate them for reproducibility.
- `source_registry.jsonl` and `artifact_registry.jsonl` are **append-only** across all runs.
- `latest/` uses directory symlinks so consumers always read the current best version without hardcoding a run ID.
- `history/runs.json` enables quick trend queries (e.g. "how many artifacts were extracted per run?") without scanning all run directories.
- `final_dossier.json` is the machine-readable counterpart to `final_dossier.md` and is the primary input for downstream analysis pipelines.
