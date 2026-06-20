from datetime import UTC, datetime

from cdd.timeutil import compact_stamp, iso_utc


def test_iso_utc_formats_with_z_suffix():
    dt = datetime(2026, 6, 20, 18, 30, 0, tzinfo=UTC)
    assert iso_utc(dt) == "2026-06-20T18:30:00Z"


def test_compact_stamp_is_run_id_safe():
    dt = datetime(2026, 6, 20, 18, 30, 0, tzinfo=UTC)
    assert compact_stamp(dt) == "20260620T183000Z"
