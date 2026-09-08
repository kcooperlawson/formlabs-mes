"""Catching a crash where it happens, so somebody hears about it.

The gap this closes. Floor terminals are configured not to show Python
tracebacks, which is right - an operator seeing a stack trace learns nothing
and stops trusting the screen. But the consequence was that when a page broke,
the person in front of it got a generic red box, the detail went into a log
file on the plant PC, and the only way anybody found out was if that person
remembered to mention it. Three days later, in their own words, about a screen
they could not name. That is not a bug report, and there is nothing to act on
in it.

So this catches the exception, writes it down with everything needed to find
it again - the page, who was on it, their role, the app version, the real
traceback - and hands the person a short reference code. They say "reference
K7F2" and the whole thing is already in IT Admin waiting.

**This is not an auto-fix and there is no such thing.** A logic bug cannot be
detected from inside the program that has it: a total adding up wrong looks
exactly like a total adding up right. What the app CAN repair by itself is the
small set of faults with one deterministic cause and one deterministic fix,
and those are already handled elsewhere - the schema migrates itself on
startup, a stale backup takes a new one, a dead database connection is
reopened rather than handed out. Everything else needs a person, and the
useful thing to automate is telling that person.

Hooked in once rather than page by page. Streamlit routes every uncaught
exception in a page script through one function, so patching that catches all
eighteen pages including the seven that predate the shared shell, and no page
has to remember to wrap itself in anything. If a future Streamlit moves that
function, `install` says so and returns False rather than raising: an error
reporter that takes the app down when it cannot attach is worse than no error
reporter.

Redaction is not optional here. A SQLAlchemy connection failure puts the
whole database URL in its message, and that URL carries the password. This
writes to a table that IT Admin renders on screen, so the traceback goes
through `redact` on the way in, every time.

The pure parts - reference codes, redaction, trimming - take no Streamlit and
no database, because those are the parts worth checking without either.
"""
from __future__ import annotations

import hashlib
import re
import traceback as _tb

# Short enough to read down a phone line, long enough not to collide within a
# plant's lifetime. No vowels and no 0/O/1/I, so nothing spells a word by
# accident and nothing gets misheard when somebody reads it out.
_ALPHABET = "ACDEFGHJKLMNPQRTUVWXY2346789"
REF_LENGTH = 4

# How much traceback is kept. Long enough for the deepest frame that matters,
# short enough that one runaway recursion cannot fill the table.
MAX_TRACE = 12000
MAX_MESSAGE = 800

_SECRET_PATTERNS = (
    # postgresql://user:password@host - the one that actually turns up, because
    # SQLAlchemy prints the URL it failed to connect to.
    (re.compile(r"(://[^:/@\s]+:)([^@/\s]+)(@)"), r"\1***\3"),
    # Anything that names itself. Covers DB_URL=..., password=..., token: ...,
    # api_key = "...", and the same words inside a dict repr.
    #
    # The leading [A-Za-z_]* is not decoration. A word boundary will not fire
    # inside GOOGLE_SHEETS_WEBHOOK, because an underscore is a word character
    # - so the plain \bwebhook\b version sailed straight past the one setting
    # name this app actually uses. Prefixes are allowed on purpose.
    (re.compile(r"""(?i)\b[A-Za-z_]*(?:password|passwd|pwd|secret|token|
                     api[_-]?key|webhook|db_url|database_url)\b
                     (\s*[:=]\s*)(["']?)([^\s"',}\)]+)""", re.VERBOSE),
     lambda m: f"{m.group(0)[:m.start(1) - m.start(0)]}{m.group(1)}{m.group(2)}***"),
)


def redact(text) -> str:
    """Strip credentials out of anything on its way into the table.

    Called on every message and traceback without exception. A connection
    error carries the database URL, the URL carries the password, and this
    table is rendered on screen in IT Admin - so the redaction has to be on
    the write path, not on the read path where somebody could forget it.
    """
    out = str(text or "")
    for pattern, repl in _SECRET_PATTERNS:
        out = pattern.sub(repl, out)
    return out


