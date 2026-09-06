@echo off
rem ===================================================================
rem  Makes sure PostgreSQL exists on this PC. Only the MES install
rem  needs this - the Device Gateway never hosts a database.
rem
rem  No setlocal: PG_BIN is handed back to the caller.
rem  Exit 0 = Postgres is here. Exit 1 = stop, tell the user why.
rem ===================================================================
set "PG_BIN="
set "_PG_TRIED="

:_pg_probe
where psql >nul 2>&1
if not errorlevel 1 (
    echo     Found psql on PATH.
    exit /b 0
)
for /f "delims=" %%d in ('dir /b /o-n "%ProgramFiles%\PostgreSQL" 2^>nul') do (
    if not defined PG_BIN if exist "%ProgramFiles%\PostgreSQL\%%d\bin\psql.exe" set "PG_BIN=%ProgramFiles%\PostgreSQL\%%d\bin"
)
if defined PG_BIN goto :_pg_found
for /f "delims=" %%d in ('dir /b /o-n "C:\Program Files (x86)\PostgreSQL" 2^>nul') do (
    if not defined PG_BIN if exist "C:\Program Files (x86)\PostgreSQL\%%d\bin\psql.exe" set "PG_BIN=C:\Program Files (x86)\PostgreSQL\%%d\bin"
)
if defined PG_BIN goto :_pg_found
goto :_pg_missing

:_pg_found
echo     Found PostgreSQL at %PG_BIN%
rem Put it on PATH for this window so _migration_helper.py's pg_dump /
rem psql calls work even though the installer never touched PATH.
set "PATH=%PG_BIN%;%PATH%"
exit /b 0

:_pg_missing
if defined _PG_TRIED goto :_pg_manual

echo.
echo     PostgreSQL is not installed on this PC.
where winget >nul 2>&1
if errorlevel 1 goto :_pg_manual

echo.
echo     I can install it with winget now. It is a large download and
echo     takes several minutes.
choice /c YN /m "     Install PostgreSQL 17 now"
if errorlevel 2 goto :_pg_manual

echo     Installing - leave this window alone until it finishes.
winget install -e --id PostgreSQL.PostgreSQL.17 --accept-package-agreements --accept-source-agreements --silent
if not errorlevel 1 goto :_pg_recheck
echo     Trying the unversioned package id...
winget install -e --id PostgreSQL.PostgreSQL --accept-package-agreements --accept-source-agreements --silent

:_pg_recheck
echo.
echo     Looking for it again...
set "_PG_TRIED=1"
goto :_pg_probe

:_pg_manual
echo.
echo  ---------------------------------------------------------------
echo   [STOP] This PC needs PostgreSQL and I can't install it here.
echo.
echo          1. Go to  https://www.postgresql.org/download/windows/
echo          2. Run the installer. Accept every default EXCEPT the
echo             password screen.
echo          3. WRITE DOWN the password you set for the user
echo             "postgres". The next step asks you for it, and a
echo             wrong password here is the single most common reason
echo             this app won't start on a new machine.
echo          4. Run START_HERE.bat again and choose 1.
echo  ---------------------------------------------------------------
exit /b 1
