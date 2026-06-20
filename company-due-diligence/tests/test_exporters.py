import json
from pathlib import Path

from cdd.exporters import export_csv, export_jsonl, export_markdown_table

_RECS = [
    {"id": "a1", "name": "Acme", "email": "x@e.com"},
    {"id": "a2", "name": "Beta", "email": "y@e.com"},
]


def test_jsonl_roundtrip(tmp_path: Path):
    out = tmp_path / "x.jsonl"
    export_jsonl(_RECS, out)
    lines = out.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["name"] == "Acme"


def test_jsonl_redacts(tmp_path: Path):
    out = tmp_path / "x.jsonl"
    export_jsonl(_RECS, out, redact={"email"})
    assert json.loads(out.read_text().splitlines()[0])["email"] == "[REDACTED]"


def test_csv_header_and_order(tmp_path: Path):
    out = tmp_path / "x.csv"
    export_csv(_RECS, out, columns=["id", "name"])
    rows = out.read_text(encoding="utf-8").splitlines()
    assert rows[0] == "id,name"
    assert rows[1] == "a1,Acme"


def test_csv_redacts(tmp_path: Path):
    out = tmp_path / "x.csv"
    export_csv(_RECS, out, columns=["id", "email"], redact={"email"})
    assert "[REDACTED]" in out.read_text()


def test_markdown_table(tmp_path: Path):
    out = tmp_path / "x.md"
    export_markdown_table(_RECS, out, columns=["id", "name"], title="People")
    text = out.read_text(encoding="utf-8")
    assert "# People" in text
    assert "| id | name |" in text
    assert "| --- | --- |" in text
    assert "| a1 | Acme |" in text
