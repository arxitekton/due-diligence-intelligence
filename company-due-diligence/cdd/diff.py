"""Run comparison and delta classification (P2.6)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RunDiff:
    from_run: str
    to_run: str
    delta_type: str
    sources_added: list[str]
    sources_removed: list[str]
    sources_changed: list[dict[str, str]]
    sources_unavailable: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "from_run": self.from_run,
            "to_run": self.to_run,
            "delta_type": self.delta_type,
            "sources_added": self.sources_added,
            "sources_removed": self.sources_removed,
            "sources_changed": self.sources_changed,
            "sources_unavailable": self.sources_unavailable,
        }


def _load_json(path: Path, label: str) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"{label} not found: {path}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    return dict[str, Any](raw)


def _index_sources(inventory: dict[str, Any]) -> dict[str, dict[str, Any]]:
    sources = list[dict[str, Any]](inventory["sources"])
    return {str(s["source_id"]): dict[str, Any](s) for s in sources}


def _classify_delta(from_repro: dict[str, Any], to_repro: dict[str, Any]) -> str:
    if str(from_repro.get("schema_set_hash", "")) != str(to_repro.get("schema_set_hash", "")):
        return "schema_delta"
    if (
        str(from_repro.get("prompt_set_hash", "")) != str(to_repro.get("prompt_set_hash", ""))
        or str(from_repro.get("model_id", "")) != str(to_repro.get("model_id", ""))
    ):
        return "extraction_delta"
    return "source_delta"


def compare_runs(company_dir: Path, from_run: str, to_run: str) -> RunDiff:
    """Compare two runs and classify the delta.

    Args:
        company_dir: Path to the company directory (contains ``runs/`` sub-directory).
        from_run: Run ID of the baseline run.
        to_run: Run ID of the target run.

    Returns:
        A frozen :class:`RunDiff` describing added, removed, changed, and
        unavailable sources together with a delta classification.

    Raises:
        FileNotFoundError: If the source inventory or run manifest for either
            run cannot be found on disk.
    """
    from_inv_path = company_dir / "runs" / from_run / "structured" / "source_inventory.json"
    to_inv_path = company_dir / "runs" / to_run / "structured" / "source_inventory.json"
    from_manifest_path = company_dir / "runs" / from_run / "run_manifest.json"
    to_manifest_path = company_dir / "runs" / to_run / "run_manifest.json"

    from_inv = _load_json(from_inv_path, f"source inventory for run '{from_run}'")
    to_inv = _load_json(to_inv_path, f"source inventory for run '{to_run}'")
    from_manifest = _load_json(from_manifest_path, f"run manifest for run '{from_run}'")
    to_manifest = _load_json(to_manifest_path, f"run manifest for run '{to_run}'")

    from_sources = _index_sources(from_inv)
    to_sources = _index_sources(to_inv)

    from_ids = set(from_sources)
    to_ids = set(to_sources)

    sources_added = sorted(to_ids - from_ids)
    sources_removed = sorted(from_ids - to_ids)

    sources_changed: list[dict[str, str]] = []
    for sid in sorted(from_ids & to_ids):
        from_src = from_sources[sid]
        to_src = to_sources[sid]
        if str(from_src.get("content_hash", "")) != str(to_src.get("content_hash", "")):
            diff_class = str(to_src.get("diff_class") or "content_change")
            sources_changed.append({"source_id": sid, "diff_class": diff_class})

    sources_unavailable = sorted(
        sid for sid, src in to_sources.items()
        if str(src.get("retrieval_status", "")) == "unavailable"
    )

    from_repro = dict[str, Any](from_manifest.get("reproducibility", {}))
    to_repro = dict[str, Any](to_manifest.get("reproducibility", {}))
    delta_type = _classify_delta(from_repro, to_repro)

    return RunDiff(
        from_run=from_run,
        to_run=to_run,
        delta_type=delta_type,
        sources_added=sources_added,
        sources_removed=sources_removed,
        sources_changed=sources_changed,
        sources_unavailable=sources_unavailable,
    )
