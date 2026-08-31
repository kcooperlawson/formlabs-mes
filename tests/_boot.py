"""Point the app's real modules at a THROWAWAY database, never production.

Two ways to get one, in order:
  1. TEST_DB_URL in the environment - an empty scratch database on any
     Postgres you already have. On Windows this is the path that works.
  2. pgserver (pip install pgserver) - spins up a private PostgreSQL under
     ~/pgdata with no install and no root. Linux/macOS.

Whichever it uses, it refuses to run against the DB_URL in your .env, so a
test run can never touch real production data.
"""
import os
import sys
import pathlib
import warnings

warnings.filterwarnings("ignore")

ROOT = pathlib.Path(__file__).resolve().parent.parent
os.chdir(ROOT)                      # pages/ and assets/ are resolved relative to here
sys.path.insert(0, str(ROOT))

TEST_DB_NAME = "formlabs_test"


def _production_url():
    try:
        for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("DB_URL="):
                return line.split("=", 1)[1].strip()
    except OSError:
        pass
    return None


def boot(fresh=True):
    """Return (server_or_None, uri) with os.environ['DB_URL'] pointed at it."""
    prod = _production_url()

    uri = os.environ.get("TEST_DB_URL")
    srv = None
    if uri:
        if fresh:
            import sqlalchemy as sa
            eng = sa.create_engine(uri)
            with eng.connect() as c:                 # wipe, don't drop: the URL is given to us
                c.execute(sa.text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
                c.commit()
            eng.dispose()
    else:
        import pgserver
        pgdata = str(pathlib.Path.home() / "pgdata")
        srv = pgserver.get_server(pgdata, cleanup_mode=None)
        if fresh:
            # WITH (FORCE) so a connection left open by an earlier test run
            # can't block the drop; fall back for older servers.
            try:
                srv.psql(f"DROP DATABASE IF EXISTS {TEST_DB_NAME} WITH (FORCE);")
            except Exception:
                srv.psql("SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                         f"WHERE datname = '{TEST_DB_NAME}';")
                srv.psql(f"DROP DATABASE IF EXISTS {TEST_DB_NAME};")
            srv.psql(f"CREATE DATABASE {TEST_DB_NAME};")
        uri = f"postgresql+psycopg2://postgres@/{TEST_DB_NAME}?host={pgdata}"

    if prod and uri and prod.strip() == uri.strip():
        raise SystemExit("REFUSING TO RUN: the test URL is your production DB_URL.")

    os.environ["DB_URL"] = uri
    return srv, uri
