"""Build the single file that gets carried to the plant PC.

    python dev/make_update.py --init-keys              once, ever
    python dev/make_update.py --notes "what's in it"   build a package
    python dev/make_update.py --notes "..." --publish  build it and publish it

    python dev/make_update.py --files crud.py api/main.py    just these files
    python dev/make_update.py --since <git rev>              a diff package

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

Which files go in: EVERY file a plant PC runs, every time (4.08 onwards) -
the whole application, not a diff. A diff package has to be built against the
exact version the far PC is on, and this project has no release tags, so
"changed since PT-V4.02" silently meant "changed since the last commit" and
could ship a package missing half of what it claimed to carry. A full package
cannot be missing a file, applies to any older version, and costs a few MB
that a USB stick and a GitHub release both handle without noticing. Pass
--since <rev> for the old diff behaviour when a small hand-built package is
genuinely wanted.

Never .env, backups, logs, uploads, venv, pgdata, certs, the tests or the
document sources - those are either the machine's own or not needed on a floor
PC. Deletions still have to be named with --delete: a file a release removed
has to be removed there too, and a full package says what should exist, not
what shouldn't (anything else on that PC - a local script, an old backup - is
none of a release's business).

--publish (added alongside the auto-update system): also uploads the built
zip to a GitHub Release tagged with the version it installs, so a plant PC
running with the internet can find and apply it on its own (see
api/routers/updates.py) instead of needing a USB stick carried in by hand.
See dev/update_publish.py for what that actually does and what it needs in
.env. This is entirely optional - a USB stick and START_HERE.bat's own
choice 7 still work exactly as before, with or without ever using this flag.
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


def build(from_version, to_version, files, deletes, packages, notes, out_dir=None):
    """out_dir exists for callers that must NOT touch dist\\ - the tests and
    dev/simulate_portable_update.py build real packages, and a package built
    for a test run once overwrote (and then deleted) the release sitting in
    dist\\ waiting to be carried to a plant PC."""
    out_dir = pathlib.Path(out_dir) if out_dir else DIST
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"mes_update_{to_version}.zip"
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


def every_shippable_file() -> list:
    """Every file a plant PC actually runs: what git tracks, plus anything
    untracked that still ships (a new module written today, a migration not
    committed yet), plus the built frontend - which is git-ignored, so git
    lists none of it, and a package without it updates the server while
    leaving the browser on the old app."""
    tracked = [rel for rel in git("ls-files") if shippable(rel) and (ROOT / rel).is_file()]

    untracked = []
    for line in git("status", "--porcelain", "-uall"):
        code, rel = line[:2], line[3:].strip().strip('"')
        if " -> " in rel:
            rel = rel.split(" -> ")[1]
        if "D" in code:
            continue
        if shippable(rel) and (ROOT / rel).is_file():
            untracked.append(rel)

    built = [p.relative_to(ROOT).as_posix() for p in sorted((ROOT / "frontend" / "dist").rglob("*"))
             if p.is_file()]
    return sorted(set(tracked) | set(untracked) | set(built))


def build_release(from_version: str = "", notes: str = "", since: str = "",
                  deletes: list | None = None, out_dir=None) -> tuple[pathlib.Path, dict]:
    """The package both `--publish` and the in-app publish button build, so
    the two can never drift apart.

    from_version is left out of the manifest on purpose for a full package:
    setup/apply_update.py only enforces a from_version when the manifest
    names one, and a package carrying the whole application is correct to
    apply to ANY older version - which is the whole point of a plant PC
    being able to update itself without somebody first working out which
    version it happens to be on.
    """
    to_version = app_version()
    if not to_version:
        raise RuntimeError("VERSION file is empty - nothing to build")

    if since:
        files, found_deletes = changed_since(since)
        deletes = list(deletes or []) + [d for d in found_deletes if d not in (deletes or [])]
        if not files and not deletes:
            raise RuntimeError(f"nothing changed since {since} - no package built")
        return build(from_version, to_version, files, deletes, [], notes, out_dir)

    files = every_shippable_file()
    if "VERSION" not in files:
        raise RuntimeError("VERSION is not in the package - the far PC would install the "
                           "new code and keep reporting the old version")
    if not any(f.startswith("frontend/dist/") for f in files):
        raise RuntimeError("frontend/dist is missing - build the frontend first "
                           "(cd frontend && npm run build), or the far PC gets new "
                           "server code behind the old browser app")
    return build(None, to_version, files, list(deletes or []), [], notes, out_dir)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--from", dest="from_version", default="",
                    help="only for a --files or --since package: the version "
                         "it may be applied to. A full package needs no such "
                         "limit and doesn't record one.")
    ap.add_argument("--since", default="",
                    help="build a DIFF package against this git revision "
                         "instead of the default full package")
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
    ap.add_argument("--publish", action="store_true",
                    help="also upload the built zip to a GitHub Release, "
                         "tagged with the version it installs, so plant PCs "
                         "running the auto-update checker can find it")
    ap.add_argument("--repo", default="",
                    help="owner/repo to publish to (default: "
                         "dev/update_publish.py's DEFAULT_REPO)")
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

    try:
        if args.files is not None:
            files = [f for f in args.files if shippable(f) and (ROOT / f).is_file()]
            if not files and not args.delete:
                sys.exit("Nothing to ship - no package built.")
            out, manifest = build(args.from_version, to_version, files, list(args.delete),
                                  args.packages, args.notes)
        else:
            # The normal path: the whole application, applies to any older
            # version. --since asks for the old diff behaviour instead.
            out, manifest = build_release(args.from_version, args.notes, args.since,
                                          list(args.delete))
    except RuntimeError as exc:
        sys.exit(f"  [X] {exc}")
    except FileNotFoundError as exc:
        sys.exit(str(exc))

    print(f"\n  {out.relative_to(ROOT)}   ({out.stat().st_size / 1024:.0f} KB)")
    print(f"  {manifest['from_version'] or 'any version'} -> {manifest['to_version']}, "
          f"{len(manifest['files'])} files\n")
    if args.files is not None or args.since:
        for entry in manifest["files"]:
            print(f"    + {entry['path']}")
    for rel in manifest["delete"]:
        print(f"    - {rel}")
    if manifest["packages"]:
        print("\n  new packages: " + ", ".join(manifest["packages"]))
    print("\n  Copy that one file to the plant PC's updates\\ folder, then run")
    print("  START_HERE.bat and choose 7.")

    if args.publish:
        print()
        print("  Publishing to GitHub...")
        # Imported here, not at the top: building a package needs nothing from
        # it, and anything that imports this module for build_release() (the
        # tests, api/routers/updates.py) shouldn't need dev\ on its path.
        import update_publish
        from dotenv import load_dotenv
        load_dotenv()
        try:
            kwargs = {"repo": args.repo} if args.repo else {}
            result = update_publish.publish_release(out, manifest, **kwargs)
        except update_publish.PublishError as exc:
            sys.exit(f"  [X] {exc}")
        print(f"  [ok] {result['tag_name']} published: {result['html_url']}")
        print(f"       asset: {result['asset_name']} "
             f"({result['asset_size'] / 1024:.0f} KB)")
        print()
        print("  Any plant PC on 4.08+ with internet access will see this the")
        print("  next time it checks for updates.")
    print()


if __name__ == "__main__":
    main()
