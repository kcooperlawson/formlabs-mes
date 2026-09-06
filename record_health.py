"""Whether the record is still being fed, and how loudly to say it is not.

This is the characteristic way a system like this fails. It does not crash
and it does not corrupt anything. The PC reboots and Postgres does not come
back, or the app is closed and nobody reopens it, or an operator's phone
cannot reach the plant address - and the application carries on looking
exactly as it always does, showing yesterday's figures with today's date on
the page. The floor finds out when somebody tries to log an hour. Management
finds out weeks later, when a month is queried and there is a hole in it.

The record cannot notice its own absence, but it can notice its own age. Logs
arrive about once an hour, so an hour of quiet is normal, two is a break or a
changeover, and three during a running shift means something is wrong and
nobody has said so.

Two rules make this bearable to live with rather than a boy-who-cried-wolf:

  Silence off-shift is not a fault. Nothing is being poured at three in the
  morning, and a screen that shouts about it all night is a screen people
  stop reading - which is the same as not having it.

  A shift that has only just started has not failed to log; it has not had
  time to. The alarm waits out its own threshold from the shift's start.

Pure functions of a timestamp, a clock and whether a shift is running. No
database and no Streamlit, so every case here can be checked in a test -
including the ones nobody can produce on demand, like the fourth hour of
silence in the middle of a running shift.
"""
from __future__ import annotations

from datetime import datetime, timezone

# Everything here is compared in UTC, and that is not a detail.
#
# Log timestamps are stored naive and in UTC - the column defaults to
# datetime.utcnow, and every screen that displays one localises it to UTC and
# then converts to the plant's zone. The shift clock, by contrast, works in
# aware plant-local time, because a shift starts at six in the morning where
# the pumps are and not where the server thinks it is.
#
# Hand those two to each other unconverted and Python refuses outright -
# "can't subtract offset-naive and offset-aware datetimes" - which takes the
# whole page down. Convert one of them wrongly instead, and it is worse: the
# arithmetic succeeds and every log reads as four or five hours old, so the
# alarm below fires all day and people learn to ignore it. A naive value is
# therefore read as UTC, which is what the database actually holds, and an
# aware one is converted.


# Logs come in hourly. One missed hour is a long changeover; three in a row
# during production is not something that happens quietly for a good reason.
QUIET_AFTER_MINUTES = 100.0
STALLED_AFTER_MINUTES = 190.0

STATES = ("no-record", "idle", "flowing", "quiet", "stalled")


def _as_utc(value):
    """Any datetime as an aware UTC one. A naive value is taken to be UTC."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def minutes_since(last_log_at, now: datetime = None):
    """Minutes since the last log, or None if nothing has ever been logged."""
    if last_log_at is None:
        return None
    delta = _as_utc(now or datetime.now(timezone.utc)) - _as_utc(last_log_at)
    # A log stamped in the future - a clock corrected backwards, a restored
    # database from a machine set differently - reads as "just now" rather
    # than as a negative age that would suppress every warning below it.
    return max(0.0, delta.total_seconds() / 60.0)


def record_state(last_log_at, shift_active: bool, now: datetime = None,
                 shift_started_at: datetime = None) -> dict:
    """How the record is doing, in a form a header or a wall display can show.

    `shift_started_at` lets a shift that has only just begun off the hook: a
    plant that starts at six should not be told at 06:05 that nothing has
    been logged for fourteen hours, because that is simply last night.
    """
    now = _as_utc(now or datetime.now(timezone.utc))
    mins = minutes_since(last_log_at, now)

    if mins is None:
        return _state("no-record", None,
                      "Nothing has been logged yet on this system.")

    if not shift_active:
        return _state("idle", mins,
                      f"Last log {_ago(mins)}. No shift running.")

    # How long production has actually had to produce a log.
    into_shift = None
    if shift_started_at is not None:
        into_shift = max(0.0, (now - _as_utc(shift_started_at)).total_seconds() / 60.0)

    def past(threshold):
        if into_shift is not None and into_shift < threshold:
            return False
        return mins >= threshold

    if past(STALLED_AFTER_MINUTES):
        return _state("stalled", mins,
                      f"No production logged for {_ago(mins).replace(' ago', '')}. "
                      f"Check the pumps and this machine.")
    if past(QUIET_AFTER_MINUTES):
        return _state("quiet", mins,
                      f"Nothing logged for {_ago(mins).replace(' ago', '')}.")
    return _state("flowing", mins, f"Last log {_ago(mins)}.")


def _state(name, mins, message) -> dict:
    return {"state": name,
            "minutes": mins,
            "is_alarm": name == "stalled",
            "is_warning": name in ("quiet", "stalled", "no-record"),
            "message": message}


def _ago(minutes: float) -> str:
    m = int(round(minutes))
    if m < 1:
        return "just now"
    if m < 60:
        return "1 minute ago" if m == 1 else f"{m} minutes ago"
    hours = m / 60.0
    if hours < 24:
        h = int(round(hours))
        return "1 hour ago" if h == 1 else f"{h} hours ago"
    days = int(round(hours / 24.0))
    return "yesterday" if days == 1 else f"{days} days ago"
