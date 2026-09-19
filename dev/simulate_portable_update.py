"""Update a PORTABLE plant PC end to end, the way the work PC has to work.

    venv\\Scripts\\python.exe dev\\simulate_portable_update.py

Builds a throwaway plant PC in a temp folder - the last commit's code, marked
as PT-V4.07, running the bundled database out of its own pgdata\\ with an
empty .env, which is exactly what a portable install looks like - and then:

  1. applies a full signed package to it and expects it to REFUSE, because
     an old utils.py can't find a portable database to back up. That refusal
     is the bug the work PC hit;
  2. carries Repair_Updater.bat over to it - the way you would to the work
     PC, since that PC has no setup/bootstrap_update.py of its own yet -
     runs it, applies the same package again, and expects it to install,
     migrate and boot;
  3. starts a real uvicorn server and has it restart itself the way
     api/routers/updates.py does, to prove the server actually stops and
     leaves the marker its launcher loop watches for;
  4. turns on gateway access (setup/portable_lan_access.py) and connects to
     the bundled database over this PC's own LAN address, the way a floor
     gateway PC would.

Nothing here touches the real project folder, its .env, its logs, or any
database the app uses.
"""
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
PY = str(PROJECT / "venv" / "Scripts" / "python.exe") if os.name == "nt" else sys.executable
WORK = Path(tempfile.mkdtemp(prefix="portable_update_"))
PLANT = WORK / "plant_pc"
FAILS, CHECKS = [], 0


def check(cond, label):
    global CHECKS
    CHECKS += 1
    print(f"  {'PASS' if cond else 'FAIL'}  {label}", flush=True)
    if not cond:
        FAILS.append(label)


def run(args, cwd=PLANT, env=None, timeout=900):
    merged = {k: v for k, v in os.environ.items()
              if k not in ("DB_URL", "TEST_DB_URL", "GATEWAY_ENCRYPTION_KEY", "PG_PASS", "PG_BIN_DIR")}
    merged["PYTHONIOENCODING"] = "utf-8"
    merged.update(env or {})
    return subprocess.run([PY, *args], cwd=str(cwd), env=merged, capture_output=True,
                          text=True, timeout=timeout)


def build_plant():
    """The last commit's code, which is what a PC that hasn't been updated in
    a while is running - not the working tree, which already has the fix."""
    PLANT.mkdir(parents=True)
    tar = subprocess.run(["git", "archive", "--format=tar", "HEAD"], cwd=PROJECT,
                         capture_output=True, check=True).stdout
    import io
    import tarfile
    with tarfile.open(fileobj=io.BytesIO(tar)) as archive:
        archive.extractall(PLANT)
    (PLANT / "VERSION").write_text("PT-V4.07\n", encoding="utf-8")
    (PLANT / ".env").write_text("", encoding="utf-8")  # portable mode: no DB_URL at all
    # The built frontend is git-ignored, so the archive has none - a portable
    # PC has one, and the launcher refuses to start without it.
    shutil.copytree(PROJECT / "frontend" / "dist", PLANT / "frontend" / "dist")


def create_portable_database():
    """A real portable PC has a pgdata\\ folder, because it has been run at
    least once. Create one, then stop it - an update is normally applied with
    the app closed.

    Built with the PROJECT's launcher, not the plant's: the plant is on 4.01
    code, whose first-run path is the one 4.03 fixed, and a pgdata folder is
    a pgdata folder whichever version created it."""
    code = (
        "import sys; sys.path.insert(0, r'{project}'); sys.path.insert(0, r'{project}\\api')\n"
        "import portable_launcher as pl, pathlib\n"
        "pl.BASE_DIR = pathlib.Path(r'{plant}')\n"
        "admin_uri, _ = pl._start_embedded_postgres()\n"
        "pl._ensure_database(admin_uri, pl.DB_NAME)\n"
        "import pgserver; pgserver.pg_ctl(['-w', 'stop'], pgdata=pathlib.Path(r'{plant}') / 'pgdata')\n"
        "print('portable database created')\n"
    ).format(plant=str(PLANT), project=str(PROJECT))
    return run(["-c", code], timeout=600)


def build_package():
    import importlib.util
    sys.path.insert(0, str(PROJECT / "dev"))
    sys.path.insert(0, str(PROJECT / "setup"))
    spec = importlib.util.spec_from_file_location("make_update", PROJECT / "dev" / "make_update.py")
    mu = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mu)
    staged = PLANT / "updates"
    staged.mkdir(exist_ok=True)
    # Built straight into the test PC's own folder: dist\ may be holding a
    # real release waiting to be carried somewhere.
    out, manifest = mu.build_release(notes="portable update test", out_dir=staged)
    return out, manifest


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


