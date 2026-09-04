"""Who reaches the administration console, in each mode.

The rule is one function - crud.can_administer - because it is applied in
eleven places across eight files, and eleven copies of a permission check is
how one of them ends up saying something different from the other ten. It
takes the mode as an argument rather than reading it, so this file can put
every combination through it without a database.

The case that matters most is the last one: a manager must NOT reach the
console in execution mode. That is the whole meaning of the separation, and
it is the half of the feature that is easy to leave untested, because nobody
notices an over-permissive check until it matters.
"""
import pathlib
import sys
import warnings

warnings.filterwarnings("ignore")
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

# The rule needs no database, but importing crud opens one - and the point of
# _boot is that a test run can never be the thing that touches production.
import _boot  # noqa: E402  (throwaway database, refuses the .env connection)

from crud import can_administer  # noqa: E402

FAILS, CHECKS = [], 0


def check(label, got, exp=True):
    global CHECKS
    CHECKS += 1
    if got != exp:
        FAILS.append(f"  x {label}\n      got:      {got!r}\n      expected: {exp!r}")


print("=" * 62)
print("WHO CAN ADMINISTER")
print("=" * 62)

LOGGING, EXECUTION = True, False

# --- an administrator is one in both modes -------------------------------
check("admin administers in logging mode", can_administer("admin", LOGGING), True)
check("admin administers in execution mode", can_administer("admin", EXECUTION), True)

# --- the manager is the whole point of the setting ------------------------
check("manager administers in logging mode", can_administer("manager", LOGGING), True)
check("manager is refused in execution mode", can_administer("manager", EXECUTION), False)

# --- nobody else, in either mode -----------------------------------------
for role in ("operator", "packer", "guest", "", None, "administrator", "mgr"):
    check(f"{role!r} refused in logging mode", can_administer(role, LOGGING), False)
    check(f"{role!r} refused in execution mode", can_administer(role, EXECUTION), False)

# --- the role as it actually arrives -------------------------------------
# It comes off session state, which took it from a database column somebody
# typed into. Case and stray whitespace are the plausible shapes, and a
# permission check that fails open on " Admin " would be a bad way to find
# out that the roster screen does not strip.
check("case is not part of the rule", can_administer("ADMIN", EXECUTION), True)
check("nor is surrounding whitespace", can_administer("  manager  ", LOGGING), True)
check("but a different word is", can_administer("admins", LOGGING), False)

# --- the mode as it arrives from the settings dict ------------------------
# simple_mode is an INTEGER column, so what reaches this function is 1 or 0
# as often as it is True or False - and a plant that has never touched the
# setting can hand over None.
check("1 reads as logging mode", can_administer("manager", 1), True)
check("0 reads as execution mode", can_administer("manager", 0), False)
check("None reads as execution mode, the stricter answer",
      can_administer("manager", None), False)
check("and never weakens the admin answer", can_administer("admin", None), True)

print(f"  {CHECKS} combinations checked")

print("\n" + "=" * 62)
if FAILS:
    print(f"{len(FAILS)} of {CHECKS} ROLE CHECKS FAILED:\n" + "\n".join(FAILS))
else:
    print(f"ALL {CHECKS} ROLE ASSERTIONS PASSED")
raise SystemExit(1 if FAILS else 0)
