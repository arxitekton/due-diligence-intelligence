"""Validation-gated atomic publication of a run's outputs into latest/."""

import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from cdd.paths import OutputPaths
from cdd.timeutil import iso_utc

# Files copied flat from run_dir into latest/
_RUN_DIR_FILES = (
    "final_dossier.md",
    "final_dossier.json",
    "data_quality_report.md",
    "change_log.md",
)

# (subdir_name, filename) pairs copied flat into latest/
_RUN_SUBDIR_FILES = (
    ("structured", "source_inventory.json"),
)


def publish_latest(
    paths: OutputPaths,
    *,
    report: dict[str, Any],
    now: datetime,
) -> bool:
    """Publish a run's outputs into latest/ if the report passed validation.

    Args:
        paths: Resolved output paths for this company + run.
        report: Validation report dict; must contain ``run_id`` and ``passed``.
        now: Timestamp used for the history record.

    Returns:
        ``True`` if published; ``False`` if ``report["passed"]`` is falsy (no-op).
    """
    if not report.get("passed"):
        return False

    run_id: str = report["run_id"]

    # Collect source → dest pairs (only files that exist)
    copies: list[tuple[Path, str]] = []

    for filename in _RUN_DIR_FILES:
        src = paths.run_dir / filename
        if src.exists():
            copies.append((src, filename))

    for subdir, filename in _RUN_SUBDIR_FILES:
        src = paths.run_subdir(subdir) / filename
        if src.exists():
            copies.append((src, filename))

    # Atomic swap: build into latest.new, then replace latest/
    latest_new: Path = paths.company_dir / "latest.new"

    # Clean any leftover temp dir from a previous crash
    shutil.rmtree(latest_new, ignore_errors=True)
    latest_new.mkdir(parents=True)

    for src, basename in copies:
        shutil.copy2(src, latest_new / basename)

    shutil.rmtree(paths.latest_dir, ignore_errors=True)
    os.replace(latest_new, paths.latest_dir)

    # Append history record
    paths.history_dir.mkdir(parents=True, exist_ok=True)
    history_record: dict[str, Any] = {
        "run_id": run_id,
        "published_at": iso_utc(now),
        "passed": True,
    }
    (paths.history_dir / f"{run_id}.json").write_text(
        json.dumps(history_record), encoding="utf-8"
    )

    return True
