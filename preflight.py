"""Is this PC ready to run the plant, and if not, exactly what is wrong.

Written for the two moments where a mistake costs a morning: carrying a
laptop onto the floor, and standing up the permanent machine afterwards. The
alternative to this script is finding out that Postgres is not running, or
that the phones cannot reach port 8501, at the moment an operator is standing
at a pump holding a cartridge.

Every check answers one question and, when the answer is bad, says what to
type to fix it. A check that only reports a problem leaves somebody to search
for the remedy at the worst possible time.

The checks are split in two on purpose. Gathering facts touches the machine -
sockets, subprocesses, the database - and cannot be tested anywhere but on a
real PC. Judging those facts is arithmetic and string comparison, and lives
in the `judge_*` functions below, which take plain values and return a
verdict. That is the half where the reasoning errors hide, and it is checked
in tests/test_preflight.py without a Postgres, a network or Windows.

    python preflight.py           run everything, print a report
    python preflight.py --quick   skip the test backup (the slow one)

Exit code 0 if the PC is ready, 1 if anything failed. Warnings do not fail:
a warning is something to know about, not something that stops the plant.
"""
from __future__ import annotations

import os

# Before anything imports Streamlit. The app's own modules pull it in, and it
# then logs "missing ScriptRunContext" for every call made outside a page -
# which is every call made here, and which buries the report under noise.
# Streamlit reads its log level from the environment at import time, so this
# has to be set before that happens rather than afterwards.
os.environ.setdefault("STREAMLIT_LOGGER_LEVEL", "error")

import socket  # noqa: E402
import subprocess  # noqa: E402
import sys  # noqa: E402

OK, WARN, FAIL, INFO = "ok", "warn", "fail", "info"

MIN_PYTHON = (3, 11)
APP_PORT = 8501
FIREWALL_RULE_NAME = "Formlabs MES"


def check(name, state, detail, fix="") -> dict:
    return {"name": name, "state": state, "detail": detail, "fix": fix}


# ---------------------------------------------------------------------------
# The judgements. Plain values in, a verdict out - no machine, no database.
# ---------------------------------------------------------------------------

def judge_python(version_info, in_venv: bool) -> dict:
    version = ".".join(str(n) for n in version_info[:3])
    if version_info[:2] < MIN_PYTHON:
        need = ".".join(str(n) for n in MIN_PYTHON)
        return check("Python", FAIL, f"Python {version} is too old (need {need}+).",
                     "Install Python 3.11 or newer from python.org, ticking "
                     "\"Add python.exe to PATH\", then run Setup_On_New_PC.bat again.")
    if not in_venv:
        # Not fatal - the checks below still tell the truth about this machine -
        # but it means the dependencies being checked are the system's, not the
        # ones the launcher will actually use.
        return check("Python", WARN, f"Python {version}, but not the project's venv.",
                     "Run this through Check_This_PC.bat, which activates venv\\ first. "
                     "Otherwise you are testing a different set of packages than "
                     "run_mes.bat will use.")
    return check("Python", OK, f"Python {version}, in the project venv.")


def judge_dependencies(missing) -> dict:
    if missing:
        return check("Dependencies", FAIL,
                     f"{len(missing)} package(s) missing: {', '.join(sorted(missing))}.",
                     "Run Setup_On_New_PC.bat - it installs everything into venv\\. "
                     "If it already ran, it failed partway; look for red text in its output.")
    return check("Dependencies", OK, "Every package the app imports is installed.")


def judge_database(reachable: bool, dbname: str, error: str = "") -> dict:
    if not reachable:
        return check("Database", FAIL, f"Cannot reach Postgres. {error}".strip(),
                     "Check the Postgres service is running (services.msc, look for "
                     "postgresql-x64-...), and that DB_URL in .env has this PC's own "
                     "password. Nothing else on this list can pass until this does.")
    return check("Database", OK, f"Connected to \"{dbname}\".")


