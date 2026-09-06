@echo off
setlocal enabledelayedexpansion
cd /d %~dp0

echo ===================================================
echo  Formlabs MES - First-Time Setup on This PC
echo ===================================================
echo.

if not exist .env (
    if exist .env.example (
        copy .env.example .env >nul
        echo [NOTICE] No .env here yet - created one from .env.example.
        echo          Open .env in Notepad and set DB_URL to this PC's Postgres
        echo          login before continuing. The line looks like:
        echo            DB_URL=postgresql://postgres:YOURPASSWORD@localhost:5432/formlabs_mes
        echo.
        pause
    ) else (
        echo [ERROR] No .env file and no .env.example - this doesn't look like
        echo         the project folder. Run this from inside it.
        pause
        exit /b 1
    )
)

echo [1/6] Checking for Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo [STOP] Python isn't installed on this PC.
    echo        Install Python 3.11+ from https://www.python.org/downloads/
    echo        - during install, check "Add python.exe to PATH" -
    echo        then run this script again.
    pause
    exit /b 1
)
echo     Found it.

echo [2/6] Setting up the virtual environment...
if not exist venv (
    python -m venv venv
)
call venv\Scripts\activate.bat
python -m pip install --upgrade pip >nul

echo [3/6] Installing dependencies (this can take a few minutes the first time)...
rem If the move package was built with offline packages, install from those
rem first. A work PC often can't reach PyPI - locked-down network, or a proxy
rem pip doesn't know about - and that failure comes minutes into setup with a
rem wall of red text. Falls back to a normal download if the local copies are
rem missing or were built for a different Python version.
set USED_OFFLINE=
if exist wheels (
    echo     Found offline packages in wheels\ - installing without the network...
    pip install --no-index --find-links=wheels -r requirements.txt
    if errorlevel 1 (
        echo     [NOTICE] Offline install didn't work here - most likely these
        echo              packages were built for a different Python version.
        echo              Falling back to downloading from the internet.
    ) else (
        set USED_OFFLINE=1
    )
)
if not defined USED_OFFLINE (
    pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo [ERROR] Installing requirements.txt failed - see the error above.
        echo         If this PC has no internet access for pip, re-run
        echo         Move_To_New_PC.bat on the old PC and answer Y when it
        echo         offers to include the offline packages.
        pause
        exit /b 1
    )
)
if exist requirements-device-gateway.txt (
    pip install -r requirements-device-gateway.txt
    if errorlevel 1 (
        echo     [WARNING] Device Gateway extras failed to install - the main
        echo               app will still run fine, just without machine
        echo               integration until this is resolved.
    )
)

echo [4/6] Checking for the PostgreSQL command-line tools (psql / pg_dump)...
python _migration_helper.py check_pg_cli
if errorlevel 1 (
    echo.
    echo [STOP] PostgreSQL doesn't appear to be installed on this PC yet.
    echo        This app needs a local Postgres server here, matching the
    echo        one it used on the old PC.
    echo.
    echo        1. Install PostgreSQL from https://www.postgresql.org/download/
    echo           and remember the password you set for the "postgres" user.
    echo        2. Open the .env file in this folder and update DB_URL (and
    echo           PG_PASS, if used) so the password matches what you just set.
    echo        3. Run this script again.
    echo.
    echo        (If PostgreSQL installs to a non-default folder, also set
    echo        PG_BIN_DIR in .env to its "bin" folder, e.g.
    echo        PG_BIN_DIR=C:\Program Files\PostgreSQL\18\bin )
    pause
    exit /b 1
)
echo     Found psql and pg_dump.

echo [5/6] Preparing the database...
python _migration_helper.py ensure_db
if errorlevel 1 (
    echo.
    echo [ERROR] Couldn't reach the Postgres server or create the database.
    echo         Double-check .env's DB_URL / PG_PASS match this PC's
    echo         Postgres installation, and that the Postgres service is
    echo         running (services.msc -^> postgresql-x64-...).
    pause
    exit /b 1
)

