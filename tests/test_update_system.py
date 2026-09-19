"""The update system's own logic, without a network or a plant PC.

The end-to-end version - a real portable PC, a real package, a real restart -
is dev/simulate_portable_update.py. This is the fast half: what a package
must contain, what the GitHub check does when the repo is private or the
allowance runs out, who may publish, and whether Repair_Updater.bat still
carries the file it claims to.
"""
import base64
import importlib.util
import os
import pathlib
import shutil
import sys
import tempfile
import zipfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "setup"))
sys.path.insert(0, str(ROOT / "dev"))

FAILS, CHECKS = [], 0


def check(cond, label):
    global CHECKS
    CHECKS += 1
    if not cond:
        FAILS.append(label)
        print(f"  FAIL  {label}")


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


print("=" * 66)
print("UPDATE SYSTEM: packages, the GitHub check, publishing, the repair file")
print("=" * 66)

# --- what a package carries --------------------------------------------------
make_update = load("make_update", ROOT / "dev" / "make_update.py")

files = make_update.every_shippable_file()
check("VERSION" in files, "a package carries VERSION - the far PC has to report the new version")
check(any(f.startswith("frontend/dist/") for f in files),
      "it carries the built frontend, which git ignores and a plant PC can't build")
check(not any(f == ".env" or f.endswith("/.env") for f in files), "it never carries a .env")
for private in ("dev/update_signing_private.pem", "setup/update_signing_private.pem"):
    check(private not in files, f"it never carries {private}")
for machine_owned in ("pgdata", "backups", "logs", "uploads", "certs", "venv", "updates", "rollback"):
    check(not any(f.split("/")[0] == machine_owned for f in files),
          f"it never carries anything from {machine_owned}\\ - that belongs to the plant PC")
check(not any(f.split("/")[0] in ("dev", "tests") for f in files),
      "it carries neither dev/ nor tests/ - a plant PC runs neither")
check("Repair_Updater.bat" in files and "setup/bootstrap_update.py" in files,
      "it carries the repair tool, so a PC only ever needs that carried to it once")

# --- the applier's own rules, against a package built here -------------------
import apply_update  # noqa: E402

check(apply_update.version_tuple("PT-V4.10") > apply_update.version_tuple("PT-V4.9"),
      "4.10 is newer than 4.9 - compared as numbers, not as text")
check(apply_update.version_tuple("PT-V4.08") > apply_update.version_tuple("PT-V4.07"),
      "and 4.08 is newer than 4.07")

# A full package records no from_version, which is what lets it apply to any
# older version - the thing that made diff packages fragile.
# Never into dist\: a real release may be sitting there waiting to be carried
# to a plant PC, and this builds a file with exactly that name.
scratch_dist = pathlib.Path(tempfile.mkdtemp(prefix="test_packages_"))
out, manifest = make_update.build_release(notes="test build", out_dir=scratch_dist)
try:
    check(manifest["from_version"] is None, f"a full package pins no from_version (got {manifest['from_version']!r})")
    check(manifest["to_version"] == (ROOT / "VERSION").read_text(encoding="utf-8").strip(),
          "it is tagged with the version in VERSION")
    with zipfile.ZipFile(out) as zf:
        problems = apply_update.check_package(zf, manifest)
    check(problems == [], f"the applier accepts it: checksums and paths all good (got {problems[:3]})")
    import update_signing  # noqa: E402
    ok, detail = update_signing.verify(manifest, ROOT / "setup" / "update_signing_public.pem")
    check(ok, f"and it is signed by this project's key ({detail})")

    # The applier must refuse a package whose files were swapped after signing.
    tampered = dict(manifest)
    tampered["files"] = [dict(f) for f in manifest["files"]]
    tampered["files"][0]["sha256"] = "0" * 64
    with zipfile.ZipFile(out) as zf:
        problems = apply_update.check_package(zf, tampered)
    check(any("checksum" in p for p in problems), f"a changed file is caught (got {problems[:2]})")
finally:
    shutil.rmtree(scratch_dist, ignore_errors=True)

