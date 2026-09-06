"""What shift is running right now, and how far into it the plant is.

Lifted out of Home.py because the wall display needs the same answer and was
deriving its own. The application already learned this lesson once - the
"Live Today" filter and the shift trajectory card each had their own slightly
different copy and they disagreed - and the fix then was one function on one
page. It is the same fix now, one module wider.

Two things this gets right that a naive version does not, both of them
recorded here because they were bugs before they were features:

  Timezone   The plant's local time, not the server's raw clock. Every logged
             timestamp elsewhere is converted to the plant's zone; a shift
             calculation on the machine's own clock could be wrong by however
             many hours the PC is offset from the floor.

  Midnight   It checks yesterday's start time as well as today's for every
             shift. A shift still running from a start the previous calendar
             day - which is what a night shift is - reads correctly, and one
             that has already ended but whose start time still looks like
             "later today" does not read as upcoming.

No Streamlit and no database: a dictionary of settings and a clock in, a
dictionary out.
"""
from datetime import datetime, timedelta, time as dtime
from zoneinfo import ZoneInfo

# ===================== SHIFT STATUS ENGINE =====================
# Single source of truth for "what shift is running right now." Used both
# by the "Live Today" data filter above and the Live Shift Trajectory card
# further down the page — previously each had its own, slightly different
# copy of this logic, and they could (and did) disagree.
#
# Two bugs fixed here at once:
#   1. Timezone: this used datetime.now(), the server's raw system clock,
#      which is not necessarily the plant's own local time. Logged
#      timestamps elsewhere on this page are explicitly tz_convert()'d to
#      America/New_York for the same reason — this calculation just never
#      got the same treatment, so "is a shift active" could be wrong by
#      however many hours the server is offset from the floor.
#   2. Midnight rollover: it only ever checked "did this shift start
#      earlier TODAY," so a shift that's still running from a start time
#      the previous calendar day (or one that already ended hours ago but
#      whose start time still looks like "later today") could report the
#      wrong answer well into the night. This checks both today's and
#      yesterday's start time for each shift.
PLANT_TZ = ZoneInfo("America/New_York")


def _shift_window(base_date, start_h, start_m, gross_hours):
    start = datetime.combine(base_date, dtime(start_h, start_m), tzinfo=PLANT_TZ)
    end = start + timedelta(hours=gross_hours)
    return start, end


def compute_shift_status(settings):
    now = datetime.now(PLANT_TZ)
    today = now.date()
    yesterday = today - timedelta(days=1)
    tomorrow = today + timedelta(days=1)

    s1_h, s1_m = map(int, settings["shift_1_start"].split(":"))
    s2_h, s2_m = map(int, settings["shift_2_start"].split(":"))
    s1_gross = float(settings["shift_1_hours"])
    s2_gross = float(settings["shift_2_hours"])
    s1_break = float(settings.get("shift_1_break_mins", 60.0)) / 60.0
    s2_break = float(settings.get("shift_2_break_mins", 60.0)) / 60.0
    s1_net = max(0.1, s1_gross - s1_break)
    s2_net = max(0.1, s2_gross - s2_break)

    shifts = [
        ("Shift 1", s1_h, s1_m, s1_gross, s1_net),
        ("Shift 2", s2_h, s2_m, s2_gross, s2_net),
    ]

    # Check "started yesterday" first so a still-running overnight shift
    # takes priority over anything that merely "starts today" but hasn't
    # happened yet.
    for base_date in (yesterday, today):
        for name, h, m, gross, net in shifts:
            start, end = _shift_window(base_date, h, m, gross)
            if start <= now < end:
                elapsed_gross = (now - start).total_seconds() / 3600.0
                elapsed_net = elapsed_gross * (net / gross) if gross > 0 else 0.0
                return {
                    "is_active": True,
                    "shift_name": name,
                    "started_at": start,
                    "elapsed_net": elapsed_net,
                    "shift_net_hours": net,
                    "remaining_hours": max(0.0, net - elapsed_net),
                    "shift_pct": min(100.0, max(0.0, (elapsed_net / net) * 100.0)) if net > 0 else 0.0,
                    "next_shift_label": "",
                }

    # No shift running — find the next one so the idle state can say
    # something useful instead of just "nothing's active."
    upcoming = []
    for base_date in (today, tomorrow):
        for name, h, m, gross, net in shifts:
            start, _ = _shift_window(base_date, h, m, gross)
            if start > now:
                upcoming.append((start, name))
    upcoming.sort(key=lambda x: x[0])
    next_shift_label = ""
    if upcoming:
        next_start, next_name = upcoming[0]
        next_shift_label = f"{next_name} at {next_start.strftime('%I:%M %p').lstrip('0')}"

    return {
        "is_active": False,
        "shift_name": "Off-Shift",
        "started_at": None,
        "elapsed_net": 0.0,
        "shift_net_hours": s1_net,
        "remaining_hours": 0.0,
        "shift_pct": 0.0,
        "next_shift_label": next_shift_label,
    }