def judge_schema(current, head) -> dict:
    if not head:
        return check("Schema", WARN, "Could not work out the expected schema version.")
    if not current:
        return check("Schema", FAIL, "The database has no schema version stamped on it.",
                     "Run Setup_On_New_PC.bat, which builds the schema. A database "
                     "restored from an older PC gets brought forward automatically.")
    if current != head:
        return check("Schema", FAIL,
                     f"The database is at {current}; this copy of the app expects {head}.",
                     "Start the app once (run_mes.bat) - it applies the missing "
                     "migrations on boot - then run this check again.")
    return check("Schema", OK, f"Up to date ({current}).")


def judge_pg_tools(found: bool, client_version, server_version) -> dict:
    """pg_dump older than the server it is dumping cannot read it.

    This is the trap that ruins the move: the restore fails partway through
    with a message about an "invalid command \\N" that says nothing about
    versions, and by then the target database is half written.
    """
    if not found:
        return check("Backup tools", FAIL, "pg_dump and psql are not on the PATH.",
                     "They ship with PostgreSQL. Add its bin folder to PATH - "
                     "usually C:\\Program Files\\PostgreSQL\\<version>\\bin - or reinstall "
                     "PostgreSQL with the command line tools ticked. "
                     "Without these there are no backups and no move.")
    if client_version and server_version and client_version < server_version:
        return check("Backup tools", FAIL,
                     f"pg_dump is version {client_version[0]} but the server is "
                     f"{server_version[0]}. It cannot read this database.",
                     "Install a PostgreSQL at least as new as the server, or put its "
                     "bin folder ahead of the old one on PATH.")
    shown = f"version {client_version[0]}" if client_version else "present"
    return check("Backup tools", OK, f"pg_dump and psql found, {shown}.")


def judge_backup(filename, size_bytes, error: str = "") -> dict:
    if not filename:
        return check("Test backup", FAIL, f"A backup could not be taken. {error}".strip(),
                     "This is the check worth caring about most: it proves a backup "
                     "will work on the day you need one, rather than assuming. "
                     "Fix the tools or the credentials above first.")
    mb = size_bytes / (1024 * 1024) if size_bytes else 0
    return check("Test backup", OK,
                 f"Took a real backup ({filename}, {mb:.1f} MB). Backups work on this PC.")


def judge_port(free: bool, ours: bool) -> dict:
    if ours:
        return check("Port 8501", OK, "The app is already running on this PC.")
    if not free:
        return check("Port 8501", FAIL, "Something else on this PC is using port 8501.",
                     "Close whatever it is, or find it with: netstat -ano | findstr :8501")
    return check("Port 8501", OK, "Free for the app to use.")


def judge_firewall(is_windows: bool, rule_found, listening_ok=None) -> dict:
    """Whether the phones will actually be able to reach this machine.

    Nothing in the application can detect this: a blocked request never
    arrives, so there is nothing to log and nothing to show. The app prints a
    confident network address, and the handsets time out with no explanation
    anywhere. Windows usually asks once, the first time Python opens a
    listening socket - but that prompt is routinely suppressed by policy on a
    work laptop, or appears behind the console window and gets dismissed.
    """
    if not is_windows:
        return check("Firewall", INFO, "Not Windows - nothing checked.")
    if rule_found is None:
        return check("Firewall", WARN,
                     "Could not tell whether inbound port 8501 is allowed.",
                     f'If the phones cannot reach this PC, run this in an '
                     f'Administrator command prompt:\n'
                     f'       netsh advfirewall firewall add rule '
                     f'name="{FIREWALL_RULE_NAME}" dir=in action=allow '
                     f'protocol=TCP localport={APP_PORT}')
    if not rule_found:
        return check("Firewall", WARN,
                     "No rule allowing inbound port 8501. The phones may time out "
                     "with nothing to explain why.",
                     f'In an Administrator command prompt:\n'
                     f'       netsh advfirewall firewall add rule '
                     f'name="{FIREWALL_RULE_NAME}" dir=in action=allow '
                     f'protocol=TCP localport={APP_PORT}')
    return check("Firewall", OK, "Inbound port 8501 is allowed.")


