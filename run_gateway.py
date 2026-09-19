"""
run_gateway.py - Standalone entrypoint for the Device Gateway.

Run this as its own long-lived process, separate from the main app
(START_HERE.bat, option 3). A continuous background polling loop doesn't belong
inside a request-driven web server - running it there would mean it stops
the moment nobody happens to be hitting the app, and ties its lifetime to
uvicorn's.

Usage:
    python run_gateway.py            start the gateway
    python run_gateway.py --check    test this PC and print a report, then exit

ZERO CONFIGURATION NEEDED to point this at the right database, on any PC:
this always searches the local network first for a formlabsmes database
announcing itself (see service_announcer.py, started automatically by
api/main.py on whichever PC runs the main app) via mDNS, and connects to
whatever it finds. That means the exact same project folder + .env you
zip up on the PC hosting the app can be unzipped onto ANY other PC on the
same network and just work - no file needs editing, because this never
even looks at .env's DB_URL to decide WHERE to connect.

It still needs a username/password to actually log into whatever
database it finds, and gets those from THIS machine's own .env - the
same one you copied over unmodified:
  - the username/password embedded in DB_URL, if that's a real
    connection string (most .env files here already have one, left over
    from whichever PC last acted as the main app host) - OR -
  - PG_PASS (the key the backup/restore tooling already uses) for the
    password, with a username of "postgres" - the default for this app.
Override either explicitly with DB_USER / DB_PASSWORD in .env if a given
machine's Postgres login is genuinely different.

If discovery finds nothing (main app isn't running anywhere on this
network right now, or this network doesn't pass mDNS/multicast traffic
between the two PCs - different VLAN, guest wifi, a managed switch doing
client isolation, etc) this falls back to using DB_URL directly, IF it's
a real connection string rather than the placeholder word "auto" - this
covers running the gateway on the exact same PC that hosts Postgres,
where DB_URL already correctly says "localhost" and there's no reason to
depend on the network working at all.

Advanced escape hatch: set GATEWAY_DB_URL in .env to skip discovery
entirely and always use that exact connection string - useful if a given
floor PC's network genuinely can't do mDNS and you'd rather pin it by
hand than fight the network. On a corporate network, expect to need it:
multicast rarely crosses from one VLAN to another.

Whatever it finds, it logs in once before going any further. If that fails -
the MES PC is still booting, a firewall is in the way, pg_hba.conf doesn't
allow this PC, the password is wrong - it says which of those it is in plain
words and tries again every so often instead of exiting. A floor PC that
boots before the MES PC still ends up connected without anybody touching it.
Once running, a database outage is waited out the same way (see
device_gateway/service.py).

--check runs the same database login, then tests this PC's encryption key,
every registered device's address or COM port, and prints what it found
(device_gateway/field_check.py). Run it on the floor PC before relying on it:
START_HERE.bat, option 12.

Also needs whatever network/USB/COM-port access the machines you
register as Devices require, which is the main reason to run it on a
floor PC near those machines rather than wherever Postgres itself happens
to live.

On Windows, wrap it as a background service (nssm, or a Task Scheduler
job set to "run whether user is logged on or not") so it survives reboots
without a terminal window staying open. On Linux, a systemd unit running
`python run_gateway.py` with Restart=on-failure does the same job.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()


def _credentials_from_existing_env():
    """Pulls a username/password to log into whatever database gets found,
    out of whatever this machine's .env already has - never requires a
    new key to be added. Order: explicit DB_USER/DB_PASSWORD override,
    then whatever's embedded in DB_URL (if it parses as a real URL), then
    PG_PASS + the "postgres" default this app has always used."""
    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASSWORD")
    if user and password:
        return user, password

    existing_url = os.getenv("DB_URL", "").strip()
    parsed_user = parsed_password = None
    if existing_url and existing_url.lower() not in ("auto", ""):
        try:
            from sqlalchemy.engine import make_url
            parsed = make_url(existing_url)
            parsed_user, parsed_password = parsed.username, parsed.password
        except Exception:
            pass

    user = user or parsed_user or "postgres"
    password = password or parsed_password or os.getenv("PG_PASS", "")
    return user, password


def _find_database():
    """Where to connect, as (url, how it was found), or (None, None) with the
    reason already printed. Only finds - _try_connect is what logs in."""
    override = os.getenv("GATEWAY_DB_URL", "").strip()
    if override:
        return override, "GATEWAY_DB_URL in .env, network discovery skipped"

    from app_logger import logger
    from service_discovery import discover

    timeout_s = float(os.getenv("DISCOVERY_TIMEOUT_S", "5"))
    print(f"Searching this network for a formlabsmes database (up to {timeout_s:.0f}s)...")
    logger.info("[run_gateway] searching the local network for the MES database...")

    found = []
    try:
        found = discover(timeout_s=timeout_s)
    except ImportError:
        print("The 'zeroconf' package isn't installed, so auto-discovery can't run "
              "(pip install -r requirements.txt should have covered this).")

    if len(found) > 1:
        print(f"Found {len(found)} different formlabsmes databases on this network - "
              f"refusing to guess which one you mean:")
        for f in found:
            print(f"  - {f['plant']}: {f['host']}:{f['port']}/{f['dbname']}")
        print("Set GATEWAY_DB_URL in this PC's .env to pick one explicitly.")
        sys.exit(1)

    if found:
        from sqlalchemy.engine import URL
        target = found[0]
        user, password = _credentials_from_existing_env()
        # URL.create, not an f-string: a password with an @ or / in it would
        # otherwise be read as part of the host.
        url = URL.create("postgresql", user, password, target["host"], target["port"],
                         target["dbname"]).render_as_string(hide_password=False)
        logger.info(f"[run_gateway] discovered MES database at "
                    f"{target['host']}:{target['port']}/{target['dbname']} "
                    f"(plant={target['plant']!r})")
        return url, f"announced on the network by {target['plant']}"

    # Nothing found on the network - fall back to a literal DB_URL if this
    # machine has a real one (e.g. it's running on the same PC as Postgres,
    # where localhost already works and the network was never involved).
    existing_url = os.getenv("DB_URL", "").strip()
    if existing_url and existing_url.lower() not in ("auto", ""):
        return existing_url, "nothing answered on the network, so this PC's own DB_URL"

    print("Could not find a formlabsmes database announcing itself on this network,")
    print("and this machine's .env has no usable DB_URL to fall back to. Possible reasons:")
    print("  - the MES app isn't running on any PC here right now (START_HERE.bat, option 3)")
    print("  - this PC can't see mDNS/multicast traffic from that PC (different VLAN,")
    print("    a corporate network, guest wifi, a switch doing client isolation). That is")
    print("    normal on corporate networks - point this PC at the MES PC in .env instead:")
    print("      GATEWAY_DB_URL=postgresql://USER:PASSWORD@MES-PC-NAME-OR-IP:5432/formlabs_mes")
    return None, None


def _describe(url: str) -> tuple:
    from sqlalchemy.engine import make_url
    parsed = make_url(url)
    return parsed.host or "localhost", parsed.port or 5432, parsed.database or "", parsed.username or ""


def _masked(url: str) -> str:
    host, port, dbname, user = _describe(url)
    return f"{user}@{host}:{port}/{dbname}"


def _try_connect(url: str):
    """(True, None) or (False, the exception). Opens one connection and
    closes it again; nothing is written."""
    import sqlalchemy as sa
    from sqlalchemy.pool import NullPool

    # Not db_core: importing that builds its engine from DB_URL, which isn't
    # settled yet (it's still "auto" on a gateway PC).
    from db_options import connect_args_for
    engine = sa.create_engine(url, connect_args=connect_args_for(url), poolclass=NullPool)
    try:
        with engine.connect() as conn:
            conn.execute(sa.text("SELECT 1"))
        return True, None
    except Exception as exc:
        return False, exc
    finally:
        engine.dispose()


def _this_pc_ip() -> str:
    try:
        from device_gateway.discovery import local_ip
        return local_ip()
    except Exception:
        return "THIS-PC-IP"


def explain_connection_error(exc: BaseException, url: str) -> list:
    """What went wrong, as lines a person at the floor PC can act on.
    psycopg2's own message names a socket error, not a cause."""
    host, port, dbname, user = _describe(url)
    text = str(getattr(exc, "orig", None) or exc)
    lower = text.lower()
    where = f"{host}:{port}"

    if "no pg_hba.conf entry" in lower:
        return [
            f"The database at {where} is reachable, but PostgreSQL there isn't set up to",
            "accept logins from this PC. On the MES PC, add this line to pg_hba.conf and",
            "restart the PostgreSQL service (services.msc):",
            f"    host  {dbname or 'all'}  {user or 'all'}  {_this_pc_ip()}/32  scram-sha-256",
        ]
    if "password authentication failed" in lower:
        return [
            f"The database at {where} answered, but refused the password for user {user!r}.",
            "Put the same DB_USER / DB_PASSWORD the MES PC uses into this PC's .env.",
        ]
    if "database" in lower and "does not exist" in lower:
        return [f"PostgreSQL at {where} is reachable, but has no database called {dbname!r}."]
    if "could not translate host name" in lower or "unknown host" in lower:
        return [
            f"This PC can't look up the name {host!r}. Use the MES PC's IP address instead",
            "of its name in GATEWAY_DB_URL, or ask IT to fix name lookups between the two PCs.",
        ]
    if "timeout expired" in lower or "timed out" in lower or "10060" in lower:
        return [
            f"Nothing answered from {where} - the traffic is being dropped on the way.",
            "Most often that's Windows Firewall on the MES PC (allow inbound TCP port",
            f"{port} from this PC), or a firewall between the plant and corporate networks.",
            f"Also check that {host} is still the MES PC's address.",
        ]
    if "connection refused" in lower or "10061" in lower:
        if host in ("localhost", "127.0.0.1", "::1"):
            return [
                f"Nothing is listening on {where} on THIS PC. A gateway PC doesn't run the",
                "database - this .env was probably copied from the MES PC. Point it at the",
                "MES PC instead, in this PC's .env:",
                "    GATEWAY_DB_URL=postgresql://USER:PASSWORD@MES-PC-NAME-OR-IP:5432/formlabs_mes",
            ]
        return [
            f"{host} is reachable, but nothing accepted a connection on port {port}.",
            "PostgreSQL isn't running on that PC, is on a different port, or only listens on",
            "localhost (set listen_addresses = '*' in postgresql.conf and restart it).",
        ]
    first = text.strip().splitlines()[0] if text.strip() else type(exc).__name__
    return [f"Could not connect to {where}: {first}"]


