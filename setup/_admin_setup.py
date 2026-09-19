"""The 'create an admin login' prompt itself - one copy, shared by two
callers that each need it for a different reason:

  - api/portable_launcher.py's first-run step, which runs this once,
    automatically, the moment a brand-new bundled database was just seeded
    with the demo accounts (see that file's _first_run_admin_setup).
  - setup/create_admin.py, the standalone "do this any time" menu option
    (START_HERE.bat) - not just at first install, and against either
    database (this PC's own PostgreSQL, or the bundled/portable one).

Needs DB_URL already pointed at a real, migrated database and `crud`
already imported (its own module-level init_db()/seed_initial_data() must
have already run) before this is called - it only prompts and writes a row,
it does not know how to reach a database on its own.
"""
import sys


def prompt_and_create(crud) -> str | None:
    """Prompts on the console for a new admin login and creates it.

    Returns the new username on success, None if skipped (blank name) or
    the account couldn't be created (username/email already taken). Raises
    nothing of its own - EOFError/KeyboardInterrupt from a closed or
    interrupted console are the caller's to handle, same as any input().
    """
    if not sys.stdin.isatty():
        print("      (no interactive console attached - nothing to do here.)")
        return None

    import getpass

    full_name = input(" Your name: ").strip()
    if not full_name:
        print("      Skipped - no name entered.")
        return None

    username = input(" Admin username: ").strip()
    while not username:
        username = input(" Admin username (required): ").strip()

    email = input(f" Email [{username}@plant.local]: ").strip() or f"{username}@plant.local"

    while True:
        pin = getpass.getpass(" Admin PIN (6+ digits, hidden as you type): ").strip()
        err = crud.pin_policy_error("admin", pin)
        if err:
            print(f"      {err}")
            continue
        confirm = getpass.getpass(" Confirm PIN: ").strip()
        if pin != confirm:
            print("      Those didn't match - try again.")
            continue
        break

    if not crud.create_user(username, email, pin, full_name, "admin"):
        print(f"      [!] '{username}' or '{email}' is already taken.")
        return None

    print(f"      Created - sign in as '{username}'.")
    return username
