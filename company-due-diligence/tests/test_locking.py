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