def _resolve_db_url(keep_trying: bool = True):
    """Fills os.environ['DB_URL'] before anything else in this process
    imports db_core's engine for real - with a database this PC has already
    logged into. Discovery runs again on every attempt, so an MES PC that
    comes up later, or on a new address, is still found."""
    wait_s, last_reason = 15, None
    while True:
        url, source = _find_database()
        if url:
            ok, exc = _try_connect(url)
            if ok:
                os.environ["DB_URL"] = url
                print(f"Connected to the MES database {_masked(url)} ({source}).")
                return
            reason = explain_connection_error(exc, url)
            if reason != last_reason:
                print(f"Can't log in to {_masked(url)} ({source}):")
                for line in reason:
                    print("  " + line)
            last_reason = reason

        if not keep_trying:
            sys.exit(1)
        print(f"Trying again in {wait_s} s - the gateway starts by itself once this works "
              f"(Ctrl+C to stop).")
        time.sleep(wait_s)
        wait_s = min(wait_s * 2, 120)


if __name__ == "__main__":
    check_only = "--check" in sys.argv[1:]
    try:
        _resolve_db_url(keep_trying=not check_only)
    except KeyboardInterrupt:
        sys.exit(1)

    if check_only:
        from device_gateway.field_check import run_check
        sys.exit(run_check())

    from device_gateway.service import run_forever
    run_forever()
