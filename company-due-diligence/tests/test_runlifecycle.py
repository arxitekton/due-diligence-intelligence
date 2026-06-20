import json
from datetime import datetime
from pathlib import Path

from cdd.paths import RUN_SUBDIRS, OutputPaths
from cdd.runlifecycle import create_run
from cdd.schema import validate


def test_create_run_builds_tree_and_valid_manifest(tmp_path: Path, fixed_now: datetime):
    paths = create_run(
        root=tmp_path,
        company_name="Acme Corp.",
        mode="full_refresh",
        now=fixed_now,
        token="a1b2c3",
        input_parameters={"company_name": "Acme Corp."},
    )
    assert isinstance(paths, OutputPaths)
    assert paths.company_slug == "acme-corp"
    assert paths.run_dir.is_dir()
    for sub in RUN_SUBDIRS:
        assert paths.run_subdir(sub).is_dir()

    manifest_path = paths.run_dir / "run_manifest.json"
    assert manifest_path.is_file()
    manifest = json.loads(manifest_path.read_text())
    assert manifest["run_id"] == "20260620T183000Z-a1b2c3"
    assert manifest["company_id"] == "acme-corp"
    assert manifest["mode"] == "full_refresh"
    assert manifest["completed_at"] is None
    assert validate(manifest, "run_manifest").ok


def test_create_run_is_idempotent_for_existing_run(tmp_path: Path, fixed_now: datetime):
    import pytest

    create_run(root=tmp_path, company_name="Acme", mode="full_refresh",
               now=fixed_now, token="a1b2c3", input_parameters={})
    with pytest.raises(FileExistsError):
        create_run(root=tmp_path, company_name="Acme", mode="full_refresh",
                   now=fixed_now, token="a1b2c3", input_parameters={})
