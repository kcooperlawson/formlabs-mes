"""Lets another PC - a Device Gateway on the floor - reach this PC's bundled
database.

    venv\\Scripts\\python.exe setup\\portable_lan_access.py            (show)
    venv\\Scripts\\python.exe setup\\portable_lan_access.py --enable
    venv\\Scripts\\python.exe setup\\portable_lan_access.py --disable
    (START_HERE.bat, option 15)

The bundled database (pgdata\\, see api/portable_launcher.py) is private by
design: it listens on 127.0.0.1 only, on a port picked fresh at every start,
with no password - which is exactly right for a PC that is the only thing
using it, and useless to a gateway PC that has to write readings into it from
across the plant.

Turning this on changes three things, and writes them into .env so every
later start does the same:

  * a FIXED port (5433 by default), so the address stops moving;
  * a real password on the postgres login, generated here, stored in .env;
  * a pg_hba.conf line allowing that login from the plant's subnet, with
    scram-sha-256 - the same authentication a full PostgreSQL install uses.

The server then also listens on this PC's LAN address. That is plant-network
exposure, not internet exposure, and it is the same trade a normal PostgreSQL
install makes to let a second PC connect at all. Windows Firewall still has
to allow the port inbound - this prints the one command that does it, rather
than changing firewall rules itself.
"""
from __future__ import annotations

import os
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV = ROOT / ".env"
PGDATA = ROOT / "pgdata"
DEFAULT_PORT = 5433

OK, BAD, INFO = "  [ok]", "  [X] ", "      "


def _read_env() -> list:
    return ENV.read_text(encoding="utf-8").splitlines() if ENV.exists() else []


def _get(lines: list, key: str) -> str:
    for line in lines:
        if line.strip().startswith(f"{key}="):
            return line.split("=", 1)[1].strip()
    return ""


def _set(lines: list, key: str, value: str) -> list:
    out, done = [], False
    for line in lines:
        if line.strip().startswith(f"{key}="):
            out.append(f"{key}={value}")
            done = True
        else:
            out.append(line)
    if not done:
        out.append(f"{key}={value}")
    return out


def _write_env(lines: list) -> None:
    ENV.write_text("\n".join(lines).rstrip("\n") + "\n", encoding="utf-8")


def local_ip() -> str:
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "THIS-PC-IP"
    finally:
        s.close()


def subnet_of(ip: str) -> str:
    parts = ip.split(".")
    return f"{'.'.join(parts[:3])}.0/24" if len(parts) == 4 else "192.168.0.0/24"


def set_password_and_hba(password: str, subnet: str) -> None:
    """Applies the password and the pg_hba line to the database itself. Starts
    it if it isn't running - pgserver attaches to a running one."""
    import pgserver
    import psycopg2

    server = pgserver.get_server(str(PGDATA))
    uri = server.get_uri()
    conn = psycopg2.connect(uri)
    try:
        conn.autocommit = True
        with conn.cursor() as cur:
            # Quoted with psycopg2, never formatted into the SQL by hand.
            cur.execute("ALTER ROLE postgres WITH PASSWORD %s", (password,))
    finally:
        conn.close()

    hba = PGDATA / "pg_hba.conf"
    marker = "# formlabs-mes: device gateway access"
    lines = [line for line in hba.read_text(encoding="utf-8").splitlines()
             if marker not in line and not line.strip().startswith("host    all             postgres        " + subnet)]
    lines += [
        marker,
        f"host    all             postgres        {subnet}            scram-sha-256",
    ]
    hba.write_text("\n".join(lines) + "\n", encoding="utf-8")
    pgserver.pg_ctl(["reload"], pgdata=PGDATA)


def enable(port: int, subnet: str | None = None) -> int:
    ip = local_ip()
    subnet = subnet or subnet_of(ip)
    lines = _read_env()
    password = _get(lines, "PORTABLE_DB_PASSWORD") or secrets.token_urlsafe(18)

    lines = _set(lines, "PORTABLE_DB_LAN", "1")
    lines = _set(lines, "PORTABLE_DB_PORT", str(port))
    lines = _set(lines, "PORTABLE_DB_PASSWORD", password)
    _write_env(lines)
    print(OK, f"written to .env: fixed port {port}, a generated password, LAN access on")

    if PGDATA.is_dir():
        try:
            set_password_and_hba(password, subnet)
            print(OK, f"the database now accepts the postgres login from {subnet}")
        except Exception as exc:
            print(BAD + f"could not set that on the database itself ({exc}).")
            print(INFO + "Start the app once (START_HERE.bat, option 3) and run this again.")
            return 1
    else:
        print(INFO + "No database here yet - it will be created with these settings on the")
        print(INFO + "first start (START_HERE.bat, option 3).")

    print()
    print("  Two things left, both outside this app:")
    print()
    print(f"  1. Allow port {port} in from the plant network, once, on THIS PC:")
    print(f'       netsh advfirewall firewall add rule name="Formlabs MES database" '
          f'dir=in action=allow protocol=TCP localport={port} remoteip={subnet}')
    print("     (run that in a Command Prompt opened as Administrator)")
    print()
    print("  2. On the gateway PC, put this one line in its .env:")
    print(f"       GATEWAY_DB_URL=postgresql://postgres:{password}@{ip}:{port}/formlabs_mes")
    print()
    print("  Then check it from that PC with START_HERE.bat, option 12.")
    print("  Restart the app here for the new port to take effect.")
    print()
    return 0


def disable() -> int:
    lines = _set(_read_env(), "PORTABLE_DB_LAN", "0")
    _write_env(lines)
    print(OK, "LAN access switched off in .env - the database goes back to being")
    print(INFO + "private to this PC (127.0.0.1, a fresh port each start) on the next start.")
    print(INFO + "The pg_hba.conf line stays; nothing can reach it to use it.")
    return 0


def show() -> int:
    lines = _read_env()
    on = _get(lines, "PORTABLE_DB_LAN") == "1"
    port = _get(lines, "PORTABLE_DB_PORT") or str(DEFAULT_PORT)
    print()
    if on:
        print(OK, f"Gateway access is ON - the bundled database listens on port {port}")
        print(INFO + f"This PC is {local_ip()}.")
    else:
        print(INFO + "Gateway access is OFF - the bundled database is private to this PC.")
        print(INFO + "Turn it on with:  setup\\portable_lan_access.py --enable")
    print()
    return 0


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    port = DEFAULT_PORT
    if "--port" in argv:
        at = argv.index("--port")
        port = int(argv[at + 1])
        del argv[at:at + 2]
    subnet = None
    if "--subnet" in argv:
        at = argv.index("--subnet")
        subnet = argv[at + 1]
        del argv[at:at + 2]

    if "--enable" in argv:
        return enable(port, subnet)
    if "--disable" in argv:
        return disable()
    return show()


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    raise SystemExit(main())
