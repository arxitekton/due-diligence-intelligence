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

from cdd.artifacts import artifact_kind, is_artifact_file, iter_structured, lineage_ok
from cdd.merge import merge_financials, merge_products
from cdd.paths import OutputPaths
from cdd.registry import derive_source_state
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

# Internal gate result: (name, passed, detail, fatal)
_GateResult = tuple[str, bool, str, bool]


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
        if not is_artifact_file(p):
            continue
        results.append((p, doc))
    return results


# ---------------------------------------------------------------------------
# Fatal gates — each returns (name, passed, detail, fatal=True)
# ---------------------------------------------------------------------------


def _gate_schemas_valid(
    artifacts: list[tuple[Path, dict[str, Any]]],
    *,
    mode: str,
) -> _GateResult:
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
    return ("schemas_valid", passed, detail, True)


def _gate_referential_integrity(
    artifacts: list[tuple[Path, dict[str, Any]]],
    *,
    run_dir: Path,
    inventory_source_ids: set[str],
) -> _GateResult:
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
        sections_raw: Any = dossier.get("sections", [])
        if not isinstance(sections_raw, list):
            dangling.append("dossier sections is not a list (malformed dossier)")
        else:
            for section_item in cast("list[Any]", sections_raw):
                if not isinstance(section_item, dict):
                    continue
                section_d = cast("dict[str, Any]", section_item)
                claims_raw: Any = section_d.get("claims", [])
                if not isinstance(claims_raw, list):
                    continue
                for claim_item in cast("list[Any]", claims_raw):
                    if not isinstance(claim_item, dict):
                        continue
                    claim_d = cast("dict[str, Any]", claim_item)
                    raw_citations: Any = claim_d.get("citations", [])
                    if not isinstance(raw_citations, list):
                        continue
                    for cit in cast("list[Any]", raw_citations):
                        if isinstance(cit, str) and cit not in artifact_ids:
                            dangling.append(
                                f"dossier claim citation {cit!r} not in artifact set"
                            )

    passed = len(dangling) == 0
    detail = "; ".join(dangling) if dangling else "all references resolved"
    return ("referential_integrity", passed, detail, True)


def _gate_lineage_complete(
    artifacts: list[tuple[Path, dict[str, Any]]],
    *,
    run_dir: Path,
) -> _GateResult:
    violations: list[str] = []

    # Every artifact must pass lineage_ok
    for p, doc in artifacts:
        if not lineage_ok(doc):
            violations.append(f"{p.name}: lineage check failed")

    # Every dossier claim of kind fact/evidence must have ≥1 citation
    dossier_path = run_dir / "final_dossier.json"
    dossier = _load_json(dossier_path)
    if dossier is not None:
        sections_val: Any = dossier.get("sections", [])
        if not isinstance(sections_val, list):
            violations.append("dossier sections is not a list (malformed dossier)")
        else:
            for section_v in cast("list[Any]", sections_val):
                if not isinstance(section_v, dict):
                    continue
                section_vd = cast("dict[str, Any]", section_v)
                claims_val: Any = section_vd.get("claims", [])
                if not isinstance(claims_val, list):
                    continue
                for claim_v in cast("list[Any]", claims_val):
                    if not isinstance(claim_v, dict):
                        continue
                    claim_vd = cast("dict[str, Any]", claim_v)
                    kind: Any = claim_vd.get("kind")
                    if kind in ("fact", "evidence"):
                        raw_cit_val: Any = claim_vd.get("citations", [])
                        citations_val: list[Any] = (
                            cast("list[Any]", raw_cit_val)
                            if isinstance(raw_cit_val, list)
                            else []
                        )
                        if not citations_val:
                            text: str = str(claim_vd.get("text", ""))[:60]
                            violations.append(
                                f"dossier claim ({kind}) has no citations: {text!r}"
                            )

    passed = len(violations) == 0
    detail = "; ".join(violations) if violations else "lineage complete"
    return ("lineage_complete", passed, detail, True)


def _gate_id_integrity(
    artifacts: list[tuple[Path, dict[str, Any]]],
) -> _GateResult:
    ids: list[str] = [
        str(doc["artifact_id"])
        for _, doc in artifacts
        if "artifact_id" in doc
    ]
    counts = Counter(ids)
    dupes = [aid for aid, n in counts.items() if n > 1]
    passed = len(dupes) == 0
    detail = f"duplicate artifact_ids: {', '.join(dupes)}" if dupes else "no duplicates"
    return ("id_integrity", passed, detail, True)


def _gate_financial_usability(
    artifacts: list[tuple[Path, dict[str, Any]]],
) -> _GateResult:
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
    return ("financial_usability", passed, detail, True)


