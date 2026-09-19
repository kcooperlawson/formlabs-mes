"""Repairs the updater on a PC too old to accept an update at all.

The case this exists for: a PC running the bundled/portable database on 4.07
or earlier. Applying an update there stops at the first step, because the
database backup can't find a portable database - `.env` has no DB_URL (the
portable launcher picks a port at run time and never writes it down) and
there's no installed PostgreSQL to provide pg_dump. apply_update.py then
refuses to go on, on purpose: an update without a backup behind it is the one
you cannot undo.

The fix for that is in utils.py, which arrives *in* an update - the one that
can't be applied. So this takes the few files the updater itself needs out of
a package that is already signed and verified, and nothing else:

    venv\\Scripts\\python.exe setup\\bootstrap_update.py
    (START_HERE.bat, option 13)

It is deliberately not a second, weaker installer:

  * the package's signature and checksums are checked first, by the same
    setup/update_signing.py the real applier uses - an unsigned or altered
    zip is refused here too;
  * only the files in ALLOWED below are written, whatever else the package
    holds - this cannot install a release, only make one installable;
  * the originals are copied to rollback\\ first;
  * nothing touches the database, so it works with the app closed, with no
    database running, and on a PC whose updater is broken in exactly the way
    that stops everything else.

Afterwards, apply the update the normal way (START_HERE.bat, option 7, or the
Updates tab in the app) and the full pipeline - backup, rollback copy, verify
it boots - runs as it always has.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import zipfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

MANIFEST_NAME = "mes_update.json"

# The updater's own plumbing, and nothing else. Every one of these is read by
# the update process itself before any application code runs.
#
# setup/update_signing_public.pem is deliberately NOT here. That key is what
# decides whether a package is genuine, so taking a replacement for it out of
# a package would let a package vouch for itself.
ALLOWED = (
    "utils.py",                  # finds the portable database and its pg_dump for the backup step
    "db_options.py",             # imported by db_core.py from 4.07 on
    "setup/apply_update.py",
    "setup/update_signing.py",
    "setup/self_restart.py",
    "setup/bootstrap_update.py",  # so this PC has the repair tool itself from now on
    "_migration_helper.py",      # the backup step runs this
)

OK, BAD, INFO = "  [ok]", "  [X] ", "      "


def newest_package(updates_dir: Path) -> Path | None:
    zips = [p for p in updates_dir.glob("*.zip") if p.is_file()] if updates_dir.is_dir() else []
    return max(zips, key=lambda p: p.stat().st_mtime) if zips else None


def repair(package_path: Path, root: Path = ROOT) -> int:
    # Imported here, not at the top: Repair_Updater.bat runs this file from a
    # temp folder, so the project's setup\ is only known once --root is read.
    sys.path.insert(0, str(root / "setup"))
    import update_signing

    print()
    print("  ===================================================")
    print("   REPAIR THE UPDATER")
    print("  ===================================================")
    print()
    print(f"  Package: {package_path.name}")
    print()

    with zipfile.ZipFile(package_path) as zf:
        try:
            manifest = json.loads(zf.read(MANIFEST_NAME).decode("utf-8"))
        except Exception as exc:
            print(BAD + f"this zip has no readable update manifest ({exc}).")
            return 1

        sig_ok, sig_detail = update_signing.verify(
            manifest, root / "setup" / "update_signing_public.pem")
        if not sig_ok:
            print(BAD + f"signature check failed: {sig_detail}.")
            print(INFO + "Nothing has been changed. This package did not come from the")
            print(INFO + "real signing key, or was altered after it was built.")
            return 1
        print(OK, sig_detail)

        wanted = {e["path"].replace("\\", "/"): e for e in manifest.get("files", [])
                  if e["path"].replace("\\", "/") in ALLOWED}
        if not wanted:
            print(BAD + "this package carries none of the updater's own files.")
            print(INFO + "Nothing to repair from it.")
            return 1

        # Same check the real applier makes: the bytes have to match what the
        # signed manifest says they are.
        for rel, entry in wanted.items():
            member = "files/" + rel
            if member not in zf.namelist():
                print(BAD + f"{rel} is listed in the manifest but missing from the zip.")
                return 1
            if hashlib.sha256(zf.read(member)).hexdigest() != entry["sha256"]:
                print(BAD + f"{rel} does not match its checksum - copy the file across again.")
                return 1
        print(OK, f"{len(wanted)} updater file(s), every checksum matches")

        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        kept = root / "rollback" / f"updater_{stamp}"
        written = []
        for rel, _entry in sorted(wanted.items()):
            target = root / Path(rel)
            if target.exists():
                backup = kept / rel
                backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, backup)
            target.parent.mkdir(parents=True, exist_ok=True)
            with open(target, "wb") as fh:
                fh.write(zf.read("files/" + rel))
            written.append(rel)

    for base, dirs, _files in os.walk(root):
        if os.path.basename(base) == "__pycache__":
            shutil.rmtree(base, ignore_errors=True)
            dirs[:] = []

    print(OK, f"{len(written)} file(s) replaced: {', '.join(written)}")
    print(OK, f"the previous copies are in rollback\\{kept.name}")
    print()
    print("  ===================================================")
    print("   DONE - this PC can accept updates now")
    print("  ===================================================")
    print()
    print("  The version on this PC has NOT changed. Apply the update itself the")
    print("  normal way: START_HERE.bat, option 7 (or the Updates tab in the app).")
    print()
    return 0


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    # --root lets Repair_Updater.bat run this from a temp folder against the
    # project it sits next to: a PC old enough to need repairing doesn't have
    # this file in its own setup\ yet, so the .bat carries a copy.
    root = ROOT
    if "--root" in argv:
        at = argv.index("--root")
        root = Path(argv[at + 1]).resolve()
        del argv[at:at + 2]
        globals()["ROOT"] = root
        sys.path.insert(0, str(root / "setup"))

    if argv:
        package = Path(argv[0])
    else:
        package = newest_package(root / "updates")
        if package is None:
            print()
            print("  No update package found.")
            print()
            print(f"  Put the .zip you were given into:  {root / 'updates'}")
            print("  then run this again.")
            print()
            return 1
    if not package.is_file():
        print(BAD + f"no such file: {package}")
        return 1
    return repair(package, root)


if __name__ == "__main__":
    raise SystemExit(main())
