"""Build a plain "copy these over the top" zip of the application.

    python dev/make_dropin.py

Writes dist/mes_files_<version>.zip: every file a plant PC runs, laid out
exactly as the project folder is, so the whole update is "extract this over
that folder, say yes to replacing files".

This is the simplest possible route and the one that always works, including
on a PC too old to accept a signed package at all. What it gives up is the
safety net: setup/apply_update.py takes a database backup first, copies the
old version aside, proves the new one boots, and puts the old one back if it
doesn't. Extracting a zip does none of that, so this deliberately carries
NOTHING that belongs to the machine it lands on:

  .env            the database login, the gateway encryption key, tokens
  pgdata\\         the bundled database itself - every pour ever logged
  backups\\        its backups
  logs\\, uploads\\, rollback\\, updates\\, certs\\, venv\\

Nothing in this zip can touch the data. The schema still catches up on its
own: the app runs its migrations at start-up, as it does after any update.
"""
import pathlib
import sys
import zipfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"

sys.path.insert(0, str(ROOT / "dev"))
import importlib.util  # noqa: E402

_spec = importlib.util.spec_from_file_location("make_update", ROOT / "dev" / "make_update.py")
make_update = importlib.util.module_from_spec(_spec)
sys.path.insert(0, str(ROOT / "setup"))
_spec.loader.exec_module(make_update)

README = """FORMLABS MES - {version}

HOW TO USE THIS
---------------
1. On the plant PC, close the app if it is running (close its window).
2. Extract everything in this zip into the project folder - the folder that
   has START_HERE.bat in it. Say YES to replacing existing files.
3. Start the app again: START_HERE.bat, option 3.

That's it. The first start brings the database schema up to date by itself.

WHAT THIS DOES NOT TOUCH
------------------------
Your database (pgdata\\), your backups, your .env, your logs, your uploads
and your HTTPS certificate are not in this zip and cannot be overwritten by
it. Every pour, account and setting on that PC stays exactly as it is.

IF YOU WANT THE SAFETY NET INSTEAD
----------------------------------
The signed package (mes_update_{version}.zip + START_HERE.bat option 7) does
the same job, but takes a database backup first, checks the files really came
from the right PC, proves the app still starts afterwards, and puts the old
version back automatically if anything fails. Use that one where you can;
use this one when you just want the files in place.
"""


def main() -> None:
    version = make_update.app_version()
    files = make_update.every_shippable_file()
    if "VERSION" not in files:
        sys.exit("VERSION isn't in the file list - refusing to build")
    if not any(f.startswith("frontend/dist/") for f in files):
        sys.exit("frontend/dist is missing - run `npm run build` in frontend/ first")

    DIST.mkdir(exist_ok=True)
    out = DIST / f"mes_files_{version}.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for rel in files:
            zf.write(ROOT / rel, rel)
        zf.writestr("READ_ME_FIRST.txt", README.format(version=version))

    print(f"\n  {out.relative_to(ROOT)}   ({out.stat().st_size / 1024 / 1024:.1f} MB, {len(files)} files)")
    print()
    print("  On the plant PC: close the app, extract this over the project folder")
    print("  (the one with START_HERE.bat), replacing files, then start it again.")
    print("  Nothing in it can touch pgdata\\, backups\\, .env or certs\\.\n")


if __name__ == "__main__":
    main()
