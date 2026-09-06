"""Two things that only matter on the day nobody is watching.

A backup policy and a stopped-record alarm share an awkward property: the
only way to find out by hand whether either works is to wait for the thing
they exist to catch. Nobody is going to switch the plant PC off for four days
to see whether the backup notice turns red, and nobody is going to stop
logging for three hours in the middle of a shift to see whether the wall
display says so. So both were written as functions of a clock and a list,
and the cases live here instead: the fourth hour of silence, the folder with
no backups in it at all, the machine whose clock went backwards.

No database, no filesystem, no browser. The parts that touch those are thin
enough to read; the parts that decide anything are all here.
"""
import pathlib
import sys
from datetime import datetime, timedelta, timezone

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import backup_policy as bp  # noqa: E402
import record_health as rh  # noqa: E402

FAILS, CHECKS = [], 0


def check(label, got, exp):
    global CHECKS
    CHECKS += 1
    if got != exp:
        FAILS.append(f"  x {label}\n      got:      {got!r}\n      expected: {exp!r}")


NOW = datetime(2026, 9, 6, 14, 0, 0)


def stamp(hours_ago):
    t = NOW - timedelta(hours=hours_ago)
    return f"mes_backup_{t.strftime('%Y%m%d_%H%M%S')}.sql"


print("=" * 66)
print("BACKUPS AND THE STOPPED RECORD")
print("=" * 66)

# --- reading a backup's age off its own name ------------------------------
# Deliberately not off the filesystem: copy the folder to another machine and
# every file arrives stamped with the moment of the copy.
check("a backup's time comes from its name",
      bp.backup_time("mes_backup_20260906_070000.sql"), datetime(2026, 9, 6, 7, 0, 0))
check("something else in the folder is not one of ours",
      bp.backup_time("notes.txt"), None)
check("nor is a near miss", bp.backup_time("mes_backup_2026_09_06.sql"), None)
check("nor is a name with an impossible date",
      bp.backup_time("mes_backup_20261340_070000.sql"), None)
check("nor is nothing at all", bp.backup_time(None), None)
print("  reading backup names OK")

# --- when one is due -------------------------------------------------------
check("a plant that has never taken one is always due",
      bp.is_backup_due([], NOW), True)
check("and a folder holding only somebody else's files still is",
      bp.is_backup_due(["notes.txt", "old.zip"], NOW), True)
check("one taken this morning is not due", bp.is_backup_due([stamp(6)], NOW), False)
check("one from yesterday is", bp.is_backup_due([stamp(25)], NOW), True)
check("the newest is what counts, not the oldest",
      bp.is_backup_due([stamp(200), stamp(1)], NOW), False)

# A machine that has just had its clock corrected must not be able to skip
# backups for as long as the error lasted.
# The first version of this clamped a future stamp to an age of zero, which
# read as "backed up just now" and would have suppressed every real backup
# until the clock caught up - the exact outcome the module exists to prevent.
# A dump dated tomorrow is not evidence of a backup, it is evidence of a
# wrong clock, so it is not counted at all.
check("a backup dated in the future counts as no backup",
      bp.hours_since_backup([stamp(-48)], NOW), None)
check("so the plant takes one rather than skipping it",
      bp.is_backup_due([stamp(-48)], NOW), True)
check("and a real one from yesterday is not hidden behind it",
      bp.is_backup_due([stamp(-48), stamp(30)], NOW), True)
check("while a real one from this morning still counts",
      bp.is_backup_due([stamp(-48), stamp(6)], NOW), False)
check("a folder of nothing but future dates says so rather than 'never'",
      "clock" in bp.backup_state([stamp(-48)], NOW)["message"], True)
print("  when one is due OK")

# --- what gets deleted -----------------------------------------------------
many = [stamp(h) for h in range(1, 21)]
prune = bp.backups_to_prune(many, keep=14)
check("only the surplus is pruned", len(prune), 6)
check("and it is the oldest that go", prune[0], stamp(20))
check("the newest is never pruned", stamp(1) in prune, False)
check("nothing is pruned when there is nothing spare",
      bp.backups_to_prune([stamp(1), stamp(2)], keep=14), [])

