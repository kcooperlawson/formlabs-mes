"""Where an export goes, and the two ways that used to go wrong silently.

Both of the faults this file guards against were live on the page until now,
and neither looked like a fault.

The destination was one environment variable set at install time. On this copy
it was not set at all, so the export could only ever say "webhook missing" -
and there was nothing anybody standing in front of the page could do about it,
because the fix was in a file on the server. A destination is a row now, which
makes who can see whose sheet a real question with a real answer, so it is
asserted here.

The time horizon did nothing. The page offered four scopes, read the answer
into a variable and exported every log ever recorded regardless. "Live Today"
on a plant with two years of history sent two years of history, and the only
visible sign was a row count nobody was checking. A control that appears to
configure something and does not is worse than no control, and it is not the
first time this page has had one.

And the part everybody gets wrong the first time: a Google Sheet link cannot
receive rows. Telling the difference between a spreadsheet URL, a script
editor URL and a deployed web app URL - and saying which one you have pasted -
is most of what makes this usable rather than a validation error.
"""
import pathlib
import sys
from datetime import date, datetime, timedelta

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import sheet_sync as ss  # noqa: E402

FAILS, CHECKS = [], 0


def check(label, got, exp):
    global CHECKS
    CHECKS += 1
    if got != exp:
        FAILS.append(f"  x {label}\n      got:      {got!r}\n      expected: {exp!r}")


print("=" * 66)
print("WHERE AN EXPORT GOES")
print("=" * 66)

# --- what somebody pasted ----------------------------------------------------
GOOD = "https://script.google.com/macros/s/AKfycbxAbc123/exec"
check("a deployed web app address is the one that works",
      ss.classify_url(GOOD)["kind"], "webhook")
check("and is accepted", ss.classify_url(GOOD)["ok"], True)
check("with nothing to say about it", ss.classify_url(GOOD)["message"], "")
check("a trailing slash does not disqualify it",
      ss.classify_url(GOOD + "/")["kind"], "webhook")

# The one everybody pastes first, because it is the link they have.
SHEET = "https://docs.google.com/spreadsheets/d/1AbCdEf/edit#gid=0"
check("a spreadsheet link is recognised for what it is",
      ss.classify_url(SHEET)["kind"], "sheet")
check("and refused, because a document has no inbox",
      ss.classify_url(SHEET)["ok"], False)
check("with the reason said plainly rather than as a validation code",
      "cannot receive rows" in ss.classify_url(SHEET)["message"], True)
check("and pointed at the steps that fix it",
      "steps" in ss.classify_url(SHEET)["message"], True)

# The second thing people paste: the editor, not the deployment.
EDITOR = "https://script.google.com/u/0/home/projects/abc123/edit"
check("a script editor link is not an address", ss.classify_url(EDITOR)["ok"], False)
check("and it names the menu that produces the real one",
      "New deployment" in ss.classify_url(EDITOR)["message"], True)

# A /dev URL works while the editor is open and stops the moment it is not,
# which is the worst possible failure: it tests clean and dies later.
DEV = "https://script.google.com/macros/s/AKfycbxAbc123/dev"
check("a /dev address is refused", ss.classify_url(DEV)["ok"], False)
check("because it only works while the editor is open",
      "editor open" in ss.classify_url(DEV)["message"], True)

check("nothing typed is not an error, just nothing yet",
      ss.classify_url("")["kind"], "empty")
check("and neither is a missing value", ss.classify_url(None)["kind"], "empty")

# Not everything has to be Google. An export tool that only permits one
# vendor's addresses is a smaller thing than it needs to be.
OTHER = "https://reports.example.com/mes-hook"
check("a non-Google address is allowed", ss.classify_url(OTHER)["ok"], True)
check("but the plant is told it is on its own", ss.classify_url(OTHER)["kind"], "unknown")
check("a bare host gets a scheme rather than a rejection",
      ss.classify_url("script.google.com/macros/s/x/exec")["url"].startswith("https://"), True)
print("  addresses OK")

# --- the horizon that used to do nothing -------------------------------------
TODAY = date(2026, 9, 7)
check("today means today", ss.horizon_start("⚡ Live Today (Active Shift)", TODAY), TODAY)
check("a week means a week back",
      ss.horizon_start("📆 Past 7 Days", TODAY), date(2026, 8, 31))
check("a month means thirty days back",
      ss.horizon_start("📊 Past 30 Days", TODAY), date(2026, 8, 8))
check("all time has no floor", ss.horizon_start("🌐 All Time History", TODAY), None)
check("and a label nobody recognises does not silently become today",
      ss.horizon_start("whatever", TODAY), None)

import pandas as pd  # noqa: E402

frame = pd.DataFrame({
    "date": [TODAY, TODAY - timedelta(days=3), TODAY - timedelta(days=20),
             TODAY - timedelta(days=400)],
    "bottles_filled": [10, 20, 30, 40],
})
check("today keeps only today's rows",
      len(ss.filter_by_horizon(frame, "⚡ Live Today (Active Shift)", TODAY)), 1)
