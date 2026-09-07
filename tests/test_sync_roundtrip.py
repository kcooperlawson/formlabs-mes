"""The whole round trip, against a stand-in for the Apps Script.

Google cannot be reached from a test run, and the cases that matter cannot be
produced on demand against the real thing anyway: a payload that arrives empty,
a deployment still running last week's code, a script attached to no
spreadsheet, a web app answering with a sign-in page. Every one of those has
already happened on this plant's install, and every one of them looked like
success from the application's side.

So the stand-in behaves exactly as the script does and can be told to
misbehave. What is proved here is the contract between the two halves - that
what the script says it wrote is what the page believes, and that no reply
short of "the rows are in the tab" is ever reported as a delivery.
"""
import json, pathlib, subprocess, sys, time
import requests

# The stand-in listens on loopback, and this container routes outbound HTTP
# through a proxy that has no idea what 127.0.0.1 means. A session that does
# not read the environment keeps the test talking to the right thing.
SESSION = requests.Session()
SESSION.trust_env = False
ROOT = str(pathlib.Path(__file__).resolve().parent.parent)
sys.path.insert(0, ROOT)
import sheet_sync as ss

PAYLOAD = {"sheet_name": "KPI Summary", "data": [{"Date": "2026-09-07", "Units": 10},
                                                 {"Date": "2026-09-06", "Units": 20},
                                                 {"Date": "2026-09-05", "Units": 30},
                                                 {"Date": "2026-09-04", "Units": 40},
                                                 {"Date": "2026-09-03", "Units": 50}]}
EXPECT = {"good": (True, "ok"), "eatrows": (False, "script"), "short": (False, "short"),
          "oldver": (True, "outdated"), "legacy": (True, "legacy"),
          "unbound": (False, "script"), "signin": (False, "signin"), "auth": (False, "auth")}
fails = 0
for mode, (want_ok, want_level) in EXPECT.items():
    p = subprocess.Popen([sys.executable, str(pathlib.Path(__file__).resolve().parent / "fixtures" / "fake_apps_script.py"), mode],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1.5)
    try:
        r = SESSION.post("http://127.0.0.1:8799/exec", json=PAYLOAD, timeout=10)
        v = ss.diagnose_response(r.status_code, r.text, expect_rows=len(PAYLOAD["data"]))
        ok = (v["ok"], v["level"]) == (want_ok, want_level)
        fails += 0 if ok else 1
        print(f"{'PASS' if ok else 'FAIL'}  {mode:9} -> ok={v['ok']!s:5} level={v['level']:9} "
              f"rows={v['rows']!s:5} sheet={v['sheet']}")
        if not ok:
            print(f"        expected ok={want_ok} level={want_level}")
        if v["message"]:
            print(f"        says: {' '.join(v['message'].split())[:110]}")
    finally:
        p.terminate(); p.wait()
print("\nROUND TRIP:", "all as expected" if not fails else f"{fails} MISMATCHES")
sys.exit(1 if fails else 0)