# --- the GitHub check --------------------------------------------------------
from api import update_check  # noqa: E402


class FakeResponse:
    def __init__(self, status_code, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload


RELEASE = {"tag_name": "PT-V9.99", "html_url": "https://example.invalid/r", "body": "notes",
           "published_at": "2026-09-17T00:00:00Z",
           "assets": [{"name": "mes_update_PT-V9.99.zip", "url": "https://example.invalid/a", "id": 1}]}

import requests  # noqa: E402

calls = {"n": 0, "headers": None}
real_get = requests.get


def fake_get(url, **kwargs):
    calls["n"] += 1
    calls["headers"] = kwargs.get("headers") or {}
    return FakeResponse(calls.get("status", 200), RELEASE)


requests.get = fake_get
real_token = os.environ.get("GITHUB_RELEASE_TOKEN")
try:
    update_check._cached.update(at=0.0, value=None)
    os.environ.pop("GITHUB_RELEASE_TOKEN", None)
    first = update_check.status()
    check(first["update_available"] is True and first["latest_version"] == "PT-V9.99",
          f"a newer published release shows as available (got {first})")
    before = calls["n"]
    second = update_check.status()
    check(calls["n"] == before, "a second look inside the cache window doesn't ask GitHub again")
    check(second["current_version"] == update_check.current_version(),
          "...but it still reports the version this PC is on right now")
    update_check.status(force=True)
    check(calls["n"] > before, "Check now asks GitHub anyway")

    os.environ["GITHUB_RELEASE_TOKEN"] = "test-token-value"
    update_check.status(force=True)
    check(calls["headers"].get("Authorization") == "Bearer test-token-value",
          f"the token is sent, which is what a PRIVATE repo needs to answer at all (got {calls['headers']})")

    # A private repo with no token answers 404, and used to look like "nothing
    # published yet" - it has to say what's actually wrong.
    calls["status"] = 404
    os.environ.pop("GITHUB_RELEASE_TOKEN", None)
    update_check._cached.update(at=0.0, value=None)
    private = update_check.status(force=True)
    check(private["error"] and "private" in private["error"].lower(),
          f"a private repo with no token says so (got {private['error']!r})")
    check(private["update_available"] is False, "...and doesn't claim an update is available")
    update_check._cached.update(at=0.0, value=None)
    after_error = update_check.status()
    check(calls["n"] > 0 and after_error["error"], "an error isn't cached for 15 minutes")

    calls["status"] = 200
    os.environ.pop("GITHUB_RELEASE_TOKEN", None)
    check(update_check.publish_enabled() is False,
          "publishing is off unless a machine opts in - a signed release is trusted everywhere")
    os.environ["MES_ALLOW_PUBLISH"] = "1"
    check(update_check.publish_enabled() is True, "...and on where MES_ALLOW_PUBLISH=1 says so")
    os.environ.pop("MES_ALLOW_PUBLISH", None)
finally:
    requests.get = real_get
    update_check._cached.update(at=0.0, value=None)
    if real_token is None:
        os.environ.pop("GITHUB_RELEASE_TOKEN", None)
    else:
        os.environ["GITHUB_RELEASE_TOKEN"] = real_token

# --- serving updates from your own PC ---------------------------------------
# The real thing, over a real socket: setup/update_server.py serving a real
# signed package, and this PC's own update check fetching it - no GitHub, no
# internet, nothing mocked but the address.
import socket  # noqa: E402
import threading  # noqa: E402

update_server = load("update_server", ROOT / "setup" / "update_server.py")

served = pathlib.Path(tempfile.mkdtemp(prefix="update_server_"))
package, manifest = make_update.build_release(notes="served from a home PC", out_dir=served)

with socket.socket() as probe:
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]

from http.server import ThreadingHTTPServer  # noqa: E402

TOKEN = "a-shared-secret"
httpd = ThreadingHTTPServer(("127.0.0.1", port), update_server.make_handler(served, TOKEN))
threading.Thread(target=httpd.serve_forever, daemon=True).start()

