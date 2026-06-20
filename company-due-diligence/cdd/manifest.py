"""Derive the current-state manifest.json from event logs (atomic write)."""

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from cdd.paths import OutputPaths
from cdd.registry import derive_source_state
from cdd.timeutil import iso_utc


def _atomic_write_json(target: Path, data: dict[str, Any]) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(target.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(data, indent=2, sort_keys=True) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, target)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def build_manifest(paths: OutputPaths, *, now: datetime) -> Path:
    sources = derive_source_state(paths.source_registry)
    active = sum(1 for s in sources.values() if s["status"] in ("active", "reappeared"))
    unavailable = sum(1 for s in sources.values() if s["status"] == "unavailable")
    manifest: dict[str, Any] = {
        "company_id": paths.company_slug,
        "generated_at": iso_utc(now),
        "source_count": len(sources),
        "sources_active": active,
        "sources_unavailable": unavailable,
        "sources": sources,
    }
    _atomic_write_json(paths.manifest, manifest)
    return paths.manifest
