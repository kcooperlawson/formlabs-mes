

import os
import subprocess
import shutil
import base64
from dotenv import load_dotenv
from sqlalchemy.engine import make_url
import streamlit as st
from datetime import datetime, timedelta
from app_logger import logger

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads", "cleanliness")
AVATAR_DIR = os.path.join(BASE_DIR, "uploads", "avatars")
BACKUP_DIR = os.path.join(BASE_DIR, "backups")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(AVATAR_DIR, exist_ok=True)
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
    Otherwise assumes the bare command is on PATH, which is the normal case
    on Linux/Mac and in most server/container deployments.
    """
    exe_name = f"{binary_name}.exe" if os.name == "nt" else binary_name
    bin_dir = os.getenv("PG_BIN_DIR", "").strip()
    if bin_dir:
        return os.path.join(bin_dir, exe_name)
    resolved = shutil.which(exe_name)
    return resolved or exe_name


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
             "-d", params["dbname"], "-f", os.path.join(BACKUP_DIR, filename)],
            env=env, check=True, capture_output=True, text=True)
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
             "-d", params["dbname"], "-f", os.path.join(BACKUP_DIR, filename)],
            env=env, check=True, capture_output=True, text=True)
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"restore_database_backup({filename!r}) failed: psql exited {e.returncode}. stderr: {e.stderr.strip()}")
        return False
    except Exception:
        logger.exception(f"restore_database_backup({filename!r}) failed unexpectedly")
        return False

def do_logout(cookie_manager):
    from crud import delete_session  # local import avoids a circular import with crud.py

    saved_theme = st.session_state.get("preferred_theme", "Default Dark")
    try:
        old_token = cookie_manager.get(cookie="formlabs_mes_token")
        if old_token:
            delete_session(old_token)
        cookie_manager.set("formlabs_mes_token", "", expires_at=datetime.now() - timedelta(days=1))
        cookie_manager.delete("formlabs_mes_token")
    except Exception:
        # Session state is cleared below regardless, so a cookie-manager
        # hiccup here doesn't block the user from logging out — but it's
        # still worth a record in case tokens are failing to revoke server-side.
        logger.exception("do_logout() cookie cleanup failed (user was logged out locally regardless)")

    st.session_state.clear()
    st.session_state["preferred_theme"] = saved_theme
    st.session_state["explicitly_logged_out"] = True


def check_authentication(cookie_manager):
    """Validates the session-token cookie server-side and restores the session if valid.
    Replaces the old per-page 'compare cookie to username' auto-login blocks."""
    if st.session_state.get("authenticated", False):
        return

    from crud import get_user_by_session_token

    cached_token = cookie_manager.get(cookie="formlabs_mes_token")
    user_data = get_user_by_session_token(cached_token)

    if user_data:
        st.session_state.update({
            "authenticated": True,
            "user_id": user_data["id"],
            "user_role": user_data["role"],
            "user_name": user_data["full_name"],
            "user_shift": user_data.get("shift", "Shift 1"),
            "preferred_theme": user_data.get("preferred_theme", "Default Dark"),
            "avatar_filename": user_data.get("avatar_filename"),
        })
        st.rerun()