real_env = {k: os.environ.get(k) for k in ("MES_UPDATE_URL", "MES_UPDATE_TOKEN", "DB_URL")}
try:
    os.environ["MES_UPDATE_URL"] = f"http://127.0.0.1:{port}/latest.json"
    update_check._cached.update(at=0.0, value=None)

    os.environ.pop("MES_UPDATE_TOKEN", None)
    locked = update_check.status(force=True)
    check(locked["error"] and "token" in locked["error"].lower(),
          f"a server started with --token turns away a PC that hasn't got it (got {locked['error']!r})")

    os.environ["MES_UPDATE_TOKEN"] = TOKEN
    update_check._cached.update(at=0.0, value=None)
    hosted = update_check.status(force=True)
    check(hosted["error"] is None and hosted["latest_version"] == manifest["to_version"],
          f"with the token, it sees the package this PC is serving (got {hosted})")

    release = update_check.latest_release()
    check(release["asset_name"] == package.name and release["sha256"],
          f"the listing names the file and what it should hash to (got {release['asset_name']})")

    listed = update_check.list_available()
    check(len(listed) >= 1 and listed[0]["version"] == manifest["to_version"],
          f"the tab lists what that server has, newest first (got {[e['version'] for e in listed]})")
    check(listed[0]["current"] is True or listed[0]["newer"] is False,
          "the version this PC is already running is marked as such, not offered as an update")
    check(all("notes" in e and "published_at" in e for e in listed),
          "each row carries its notes and when it was published")

    # Two packages on the server: an older one must be listed too, and must be
    # installable only when the caller says "yes, go back".
    import json as _json  # noqa: E402
    import shutil as _shutil  # noqa: E402

    older = served / "mes_update_PT-V0.99.zip"
    _shutil.copy2(served / package.name, older)
    with zipfile.ZipFile(served / package.name) as src, zipfile.ZipFile(older, "w") as dst:
        for item in src.infolist():
            data = src.read(item.filename)
            if item.filename == "mes_update.json":
                old_manifest = _json.loads(data)
                old_manifest["to_version"] = "PT-V0.99"
                old_manifest["signature"] = update_signing.sign(old_manifest)
                data = _json.dumps(old_manifest, indent=2).encode()
            dst.writestr(item, data)

    listed = update_check.list_available()
    versions = [e["version"] for e in listed]
    check("PT-V0.99" in versions and versions[0] == manifest["to_version"],
          f"an older release is listed as well, below the newer one (got {versions})")
    older_row = next(e for e in listed if e["version"] == "PT-V0.99")
    check(older_row["newer"] is False, "...and is marked as not newer, so the page offers it as going back")
    try:
        update_check.apply_version("PT-V0.99")
        refused_downgrade = False
    except update_check.CheckError as exc:
        refused_downgrade = "not older" in str(exc)
    check(refused_downgrade, "going back is refused unless it is asked for deliberately")

    # Pointing this PC somewhere else, the way the Updates tab does.
    real_env_file = update_check.ENV_FILE
    update_check.ENV_FILE = pathlib.Path(tempfile.mkdtemp(prefix="env_")) / ".env"
    update_check.ENV_FILE.write_text("DB_URL=postgresql://keep/me\n", encoding="utf-8")
    try:
        info = update_check.set_source("192.168.0.15", "hunter2")
        check(info["kind"] == "server" and info["address"] == "http://192.168.0.15:8443",
              f"a bare IP typed into the page becomes a full address (got {info})")
        written = update_check.ENV_FILE.read_text(encoding="utf-8")
        check("DB_URL=postgresql://keep/me" in written, "...written into .env without disturbing what was there")
        check("MES_UPDATE_URL=http://192.168.0.15:8443" in written and "MES_UPDATE_TOKEN=hunter2" in written,
              f"...and both settings are in it (got {written!r})")
        back = update_check.set_source("", "")
        check(back["kind"] == "github", "a blank address goes back to GitHub")
    finally:
        _shutil.rmtree(update_check.ENV_FILE.parent, ignore_errors=True)
        update_check.ENV_FILE = real_env_file
        os.environ["MES_UPDATE_URL"] = f"http://127.0.0.1:{port}/latest.json"
        os.environ["MES_UPDATE_TOKEN"] = TOKEN
    older.unlink(missing_ok=True)

    real_updates = update_check.UPDATES
    update_check.UPDATES = pathlib.Path(tempfile.mkdtemp(prefix="downloaded_"))
    try:
        fetched = update_check.download_release(release)
        check(fetched.is_file() and fetched.stat().st_size == (served / package.name).stat().st_size,
              "the plant PC downloads the whole package over that connection")
        with zipfile.ZipFile(fetched) as zf:
            downloaded_manifest = __import__("json").loads(zf.read("mes_update.json"))
        ok, _ = update_signing.verify(downloaded_manifest, ROOT / "setup" / "update_signing_public.pem")
        check(ok, "...and what arrived is still signed by the real key")

        # Swap the served file for a tampered one: the download must be refused
        # on the checksum, before apply_update.py ever opens it.
        good = (served / package.name).read_bytes()
        (served / package.name).write_bytes(good[:-200] + b"x" * 200)
        try:
            update_check.download_release(release)
            refused = False
        except update_check.CheckError as exc:
            refused = "doesn't match" in str(exc)
        check(refused, "a package altered on the way is refused on arrival")
        (served / package.name).write_bytes(good)
    finally:
        shutil.rmtree(update_check.UPDATES, ignore_errors=True)
        update_check.UPDATES = real_updates
