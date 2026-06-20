"""Evidentiary validation gates for a completed run (P2.8).

``validate_run`` assembles and returns a ``data_quality_report`` dict that
passes schema validation.  It does NOT write any files — the CLI owns that.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

from cdd.artifacts import artifact_kind, iter_structured, lineage_ok
from cdd.paths import OutputPaths
from cdd.schema import validate
from cdd.timeutil import iso_utc

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_STRICT_MODES: frozenset[str] = frozenset(
    {
        "full_refresh",
        "incremental_refresh",
        "validation_only",
        "dossier_only",
        "compare_runs",
    }
)

_KIND_TO_SCHEMA: dict[str, str] = {
    "financial": "financial_artifact",
    "product": "product_artifact",
    "extracted": "extracted_artifact",
}


def _gate(name: str, *, passed: bool, detail: str) -> dict[str, Any]:
    return {"name": name, "passed": passed, "detail": detail}


def _load_json(path: Path) -> dict[str, Any] | None:
    """Return parsed JSON dict or None if file is absent / not a dict."""
    if not path.exists():
        return None
    raw: Any = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        return None
    return raw  # type: ignore[return-value]


def _collect_artifacts(
    paths: OutputPaths,
) -> list[tuple[Path, dict[str, Any]]]:
    """Return artifact files, skipping source_inventory.json and _-prefixed names."""
    results: list[tuple[Path, dict[str, Any]]] = []
    for p, doc in iter_structured(paths.run_dir):
        if p.name == "source_inventory.json":
            continue
        if p.name.startswith("_"):
            continue
        results.append((p, doc))
    return results


# ---------------------------------------------------------------------------
# Fatal gates
# ---------------------------------------------------------------------------


def _gate_schemas_valid(
    artifacts: list[tuple[Path, dict[str, Any]]],
    *,
    mode: str,
) -> dict[str, Any]:
    offending: list[str] = []
    strict = mode in _STRICT_MODES
    for p, doc in artifacts:
        kind = artifact_kind(doc)
        schema_name = _KIND_TO_SCHEMA[kind]
        result = validate(doc, schema_name)
        if result.degraded and strict:
            offending.append(f"{p.name}: schema validation degraded (jsonschema absent)")
        elif not result.ok:
            offending.append(f"{p.name}: {'; '.join(result.errors)}")
    passed = len(offending) == 0
    detail = "; ".join(offending) if offending else "all artifacts valid"
    return _gate("schemas_valid", passed=passed, detail=detail)


def _gate_referential_integrity(
    artifacts: list[tuple[Path, dict[str, Any]]],
    *,
    run_dir: Path,
    inventory_source_ids: set[str],
) -> dict[str, Any]:
    dangling: list[str] = []

    artifact_ids: set[str] = {
        str(doc["artifact_id"])
        for _, doc in artifacts
        if "artifact_id" in doc
    }

    # Every artifact's source_id must be in inventory
    for p, doc in artifacts:
        sid = doc.get("source_id")
        if sid and sid not in inventory_source_ids:
            dangling.append(f"{p.name}: source_id {sid!r} not in inventory")

    # Every dossier citation must be a known artifact_id
    dossier_path = run_dir / "final_dossier.json"
    dossier = _load_json(dossier_path)
    if dossier is not None:
        sections: list[Any] = dossier.get("sections", [])
        for section in sections:
            claims: list[Any] = section.get("claims", [])
            for claim in claims:
                citations: list[Any] = claim.get("citations", [])
                for cit in citations:
                    if isinstance(cit, str) and cit not in artifact_ids:
                        dangling.append(
                            f"dossier claim citation {cit!r} not in artifact set"
                        )

    passed = len(dangling) == 0
    detail = "; ".join(dangling) if dangling else "all references resolved"
    return _gate("referential_integrity", passed=passed, detail=detail)


def _gate_lineage_complete(
    artifacts: list[tuple[Path, dict[str, Any]]],
    *,
    run_dir: Path,
) -> dict[str, Any]:
    violations: list[str] = []

    # Every artifact must pass lineage_ok
    for p, doc in artifacts:
        if not lineage_ok(doc):
            violations.append(f"{p.name}: lineage check failed")

    # Every dossier claim of kind fact/evidence must have ≥1 citation
    dossier_path = run_dir / "final_dossier.json"
    dossier = _load_json(dossier_path)
    if dossier is not None:
        sections: list[Any] = dossier.get("sections", [])
        for section in sections:
            claims: list[Any] = section.get("claims", [])
            for claim in claims:
                kind: Any = claim.get("kind")
                if kind in ("fact", "evidence"):
                    citations: list[Any] = claim.get("citations", [])
                    if not citations:
                        text: str = str(claim.get("text", ""))[:60]
                        violations.append(
                            f"dossier claim ({kind}) has no citations: {text!r}"
                        )

    passed = len(violations) == 0
    detail = "; ".join(violations) if violations else "lineage complete"
    return _gate("lineage_complete", passed=passed, detail=detail)


def _gate_id_integrity(
    artifacts: list[tuple[Path, dict[str, Any]]],
) -> dict[str, Any]:
    ids: list[str] = [
        str(doc["artifact_id"])
        for _, doc in artifacts
        if "artifact_id" in doc
    ]
    counts = Counter(ids)
    dupes = [aid for aid, n in counts.items() if n > 1]
    passed = len(dupes) == 0
    detail = f"duplicate artifact_ids: {', '.join(dupes)}" if dupes else "no duplicates"
    return _gate("id_integrity", passed=passed, detail=detail)


def _gate_financial_usability(
    artifacts: list[tuple[Path, dict[str, Any]]],
) -> dict[str, Any]:
    problems: list[str] = []

    for p, doc in artifacts:
        if artifact_kind(doc) != "financial":
            continue

        periods = cast("list[Any]", doc.get("periods", []))
        period_map: dict[str, dict[str, Any]] = {}
        for period in periods:
            if isinstance(period, dict):
                pdict = cast("dict[str, Any]", period)
                pid: Any = pdict.get("period_id")
                if pid:
                    period_map[str(pid)] = pdict

        line_items = cast("list[Any]", doc.get("line_items", []))
        seen_tuples: list[tuple[object, object, object]] = []

        for li in line_items:
            if not isinstance(li, dict):
                continue
            lidict = cast("dict[str, Any]", li)
            li_id: object = lidict.get("line_item_id")
            scope: object = lidict.get("scope")
            col_ref: object = lidict.get("column_ref")
            cell_locator: object = lidict.get("cell_locator")

            # scope must be non-null
            if scope is None:
                problems.append(f"{p.name}/{li_id}: scope is null")

            # cell_locator must be non-empty dict
            if not isinstance(cell_locator, dict) or len(
                cast("dict[str, Any]", cell_locator)
            ) == 0:
                problems.append(f"{p.name}/{li_id}: cell_locator is missing or empty")

            # column_ref must reference a valid period with currency_reported + unit_scale
            if col_ref is not None:
                period_obj = period_map.get(str(col_ref))
                if period_obj is None:
                    problems.append(
                        f"{p.name}/{li_id}: column_ref {col_ref!r} not in periods"
                    )
                else:
                    if not period_obj.get("currency_reported"):
                        problems.append(
                            f"{p.name}/{li_id}: period {col_ref!r} missing currency_reported"
                        )
                    if not period_obj.get("unit_scale"):
                        problems.append(
                            f"{p.name}/{li_id}: period {col_ref!r} missing unit_scale"
                        )

            # duplicate (scope, period_id, line_item_id) check
            key: tuple[object, object, object] = (scope, col_ref, li_id)
            if key in seen_tuples:
                problems.append(
                    f"{p.name}: duplicate"
                    f" (scope={scope!r}, period={col_ref!r}, line_item_id={li_id!r})"
                )
            else:
                seen_tuples.append(key)

    passed = len(problems) == 0
    detail = "; ".join(problems) if problems else "financial usability ok"
    return _gate("financial_usability", passed=passed, detail=detail)


# ---------------------------------------------------------------------------
# Lenient gates (pass-when-not-applicable)
# ---------------------------------------------------------------------------


def _gate_manifest_closure(*, run_dir: Path) -> dict[str, Any]:
    manifest = _load_json(run_dir / "run_manifest.json")
    if manifest is None:
        return _gate("manifest_closure", passed=True, detail="no manifest file")

    output_paths: Any = manifest.get("output_paths", [])
    if not output_paths:
        return _gate("manifest_closure", passed=True, detail="output_paths empty")

    missing: list[str] = []
    for op in output_paths:
        if isinstance(op, str):
            candidate = Path(op)
            if not candidate.is_absolute():
                candidate = run_dir / op
            if not candidate.exists():
                missing.append(op)

    passed = len(missing) == 0
    detail = (
        f"missing paths: {', '.join(missing)}"
        if missing
        else "all output_paths present"
    )
    return _gate("manifest_closure", passed=passed, detail=detail)


def _gate_refresh_semantics(*, mode: str) -> dict[str, Any]:
    if mode == "incremental_refresh":
        detail = "not evaluated: per-run data insufficient to verify source availability markers"
    else:
        detail = "not applicable for mode: " + mode
    return _gate("refresh_semantics", passed=True, detail=detail)


def _gate_conflict_visibility() -> dict[str, Any]:
    return _gate(
        "conflict_visibility",
        passed=True,
        detail="evaluated by merge step",
    )


# ---------------------------------------------------------------------------
# Non-fatal reporters
# ---------------------------------------------------------------------------


def _stale_sources(
    inventory_sources: list[dict[str, Any]],
    *,
    now: datetime,
    stale_after_days: int,
) -> list[str]:
    cutoff = now - timedelta(days=stale_after_days)
    if cutoff.tzinfo is None:
        cutoff = cutoff.replace(tzinfo=UTC)
    stale: list[str] = []
    for src in inventory_sources:
        last_seen: Any = src.get("last_seen_at")
        if last_seen is None:
            continue
        if not isinstance(last_seen, str):
            continue
        try:
            ts = datetime.fromisoformat(last_seen.replace("Z", "+00:00"))
        except ValueError:
            continue
        if ts < cutoff:
            stale.append(str(src.get("source_id", "")))
    return stale


def _low_confidence_artifacts(
    artifacts: list[tuple[Path, dict[str, Any]]],
    *,
    threshold: float,
) -> list[str]:
    result: list[str] = []
    for _, doc in artifacts:
        confidence: Any = doc.get("confidence")
        if confidence is None:
            continue
        if not isinstance(confidence, (int, float)):
            continue
        if float(confidence) < threshold:
            artifact_id: Any = doc.get("artifact_id")
            if artifact_id:
                result.append(str(artifact_id))
    return result


def _missing_source_classes(
    inventory_sources: list[dict[str, Any]],
    *,
    expected: set[str],
) -> list[str]:
    if not expected:
        return []
    present: set[str] = {
        str(src["source_class"])
        for src in inventory_sources
        if src.get("source_class")
    }
    return sorted(expected - present)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def validate_run(
    paths: OutputPaths,
    *,
    mode: str,
    now: datetime,
    stale_after_days: int = 180,
    low_confidence_threshold: float = 0.5,
    expected_primary_classes: set[str] | None = None,
) -> dict[str, Any]:
    """Run all evidentiary gates and return a data_quality_report dict."""

    if expected_primary_classes is None:
        expected_primary_classes = set()

    # Ensure now is timezone-aware
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)

    # Load inventory
    inventory_path = paths.run_dir / "structured" / "source_inventory.json"
    inventory = _load_json(inventory_path)
    inventory_sources: list[dict[str, Any]] = []
    inventory_source_ids: set[str] = set()
    if inventory is not None:
        raw_sources = cast("list[Any]", inventory.get("sources", []))
        for raw_src in raw_sources:
                if isinstance(raw_src, dict):
                    src = cast("dict[str, Any]", raw_src)
                    inventory_sources.append(src)
                    sid: object = src.get("source_id")
                    if sid:
                        inventory_source_ids.add(str(sid))

    # Collect artifacts (skipping inventory + _ files)
    artifacts = _collect_artifacts(paths)

    # Load run_manifest for run_id / company_id
    manifest = _load_json(paths.run_dir / "run_manifest.json")
    run_id: str = (
        str(manifest["run_id"]) if manifest and "run_id" in manifest else paths.run_id
    )
    company_id: str = (
        str(manifest["company_id"])
        if manifest and "company_id" in manifest
        else paths.company_slug
    )

    # --- Fatal gates ---
    gates: list[dict[str, Any]] = [
        _gate_schemas_valid(artifacts, mode=mode),
        _gate_referential_integrity(
            artifacts,
            run_dir=paths.run_dir,
            inventory_source_ids=inventory_source_ids,
        ),
        _gate_lineage_complete(artifacts, run_dir=paths.run_dir),
        _gate_id_integrity(artifacts),
        _gate_financial_usability(artifacts),
        # Lenient gates
        _gate_manifest_closure(run_dir=paths.run_dir),
        _gate_refresh_semantics(mode=mode),
        _gate_conflict_visibility(),
    ]

    passed: bool = all(g["passed"] for g in gates[:5])  # only fatal gates

    # --- Non-fatal reporters ---
    stale: list[str] = _stale_sources(
        inventory_sources, now=now, stale_after_days=stale_after_days
    )
    low_conf: list[str] = _low_confidence_artifacts(
        artifacts, threshold=low_confidence_threshold
    )
    missing_classes: list[str] = _missing_source_classes(
        inventory_sources, expected=expected_primary_classes
    )

    report: dict[str, Any] = {
        "run_id": run_id,
        "company_id": company_id,
        "generated_at": iso_utc(now),
        "passed": passed,
        "gates": gates,
        "conflicts": [],
        "stale_sources": stale,
        "low_confidence": low_conf,
        "missing_source_classes": missing_classes,
    }

    # Validate the assembled report against its own schema — internal bug if it fails
    result = validate(report, "data_quality_report")
    if not result.ok:
        raise RuntimeError(
            f"data_quality_report failed self-validation: {result.errors}"
        )

    return report
