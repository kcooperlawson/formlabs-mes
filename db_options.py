"""db_options.py - Where the database is, and how to connect to it.

Lives apart from db_core.py because db_core builds its engine the moment it
is imported, from whatever DB_URL says at that instant. run_gateway.py has to
test a connection before DB_URL is final (on a gateway PC it starts out as
the word "auto"), so it needs these without that side effect.
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# The database api/portable_launcher.py creates inside pgdata\. Kept in step
# with that file's own DB_NAME.
PORTABLE_DB_NAME = "formlabs_mes"


def resolve_database_url(explicit: str | None = None) -> str | None:
    """The database this project should use, or None if there isn't one.

    DB_URL when it names a real one. Otherwise the bundled database in
    pgdata\\, if this is a portable install - which is the case DB_URL can't
    cover, because run_mes_portable.bat ignores DB_URL and the port its
    database listens on is chosen at run time and never written down.

    Before this existed, anything started from a console on a portable PC had
    no database at all: the update's own "does it still boot" check, the
    backup helper, the gateway's --check. The app itself was fine only
    because api/portable_launcher.py had already put the real URL into its
    own environment before importing anything.
    """
    url = (explicit if explicit is not None else os.getenv("DB_URL", "")).strip()
    if url and url.lower() != "auto":
        return url

    pgdata = ROOT / "pgdata"
    if not pgdata.is_dir():
        return None
    try:
        import pgserver
        # Attaches to the running server, or starts it for this caller if the
        # app isn't up. get_uri() names postgres's own admin database; the
        # app's data lives in PORTABLE_DB_NAME beside it.
        uri = pgserver.get_server(str(pgdata)).get_uri()
        return uri.rsplit("/", 1)[0] + f"/{PORTABLE_DB_NAME}"
    except Exception:
        return None


def connect_args_for(url: str) -> dict:
    """connect_args for create_engine.

    These matter when the database is on another PC, which is the normal
    case for a Device Gateway. Without a connect_timeout, a connection
    attempt to a host that silently drops packets waits on the operating
    system's own TCP give-up. Without keepalives, a connection whose far end
    vanished (a firewall forgetting an idle session, the MES PC losing power)
    can wait for a reply that never comes. With both, those turn into an
    ordinary error within about a minute, which the caller can retry.
    """
    try:
        from sqlalchemy.engine import make_url
        if not make_url(url).drivername.startswith("postgresql"):
            return {}
    except Exception:
        return {}
    return {"connect_timeout": 10, "keepalives": 1, "keepalives_idle": 30,
            "keepalives_interval": 10, "keepalives_count": 3}
