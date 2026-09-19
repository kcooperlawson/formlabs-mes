"""The 'create an admin login' prompt (setup/_admin_setup.py), shared by
api/portable_launcher.py's automatic first-run step and
setup/create_admin_login.py, the standalone "create an admin login" option
on START_HERE.bat's own menu (options 10/11) - not create_admin.py at the
project root, which is a separate, narrower, non-interactive tool the
installers call directly and this file does not touch.

Every account this app seeds on a brand-new database - including the admin
one, "manager" / PIN "admin123" - is a fixed, published password. This
checks the thing that replaces it: PIN-length and confirm-mismatch retries
don't lose the rest of the answers, a real account actually gets created
with the PIN typed (not silently something else), a taken username/email
is rejected rather than silently overwriting, and the demo admin is only
ever removed when asked - not by every caller, not automatically here.

No browser and no batch file: input()/getpass.getpass() are swapped for
canned answers, same as any other pure-Python check in this suite.
"""
import builtins
import getpass
import pathlib
import sys
import warnings

warnings.filterwarnings("ignore")
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "setup"))

import _boot  # noqa: E402  (throwaway database, refuses the .env connection)

_boot.boot(fresh=True, db_name="formlabs_admin_setup")

import crud  # noqa: E402  (seeds operator/sasha/manager on this fresh schema)
import _admin_setup  # noqa: E402
import create_admin_login  # noqa: E402
from db_core import ScopedSession  # noqa: E402
from models import User  # noqa: E402

FAILS, CHECKS = [], 0


def check(label, got, exp):
    global CHECKS
    CHECKS += 1
    if got != exp:
        FAILS.append(f"{label}: expected {exp!r}, got {got!r}")


def usernames():
    s = ScopedSession()
    try:
        return sorted(u.username for u in s.query(User).all())
    finally:
        s.close()


def run_prompt(answers, pins, isatty=True):
    """Drives _admin_setup.prompt_and_create with canned console answers,
    restoring the real input()/getpass.getpass()/isatty() no matter what -
    a failed assertion later in the file must not leave every check after
    it answering from an exhausted iterator."""
    answers_it, pins_it = iter(answers), iter(pins)
    real_input, real_getpass, real_isatty = builtins.input, getpass.getpass, sys.stdin.isatty
    builtins.input = lambda prompt="": next(answers_it)
    getpass.getpass = lambda prompt="": next(pins_it)
    sys.stdin.isatty = lambda: isatty
    try:
        return _admin_setup.prompt_and_create(crud)
    finally:
        builtins.input, getpass.getpass, sys.stdin.isatty = real_input, real_getpass, real_isatty


check("fresh database seeds the three demo accounts",
      usernames(), ["manager", "operator", "sasha"])

# --- non-interactive stdin: skipped outright, never blocks on input() -----
check("a non-interactive session (a service, not a person) does nothing",
      run_prompt([], [], isatty=False), None)
check("...and touches no accounts",
      usernames(), ["manager", "operator", "sasha"])

# --- blank name: an explicit skip, same as declining ------------------------
check("pressing Enter with no name skips",
      run_prompt([""], []), None)
check("...and touches no accounts",
      usernames(), ["manager", "operator", "sasha"])

# --- too-short PIN retries the PIN, not the whole form ----------------------
result = run_prompt(
    ["Keagan", "keagan", ""],
    ["123", "654321", "654321"],  # too short, then a valid PIN typed twice
)
check("a short PIN is rejected, then a valid one succeeds", result, "keagan")
check("the new admin can sign in with the PIN they actually typed",
      crud.authenticate_user("keagan", "654321")[0] is not None, True)
check("the new admin holds the admin role",
      crud.authenticate_user("keagan", "654321")[0]["role"], "admin")
check("demo accounts are untouched by a plain create - retiring manager is a separate, explicit step",
      usernames(), ["keagan", "manager", "operator", "sasha"])

# --- mismatched confirm retries the PIN pair, not the whole form ------------
result = run_prompt(
    ["Dana", "dana", ""],
    ["111111", "222222", "111111", "111111"],  # mismatch, then matching pair
)
check("a PIN/confirm mismatch is rejected, then a matching pair succeeds", result, "dana")
check("...and both new admins exist side by side",
      usernames(), ["dana", "keagan", "manager", "operator", "sasha"])

# --- a taken username is rejected, not silently overwritten -----------------
result = run_prompt(["Someone Else", "keagan", ""], ["333333", "333333"])
check("a taken username is refused", result, None)
check("...and the original 'keagan' account is unchanged",
      crud.authenticate_user("keagan", "654321")[0] is not None, True)

# --- create_admin_login.py's own "offer to retire the demo admin" ----------
# Answering "n" (or anything but y) leaves the demo admin alone - this can be
# run long after first install, when someone may be relying on it as a
# break-glass account.
real_input = builtins.input
builtins.input = lambda prompt="": "n"
try:
    create_admin_login._offer_retire_demo_admin(crud)
finally:
    builtins.input = real_input
check("declining leaves the demo admin in place",
      "manager" in usernames(), True)

real_input = builtins.input
builtins.input = lambda prompt="": "y"
try:
    create_admin_login._offer_retire_demo_admin(crud)
finally:
    builtins.input = real_input
check("accepting removes the demo admin",
      "manager" in usernames(), False)

# Asking again once it's already gone is a silent no-op, not a second prompt -
# get_all_users_df() simply won't have it, so input() is never even reached.
def _boom(prompt=""):
    raise AssertionError("should not have asked - 'manager' is already gone")


real_input = builtins.input
builtins.input = _boom
try:
    create_admin_login._offer_retire_demo_admin(crud)
finally:
    builtins.input = real_input
check("asking again once manager is already gone does not prompt at all",
      "manager" in usernames(), False)

print("\n" + "=" * 66)
if FAILS:
    print(f"{len(FAILS)} of {CHECKS} ADMIN SETUP CHECKS FAILED:\n" + "\n".join(FAILS))
else:
    print(f"ALL {CHECKS} ADMIN SETUP ASSERTIONS PASSED")
raise SystemExit(1 if FAILS else 0)
