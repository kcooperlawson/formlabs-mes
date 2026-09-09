"""The hardware gateway switch, and the screen it opens.

The Device Gateway registry sat in the code for months with nothing linking to
it. That was on purpose - the gateway has never polled a real machine - but an
unlinked page is a bad way to say "not yet", because the only person who knows
why is whoever wrote the comment. It is a Plant Settings switch now, off by
default, and this test covers the three things that switch has to get right.

One: the setting has to survive a save. A setting that writes and does not read
back is a switch that does nothing, which is what shift_count was quietly doing
until its own test caught it.

Two: the link and the page have to agree. If the sidebar shows the link on one
rule and the page refuses on another, somebody clicks a link and gets Access
Denied, and now they think their account is broken.

Three: with the gateway off, the page has to say where the switch is. An empty
registry with no explanation is how a feature gets reported as a bug.
"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import _boot  # noqa: E402  (throwaway database, refuses production)

import crud  # noqa: E402
import database as db  # noqa: E402

FAILURES = []
COUNT = 0


def check(cond, what):
    global COUNT
    COUNT += 1
    if not cond:
        FAILURES.append(what)
        print(f"  FAIL  {what}")


def src(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


# ------------------------------------------------------------ the setting --
print("\nThe switch itself")

start = db.get_plant_settings()
check("enable_device_gateway" in start,
      "plant settings carry the gateway switch at all")
check(bool(start.get("enable_device_gateway")) is False,
      "a plant that has never touched it has the gateway off")

db.update_plant_settings({"enable_device_gateway": True})
check(bool(db.get_plant_settings().get("enable_device_gateway")) is True,
      "switching it on reads back as on")

db.update_plant_settings({"enable_device_gateway": False})
check(bool(db.get_plant_settings().get("enable_device_gateway")) is False,
      "switching it back off reads back as off")

# Saved as an integer flag, the same as every other checkbox in that form. A
# raw True lands in the column as something the next reader has to guess at.
check("enable_device_gateway" in src("crud.py").split("int_flags")[1][:400],
      "the switch is handled as an integer flag, like the rest of the checkboxes")

# The migration has to be in the chain, or a plant that upgrades gets a column
# that only exists on machines where the models file happened to create it.
mig = src("migrations/versions/0017_device_gateway_toggle.py")
check('down_revision = "0016_operator_last_picks"' in mig or
      "down_revision = '0016_operator_last_picks'" in mig,
      "0017 follows 0016, so the chain has no gap")
check("enable_device_gateway = 0" in mig,
      "existing plants are migrated to off rather than to null")

# ------------------------------------------------------- the way in and out --
print("\nThe link and the page agree")

admin_src = src("pages/Admin_Panel.py")
cockpit_src = src("pages/Manager_Cockpit.py")
registry_src = src("pages/Device_Registry.py")
shell_src = src("ui_shell.py")

# The link lives in the shared menu now - one definition, drawn by every
# sidebar in the application - so this checks it there and checks that the
# consoles use that menu rather than writing their own.
check("pages/Device_Registry.py" in shell_src, "the shared menu links to the registry")
_where_flag = shell_src.find('get("enable_device_gateway"')
_where_link = shell_src.find('st.page_link("pages/Device_Registry.py"')
check(0 <= _where_flag < _where_link,
      "the shared menu reads the switch before it draws the link")
check("role_can_administer" in shell_src[max(0, _where_flag - 400):_where_link],
      "and only offers it to somebody who administers")
for name, text in (("IT Admin", admin_src), ("Manager Cockpit", cockpit_src)):
    check("nav_menu()" in text, f"{name} draws the shared menu")

check("role_can_administer" in registry_src,
      "the registry gates on the same permission the link does")
check('user_role") != "admin"' not in registry_src,
      "the registry no longer uses its own stricter rule than the link that reaches it")

flag_at = registry_src.find('get("enable_device_gateway"')
stop_at = registry_src.find("st.stop()", flag_at)
check(flag_at > 0 and stop_at > flag_at,
      "with the gateway off the registry stops instead of drawing an empty page")
tail = registry_src[flag_at:stop_at]
check("Plant Settings" in tail or "IT Admin" in tail,
      "and it says where the switch is, rather than only refusing")

# --------------------------------------------------------- the handbook link --
print("\nThe handbook reaches every sidebar")

check("def handbook_link" in src("ui_shell.py"),
      "there is one definition of the handbook link")

# Every page that builds its own sidebar instead of calling render_shell. The
# first version of this link was written inline and reached two of six.
own_sidebar = ["Home.py", "pages/Manager_Cockpit.py", "pages/Analytics_Hub.py",
               "pages/Live_Reactors.py", "pages/Admin_Panel.py"]
for rel in own_sidebar:
    check("handbook_link()" in src(rel), f"{rel} calls the shared handbook link")

# And nobody has pasted the markup back in. One definition or none.
for rel in own_sidebar:
    check(len(re.findall(r"Formlabs_MES_Handbook\.pdf", src(rel))) == 0,
          f"{rel} has no second copy of the link markup")

print(f"\n{COUNT - len(FAILURES)}/{COUNT} passed")
if FAILURES:
    print(f"\n{len(FAILURES)} FAILED:")
    for f in FAILURES:
        print(f"  - {f}")
sys.exit(1 if FAILURES else 0)
