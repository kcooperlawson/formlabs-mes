"""
_preflight.py - "why won't it run on this machine?"

Checks every thing that has ever stopped this project starting on a new
PC, in the order they fail, and prints one line each. It changes nothing.

    python setup/_preflight.py                 full report
    python setup/_preflight.py --address-only  just the URL for the phones
"""
import os
import re
import socket
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parent.parent

OK, WARN, BAD = "[ok]", "[! ]", "[X ]"
_problems = []
_warnings = []


def line(state, label, detail=""):
    print(f"  {state} {label}" + (f"  -  {detail}" if detail else ""))
    if state == BAD:
        _problems.append(label)
    elif state == WARN:
        _warnings.append(label)


def head(title):
    print()
    print(f"  {title}")
    print("  " + "-" * (len(title) + 2))


# ------------------------------------------------------------- address

def lan_ip():
    """The address the phones must use. Not 127.0.0.1, and not whatever
    gethostbyname returns on a PC with a VPN or Hyper-V adapter."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))  # no packet is sent; this just picks a route
        return s.getsockname()[0]
    except Exception:
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return ""
    finally:
        s.close()


def print_address():
    ip = lan_ip()
    name = socket.gethostname()
    print("   Operators open this on their phones:")
    if ip:
        print(f"       http://{ip}:8501")
    print(f"       http://{name}:8501")
    if not ip:
        print("   (couldn't work out this PC's network address)")


# -------------------------------------------------------------- checks

def check_python():
    head("Python")
    v = sys.version_info
    txt = f"{v.major}.{v.minor}.{v.micro}"
    if v >= (3, 11):
        line(OK, f"Python {txt}", sys.executable)
    else:
        line(BAD, f"Python {txt} is too old", "needs 3.11 or newer")
    in_venv = sys.prefix != sys.base_prefix
    if in_venv:
        line(OK, "Running inside the project venv")
    else:
        line(WARN, "Not running inside venv\\",
             "the launcher normally uses venv\\Scripts\\python.exe")


def check_packages():
    head("Packages")
    core = ["streamlit", "sqlalchemy", "psycopg2", "alembic", "pandas",
            "dotenv", "bcrypt", "plotly"]
    missing = []
    for mod in core:
        try:
            __import__(mod)
        except Exception:
            missing.append(mod)
    if missing:
        line(BAD, "Missing core packages", ", ".join(missing))
        print("        -> START_HERE.bat, option 1 (or 2 for a gateway PC)")
    else:
        line(OK, "All core packages import")

    extras = {"pymodbus": "Modbus TCP/RTU", "serial": "serial devices",
              "paho.mqtt.client": "MQTT", "opcua": "OPC-UA",
              "zeroconf": "gateway auto-discovery"}
    missing_x = [f"{name} ({why})" for name, why in extras.items()
                 if not _importable(name)]
    if missing_x:
        line(WARN, "Gateway extras missing", "; ".join(missing_x))
    else:
        line(OK, "Gateway extras present")


def _importable(name):
    try:
        __import__(name)
        return True
    except Exception:
        return False


def check_env():
    head(".env")
    env = ROOT / ".env"
    if not env.exists():
        line(BAD, "No .env file", "setup writes one; run option 1 or 2")
        return {}
    text = env.read_text(encoding="utf-8", errors="replace")
    values = {}
    for ln in text.splitlines():
        m = re.match(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)$", ln)
        if m:
            values[m.group(1)] = m.group(2).strip()

    url = values.get("DB_URL", "")
    if not url:
        line(BAD, "DB_URL is not set")
    elif url.lower() == "auto":
        line(OK, "DB_URL=auto", "gateway PC - finds the database on the network")
    elif re.search(r"://(USER|CHANGEME)?:?(PASSWORD|YOURPASSWORD|CHANGEME)?@", url):
        line(BAD, "DB_URL still has the example placeholders in it",
             "this is the usual reason a fresh copy won't start")
    else:
        safe = re.sub(r"://([^:]*):[^@]*@", r"://\1:***@", url)
        line(OK, "DB_URL set", safe)

    pg_bin = values.get("PG_BIN_DIR", "")
    if url.lower() == "auto":
        pass
    elif not pg_bin:
        line(WARN, "PG_BIN_DIR empty", "backup and restore will not work")
    elif not (Path(pg_bin) / "pg_dump.exe").exists():
        line(WARN, "PG_BIN_DIR points somewhere with no pg_dump.exe", pg_bin)
    else:
        line(OK, "PG_BIN_DIR", pg_bin)
    return values


def check_database(values):
    head("Database")
    url = values.get("DB_URL", "")
    if url.lower() == "auto":
        line(OK, "Skipped", "this PC is a gateway; it discovers the database")
        return
    if not url:
        line(BAD, "Nothing to test", "DB_URL is not set")
        return
    try:
        import psycopg2
    except ImportError:
        line(WARN, "Can't test", "psycopg2 isn't installed yet")
        return

    m = re.match(r"^postgres(?:ql)?://([^:/@]*):?([^@]*)@([^:/]+):?(\d*)/(.*)$", url)
    if not m:
        line(BAD, "DB_URL isn't a valid PostgreSQL URL")
        return
    user, password, host, port, dbname = m.groups()
    user, password = unquote(user), unquote(password)
    port = int(port or 5432)

    try:
        conn = psycopg2.connect(user=user, password=password, host=host,
                                port=port, dbname="postgres", connect_timeout=6)
        conn.close()
        line(OK, f"PostgreSQL is reachable at {host}:{port}")
    except Exception as exc:
        msg = str(exc).strip().splitlines()[0]
        line(BAD, "Cannot reach PostgreSQL", msg)
        low = msg.lower()
        if "password authentication failed" in low:
            print("        -> Wrong password in .env. Re-run option 1; it asks")
            print("           for it and tests it before writing.")
        elif "could not connect" in low or "refused" in low or "timeout" in low:
            print("        -> The service isn't running. Win+R, services.msc,")
            print("           start postgresql-x64-...")
        return

    try:
        conn = psycopg2.connect(user=user, password=password, host=host,
                                port=port, dbname=dbname, connect_timeout=6)
        cur = conn.cursor()
        cur.execute("select count(*) from information_schema.tables "
                    "where table_schema='public'")
        n = cur.fetchone()[0]
        conn.close()
        if n:
            line(OK, f"Database '{dbname}' exists", f"{n} tables")
        else:
            line(WARN, f"Database '{dbname}' exists but is empty",
                 "the app builds its schema on first start")
    except Exception:
        line(WARN, f"Database '{dbname}' doesn't exist yet",
             "setup creates it")


def check_port():
    head("Network")
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(1.5)
    busy = s.connect_ex(("127.0.0.1", 8501)) == 0
    s.close()
    if busy:
        line(WARN, "Port 8501 is already in use",
             "the app may already be running in another window")
    else:
        line(OK, "Port 8501 is free")

    ip = lan_ip()
    if ip:
        line(OK, "This PC's address on the network", ip)
    else:
        line(WARN, "Couldn't determine this PC's network address")

    if os.name == "nt":
        try:
            out = subprocess.run(
                ["netsh", "advfirewall", "show", "currentprofile"],
                capture_output=True, text=True, timeout=10).stdout
            if re.search(r"State\s+ON", out, re.IGNORECASE):
                line(WARN, "Windows Firewall is on",
                     "phones can't reach 8501 until it's allowed through")
                print("        -> Run once, as administrator:")
                print('           netsh advfirewall firewall add rule '
                      'name="Formlabs MES" dir=in action=allow '
                      'protocol=TCP localport=8501')
            else:
                line(OK, "Windows Firewall is off on this profile")
        except Exception:
            line(WARN, "Couldn't read the firewall state")


def check_files():
    head("Project files")
    for rel in ["Home.py", "crud.py", "requirements.txt", "migrations",
                ".streamlit/config.toml"]:
        p = ROOT / rel
        line(OK if p.exists() else BAD, rel,
             "" if p.exists() else "missing - unzip the whole package")


def main():
    if "--address-only" in sys.argv:
        print_address()
        return 0

    print()
    print("  ===================================================")
    print(f"   PREFLIGHT  -  {socket.gethostname()}")
    print("  ===================================================")
    check_files()
    check_python()
    check_packages()
    values = check_env()
    check_database(values)
    check_port()

    print()
    print("  ===================================================")
    if _problems:
        print(f"   {len(_problems)} thing(s) will stop it running:")
        for p in _problems:
            print(f"     - {p}")
    else:
        print("   Nothing is blocking it. It should start.")
    if _warnings:
        print(f"   {len(_warnings)} warning(s) - it runs, but check these:")
        for w in _warnings:
            print(f"     - {w}")
    print("  ===================================================")
    print()
    print_address()
    return 1 if _problems else 0


if __name__ == "__main__":
    sys.exit(main())