check("a week keeps the week", len(ss.filter_by_horizon(frame, "📆 Past 7 Days", TODAY)), 2)
check("a month keeps the month", len(ss.filter_by_horizon(frame, "📊 Past 30 Days", TODAY)), 3)
# The assertion that would have caught the original bug: all four rows, and
# only for All Time. Before this, every scope returned all four.
check("and only all-time keeps the lot",
      len(ss.filter_by_horizon(frame, "🌐 All Time History", TODAY)), 4)

check("an empty record does not raise",
      ss.filter_by_horizon(pd.DataFrame(), "📆 Past 7 Days", TODAY).empty, True)
check("nor does a frame with no date column",
      len(ss.filter_by_horizon(pd.DataFrame({"x": [1, 2]}), "📆 Past 7 Days", TODAY)), 2)
check("an unparseable date is dropped rather than crashing the export",
      len(ss.filter_by_horizon(pd.DataFrame({"date": ["not a date", TODAY]}),
                               "⚡ Live Today (Active Shift)", TODAY)), 1)
print("  time horizon OK")

# --- who can see whose sheet -------------------------------------------------
rows = [
    {"id": 1, "name": "Plant sheet", "owner_user_id": None, "owner_name": "setup", "is_shared": True},
    {"id": 2, "name": "My weekly", "owner_user_id": 7, "owner_name": "Keagan", "is_shared": False},
    {"id": 3, "name": "Her report", "owner_user_id": 9, "owner_name": "Ana", "is_shared": False},
    {"id": 4, "name": "Ops board", "owner_user_id": 9, "owner_name": "Ana", "is_shared": True},
]
mine = ss.visible_targets(rows, user_id=7)
check("I see my own sheet", any(r["id"] == 2 for r in mine), True)
check("and the shared ones", {r["id"] for r in mine}, {1, 2, 4})
# The one that matters: a private sheet is private. The whole point of letting
# managers add their own is that they do not have to negotiate for one.
check("but never a colleague's private sheet", any(r["id"] == 3 for r in mine), False)
check("an administrator sees everything", len(ss.visible_targets(rows, 1, is_admin=True)), 4)
check("somebody with no account yet sees only shared ones",
      {r["id"] for r in ss.visible_targets(rows, None)}, {1, 4})
check("and an empty list is an empty list, not an error",
      ss.visible_targets([], 7), [])

check("a shared sheet says who shared it",
      "shared by Ana" in ss.target_label(rows[3]), True)
check("your own is just its name and yours", ss.target_label(rows[1]), "My weekly — Keagan")
check("and one with no name still reads",
      "Unnamed sheet" in ss.target_label({"owner_name": ""}), True)
print("  visibility OK")

# --- has this destination actually been working ------------------------------
NOW = datetime(2026, 9, 7, 12, 0, 0)
check("a sheet nobody has used says so", ss.last_sync_text(None, None, NOW), "Never used.")
check("a recent success is reported in minutes",
      "20 min ago" in ss.last_sync_text(NOW - timedelta(minutes=20), "ok", NOW), True)
check("an older one in hours",
      "5 h ago" in ss.last_sync_text(NOW - timedelta(hours=5), "ok", NOW), True)
check("an old one in days",
      "3 days ago" in ss.last_sync_text(NOW - timedelta(days=3), "ok", NOW), True)

# A destination that has stopped working looks exactly like a healthy one
# until somebody needs the numbers, so the failure has to be on the page.
fail = ss.last_sync_text(NOW - timedelta(hours=2), "HTTP 401", NOW)
check("a failure is not reported as a send", "Last sent" in fail, False)
check("it says it failed", "failed" in fail, True)
check("and carries what went wrong", "HTTP 401" in fail, True)
print("  destination health OK")

# --- the script handed to the user -------------------------------------------
# It is quoted in the interface as the thing to paste, so it has to be the
# thing that works with what the page actually sends.
check("the script reads the payload the page sends", "sheet_name" in ss.APPS_SCRIPT, True)
check("and the rows with it", "body.data" in ss.APPS_SCRIPT, True)
check("it creates the tab if the sheet has not got one",
      "insertSheet" in ss.APPS_SCRIPT, True)
# doGet is what lets the Test button check an address without writing to the
# sheet. A test that changes the thing it is testing is not a test.
check("and it answers a plain request, so testing writes nothing",
      "function doGet" in ss.APPS_SCRIPT, True)
check("with the token the Test button looks for",
      "formlabs-mes-ok" in ss.APPS_SCRIPT, True)
check("the setup steps end on the address to paste",
      "/exec" in ss.SETUP_STEPS[-1], True)
check("and there are four of them", len(ss.SETUP_STEPS), 4)
print("  the script OK")

print("\n" + "=" * 66)
if FAILS:
    print(f"{len(FAILS)} of {CHECKS} SHEET SYNC CHECKS FAILED:\n" + "\n".join(FAILS))
else:
    print(f"ALL {CHECKS} SHEET SYNC ASSERTIONS PASSED")
raise SystemExit(1 if FAILS else 0)
