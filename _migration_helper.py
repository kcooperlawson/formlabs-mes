"""
_migration_helper.py - Backs and restores the Formlabs MES database when
moving the project to a different PC.

Deliberately reuses utils.py's create_database_backup() / restore_database_backup()
instead of re-implementing pg_dump/psql argument handling here — those
functions already derive host/user/port/dbname/password from this
machine's own .env (DB_URL), which is exactly the credential source that
needs to be correct on whichever PC this script is run on.

Called by Move_To_New_PC.bat (on the OLD pc) and Setup_On_New_PC.bat
(on the NEW pc). Not meant to be run by hand, but it's safe to:
    python _migration_helper.py backup
    python _migration_helper.py ensure_db
    python _migration_helper.py restore <filename_in_backups_folder>
    python _migration_helper.py db_host
    python _migration_helper.py check_dump_compat <filename_in_backups_folder>
"""
import sys


def cmd_backup():
    from utils import create_database_backup
    filename = create_database_backup()
    if filename:
        print(f"BACKUP_OK:{filename}")
        return 0
    print("BACKUP_FAILED")
    return 1


def cmd_ensure_db():
    """Creates the target database on this machine's Postgres server if it
    doesn't already exist. Connects to the server's default 'postgres'
    maintenance database to do it, using the same connection details
    utils.py already resolves from DB_URL."""
    import psycopg2
    from utils import _get_db_connection_params

    params = _get_db_connection_params()
    if not params or not params["dbname"]:
        print("ENSURE_DB_FAILED: DB_URL is missing or unparseable in .env")
        return 1

    try:
        admin_conn = psycopg2.connect(
            dbname="postgres", user=params["user"], password=params["password"],
            host=params["host"], port=params["port"],
        )
        admin_conn.autocommit = True
        cur = admin_conn.cursor()
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (params["dbname"],))
        exists = cur.fetchone() is not None
        if not exists:
            # Identifiers can't be parameterized — dbname comes from our own
            # .env, not user input, so this is safe.
            cur.execute(f'CREATE DATABASE "{params["dbname"]}"')
            print(f"ENSURE_DB_OK:created:{params['dbname']}")
        else:
            print(f"ENSURE_DB_OK:existed:{params['dbname']}")
        cur.close()
        admin_conn.close()
        return 0
    except Exception as e:
        print(f"ENSURE_DB_FAILED: {e}")
        return 1


def cmd_restore(filename: str):
    from utils import restore_database_backup
    ok = restore_database_backup(filename)
    print("RESTORE_OK" if ok else "RESTORE_FAILED")
    return 0 if ok else 1


def cmd_check_pg_cli():
    """Checks whether the psql/pg_dump command-line tools are actually
    reachable (via PG_BIN_DIR in .env, same as utils.py resolves, or PATH).
    This is separate from whether the Postgres *server* is reachable —
    psycopg2 (used by ensure_db) talks the wire protocol directly and
    doesn't need these binaries at all, but restore_database_backup()
    shells out to psql, so this needs to pass before that step will work."""
    import os
    import shutil
    from utils import _get_pg_bin
    ok = True
    for tool in ("psql", "pg_dump"):
        resolved = _get_pg_bin(tool)
        # _get_pg_bin() returns a real path when PG_BIN_DIR is set, or the
        # bare command name as a last-resort fallback when it can't resolve
        # one — in that fallback case it needs a fresh PATH check here,
        # since the earlier failed shutil.which() inside _get_pg_bin() is
        # exactly why it fell back to the bare name in the first place.
        if os.path.isabs(resolved):
            found = os.path.isfile(resolved)
        else:
            found = shutil.which(resolved) is not None
        print(f"{'OK' if found else 'MISSING'}:{tool}:{resolved}")
        if not found:
            ok = False
    return 0 if ok else 1


def cmd_check_dump_compat(filename: str):
    """Refuses a restore that this PC's psql is too old to read.

    pg_dump writes a plain-SQL dump that assumes a server at least as new as
    the one it came from. PostgreSQL 18's pg_dump emits the \\restrict meta-
    command and SET transaction_timeout; hand that file to a psql from 16 and
    it dies on line 5 with "invalid command \\restrict", which says nothing
    at all about the actual problem — the version gap.

    So compare the two before spending several minutes on a restore that
    cannot work, and say plainly what to install.
    """
    import os
    import re
    import subprocess
    from utils import _get_pg_bin

    path = filename if os.path.isabs(filename) else os.path.join("backups", filename)
    dump_major = None
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for _ in range(40):                      # the header is at the top
                line = fh.readline()
                if not line:
                    break
                m = re.search(r"Dumped from database version (\d+)", line)
                if m:
                    dump_major = int(m.group(1))
                    break
    except OSError as e:
        print(f"DUMP_COMPAT_UNKNOWN: could not read {path}: {e}")
        return 0                                     # don't block on this alone

    if dump_major is None:
        print("DUMP_COMPAT_UNKNOWN: no version header in the dump")
        return 0

    try:
        out = subprocess.check_output([_get_pg_bin("psql"), "--version"],
                                      text=True, stderr=subprocess.STDOUT)
        local_major = int(re.search(r"(\d+)", out.split()[-1]).group(1))
    except Exception as e:
        print(f"DUMP_COMPAT_UNKNOWN: could not read psql version: {e}")
        return 0

    if local_major < dump_major:
        print(f"DUMP_COMPAT_FAILED:{dump_major}:{local_major}")
        return 1
    print(f"DUMP_COMPAT_OK:dump={dump_major}:local={local_major}")
    return 0


def cmd_db_host():
    """Prints just the DB_URL host, so the calling batch script can decide
    whether this looks like a local Postgres server (the expected case when
    moving to a fresh PC) or a shared/remote one (where blindly restoring a
    dump on top of it could clobber live data both PCs already share)."""
    from utils import _get_db_connection_params
    params = _get_db_connection_params()
    print(params["host"] if params else "UNKNOWN")


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command == "backup":
        sys.exit(cmd_backup())
    elif command == "ensure_db":
        sys.exit(cmd_ensure_db())
    elif command == "restore":
        if len(sys.argv) < 3:
            print("RESTORE_FAILED: no filename given")
            sys.exit(1)
        sys.exit(cmd_restore(sys.argv[2]))
    elif command == "db_host":
        cmd_db_host()
        sys.exit(0)
    elif command == "check_pg_cli":
        sys.exit(cmd_check_pg_cli())
    elif command == "check_dump_compat":
        if len(sys.argv) < 3:
            print("DUMP_COMPAT_UNKNOWN: no filename given")
            sys.exit(0)
        sys.exit(cmd_check_dump_compat(sys.argv[2]))
    else:
        print(f"Unknown command: {command!r}")
        sys.exit(1)
