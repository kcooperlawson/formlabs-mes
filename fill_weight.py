"""Fill-weight check: judging one measured cartridge against its spec.

The resin table has always known the target fill weight and the tolerance
window - 1110 g, accept 1100 to 1115 - and nothing ever recorded what a
cartridge actually weighed. So the app could tell you how many units were
poured but not how much resin went into them. This module is the small piece
of arithmetic that closes that: given a reading and a spec, where in the
window did this one land, and by how much.

Two things worth stating, because they shape everything downstream.

**The window is lopsided.** A typical spec allows 10 g under target and only
5 g over. So a pump set to run safely clear of the low limit sits high in the
window on every single cartridge, and every gram above target is resin given
away - about 0.09% of the fill, forever, on every unit. That is the number
this exists to surface. It is invisible today.

**A reading is a measurement, not a control.** Nothing here blocks, refuses
or gates. A wrong lot is a defect and the lot check rightly stops the line;
a heavy cartridge is information. If capturing it could stop an operator
working, it would be typed rather than weighed within a week, and a column
full of `1110` is worse than an empty one - it looks like data.

Deliberately free of Streamlit and of the database, so the pouring form, the
write path, the analytics and the tests all judge a reading the same way.
"""
from __future__ import annotations

# Anything outside this is a typo or a scale reading a pallet, not a
# cartridge. Used only to reject nonsense before it reaches the database -
# not as a tolerance, which comes from the resin's own spec.
PLAUSIBLE_MIN_G = 1.0
PLAUSIBLE_MAX_G = 100_000.0

IN = "in"
UNDER = "under"
OVER = "over"


def _num(value):
    """Float or None. Tolerates the strings and NaNs a dataframe hands over."""
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return None if f != f else f  # NaN


def spec_from_row(row) -> dict | None:
    """Pull a usable weight spec out of a resin_specs row (or dict).

    Returns None when the resin has no spec on file, which is a normal state
    - a resin can be poured before anyone has entered its numbers, and the
    form has to keep working. Also returns None for a spec whose window is
    incoherent (min above max), rather than silently judging against it.
    """
    if row is None:
        return None
    try:
        get = row.get
    except AttributeError:
        return None

    target = _num(get("actual_spec_g"))
    lo = _num(get("min_weight_g"))
    hi = _num(get("max_weight_g"))
    if target is None or target <= 0:
        return None
    if lo is not None and hi is not None and lo > hi:
        return None
    return {"target": target, "lo": lo, "hi": hi}


def judge(measured, spec) -> dict | None:
    """Judge one reading. Returns None if there is nothing to judge.

    Returned keys:
      measured    the reading, as a float
      target      the spec's target
      deviation   measured - target: positive is resin given away
      status      "in" / "under" / "over", or None with no window on file
      pct_of_fill deviation as a percentage of target

    `status` is judged against the window as it stands NOW and is stored on
    the log, so a later edit to the resin's tolerances cannot silently
    re-judge a reading somebody already took.
    """
    m = _num(measured)
    if m is None or not (PLAUSIBLE_MIN_G <= m <= PLAUSIBLE_MAX_G):
        return None
    if not spec or _num(spec.get("target")) is None:
        return None

    target = float(spec["target"])
    lo, hi = _num(spec.get("lo")), _num(spec.get("hi"))
    deviation = m - target

    if lo is not None and m < lo:
        status = UNDER
    elif hi is not None and m > hi:
        status = OVER
    elif lo is None and hi is None:
        status = None            # a target but no window: record, don't judge
    else:
        status = IN

    return {
        "measured": m,
        "target": target,
        "deviation": round(deviation, 2),
        "status": status,
        "pct_of_fill": round(deviation / target * 100.0, 3) if target else 0.0,
    }


def describe(verdict) -> tuple[str, str]:
    """(icon, sentence) to show the operator the moment they type a reading.

    Feedback is the whole reason an optional field gets filled in. A box that
    swallows a number teaches people to skip it; one that answers tells them
    something they did not know about the pump they are standing at.
    """
    if not verdict:
        return "", ""
    dev, status = verdict["deviation"], verdict["status"]
    if abs(dev) < 0.05:
        off = "exactly on target"
    else:
        off = f"{abs(dev):.1f} g {'over' if dev > 0 else 'under'} target"

    if status == IN:
        return "✅", f"In band — {off}."
    if status == OVER:
        return "🔺", f"Over the high limit — {off}. Worth flagging to your lead."
    if status == UNDER:
        return "🔻", f"Under the low limit — {off}. Worth flagging to your lead."
    return "•", f"Recorded — {off}."


def giveaway(rows) -> dict:
    """Aggregate readings into the figure a plant manager cares about.

    `rows` is any iterable of (deviation_g, units_represented). Each reading
    stands for the units logged alongside it, because one weight an hour is a
    sample of that hour's output, not a single cartridge in isolation.

    Returns grams given away, the mean deviation, and the sample size. Never
    raises on empty or malformed input - an empty analytics panel is a fine
    outcome, a page that dies because nobody has weighed anything yet is not.
    """
    total_dev = 0.0
    total_units = 0
    n = 0
    for dev, units in rows or []:
        d, u = _num(dev), _num(units)
        if d is None:
            continue
        u = 0.0 if u is None or u < 0 else u
        total_dev += d * u
        total_units += u
        n += 1
    return {
        "samples": n,
        "units_represented": int(total_units),
        "grams": round(total_dev, 1),
        "kg": round(total_dev / 1000.0, 2),
        "mean_deviation": round(total_dev / total_units, 2) if total_units else 0.0,
    }


def band_percent(in_band, judged) -> str:
    """The "share of readings inside their window" figure, as it should print.

    Exists because `f"{349/350*100:.0f}%"` is "100%", displayed beside a
    scatter plot that visibly contains an out-of-band point. The one exception
    is the entire reason anyone opens this panel, and a headline that rounds it
    away is worse than no headline: the reader who spots the contradiction
    stops trusting every other number on the page.

    So a clean sweep is the only thing that reads 100%, and a single good
    reading among failures is the only thing that reads 0%. Everything between
    keeps a decimal and is clamped away from both ends.
    """
    try:
        good, total = int(in_band), int(judged)
    except (TypeError, ValueError):
        return "—"
    if total <= 0:
        return "—"
    good = max(0, min(good, total))
    if good == total:
        return "100%"
    if good == 0:
        return "0%"
    pct = good / total * 100.0
    if pct > 99.9:
        return "99.9%"
    if pct < 0.1:
        return "0.1%"
    return f"{pct:.1f}%"
