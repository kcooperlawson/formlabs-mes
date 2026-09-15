"""Runs the FastAPI app against a private, bundled PostgreSQL instead of a
system-wide install - see requirements.txt's pgserver note for why: a work
PC that can't reach winget or PyPI, or where nobody has admin rights to run
an installer, still needs nothing more than what Move_To_New_PC.bat already
carries across.

One process, not a database process plus an app process: this script starts
the embedded server, points DB_URL at it, and only THEN imports the app -
crud.py's own module-level init_db()/seed_initial_data() calls handle the
schema and the default accounts the moment they're imported, exactly the
same self-healing boot every other launcher already relies on. Doing this
in one process sidesteps having to hand a dynamically-chosen port between
two separate processes; a real system PostgreSQL is always on a fixed port,
but pgserver picks a free one fresh each run.

The data lives in pgdata/ next to this project - not the caller's home
directory - so the whole folder (project + its database) is what moves
between machines, same as the rest of this app's "the folder IS the
install" philosophy (see run_mes.bat/run_mes_api.bat's own venv-relative
launching). Entry point for run_mes_portable.bat; never imported by the
normal api.main boot path, so a PC with a real PostgreSQL install running
against .env's DB_URL is completely unaffected by this file existing.
"""
import os
import pathlib
import sys

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
DB_NAME = "formlabs_mes"

_pg_server = None  # kept alive for the life of this process; see main()'s finally


def _start_embedded_postgres() -> str:
    import pgserver

    pgdata = BASE_DIR / "pgdata"
    first_run = not pgdata.exists()
    if first_run:
        print(f"      First run - creating a private database at {pgdata}")
        print("      (this takes a few seconds, only on this very first launch)")

    global _pg_server
    _pg_server = pgserver.get_server(str(pgdata))
    return _pg_server.get_uri()  # postgresql://postgres:@127.0.0.1:<port>/postgres


def _ensure_database(admin_uri: str, name: str) -> str:
    """Same check-then-create pattern as _migration_helper.py's own
    cmd_ensure_db(), just against pgserver's own dynamically-chosen
    connection instead of .env's DB_URL."""
    import psycopg2

    conn = psycopg2.connect(admin_uri)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (name,))
            if cur.fetchone() is None:
                cur.execute(f'CREATE DATABASE "{name}"')
    finally:
        conn.close()
    return admin_uri.rsplit("/", 1)[0] + f"/{name}"


def main() -> None:
    print("=" * 70)
    print(" Formlabs MES - Portable Mode (bundled database, no install needed)")
    print("=" * 70)

    dist_index = BASE_DIR / "frontend" / "dist" / "index.html"
    if not dist_index.exists():
        print("[ERROR] frontend\\dist\\index.html is missing.")
        print("        This copy wasn't built with the frontend included.")
        sys.exit(1)

    print("[1/3] Starting the bundled database...")
    admin_uri = _start_embedded_postgres()
    db_url = _ensure_database(admin_uri, DB_NAME)
    os.environ["DB_URL"] = db_url
    print(f"      Ready ({db_url.rsplit('@', 1)[-1]}).")

    print("[2/3] Bringing the schema up to date...")
    sys.path.insert(0, str(BASE_DIR))
    import crud  # noqa: E402  (its own module-level code runs init_db() + seed_initial_data())
    print("      Ready.")

    print("[3/3] Starting the server...")
    ssl_certfile = BASE_DIR / "certs" / "mes.crt"
    ssl_keyfile = BASE_DIR / "certs" / "mes.key"
    ssl_kwargs = {}
    if ssl_certfile.exists() and ssl_keyfile.exists():
        ssl_kwargs = {"ssl_certfile": str(ssl_certfile), "ssl_keyfile": str(ssl_keyfile)}
    else:
        print("      [!] No HTTPS certificate found (certs\\mes.crt/mes.key) - plain HTTP.")
        print("          Run setup\\generate_tls_cert.py once to add one.")

    # setup/_preflight.py already works out the LAN IP/hostname and prints
    # the address the phones should use - reused here rather than
    # duplicated, same address logic Check_This_PC.bat prints.
    sys.path.insert(0, str(BASE_DIR / "setup"))
    import _preflight  # noqa: E402
    print()
    _preflight.print_address()
    print()

    from api.main import app
    import uvicorn

    try:
        uvicorn.run(app, host="0.0.0.0", port=8000, **ssl_kwargs)
    finally:
        # Deterministic shutdown of the embedded server rather than leaving
        # it to whenever the interpreter happens to garbage-collect the
        # module-level reference - Ctrl+C ends uvicorn.run() and this runs
        # immediately after, on the same clean-exit path every time.
        if _pg_server is not None:
            print("Stopping the bundled database...")
            _pg_server.cleanup()


if __name__ == "__main__":
    main()
