"""A stand-in for the Apps Script, so the round trip can be exercised.

Google is unreachable from here, and the interesting cases - a payload that
arrives empty, a deployment running last week's code, a sheet that is not
attached to the script - cannot be produced on demand against the real thing
anyway. This behaves exactly as the script does and lets all of them be run.
"""
import json, pathlib, sys
from http.server import BaseHTTPRequestHandler, HTTPServer
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
import sheet_sync as ss

MODE = sys.argv[1] if len(sys.argv) > 1 else "good"
TAB = {}

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _send(self, code, body, ctype="application/json"):
        b = body.encode(); self.send_response(code)
        self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(b)))
        self.end_headers(); self.wfile.write(b)
    def do_POST(self):
        raw = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        if MODE == "signin":
            return self._send(200, "<html>Sign in - accounts.google.com/ServiceLogin</html>", "text/html")
        if MODE == "auth":
            return self._send(401, "Unauthorized", "text/plain")
        if MODE == "legacy":
            return self._send(200, "formlabs-mes-ok: 5 rows", "text/plain")
        body = json.loads(raw)
        rep = {"token": ss.OK_TOKEN, "version": 2 if MODE == "oldver" else ss.SCRIPT_VERSION,
               "ok": True, "rows": 0, "sheet": "Keagan Weekly", "url": "https://docs.google.com/fake"}
        if MODE == "unbound":
            rep.update(ok=False, error="This script is not attached to a spreadsheet.")
            return self._send(200, json.dumps(rep))
        if body.get("ping"):
            rep["ping"] = True; return self._send(200, json.dumps(rep))
        rows = body.get("data") or []
        if MODE == "eatrows":
            rows = []
        if not rows:
            rep.update(ok=False, error="The payload arrived with no rows in it.",
                       tab=body.get("sheet_name"))
            return self._send(200, json.dumps(rep))
        TAB[body.get("sheet_name")] = rows
        rep.update(rows=len(rows) - (2 if MODE == "short" else 0), tab=body.get("sheet_name"))
        return self._send(200, json.dumps(rep))

HTTPServer(("127.0.0.1", 8799), H).serve_forever()