finally:
    httpd.shutdown()
    shutil.rmtree(served, ignore_errors=True)
    update_check._cached.update(at=0.0, value=None)
    for key, value in real_env.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value

# --- restarting --------------------------------------------------------------
import self_restart  # noqa: E402

check(self_restart.marker_path(ROOT) == ROOT / "updates" / ".restart-requested",
      "the restart marker is the file both launchers watch for")
os.environ["MES_SUPERVISED"] = "1"
check(self_restart.supervised() is True, "a launcher loop announces itself with MES_SUPERVISED")
os.environ.pop("MES_SUPERVISED", None)
os.environ["MES_LAUNCH_MODE"] = "portable"
check(self_restart._relaunch_command(ROOT)[-1].endswith("portable_launcher"),
      f"on a portable PC nothing relaunches a bare uvicorn (got {self_restart._relaunch_command(ROOT)[-2:]})")
os.environ.pop("MES_LAUNCH_MODE", None)

# --- the repair file a stuck PC gets ----------------------------------------
bat = (ROOT / "Repair_Updater.bat").read_text(encoding="utf-8", errors="replace").splitlines()
check(":PAYLOAD" in bat, "Repair_Updater.bat has its embedded payload marker")
payload = base64.b64decode("".join(bat[bat.index(":PAYLOAD") + 1:]))
check(payload == (ROOT / "setup" / "bootstrap_update.py").read_bytes(),
      "the copy embedded in Repair_Updater.bat is byte-for-byte setup/bootstrap_update.py "
      "(regenerate it with: python dev/embed_repair_updater.py)")

bootstrap = load("bootstrap_update", ROOT / "setup" / "bootstrap_update.py")
check("setup/update_signing_public.pem" not in bootstrap.ALLOWED,
      "the repair tool will never replace the key that decides whether a package is genuine")
check("utils.py" in bootstrap.ALLOWED and "setup/apply_update.py" in bootstrap.ALLOWED,
      "it does replace the updater's own files, which is its whole job")
check(all(name.split("/")[0] not in ("api", "frontend", "crud.py") for name in bootstrap.ALLOWED),
      "and nothing of the application itself - it cannot install a release")

print("\n" + "=" * 66)
if FAILS:
    print(f"{len(FAILS)} of {CHECKS} UPDATE SYSTEM CHECKS FAILED:")
    for f in FAILS:
        print(f"  - {f}")
else:
    print(f"ALL {CHECKS} UPDATE SYSTEM ASSERTIONS PASSED")
sys.stdout.flush()
raise SystemExit(1 if FAILS else 0)
