"""When a backup is due, which one is newest, and which ones to let go.

A backup button that somebody has to remember to press is not a backup
policy. `utils.create_database_backup()` has always worked; nothing has ever
called it on a schedule, so the plant's protection against a dead disk was
whoever last thought to click it. On a floor PC that is a coin toss, and the
day it matters is the day nobody looked.

So this decides three things:

  is one due       Not "has a day passed since midnight" - the application is
                   not running at midnight and nothing is scheduled outside
                   it. It is "is the newest backup older than a day", asked
                   whenever somebody opens a screen. A PC left on for a week
                   takes seven; one switched on twice a week takes two; one
                   opened five times in an hour takes none.

  which is newest  Read off the filenames rather than the filesystem's
                   timestamps, because a folder copied to another machine
                   arrives with every file stamped the moment it was copied
                   and the real dates are only in the names.

  what to prune    Keep the most recent few and delete the rest. Unbounded
                   backups fill a floor PC's disk quietly, and a disk with no
                   room is the same outage the backups were meant to survive.

Pure functions over a list of filenames and a clock. No database, no
Streamlit, no filesystem in the part that decides - which is what lets the
whole policy be checked in a test that runs in milliseconds, including the
cases nobody can produce on demand: an empty folder, a folder full of
somebody else's files, a clock that has gone backwards.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta

# The name create_database_backup() writes: mes_backup_YYYYmmdd_HHMMSS.sql
BACKUP_NAME_RE = re.compile(r"^mes_backup_(\d{8})_(\d{6})\.sql$")
BACKUP_STAMP = "%Y%m%d_%H%M%S"

# A day, less enough slack that a plant opening the app at roughly the same
# time each morning is not skipped every other day by a few minutes' drift.
DUE_AFTER_HOURS = 20.0

# Enough to cover a fortnight of daily dumps, so a problem introduced and
# noticed a week later still has a copy from before it. Each dump of this
# database is small; the cap is about tidiness, not space.
KEEP_BACKUPS = 14

# Past this, the newest copy is old enough that somebody should be told
# rather than left to notice.
STALE_AFTER_HOURS = 72.0


def backup_time(filename: str):
    """The moment a backup was taken, from its name. None if not one of ours.

    The name is the authority, not the file's modification time: copy the
    folder to a new machine and every file arrives stamped with the moment of
    the copy, which would make a year-old dump look like this morning's.
    """
    m = BACKUP_NAME_RE.match(str(filename or "").strip())
    if not m:
        return None
    try:
        return datetime.strptime(f"{m.group(1)}_{m.group(2)}", BACKUP_STAMP)
    except ValueError:
        return None


def sorted_backups(filenames) -> list:
    """Our backups, newest first, as (filename, taken_at). Others ignored."""
    found = []
    for name in filenames or []:
        when = backup_time(name)
        if when is not None:
            found.append((name, when))
    found.sort(key=lambda pair: (pair[1], pair[0]), reverse=True)
    return found


def newest_backup(filenames):
    """The most recent backup, or None if the folder holds none of ours."""
    found = sorted_backups(filenames)
    return found[0] if found else None


def usable_backups(filenames, now: datetime = None) -> list:
    """Backups that are not stamped in the future, newest first.

    A dump whose name says tomorrow is not evidence that the plant is backed
    up - it is evidence that a clock was wrong when it was written, or that
    the folder came from a machine set differently. Counting it as "recent"
    would suppress every real backup until the clock caught up, which is the
    one outcome this whole module exists to prevent. So it is ignored when
    working out age, and the plant takes another.
    """
    now = now or datetime.now()
    return [(name, when) for name, when in sorted_backups(filenames) if when <= now]


def hours_since_backup(filenames, now: datetime = None):
    """Age of the newest trustworthy backup, or None if there is not one."""
    now = now or datetime.now()
    found = usable_backups(filenames, now)
    if not found:
        return None
    return max(0.0, (now - found[0][1]).total_seconds() / 3600.0)


def is_backup_due(filenames, now: datetime = None,
                  due_after_hours: float = DUE_AFTER_HOURS) -> bool:
    """Whether to take one now.

    No backups at all is always due: that is a plant that has never had one,
    which is the case this exists for.
    """
    age = hours_since_backup(filenames, now)
    return True if age is None else age >= due_after_hours


def backups_to_prune(filenames, keep: int = KEEP_BACKUPS) -> list:
    """The names to delete, oldest first, keeping the most recent `keep`.

    Only files matching our own naming are ever returned. Anything else in
    that folder belongs to somebody else and is not this function's to
    delete.
    """
    keep = max(1, int(keep))
    found = sorted_backups(filenames)
    return [name for name, _ in reversed(found[keep:])]


def backup_state(filenames, now: datetime = None) -> dict:
    """What to tell somebody looking at the backup section of IT Admin.

    Three states, because they need three different responses: `none` is a
    plant that has never taken one, `stale` is one where something has been
    stopping them for days, and `ok` is the ordinary case that should say so
    plainly rather than saying nothing at all - a screen that is silent when
    things are fine is indistinguishable from a screen that is broken.
    """
    now = now or datetime.now()
    all_found = sorted_backups(filenames)
    found = usable_backups(filenames, now)
    age = hours_since_backup(filenames, now)
    if not found:
        return {"state": "none", "count": len(all_found), "newest": None,
                "age_hours": None,
                "message": ("No backup has ever been taken on this machine."
                            if not all_found else
                            "Every backup here is dated in the future. "
                            "Check this machine's clock.")}
    newest_name, newest_at = found[0]
    if age >= STALE_AFTER_HOURS:
        days = age / 24.0
        return {"state": "stale", "count": len(found), "newest": newest_name,
                "age_hours": age,
                "message": f"The newest backup is {days:.0f} days old. "
                           f"Something is stopping the automatic one."}
    return {"state": "ok", "count": len(found), "newest": newest_name,
            "age_hours": age,
            "message": (f"Last backup {_ago(age)}, {len(found)} kept."
                        if age >= 1 else
                        f"Last backup less than an hour ago, {len(found)} kept.")}


def _ago(hours: float) -> str:
    if hours < 24:
        h = int(round(hours))
        return "1 hour ago" if h == 1 else f"{h} hours ago"
    days = int(round(hours / 24.0))
    return "yesterday" if days == 1 else f"{days} days ago"
