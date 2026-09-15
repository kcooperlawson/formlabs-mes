

import os
import time
import glob
import subprocess
import shutil
import base64
from dotenv import load_dotenv, set_key
from sqlalchemy.engine import make_url
from datetime import datetime
from app_logger import logger

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads", "cleanliness")
AVATAR_DIR = os.path.join(BASE_DIR, "uploads", "avatars")
LOT_PHOTO_DIR = os.path.join(BASE_DIR, "uploads", "lot_labels")


def esc(value) -> str:
    """Escape a value before it goes into a raw-HTML block.

    Anywhere the app renders with `unsafe_allow_html=True`, an f-string drops
    database values straight into markup. Most of those values are typed by
    people on the floor - operator names, note fields, chat messages, lot
    codes - so they have to be escaped on the way in. Two reasons, and the
    second one bites more often than the first:

      1. Security. Unescaped input rendered as HTML is a cross-site scripting
         hole, even on an internal plant tool.
      2. Layout. A note containing "<" or "&" currently breaks the card it is
         rendered in, on whoever's screen happens to load it.

    None turns into an empty string rather than the text "None".

    Only for raw-HTML blocks. Streamlit already escapes HTML in normal
    st.markdown / st.caption calls, so escaping there would show the entity
    codes to the user instead.
    """
    import html as _html
    if value is None:
        return ""
    return _html.escape(str(value), quote=True)
BACKUP_DIR = os.path.join(BASE_DIR, "backups")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(AVATAR_DIR, exist_ok=True)
os.makedirs(LOT_PHOTO_DIR, exist_ok=True)
os.makedirs(BACKUP_DIR, exist_ok=True)


def get_avatar_path(avatar_filename: str | None) -> str | None:
    """Resolves a stored avatar_filename to an absolute path on disk, or
    None if there is no filename on record or the file is missing (deleted,
    moved, or never actually saved). Callers should always treat None as
    "fall back to a default/emoji avatar" rather than erroring."""
    if not avatar_filename:
        return None
    path = os.path.join(AVATAR_DIR, avatar_filename)
    return path if os.path.isfile(path) else None