# The one that matters: this deletes files on somebody's plant PC.
check("a file that is not ours is never returned for deletion",
      bp.backups_to_prune(["payroll.xlsx", "IMPORTANT.sql"] + many, keep=1)[-1] != "payroll.xlsx",
      True)
check("in fact nothing but our own backups is ever returned",
      all(bp.backup_time(n) is not None
          for n in bp.backups_to_prune(["payroll.xlsx"] + many, keep=2)), True)
check("keeping zero is refused - it would leave the plant with none",
      len(bp.backups_to_prune(many, keep=0)), 19)
print("  pruning OK")

# --- what IT Admin is told -------------------------------------------------
check("a plant with no backups is told so", bp.backup_state([], NOW)["state"], "none")
check("a plant backing up daily is told it is fine",
      bp.backup_state([stamp(6), stamp(30)], NOW)["state"], "ok")
check("and one where they stopped days ago is told that instead",
      bp.backup_state([stamp(100)], NOW)["state"], "stale")
check("the stale message says how old, not just that it is old",
      "4 days old" in bp.backup_state([stamp(100)], NOW)["message"], True)
check("the healthy message says when, so silence never means broken",
      "hours ago" in bp.backup_state([stamp(6)], NOW)["message"], True)
print("  what IT Admin is told OK")

# --- the record, and whether it is still being fed -------------------------
SHIFT_START = NOW - timedelta(hours=8)


def state(mins_ago, active=True, started=SHIFT_START):
    at = None if mins_ago is None else NOW - timedelta(minutes=mins_ago)
    return rh.record_state(at, active, NOW, started)


check("an hour of quiet mid-shift is an ordinary hour", state(60)["state"], "flowing")
check("nearly two hours is worth flagging quietly", state(110)["state"], "quiet")
check("four hours in a running shift is an alarm", state(240)["state"], "stalled")
check("and only that one is an alarm", state(110)["is_alarm"], False)
check("a plant with nothing logged at all says so", state(None)["state"], "no-record")

# The rule that decides whether anybody keeps reading this: silence when
# nothing is being poured is not a fault.
check("overnight silence off-shift is not a fault",
      state(600, active=False)["state"], "idle")
check("and raises nothing", state(600, active=False)["is_warning"], False)

# And a shift that has only just started has not failed to log; last night's
# gap is not this shift's problem.
check("a shift five minutes old is not blamed for last night",
      state(600, started=NOW - timedelta(minutes=5))["state"], "flowing")
check("but the same gap four hours in is an alarm",
      state(600, started=NOW - timedelta(hours=4))["state"], "stalled")

check("a log stamped in the future reads as just now, not as negative time",
      rh.minutes_since(NOW + timedelta(hours=3), NOW), 0.0)

# The one that took the home page down before it shipped. Log timestamps come
# out of the database naive and in UTC; the shift clock hands over an aware
# plant-local time. Subtract them unconverted and Python refuses and the page
# dies. Convert one wrongly and it is worse - the sum works and every log
# reads hours old, so the alarm fires all day and people stop reading it.
_utc = timezone.utc
_plant = timezone(timedelta(hours=-4))          # the plant, in summer
_naive_utc_log = datetime(2026, 9, 6, 17, 30)   # 13:30 on the floor
_aware_now = datetime(2026, 9, 6, 14, 0, tzinfo=_plant)   # 18:00 UTC
check("a naive UTC log against an aware plant clock does not raise",
      rh.minutes_since(_naive_utc_log, _aware_now), 30.0)
mixed = rh.record_state(_naive_utc_log, True, _aware_now,
                        shift_started_at=datetime(2026, 9, 6, 6, 0, tzinfo=_plant))
check("and reads as half an hour old, not as five hours", mixed["state"], "flowing")
check("so nothing false is raised at half an hour", mixed["is_warning"], False)
check("wording is human, not a raw number of minutes",
      "2 hours ago" in state(90)["message"], True)
check("and under an hour it counts in minutes",
      "40 minutes ago" in state(40)["message"], True)
print("  the stopped record OK")

print("\n" + "=" * 66)
if FAILS:
    print(f"{len(FAILS)} of {CHECKS} HEALTH CHECKS FAILED:\n" + "\n".join(FAILS))
else:
    print(f"ALL {CHECKS} HEALTH ASSERTIONS PASSED")
raise SystemExit(1 if FAILS else 0)
