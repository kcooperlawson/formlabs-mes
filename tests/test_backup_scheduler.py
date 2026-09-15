"""api/backup_scheduler.py's throttle logic, ported from Home.py's own
@st.cache_data(ttl=3600) daily backup check.

Deliberately never calls maybe_run_scheduled_backup() for real: BACKUP_DIR
is a fixed path on disk shared with the real backup rotation regardless of
which database is active, so actually invoking it here - even against this
test's own scratch database - would write into and prune the real one, the
same incident this comment exists to prevent a repeat of. The pure bucket
logic (_is_new_bucket) is tested directly instead; the TEST_DB_URL/
MES_DISABLE_AUTO_BACKUP guards are tested by confirming the public function
is a documented, deliberate no-op under the test harness itself.
"""
import os
import pathlib
import sys
from datetime import datetime

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from _boot import boot  # noqa: E402

boot(fresh=False)  # no database needed at all for this one

import api.backup_scheduler as sched  # noqa: E402

FAILS, CHECKS = [], 0


def check(cond, label):
    global CHECKS
    CHECKS += 1
    if not cond:
        FAILS.append(label)
        print(f"  FAIL  {label}")


print("=" * 66)
print("BACKUP SCHEDULER: the throttled once-an-hour check")
print("=" * 66)

# Reset module state - other tests in the same process may have already
# touched this.
sched._last_checked_bucket = None

now = datetime(2026, 1, 1, 10, 30)
check(sched._is_new_bucket(now) is True, "the first check in an hour-bucket fires")
check(sched._is_new_bucket(now) is False, "a second check in the SAME hour-bucket does not")
check(sched._is_new_bucket(datetime(2026, 1, 1, 10, 59)) is False,
      "...even fifty-nine minutes later, still the same bucket")
check(sched._is_new_bucket(datetime(2026, 1, 1, 11, 0)) is True,
      "the next hour-bucket fires again")
check(sched._is_new_bucket(datetime(2026, 1, 2, 10, 30)) is True,
      "a bucket a full day later (same hour-of-day) is still a new bucket")

# --- the public entrypoint must be inert under the test harness -----------
# This test itself is running under TEST_DB_URL (see tests/_boot.py) - the
# same environment every other automated test runs under - so this call is
# exactly the one a careless integration test could get wrong and actually
# touch the real backups/ directory. It must not.
check(bool(os.environ.get("TEST_DB_URL")), "sanity check: this test really is running under TEST_DB_URL")
sched._last_checked_bucket = None
before = sched._last_checked_bucket
sched.maybe_run_scheduled_backup()
check(sched._last_checked_bucket == before,
      "maybe_run_scheduled_backup() is a documented no-op under TEST_DB_URL - it never even reaches the bucket check")

# --- MES_DISABLE_AUTO_BACKUP is a second, independent off-switch -----------
_saved = os.environ.pop("TEST_DB_URL")
try:
    os.environ["MES_DISABLE_AUTO_BACKUP"] = "1"
    sched._last_checked_bucket = None
    sched.maybe_run_scheduled_backup()
    check(sched._last_checked_bucket is None,
          "MES_DISABLE_AUTO_BACKUP alone is enough to suppress it, even without TEST_DB_URL")
finally:
    os.environ.pop("MES_DISABLE_AUTO_BACKUP", None)
    os.environ["TEST_DB_URL"] = _saved

print("\n" + "=" * 66)
if FAILS:
    print(f"{len(FAILS)} of {CHECKS} BACKUP SCHEDULER CHECKS FAILED:")
    for f in FAILS:
        print(f"  - {f}")
else:
    print(f"ALL {CHECKS} BACKUP SCHEDULER ASSERTIONS PASSED")
raise SystemExit(1 if FAILS else 0)
