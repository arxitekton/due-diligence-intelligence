"""Lineage-preserving merge of financial and product artifacts with conflict-set emission."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from typing import Any

# Type aliases at module level so pyright can resolve them.
_GroupKey = tuple[str, str, str]
_ProductGroupKey = tuple[str, str]
_Obs = dict[str, Any]


def _conflict_id(scope: str, period_id: str, taxonomy_key: str) -> str:
    raw = f"{scope}|{period_id}|{taxonomy_key}"
    return "cf_" + hashlib.sha256(raw.encode()).hexdigest()[:12]


def _product_conflict_id(entity_type: str, family: str) -> str:
    raw = f"product|{entity_type}|{family}"
    return "cf_" + hashlib.sha256(raw.encode()).hexdigest()[:12]


def merge_financials(artifacts: list[dict[str, Any]]) -> dict[str, Any]:
    """Merge a list of financial_artifact dicts, preserving lineage and emitting conflict sets.

    Args:
        artifacts: List of financial_artifact dicts conforming to the CDD schema.

    Returns:
        Dict with keys ``merged`` (agreed entries) and ``conflicts`` (conflict sets).
    """
    groups: defaultdict[_GroupKey, list[_Obs]] = defaultdict(list)

    for artifact in artifacts:
        artifact_id: str = str(artifact["artifact_id"])
        source_id: str = str(artifact["source_id"])

        # build a lookup: period_id -> period dict
        period_lookup: dict[str, _Obs] = {
            str(p["period_id"]): dict(p) for p in list(artifact["periods"])
        }

        for li in list(artifact["line_items"]):
            normalized_candidate: _Obs | None = li.get("normalized_candidate")
            if normalized_candidate is None:
                continue

            if li.get("value_numeric") is None:
                continue

            period_id: str = str(li["column_ref"])
            period = period_lookup.get(period_id)
            if period is None:
                continue

            taxonomy_key: str = str(normalized_candidate["taxonomy_key"])
            scope: str = str(li["scope"])
            value: float = float(li["value_numeric"])
            currency: str = str(period["currency_reported"])
            restated: bool = bool(period["restated"])

            key: _GroupKey = (scope, period_id, taxonomy_key)
            obs: _Obs = {
                "artifact_id": artifact_id,
                "source_id": source_id,
                "scope": scope,
                "period": period_id,
                "value": value,
                "currency": currency,
                "restated": restated,
            }
            groups[key].append(obs)

    merged: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []

    for key in sorted(groups.keys()):
        scope, period_id, taxonomy_key = key
        observations: list[_Obs] = sorted(
            groups[key], key=lambda o: (str(o["artifact_id"]), str(o["source_id"]))
        )

        currencies: set[str] = {str(o["currency"]) for o in observations}
        restated_flags: set[bool] = {bool(o["restated"]) for o in observations}
        values: set[float] = {float(o["value"]) for o in observations}

        members: list[dict[str, Any]] = [
            {
                "artifact_id": str(o["artifact_id"]),
                "value": float(o["value"]),
                "scope": str(o["scope"]),
                "period": str(o["period"]),
                "source_id": str(o["source_id"]),
            }
            for o in observations
        ]

        # Determine conflict reason (priority: currency > restatement > value).
        reason_code: str | None = None
        if len(currencies) > 1:
            reason_code = "currency_mismatch"
        elif len(restated_flags) > 1:
            reason_code = "restatement"
        elif len(values) > 1:
            reason_code = "source_authority_conflict"

        if reason_code is not None:
            conflicts.append({
                "conflict_id": _conflict_id(scope, period_id, taxonomy_key),
                "reason_code": reason_code,
                "members": members,
                "note": None,
            })
        else:
            # All agree — emit one merged entry retaining all members.
            merged.append({
                "scope": scope,
                "period_id": period_id,
                "taxonomy_key": taxonomy_key,
                "value": float(observations[0]["value"]),
                "currency": str(observations[0]["currency"]),
                "members": members,
            })

    return {"merged": merged, "conflicts": conflicts}


def merge_products(artifacts: list[dict[str, Any]]) -> dict[str, Any]:
    """Merge a list of product_artifact dicts, preserving lineage and emitting conflict sets.

    Groups entities by (entity_type, family) from their normalized_candidate.
    Entities without a normalized_candidate are skipped.
    Lifecycle disagreement within a group emits a conflict_set; otherwise emits a merged entry.

    Args:
        artifacts: List of product_artifact dicts conforming to the CDD schema.

    Returns:
        Dict with keys ``merged`` (agreed entries) and ``conflicts`` (conflict sets).
    """
    groups: defaultdict[_ProductGroupKey, list[_Obs]] = defaultdict(list)

    for artifact in artifacts:
        artifact_id: str = str(artifact["artifact_id"])
        source_id: str = str(artifact["source_id"])

        for entity in list(artifact["entities"]):
            normalized_candidate: _Obs | None = entity.get("normalized_candidate")
            if normalized_candidate is None:
                continue

            family: str = str(normalized_candidate["family"])
            entity_type: str = str(entity["entity_type"])
            name: str = str(entity["source_native_name"])
            lifecycle: str | None = entity.get("lifecycle_status")

            key: _ProductGroupKey = (entity_type, family)
            obs: _Obs = {
                "artifact_id": artifact_id,
                "source_id": source_id,
                "entity_type": entity_type,
                "family": family,
                "name": name,
                "lifecycle": lifecycle,
            }
            groups[key].append(obs)

    merged: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []

    for key in sorted(groups.keys()):
        entity_type, family = key
        observations: list[_Obs] = sorted(
            groups[key], key=lambda o: (str(o["artifact_id"]), str(o["source_id"]))
        )

        lifecycles: set[str | None] = {o["lifecycle"] for o in observations}

        members: list[dict[str, Any]] = [
            {
                "artifact_id": str(o["artifact_id"]),
                "value": str(o["name"]),
                "scope": str(o["entity_type"]),
                "period": None,
                "source_id": str(o["source_id"]),
            }
            for o in observations
        ]

        if len(lifecycles) > 1:
            conflicts.append({
                "conflict_id": _product_conflict_id(entity_type, family),
                "reason_code": "source_authority_conflict",
                "members": members,
                "note": "lifecycle_status disagreement",
            })
        else:
            lifecycle_val: str | None = observations[0]["lifecycle"]
            merged.append({
                "entity_type": entity_type,
                "family": family,
                "lifecycle": lifecycle_val,
                "members": members,
            })

    return {"merged": merged, "conflicts": conflicts}
