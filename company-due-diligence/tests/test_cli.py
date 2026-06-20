import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # company-due-diligence/


def _run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, *args], cwd=ROOT, capture_output=True, text=True
    )


def test_normalize_company_id_cli():
    r = _run(["scripts/normalize_company_id.py", "--company", "Acme Corp."])
    assert r.returncode == 0
    assert r.stdout.strip() == "acme-corp"


def test_create_run_cli_builds_tree(tmp_path: Path):
    r = _run(["scripts/create_run.py", "--company", "Acme Corp.",
              "--mode", "full_refresh", "--root", str(tmp_path), "--token", "a1b2c3"])
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    manifest = Path(out["run_manifest"])
    assert manifest.is_file()
    assert json.loads(manifest.read_text())["company_id"] == "acme-corp"


def test_compute_hashes_cli(tmp_path: Path):
    f = tmp_path / "page.html"
    f.write_bytes(b"<body>Hello   World<script>t=1</script></body>")
    r = _run(["scripts/compute_hashes.py", "--file", str(f), "--mime", "text/html"])
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert len(out["raw_hash"]) == 64
    assert out["profile_id"] == "html"


def test_update_source_registry_cli(tmp_path: Path):
    log = tmp_path / "source_registry.jsonl"
    r = _run(["scripts/update_source_registry.py", "--log", str(log),
              "--run-id", "20260620T183000Z-a1", "--source-id", "src_0123456789abcdef",
              "--event-type", "discovered", "--event-time", "2026-06-20T18:30:00Z",
              "--payload", '{"url":"https://example.com","source_class":"ir"}'])
    assert r.returncode == 0, r.stderr
    lines = log.read_text().strip().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["event_id"] == "evt_000001"


def test_build_manifest_cli(tmp_path: Path):
    company = tmp_path / "companies" / "acme-corp"
    company.mkdir(parents=True)
    (company / "source_registry.jsonl").write_text(
        json.dumps({"event_id": "evt_000001", "event_time": "2026-06-20T18:30:00Z",
                    "run_id": "r1", "entity_type": "source",
                    "entity_id": "src_0000000000000001", "event_type": "retrieved",
                    "payload": {}}, sort_keys=True) + "\n", encoding="utf-8")
    r = _run(["scripts/build_manifest.py", "--root", str(tmp_path),
              "--company-id", "acme-corp", "--now", "2026-06-20T18:30:00Z"])
    assert r.returncode == 0, r.stderr
    manifest = json.loads((company / "manifest.json").read_text())
    assert manifest["source_count"] == 1
