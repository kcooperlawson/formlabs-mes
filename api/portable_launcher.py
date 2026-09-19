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
install" philosophy (see START_HERE.bat's own venv-relative launching).
Entry point for run_mes_portable.bat; never imported by the
normal api.main boot path, so a PC with a real PostgreSQL install running
against .env's DB_URL is completely unaffected by this file existing.
"""
import os
import pathlib
import sys
import threading

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
DB_NAME = "formlabs_mes"

_pg_server = None  # kept alive for the life of this process; see main()'s finally


def _tail_log_while(pgdata: "pathlib.Path", stop: threading.Event) -> None:
    """Echoes new lines from postgres's own log to this console while a slow
    startup is in progress. Recovering from an unclean shutdown (the window
    was closed instead of stopped with Ctrl+C, or Windows/antivirus was
    still holding a file handle) can take the better part of a minute with
    nothing else printed in that window - indistinguishable from a hang
    unless something moves. This is read-only and never touches postgres
    itself; worst case (the file briefly locked by the server writing to
    it) it just misses a line rather than erroring."""
    log_path = pgdata / "log"
    pos = log_path.stat().st_size if log_path.exists() else 0
    while not stop.wait(0.5):
        try:
            if not log_path.exists():
                continue
            with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                f.seek(pos)
                for line in f:
                    print(f"      | {line.rstrip()}")
                pos = f.tell()
        except OSError:
            pass


def _await_postgres_ready(pgdata: "pathlib.Path", PostmasterInfo, seconds: int) -> bool:
    import time

    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        info = PostmasterInfo.read_from_pgdata(pgdata)
        if info is not None and info.is_running() and info.status == "ready":
            return True
        time.sleep(1)
    return False


def _start_embedded_postgres() -> tuple[str, bool]:
    import pgserver
    from pgserver.postgres_server import PostmasterInfo

    pgdata = BASE_DIR / "pgdata"
    first_run = not pgdata.exists()
    if first_run:
        print(f"      First run - creating a private database at {pgdata}")
        print("      (this takes a few seconds, only on this very first launch)")
    else:
        stale = PostmasterInfo.read_from_pgdata(pgdata)
        if stale is not None and not stale.is_running():
            # Exactly what's left behind when the last run ended by closing
            # the window instead of Ctrl+C, a crash, or a forced shutdown -
            # postgres itself recovers automatically, but that recovery is
            # silent by default and has run past 30+ seconds on a real
            # machine before now, reading as "it's frozen, kill it" to
            # someone watching a still console. It is not frozen; closing it
            # here is what produces the NEXT slow recovery.
            print("      Last shutdown wasn't clean - running automatic recovery.")
            print("      This can take up to a minute. Do not close this window.")

    stop = threading.Event()
    tail = threading.Thread(target=_tail_log_while, args=(pgdata, stop), daemon=True)
    tail.start()
    try:
        global _pg_server
        try:
            _pg_server = pgserver.get_server(str(pgdata))
        except Exception as first_err:
            # pgserver's own "wait for it to start" has a fixed 10-second
            # timeout - too short for a real post-crash recovery (the
            # sharing-violation retry alone runs up to 30s on this kind of
            # setup), even though postgres itself is very often still fine
            # and finishes starting up moments later in the background. A
            # second pg_ctl start here would race that still-running first
            # attempt, so this just watches its own status file instead
            # until it reports ready, then reconnects to it - a fast reuse,
            # not a new start.
            print("      Still starting - watching a bit longer...")
            if not _await_postgres_ready(pgdata, PostmasterInfo, seconds=60):
                raise first_err
            # get_server() caches its handle by pgdata path the moment
            # PostgresServer.__init__() starts, even though the timeout
            # above happened INSIDE that same __init__ (in
            # ensure_postgres_running()) - so the failed attempt already
            # left a half-built, cached instance with no postmaster info
            # behind. Reusing that same broken handle to reconnect would
            # just hit the same assertion get_uri() did before; drop it so
            # this reconnect builds a real one, which - now that the status
            # file above says ready - is a fast handshake, not a new start.
            from pgserver.postgres_server import PostgresServer
            PostgresServer._instances.pop(pgdata.expanduser().resolve(), None)
            _pg_server = pgserver.get_server(str(pgdata))
    except Exception:
        print()
        print("      [ERROR] The bundled database would not start.")
        print(f"              Full log: {pgdata / 'log'}")
        print("              If this keeps happening and you don't need the data in")
        print(f"              {pgdata}, close this window, rename or delete that folder,")
        print("              and launch again to start from a fresh database.")
        raise
    finally:
        stop.set()
        tail.join(timeout=2)
    uri = _pg_server.get_uri()  # postgresql://postgres:@127.0.0.1:<random port>/postgres
    lan = _lan_settings()
    if lan:
        uri = _restart_for_lan(pgdata, lan)
    return uri, first_run


def _lan_settings() -> dict | None:
    """Set by setup/portable_lan_access.py when a Device Gateway on another PC
    has to reach this database. Off unless .env says otherwise."""
    if os.getenv("PORTABLE_DB_LAN", "").strip() != "1":
        return None
    return {"port": int(os.getenv("PORTABLE_DB_PORT", "5433") or 5433),
            "password": os.getenv("PORTABLE_DB_PASSWORD", "")}


def _restart_for_lan(pgdata: "pathlib.Path", lan: dict) -> str:
    """Stops the database pgserver just started on a private random port, and
    starts it again on a fixed port, listening on every interface.

    pgserver always picks a free port and binds one address, which is right
    for a database only this PC uses and impossible for a gateway PC to find.
    Rather than reimplement start-up, this lets pgserver do the work - first
    run, recovery, all of it - and then restarts the same database with the
    options it needs. Everything else here, including the shutdown path
    below, already drives it through pg_ctl, so nothing else changes.
    """
    import pgserver

    print(f"      Gateway access is on - moving the database to port {lan['port']} on this PC's network address.")
    try:
        pgserver.pg_ctl(["-w", "stop"], pgdata=pgdata)
    except Exception:
        pass  # already stopped is the same starting point
    pgserver.pg_ctl(["-w", "-l", str(pgdata / "log"),
                     "-o", f"-p {lan['port']} -h *", "start"], pgdata=pgdata)
    password = f":{lan['password']}" if lan["password"] else ":"
    return f"postgresql://postgres{password}@127.0.0.1:{lan['port']}/postgres"


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


def _first_run_admin_setup(crud) -> None:
    """Reached exactly once - the moment this copy's database was just
    created (see main()'s first_run) - after crud's own module-level
    seed_initial_data() already dropped in three demo accounts, "manager" /
    "admin123" among them. A well-known admin password left sitting on a
    real install is a real credential, not just a placeholder, so this asks
    - right here, on the console someone is physically watching to run this
    the first time - for a real one, and retires the demo admin once a real
    one exists. The two demo operator accounts (operator/1234, sasha/1234)
    are left alone; they're low-privilege and useful for a quick test pour.

    The prompt itself (setup/_admin_setup.py) also backs the standalone
    "create an admin login" menu option in START_HERE.bat, for anyone who
    skips this, or wants a second admin, or is on the OTHER database (this
    PC's own PostgreSQL) - this is only the "ask automatically, once" path.
    """
    if not sys.stdin.isatty():
        print("      (non-interactive session - keeping the demo accounts;")
        print("       add a real admin later from START_HERE.bat's own")
        print("       'create an admin login' option.)")
        return

    sys.path.insert(0, str(BASE_DIR / "setup"))
    import _admin_setup

    print()
    print("=" * 70)
    print(" First-time setup - create your own admin login")
    print("=" * 70)
    print(" Demo accounts were also seeded for reference (operator/1234,")
    print(" sasha/1234) - those are left alone. The demo admin (manager /")
    print(" admin123) will be replaced by the one you create here.")
    print()
    print(" Press Enter with no name to skip this and keep manager/admin123.")
    print()

    try:
        username = _admin_setup.prompt_and_create(crud)
    except (EOFError, KeyboardInterrupt):
        username = None
    if username is None:
        print("      Skipped - sign in as manager / admin123 for now.")
        return

    crud.delete_user_by_username("manager")
    print()


def main() -> None:
    print("=" * 70)
    print(" Formlabs MES - Portable Mode (bundled database, no install needed)")
    print("=" * 70)

    dist_index = BASE_DIR / "frontend" / "dist" / "index.html"
    if not dist_index.exists():
        print("[ERROR] frontend\\dist\\index.html is missing.")
        print("        This copy wasn't built with the frontend included.")
        sys.exit(1)

    # setup/self_restart.py reads this to know that restarting here means
    # restarting the DATABASE too, not just a web server.
    os.environ["MES_LAUNCH_MODE"] = "portable"

    print("[1/3] Starting the bundled database...")
    admin_uri, first_run = _start_embedded_postgres()
    db_url = _ensure_database(admin_uri, DB_NAME)
    os.environ["DB_URL"] = db_url
    print(f"      Ready ({db_url.rsplit('@', 1)[-1]}).")

    print("[2/3] Bringing the schema up to date...")
    sys.path.insert(0, str(BASE_DIR))
    import crud  # noqa: E402  (its own module-level code runs init_db() + seed_initial_data())
    print("      Ready.")

    if first_run:
        _first_run_admin_setup(crud)

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
        #
        # Not _pg_server.cleanup(): that only actually stops anything once
        # its own cross-process ref-count of "handles still open on this
        # pgdata" reaches zero, tracked in pgdata\.handle_pids.json - and a
        # PID that ever left there without a clean exit (a crash, a forced
        # close, exactly the case this whole file exists to survive) stays
        # in that count forever, since nothing ever un-registers a dead
        # process from it. Once that happens once, cleanup() silently stops
        # doing anything on every later run, every shutdown becomes the
        # unclean kind, and the slow recovery above runs every single time.
        # pg_ctl stop is unconditional and doesn't care how many other
        # handles anyone thinks are open.
        if _pg_server is not None:
            print("Stopping the bundled database...")
            try:
                import pgserver
                pgserver.pg_ctl(["-w", "stop"], pgdata=BASE_DIR / "pgdata")
            except Exception as e:
                print(f"      [!] Could not stop it cleanly ({e}); it may still be running.")


if __name__ == "__main__":
    main()
