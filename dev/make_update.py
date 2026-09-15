"""Build the single file that gets carried to the plant PC.

    python dev/make_update.py --init-keys                 once, ever
    python dev/make_update.py --from PT-V3.40
    python dev/make_update.py --from PT-V3.40 --files crud.py api/main.py
    python dev/make_update.py --from PT-V3.40 --since <git rev> --notes "..."

It writes  dist/mes_update_<to version>.zip  and prints what went in it.

The zip holds the changed files under files/, and a manifest naming every one
of them with its checksum, the version it goes from and to, anything to delete,
and any new packages. setup/apply_update.py on the other end reads that and
nothing else - the package carries no code that runs, because a USB stick that
executes on a plant PC is a different object from one that carries files.

Every build is also signed (setup/update_signing.py) with the private key at
dev/update_signing_private.pem. A checksum proves a file arrived intact; a
signature proves it came from whoever holds that key, not just whoever last
wrote to the USB stick. Run --init-keys once to create the key pair - it
prints exactly what to do with each half. After that, every build signs
itself automatically and refuses to produce an unsigned package.

Which files go in: whatever changed in git since the deployed version, or an
explicit list. Never .env, backups, logs, uploads, venv, the tests or the
document sources - those are either the machine's own or not needed on a floor
PC. Deletions are picked up from git as well, because a page that a release
removed has to be removed there too; one left behind still appears in the menu
and still opens.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import subprocess
import sys
import zipfile
from datetime import datetime

ROOT = pathlib.Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"

sys.path.insert(0, str(ROOT / "setup"))
import update_signing  # noqa: E402

# Not the machine's, not needed on the floor, or simply large.
SKIP_DIRS = {"venv", "backups", "logs", "uploads", "updates", "rollback",
             ".git", "__pycache__", "_to_delete", "dist", "tests", "dev",
             "docs", "wheels", "assets_src", "pgdata", "certs"}
SKIP_NAMES = {".env", ".env.local", "combined_code.txt"}
SKIP_SUFFIX = {".pyc", ".zip", ".tgz", ".log", ".bak", ".sql"}


def app_version() -> str:
    # Used to be read out of Home.py's own APP_VERSION line - moved to a
    # plain VERSION file at the root once Home.py (and the rest of the
    # Streamlit UI) was retired, so this stays meaningful for whichever app
    # is actually shipping (crud.py, api/, frontend/) rather than a file
    # that no longer exists.
    return (ROOT / "VERSION").read_text(encoding="utf-8").strip()


def shippable(rel: str) -> bool:
    parts = rel.replace("\\", "/").split("/")
    if parts[0] in SKIP_DIRS or parts[-1] in SKIP_NAMES:
        return False
    if pathlib.PurePosixPath(rel).suffix in SKIP_SUFFIX:
        return False
    return True


def git(*args):
    out = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    return out.stdout.splitlines() if out.returncode == 0 else []


def changed_since(rev: str):
    """(changed, deleted) paths from git, filtered to what may ship."""
    changed, deleted = [], []
    for line in git("diff", "--name-status", rev, "HEAD"):
        bits = line.split("\t")
        if len(bits) < 2:
            continue
        status, rel = bits[0], bits[-1]
        if not shippable(rel):
            continue
        (deleted if status.startswith("D") else changed).append(rel)
    # Anything edited but not committed yet counts too - the person building
    # this is the person who just made the change, and a release that misses
    # the file it was built for is the worst possible failure here.
    for line in git("status", "--porcelain"):
        rel = line[3:].strip()
        if line[:2] != " D" and shippable(rel) and (ROOT / rel).is_file() \
                and rel not in changed:
            changed.append(rel)
    return sorted(set(changed)), sorted(set(deleted))


def build(from_version, to_version, files, deletes, packages, notes):
    DIST.mkdir(exist_ok=True)
    out = DIST / f"mes_update_{to_version}.zip"
    manifest = {
        "format": 1,
        "from_version": from_version or None,
        "to_version": to_version,
        "built_at": datetime.now().isoformat(timespec="seconds"),
        "notes": notes or "",
        "files": [],
        "delete": deletes,
        "packages": packages,
    }
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for rel in files:
            data = (ROOT / rel).read_bytes()
            manifest["files"].append({
                "path": rel.replace("\\", "/"),
                "sha256": hashlib.sha256(data).hexdigest(),
                "bytes": len(data),
            })
            zf.writestr("files/" + rel.replace("\\", "/"), data)
        manifest["signature"] = update_signing.sign(manifest)
        zf.writestr("mes_update.json", json.dumps(manifest, indent=2))
    return out, manifest


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--from", dest="from_version", default="",
                    help="the version the plant PC is on, e.g. PT-V3.40")
    ap.add_argument("--since", default="",
                    help="git revision to diff against (default: the tag "
                         "matching --from, else the last commit)")
    ap.add_argument("--files", nargs="*", default=None,
                    help="build from this explicit list instead of git")
    ap.add_argument("--delete", nargs="*", default=[],
                    help="files the plant PC should remove")
    ap.add_argument("--packages", nargs="*", default=[],
                    help="new pip requirements this release needs")
    ap.add_argument("--notes", default="",
                    help="what is in it, in one or two lines, shown before "
                         "the person confirms")
    ap.add_argument("--init-keys", action="store_true",
                    help="create the signing key pair (once, ever) and exit")
    args = ap.parse_args()

    if args.init_keys:
        try:
            priv, pub = update_signing.generate_keypair()
        except FileExistsError as exc:
            sys.exit(str(exc))
        print(f"\n  Wrote {priv.relative_to(ROOT)} and {pub.relative_to(ROOT)}\n")
        print(f"  {priv.name} signs every release from here on. Keep it")
        print("  somewhere that is not this repo and not a plant PC - a")
        print("  password manager or an encrypted drive, not a USB stick")
        print("  that also carries update packages. If it's ever lost, every")
        print("  plant PC's copy of update_signing_public.pem stops matching")
        print("  anything you can sign until you redistribute a new one.")
        print()
        print(f"  {pub.name} is not a secret - commit it. Every PC needs it")
        print("  to check a release actually came from here.\n")
        return

    to_version = app_version()
    if not to_version:
        sys.exit("Home.py has no APP_VERSION - nothing to build.")

    if args.files is not None:
        files = [f for f in args.files if shippable(f) and (ROOT / f).is_file()]
        deletes = list(args.delete)
    else:
        rev = args.since or (args.from_version if args.from_version in git("tag")
                             else "HEAD~1")
        files, deletes = changed_since(rev)
        deletes += [d for d in args.delete if d not in deletes]

    if not files and not deletes:
        sys.exit("Nothing changed - no package built.")

    try:
        out, manifest = build(args.from_version, to_version, files, deletes,
                              args.packages, args.notes)
    except FileNotFoundError as exc:
        sys.exit(str(exc))

    print(f"\n  {out.relative_to(ROOT)}   ({out.stat().st_size / 1024:.0f} KB)")
    print(f"  {manifest['from_version'] or 'any'} -> {manifest['to_version']}\n")
    for entry in manifest["files"]:
        print(f"    + {entry['path']}")
    for rel in manifest["delete"]:
        print(f"    - {rel}")
    if manifest["packages"]:
        print("\n  new packages: " + ", ".join(manifest["packages"]))
    print("\n  Copy that one file to the plant PC's updates\\ folder, then run")
    print("  START_HERE.bat and choose 7.\n")


if __name__ == "__main__":
    main()
