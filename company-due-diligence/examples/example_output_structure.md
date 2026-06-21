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
        │       ├── raw_artifacts/               # raw extraction outputs before structuring
        │       ├── extracted_tables/            # source-native tables preserved verbatim
        │       ├── structured/                  # schema-validated artifacts (one JSON each)
        │       │   ├── company_profile.json     # extracted_artifact
        │       │   ├── financials.json          # financial_artifact schema
        │       │   ├── management_team.json     # extracted_artifact (artifact_type=leadership)
        │       │   ├── competitors.json         # extracted_artifact
        │       │   ├── source_inventory.json    # DERIVED per-run inventory (build_source_inventory)
        │       │   └── _merged.json             # merge_artifacts output (skipped as a non-artifact)
        │       ├── reports/                     # reserved for agent-authored intermediate reports
        │       ├── logs/
        │       ├── run_manifest.json            # this run's manifest (incl. reproducibility block)
        │       ├── final_dossier.md             # rendered dossier (run-dir root, NOT under reports/)
        │       ├── final_dossier.json           # machine-readable dossier (company_dossier schema)
        │       ├── change_log.md                # cross-run diff (compare_runs → generate_change_log)
        │       ├── data_quality_report.md       # validate_outputs gate results (human-readable)
        │       └── data_quality_report.json     # validate_outputs report (data_quality_report schema)
        │
        ├── source_registry.jsonl                # append-only event log of all source events (all runs)
        ├── artifact_registry.jsonl              # append-only event log of all artifact events (all runs)
        ├── manifest.json                        # derived company-level current-state index
        │
        ├── latest/                              # flat COPIES of the last validated run's published files
        │   ├── final_dossier.md
        │   ├── final_dossier.json
        │   ├── data_quality_report.md
        │   ├── change_log.md
        │   ├── source_inventory.json
        │   └── run_manifest.json
        │
        └── history/                             # one published-run record per run
            └── 20260620T183000Z-a1b2c3.json     # {run_id, published_at, passed}
```

## Notes

- `runs/` are **write-once** after a run completes; never mutate them for reproducibility.
- `source_registry.jsonl` and `artifact_registry.jsonl` are **append-only** across all runs.
- `latest/` holds flat **copies** (not symlinks) of the most recent *validated* run's published files, swapped in atomically only after `validate_outputs` passes.
- `manifest.json` and `structured/source_inventory.json` are **derived** views (regenerated from the registry), never hand-edited.
- `history/{run_id}.json` records one entry per published run.
- `final_dossier.json` is the machine-readable counterpart to `final_dossier.md` and the primary input for downstream pipelines.