def judge_addresses(hostname, ips) -> dict:
    """What to give the operators, and which one survives a reconnect.

    A laptop's address changes when it rejoins the network. Bookmark the
    number on six handsets and they all break the next morning, which looks
    exactly like the application breaking. The machine name normally keeps
    working, so it is the one to write on the card.
    """
    if not ips and not hostname:
        return check("Address for the phones", WARN,
                     "This PC does not appear to be on a network.")
    lines = []
    if hostname:
        lines.append(f"http://{hostname}:{APP_PORT}      <- bookmark this one")
    for ip in ips:
        lines.append(f"http://{ip}:{APP_PORT}")
    detail = "\n       ".join(lines)
    fix = ("The name keeps working after the machine rejoins the network; the "
           "number does not. On a laptop that matters - put the name on the "
           "phones. If the name will not resolve on this network, use the "
           "number and re-check it after each reconnect.")
    return check("Address for the phones", INFO, detail, fix)


def judge_disk(free_bytes) -> dict:
    if free_bytes is None:
        return check("Disk space", WARN, "Could not read the free space on this drive.")
    gb = free_bytes / (1024 ** 3)
    if gb < 1:
        return check("Disk space", FAIL, f"{gb:.1f} GB free.",
                     "Backups and photo audits both write to this drive. Free some "
                     "space before running the plant on it.")
    if gb < 5:
        return check("Disk space", WARN, f"{gb:.1f} GB free - enough, but not much.")
    return check("Disk space", OK, f"{gb:.0f} GB free.")


def judge_clock(machine_tz, plant_tz) -> dict:
    """The app decides what shift is running in the plant's zone, always.

    A machine set to another zone is not broken - the conversion handles it -
    but it is worth saying out loud, because a manager comparing a screen
    against a wall clock will otherwise think the shift detection is wrong.
    """
    if machine_tz and plant_tz and machine_tz != plant_tz:
        return check("Clock", WARN,
                     f"This PC is set to {machine_tz}; the plant is {plant_tz}.",
                     "Shift times are worked out in the plant's zone regardless, so "
                     "this is not a fault - but times shown on this machine's own "
                     "clock will not match the app's.")
    return check("Clock", OK, f"This PC and the plant are both {plant_tz}.")


def exit_code(checks) -> int:
    return 1 if any(c["state"] == FAIL for c in checks) else 0


def report(checks) -> str:
    """The printed page. One line per check, with the remedy under a bad one."""
    mark = {OK: "  OK  ", WARN: " WARN ", FAIL: " FAIL ", INFO: "      "}
    width = max(len(c["name"]) for c in checks) + 2
    out = []
    for c in checks:
        first, *rest = str(c["detail"]).split("\n")
        out.append(f"[{mark[c['state']]}] {c['name']:<{width}} {first}")
        for line in rest:
            out.append(f"{'':<{width + 10}}{line.strip()}")
        if c["fix"] and c["state"] in (WARN, FAIL, INFO):
            for line in c["fix"].split("\n"):
                out.append(f"{'':<{width + 10}}{line.strip()}")
    fails = sum(1 for c in checks if c["state"] == FAIL)
    warns = sum(1 for c in checks if c["state"] == WARN)
    out.append("")
    if fails:
        out.append(f"NOT READY - {fails} thing(s) must be fixed. "
                   f"Each one above says what to do.")
    elif warns:
        out.append(f"READY, with {warns} thing(s) worth knowing about.")
    else:
        out.append("READY. This PC can run the plant.")
    return "\n".join(out)


# ---------------------------------------------------------------------------
# Gathering. Everything below touches the machine.
# ---------------------------------------------------------------------------

def _in_venv() -> bool:
    return sys.prefix != getattr(sys, "base_prefix", sys.prefix)


