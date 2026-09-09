"""What the plant is expected to pour, worked out instead of typed.

There used to be one number for the whole floor. Four hundred litres an hour
in plant settings, multiplied by however long the shift had been running, and
every pace figure in the application measured against it. It cannot be right
two days running. One pourer read sixty per cent behind and three read
comfortably ahead, and the only lever management had was to retype the number,
which then had to be retyped tomorrow.

Two things are being confused in that one figure. How fast a pump goes, which
is a property of the equipment and does not change from one day to the next,
and how many pumps are running, which changes every shift. So the rate lives
on the pump now, set once when it is installed or rebuilt, and how many are
running is read off what the floor already told us.

Where the hours come from matters more than it looks. Not from the pouring
logs: a station that poured nothing would then be expected to pour nothing,
the target would shrink to meet the output, and the plant could never be
behind. A dashboard that always says you are fine is worse than no dashboard.
They come from the startup checklist instead. Certifying a pump is a statement
that it is running this shift, and it happens before a drop is poured, so a
pump that gets certified and then goes quiet stays counted against you. Which
is the case worth catching.

Logged downtime comes off. A pump down for a changeover or a fault is not held
against pace, and that is the first reason operators have ever had to log
downtime, which until now cost them time and bought them nothing.

Nothing certified means nothing to work from, so it falls back to the plant
figure and behaves exactly as it did before. Every day before this shipped
reads the way it always did.
"""
from datetime import datetime, timedelta, timezone
from statistics import median

from db_core import ScopedSession
from models import DailyChecklist, DowntimeLog, ProductionLog, PumpStation
from shift_clock import PLANT_TZ, _shift_window

DEFAULT_LPH = 400.0
POUR_LOG = "Hourly Bottle Count"


