"""Multiple photos per cleanliness audit: the write path, the rules, and ownership.

The rules are the whole design, and each is easy to break later without
noticing, so they are asserted against the real database and the real
filesystem rather than described in a comment:

  1. **A single photo behaves exactly as before.** Its file lands in
     image_filename, where every existing reader looks, and nothing is in
     the photo table. Nobody notices this change unless this is true.
  2. **Several photos keep the order the operator attached them in:**
     first into the legacy column, the rest into the table.
  3. **Zero photos is still legal** for a routine audit.
  4. **The cap is enforced in one place** (MAX_AUDIT_PHOTOS), and the
     operator sees the same number on their screen.
  5. **An audit owns its photos.** Deleting the audit takes every file it
     wrote with it, and a failed submission takes the files it started
     writing with it. An orphaned photo is a photo nobody can find.
"""
import os
import sys
import types
import warnings

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _boot import boot, ROOT  # noqa: E402

boot(fresh=True)

import crud  # noqa: E402
from db_core import ScopedSession  # noqa: E402
from models import CleanlinessAudit, CleanlinessAuditPhoto  # noqa: E402

CHECKS = 0


def check(cond, label):
    global CHECKS
    assert cond, f"FAILED: {label}"
    CHECKS += 1


def section(title):
    print("\n" + "=" * 66)
    print(title)
    print("=" * 66)


def fake(name, payload):
    """A Streamlit-style uploaded file: a name and a buffer."""
    return types.SimpleNamespace(name=name, getbuffer=lambda: payload)


def photos_on_disk():
    return {f for f in os.listdir(crud.UPLOAD_DIR) if f.startswith("audit_")}


def read_photo(filename):
    with open(os.path.join(crud.UPLOAD_DIR, filename), "rb") as f:
        return f.read()


def audit_with_notes(notes):
    session = ScopedSession()
    try:
        return session.query(CleanlinessAudit).filter(CleanlinessAudit.notes == notes).one()
    finally:
        session.close()


def add_audit(notes, photos):
    return crud.add_cleanliness_audit(
        audit_type="Start Of Shift (Cleanliness Check)", operator_name="Photo Tester",
        pump_station="Pump 1", shift="Shift 1", resin_type="",
        notes=notes, is_spill=False, uploaded_files=photos)


# ------------------------------------------------------------- single --
section("1. ONE PHOTO - THE WAY IT HAS ALWAYS BEEN")
before = photos_on_disk()
add_audit("one photo", [fake("one.png", b"photo-one")])
audit = audit_with_notes("one photo")
new_files = photos_on_disk() - before
check(len(new_files) == 1, "exactly one file landed on disk")
check(audit.image_filename in new_files, "the file is in image_filename, where every reader looks")
check(read_photo(audit.image_filename) == b"photo-one", "the bytes on disk are the operator's")
check(crud.get_cleanliness_audit_photos().get(audit.id, []) == [], "the photo table is empty for this audit")
print("  a single photo is indistinguishable from the old behaviour")

# -------------------------------------------------------------- several --
section("2. SEVERAL PHOTOS - IN THE ORDER ATTACHED")
before = photos_on_disk()
add_audit("three photos", [
    fake("one.jpg", b"photo-1"), fake("two.jpg", b"photo-2"), fake("three.jpg", b"photo-3")])
audit = audit_with_notes("three photos")
extras = crud.get_cleanliness_audit_photos().get(audit.id, [])
check(len(photos_on_disk() - before) == 3, "all three files are on disk")
check(len(extras) == 2, "the first photo is the column, the other two are the table")
check(read_photo(audit.image_filename) == b"photo-1", "photo 1 is the main one")
check([read_photo(f) for f in extras] == [b"photo-2", b"photo-3"], "the extras keep upload order")
print("  first photo leads, the rest follow in the order attached")