def _missing_dependencies():
    """Which of the app's packages will not import.

    stderr is muted for the duration. Streamlit narrates "missing
    ScriptRunContext" while these load, from a handler it installs partway
    through, which is why filtering it afterwards catches only some of it -
    and a page of that above the report is the difference between somebody
    reading this and somebody skimming it. Nothing is lost by muting: a
    package that will not import raises, and the exception is caught below.
    """
    import contextlib
    needed = ["streamlit", "sqlalchemy", "psycopg2", "pandas", "bcrypt", "alembic",
              "dotenv", "extra_streamlit_components", "PIL", "plotly"]
    missing = []
    with open(os.devnull, "w") as devnull, contextlib.redirect_stderr(devnull):
        for mod in needed:
            try:
                __import__(mod)
            except Exception:
                missing.append(mod)
    return missing


def _database_facts():
    try:
        from sqlalchemy import text
        from db_core import engine
        from utils import _get_db_connection_params
        params = _get_db_connection_params() or {}
        with engine.connect() as conn:
            server = conn.execute(text("SHOW server_version")).scalar()
        return True, params.get("dbname", "?"), server, ""
    except Exception as e:
        return False, "?", None, str(e).splitlines()[0][:160]


def _schema_facts():
    try:
        import pathlib
        import re
        from sqlalchemy import text
        from db_core import engine
        with engine.connect() as conn:
            current = conn.execute(
                text("SELECT version_num FROM alembic_version")).scalar()
    except Exception:
        current = None
    # Head is whichever revision no other file names as its down_revision -
    # derived rather than written down, so adding a migration cannot leave a
    # stale literal behind here.
    try:
        import pathlib
        import re
        folder = pathlib.Path(__file__).parent / "migrations" / "versions"
        revs, downs = set(), set()
        for f in folder.glob("*.py"):
            body = f.read_text()
            m = re.search(r"^revision\s*=\s*[\"']([^\"']+)", body, re.M)
            d = re.search(r"^down_revision\s*=\s*[\"']([^\"']+)", body, re.M)
            if m:
                revs.add(m.group(1))
            if d:
                downs.add(d.group(1))
        heads = revs - downs
        head = heads.pop() if len(heads) == 1 else None
    except Exception:
        head = None
    return current, head


def _pg_tool_facts():
    from utils import _get_pg_bin
    try:
        out = subprocess.run([_get_pg_bin("pg_dump"), "--version"],
                             capture_output=True, text=True, timeout=20)
        if out.returncode != 0:
            return False, None
        import re
        m = re.search(r"(\d+)(?:\.(\d+))?", out.stdout)
        version = (int(m.group(1)), int(m.group(2) or 0)) if m else None
        return True, version
    except Exception:
        return False, None


