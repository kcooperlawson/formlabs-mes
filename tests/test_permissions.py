"""Abilities: what a role gives, what a person is given, and who may give it.

This exists because of a bug that was not a permission hole at all. The rule
about who reaches the plant dashboard lived in the door on one page and was
copied by hand into six navigation bars, so when the door changed the bars went
on offering a link that bounced. Fixing that by hand a second time is how it
comes back a third.

So there is one function - user_can - and both the door and the link ask it.
What this file checks is that the function is right, that a grant is a grant
and a revoke is a revoke, that the history survives both, and the two rules
that stop this becoming a way to hand out the plant: you cannot give away an
ability you do not have, and only somebody who administers can give anything.

The last section is the one that matters most in a year: it reads the source of
every page and asserts the door and the menu are asking the same question.
"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import _boot  # noqa: E402  (throwaway database, refuses production)

import crud  # noqa: E402

FAILURES, COUNT = [], 0


def check(cond, what):
    global COUNT
    COUNT += 1
    if not cond:
        FAILURES.append(what)
        print(f"  FAIL  {what}")


def src(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


# ------------------------------------------------------------- the catalogue --
print("\nThe catalogue")

check(len(crud.ABILITIES) >= 8, "there are abilities to hand out at all")
for key, value in crud.ABILITIES.items():
    check(key.replace("_", "").isalnum(), f"{key} is a plain key")
    check(isinstance(value, tuple) and len(value) == 2,
          f"{key} has a label and an explanation")
    label, blurb = value
    check(label and label[0].isupper(), f"{key} reads as a sentence to a manager")
    check(len(blurb) > 30, f"{key} explains what it lets somebody do")

check(set(crud.ROLE_ABILITIES) == {"admin", "manager", "operator", "packer"},
      "every role in the application has an entry")
check(crud.role_abilities("admin") == set(crud.ABILITIES),
      "an administrator starts with everything")
check(crud.role_abilities("manager") == set(crud.ABILITIES),
      "so does a manager - this plant runs as a log and they administer it")
check(crud.role_abilities("operator") == set(),
      "an operator starts with none of it")
check(crud.role_abilities("OPERATOR ") == set(),
      "case and whitespace are not part of the rule")
check(crud.role_abilities("supervisor") == set(),
      "and a role nobody has heard of gets nothing")

# ------------------------------------------------------------ giving one out --
print("\nGiving an ability to one account")

crud.create_user("t_boss", "t_boss@test.local", "1234", "Test Boss", "manager")
crud.create_user("t_hand", "t_hand@test.local", "1234", "Test Hand", "operator")
users = crud.get_all_users_df()
boss_id = int(users[users["username"] == "t_boss"]["id"].iloc[0])
hand_id = int(users[users["username"] == "t_hand"]["id"].iloc[0])

# This suite runs against a database that is kept between runs, and grants
# are meant to outlive a restart - so the second run would inherit the first
# run's grants and read them as a bug in the code rather than in the test.
# The two fixture accounts start every run with nothing on them.
from db_core import ScopedSession  # noqa: E402
from models import UserAbility  # noqa: E402
_s = ScopedSession()
_s.query(UserAbility).filter(UserAbility.user_id.in_([boss_id, hand_id])).delete(
    synchronize_session=False)
_s.commit()
_s.close()

check(crud.user_can(hand_id, "operator", "view_scada") is False,
      "an operator cannot see the plant dashboard to begin with")

ok, msg = crud.grant_ability(hand_id, "view_scada", by_name="Test Boss",
                             by_user_id=boss_id, by_role="manager")
check(ok, f"a manager can give it away ({msg})")
check(crud.user_can(hand_id, "operator", "view_scada") is True,
      "and then the operator can see it")
check(crud.user_can(hand_id, "operator", "view_analytics") is False,
      "one ability at a time - nothing else came with it")
check(crud.granted_abilities(hand_id) == {"view_scada"},
      "the grant is the only one on the account")

ok, _ = crud.grant_ability(hand_id, "view_scada", by_name="Test Boss",
                           by_user_id=boss_id, by_role="manager")
check(ok and len(crud.ability_history(hand_id)) == 1,
      "giving the same ability twice does not write a second row")

# ---------------------------------------------------------- taking it back --
print("\nTaking it back")

ok, _ = crud.revoke_ability(hand_id, "view_scada", by_name="Test Boss")
check(ok, "a grant can be removed")
check(crud.user_can(hand_id, "operator", "view_scada") is False,
      "and the ability goes with it")

_hist = crud.ability_history(hand_id)
check(len(_hist) == 1, "the row is kept rather than deleted")
check(_hist[0]["active"] is False, "and marked as no longer in force")
check(_hist[0]["granted_by"] == "Test Boss" and _hist[0]["revoked_by"] == "Test Boss",
      "with both names on it, which is what anybody asks first")
check(_hist[0]["granted_at"] is not None and _hist[0]["revoked_at"] is not None,
      "and both times")

ok, _ = crud.revoke_ability(hand_id, "view_scada", by_name="Test Boss")
check(ok, "removing an ability nobody has is not an error")

# ------------------------------------------------------------- who may give --
print("\nWho is allowed to hand things out")

ok, msg = crud.grant_ability(boss_id, "manage_logs", by_name="Test Hand",
                             by_user_id=hand_id, by_role="operator")
check(not ok, "an operator cannot give away an ability they do not have")
check("do not have" in msg, f"and is told why ({msg})")

crud.grant_ability(hand_id, "view_analytics", by_name="Test Boss",
                   by_user_id=boss_id, by_role="manager")
ok, msg = crud.grant_ability(boss_id, "view_analytics", by_name="Test Hand",
                             by_user_id=hand_id, by_role="operator")
check(not ok, "not even one they were themselves given")
check(crud.user_can(boss_id, "manager", "manage_logs") is True,
      "the manager still has their own abilities from their role")

ok, msg = crud.grant_ability(hand_id, "fly_the_plant", by_name="Test Boss",
                             by_user_id=boss_id, by_role="manager")
check(not ok and "no ability" in msg, "an ability that does not exist is refused")

ok, msg = crud.grant_ability(boss_id, "view_scada", by_name="Test Boss",
                             by_user_id=boss_id, by_role="manager")
check(not ok and "role" in msg,
      "and granting what the role already gives says so rather than writing a row")

check(crud.user_can(hand_id, "operator", "") is False, "a blank ability is a no")
check(crud.user_can(None, "operator", "view_scada") is False,
      "so is nobody at all")
check(crud.user_can(hand_id, "manager", "manage_people") is True,
      "the role is still what answers first, before any lookup")

_map = crud.abilities_of(hand_id, "operator")
check(_map["view_analytics"] == "granted", "the panel can tell a grant from a role")
check(_map["manage_logs"] == "", "and from nothing at all")
check(crud.abilities_of(boss_id, "manager")["manage_logs"] == "role",
      "and says when it comes with the job")

# ---------------------------------------------- the accessor a page actually uses --
# crud.user_can takes arguments; a page calls database.can(), which reads who
# is signed in off the session. That indirection is where a mistake would
# actually live, so it is checked against a real account rather than assumed.
print("\nWhat a page asks")

import streamlit as _st  # noqa: E402
import database as _db  # noqa: E402

_st.session_state["user_role"] = "operator"
_st.session_state["user_id"] = hand_id
_db._granted_abilities.clear()
check(_db.can("manage_logs") is False, "an operator is refused by can()")

crud.grant_ability(hand_id, "manage_logs", by_name="Test Boss",
                   by_user_id=boss_id, by_role="manager")
_db._granted_abilities.clear()
check(_db.can("manage_logs") is True, "and allowed once it is granted")
check(_db.can("manage_people") is False, "with nothing else coming along")

crud.revoke_ability(hand_id, "manage_logs", by_name="Test Boss")
_db._granted_abilities.clear()
check(_db.can("manage_logs") is False, "and refused again when it is taken back")

_st.session_state["user_role"] = "manager"
check(_db.can("manage_logs") is True, "a role still answers before any lookup")
_st.session_state["user_role"] = "operator"

# ----------------------------------------------------- the doors and the menu --
print("\nEvery door and every link ask the same question")

# The failure this prevents: a page whose door says one thing and whose menu
# entry says another. They drifted for a day and an operator was handed a
# button that sent them back where they started.
DOORS = {
    "pages/Analytics_Hub.py": "view_analytics",
    "pages/Manager_Cockpit.py": "view_manager_cockpit",
    "pages/Mgr_Historical.py": "view_manager_cockpit",
    "pages/Mgr_Scrap_Intel.py": "view_manager_cockpit",
    "pages/Mgr_Lot_Verification.py": "view_manager_cockpit",
    "pages/Mgr_Cleanliness.py": "view_manager_cockpit",
    "pages/Mgr_Floor_Comms.py": "view_manager_cockpit",
    "pages/Mgr_Assigned_Runs.py": "view_manager_cockpit",
    "pages/Mgr_Theme_Gallery.py": "view_manager_cockpit",
    "pages/Mgr_Google_Sync.py": "export_data",
    "pages/Mgr_Log_Management.py": "manage_logs",
    "pages/Mgr_Roster.py": "manage_people",
    "pages/Mgr_Resin_Canvas.py": "manage_resins",
}
for page, ability in DOORS.items():
    text = src(page)
    check(f'can("{ability}")' in text, f"{pathlib.Path(page).name} asks for {ability}")
    check('user_role") not in ["manager", "admin"]' not in text,
          f"{pathlib.Path(page).name} no longer has its own copy of the rule")

check('if not can("view_scada")' in src("Home.py"),
      "the plant dashboard asks for view_scada at its door")
check('can("manage_reactors")' in src("pages/Live_Reactors.py"),
      "editing reactors asks for manage_reactors")

# One menu, built from abilities, used by every bar in the application.
shell = src("ui_shell.py")
check("def nav_links(" in shell and "def nav_bar(" in shell and "def nav_menu(" in shell,
      "there is one definition of the menu")
for ability in ("view_scada", "view_manager_cockpit", "view_analytics"):
    check(f'can("{ability}")' in shell, f"the menu asks for {ability}")

# And nobody has written their own bar again. Six of them is how this started.
for page in sorted((ROOT / "pages").glob("*.py")) + [ROOT / "Home.py"]:
    text = page.read_text(encoding="utf-8")
    check("st.columns(6, gap=" not in text and "nav_col1" not in text,
          f"{page.name} uses the shared navigation rather than its own bar")

print(f"\n{COUNT - len(FAILURES)}/{COUNT} passed")
if FAILURES:
    print(f"\n{len(FAILURES)} FAILED:")
    for f in FAILURES:
        print(f"  - {f}")
sys.exit(1 if FAILURES else 0)