def get_avatar_data_uri(avatar_filename: str | None) -> str | None:
    """Same lookup as get_avatar_path(), but returns a base64 data: URI
    instead of a filesystem path. Needed anywhere an avatar has to be
    embedded inside raw HTML (st.markdown(..., unsafe_allow_html=True))
    rather than passed to a Streamlit widget like st.image/st.chat_message
    that can take a path directly."""
    path = get_avatar_path(avatar_filename)
    if not path:
        return None
    ext = os.path.splitext(path)[1].lstrip(".").lower() or "png"
    mime = "jpeg" if ext == "jpg" else ext
    try:
        with open(path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode()
        return f"data:image/{mime};base64,{encoded}"
    except Exception:
        logger.exception(f"get_avatar_data_uri() failed to read {path!r}")
        return None


def _get_pg_bin(binary_name: str) -> str:
    """Resolves the pg_dump/psql executable path.

    Uses PG_BIN_DIR from .env if set — needed on Windows, where these tools
    usually aren't on PATH (e.g. PG_BIN_DIR=C:\\Program Files\\PostgreSQL\\18\\bin).
    Falls back to PATH, which is the normal case on Linux/Mac and in most
    server/container deployments.

    If neither finds it and this is Windows, scans the Postgres installer's
    own standard install location (C:\\Program Files\\PostgreSQL\\<version>\\bin)
    instead of just failing — that's where it lives on the overwhelming
    majority of Windows installs, PATH or no PATH, and there was previously
    no fallback for this at all: any Windows machine without PG_BIN_DIR set
    by hand had backup/restore silently broken (FileNotFoundError) with no
    guidance on what to fix. When the scan finds it, persists it to .env's
    PG_BIN_DIR so this only has to happen once per machine.
    """
    exe_name = f"{binary_name}.exe" if os.name == "nt" else binary_name
    bin_dir = os.getenv("PG_BIN_DIR", "").strip()
    if bin_dir:
        candidate = os.path.join(bin_dir, exe_name)
        if os.path.isfile(candidate):
            return candidate
        # A stale or malformed PG_BIN_DIR (a doubled backslash pasted in by
        # hand, a version that got uninstalled, ...) used to be trusted
        # forever and break every backup/restore with a bare WinError 2 and
        # no hint why. Falling through to re-detect instead means a bad
        # value heals itself the next time this runs, rather than staying
        # broken until somebody finds this exact line of code.
        logger.warning(
            f"_get_pg_bin() PG_BIN_DIR={bin_dir!r} in .env does not contain "
            f"{exe_name} - ignoring it and re-detecting PostgreSQL"
        )

    resolved = shutil.which(exe_name)
    if resolved:
        return resolved

    if os.name == "nt":
        candidates = sorted(
            glob.glob(os.path.join("C:\\Program Files\\PostgreSQL", "*", "bin", exe_name)),
            reverse=True,  # prefer the newest version if more than one is installed
        )
        if candidates:
            found_path = candidates[0]
            # Forward slashes rather than os.path.dirname()'s native
            # backslashes: Windows file APIs accept '/' fine, and it sidesteps
            # python-dotenv's own quoting/escaping of '\\' on write - which is
            # exactly what corrupted this value once already (a persisted
            # "C:\Program Files\..." came back out with doubled backslashes
            # and stray quotes, and broke pg_dump for good until someone
            # noticed this comment).
            found_dir = os.path.dirname(found_path).replace("\\", "/")
            try:
                env_path = os.path.join(BASE_DIR, ".env")
                if os.path.exists(env_path):
                    set_key(env_path, "PG_BIN_DIR", found_dir)
                    os.environ["PG_BIN_DIR"] = found_dir
                    logger.info(f"_get_pg_bin() auto-detected PostgreSQL at {found_dir!r} and saved it to .env")
            except Exception:
                logger.exception("_get_pg_bin() found PostgreSQL but couldn't persist PG_BIN_DIR to .env")
            return found_path

    return exe_name


def _get_db_connection_params():
    """Derives host/port/user/dbname/password from DB_URL — the same
    variable db_core.py already uses to connect the app itself — instead of
    the previous hardcoded 'localhost' / 'postgres' / 'formlabs_mes', which
    would silently back up (or restore into!) the wrong database the moment
    DB_URL pointed anywhere other than the original default setup."""
    db_url = os.getenv("DB_URL")
    if not db_url:
        return None
    try:
        url = make_url(db_url)
    except Exception:
        return None
    return {
        "user": url.username or "postgres",
        "host": url.host or "localhost",
        "port": str(url.port or 5432),
        "dbname": url.database or "",
        "password": url.password,
    }


def create_database_backup() -> str:
    filename = f"mes_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sql"
    params = _get_db_connection_params()
    if not params or not params["dbname"]:
        logger.error("create_database_backup() aborted: DB_URL is missing or unparseable")
        return None

    env = os.environ.copy()
    # Prefer the password embedded in DB_URL (the actual connection Home.py
    # uses); fall back to PG_PASS for setups that keep it separate. Never a
    # hardcoded default.
    env["PGPASSWORD"] = params["password"] or os.getenv("PG_PASS", "")

    try:
        subprocess.run(
            [_get_pg_bin("pg_dump"), "-U", params["user"], "-h", params["host"], "-p", params["port"],
             "-d", params["dbname"],
             # --clean + --if-exists: the dump includes "DROP TABLE IF EXISTS ..."
             # before every CREATE TABLE, so restoring onto a target database
             # that already has some (or all) of these tables/rows - a partially
             # seeded DB, a previous failed restore, whatever - drops and
             # replaces them cleanly instead of erroring out on "already exists"
             # and silently skipping that table's data.
             "--clean", "--if-exists", "--no-owner", "--no-privileges",
             "-f", os.path.join(BACKUP_DIR, filename)],
            env=env, check=True, capture_output=True, text=True)
        # Beside the dump, what was in the database when it was taken - so a
        # restore on another machine can be checked rather than assumed.
        write_backup_manifest(filename)
        return filename
    except subprocess.CalledProcessError as e:
        # capture_output=True above means e.stderr actually has pg_dump's real
        # complaint (wrong password, host unreachable, permission denied,
        # ...) instead of this just failing with no explanation anywhere.
        logger.error(f"create_database_backup() failed: pg_dump exited {e.returncode}. stderr: {e.stderr.strip()}")
        return None
    except Exception:
        logger.exception("create_database_backup() failed unexpectedly")
        return None

MANIFEST_SUFFIX = ".manifest.json"

# What gets counted into a manifest. Deliberately the tables somebody would
# ask about after a move - "did the logs come across, are my people there" -
# rather than every table, because a wall of numbers is not reassurance.
MANIFEST_TABLES = (
    ("production_logs", "ProductionLog"),
    ("downtime_logs", "DowntimeLog"),
    ("lot_verifications", "LotVerification"),
    ("daily_checklists", "DailyChecklist"),
    ("cleanliness_audits", "CleanlinessAudit"),
    ("assigned_runs", "AssignedRun"),
    ("users", "User"),
    ("pump_stations", "PumpStation"),
    ("reactors", "Reactor"),
    ("resin_specs", "ResinSpec"),
)


def database_manifest() -> dict:
    """Row counts and the newest log, as they stand right now.

    Written beside every backup and compared after every restore. "Database
    restored successfully" is pg_dump's opinion of its own exit code; this is
    the thing that actually answers the question somebody moving a plant to a
    new machine is asking, which is whether their data is there.
    """
    from datetime import datetime
    import models
    from db_core import ScopedSession
    from sqlalchemy import func

    session = ScopedSession()
    try:
        counts = {}
        for label, model_name in MANIFEST_TABLES:
            model = getattr(models, model_name, None)
            if model is None:
                continue
            try:
                counts[label] = int(session.query(func.count(model.id)).scalar() or 0)
            except Exception:
                logger.exception(f"database_manifest() could not count {label}")
        newest = None
        try:
            value = session.query(func.max(models.ProductionLog.timestamp)).scalar()
            newest = value.isoformat() if value else None
        except Exception:
            pass
        return {"taken_at": datetime.now().isoformat(timespec="seconds"),
                "counts": counts, "newest_log": newest}
    finally:
        session.close()


def write_backup_manifest(dump_filename: str) -> str:
    """Record what was in the database at the moment this dump was taken."""
    import json
    try:
        manifest = database_manifest()
        manifest["backup"] = dump_filename
        path = os.path.join(BACKUP_DIR, dump_filename + MANIFEST_SUFFIX)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
        return path
    except Exception:
        # A manifest is a convenience; a backup without one is still a backup,
        # and failing the dump over this would be the wrong trade entirely.
        logger.exception("write_backup_manifest() failed")
        return ""


def read_backup_manifest(dump_filename: str) -> dict:
    """The manifest beside a dump, or an empty dict if it has none."""
    import json
    path = os.path.join(BACKUP_DIR, dump_filename + MANIFEST_SUFFIX)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def list_backup_files() -> list:
    """Every filename in the backup folder, ours or not."""
    try:
        return sorted(os.listdir(BACKUP_DIR))
    except OSError:
        logger.exception("list_backup_files() could not read the backup folder")
        return []


def prune_old_backups(keep: int = None) -> int:
    """Delete all but the most recent few of our own dumps.

    Only files matching this application's own naming are ever considered -
    backup_policy decides which, and anything else in that folder is somebody
    else's and is left alone. Returns how many were removed.
    """
    from backup_policy import KEEP_BACKUPS, backups_to_prune
    removed = 0
    for name in backups_to_prune(list_backup_files(), KEEP_BACKUPS if keep is None else keep):
        try:
            os.remove(os.path.join(BACKUP_DIR, name))
            removed += 1
        except OSError:
            logger.exception(f"prune_old_backups() could not delete {name!r}")
        # The manifest belongs to that dump and is meaningless without it.
        try:
            os.remove(os.path.join(BACKUP_DIR, name + MANIFEST_SUFFIX))
        except OSError:
            pass
    return removed


def run_scheduled_backup(force: bool = False) -> str:
    """Take a backup if one is due, prune the old ones, and say what happened.

    Called on an ordinary page load rather than from a scheduler, because
    there is no scheduler on a plant PC and adding one is a second thing to
    install and forget. The application is open all day; asking "is the
    newest backup a day old" each time somebody opens a screen gets a daily
    backup out of a machine that is used daily, and no backups out of a
    machine nobody has switched on - which is the correct answer in both
    cases.

    Returns the filename if one was taken, otherwise None. Never raises: a
    failed backup must not be able to stop an operator logging an hour.

    Guarded by MES_DISABLE_AUTO_BACKUP the same way api/backup_scheduler.py's
    equivalent check is: BACKUP_DIR is a fixed path independent of DB_URL, so
    running this app against a scratch/dev database still writes into and
    prunes the SAME real backup rotation as production. That mismatch is
    exactly what caused a real incident (three genuine backups pruned by a
    dev session pointed at a test database) - this is the fix, on the one
    code path both the Streamlit app and the API's own scheduler now share.
    """
    if os.environ.get("MES_DISABLE_AUTO_BACKUP"):
        return None
    from backup_policy import is_backup_due
    try:
        if not force and not is_backup_due(list_backup_files()):
            return None
        filename = create_database_backup()
        if filename:
            pruned = prune_old_backups()
            logger.info(f"scheduled backup taken: {filename}"
                        + (f"; {pruned} older removed" if pruned else ""))
        else:
            # Worth a line in the log even though the caller carries on: a
            # backup that silently never happens is the whole failure this
            # was built to end.
            logger.error("scheduled backup was due but create_database_backup() failed")
        return filename
    except Exception:
        logger.exception("run_scheduled_backup() failed unexpectedly")
        return None


def restore_database_backup(filename: str) -> bool:
    params = _get_db_connection_params()
    if not params or not params["dbname"]:
        logger.error("restore_database_backup() aborted: DB_URL is missing or unparseable")
        return False

    env = os.environ.copy()
    env["PGPASSWORD"] = params["password"] or os.getenv("PG_PASS", "")

    try:
        subprocess.run(
            [_get_pg_bin("psql"), "-U", params["user"], "-h", params["host"], "-p", params["port"],
             "-d", params["dbname"],
             # ON_ERROR_STOP=1: without this, psql -f prints an error for a
             # failing statement (a duplicate key, a bad COPY block, whatever)
             # and just keeps going through the rest of the file - so one
             # table's data can silently fail to load while everything else
             # looks like it restored fine. With this set, restore_database_backup()
             # actually fails (and logs the real Postgres error below) instead
             # of returning True over a partially-restored database.
             "-v", "ON_ERROR_STOP=1",
             "-f", os.path.join(BACKUP_DIR, filename)],
            env=env, check=True, capture_output=True, text=True)
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"restore_database_backup({filename!r}) failed: psql exited {e.returncode}. stderr: {e.stderr.strip()}")
        return False
    except Exception:
        logger.exception(f"restore_database_backup({filename!r}) failed unexpectedly")
        return False

# set_cookie/flash/draw_flashes/do_logout/check_authentication used to live
# here - the Streamlit UI's own cookie-write timing fix, toast-that-survives-
# a-rerun banner, sign-out sequencing, and session-restore. All five existed
# only because Streamlit reruns the whole page script on every interaction;
# the FastAPI app doesn't have that problem (api/deps.py's get_current_user
# and api/routers/auth.py's login/logout are the real, current versions of
# what these did), and retired along with Home.py/pages/ui_shell.py when the
# Streamlit UI was.