# ----------------------------------------------------------------- zero --
section("3. ZERO PHOTOS - A NOTE WITHOUT A PICTURE")
before = photos_on_disk()
add_audit("no photo", [])
audit = audit_with_notes("no photo")
check(audit.image_filename is None, "image_filename is empty, as it was for note-only rows")
check(photos_on_disk() == before, "no file on disk")
check(audit.id not in crud.get_cleanliness_audit_photos(), "no rows in the photo table")
print("  a routine audit with nothing to photograph still writes")

# ------------------------------------------------------------------ cap --
section("4. THE CAP - MORE THAN MAX AUDIT PHOTOS")
before = photos_on_disk()
add_audit("six photos", [fake(f"n{i}.jpg", f"many-{i}".encode()) for i in range(1, 7)])
audit = audit_with_notes("six photos")
kept = photos_on_disk() - before
extras = crud.get_cleanliness_audit_photos().get(audit.id, [])
check(len(kept) == crud.MAX_AUDIT_PHOTOS, f"only {crud.MAX_AUDIT_PHOTOS} files were written")
check(len(extras) == crud.MAX_AUDIT_PHOTOS - 1, "the remainder of the cap is in the table")
check(read_photo(audit.image_filename) == b"many-1", "the first photo is still the main one")
check([read_photo(f) for f in extras] == [b"many-2", b"many-3", b"many-4"], "it is the FIRST four, in order")
check(b"many-5" not in {read_photo(f) for f in kept}, "the extras nobody saw never hit the disk")
print(f"  {crud.MAX_AUDIT_PHOTOS} in, {len(kept)} kept - the rest were never written")

# ------------------------------------------------------------ ownership --
section("5. DELETE - THE AUDIT TAKES ITS PHOTOS WITH IT")
audit = audit_with_notes("three photos")
owned = {audit.image_filename} | set(crud.get_cleanliness_audit_photos().get(audit.id, []))
check(len(owned) == 3, "three owned files before the delete")
check(all(os.path.exists(os.path.join(crud.UPLOAD_DIR, f)) for f in owned), "all of them on disk")
check(crud.delete_cleanliness_audit(audit.id) is True, "the delete succeeds")
check(not any(os.path.exists(os.path.join(crud.UPLOAD_DIR, f)) for f in owned),
      "every owned file is gone afterwards")
session = ScopedSession()
try:
    check(session.query(CleanlinessAudit).filter(CleanlinessAudit.id == audit.id).first() is None,
          "the audit row is gone")
    check(session.query(CleanlinessAuditPhoto).filter(CleanlinessAuditPhoto.audit_id == audit.id).count() == 0,
          "no orphan rows in the photo table")
finally:
    session.close()
check(audit.id not in crud.get_cleanliness_audit_photos(), "the gallery mapping no longer knows it")
print("  the row, its photos in the table, and its files on disk all leave together")

# ----------------------------------------------------------------- fault --
section("6. A FAILED SUBMISSION LEAVES NO FILES BEHIND")

def broken(name="bad.jpg"):
    f = fake(name, b"never-written")
    def blow_up():
        raise ValueError("disk full")
    f.getbuffer = blow_up
    return f

before = photos_on_disk()
# add_cleanliness_audit catches broadly and returns False rather than
# raising - see its own docstring and app_logger.py's: a shop-floor kiosk
# app shouldn't take a page down over a bad upload, the exception is logged
# instead (app_logger writes it to logs/), and the caller is told through
# the return value, the same as every other write in crud.py.
ok = add_audit("should fail", [fake("ok.jpg", b"photo-a"), broken()])
check(ok is False, "the failure is reported to the caller, not raised")
check(photos_on_disk() == before, "the one file that made it to disk was removed again")
session = ScopedSession()
try:
    check(session.query(CleanlinessAudit).filter(CleanlinessAudit.notes == "should fail").count() == 0,
          "no half-written audit row")
finally:
    session.close()
print("  a failed write rolls its own files back, the way it always should have")

section("RESULT")
print(f"ALL {CHECKS} CLEANLINESS PHOTO ASSERTIONS PASSED")