rem A backup in backups\ is an OFFER, not a requirement. A plant starting
rem fresh should start fresh: the app builds its own schema on first run and
rem seeds one administrator account, three placeholder pumps and the downtime
rem reasons, and the real pumps and people get entered from the console. The
rem restore path exists for moving an established database between machines,
rem and it asks before it does anything, because restoring over a database
rem that is already in use replaces it.
set LATEST_DUMP=
for /f "delims=" %%f in ('dir /b /o-d "backups\*.sql" 2^>nul') do (
    if not defined LATEST_DUMP set LATEST_DUMP=%%f
)
if not defined LATEST_DUMP (
    echo     No database backup in backups\ - starting clean.
    set CLEAN_START=1
    goto :schema
)

echo.
echo     A database backup is included: %LATEST_DUMP%
echo.
echo       R = Restore it into this PC's database ^(brings across every log,
echo           account and setting from the PC it was taken on^)
echo       C = Start Clean ^(empty database; one administrator account^)
echo.
choice /c RC /m "     Restore the backup, or start clean"
if errorlevel 2 (
    echo     Starting clean. The backup stays in backups\ if you want it later:
    echo       python _migration_helper.py restore %LATEST_DUMP%
    set CLEAN_START=1
    goto :schema
)

for /f "delims=" %%h in ('python _migration_helper.py db_host') do set DB_HOST=%%h
if /i not "%DB_HOST%"=="localhost" if /i not "%DB_HOST%"=="127.0.0.1" (
    echo.
    echo     [NOTICE] .env is NOT pointing at a local database - it points at
    echo     "%DB_HOST%", which may be a live, shared database. Restoring the
    echo     backup on top of it would OVERWRITE whatever is there now.
    echo.
    choice /c YN /m "     Are you SURE you want to restore into %DB_HOST%"
    if errorlevel 2 (
        echo     Skipping the restore. Starting clean instead.
        set CLEAN_START=1
        goto :schema
    )
)

python _migration_helper.py check_dump_compat "%LATEST_DUMP%"
if errorlevel 1 (
    echo.
    echo [STOP] The PostgreSQL installed on this PC is OLDER than the one the
    echo        backup came from, and cannot read this dump. The restore would
    echo        fail partway through with a message about an "invalid command"
    echo        that says nothing about the real problem.
    echo.
    echo        Install a PostgreSQL at least as new as the version shown
    echo        above from https://www.postgresql.org/download/windows/
    echo        then run this script again - or run it again and choose C.
    pause
    exit /b 1
)

echo     Restoring %LATEST_DUMP% ...
python _migration_helper.py restore "%LATEST_DUMP%"
if errorlevel 1 (
    echo.
    echo [ERROR] Restore failed - check the logs\ folder for the exact
    echo         Postgres error ^(often a password mismatch in .env^). The
    echo         restore stops on the FIRST real error rather than skipping
    echo         bad tables, so whatever is in the logs is the problem.
    pause
    exit /b 1
)
echo     Database restored.

:schema
echo     Bringing the database schema up to date...
rem Deliberately NOT "alembic stamp head". A restored dump carries its own
rem alembic_version, and "stamp" would overwrite that with head without
rem running anything - silently skipping every migration added since the
rem dump was taken, invisible until something touches a column that was
rem never created.
rem
rem Importing crud runs the same boot the app itself runs: an empty database
rem gets every migration and the seed accounts; a restored one gets only the
rem migrations it is missing; one from before Alembic existed is stamped at
rem the baseline and then brought forward. All three are tested, in separate
rem processes, by tests\test_boot_paths.py.
python -c "import crud"
if errorlevel 1 (
    echo.
    echo [ERROR] Could not build or update the database schema - see logs\.
    pause
    exit /b 1
)
echo     Schema is up to date.

:launch
    )
)

python _migration_helper.py ensure_db
if errorlevel 1 (
    echo.
    echo [ERROR] Couldn't reach the Postgres server or create the database.
    echo         Double-check .env's DB_URL / PG_PASS match this PC's
    echo         Postgres installation, and that the Postgres service is
    echo         running (services.msc -^> postgresql-x64-...).
    pause
    exit /b 1
)

