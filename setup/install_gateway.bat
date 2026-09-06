@echo off
rem ===================================================================
rem  Install the Device Gateway on this PC.
rem
rem  This PC does NOT host a database and does NOT serve the app. It
rem  sits near the machines, talks to them over Modbus / serial / MQTT /
rem  OPC-UA, and writes readings into whichever MES database it finds on
rem  the network. So: no PostgreSQL install, no database creation, no
rem  migrations. Just Python, the packages, and a login.
rem ===================================================================
setlocal
cd /d "%~dp0.."

echo.
echo  ===================================================
echo   INSTALL - Device Gateway
echo  ===================================================
echo.

if exist "run_gateway.py" goto :have_files
echo  [ERROR] run_gateway.py is not in this folder, so this isn't the
echo          project root. Unzip the whole package and run
echo          START_HERE.bat from inside it.
endlocal
exit /b 1

:have_files
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
"%VPY%" -m pip install --upgrade pip --quiet
echo     Ready.

echo.
echo  [3/4] Dependencies...
rem The full requirements.txt goes on here too, not a trimmed list. The
rem gateway imports crud.py, which pulls in SQLAlchemy, Alembic, pandas
rem and their chain - and every attempt to hand-pick that list ends in a
rem missing import on the floor at 6am. Disk is cheaper than that.
set "USED_OFFLINE="
if not exist "wheels" goto :online
echo     Offline packages found in wheels\ - installing without the network.
"%VPY%" -m pip install --no-index --find-links=wheels -r requirements.txt
if errorlevel 1 goto :offline_failed
"%VPY%" -m pip install --no-index --find-links=wheels -r requirements-device-gateway.txt
set "USED_OFFLINE=1"
goto :deps_done

:offline_failed
echo     [NOTICE] The offline packages don't fit this Python version.
echo              Falling back to downloading from the internet.

:online
"%VPY%" -m pip install -r requirements.txt
if errorlevel 1 goto :fail_deps
"%VPY%" -m pip install -r requirements-device-gateway.txt
if errorlevel 1 (
    echo     [WARNING] The protocol libraries failed to install. The gateway
    echo               will start, but any device using Modbus, serial, MQTT
    echo               or OPC-UA will fail to connect until this is fixed.
)

:deps_done
echo     Installed.

echo.
echo  [4/4] Database login...
"%VPY%" "setup\_configure_env.py" gateway
if errorlevel 1 goto :fail_env

echo.
echo  ===================================================
echo   DONE - this PC is set up as a Device Gateway.
echo  ===================================================
echo.
echo   It will find the MES database by itself, as long as the MES PC
echo   is running the app on the same network.
echo.
echo   Next:
echo     1. Make sure the MES PC is running ^(START_HERE.bat, option 3^).
echo     2. Here, run START_HERE.bat and choose 4.
echo     3. Register the machines from the MES app: Device Registry.
echo.
echo   To keep it running after a reboot without a window open, wrap it
echo   in Task Scheduler as "run whether user is logged on or not":
echo       Program:   %~dp0..\venv\Scripts\python.exe
echo       Arguments: run_gateway.py
echo       Start in:  %~dp0..
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
echo          Usually antivirus or a locked-down folder. Try moving this
echo          folder to C:\formlabs-mes and running START_HERE.bat again.
endlocal
exit /b 1

:fail_deps
echo.
echo  [ERROR] Installing requirements.txt failed - the real error is in
echo          the red text above. If this PC has no internet for pip,
echo          build the package on the MES PC with the offline packages
echo          included ^(START_HERE.bat, option 6, answer Y^).
endlocal
exit /b 1

:fail_env
echo.
echo  [ERROR] Could not write the database login.
endlocal
exit /b 1
