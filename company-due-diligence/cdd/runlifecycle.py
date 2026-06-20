"""Create a new run: folder tree + seeded run_manifest.json."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from cdd.ids import make_run_id, normalize_company_id
from cdd.paths import RUN_SUBDIRS, OutputPaths
from cdd.timeutil import iso_utc


def _seed_manifest(
    run_id: str,
    company_slug: str,
    company_name: str,
    mode: str,
    now: datetime,
    input_parameters: dict[str, object],
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "company_id": company_slug,
        "company_name": company_name,
        "started_at": iso_utc(now),
        "completed_at": None,
        "mode": mode,
        "input_parameters": input_parameters,
        "reproducibility": {
            "prompt_set_hash": None,
            "schema_set_hash": None,
            "model_id": None,
            "tool_versions": {},
            "normalizer_profile_versions": {},
            "locale": None,
        },
        "sources_discovered": 0,
        "sources_retrieved": 0,
        "sources_new": 0,
        "sources_changed": 0,
        "sources_unavailable": 0,
        "artifacts_extracted": 0,
        "schemas_validated": False,
        "output_paths": [],
        "warnings": [],
        "errors": [],
    }


def create_run(
    *,
    root: Path,
    company_name: str,
    mode: str,
    now: datetime,
    token: str,
    input_parameters: dict[str, object],
) -> OutputPaths:
    company_slug = normalize_company_id(company_name)
    run_id = make_run_id(now, token)
    paths = OutputPaths(root=Path(root), company_slug=company_slug, run_id=run_id)

    if paths.run_dir.exists():
        raise FileExistsError(f"run already exists: {paths.run_dir}")

    paths.run_dir.mkdir(parents=True)
    for sub in RUN_SUBDIRS:
        paths.run_subdir(sub).mkdir()
    paths.company_dir.joinpath("runs").mkdir(exist_ok=True)

    manifest = _seed_manifest(run_id, company_slug, company_name, mode, now, input_parameters)
    (paths.run_dir / "run_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return paths
