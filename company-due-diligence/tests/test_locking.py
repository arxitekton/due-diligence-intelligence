from datetime import UTC, datetime
from pathlib import Path

import pytest

from cdd.locking import LockHeld, company_lock


def test_lock_acquire_and_release(tmp_path: Path):
    d = tmp_path / "companies" / "acme-corp"
    d.mkdir(parents=True)
    with company_lock(d, owner="run-1", now=datetime(2026, 6, 20, tzinfo=UTC)):
        assert (d / ".lock").exists()
    assert not (d / ".lock").exists()


def test_lock_blocks_second_holder(tmp_path: Path):
    d = tmp_path / "companies" / "acme-corp"
    d.mkdir(parents=True)
    now = datetime(2026, 6, 20, 12, 0, 0, tzinfo=UTC)
    with company_lock(d, owner="run-1", now=now):
        with pytest.raises(LockHeld):
            with company_lock(d, owner="run-2", now=now):
                pass


def test_empty_fresh_lock_is_not_stolen(tmp_path: Path):
    # Simulate the race window: a lock file exists but is still empty (not yet
    # written). A fresh empty lock must be treated as held, not stale.
    d = tmp_path / "companies" / "acme-corp"
    d.mkdir(parents=True)
    (d / ".lock").write_text("", encoding="utf-8")
    now = datetime(2026, 6, 20, 12, 0, 0, tzinfo=UTC)
    with pytest.raises(LockHeld):
        with company_lock(d, owner="run-2", now=now):
            pass
