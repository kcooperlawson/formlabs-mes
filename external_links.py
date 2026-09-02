"""Checking an address somebody typed into a settings box before it becomes a link.

Two separate reasons this is not just `st.link_button(label, url)`.

**A link that goes nowhere is worse than no link.** The address is typed by an
administrator into a text field, and the two things people actually paste are
`forms.example.com/pump` with no scheme - which a browser resolves relative to
the current page and lands on a 404 inside the MES - and a whole line copied
out of an email with a trailing full stop or a stray space. Both look right in
the settings screen. Neither works from the floor, and the person who finds out
is an operator standing at a pump.

**A settings field that becomes an anchor is a place to put `javascript:`.**
Only http and https are allowed through. That closes it whether the value
arrived from the admin screen or straight from the database, and it costs one
comparison.

Deliberately not a network check. Whether the form is reachable is a question
about someone else's server at some other moment; asking it here would put a
timeout in the middle of rendering the operator terminal.
"""
from __future__ import annotations

from urllib.parse import urlparse

ALLOWED_SCHEMES = ("http", "https")


def normalise(raw: str) -> tuple[str, str]:
    """Return (url, problem). A usable address gives ("https://...", "");
    anything else gives ("", <what is wrong with it, in plain words>).

    An address with no scheme is assumed to be https rather than rejected,
    because "forms.office.com/r/abc" is what people copy off a screen and
    guessing https for it is both what they meant and the safe direction to
    guess.
    """
    text = (raw or "").strip().strip("<>").rstrip(".,;")
    if not text:
        return "", ""

    if "://" not in text:
        # No scheme at all. Only treat it as a bare host if it looks like one -
        # otherwise "javascript:alert(1)" has no "://" either and would sail
        # through as "https://javascript:alert(1)".
        if ":" in text.split("/", 1)[0]:
            return "", "That does not look like a web address."
        text = "https://" + text

    parsed = urlparse(text)
    if parsed.scheme.lower() not in ALLOWED_SCHEMES:
        return "", "Only http and https addresses can be linked."
    if not parsed.netloc or "." not in parsed.netloc.split(":")[0]:
        return "", "That address is missing a domain name."
    if " " in text:
        return "", "That address has a space in it - check it was copied whole."
    return text, ""


def label_or_default(raw: str, default: str = "Open the pump form") -> str:
    """The button's wording. Falls back rather than rendering a blank button,
    and is length-capped because this sits on a phone screen where a long
    label wraps the control instead of fitting inside it."""
    text = (raw or "").strip()
    if not text:
        return default
    return text[:40]
