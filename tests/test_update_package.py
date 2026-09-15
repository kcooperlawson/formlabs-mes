"""The USB update: build a package, apply it, and make it fail on purpose.

None of this touches the real project. Every case builds a small fake plant PC
in a temporary folder - a Home.py with a version in it, a file to change, an
.env, a backups folder - and runs the real applier against it, with the two
steps that need a database and a Python environment stood in for.

The cases are the ones that actually happen on a floor:

  * a half-copied USB stick, which looks exactly like a good one until the
    checksums are read
  * the same package applied twice
  * a package built for a different version than the PC is on
  * an update that breaks the app, which has to put the old version back
    rather than leaving a plant with a broken screen and a person holding a
    USB stick
  * .env and backups\\, which belong to the machine and must survive an
    update that would otherwise overwrite them
  * a package that is not signed with the real key, or was changed after
    it was signed - a checksum alone cannot tell either of those apart
    from a good release
"""
import hashlib
import json
import pathlib
import shutil
import sys
import tempfile
import zipfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "setup"))

import apply_update  # noqa: E402
import update_signing  # noqa: E402

FAILURES, COUNT = [], 0

# A throwaway key pair for this test run only - never the real
# dev/update_signing_private.pem. Every fake_plant() gets the public half
# in its own setup/, so signature checks run for real without touching
# anything that actually protects a live plant PC.
_TEST_KEYS = pathlib.Path(tempfile.mkdtemp(prefix="mes_testkeys_"))
_TEST_PRIVATE = _TEST_KEYS / "private.pem"
_TEST_PUBLIC = _TEST_KEYS / "public.pem"
update_signing.generate_keypair(_TEST_PRIVATE, _TEST_PUBLIC)


def check(cond, what):
    global COUNT
    COUNT += 1
    if not cond:
        FAILURES.append(what)
        print(f"  FAIL  {what}")


# --------------------------------------------------------------- fixtures --
def fake_plant(version="PT-V3.40"):
    """A folder shaped like the plant PC, with things that must not be touched."""
    root = pathlib.Path(tempfile.mkdtemp(prefix="mes_plant_"))
    # apply_update.read_version() reads this file, not a line inside some
    # other source file - see its own docstring for why.
    (root / "VERSION").write_text(f"{version}\n", encoding="utf-8")
    (root / "Home.py").write_text(
        f'APP_VERSION = "{version}"\nHELLO = "old"\n', encoding="utf-8")
    (root / "crud.py").write_text("VALUE = 1\n", encoding="utf-8")
    (root / "pages").mkdir()
    (root / "pages" / "Old_Page.py").write_text("# retired\n", encoding="utf-8")
    (root / ".env").write_text("DB_URL=postgresql://thismachine\n", encoding="utf-8")
    (root / "backups").mkdir()
    (root / "backups" / "mes_backup_1.sql").write_text("dump", encoding="utf-8")
    (root / "logs").mkdir()
    (root / "setup").mkdir()
    shutil.copy(_TEST_PUBLIC, root / "setup" / "update_signing_public.pem")
    return root


def make_package(files, to_version="PT-V3.41", from_version="PT-V3.40",
                 delete=(), packages=(), notes="", corrupt=False, sign=True,
                 signing_key=None):
    """A package built the way dev/make_update.py builds one.

    sign=False leaves the manifest exactly as an update built before this
    feature existed would look - no "signature" key at all. signing_key
    lets a case sign with the WRONG key, to prove that is caught too.
    """
    path = pathlib.Path(tempfile.mkdtemp(prefix="mes_pkg_")) / f"mes_update_{to_version}.zip"
    manifest = {"format": 1, "from_version": from_version, "to_version": to_version,
                "built_at": "now", "notes": notes, "files": [],
                "delete": list(delete), "packages": list(packages)}
    with zipfile.ZipFile(path, "w") as zf:
        for rel, text in files.items():
            data = text.encode("utf-8")
            manifest["files"].append({
                "path": rel,
                "sha256": hashlib.sha256(data if not corrupt else b"different").hexdigest(),
                "bytes": len(data)})
            zf.writestr("files/" + rel, data)
        if sign:
            manifest["signature"] = update_signing.sign(
                manifest, signing_key or _TEST_PRIVATE)
        zf.writestr("mes_update.json", json.dumps(manifest))
    return path


def run(package, root, backup=(True, "mes_backup_x.sql"), verify=(True, "ok")):
    """Apply, with the database backup and the boot check stood in for.

    Those two shell out to the plant PC's own Python and Postgres. Everything
    between them - the checksums, the version rules, the copy aside, the
    writes, the rollback - is the real code.
    """
    real_backup, real_verify, real_pkgs = (
        apply_update.take_backup, apply_update.verify, apply_update.install_packages)
    apply_update.take_backup = lambda r=None: backup
    apply_update.verify = lambda r, w: verify
    apply_update.install_packages = lambda m, r: (True, "none needed")
    try:
        return apply_update.apply(str(package), root=str(root), assume_yes=True)
    finally:
        apply_update.take_backup = real_backup
        apply_update.verify = real_verify
        apply_update.install_packages = real_pkgs