set LATEST_DUMP=
for /f "delims=" %%f in ('dir /b /o-d "backups\*.sql" 2^>nul') do (
    if not defined LATEST_DUMP set LATEST_DUMP=%%f
)
if not defined LATEST_DUMP (
    echo.
    echo [ERROR] No .sql backup found in the backups\ folder - this package
    echo         may not have been built with Move_To_New_PC.bat.
    pause
    exit /b 1
)
python _migration_helper.py check_dump_compat "%LATEST_DUMP%"
if errorlevel 1 (
    echo.
    echo [STOP] The PostgreSQL installed on this PC is OLDER than the one the
    echo        backup came from, and cannot read this dump. The restore would
    echo        fail partway through with a message about an "invalid command"
    echo        that says nothing about the real problem.
    echo.
    echo        Install a PostgreSQL at least as new as the version shown
    echo        above from https://www.postgresql.org/download/windows/
    echo        then run this script again.
    pause
    exit /b 1
)

echo     Restoring %LATEST_DUMP% ...
python _migration_helper.py restore "%LATEST_DUMP%"
if errorlevel 1 (
    echo.
    echo [ERROR] Restore failed - check the logs\ folder for the exact
    echo         Postgres error ^(often a password mismatch in .env^) - the
    echo         restore now stops on the FIRST real error instead of
    echo         silently skipping bad tables, so whatever's in the logs
    echo         is the actual problem to fix.
    pause
    exit /b 1
)
echo     Database restored successfully.

echo     Bringing the restored database's schema up to date...
rem Deliberately NOT "alembic stamp head". pg_dump includes the
rem alembic_version table, so the restored database already knows which
rem migration it was on - and "stamp" would OVERWRITE that with head
rem without running anything, silently skipping every migration added
rem since the dump was taken. That is invisible until something touches a
rem column that was never created.
rem
rem crud.init_db() is the same code path the app itself runs on boot and
rem already handles all three cases: a restored database that carries a
rem version (upgrade only what's missing), one from before Alembic existed
rem (stamp at baseline), and an empty one (run everything).
python -c "import crud; crud.init_db()"
if errorlevel 1 (
    echo.
    echo [ERROR] Could not apply database migrations - see logs\ for details.
    echo         The data restored fine; the schema just isn't caught up, so
    echo         the app may fail on a screen that uses a newer column.
    pause
    exit /b 1
)

rem The restore said it worked. This checks whether it did. Every backup
rem carries a manifest of the row counts at the moment it was taken, and this
rem counts the same tables here and prints both columns. A dump truncated
rem while copying, a restore that ran against the wrong database, a table
rem that failed while the rest went through - none of those announce
rem themselves, and the first sign is a month with a hole in it.
echo.
echo     Checking the data actually came across...
python _migration_helper.py verify_restore "%LATEST_DUMP%"
if errorlevel 1 (
    echo.
    echo [STOP] The restored database has fewer rows than the backup said it
    echo        should. Do NOT start logging on this PC yet - the machine the
    echo        backup came from still has the data, so nothing is lost as
    echo        long as nothing new is written here first.
    echo.
    echo        Re-copy the backup file and run this script again; a dump
    echo        truncated during the copy is the usual cause.
    pause
    exit /b 1
)
echo     Schema is up to date.

:launch
echo [6/6] Launching the app...
echo.
echo ===================================================
echo  Setup complete.
if defined CLEAN_START (
    echo.
    echo  This is a clean database. Sign in with:
    echo      username:  manager
    echo      PIN:       admin
    echo  and do these first, from IT Admin:
    echo    1. Change that PIN ^(Account ^& Preferences, top of the sidebar^).
    echo    2. Replace the three placeholder pumps with the real ones.
    echo    3. Add the operators.
    echo  Day to day, start the app with run_mes.bat.
)
echo.
echo  Starting... close this window to stop the app.
echo ===================================================
streamlit run Home.py
pause
