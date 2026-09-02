"""The pump form link: what an administrator can type, and what it becomes.

The value here is that this is the one field in the application whose contents
become a destination a browser is sent to. Everything else typed into settings
ends up as a number in a report; this ends up as a tap target on an operator's
phone. So the interesting cases are not "does a good URL work" but the four
ways a real paste goes wrong - no scheme, a trailing full stop off the end of a
sentence, a whole line with a space in it, and a scheme that is not the web -
plus the round trip through the settings row, because a setting that saves and
does not read back is a setting that does nothing (which is exactly what
shift_count was doing until this test's sibling caught it).
"""
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import _boot  # noqa: E402  (sets up a throwaway database, refuses production)

import external_links  # noqa: E402

FAILURES = []
COUNT = 0


def check(cond, what):
    global COUNT
    COUNT += 1
    if not cond:
        FAILURES.append(what)
        print(f"  FAIL  {what}")


# ----------------------------------------------------------- what goes in --
print("\nAddresses an administrator might paste")

url, problem = external_links.normalise("https://forms.office.com/r/abc123")
check(url == "https://forms.office.com/r/abc123", "a plain https address survives untouched")
check(problem == "", "and reports no problem")

# The single most likely paste: copied off a screen, not out of a browser bar.
url, problem = external_links.normalise("forms.office.com/r/abc123")
check(url == "https://forms.office.com/r/abc123",
      "a bare host gains https rather than being rejected")
check(problem == "", "and is not reported as a problem")

# Without this it resolves relative to the MES and lands on a 404 *inside* the
# app, which looks like the MES is broken rather than like the setting is wrong.
check(not external_links.normalise("forms.office.com/r/abc")[0].startswith("forms"),
      "a bare host never stays scheme-relative")

url, _ = external_links.normalise("  https://forms.office.com/r/abc  ")
check(url == "https://forms.office.com/r/abc", "surrounding whitespace is trimmed")

url, _ = external_links.normalise("https://forms.office.com/r/abc.")
check(url == "https://forms.office.com/r/abc",
      "a full stop pasted off the end of a sentence is dropped")

url, _ = external_links.normalise("<https://forms.office.com/r/abc>")
check(url == "https://forms.office.com/r/abc", "angle brackets from an email client are dropped")

url, problem = external_links.normalise("https://forms.office.com/r/a bc")
check(url == "" and problem, "an address with a space in it is refused, not silently broken")

url, problem = external_links.normalise("")
check(url == "" and problem == "",
      "empty is not an error - it is how a plant with no such form is configured")
url, problem = external_links.normalise(None)
check(url == "" and problem == "", "and neither is None, which is what the column holds by default")

url, problem = external_links.normalise("just some words")
check(url == "" and problem, "prose is refused rather than turned into a link")


# --------------------------------------------------------- what stays out --
print("\nSchemes that must not become a link")

for hostile in ("javascript:alert(1)",
                "JavaScript:alert(1)",
                "data:text/html,<script>alert(1)</script>",
                "vbscript:msgbox(1)",
                "file:///C:/Windows/System32"):
    url, problem = external_links.normalise(hostile)
    check(url == "", f"refused: {hostile.split(':')[0]}")
    check(problem != "", f"and says why: {hostile.split(':')[0]}")

# The one that would slip past a naive "does it contain ://" check, because
# it does not contain one - so the bare-host branch is where it would land.
url, _ = external_links.normalise("javascript:alert(1)")
check(url == "", "javascript: is not rescued by the bare-host branch")


# ------------------------------------------------------------- the label --
print("\nButton wording")

check(external_links.label_or_default("") == "Open the pump form",
      "an empty label falls back rather than rendering a blank button")
check(external_links.label_or_default("   ") == "Open the pump form",
      "and so does a label of only spaces")
check(external_links.label_or_default("Pump check") == "Pump check", "a real label is used as given")
check(len(external_links.label_or_default("x" * 200)) <= 40,
      "a pasted paragraph is capped, because on a phone it would wrap the control")


# ------------------------------------------------- the round trip through DB --
print("\nSaving it and reading it back")

_boot.boot(fresh=True, db_name="formlabs_test_links")
import crud  # noqa: E402

crud.update_plant_settings({
    "pump_form_url": "https://forms.office.com/r/pump",
    "pump_form_label": "Pump form",
})
settings = crud.get_plant_settings()
check(settings.get("pump_form_url") == "https://forms.office.com/r/pump",
      "the address written to settings reads back out of settings")
check(settings.get("pump_form_label") == "Pump form", "and so does the label")

# The bug this test exists because of. shift_count had a column, a migration,
# an admin field and a save path - and get_plant_settings never returned it, so
# every caller silently fell through to the default. It happened to be the
# right answer for this plant, which is why nobody noticed.
crud.update_plant_settings({"shift_count": 3})
check(crud.get_plant_settings().get("shift_count") == 3,
      "shift_count reads back the value that was saved, not the default")
crud.update_plant_settings({"shift_count": 2})
check(crud.get_plant_settings().get("shift_count") == 2, "and back again")

# An install that has never been told about a form must produce no button.
crud.update_plant_settings({"pump_form_url": "", "pump_form_label": ""})
settings = crud.get_plant_settings()
check(external_links.normalise(settings.get("pump_form_url", ""))[0] == "",
      "cleared settings mean no button, not a button to nowhere")


print(f"\n{COUNT - len(FAILURES)}/{COUNT} passed")
if FAILURES:
    print(f"\n{len(FAILURES)} FAILED:")
    for f in FAILURES:
        print(f"  - {f}")
sys.exit(1 if FAILURES else 0)
