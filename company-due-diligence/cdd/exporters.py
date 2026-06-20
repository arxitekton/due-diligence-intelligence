"""JSONL, CSV, and Markdown table exporters with optional field redaction."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

_REDACTED = "[REDACTED]"


def _apply_redact(record: dict[str, Any], redact: set[str] | None) -> dict[str, Any]:
    if not redact:
        return record
    return {k: (_REDACTED if k in redact else v) for k, v in record.items()}


def export_jsonl(
    records: list[dict[str, Any]],
    path: Path,
    *,
    redact: set[str] | None = None,
) -> None:
    """Write *records* to *path* as JSONL (one JSON object per line, keys sorted).

    Args:
        records: List of dicts to serialise.
        path: Destination file path (parent dirs created as needed).
        redact: Keys whose values are replaced with ``"[REDACTED]"``.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(_apply_redact(rec, redact), sort_keys=True) + "\n")


def export_csv(
    records: list[dict[str, Any]],
    path: Path,
    *,
    columns: list[str],
    redact: set[str] | None = None,
) -> None:
    """Write *records* to *path* as CSV with an explicit column order.

    Args:
        records: List of dicts to serialise.
        path: Destination file path (parent dirs created as needed).
        columns: Header names written in this order; missing keys become empty string.
        redact: Keys whose values are replaced with ``"[REDACTED]"``.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(columns)
        for rec in records:
            redacted = _apply_redact(rec, redact)
            writer.writerow([str(redacted.get(col, "")) for col in columns])


def export_markdown_table(
    records: list[dict[str, Any]],
    path: Path,
    *,
    columns: list[str],
    title: str,
    redact: set[str] | None = None,
) -> None:
    """Write *records* to *path* as a Markdown table under a level-1 heading.

    Args:
        records: List of dicts to serialise.
        path: Destination file path (parent dirs created as needed).
        columns: Column names written in this order; missing keys become empty string.
        title: Text for the ``# heading`` line.
        redact: Keys whose values are replaced with ``"[REDACTED]"``.
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    def _escape(value: str) -> str:
        return value.replace("|", r"\|")

    def _row(cells: list[str]) -> str:
        return "| " + " | ".join(cells) + " |"

    lines: list[str] = [
        f"# {title}",
        _row(columns),
        _row(["---"] * len(columns)),
    ]
    for rec in records:
        redacted = _apply_redact(rec, redact)
        cells = [_escape(str(redacted.get(col, ""))) for col in columns]
        lines.append(_row(cells))

    with path.open("w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
