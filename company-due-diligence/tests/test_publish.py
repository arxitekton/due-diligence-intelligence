import json
from datetime import UTC, datetime
from pathlib import Path

from cdd.paths import OutputPaths
from cdd.publish import publish_latest

RUN = "20260620T183000Z-a1b2c3"


def _paths(tmp: Path) -> OutputPaths:
    return OutputPaths(root=tmp, company_slug="acme-corp", run_id=RUN)


def _seed_run(paths: OutputPaths, dossier: dict) -> None:
    (paths.run_dir / "structured").mkdir(parents=True)
    (paths.run_dir / "final_dossier.json").write_text(json.dumps(dossier), encoding="utf-8")
    (paths.run_dir / "final_dossier.md").write_text("# Dossier", encoding="utf-8")
    (paths.run_dir / "structured" / "source_inventory.json").write_text(
        json.dumps({"sources": []}), encoding="utf-8")


def _report(passed: bool) -> dict:
    return {"run_id": RUN, "company_id": "acme-corp", "passed": passed}


def _now() -> datetime:
    return datetime(2026, 6, 20, 18, 30, tzinfo=UTC)


def test_failed_report_does_not_publish(tmp_path: Path):
    paths = _paths(tmp_path)
    _seed_run(paths, {"k": 1})
    assert publish_latest(paths, report=_report(False), now=_now()) is False
    assert not paths.latest_dir.exists() or not any(paths.latest_dir.iterdir())


def test_passed_report_publishes_and_records_history(tmp_path: Path):
    paths = _paths(tmp_path)
    _seed_run(paths, {"k": 1})
    assert publish_latest(paths, report=_report(True), now=_now()) is True
    assert json.loads((paths.latest_dir / "final_dossier.json").read_text()) == {"k": 1}
    assert (paths.latest_dir / "source_inventory.json").exists()
    hist = json.loads((paths.history_dir / f"{RUN}.json").read_text())
    assert hist["run_id"] == RUN and hist["passed"] is True


def test_republish_overwrites_atomically(tmp_path: Path):
    paths = _paths(tmp_path)
    _seed_run(paths, {"k": 1})
    publish_latest(paths, report=_report(True), now=_now())
    (paths.run_dir / "final_dossier.json").write_text(json.dumps({"k": 2}), encoding="utf-8")
    publish_latest(paths, report=_report(True), now=_now())
    assert json.loads((paths.latest_dir / "final_dossier.json").read_text()) == {"k": 2}
