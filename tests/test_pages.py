"""Render every page headless as an admin and report which ones raise."""
import os, sys, warnings
warnings.filterwarnings("ignore")
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _boot import boot, ROOT
boot(fresh=False)

from streamlit.testing.v1 import AppTest
import streamlit as _st
_st.page_link = lambda *a, **k: None
_st.logo = lambda *a, **k: None
_st.switch_page = lambda *a, **k: None

import crud
# Tv_Dashboard ends in a deliberate sleep-then-rerun refresh loop, so it never
# returns control to a test harness. It is covered by compile + pyflakes instead.
SKIP = {"Tv_Dashboard.py"}
PAGES = ["Home.py"] + sorted(f"pages/{f}" for f in os.listdir(ROOT / "pages")
                             if f.endswith(".py") and f not in SKIP)
rows, bad = [], 0


def render(path, label=None):
    """Run one page as an admin and record what happened."""
    global bad
    at = AppTest.from_file(str(ROOT / path), default_timeout=120)
    for k, v in {"authenticated": True, "user_name": "Maria Vega",
                 "user_role": "admin", "user_shift": "Shift 1",
                 "user_id": 1, "username": "maria"}.items():
        at.session_state[k] = v
    try:
        at.run()
        exc = at.exception
        if exc:
            bad += 1
            msg = str(exc[0].message).strip().splitlines()[-1][:90]
            rows.append(("RAISED ", label or path, msg))
        else:
            n = len(at.markdown) + len(at.dataframe) + len(at.button) + len(at.selectbox)
            rows.append(("ok     ", label or path, f"{n} elements"))
    except Exception as e:
        bad += 1
        rows.append(("ERROR  ", label or path, str(e).splitlines()[-1][:90]))


# The Device Gateway registry stops at a notice unless the plant has switched
# the gateway on, so with the switch left alone this sweep would render one
# line of that page and call it covered. The switch goes on for the sweep and
# back to whatever it was afterwards, and the off path gets its own run at the
# end.
import database as _db
_gateway_was = bool(_db.get_plant_settings().get("enable_device_gateway", 0))
_db.update_plant_settings({"enable_device_gateway": True})
try:
    for path in PAGES:
        render(path)
finally:
    _db.update_plant_settings({"enable_device_gateway": _gateway_was})

render("pages/Device_Registry.py", label="pages/Device_Registry.py (gateway off)")

print("=" * 78)
print("PAGE RENDER SWEEP  (admin session, real Postgres, nav stubbed)")
print("=" * 78)
for st_, p, note in rows:
    print(f"  {st_} {p:<36} {note}")
print("=" * 78)
print(f"{len(rows)-bad}/{len(rows)} pages rendered clean")
raise SystemExit(1 if bad else 0)
