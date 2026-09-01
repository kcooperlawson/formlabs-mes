@echo off
setlocal enabledelayedexpansion
cd /d %~dp0

echo ===================================================
echo  Formlabs MES - First-Time Setup on This PC
echo ===================================================
echo.

if not exist .env (
    echo [ERROR] No .env file here - this doesn't look like the unzipped
    echo         move package. Run this from inside that folder.
    pause
    exit /b 1
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

echo [5/6] Checking database host and preparing the database...
for /f "delims=" %%h in ('python _migration_helper.py db_host') do set DB_HOST=%%h
echo     .env points at: %DB_HOST%
if /i not "%DB_HOST%"=="localhost" if /i not "%DB_HOST%"=="127.0.0.1" (
    echo.
    echo     [NOTICE] This is NOT pointing at a local database - it's pointing
    echo     at "%DB_HOST%", which may already be a live, shared database.
    echo     Restoring the backup on top of it could OVERWRITE current data.
    echo.
    choice /c YN /m "     Are you SURE you want to restore the backup into %DB_HOST% now"
    if errorlevel 2 (
        echo     Skipping restore. You can launch the app once you're sure -
        echo     just re-run this script and answer Y, or run it manually:
        echo     python _migration_helper.py restore ^<filename in backups\^>
        goto :launch
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
echo     Schema is up to date.

:launch
echo [6/6] Launching the app...
echo.
echo ===================================================
echo  Setup complete. Starting Formlabs MES...
echo  (Close this window to stop the app later.)
echo ===================================================
streamlit run Home.py
pause