def reference_code(page: str, error_type: str, message: str) -> str:
    """A short code for this KIND of fault, the same every time it happens.

    Deliberately derived from the fault rather than random. The same break on
    the same page gives the same code, so three managers reporting K7F2 are
    reporting one bug and it is obvious that they are - where three random
    codes look like three bugs. It also means the code can be worked out again
    later from the row itself.

    Not a security boundary and not unique: two genuinely different faults can
    collide, which is why the row carries the page, the type and the traceback
    as well. This is a thing to say out loud, not an identifier.
    """
    seed = f"{page}|{error_type}|{_signature(message)}"
    digest = hashlib.md5(seed.encode("utf-8", "replace")).digest()
    n = int.from_bytes(digest[:8], "big")
    out = []
    for _ in range(REF_LENGTH):
        n, i = divmod(n, len(_ALPHABET))
        out.append(_ALPHABET[i])
    return "".join(out)


def _signature(message) -> str:
    """The stable part of a message, for grouping.

    Numbers, quoted values and hex addresses are stripped out first. Without
    that, "column 47 does not exist" and "column 48 does not exist" are two
    bugs, and an object repr with a memory address in it is a new bug every
    single time it happens.
    """
    text = str(message or "").strip().lower()
    text = re.sub(r"0x[0-9a-f]+", "#", text)
    text = re.sub(r"\d+", "#", text)
    text = re.sub(r"'[^']*'|\"[^\"]*\"", "'@'", text)
    return re.sub(r"\s+", " ", text)[:300]


def trim(text, limit: int) -> str:
    """Cut to a length, keeping the END of a traceback rather than the start.

    The last frames are the ones that say what actually broke. A traceback cut
    from the far end keeps the framework's entry points and throws away the
    line of ours that raised, which is the only part anybody reads.
    """
    out = str(text or "")
    if len(out) <= limit:
        return out
    return "... earlier frames trimmed ...\n" + out[-limit:]


def describe(exc) -> dict:
    """An exception as the fields the table stores. No Streamlit, no database."""
    error_type = type(exc).__name__ if exc is not None else "Unknown"
    message = redact(trim(str(exc), MAX_MESSAGE))
    try:
        trace = "".join(_tb.format_exception(type(exc), exc, exc.__traceback__))
    except Exception:
        trace = ""
    return {
        "error_type": error_type[:120],
        "message": message,
        "traceback": redact(trim(trace, MAX_TRACE)),
    }


def user_message(ref: str) -> str:
    """What the person in front of the broken screen is told.

    Says three things and nothing else: something broke, it is already
    recorded, and here is what to quote. No apology paragraph, no traceback,
    and no instruction to try again - if trying again worked, they would
    already have done it.
    """
    return (f"Something on this screen failed. It has been logged as "
            f"**reference {ref}** — no need to write anything down beyond that "
            f"code. Everything else on the app still works; go back and carry "
            f"on, and give that code to whoever looks after this.")


# --------------------------------------------------------------------------
# The hook. Everything below needs Streamlit; everything above does not.
# --------------------------------------------------------------------------

_INSTALLED = False


def install(recorder=None, page_name=None) -> bool:
    """Route Streamlit's uncaught page exceptions through here as well.

    `recorder` is called with the finished dict and returns the reference code
    to show. Injected rather than imported so the pure half of this module
    stays testable, and so a database that is itself the thing that broke
    cannot turn one failure into two.

    Returns False rather than raising if Streamlit's internals have moved.
    Reporting a crash is worth a lot; taking the app down because the crash
    reporter could not attach is worth nothing.
    """
    global _INSTALLED
    if _INSTALLED:
        return True
    try:
        import streamlit as st
        from streamlit import error_util
        original = error_util.handle_uncaught_app_exception
    except Exception:
        return False

    def handler(exc, *args, **kwargs):
        ref = None
        try:
            payload = describe(exc)
            payload["page"] = str(page_name() if callable(page_name) else page_name or "")[:120]
            if recorder is not None:
                ref = recorder(payload)
        except Exception:
            # The reporter failing must never replace the real error with its
            # own. Fall through and let Streamlit show what it was going to.
            ref = None
        if ref:
            try:
                st.error(user_message(ref))
                return
            except Exception:
                pass
        return original(exc, *args, **kwargs)

    error_util.handle_uncaught_app_exception = handler
    _INSTALLED = True
    return True
