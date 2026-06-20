from pathlib import Path

from cdd.paths import OutputPaths

RUN_SUBDIRS = [
    "raw_sources", "raw_artifacts", "extracted_tables",
    "structured", "reports", "logs",
]


def test_company_dir_layout(tmp_path: Path):
    p = OutputPaths(root=tmp_path, company_slug="acme-corp", run_id="20260620T183000Z-a1")
    assert p.company_dir == tmp_path / "companies" / "acme-corp"
    assert p.source_registry == p.company_dir / "source_registry.jsonl"
    assert p.artifact_registry == p.company_dir / "artifact_registry.jsonl"
    assert p.manifest == p.company_dir / "manifest.json"


def test_run_dir_and_subdirs(tmp_path: Path):
    p = OutputPaths(root=tmp_path, company_slug="acme-corp", run_id="20260620T183000Z-a1")
    assert p.run_dir == p.company_dir / "runs" / "20260620T183000Z-a1"
    for sub in RUN_SUBDIRS:
        assert p.run_subdir(sub) == p.run_dir / sub


def test_run_subdir_rejects_unknown(tmp_path: Path):
    import pytest

    p = OutputPaths(root=tmp_path, company_slug="acme-corp", run_id="r1")
    with pytest.raises(ValueError):
        p.run_subdir("nope")
