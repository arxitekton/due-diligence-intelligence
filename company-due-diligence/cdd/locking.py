"""Advisory per-company file lock (single-writer for shared registries/manifest)."""

import json
import os
from collections.abc import Generator
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path

from cdd.timeutil import iso_utc


class LockHeld(RuntimeError):
    pass


@contextmanager
def company_lock(
    company_dir: Path,
    *,
    owner: str,
    now: datetime,
    stale_after: timedelta = timedelta(hours=1),
) -> Generator[None, None, None]:
    company_dir = Path(company_dir)
    company_dir.mkdir(parents=True, exist_ok=True)
    lock = company_dir / ".lock"
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        if _is_stale(lock, now, stale_after):
            lock.unlink(missing_ok=True)
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        else:
            raise LockHeld(f"lock held on {company_dir}") from None
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump({"owner": owner, "acquired_at": iso_utc(now)}, fh)
        yield
    finally:
        lock.unlink(missing_ok=True)


def _is_stale(lock: Path, now: datetime, stale_after: timedelta) -> bool:
    try:
        data: dict[str, object] = json.loads(lock.read_text(encoding="utf-8"))
        acquired = datetime.strptime(str(data["acquired_at"]), "%Y-%m-%dT%H:%M:%SZ")
        acquired = acquired.replace(tzinfo=now.tzinfo)
        return now - acquired > stale_after
    except (OSError, ValueError, KeyError):
        # Empty/unparseable lock: a just-created lock is momentarily empty between
        # O_EXCL creation and the JSON write — do NOT treat that as stale (it would
        # let a concurrent acquirer steal a valid fresh lock). Fall back to file
        # mtime: only consider it stale if the file itself is older than stale_after.
        try:
            mtime = datetime.fromtimestamp(lock.stat().st_mtime, tz=now.tzinfo)
        except OSError:
            return True
        return now - mtime > stale_after
