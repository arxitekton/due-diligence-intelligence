"""Structured-artifact loading and lineage helpers."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast


def iter_structured(run_dir: Path) -> Iterator[tuple[Path, dict[str, Any]]]:
    """Yield ``(path, doc)`` for every ``*.json`` in ``run_dir/structured/``.

    Results are sorted by filename. If the directory does not exist, yields
    nothing.
    """
    structured_dir = run_dir / "structured"
    if not structured_dir.is_dir():
        return
    for path in sorted(structured_dir.glob("*.json")):
        doc: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        yield path, doc


def artifact_kind(doc: dict[str, Any]) -> str:
    """Return the kind label for *doc*.

    - ``"financial"`` — doc has both ``line_items`` and ``periods``
    - ``"product"``   — doc has ``entities``
    - ``"extracted"`` — all other cases
    """
    if "line_items" in doc and "periods" in doc:
        return "financial"
    if "entities" in doc:
        return "product"
    return "extracted"


def lineage_ok(doc: dict[str, Any]) -> bool:
    """Return ``True`` iff ``doc["lineage"]`` is a structurally valid lineage dict.

    Required fields and constraints:
    - ``source_snapshot_id``: non-empty str
    - ``content_path``: non-empty str
    - ``snippet``: non-empty str
    - ``locator``: non-empty dict
    - ``extraction_prompt``: dict with ``name`` and ``version`` keys

    Returns ``False`` on any missing or empty value; never raises.
    """
    try:
        lineage = doc["lineage"]
        if not isinstance(lineage, dict):
            return False
        lin: dict[str, Any] = cast(dict[str, Any], lineage)
        for field in ("source_snapshot_id", "content_path", "snippet"):
            value: Any = lin[field]
            if not isinstance(value, str) or not value:
                return False
        locator: Any = lin["locator"]
        if not isinstance(locator, dict) or not locator:
            return False
        prompt: Any = lin["extraction_prompt"]
        if not isinstance(prompt, dict):
            return False
        if "name" not in prompt or "version" not in prompt:
            return False
    except (KeyError, TypeError):
        return False
    return True


def is_artifact_file(path: Path) -> bool:
    """Return True iff *path* should be treated as an artifact (not a meta-file).

    Excludes:
    - ``source_inventory.json`` (inventory file, not an artifact)
    - Any filename starting with ``_`` (internal/merged outputs like ``_merged.json``)
    """
    return path.name != "source_inventory.json" and not path.name.startswith("_")


def referenced_source_ids(doc: dict[str, Any]) -> set[str]:
    """Return ``{doc["source_id"]}`` if present and truthy, else an empty set."""
    source_id = doc.get("source_id")
    if source_id:
        return {str(source_id)}
    return set()