def read(root, rel):
    p = pathlib.Path(root) / rel
    return p.read_text(encoding="utf-8") if p.is_file() else None


# ------------------------------------------------------------ a good update --
print("\nAn update that works")

plant = fake_plant()
pkg = make_package({"VERSION": "PT-V3.41\n",
                    "Home.py": 'APP_VERSION = "PT-V3.41"\nHELLO = "new"\n',
                    "pages/New_Page.py": "# added\n"},
                   delete=["pages/Old_Page.py"], notes="Two things and a fix.")
code = run(pkg, plant)

check(code == 0, "it reports success")
check(apply_update.read_version(plant) == "PT-V3.41", "the version moved")
check("new" in read(plant, "Home.py"), "the changed file was written")
check(read(plant, "pages/New_Page.py") is not None, "a new file was created")
check(read(plant, "pages/Old_Page.py") is None, "and a retired one was removed")
check(read(plant, ".env") == "DB_URL=postgresql://thismachine\n",
      ".env is untouched - it belongs to the machine, not the release")
check(read(plant, "backups/mes_backup_1.sql") == "dump", "backups are untouched")
check((pathlib.Path(plant) / "rollback").is_dir(), "a rollback copy was kept")
check(not pkg.exists(), "the package was filed away rather than left to be "
                        "applied again")
_applied = list((pathlib.Path(plant) / "updates" / "applied").glob("*.zip"))
check(len(_applied) == 1, "and it is in updates/applied")
check("applied" in (read(plant, "logs/updates.log") or ""), "the log says what happened")

# -------------------------------------------------------- a broken update --
print("\nAn update that breaks the app")

plant = fake_plant()
pkg = make_package({"VERSION": "PT-V3.41\n",
                    "Home.py": 'APP_VERSION = "PT-V3.41"\nHELLO = "broken"\n'})
code = run(pkg, plant, verify=(False, "the application did not start: boom"))

check(code == 1, "it reports failure")
check(apply_update.read_version(plant) == "PT-V3.40",
      "the PC is back on the version it was running")
check("old" in read(plant, "Home.py"), "and the old file is back byte for byte")
check(read(plant, ".env") == "DB_URL=postgresql://thismachine\n",
      ".env survived the rollback too")
check(pkg.exists(), "the package is left where it was, not filed as applied")
check("FAILED" in (read(plant, "logs/updates.log") or ""),
      "and the failure is in the log")

# ------------------------------------------------------- a half-copied stick --
print("\nA package that did not copy properly")

plant = fake_plant()
pkg = make_package({"Home.py": 'APP_VERSION = "PT-V3.41"\n'}, corrupt=True)
code = run(pkg, plant)

check(code == 1, "a bad checksum stops it")
check(apply_update.read_version(plant) == "PT-V3.40", "before anything is written")
check("old" in read(plant, "Home.py"), "the file on disk is untouched")
check(not (pathlib.Path(plant) / "rollback").is_dir(),
      "and it did not even get as far as copying the project aside")

# --------------------------------------------------------- signed, or refused --
print("\nA package must be signed with the real key")

plant = fake_plant()
pkg = make_package({"Home.py": 'APP_VERSION = "PT-V3.41"\n'}, sign=False)
code = run(pkg, plant)
check(code == 1, "an unsigned package is refused")
check(apply_update.read_version(plant) == "PT-V3.40", "nothing is changed")
check(not (pathlib.Path(plant) / "rollback").is_dir(),
      "it never got as far as copying the project aside")

plant = fake_plant()
_wrong_priv = _TEST_KEYS / "wrong.pem"
if not _wrong_priv.exists():
    update_signing.generate_keypair(_wrong_priv, _TEST_KEYS / "wrong_pub.pem")
pkg = make_package({"Home.py": 'APP_VERSION = "PT-V3.41"\n'}, signing_key=_wrong_priv)
code = run(pkg, plant)
check(code == 1, "a package signed with the wrong key is refused")
check(apply_update.read_version(plant) == "PT-V3.40", "nothing is changed")

plant = fake_plant()
pkg = make_package({"Home.py": 'APP_VERSION = "PT-V3.41"\nHELLO = "new"\n'})
# Tamper with the checksum AND the payload together, consistently, after
# signing - the case a checksum alone cannot catch, because the file and
# its recorded hash still agree with each other.
with zipfile.ZipFile(pkg) as zf:
    manifest = json.loads(zf.read("mes_update.json"))
    members = {n: zf.read(n) for n in zf.namelist() if n != "mes_update.json"}
