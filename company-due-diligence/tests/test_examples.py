import json
from pathlib import Path

from cdd.schema import validate

EX = Path(__file__).resolve().parent.parent / "examples"


def test_example_run_manifest_validates():
    doc = json.loads((EX / "example_run_manifest.json").read_text(encoding="utf-8"))
    assert validate(doc, "run_manifest").ok, validate(doc, "run_manifest").errors


def test_example_source_registry_lines_validate():
    for line in (EX / "example_source_registry.jsonl").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            assert validate(json.loads(line), "source_registry").ok, line


def test_example_artifact_registry_lines_validate():
    for line in (EX / "example_artifact_registry.jsonl").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            assert validate(json.loads(line), "artifact_registry").ok, line