RESTART_APP = '''
import os, sys, threading, time
sys.path.insert(0, r"{plant}")
sys.path.insert(0, r"{plant}\\setup")
os.environ["MES_SUPERVISED"] = "1"
import uvicorn
from fastapi import FastAPI
import self_restart

app = FastAPI()

@app.get("/restart")
def restart():
    return {{"mode": self_restart.request_restart(root=r"{plant}", delay_seconds=0.5)}}

uvicorn.run(app, host="127.0.0.1", port={port}, log_level="error")
print("SERVER RETURNED FROM uvicorn.run")
'''



LAN_PROBE = """
import os, socket, sys
sys.path.insert(0, r"{plant}")
sys.path.insert(0, r"{plant}\\api")
sys.path.insert(0, r"{plant}\\setup")
import portable_launcher as pl, portable_lan_access as lan, pathlib
pl.BASE_DIR = pathlib.Path(r"{plant}")
lan.ROOT = pathlib.Path(r"{plant}"); lan.ENV = pathlib.Path(r"{plant}") / ".env"
lan.PGDATA = pathlib.Path(r"{plant}") / "pgdata"

print("ENABLE_RC", lan.enable({port}))
for line in (pathlib.Path(r"{plant}") / ".env").read_text(encoding="utf-8").splitlines():
    if "=" in line:
        k, v = line.split("=", 1)
        os.environ[k.strip()] = v.strip()

admin_uri, _ = pl._start_embedded_postgres()
pl._ensure_database(admin_uri, pl.DB_NAME)

import psycopg2
ip, password = lan.local_ip(), os.environ["PORTABLE_DB_PASSWORD"]
try:
    conn = psycopg2.connect(f"postgresql://postgres:{{password}}@{{ip}}:{port}/formlabs_mes", connect_timeout=10)
    with conn.cursor() as cur:
        cur.execute("SELECT current_database(), inet_server_port()")
        print("REACHED_OVER_LAN", cur.fetchone())
    conn.close()
except Exception as exc:
    print("LAN_FAILED", exc)

try:
    psycopg2.connect(f"postgresql://postgres:wrong@{{ip}}:{port}/formlabs_mes", connect_timeout=10)
    print("WRONG_PASSWORD_ACCEPTED")
except Exception:
    print("WRONG_PASSWORD_REFUSED")

import pgserver
pgserver.pg_ctl(["-w", "stop"], pgdata=pathlib.Path(r"{plant}") / "pgdata")
print("LAN_PROBE_DONE")
"""


def lan_phase():
    print("\n== 4. A gateway PC on the floor can reach the bundled database")
    port = free_port()
    probe = run(["-c", LAN_PROBE.format(plant=str(PLANT), port=port)], timeout=600)
    out = probe.stdout
    if "LAN_PROBE_DONE" not in out:
        print(out[-1500:], probe.stderr[-1000:])
    check("ENABLE_RC 0" in out, "turning on gateway access sets a fixed port, a password and a pg_hba line")
    check("REACHED_OVER_LAN" in out,
          f"the database answers on this PC's LAN address, port {port} (got {out.strip().splitlines()[-2:] if out else None})")
    check("WRONG_PASSWORD_REFUSED" in out, "...and refuses a wrong password")
    env_text = (PLANT / ".env").read_text(encoding="utf-8")
    check("PORTABLE_DB_LAN=1" in env_text and "PORTABLE_DB_PASSWORD=" in env_text,
          "...with the settings written to .env so every later start does the same")
    check("GATEWAY_DB_URL=postgresql://postgres:" in out,
          "...and it prints the exact line to put in the gateway PC's .env")


