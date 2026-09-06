@echo off
rem ===================================================================
rem  Install the MES / Logger on this PC.
rem
rem  This PC will run the Streamlit app AND host the PostgreSQL
rem  database. Operators point their phones at it.
rem
rem  Every step is idempotent - running this twice is safe and is the
rem  right move if something failed halfway through.
rem ===================================================================
setlocal
cd /d "%~dp0.."

echo.
echo  ===================================================
echo   INSTALL - MES / Logger
echo  ===================================================
echo.

echo  [1/6] Python...
call "setup\_ensure_python.bat"
if not defined PY_CMD goto :fail_quiet

echo.
echo  [2/6] Virtual environment...
if exist "venv\Scripts\python.exe" goto :venv_ready
%PY_CMD% -m venv venv
if errorlevel 1 goto :fail_venv
:venv_ready
set "VPY=venv\Scripts\python.exe"
"%VPY%" -m pip install --upgrade pip --quiet
echo     Ready.

echo.
echo  [3/6] Dependencies ^(a few minutes the first time^)...
set "USED_OFFLINE="
if not exist "wheels" goto :online
echo     Offline packages found in wheels\ - installing without the network.
"%VPY%" -m pip install --no-index --find-links=wheels -r requirements.txt
if errorlevel 1 goto :offline_failed
set "USED_OFFLINE=1"
"%VPY%" -m pip install --no-index --find-links=wheels -r requirements-device-gateway.txt
goto :deps_done

:offline_failed
echo     [NOTICE] The offline packages don't fit this Python version.
echo              Falling back to downloading from the internet.

:online
"%VPY%" -m pip install -r requirements.txt
if errorlevel 1 goto :fail_deps
if exist "requirements-device-gateway.txt" "%VPY%" -m pip install -r requirements-device-gateway.txt

:deps_done
echo     Installed.

echo.
echo  [4/6] PostgreSQL...
call "setup\_ensure_postgres.bat"
if errorlevel 1 goto :fail_quiet

echo.
echo  [5/6] Database connection and .env...
"%VPY%" "setup\_configure_env.py" mes
if errorlevel 1 goto :fail_env

"%VPY%" _migration_helper.py ensure_db
if errorlevel 1 goto :fail_ensuredb

echo.
echo  [6/6] Schema and data...

rem A backup in backups\ is an OFFER, not a requirement. A plant starting
rem fresh should start fresh: the app builds its own schema on first run
rem and seeds one administrator account, placeholder pumps and the
rem downtime reasons. The restore path is for MOVING an established
rem database between machines, and it asks first, because restoring over
rem a database already in use replaces it.
set "LATEST_DUMP="
for /f "delims=" %%f in ('dir /b /o-d "backups\*.sql" 2^>nul') do (
    if not defined LATEST_DUMP set "LATEST_DUMP=%%f"
)
if not defined LATEST_DUMP goto :clean_start

echo.
echo     A database backup is included:  %LATEST_DUMP%
echo.
echo       R = Restore it  ^(brings across every log, account and setting
echo           from the PC it was taken on^)
echo       C = Start clean ^(empty database, one administrator account^)
echo.
choice /c RC /m "     Restore the backup, or start clean"
if errorlevel 2 goto :clean_start

set "DB_HOST="
for /f "delims=" %%h in ('"%VPY%" _migration_helper.py db_host') do set "DB_HOST=%%h"
if /i "%DB_HOST%"=="localhost" goto :dump_compat
if /i "%DB_HOST%"=="127.0.0.1" goto :dump_compat
echo.
echo     [NOTICE] .env points at "%DB_HOST%", not this PC. That may be a
echo     live, shared database, and restoring would OVERWRITE it.
echo.
choice /c YN /m "     Are you SURE you want to restore into %DB_HOST%"
if errorlevel 2 goto :clean_start

:dump_compat
"%VPY%" _migration_helper.py check_dump_compat "%LATEST_DUMP%"
if errorlevel 1 goto :fail_pgold

echo     Restoring %LATEST_DUMP% ...
"%VPY%" _migration_helper.py restore "%LATEST_DUMP%"
if errorlevel 1 goto :fail_restore
echo     Database restored.
goto :schema

:clean_start
set "CLEAN_START=1"
echo     Starting with a clean database.

:schema
rem Deliberately NOT "alembic stamp head". A restored dump carries its own
rem alembic_version, and "stamp" would overwrite that with head without
rem running anything - silently skipping every migration added since the
rem dump was taken, invisible until something touches a column that was
rem never created.
rem
rem Importing crud runs the same boot the app itself runs: an empty
rem database gets every migration and the seed accounts; a restored one
rem gets only the migrations it is missing; one from before Alembic
rem existed is stamped at the baseline and then brought forward.
echo     Bringing the schema up to date...
"%VPY%" -c "import crud"
if errorlevel 1 goto :fail_schema
echo     Schema is up to date.

echo.
echo  ===================================================
echo   DONE - this PC is set up as the MES / Logger.
echo  ===================================================
if not defined CLEAN_START goto :addr
echo.
echo   Clean database. Sign in with:
echo       username:  manager
echo       PIN:       admin
echo   Then, from IT Admin:
echo     1. Change that PIN ^(Account ^& Preferences, top of sidebar^).
echo     2. Replace the placeholder pumps with the real ones.
echo     3. Add the operators.

:addr
echo.
"%VPY%" "setup\_preflight.py" --address-only
echo.
echo   Day to day: run START_HERE.bat and choose 3.
echo.
endlocal
exit /b 0

rem --- failures -----------------------------------------------------

:fail_quiet
echo.
echo  Setup stopped. Fix the item above and run this again.
endlocal
exit /b 1

:fail_venv
echo.
echo  [ERROR] Could not create the virtual environment.
echo          Most often this is antivirus or a locked-down folder.
echo          Try moving this whole folder to C:\formlabs-mes and
echo          running START_HERE.bat again.
endlocal
exit /b 1

:fail_deps
echo.
echo  [ERROR] Installing requirements.txt failed - the real error is in
echo          the red text above.
echo          If this PC has no internet for pip, run START_HERE.bat on
echo          the old PC, choose 6, and answer Y when it offers to
echo          include the offline packages.
endlocal
exit /b 1

:fail_env
echo.
echo  [ERROR] Could not reach PostgreSQL with the details given.
echo          Run START_HERE.bat and choose 5 to see exactly what failed.
endlocal
exit /b 1

:fail_ensuredb
echo.
echo  [ERROR] Reached PostgreSQL but could not create the database.
echo          Check the Postgres service is running:
echo          services.msc -^> postgresql-x64-...
endlocal
exit /b 1

:fail_pgold
echo.
echo  [STOP] The PostgreSQL on this PC is OLDER than the one the backup
echo         came from and cannot read the dump. Install a newer
echo         PostgreSQL, or run this again and choose C to start clean.
endlocal
exit /b 1

:fail_restore
echo.
echo  [ERROR] Restore failed - the exact Postgres error is in logs\.
echo          Usually a password mismatch. The restore stops on the
echo          FIRST real error rather than skipping tables, so whatever
echo          is in the log is the problem.
endlocal
exit /b 1

:fail_schema
echo.
echo  [ERROR] Could not build or update the schema - see logs\.
endlocal
exit /b 1
