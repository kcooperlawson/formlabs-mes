"""
run_gateway.py - Standalone entrypoint for the Device Gateway.

Run this as its own long-lived process, separate from the main app
(run_mes_api.bat). A continuous background polling loop doesn't belong
inside a request-driven web server - running it there would mean it stops
the moment nobody happens to be hitting the app, and ties its lifetime to
uvicorn's.

Usage:
    python run_gateway.py

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
hand than fight the network.

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


def _resolve_db_url():
    """Fills os.environ['DB_URL'] before anything else in this process
    imports db_core.py (which reads DB_URL at import time)."""
    override = os.getenv("GATEWAY_DB_URL", "").strip()
    if override:
        os.environ["DB_URL"] = override
        print("Using GATEWAY_DB_URL override from .env - skipping network discovery.")
        return

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
        target = found[0]
        user, password = _credentials_from_existing_env()
        os.environ["DB_URL"] = f"postgresql://{user}:{password}@{target['host']}:{target['port']}/{target['dbname']}"
        print(f"Found it: {target['plant']} at {target['host']}:{target['port']}/{target['dbname']}")
        logger.info(f"[run_gateway] discovered MES database at "
                    f"{target['host']}:{target['port']}/{target['dbname']} "
                    f"(plant={target['plant']!r})")
        return

    # Nothing found on the network - fall back to a literal DB_URL if this
    # machine has a real one (e.g. it's running on the same PC as Postgres,
    # where localhost already works and the network was never involved).
    existing_url = os.getenv("DB_URL", "").strip()
    if existing_url and existing_url.lower() not in ("auto", ""):
        print("Nothing found on the network - falling back to this machine's own "
              "DB_URL (fine if this PC also hosts Postgres itself).")
        return

    print("Could not find a formlabsmes database announcing itself on this network,")
    print("and this machine's .env has no usable DB_URL to fall back to. Possible reasons:")
    print("  - the main app (Home.py) isn't currently running on any PC here")
    print("  - this PC can't see mDNS/multicast traffic from that PC (different")
    print("    VLAN, guest wifi, a managed switch with client isolation, etc.)")
    print("  - that PC's Postgres isn't configured to accept outside connections yet")
    print("    (see README_DEVICE_GATEWAY.md's Auto-discovery section)")
    print("As a fallback, set GATEWAY_DB_URL directly in this PC's .env.")
    sys.exit(1)


_resolve_db_url()

from device_gateway.service import run_forever

if __name__ == "__main__":
    run_forever()
