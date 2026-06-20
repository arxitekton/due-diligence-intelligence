from datetime import UTC, datetime

from cdd.changelog import render_change_log
from cdd.diff import RunDiff


def _diff() -> RunDiff:
    return RunDiff(
        from_run="runA", to_run="runB", delta_type="source_delta",
        sources_added=["src_0000000000000002"],
        sources_removed=[],
        sources_changed=[{"source_id": "src_0000000000000001", "diff_class": "content_change"}],
        sources_unavailable=["src_0000000000000003"],
    )


def test_change_log_contains_sections_and_header():
    md = render_change_log(_diff(), now=datetime(2026, 6, 20, 18, 30, tzinfo=UTC))
    assert "# Change Log" in md
    assert "runA" in md and "runB" in md
    assert "source_delta" in md
    assert "## New sources" in md
    assert "## Changed sources" in md
    assert "## Unavailable sources" in md
    assert "## Removed sources" in md
    assert "src_0000000000000002" in md
    assert "src_0000000000000001" in md and "content_change" in md
    assert "src_0000000000000003" in md
    assert "2026-06-20T18:30:00Z" in md


def test_change_log_empty_sections_say_none():
    empty = RunDiff(
        from_run="r1", to_run="r2", delta_type="source_delta",
        sources_added=[], sources_removed=[], sources_changed=[], sources_unavailable=[],
    )
    md = render_change_log(empty, now=datetime(2026, 6, 20, tzinfo=UTC))
    assert md.count("_None_") == 4
