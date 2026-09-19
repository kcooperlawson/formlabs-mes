"""Create an admin login - on demand, any time, not just at first install.

Not create_admin.py at the project root - that one is a narrower,
non-interactive emergency tool the installers call with fixed arguments
(create_admin.py manager admin123 "Plant Lead") to guarantee the seeded
account exists; it predates this file and stays exactly as it is. This one
is the interactive "set up a real admin login" wizard behind START_HERE.bat's
own menu options 10 and 11 - ordinary use, not a break-glass tool.

Two databases this can target, exactly matching START_HERE.bat's own split
for running the app:

    python setup\\create_admin_login.py            this PC's own PostgreSQL
                                                    (.env's DB_URL - same
                                                    database option 3 runs
                                                    against)
    python setup\\create_admin_login.py --portable  the bundled/embedded
                                                    database (same one
                                                    option 9 runs against,
                                                    and the one
                                                    api/portable_launcher.py
                                                    already offers this same
                                                    prompt for automatically
                                                    on its very first launch)

For the portable database this starts it up first (which, right after an
unclean shutdown, can take up to a minute - see
api/portable_launcher.py's own recovery handling, reused here) and stops it
again afterward, since this script's job ends the moment the account
exists; it is not "run the app."
"""
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "setup"))


def _offer_retire_demo_admin(crud) -> None:
    """Asks, rather than doing it automatically the way the portable
    launcher's own first-run prompt does - this script can be run long
    after that moment, when 'manager' might already be gone, or kept on
    purpose as a break-glass account. Silent no-op if it isn't there."""
    if "manager" not in set(crud.get_all_users_df()["username"]):
        return
    answer = input(" Also remove the demo admin login ('manager')? [y/N]: ").strip().lower()
    if answer == "y":
        crud.delete_user_by_username("manager")
        print("      Removed 'manager'.")


def _target_regular() -> None:
    if not (ROOT / ".env").exists():
        print("[ERROR] No .env file here yet - this PC hasn't been set up with")
        print("        its own PostgreSQL. Choose 1 (Install the MES) first, or")
        print("        use the --portable option for the bundled database instead.")
        sys.exit(1)
    import crud  # noqa: E402  (module-level init_db()/seed_initial_data() run here)
    import _admin_setup

    if _admin_setup.prompt_and_create(crud):
        _offer_retire_demo_admin(crud)


def _target_portable() -> None:
    from api import portable_launcher
    from pgserver.postgres_server import PostmasterInfo

    pgdata = ROOT / "pgdata"
    # If option 9 (or another copy of this script) already has it up - most
    # concretely, operators mid-shift on a live portable install while
    # someone opens this from a second START_HERE.bat window - this must
    # never be the thing that stops it out from under them on the way out.
    # Only stop what this run is the one that actually started.
    already_running = (info := PostmasterInfo.read_from_pgdata(pgdata)) is not None and info.is_running()

    pg_server = None
    try:
        print("Starting the bundled database...")
        admin_uri, _first_run = portable_launcher._start_embedded_postgres()
        pg_server = portable_launcher._pg_server
        db_url = portable_launcher._ensure_database(admin_uri, portable_launcher.DB_NAME)
        os.environ["DB_URL"] = db_url
        print(f"Ready ({db_url.rsplit('@', 1)[-1]}).")
        print()

        import crud  # noqa: E402
        import _admin_setup

        if _admin_setup.prompt_and_create(crud):
            _offer_retire_demo_admin(crud)
    finally:
        # Not pg_server.cleanup() - see api/portable_launcher.py's own
        # shutdown for why that can silently stop doing anything after a
        # single past crash. pg_ctl stop always actually stops it -
        # exactly why it's only called when this run is the one that
        # started it.
        if pg_server is not None and not already_running:
            print()
            print("Stopping the bundled database...")
            try:
                import pgserver
                pgserver.pg_ctl(["-w", "stop"], pgdata=pgdata)
            except Exception as e:
                print(f"      [!] Could not stop it cleanly ({e}); it may still be running.")
        elif pg_server is not None:
            print()
            print("Leaving the bundled database running - something else was already using it.")


def main() -> None:
    print("=" * 70)
    print(" Formlabs MES - Create an admin login")
    print("=" * 70)
    print()

    if "--portable" in sys.argv[1:]:
        _target_portable()
    else:
        _target_regular()


if __name__ == "__main__":
    main()