def _port_facts(port=APP_PORT):
    """Free, and whether whatever holds it answers as our own app."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.6)
    in_use = s.connect_ex(("127.0.0.1", port)) == 0
    s.close()
    if not in_use:
        return True, False
    try:
        import urllib.request
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/_stcore/health",
                                    timeout=2) as r:
            return False, r.status == 200
    except Exception:
        return False, False


def _firewall_facts():
    if os.name != "nt":
        return None
    try:
        out = subprocess.run(
            ["netsh", "advfirewall", "firewall", "show", "rule",
             f"name={FIREWALL_RULE_NAME}"],
            capture_output=True, text=True, timeout=20)
        if "No rules match" in out.stdout or out.returncode != 0:
            # A rule under our own name is the tidy case. Windows also creates
            # one automatically the first time it prompts, named after python
            # itself, so a missing named rule is a warning rather than a
            # failure - the phones may well work anyway.
            probe = subprocess.run(
                ["netsh", "advfirewall", "firewall", "show", "rule",
                 "name=all", "dir=in"], capture_output=True, text=True, timeout=40)
            return f"{APP_PORT}" in probe.stdout and "python" in probe.stdout.lower()
        return True
    except Exception:
        return None


def _address_facts():
    hostname = ""
    ips = []
    try:
        hostname = socket.gethostname()
    except Exception:
        pass
    try:
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            ip = info[4][0]
            if not ip.startswith("127.") and ip not in ips:
                ips.append(ip)
    except Exception:
        pass
    if not ips:
        # The reliable trick when the hostname does not resolve: ask the OS
        # which interface it would use to reach the outside world. No packet
        # is actually sent.
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ips = [s.getsockname()[0]]
            s.close()
        except Exception:
            pass
    return hostname, ips


def _disk_facts():
    try:
        import shutil
        return shutil.disk_usage(os.path.dirname(os.path.abspath(__file__))).free
    except Exception:
        return None


def _clock_facts():
    try:
        from datetime import datetime
        from shift_clock import PLANT_TZ
        machine = datetime.now().astimezone().tzname()
        plant = datetime.now(PLANT_TZ).tzname()
        return machine, plant
    except Exception:
        return None, None


def _quieten_streamlit():
    """Stop Streamlit narrating that it is not inside a page.

    Importing the app's modules pulls Streamlit in, and it then logs "missing
    ScriptRunContext" for every call made outside a page - which is every call
    made here. It configures its own logging on import, so the level has to be
    set afterwards; setting it beforehand, or through the environment, is
    overwritten.
    """
    import logging

    class _NoBareModeChatter(logging.Filter):
        def filter(self, record):
            return "ScriptRunContext" not in record.getMessage()

    # The filter goes on the handler rather than on the loggers, because the
    # loggers that emit this are created lazily - one per module, as each is
    # first used - so setting levels only silences the ones that happen to
    # exist at this moment. Everything propagates up to Streamlit's own
    # handler, so that is the one place that catches all of them.
    root = logging.getLogger("streamlit")
    root.setLevel(logging.ERROR)
    for handler in root.handlers or logging.getLogger().handlers:
        handler.addFilter(_NoBareModeChatter())


def run_all(quick: bool = False):
    checks = [judge_python(sys.version_info, _in_venv())]

    # Streamlit has to be in before it can be quietened, and it has to be
    # quietened before anything that touches it - extra_streamlit_components
    # registers components at import time and each one narrates itself.
    try:
        import streamlit  # noqa: F401
        _quieten_streamlit()
    except Exception:
        pass

    missing = _missing_dependencies()
    # Again: Streamlit installs its handler lazily, so the sweep above catches
    # what existed then and this catches what importing the rest created.
    _quieten_streamlit()
    checks.append(judge_dependencies(missing))
    if missing:
        # Nothing below can run without them, and a wall of import errors
        # hides the one line that matters.
        checks.append(check("Everything else", INFO,
                            "Skipped until the packages above are installed."))
        return checks

    reachable, dbname, server_version, error = _database_facts()
    checks.append(judge_database(reachable, dbname, error))

    if reachable:
        current, head = _schema_facts()
        checks.append(judge_schema(current, head))

    found, client_version = _pg_tool_facts()
    server_major = None
    if server_version:
        try:
            server_major = (int(str(server_version).split(".")[0]), 0)
        except (ValueError, IndexError):
            server_major = None
    checks.append(judge_pg_tools(found, client_version, server_major))

    if reachable and found and not quick:
        from utils import BACKUP_DIR, create_database_backup, prune_old_backups
        filename = create_database_backup()
        size = None
        if filename:
            try:
                size = os.path.getsize(os.path.join(BACKUP_DIR, filename))
            except OSError:
                size = None
            prune_old_backups()
        checks.append(judge_backup(filename, size,
                                   "" if filename else "See logs\\ for the pg_dump error."))

    free, ours = _port_facts()
    checks.append(judge_port(free, ours))
    checks.append(judge_firewall(os.name == "nt", _firewall_facts()))
    checks.append(judge_disk(_disk_facts()))
    machine_tz, plant_tz = _clock_facts()
    checks.append(judge_clock(machine_tz, plant_tz))
    hostname, ips = _address_facts()
    checks.append(judge_addresses(hostname, ips))
    return checks


if __name__ == "__main__":
    print("=" * 70)
    print(" Formlabs MES - is this PC ready?")
    print("=" * 70)
    print()
    results = run_all(quick="--quick" in sys.argv)
    print(report(results))
    print()
    sys.exit(exit_code(results))