def _as_utc(value):
    """The same rule record_health uses. Rows are written with utcnow and
    carry no zone; the shift clock works in plant time and does carry one.
    Comparing the two raw is a four hour error that looks like arithmetic."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _shift_hours(settings, shift_name):
    """(gross, net) for a shift, breaks handled the way the shift clock does."""
    n = "2" if str(shift_name).strip() == "Shift 2" else "1"
    gross = float(settings.get(f"shift_{n}_hours", 8.5) or 8.5)
    brk = float(settings.get(f"shift_{n}_break_mins", 60.0) or 0.0) / 60.0
    return gross, max(0.1, gross - brk)


def pump_rates(default_lph=None):
    """station name -> expected litres an hour.

    A pump with nothing set falls back to the plant figure rather than to a
    constant in here, so a floor running at 340 is not quietly moved to 400 by
    a pump nobody has got round to yet.
    """
    fallback = float(default_lph if default_lph else DEFAULT_LPH)
    session = ScopedSession()
    try:
        out = {}
        for p in session.query(PumpStation).all():
            rate = getattr(p, "target_lph", None)
            out[str(p.station_name)] = (float(rate) if rate and float(rate) > 0
                                        else fallback)
        return out
    except Exception:
        return {}
    finally:
        session.close()


def set_pump_rate(pump_id, target_lph):
    """Clearing it (0 or None) puts that pump back on the plant figure."""
    session = ScopedSession()
    try:
        p = session.query(PumpStation).filter(PumpStation.id == int(pump_id)).first()
        if p is None:
            return False
        try:
            v = float(target_lph)
        except (TypeError, ValueError):
            v = 0.0
        p.target_lph = v if v > 0 else None
        session.commit()
        return True
    except Exception:
        session.rollback()
        return False
    finally:
        session.close()


def _certified(on_date, shift_name):
    """station -> when it was certified, as UTC. Earliest wins: a second
    operator arriving at a pump already running does not restart its clock."""
    session = ScopedSession()
    try:
        out = {}
        rows = session.query(DailyChecklist).filter(
            DailyChecklist.date == on_date,
            DailyChecklist.shift == shift_name).all()
        for r in rows:
            st = str(r.pump_station or "").strip()
            if not st:
                continue
            ts = _as_utc(r.timestamp)
            if ts is None:
                continue
            if st not in out or ts < out[st]:
                out[st] = ts
        return out
    except Exception:
        return {}
    finally:
        session.close()


def _downtime_hours(on_date, shift_name):
    """station -> hours logged as down on this shift."""
    session = ScopedSession()
    try:
        out = {}
        rows = session.query(DowntimeLog).filter(
            DowntimeLog.date == on_date,
            DowntimeLog.shift == shift_name).all()
        for r in rows:
            st = str(r.pump_station or "").strip()
            if not st:
                continue
            out[st] = out.get(st, 0.0) + (float(r.duration_min or 0) / 60.0)
        return out
    except Exception:
        return {}
    finally:
        session.close()


def expected_for_shift(settings, shift_name, shift_start, now=None, on_date=None):
    """What the pumps certified for this shift should have poured by now.

    Returns expected_l (by now), rate_lph (the combined rate of what is on),
    shift_target_l (the whole shift), the per station breakdown, and derived,
    which is False when nothing was certified and it fell back to the plant
    figure. Every caller shows a different one of those, so they all come back
    from one query rather than three readings that can disagree.
    """
    fallback = float(settings.get("target_lph", DEFAULT_LPH) or DEFAULT_LPH)
    gross, net = _shift_hours(settings, shift_name)
    now = now or datetime.now(PLANT_TZ)
    start = _as_utc(shift_start)
    if start is None or gross <= 0:
        return {"expected_l": 0.0, "rate_lph": fallback, "shift_target_l": 0.0,
                "stations": [], "derived": False}
    end = start + timedelta(hours=gross)
    now_utc = _as_utc(now)
    on_date = on_date or start.astimezone(PLANT_TZ).date()

    certified = _certified(on_date, shift_name)
    if not certified:
        # Nothing to work from, so behave exactly as the plant did before.
        elapsed_net = max(0.0, min(net, (min(now_utc, end) - start).total_seconds()
                                   / 3600.0 * (net / gross)))
        return {"expected_l": fallback * elapsed_net, "rate_lph": fallback,
                "shift_target_l": fallback * net, "stations": [], "derived": False}

    rates = pump_rates(fallback)
    down = _downtime_hours(on_date, shift_name)

    stations, expected_l, shift_target_l, rate_now = [], 0.0, 0.0, 0.0
    for st, cert_at in sorted(certified.items()):
        rate = float(rates.get(st, fallback))
        # Clamped to the shift: certifying early does not buy hours, and a
        # late start is not charged for the time nobody was standing there.
        opened = max(start, min(cert_at, end))
        # Wall clock scaled into net hours the same way the shift clock does,
        # so breaks are taken out once and in one place.
        scale = (net / gross) if gross > 0 else 0.0
        so_far = max(0.0, (min(now_utc, end) - opened).total_seconds() / 3600.0) * scale
        rest = max(0.0, (end - opened).total_seconds() / 3600.0) * scale
        dt = float(down.get(st, 0.0))
        # Downtime comes off what has happened, not off what is still to come:
        # an hour lost this morning is gone, and pretending the shift can make
        # it up later is how a target stops being one.
        hours_now = max(0.0, so_far - dt)
        hours_all = max(0.0, rest - dt)
        exp = rate * hours_now
        stations.append({"station": st, "rate_lph": rate,
                         "certified_at": opened.astimezone(PLANT_TZ),
                         "hours": hours_now, "downtime_h": dt,
                         "expected_l": exp})
        expected_l += exp
        shift_target_l += rate * hours_all
        if now_utc < end:
            rate_now += rate

    return {"expected_l": expected_l, "rate_lph": rate_now or fallback,
            "shift_target_l": shift_target_l, "stations": stations,
            "derived": True}


def expected_for_day(settings, on_date=None, now=None):
    """Both shifts of one day added up, for the whole-plant daily view."""
    now = now or datetime.now(PLANT_TZ)
    on_date = on_date or now.astimezone(PLANT_TZ).date()
    total = {"expected_l": 0.0, "rate_lph": 0.0, "shift_target_l": 0.0,
             "stations": [], "derived": False}
    for n, name in (("1", "Shift 1"), ("2", "Shift 2")):
        try:
            h, m = map(int, str(settings[f"shift_{n}_start"]).split(":"))
        except Exception:
            continue
        gross, _net = _shift_hours(settings, name)
        start, _end = _shift_window(on_date, h, m, gross)
        if _as_utc(start) > _as_utc(now):
            continue                      # a shift that has not begun expects nothing
        part = expected_for_shift(settings, name, start, now=now, on_date=on_date)
        total["expected_l"] += part["expected_l"]
        total["shift_target_l"] += part["shift_target_l"]
        total["stations"].extend(part["stations"])
        total["derived"] = total["derived"] or part["derived"]
        if part["derived"]:
            total["rate_lph"] += part["rate_lph"]
    if not total["rate_lph"]:
        total["rate_lph"] = float(settings.get("target_lph", DEFAULT_LPH) or DEFAULT_LPH)
    return total


def measured_rates(shifts_back=20, min_samples=3):
    """What each pump has actually run at, so a target is reviewed not invented.

    One sample is one station on one shift: the litres logged, over the hours
    between its first and last log of that shift plus one, which is the same
    arithmetic the wall display uses for an operator. The median rather than
    the mean, because one short shift or one enormous drum pour would drag an
    average somewhere no pump has ever been.

    Returns station -> {"median_lph", "samples"}. A pump with fewer than
    min_samples is left out entirely rather than reported thinly: a suggestion
    from two shifts is a guess wearing a number.
    """
    from crud import log_litres
    session = ScopedSession()
    try:
        rows = session.query(ProductionLog).filter(
            ProductionLog.log_type == POUR_LOG).all()
    except Exception:
        return {}
    finally:
        session.close()

    buckets = {}
    for r in rows:
        st = str(r.pump_station or "").strip()
        if not st or r.date is None:
            continue
        key = (st, r.date, str(r.shift or ""))
        b = buckets.setdefault(key, {"l": 0.0, "first": None, "last": None})
        b["l"] += log_litres(r.bottles_filled, r.cartridge_type,
                             getattr(r, "litres_poured", None))
        ts = _as_utc(r.timestamp)
        if ts is not None:
            if b["first"] is None or ts < b["first"]:
                b["first"] = ts
            if b["last"] is None or ts > b["last"]:
                b["last"] = ts

    recent = sorted({d for (_s, d, _sh) in buckets}, reverse=True)[:max(1, shifts_back)]
    keep = set(recent)

    per = {}
    for (st, d, _sh), b in buckets.items():
        if d not in keep or b["first"] is None or b["l"] <= 0:
            continue
        span = (b["last"] - b["first"]).total_seconds() / 3600.0
        hours = max(1.0, span + 1.0)
        per.setdefault(st, []).append(b["l"] / hours)

    return {st: {"median_lph": float(median(v)), "samples": len(v)}
            for st, v in per.items() if len(v) >= min_samples}
