"""The automatic backup, ported from Home.py's own
@st.cache_data(ttl=3600)-wrapped daily check: ride the backup on whoever
happens to be using the app, throttled to at most once per hour-bucket per
process, rather than a second scheduler process to install, configure and
forget. backup_policy.is_backup_due (inside utils.run_scheduled_backup)
decides whether one is actually taken; most calls here do nothing but
compare a bucket string.

Wired into api.deps.get_current_user, so it rides on essentially every
authenticated request the same way the original rides on every page load.

Skipped entirely under TEST_DB_URL (the test harness always sets this - see
tests/_boot.py) or MES_DISABLE_AUTO_BACKUP: BACKUP_DIR is a fixed path on
disk, shared with the real backup rotation regardless of which database
DB_URL happens to point at, so running this against a scratch or dev
database still writes into - and prunes - the real one. Set
MES_DISABLE_AUTO_BACKUP=1 whenever running a dev server against anything
other than the actual production database.
"""
import os
import threading
from datetime import datetime

_last_checked_bucket: str | None = None
_lock = threading.Lock()


def _is_new_bucket(now: datetime | None = None) -> bool:
    """True at most once per hour-bucket, across however many times this
    is called - the pure part of the throttle, kept separate from the
    thread-spawning side effect so it can be tested without ever touching
    a real backup."""
    global _last_checked_bucket
    bucket = (now or datetime.now()).strftime("%Y%m%d%H")
    with _lock:
        if _last_checked_bucket == bucket:
            return False
        _last_checked_bucket = bucket
        return True


def _run_backup() -> None:
    import utils
    utils.run_scheduled_backup()


def maybe_run_scheduled_backup() -> None:
    if os.environ.get("TEST_DB_URL") or os.environ.get("MES_DISABLE_AUTO_BACKUP"):
        return
    if not _is_new_bucket():
        return
    # pg_dump is a real subprocess call - kicked off on a background thread
    # so the request that happened to trigger the hourly check isn't the
    # one left waiting on it.
    threading.Thread(target=_run_backup, daemon=True).start()