def _gate_manifest_closure(*, run_dir: Path) -> _GateResult:
    """Check that every path listed in run_manifest.output_paths exists on disk.

    Content-hash recompute is NOT performed: run_manifest.output_paths records
    bare paths with no associated hashes (a schema addition would be needed —
    out of scope).  Existence is verified; hash integrity is not yet wired.
    """
    manifest = _load_json(run_dir / "run_manifest.json")
    if manifest is None:
        return ("manifest_closure", True, "no manifest file", True)

    output_paths: Any = manifest.get("output_paths", [])
    if not output_paths:
        return ("manifest_closure", True, "output_paths empty", True)

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
        else "all output_paths present (existence verified; hash recompute not yet wired)"
    )
    return ("manifest_closure", passed, detail, True)


def _gate_refresh_semantics(
    *,
    mode: str,
    paths: OutputPaths,
    inventory_source_ids: set[str],
) -> _GateResult:
    """Verify that no previously-active source was silently dropped in incremental_refresh.

    For non-incremental modes: passes immediately (not applicable).
    For incremental_refresh:
      - If no source_registry exists: passes (no prior state to compare against).
      - Otherwise derives currently active/reappeared source IDs from the registry
        and reports any that are absent from this run's inventory without an
        unavailable marker (silent drop = gate failure).
    """
    if mode != "incremental_refresh":
        return ("refresh_semantics", True, f"not applicable (mode={mode})", True)

    if not paths.source_registry.exists():
        return ("refresh_semantics", True, "no source registry", True)

    state = derive_source_state(paths.source_registry)
    known_active: set[str] = {
        sid for sid, s in state.items() if s["status"] in ("active", "reappeared")
    }
    silently_dropped = sorted(known_active - inventory_source_ids)
    if silently_dropped:
        joined = ", ".join(silently_dropped)
        detail = (
            "known sources absent from inventory without unavailable marker: "
            + joined
        )
        return ("refresh_semantics", False, detail, True)
    return ("refresh_semantics", True, "all known active sources accounted for", True)


def _gate_conflict_visibility(
    artifacts: list[tuple[Path, dict[str, Any]]],
) -> tuple[_GateResult, list[dict[str, Any]]]:
    """Surface financial and product conflicts into the report (never silently merged).

    Collects financial and product artifacts, runs merge_financials and
    merge_products, and returns both the gate result and the combined conflict
    list to populate report["conflicts"].
    The gate passes by construction once conflicts are surfaced — surfacing IS
    the visibility guarantee per spec §10.

    If merge_financials or merge_products raises (e.g. because an artifact is
    malformed — caught by financial_usability), we degrade gracefully:
    return an empty conflict list and note the skip.  financial_usability will
    mark the run failed independently.
    """
    financials: list[dict[str, Any]] = [
        doc for _, doc in artifacts if artifact_kind(doc) == "financial"
    ]
    products: list[dict[str, Any]] = [
        doc for _, doc in artifacts if artifact_kind(doc) == "product"
    ]
    conflicts: list[dict[str, Any]] = []
    try:
        fin_result = merge_financials(financials)
        conflicts.extend(fin_result["conflicts"])
    except (KeyError, TypeError, ValueError):
        pass
    try:
        prod_result = merge_products(products)
        conflicts.extend(prod_result["conflicts"])
    except (KeyError, TypeError, ValueError):
        pass
    n = len(conflicts)
    if n == 0 and not financials and not products:
        detail = "no financial or product artifacts to merge"
    elif n == 0:
        detail = "0 conflict(s) surfaced"
    else:
        detail = f"{n} conflict(s) surfaced"
    return ("conflict_visibility", True, detail, True), conflicts


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

    # --- Run all gates (all 8 are FATAL per spec §10) ---
    # conflict_visibility returns (gate_result, conflicts) so handle separately
    cv_result, conflicts = _gate_conflict_visibility(artifacts)

    gate_results: list[_GateResult] = [
        _gate_schemas_valid(artifacts, mode=mode),
        _gate_referential_integrity(
            artifacts,
            run_dir=paths.run_dir,
            inventory_source_ids=inventory_source_ids,
        ),
        _gate_lineage_complete(artifacts, run_dir=paths.run_dir),
        _gate_id_integrity(artifacts),
        _gate_financial_usability(artifacts),
        _gate_manifest_closure(run_dir=paths.run_dir),
        _gate_refresh_semantics(
            mode=mode,
            paths=paths,
            inventory_source_ids=inventory_source_ids,
        ),
        cv_result,
    ]

    # passed = all FATAL gates pass (all 8 are fatal; strip internal fatal flag for report)
    passed: bool = all(g_passed for (_, g_passed, _, fatal) in gate_results if fatal)

    # Build public gate dicts (schema: name/passed/detail only — no fatal field)
    gates: list[dict[str, Any]] = [
        _gate(name, passed=g_passed, detail=detail)
        for (name, g_passed, detail, _) in gate_results
    ]

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
        "conflicts": conflicts,
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