tampered = b'APP_VERSION = "PT-V3.41"\nHELLO = "malicious"\n'
members["files/Home.py"] = tampered
for entry in manifest["files"]:
    if entry["path"] == "Home.py":
        entry["sha256"] = hashlib.sha256(tampered).hexdigest()
        entry["bytes"] = len(tampered)
pkg.unlink()
with zipfile.ZipFile(pkg, "w") as zf:
    for name, data in members.items():
        zf.writestr(name, data)
    zf.writestr("mes_update.json", json.dumps(manifest))  # old signature, new content
code = run(pkg, plant)
check(code == 1, "content changed after signing is refused, even with a "
                 "self-consistent checksum")
check(apply_update.read_version(plant) == "PT-V3.40", "nothing is changed")

# ------------------------------------------------------------ wrong version --
print("\nThe wrong package for this PC")

plant = fake_plant(version="PT-V3.38")
pkg = make_package({"Home.py": 'APP_VERSION = "PT-V3.41"\n'}, from_version="PT-V3.40")
check(run(pkg, plant) == 1, "a package built for another version is refused")
check(apply_update.read_version(plant) == "PT-V3.38", "and nothing is changed")

plant = fake_plant(version="PT-V3.41")
pkg = make_package({"Home.py": 'APP_VERSION = "PT-V3.41"\n'}, from_version=None)
check(run(pkg, plant) == 1, "so is one this PC has already had")

plant = fake_plant(version="PT-V3.41")
pkg = make_package({"Home.py": 'APP_VERSION = "PT-V3.39"\n'},
                   to_version="PT-V3.39", from_version=None)
check(run(pkg, plant) == 1, "and so is an older one going backwards")

# ------------------------------------------------- what a package may write --
print("\nWhat a package is allowed to contain")

plant = fake_plant()
pkg = make_package({".env": "DB_URL=somewhere-else\n"})
check(run(pkg, plant) == 1, "a package that would overwrite .env is refused")
check(read(plant, ".env") == "DB_URL=postgresql://thismachine\n", "and does not")

plant = fake_plant()
pkg = make_package({"backups/mes_backup_1.sql": "clobbered"})
check(run(pkg, plant) == 1, "so is one that would write into backups")

plant = fake_plant()
pkg = make_package({"../outside.py": "escaped"})
check(run(pkg, plant) == 1, "and one that points outside the project folder")

plant = fake_plant()
pkg = make_package({"Home.py": 'APP_VERSION = "PT-V3.41"\n'},
                   delete=[".env", "backups/mes_backup_1.sql"])
run(pkg, plant)
check(read(plant, ".env") is not None and read(plant, "backups/mes_backup_1.sql"),
      "a delete list cannot remove the machine's own files either")

# ---------------------------------------------------------- no backup, stop --
print("\nWhen the backup fails")

plant = fake_plant()
pkg = make_package({"Home.py": 'APP_VERSION = "PT-V3.41"\n'})
code = run(pkg, plant, backup=(False, "pg_dump not found"))
check(code == 1, "no backup means no update")
check("old" in read(plant, "Home.py"),
      "and nothing was written, because that is the one you cannot undo")

# ------------------------------------------------------------ the builder --
print("\nThe builder agrees with the applier")

import importlib.util  # noqa: E402
_spec = importlib.util.spec_from_file_location("make_update", ROOT / "dev" / "make_update.py")
_mk = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mk)

check(_mk.app_version() == apply_update.read_version(ROOT),
      "both read the version out of the same VERSION file")
check(_mk.shippable("crud.py") and _mk.shippable("api/main.py"),
      "application files ship")
for rel in (".env", "backups/x.sql", "venv/lib/thing.py", "logs/app.log",
            "tests/test_api_boot.py", "docs/handbook.html", "updates/old.zip"):
    check(not _mk.shippable(rel), f"{rel} does not ship")

check(apply_update.version_tuple("PT-V3.41") > apply_update.version_tuple("PT-V3.40"),
      "3.41 is newer than 3.40")
check(apply_update.version_tuple("PT-V3.9") < apply_update.version_tuple("PT-V3.40"),
      "and 3.40 is newer than 3.9, which a text comparison would get wrong")

shutil.rmtree(pathlib.Path(tempfile.gettempdir()), ignore_errors=True) if False else None

print(f"\n{COUNT - len(FAILURES)}/{COUNT} passed")
if FAILURES:
    print(f"\n{len(FAILURES)} FAILED:")
    for f in FAILURES:
        print(f"  - {f}")
sys.exit(1 if FAILURES else 0)
