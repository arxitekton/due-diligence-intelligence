"""Pure UTC time formatting helpers (no clock reads)."""

from datetime import UTC, datetime


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def iso_utc(dt: datetime) -> str:
    """RFC3339 UTC, second precision, 'Z' suffix."""
    return _as_utc(dt).strftime("%Y-%m-%dT%H:%M:%SZ")


def compact_stamp(dt: datetime) -> str:
    """Compact UTC stamp suitable for run_id prefixes."""
    return _as_utc(dt).strftime("%Y%m%dT%H%M%SZ")
