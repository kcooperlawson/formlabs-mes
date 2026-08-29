import os
import subprocess
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads", "cleanliness")
AVATAR_DIR = os.path.join(BASE_DIR, "uploads", "avatars")
BACKUP_DIR = os.path.join(BASE_DIR, "backups")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(AVATAR_DIR, exist_ok=True)
os.makedirs(BACKUP_DIR, exist_ok=True)

def create_database_backup() -> str:
    filename = f"mes_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sql"
    env = os.environ.copy()

    # Strictly pulling from .env, no fallback!
    env["PGPASSWORD"] = os.getenv("PG_PASS")

    try:
        subprocess.run(
            [r"C:\Program Files\PostgreSQL\18\bin\pg_dump.exe", "-U", "postgres", "-h", "localhost", "-p", "5432", "-d",
             "formlabs_mes", "-f", os.path.join(BACKUP_DIR, filename)], env=env, check=True)
        return filename
    except Exception:
        return None

def restore_database_backup(filename: str) -> bool:
    env = os.environ.copy()

    # Strictly pulling from .env, no fallback!
    env["PGPASSWORD"] = os.getenv("PG_PASS")

    try:
        subprocess.run(
            [r"C:\Program Files\PostgreSQL\18\bin\psql.exe", "-U", "postgres", "-h", "localhost", "-p", "5432", "-d",
             "formlabs_mes", "-f", os.path.join(BACKUP_DIR, filename)], env=env, check=True)
        return True
    except Exception:
        return False