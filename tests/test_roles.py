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

# --- who sees the plant dashboard ----------------------------------------
# One function, asked by the door on Home.py and by every navigation bar. The
# bug it exists to prevent is not a permission hole, it is the opposite: a
# link drawn for somebody the door then turns away, which reads as the app
# being broken rather than as a rule.
from crud import can_view_scada  # noqa: E402

print("\n  The plant dashboard")
check("a manager sees it", can_view_scada("manager"), True)
check("an admin sees it", can_view_scada("admin"), True)
check("an operator does not", can_view_scada("operator"), False)
check("nor does a packer", can_view_scada("packer"), False)
check("case and whitespace are not part of the rule",
      can_view_scada("  Manager "), True)
check("an unknown role does not", can_view_scada("supervisor"), False)
check("and neither does a missing one", can_view_scada(None), False)

# The management screens refuse an operator at the door, not only in the
# menu. Analytics was the exception on the old Streamlit pages: it left the
# menu and the address went on working, so anybody signed in could read the
# whole plant's figures. Each router now carries its own door (a FastAPI
# dependency, not a page-top st.stop()) - checked at the source that
# actually serves the data, which is a stronger guarantee than the old
# single-page check: a manager-cockpit sub-feature that forgot the sidebar
# link would still be caught here, where it never would have been by a menu
# check alone.
import pathlib as _pl  # noqa: E402
_root = _pl.Path(__file__).resolve().parent.parent
for _router, _ability in (("batch_history.py", "view_manager_cockpit"),
                          ("analytics.py", "view_analytics")):
    _src = (_root / "api" / "routers" / _router).read_text(encoding="utf-8")
    check(f"{_router} turns away anyone without {_ability}, at its own door",
          f'require_ability("{_ability}")' in _src, True)

print("\n" + "=" * 62)
if FAILS:
    print(f"{len(FAILS)} of {CHECKS} ROLE CHECKS FAILED:\n" + "\n".join(FAILS))
else:
    print(f"ALL {CHECKS} ROLE ASSERTIONS PASSED")
raise SystemExit(1 if FAILS else 0)
