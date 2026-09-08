"""The crash reporter, checked without a browser and without a crash.

This is the code that runs when everything else has already gone wrong, which
makes it the worst possible place for a bug. Two properties matter more than
the rest and neither is visible by looking at a working app:

  **It must never make things worse.** Every path here runs inside an
  exception handler. A reporter that raises replaces a real bug with its own,
  and what the person in front of the screen then sees is a crash in the crash
  handler - which is both useless and alarming.

  **It must not print the database password on a manager's screen.** A
  SQLAlchemy connection failure puts the whole connection URL in its message,
  and that URL carries the password. This writes to a table IT Admin renders,
  so redaction has to happen on the way IN. That is checked here against the
  exact shapes those errors actually take, not a made-up one.

No database, no Streamlit, no browser: the parts that carry the risk were
written as plain functions from a value to a value precisely so they could be
checked like this.
"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import error_report as er  # noqa: E402

FAILS, CHECKS = [], 0


def check(label, got, exp):
    global CHECKS
    CHECKS += 1
    if got != exp:
        FAILS.append(f"  x {label}\n      got:      {got!r}\n      expected: {exp!r}")


print("=" * 66)
print("CRASH REPORTING")
print("=" * 66)

# --- redaction ---------------------------------------------------------------
# The real one. This is what SQLAlchemy says when the database is unreachable,
# and it is by far the most likely thing to end up in this table.
url_err = ('(psycopg2.OperationalError) connection to server failed\n'
           'postgresql+psycopg2://mes_user:Sup3rS3cret!@10.0.4.12:5432/formlabs')
red = er.redact(url_err)
check("the password is gone from a connection URL", "Sup3rS3cret" in red, False)
check("but the host is kept, because that is the diagnostic", "10.0.4.12" in red, True)
check("and so is the user", "mes_user" in red, True)

for line in ('DB_URL=postgresql://a:b@h/db',
             'password = "hunter2"',
             "api_key: sk-live-9932",
             "GOOGLE_SHEETS_WEBHOOK=https://script.google.com/x/exec?k=abc"):
    out = er.redact(line)
    check(f"a labelled secret is masked: {line[:22]}",
          any(bad in out for bad in ("hunter2", "sk-live-9932", "k=abc", ":b@")), False)

check("ordinary text is left alone",
      er.redact("KeyError: 'bottles_filled'"), "KeyError: 'bottles_filled'")
check("nothing at all does not raise", er.redact(None), "")
print("  redaction OK")

# --- reference codes ---------------------------------------------------------
# Derived from the fault, not random, so three managers reporting the same
# code are visibly reporting one bug instead of three.
a = er.reference_code("Analytics_Hub", "KeyError", "'shift_count'")
b = er.reference_code("Analytics_Hub", "KeyError", "'shift_count'")
check("the same fault gives the same code every time", a, b)
check("a different page gives a different code",
      a == er.reference_code("Manager_Cockpit", "KeyError", "'shift_count'"), False)
check("a different error type does too",
      a == er.reference_code("Analytics_Hub", "TypeError", "'shift_count'"), False)
check("the code is short enough to read down a phone", len(a), er.REF_LENGTH)
check("and has no characters that get misheard",
      set(a) & set("OIL01"), set())

# Numbers and quoted values are stripped before grouping, so one bug that
# reports a different row number each time is still one bug.
check("row numbers do not split one fault into many",
      er.reference_code("P", "ValueError", "column 47 missing"),
      er.reference_code("P", "ValueError", "column 48 missing"))
check("nor does a memory address in an object repr",
      er.reference_code("P", "TypeError", "<Run object at 0x7f1a2b>"),
      er.reference_code("P", "TypeError", "<Run object at 0x9c4d1e>"))
check("but two genuinely different messages still separate",
      er.reference_code("P", "ValueError", "column missing")
      == er.reference_code("P", "ValueError", "connection lost"), False)
print("  reference codes OK")

# --- trimming ----------------------------------------------------------------
# A traceback is cut from the FRONT. The last frames say what actually broke;
# cutting from the end keeps the framework's entry points and throws away the
# line of ours that raised, which is the only part anybody reads.
long_trace = "\n".join(f"frame {i}" for i in range(4000))
cut = er.trim(long_trace, 500)
check("an enormous traceback is cut down", len(cut) <= 560, True)
check("and it is the END that survives", cut.endswith("frame 3999"), True)
check("with the cut said out loud rather than hidden", "trimmed" in cut, True)
check("something already short is untouched", er.trim("boom", 500), "boom")
print("  trimming OK")

# --- describing an exception -------------------------------------------------
try:
    raise ValueError("connect to postgresql://u:letmein@h/db failed")
except ValueError as exc:
    d = er.describe(exc)
check("the type is recorded", d["error_type"], "ValueError")
check("the traceback names the line that raised", "raise ValueError" in d["traceback"], True)
check("the password is not in the message", "letmein" in d["message"], False)
check("and not in the traceback either", "letmein" in d["traceback"], False)

d2 = er.describe(None)
check("being handed nothing does not raise", d2["error_type"], "Unknown")
print("  describing OK")

# --- what the person sees ----------------------------------------------------
msg = er.user_message("K7F2")
check("they are told the code", "K7F2" in msg, True)
check("and told it is already recorded", "logged" in msg.lower(), True)
check("they are not shown a traceback", "Traceback" in msg, False)
print("  the message OK")

# --- installing --------------------------------------------------------------
# The one that matters: if Streamlit's internals have moved, this returns
# False. It must not raise, because taking the whole app down over a crash
# reporter that could not attach is worse than having no crash reporter.
er._INSTALLED = False
seen = []
ok = er.install(recorder=lambda payload: seen.append(payload) or "AAAA",
                page_name="Analytics_Hub")
check("it attaches to this Streamlit", ok, True)
check("attaching twice is a no-op rather than a second patch",
      er.install(recorder=lambda p: "BBBB"), True)

from streamlit import error_util  # noqa: E402
try:
    raise KeyError("shift_count")
except KeyError as exc:
    try:
        error_util.handle_uncaught_app_exception(exc)
    except Exception:
        pass
check("a real exception reaches the recorder", len(seen), 1)
check("carrying the page it happened on", seen[0]["page"], "Analytics_Hub")
check("and the type", seen[0]["error_type"], "KeyError")

# A recorder that itself fails must not turn one broken screen into two.
er._INSTALLED = False


def exploding_recorder(payload):
    raise RuntimeError("the database is the thing that is down")


er.install(recorder=exploding_recorder, page_name="X")
try:
    raise ValueError("original fault")
except ValueError as exc:
    try:
        error_util.handle_uncaught_app_exception(exc)
        survived = True
    except RuntimeError:
        survived = False
check("a reporter that fails does not replace the real error with its own",
      survived, True)
print("  installing OK")

print("\n" + "=" * 66)
if FAILS:
    print(f"{len(FAILS)} of {CHECKS} CRASH REPORT CHECKS FAILED:\n" + "\n".join(FAILS))
else:
    print(f"ALL {CHECKS} CRASH REPORT ASSERTIONS PASSED")
raise SystemExit(1 if FAILS else 0)
