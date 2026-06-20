"""Render a Markdown change log from a RunDiff (P2.7)."""

from __future__ import annotations

from datetime import datetime

from cdd.diff import RunDiff
from cdd.timeutil import iso_utc


def render_change_log(diff: RunDiff, *, now: datetime) -> str:
    """Return a deterministic Markdown change log for *diff*.

    Args:
        diff: The :class:`~cdd.diff.RunDiff` produced by comparing two runs.
        now: Timestamp used as the generation time (caller-supplied for determinism).

    Returns:
        A Markdown string with a title, header block, and four categorised
        sections (new / changed / unavailable / removed sources).
    """
    generated = iso_utc(now)

    added_count = len(diff.sources_added)
    changed_count = len(diff.sources_changed)
    unavailable_count = len(diff.sources_unavailable)
    removed_count = len(diff.sources_removed)

    lines: list[str] = [
        "# Change Log",
        "",
        f"Generated: {generated}",
        f"From run:  {diff.from_run}",
        f"To run:    {diff.to_run}",
        f"Delta type: {diff.delta_type}",
        (
            f"Counts: {added_count} added, {changed_count} changed, "
            f"{unavailable_count} unavailable, {removed_count} removed"
        ),
        "",
        "## New sources",
        "",
    ]

    if diff.sources_added:
        for sid in sorted(diff.sources_added):
            lines.append(f"- {sid}")
    else:
        lines.append("_None_")

    lines += [
        "",
        "## Changed sources",
        "",
    ]

    if diff.sources_changed:
        for entry in sorted(diff.sources_changed, key=lambda e: e["source_id"]):
            lines.append(f"- `{entry['source_id']}` — {entry['diff_class']}")
    else:
        lines.append("_None_")

    lines += [
        "",
        "## Unavailable sources",
        "",
    ]

    if diff.sources_unavailable:
        for sid in sorted(diff.sources_unavailable):
            lines.append(f"- {sid}")
    else:
        lines.append("_None_")

    lines += [
        "",
        "## Removed sources",
        "",
    ]

    if diff.sources_removed:
        for sid in sorted(diff.sources_removed):
            lines.append(f"- {sid}")
    else:
        lines.append("_None_")

    lines.append("")
    return "\n".join(lines)
