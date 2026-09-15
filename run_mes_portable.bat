@echo off
setlocal
cd /d %~dp0

rem ===================================================================
rem  Formlabs MES - Portable Launcher
rem
rem  For a PC where installing PostgreSQL is the blocker - a locked-down
rem  work network, no admin rights, no time. This needs Python and
rem  nothing else: the database itself is pgserver (see requirements.txt),
rem  a real PostgreSQL with its own binaries bundled in the pip package,
rem  running out of pgdata\ next to this project instead of a system-wide
rem  install. First run creates that database and seeds the default
rem  admin account; every run after that just starts it back up.
rem
rem  This does NOT touch .env or any real PostgreSQL install on this PC -
rem  run_mes.bat and run_mes_api.bat are completely unaffected by this
rem  file existing, and this file ignores DB_URL entirely.
rem ===================================================================

echo.
echo  ===================================================
echo   Formlabs MES - Portable Launcher
echo  ===================================================
echo.

echo  [1/4] Python...
call "setup\_ensure_python.bat"
if not defined PY_CMD goto :fail_quiet

echo.
echo  [2/4] Virtual environment...
if exist "venv\Scripts\python.exe" goto :venv_ready
%PY_CMD% -m venv venv
if errorlevel 1 goto :fail_venv
:venv_ready
set "VPY=venv\Scripts\python.exe"
echo     Ready.

echo.
echo  [3/4] Dependencies ^(a few minutes the first time^)...
"%VPY%" -c "import pgserver, fastapi, uvicorn" >nul 2>&1
if not errorlevel 1 goto :deps_done

"%VPY%" -m pip install --upgrade pip --quiet
if not exist "wheels" goto :online
echo     Offline packages found in wheels\ - installing without the network.
"%VPY%" -m pip install --no-index --find-links=wheels -r requirements.txt
if errorlevel 1 goto :offline_failed
goto :deps_done

:offline_failed
echo     [NOTICE] The offline packages don't fit this Python version.
echo              Falling back to downloading from the internet.

:online
"%VPY%" -m pip install -r requirements.txt
if errorlevel 1 goto :fail_deps

:deps_done
echo     Ready.

echo.
echo  [4/4] Frontend build...
if exist "frontend\dist\index.html" goto :launch
echo.
echo  [ERROR] frontend\dist\index.html is missing - this copy wasn't
echo          packaged with the built frontend included.
echo          From the frontend\ folder on a PC with Node installed, run:
echo              npm install
echo              npm run build
echo          then copy frontend\dist here and try again.
pause
exit /b 1

:launch
echo     Ready.
echo.
"%VPY%" -m api.portable_launcher
goto :eof

:fail_quiet
pause
exit /b 1

:fail_venv
echo.
echo  [ERROR] Could not create the virtual environment.
pause
exit /b 1

:fail_deps
echo.
echo  [ERROR] Could not install dependencies. Check your internet
echo          connection, or include offline packages next time this
echo          is packaged with Move_To_New_PC.bat.
pause
exit /b 1
