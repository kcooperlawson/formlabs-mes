"""
resin_backup.py - Standalone export/import for just the resin_specs table.

Bypasses pg_dump/psql and Alembic entirely - use this when you need to move
ONLY the resin catalog between machines (or fix one machine's copy) without
touching anything else in the database.

Safe to run any time: import upserts by id (INSERT ... ON CONFLICT DO
UPDATE), so it never errors on rows that already exist and never creates
duplicates - re-running it is harmless.

Usage:
    python resin_backup.py export
        Writes resin_backups/resin_specs_<timestamp>.json with every row
        currently in resin_specs on THIS machine.

    python resin_backup.py import <filename>
        Upserts every row from that file into resin_specs on THIS machine's
        database (whatever DB_URL in .env points to). Fixes the id sequence
        afterward so new resins added later through the app don't collide
        with a restored id.
"""
import sys
import os
import json
from datetime import datetime

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import create_engine, MetaData, text
from sqlalchemy.dialects.postgresql import insert as pg_insert

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKUP_DIR = os.path.join(BASE_DIR, "resin_backups")


def _get_table(engine):
    meta = MetaData()
    meta.reflect(bind=engine, only=["resin_specs"])
    return meta.tables["resin_specs"]


def cmd_export():
    engine = create_engine(os.getenv("DB_URL"))
    table = _get_table(engine)
    with engine.connect() as conn:
        rows = [dict(r._mapping) for r in conn.execute(table.select().order_by(table.c.id))]

    os.makedirs(BACKUP_DIR, exist_ok=True)
    filename = f"resin_specs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    path = os.path.join(BACKUP_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2, default=str)

    print(f"Exported {len(rows)} resin_specs rows to {path}")
    print("Copy that one file into the other PC's resin_backups\\ folder, then run:")
    print(f"    .\\venv\\Scripts\\python.exe resin_backup.py import {filename}")


def cmd_import(filename: str):
    path = filename if os.path.isabs(filename) else os.path.join(BACKUP_DIR, filename)
    if not os.path.exists(path):
        # also check current directory, in case it wasn't dropped into resin_backups\
        alt = os.path.join(BASE_DIR, filename)
        if os.path.exists(alt):
            path = alt
        else:
            print(f"File not found: {path}")
            sys.exit(1)

    with open(path, "r", encoding="utf-8") as f:
        rows = json.load(f)

    engine = create_engine(os.getenv("DB_URL"))
    table = _get_table(engine)

    with engine.begin() as conn:
        before = conn.execute(text("SELECT count(*) FROM resin_specs")).scalar()
        for row in rows:
            stmt = pg_insert(table).values(**row)
            update_cols = {c.name: stmt.excluded[c.name] for c in table.columns if c.name != "id"}
            stmt = stmt.on_conflict_do_update(index_elements=["id"], set_=update_cols)
            conn.execute(stmt)

        conn.execute(text(
            "SELECT setval(pg_get_serial_sequence('resin_specs', 'id'), "
            "(SELECT COALESCE(MAX(id), 1) FROM resin_specs))"
        ))
        after = conn.execute(text("SELECT count(*) FROM resin_specs")).scalar()

    print(f"Imported {len(rows)} rows from {path}")
    print(f"resin_specs row count: {before} -> {after}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python resin_backup.py export | import <filename>")
        sys.exit(1)

    command = sys.argv[1]
    if command == "export":
        cmd_export()
    elif command == "import":
        if len(sys.argv) < 3:
            print("Usage: python resin_backup.py import <filename>")
            sys.exit(1)
        cmd_import(sys.argv[2])
    else:
        print(f"Unknown command: {command!r}")
        sys.exit(1)
