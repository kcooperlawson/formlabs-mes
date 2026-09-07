"""Pours measured as an amount rather than counted as containers.

Most of what leaves a tank goes into a cartridge, and a cartridge is a known
size - so the record counts containers and multiplies. Some of it does not: a
specific amount is decanted into a drum, a tote, a pail, and the number that
matters is the amount, not how many things it went into.

Two things have to be right for that to reach the tank correctly.

The amount may arrive in kilograms. Resin is bought and reported by weight and
a tank holds litres, so one of them has to be converted, and converting needs
a density. The density is already in the spec table without being called that:
a spec of 1,110 g in a 1 L cartridge and one of 5,550 g in a 5 L jug are the
same 1.11 kg per litre, so every registered format of a resin gives the same
answer and it does not matter which one the spec happens to be written
against. That derivation used to live inline on the reactor page. It is here
now because two screens needed it and two copies of a conversion is how the
tank and the form come to disagree about the same pour.

And an amount entered by hand can be wrong in ways a count cannot. A count is
a small integer somebody can see the truth of; 1800 litres typed instead of
180 into a 5,000 L tank looks perfectly ordinary on the screen and empties the
tank on the next refresh. So a pour is checked against the vessel it came out
of before it is written, and the check is here rather than on the form,
because a manager logging the same pour from a different page must get the
same answer.

Pure functions on plain numbers. No Streamlit, no database, no rounding to a
display format - callers decide how to show what these return.
"""
from __future__ import annotations

# A litre of resin weighs about this much when nothing more specific is known.
# Same figure the reactor page has used since the tanks first reported
# kilograms; it is the middle of the range these formulations actually sit in.
DEFAULT_DENSITY_KG_L = 1.11

UNITS = ("L", "kg")

# A single pour larger than this is almost certainly a typo, whatever tank it
# is against - the biggest vessel on the floor is 5,000 L and nobody empties
# one into a drum in a single entry.
ABSURD_LITRES = 6000.0


def _num(value, fallback=0.0) -> float:
    """A float from whatever the form handed over, without raising."""
    try:
        out = float(value)
    except (TypeError, ValueError):
        return fallback
    if out != out:                       # NaN
        return fallback
    return out


def density_map(spec_rows, container_litres) -> dict:
    """Kilograms per litre for each resin, keyed by lowercased name.

    `spec_rows` is any iterable of mappings with `resin_name`,
    `cartridge_type` and `actual_spec_g`; `container_litres` is the function
    that sizes a format. Taking both as arguments rather than importing them
    keeps this module free of the database and testable on invented specs.

    The first registered format of a resin wins. They should all agree - the
    same resin does not change density because it was put in a bigger jug -
    and where a spec is mistyped, disagreeing silently would be worse than
    taking one answer and having it be visibly wrong.
    """
    out = {}
    for row in spec_rows or []:
        try:
            name = str(row["resin_name"]).strip().lower()
            grams = _num(row["actual_spec_g"])
            litres = _num(container_litres(row["cartridge_type"]))
        except (KeyError, TypeError):
            continue
        if not name or litres <= 0 or grams <= 0:
            continue
        out.setdefault(name, (grams / 1000.0) / litres)
    return out


def resin_density(resin_name, densities=None) -> float:
    """The density to use for this resin, falling back rather than failing."""
    key = str(resin_name or "").strip().lower()
    value = _num((densities or {}).get(key), 0.0)
    return value if value > 0 else DEFAULT_DENSITY_KG_L


def to_litres(amount, unit="L", density=DEFAULT_DENSITY_KG_L) -> float:
    """Litres, from an amount given in either litres or kilograms."""
    amount = _num(amount)
    if amount <= 0:
        return 0.0
    if str(unit or "L").strip().lower() in ("kg", "kgs", "kilogram", "kilograms"):
        d = _num(density, DEFAULT_DENSITY_KG_L)
        return amount / (d if d > 0 else DEFAULT_DENSITY_KG_L)
    return amount


def pour_litres(containers, amount_each, unit="L",
                density=DEFAULT_DENSITY_KG_L) -> float:
    """Total litres for `containers` vessels of `amount_each` apiece.

    The count is here rather than assumed to be one because three identical
    drums off the same tank is one thing that happened, and making an operator
    write it three times is how the third one gets forgotten.
    """
    count = int(_num(containers, 1))
    if count < 1:
        count = 1
    return count * to_litres(amount_each, unit, density)


def check_pour(litres, capacity_l=None, remaining_l=None) -> dict:
    """Whether this pour can be written, and what to say if it cannot.

    Returns {ok, blocked, level, message}. `blocked` is the one that stops a
    submit; a warning is returned for the case that is suspicious but real,
    because a tank that has been topped up without the top-up being logged
    genuinely can give out more than the record thinks is in it, and refusing
    that pour would mean the record is wrong AND the operator cannot fix it.
    """
    litres = _num(litres)
    capacity = _num(capacity_l, 0.0)
    remaining = _num(remaining_l, -1.0)

    if litres <= 0:
        return {"ok": False, "blocked": True, "level": "empty",
                "message": "Enter how much was poured."}

    if litres > ABSURD_LITRES:
        return {"ok": False, "blocked": True, "level": "absurd",
                "message": (f"{litres:,.0f} L is larger than any vessel on the floor. "
                            "Check the amount and the unit.")}

    if capacity > 0 and litres > capacity:
        return {"ok": False, "blocked": True, "level": "over-capacity",
                "message": (f"{litres:,.0f} L is more than this vessel holds "
                            f"({capacity:,.0f} L). Check the amount and the unit.")}

    if remaining >= 0 and litres > remaining:
        return {"ok": True, "blocked": False, "level": "over-level",
                "message": (f"{litres:,.0f} L is more than the record says is left "
                            f"in this vessel ({remaining:,.0f} L). Log it if that is "
                            "what happened - the tank was probably refilled without "
                            "the new lot being logged yet.")}

    return {"ok": True, "blocked": False, "level": "ok", "message": ""}


def describe_pour(containers, amount_each, unit="L",
                  density=DEFAULT_DENSITY_KG_L, note="") -> str:
    """One line saying what is about to be written, in litres.

    Shown before the submit rather than after, because the conversion is the
    part an operator cannot check in their head: they know they poured 200 kg,
    and whether that is 180 litres is the application's claim, not theirs.
    """
    count = max(1, int(_num(containers, 1)))
    each = _num(amount_each)
    total = pour_litres(count, each, unit, density)
    unit_label = "kg" if str(unit).strip().lower().startswith("kg") else "L"

    what = str(note or "").strip() or ("container" if count == 1 else "containers")
    head = (f"{each:,.10g} {unit_label} into {what}" if count == 1
            else f"{count} x {each:,.10g} {unit_label} into {what}")

    if unit_label == "kg":
        return f"{head} = {total:,.1f} L off this vessel"
    return f"{head} = {total:,.1f} L off this vessel"


def log_litres(bottles_filled, cartridge_type, litres_poured,
               container_litres) -> float:
    """The volume one log row represents.

    The single definition, used by the tank levels, the shift totals, the wall
    display and the exports. A measured amount wins outright when there is one
    - it was put there by somebody who weighed or read it, and no arithmetic
    on a container count can improve on that. Everything else is the old
    count-times-format, unchanged.
    """
    direct = _num(litres_poured, -1.0)
    if direct > 0:
        return direct
    return int(_num(bottles_filled, 0)) * _num(container_litres(cartridge_type), 0.0)
