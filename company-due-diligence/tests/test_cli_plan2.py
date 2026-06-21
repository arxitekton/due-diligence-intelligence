import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, *args], cwd=ROOT, capture_output=True, text=True)


def _src(sid: str, h: str, status: str = "ok", diff: str = "unchanged") -> dict[str, object]:
    return {
        "source_id": sid,
        "url": "https://e/x",
        "source_class": "ir",
        "source_priority": "primary",
        "title": None,
        "publication_date": None,
        "retrieved_at": None,
        "first_seen_at": None,
        "last_seen_at": None,
        "content_hash": h,
        "retrieval_status": status,
        "diff_class": diff,
        "notes": None,
    }


def _repro() -> dict[str, object]:
    return {
        "prompt_set_hash": "p0",
        "schema_set_hash": "s0",
        "model_id": "m0",
        "tool_versions": {},
        "normalizer_profile_versions": {},
        "locale": "en-US",
    }


def _write_run(cdir: Path, run_id: str, sources: list[dict[str, object]]) -> None:
    run = cdir / "runs" / run_id
    (run / "structured").mkdir(parents=True)
    (run / "structured" / "source_inventory.json").write_text(
        json.dumps(
            {
                "company_id": "acme-corp",
                "run_id": run_id,
                "generated_at": "2026-06-20T18:30:00Z",
                "sources": sources,
            }
        ),
        encoding="utf-8",
    )
    (run / "run_manifest.json").write_text(
        json.dumps({"reproducibility": _repro()}), encoding="utf-8"
    )


def test_compare_runs_cli(tmp_path: Path) -> None:
    cdir = tmp_path / "companies" / "acme-corp"
    _write_run(cdir, "runA", [_src("src_0000000000000001", "h1")])
    _write_run(
        cdir,
        "runB",
        [
            _src("src_0000000000000001", "h1b", diff="content_change"),
            _src("src_0000000000000002", "h2"),
        ],
    )
    r = _run(
        [
            "scripts/compare_runs.py",
            "--company-id",
            "acme-corp",
            "--from-run",
            "runA",
            "--to-run",
            "runB",
            "--root",
            str(tmp_path),
        ]
    )
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out["sources_added"] == ["src_0000000000000002"]


def test_generate_change_log_cli(tmp_path: Path) -> None:
    cdir = tmp_path / "companies" / "acme-corp"
    _write_run(cdir, "runA", [_src("src_0000000000000001", "h1")])
    _write_run(cdir, "runB", [_src("src_0000000000000002", "h2")])
    r = _run(
        [
            "scripts/generate_change_log.py",
            "--company-id",
            "acme-corp",
            "--from-run",
            "runA",
            "--to-run",
            "runB",
            "--now",
            "2026-06-20T18:30:00Z",
            "--root",
            str(tmp_path),
        ]
    )
    assert r.returncode == 0, r.stderr
    cl = cdir / "runs" / "runB" / "change_log.md"
    assert cl.is_file() and "# Change Log" in cl.read_text()


def test_export_csv_cli(tmp_path: Path) -> None:
    src = tmp_path / "in.json"
    src.write_text(json.dumps([{"id": "a1", "name": "Acme"}]), encoding="utf-8")
    out = tmp_path / "out.csv"
    r = _run(
        [
            "scripts/export_csv.py",
            "--in",
            str(src),
            "--out",
            str(out),
            "--columns",
            "id,name",
        ]
    )
    assert r.returncode == 0, r.stderr
    assert out.read_text().splitlines()[0] == "id,name"


def test_export_jsonl_redact_cli(tmp_path: Path) -> None:
    src = tmp_path / "in.json"
    src.write_text(json.dumps([{"id": "a1", "email": "x@e.com"}]), encoding="utf-8")
    out = tmp_path / "out.jsonl"
    r = _run(
        [
            "scripts/export_jsonl.py",
            "--in",
            str(src),
            "--out",
            str(out),
            "--redact",
            "email",
        ]
    )
    assert r.returncode == 0, r.stderr
    assert json.loads(out.read_text().splitlines()[0])["email"] == "[REDACTED]"


def test_merge_artifacts_cli_handles_products(tmp_path: Path) -> None:
    sdir = tmp_path / "structured"
    sdir.mkdir()
    prod = {
        "artifact_id": "art_0000000000000b01",
        "schema_version": "1",
        "company_id": "acme-corp",
        "run_id": "r",
        "source_id": "src_0000000000000001",
        "lineage": {
            "source_snapshot_id": "s",
            "content_path": "p",
            "locator": {"x": 1},
            "snippet": "x",
            "extraction_prompt": {"name": "product_extraction", "version": "1"},
        },
        "source_context": {
            "document_title": "P",
            "section_path": [],
            "source_native_statement_name": None,
            "table_id": None,
            "page": None,
        },
        "entities": [
            {
                "entity_id": "e1",
                "entity_type": "platform",
                "source_native_name": "Acme",
                "aliases": [],
                "source_native_category_path": [],
                "parent_entity_id": None,
                "display_order": 1,
                "description_quote": None,
                "lifecycle_status": "ga",
                "geography_scope": [],
                "pricing_observations": [],
                "attributes": [],
                "normalized_candidate": {"family": "cloud", "confidence": 0.9},
            }
        ],
        "notes": None,
    }
    (sdir / "prod.json").write_text(json.dumps(prod), encoding="utf-8")
    r = _run(["scripts/merge_artifacts.py", "--run-dir", str(tmp_path)])
    assert r.returncode == 0, r.stderr
    merged = json.loads((sdir / "_merged.json").read_text())
    assert "product" in merged and "financial" in merged
