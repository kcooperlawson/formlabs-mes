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
for path in PAGES:
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
            rows.append(("RAISED ", path, msg))
        else:
            n = len(at.markdown) + len(at.dataframe) + len(at.button) + len(at.selectbox)
            rows.append(("ok     ", path, f"{n} elements"))
    except Exception as e:
        bad += 1
        rows.append(("ERROR  ", path, str(e).splitlines()[-1][:90]))

print("=" * 78)
print("PAGE RENDER SWEEP  (admin session, real Postgres, nav stubbed)")
print("=" * 78)
for st_, p, note in rows:
    print(f"  {st_} {p:<36} {note}")
print("=" * 78)
print(f"{len(rows)-bad}/{len(rows)} pages rendered clean")
raise SystemExit(1 if bad else 0)