def main():
    print(f"Building a portable plant PC on PT-V4.07 in {PLANT} ...", flush=True)
    build_plant()
    made = create_portable_database()
    if "portable database created" not in made.stdout:
        print(made.stdout[-1200:], made.stderr[-1200:])
    check("portable database created" in made.stdout,
          f"the test PC has a bundled database, like a portable install does (got {made.stdout.strip()[-200:]!r})")
    package, manifest = build_package()
    print(f"Full package: {package.name}, {len(manifest['files'])} files, "
          f"from_version={manifest['from_version']}", flush=True)

    check(manifest["from_version"] is None,
          f"the package applies to any older version, not one (got {manifest['from_version']!r})")
    check(any(f["path"] == "VERSION" for f in manifest["files"]), "it carries VERSION")
    check(any(f["path"].startswith("frontend/dist/") for f in manifest["files"]), "it carries the built frontend")
    check(not any(f["path"].endswith(".env") for f in manifest["files"]), "it carries no .env")

    print("\n== 1. An old portable PC refuses the update (the bug from the work PC)")
    first = run(["setup/apply_update.py", f"updates/{package.name}", "--yes"])
    refused = "backup failed" in first.stdout
    check(refused and "[X]" in first.stdout,
          f"it stops at the database backup rather than half-updating (exit {first.returncode})")
    check((PLANT / "VERSION").read_text(encoding="utf-8").strip() == "PT-V4.07",
          "...and the PC is untouched, still on PT-V4.07")
    if not refused:
        print(first.stdout[-1500:])

    print("\n== 2. Repair the updater (one file carried over), then apply the same package")
    check(not (PLANT / "setup" / "bootstrap_update.py").exists(),
          "the old PC has no repair tool of its own - it only arrives in an update")
    shutil.copy2(PROJECT / "Repair_Updater.bat", PLANT / "Repair_Updater.bat")
    boot = subprocess.run(["cmd", "/c", str(PLANT / "Repair_Updater.bat"), f"updates\\{package.name}"],
                          cwd=str(PLANT), capture_output=True, text=True, timeout=300,
                          input="\n", env={**os.environ, "PYTHONIOENCODING": "utf-8",
                                           # this throwaway PC has no venv of its own
                                           "MES_PYTHON": PY})
    check(boot.returncode == 0 and "can accept updates now" in boot.stdout,
          f"Repair_Updater.bat unpacks itself, checks the signature, and repairs the updater (exit {boot.returncode})")
    check("utils.py" in boot.stdout, "...naming utils.py, the file that finds the portable database")
    check((PLANT / "VERSION").read_text(encoding="utf-8").strip() == "PT-V4.07",
          "...without installing the release itself")
    check(any((PLANT / "rollback").glob("updater_*")), "...keeping the files it replaced in rollback\\")
    if boot.returncode != 0:
        print(boot.stdout[-2000:], boot.stderr[-800:])

    # A package whose utils.py was swapped after it was signed - rebuilt
    # properly, not appended to, so the reader really does see the new bytes.
    import zipfile
    tampered = PLANT / "updates" / "tampered.zip"
    with zipfile.ZipFile(PLANT / "updates" / package.name) as src, zipfile.ZipFile(tampered, "w") as dst:
        for item in src.infolist():
            data = src.read(item.filename)
            if item.filename == "files/utils.py":
                data = b"raise SystemExit('malicious')\n"
            dst.writestr(item, data)
    check((PLANT / "setup" / "bootstrap_update.py").is_file(),
          "the repair tool installed itself, so START_HERE option 13 exists from now on")
    bad = run(["setup/bootstrap_update.py", str(tampered)])
    check(bad.returncode != 0 and "checksum" in bad.stdout.lower(),
          f"a package with a swapped-in file is refused by the repair tool too (exit {bad.returncode})")
    tampered.unlink()

    second = run(["setup/apply_update.py", f"updates/{package.name}", "--yes"])
    applied = second.returncode == 0
    check(applied, f"the update now installs on the portable PC (exit {second.returncode})")
    for step in ("Database backup", "Checking it actually runs"):
        check(step in second.stdout and "[X]" not in second.stdout.split(step)[-1][:200],
              f"...{step.lower()} passed")
    check((PLANT / "VERSION").read_text(encoding="utf-8").strip() == manifest["to_version"],
          f"...and the PC reports {manifest['to_version']}")
    check((PLANT / "pgdata").is_dir() and any((PLANT / "backups").glob("*.sql")),
          "...with a real backup of the bundled database taken first")
    if not applied:
        print(second.stdout[-2500:], second.stderr[-800:])

    print("\n== 3. The app restarts itself (portable mode's launcher restarts the database too)")
    port = free_port()
    script = PLANT / "restart_probe.py"
    script.write_text(RESTART_APP.format(plant=str(PLANT), port=port), encoding="utf-8")
    marker = PLANT / "updates" / ".restart-requested"
    marker.unlink(missing_ok=True)
    server = subprocess.Popen([PY, str(script)], cwd=str(PLANT), stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, text=True)
    try:
        import urllib.request
        ready, deadline = False, time.time() + 60
        while time.time() < deadline and not ready:
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=1):
                    ready = True
            except OSError:
                time.sleep(0.5)
        check(ready, "a server is up to restart")
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/restart", timeout=10) as resp:
            body = resp.read().decode()
        check('"supervised"' in body, f"it reports the launcher will restart it (got {body.strip()})")
        exited = server.wait(timeout=45)
        out = server.stdout.read()
        check(exited == 0, f"the server stopped by itself (exit {exited})")
        check("SERVER RETURNED FROM uvicorn.run" in out,
              "...by ending uvicorn cleanly, so portable mode gets to stop its database")
        check(marker.is_file(), "...leaving the marker its launcher loop watches for")
    finally:
        if server.poll() is None:
            server.kill()

    for script_path, label in ((PROJECT / "run_mes_portable.bat", "run_mes_portable.bat"),
                               (PROJECT / "START_HERE.bat", "START_HERE.bat")):
        text = script_path.read_text(encoding="utf-8", errors="replace")
        check(".restart-requested" in text and "goto :" in text,
              f"{label} starts the app in a loop that watches for that marker")

    lan_phase()

    print("\n" + "=" * 66)
    if FAILS:
        print(f"{len(FAILS)} of {CHECKS} PORTABLE UPDATE CHECKS FAILED:")
        for f in FAILS:
            print(f"  - {f}")
    else:
        print(f"ALL {CHECKS} PORTABLE UPDATE CHECKS PASSED")
    print(f"Test PC: {PLANT}")
    sys.stdout.flush()
    os._exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
