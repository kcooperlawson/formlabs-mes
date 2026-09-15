@echo off
rem ===================================================================
rem  Finds a usable Python (3.11+) and leaves it in PY_CMD for whoever
rem  called this file. Installs one with winget if there isn't one.
rem
rem  NO setlocal in here on purpose: setlocal would throw PY_CMD away
rem  the moment this file ends, which is the one thing it exists to do.
rem
rem  Call with an argument of "noinstall" to only look, never install.
rem ===================================================================
set "PY_CMD="
set "_EP_NOINSTALL=%~1"
set "_EP_TRIED="

:_ep_probe_all
call :_ep_probe_cmd py -3.13
if defined PY_CMD goto :_ep_found
call :_ep_probe_cmd py -3.12
if defined PY_CMD goto :_ep_found
call :_ep_probe_cmd py -3
if defined PY_CMD goto :_ep_found
call :_ep_probe_cmd python
if defined PY_CMD goto :_ep_found

call :_ep_probe_path "%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
if defined PY_CMD goto :_ep_found
call :_ep_probe_path "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if defined PY_CMD goto :_ep_found
call :_ep_probe_path "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
if defined PY_CMD goto :_ep_found
call :_ep_probe_path "%ProgramFiles%\Python313\python.exe"
if defined PY_CMD goto :_ep_found
call :_ep_probe_path "%ProgramFiles%\Python312\python.exe"
if defined PY_CMD goto :_ep_found
call :_ep_probe_path "%ProgramFiles%\Python311\python.exe"
if defined PY_CMD goto :_ep_found
call :_ep_probe_path "C:\Python313\python.exe"
if defined PY_CMD goto :_ep_found
call :_ep_probe_path "C:\Python312\python.exe"
if defined PY_CMD goto :_ep_found

goto :_ep_missing

:_ep_found
echo     Python: %PY_CMD%
exit /b 0

:_ep_missing
if /i "%_EP_NOINSTALL%"=="noinstall" exit /b 1
if defined _EP_TRIED goto :_ep_manual

echo.
echo     No Python 3.11+ found on this PC.
where winget >nul 2>&1
if errorlevel 1 goto :_ep_manual

echo     Installing Python 3.12 with winget - this takes a couple of minutes.
echo.
winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements --silent
echo.
echo     Looking for it again...
set "_EP_TRIED=1"
goto :_ep_probe_all

:_ep_manual
echo.
echo  ---------------------------------------------------------------
echo   [STOP] This PC needs Python 3.11 or newer and I can't install
echo          it automatically here.
echo.
echo          1. Go to  https://www.python.org/downloads/
echo          2. Download Python 3.12 and run the installer.
echo          3. TICK THE BOX "Add python.exe to PATH" on the first
echo             screen - this is the step people miss, and skipping
echo             it is why the app can't find its packages later.
echo          4. Run START_HERE.bat again.
echo  ---------------------------------------------------------------
exit /b 1

rem --- helpers ------------------------------------------------------

:_ep_probe_cmd
rem %* is a command like: py -3.12
%* -c "import sys;sys.exit(0 if sys.version_info>=(3,11) else 1)" >nul 2>&1
if errorlevel 1 exit /b 0
set "PY_CMD=%*"
exit /b 0

:_ep_probe_path
if not exist "%~1" exit /b 0
"%~1" -c "import sys;sys.exit(0 if sys.version_info>=(3,11) else 1)" >nul 2>&1
if errorlevel 1 exit /b 0
rem Quoted on purpose: these paths contain spaces (Program Files).
set PY_CMD="%~1"
exit /b 0
