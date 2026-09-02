"""How many shifts this plant runs, and which one it is right now.

The app was built assuming three shifts. This plant runs two. Rather than
delete the third everywhere and bake in a new wrong number, the count is a
plant setting - because "how many shifts do we run" is exactly the sort of
thing that changes when a plant gets busy, and it should not require anyone
to edit source when it does.

Two rules shape everything here:

**Historical rows still say what they said.** Logs written when the app
offered three shifts carry "Shift 3", and they are real production. Those
rows must keep displaying, filtering and editing correctly forever, so
nothing in this module ever rewrites or hides them - the pickers just stop
OFFERING a shift the plant no longer runs, and keep offering one that a
record already holds so editing that record cannot silently reassign
somebody's work to a different shift.

**A shift boundary is a wrap-around, not a sort.** The last shift of the day
runs past midnight into the next, so "which shift is 01:30" cannot be
answered by comparing strings and taking the largest - 01:30 is smaller than
every start time, and the naive answer is "none of them".

Deliberately free of Streamlit and of the database: it takes a settings dict
and, where it matters, a clock.
"""
from __future__ import annotations

from datetime import datetime, time

FLOATER = "Floater"

# What the app shipped with before the count was configurable. Kept as the
# ceiling for legacy labels so a stored "Shift 3" is recognised as a real
# historical shift rather than as junk.
MAX_TRACKED_SHIFTS = 3

DEFAULT_STARTS = {1: "06:00", 2: "14:30", 3: "23:00"}


def shift_count(settings=None) -> int:
    """How many shifts this plant runs. Clamped to something sane."""
    try:
        n = int((settings or {}).get("shift_count", 2))
    except (TypeError, ValueError):
        n = 2
    return max(1, min(n, MAX_TRACKED_SHIFTS))


def shift_labels(settings=None) -> list[str]:
    """The shifts this plant currently runs, in order."""
    return [f"Shift {i}" for i in range(1, shift_count(settings) + 1)]


def picker_options(settings=None, current: str = None) -> list[str]:
    """Options for a shift dropdown.

    `current` is whatever the record being edited already holds. If that is a
    shift the plant no longer runs, it is kept in the list - otherwise
    opening an old record and pressing save would quietly move that person's
    work to a shift they never worked, and the record would look edited
    rather than corrupted.
    """
    opts = shift_labels(settings) + [FLOATER]
    cur = (current or "").strip()
    if cur and cur not in opts:
        opts.append(cur)
    return opts


def is_retired(label: str, settings=None) -> bool:
    """True for a real shift label the plant has since stopped running."""
    lab = (label or "").strip()
    return bool(lab) and lab != FLOATER and lab not in shift_labels(settings)


def _parse_hhmm(value, fallback: str) -> time:
    for candidate in (value, fallback):
        try:
            h, m = str(candidate).strip().split(":")[:2]
            return time(int(h) % 24, int(m) % 60)
        except (ValueError, AttributeError, TypeError):
            continue
    return time(6, 0)


def shift_windows(settings=None) -> list[tuple[str, time]]:
    """(label, start time) for each shift the plant runs, earliest first."""
    n = shift_count(settings)
    s = settings or {}
    out = []
    for i in range(1, n + 1):
        start = _parse_hhmm(s.get(f"shift_{i}_start"), DEFAULT_STARTS.get(i, "06:00"))
        out.append((f"Shift {i}", start))
    out.sort(key=lambda p: p[1])
    return out


def current_shift(settings=None, now: datetime = None) -> str:
    """Which shift a moment falls in.

    Handles the wrap-around: the last shift of the day owns everything from
    its start time until the first shift begins the next morning, so 01:30 on
    a two-shift plant belongs to Shift 2, not to nothing.
    """
    windows = shift_windows(settings)
    if not windows:
        return "Shift 1"
    t = (now or datetime.now()).time()
    chosen = windows[-1][0]          # before the first start = still last night's
    for label, start in windows:
        if t >= start:
            chosen = label
    return chosen


def is_outside_day_shift(settings=None, now: datetime = None) -> bool:
    """True when the clock is outside the FIRST shift of the day.

    Used to warm and dim the interface for whoever is on late: a screen
    stared at for eight hours in a dim plant should not be running the same
    brightness it uses at ten in the morning. Deliberately derived from the
    plant's own configured start times rather than a hardcoded hour, because
    "night" here means "not the day shift", which is a local fact.
    """
    windows = shift_windows(settings)
    if len(windows) < 2:
        return False
    return current_shift(settings, now) != windows[0][0]
