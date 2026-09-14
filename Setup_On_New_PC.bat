@echo off
rem ===================================================================
rem  Formlabs MES - First-Time Setup on This PC.
rem
rem  Unzip a package built by Move_To_New_PC.bat anywhere on this PC,
rem  then run this from inside that folder. It installs Python if this
rem  PC doesn't have it, installs PostgreSQL if this PC doesn't have
rem  that either, creates the database and connects to it, and restores
rem  the backup the package was built with - all without needing
rem  anything typed into a config file by hand first.
rem
rem  This calls the exact same setup\ scripts install_mes.bat does, so
rem  a PC set up this way and a PC set up fresh behave identically and
rem  a fix to one script fixes both installers at once.
rem ===================================================================
setlocal
cd /d "%~dp0"

echo.
echo  ===================================================
echo   Formlabs MES - First-Time Setup on This PC
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
rem If Move_To_New_PC.bat bundled offline packages, this needs no
rem internet at all - the usual blocker on a locked-down work PC.
set "USED_OFFLINE="
if not exist "wheels" goto :online
echo     Offline packages found in wheels\ - installing without the network.
"%VPY%" -m pip install --no-index --find-links=wheels -r requirements.txt
if errorlevel 1 goto :offline_failed
set "USED_OFFLINE=1"
if exist "requirements-device-gateway.txt" "%VPY%" -m pip install --no-index --find-links=wheels -r requirements-device-gateway.txt
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
rem Asks once for this PC's PostgreSQL login, writes .env, and proves the
rem connection actually works before going any further - instead of
rem finding out three steps later from an error that never mentions a
rem password.
"%VPY%" "setup\_configure_env.py" mes
if errorlevel 1 goto :fail_env

"%VPY%" _migration_helper.py ensure_db
if errorlevel 1 goto :fail_ensuredb

rem A backup in backups\ is there because Move_To_New_PC.bat took one
rem before packaging. Restoring it is what makes this a MOVE rather than
rem a fresh install - it asks first, because restoring replaces whatever
rem is already in the database this PC just connected to.
set "LATEST_DUMP="
for /f "delims=" %%f in ('dir /b /o-d "backups\*.sql" 2^>nul') do (
    if not defined LATEST_DUMP set "LATEST_DUMP=%%f"
)
if not defined LATEST_DUMP (
    echo     No database backup in backups\ - starting clean.
    set "CLEAN_START=1"
    goto :schema
)

echo.
echo     A database backup is included: %LATEST_DUMP%
echo.
echo       R = Restore it into this PC's database ^(brings across every log,
echo           account and setting from the PC it was taken on^)
echo       C = Start clean ^(empty database; one administrator account^)
echo.
choice /c RC /m "     Restore the backup, or start clean"
if errorlevel 2 (
    echo     Starting clean. The backup stays in backups\ if you want it later.
    set "CLEAN_START=1"
    goto :schema
)

set "DB_HOST="
for /f "delims=" %%h in ('"%VPY%" _migration_helper.py db_host') do set "DB_HOST=%%h"
if /i "%DB_HOST%"=="localhost" goto :dump_compat
if /i "%DB_HOST%"=="127.0.0.1" goto :dump_compat
echo.
echo     [NOTICE] .env points at "%DB_HOST%", not this PC. That may be a
echo     live, shared database, and restoring would OVERWRITE it.
echo.
choice /c YN /m "     Are you SURE you want to restore into %DB_HOST%"
if errorlevel 2 (
    echo     Skipping the restore. Starting clean instead.
    set "CLEAN_START=1"
    goto :schema
)

:dump_compat
"%VPY%" _migration_helper.py check_dump_compat "%LATEST_DUMP%"
if errorlevel 1 goto :fail_pgold

echo     Restoring %LATEST_DUMP% ...
"%VPY%" _migration_helper.py restore "%LATEST_DUMP%"
if errorlevel 1 goto :fail_restore
echo     Database restored.

rem The restore said it worked. This checks whether it did. Every backup
rem carries a manifest of the row counts at the moment it was taken, and
rem this counts the same tables here and prints both columns - a dump
rem truncated while copying is otherwise invisible until a month has a
rem hole in it.
echo     Checking the data actually came across...
"%VPY%" _migration_helper.py verify_restore "%LATEST_DUMP%"
if errorlevel 1 goto :fail_verify

:schema
rem Deliberately NOT "alembic stamp head". A restored dump carries its own
rem alembic_version, and "stamp" would overwrite that with head without
rem running anything - silently skipping every migration added since the
rem dump was taken, invisible until something touches a column that was
rem never created.
rem
rem crud.init_db() is the same boot the app itself runs: a restored
rem database gets only the migrations it's missing, one from before
rem Alembic existed is stamped at the baseline and brought forward, and an
rem empty one gets everything plus the seed accounts.
echo     Bringing the schema up to date...
"%VPY%" -c "import crud; crud.init_db()"
if errorlevel 1 goto :fail_schema
echo     Schema is up to date.

rem seed_initial_data() (inside "import crud" above) only ever creates the
rem manager/admin account when the users table is completely empty - by
rem design, so this never touches a plant's real accounts on a restore or a
rem re-run. On a genuine clean start it should always have just run, but
rem this makes the login a guarantee instead of a hope: same account, same
rem PIN, made or re-confirmed by the same tool as the "IT Admin - Accounts"
rem emergency reset, rather than leaving day one dependent on nothing
rem having gone sideways in seeding.
if defined CLEAN_START (
    echo.
    echo  Confirming the admin account can sign in...
    "%VPY%" create_admin.py manager admin123 "Plant Lead"
)

echo.
echo  [6/6] HTTPS certificate...
"%VPY%" "setup\generate_tls_cert.py"

echo.
echo  ===================================================
echo   DONE - this PC is set up and ready.
echo  ===================================================
if not defined CLEAN_START goto :addr
echo.
echo   Clean database. Sign in with:
echo       username:  manager
echo       PIN:       admin123
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
echo          running this script again.
endlocal
exit /b 1

:fail_deps
echo.
echo  [ERROR] Installing requirements.txt failed - the real error is in
echo          the red text above.
echo          If this PC has no internet for pip, re-run
echo          Move_To_New_PC.bat on the old PC and answer Y when it
echo          offers to include the offline packages.
endlocal
exit /b 1

:fail_env
echo.
echo  [ERROR] Could not reach PostgreSQL with the details given.
echo          Run this script again to retry the password.
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

:fail_verify
echo.
echo  [STOP] The restored database has fewer rows than the backup said it
echo         should. Do NOT start logging on this PC yet - the old PC
echo         still has the data, so nothing is lost as long as nothing
echo         new is written here first. Re-copy the backup file and run
echo         this script again; a dump truncated during the copy is the
echo         usual cause.
endlocal
exit /b 1

:fail_schema
echo.
echo  [ERROR] Could not build or update the schema - see logs\.
endlocal
exit /b 1
