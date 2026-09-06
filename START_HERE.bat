@echo off
rem ===================================================================
rem  Formlabs MES - the one thing you double-click on any PC.
rem
rem  This is deliberately the ONLY entry point. Everything else lives in
rem  setup\ and is called from here, so there is never a question of
rem  "which .bat do I run on this machine".
rem ===================================================================
title Formlabs MES
cd /d "%~dp0"

:menu
cls
echo.
echo  ===================================================
echo   FORMLABS MES
echo  ===================================================
echo.
if exist "venv\Scripts\python.exe" (
    echo   This PC:  set up  ^(venv is present^)
) else (
    echo   This PC:  NOT set up yet  ^(no venv^)
)
echo.
echo   INSTALL - do once per PC
echo     1  Install the MES / Logger   ^(this PC runs the app + database^)
echo     2  Install the Device Gateway ^(this PC only talks to machines^)
echo.
echo   RUN - every day
echo     3  Start the MES / Logger
echo     4  Start the Device Gateway
echo.
echo     5  Diagnose this PC ^(what is missing, what is wrong^)
echo     6  Package this project for another PC
echo     Q  Quit
echo.
set "PICK="
set /p "PICK=  Choose and press Enter: "

if /i "%PICK%"=="1" goto :install_mes
if /i "%PICK%"=="2" goto :install_gw
if /i "%PICK%"=="3" goto :run_mes
if /i "%PICK%"=="4" goto :run_gw
if /i "%PICK%"=="5" goto :diagnose
if /i "%PICK%"=="6" goto :package
if /i "%PICK%"=="Q" goto :eof
goto :menu

:install_mes
call "setup\install_mes.bat"
echo.
pause
goto :menu

:install_gw
call "setup\install_gateway.bat"
echo.
pause
goto :menu

:run_mes
if not exist "venv\Scripts\python.exe" goto :not_setup
echo.
echo  Starting the MES. Close this window to stop it.
echo  Operators open the address printed below on their phones.
echo.
venv\Scripts\python.exe -m streamlit run Home.py --server.address=0.0.0.0
echo.
pause
goto :menu

:run_gw
if not exist "venv\Scripts\python.exe" goto :not_setup
echo.
echo  Starting the Device Gateway. Close this window to stop it.
echo.
venv\Scripts\python.exe run_gateway.py
echo.
pause
goto :menu

:diagnose
echo.
if not exist "venv\Scripts\python.exe" goto :diagnose_novenv
venv\Scripts\python.exe "setup\_preflight.py"
echo.
pause
goto :menu

:diagnose_novenv
call "setup\_ensure_python.bat" noinstall
if not defined PY_CMD goto :diagnose_nopy
%PY_CMD% "setup\_preflight.py"
echo.
pause
goto :menu

:diagnose_nopy
echo  [X] No Python on this PC at all, and no venv. Choose 1 or 2 first.
echo.
pause
goto :menu

:package
if not exist "Move_To_New_PC.bat" (
    echo.
    echo  Move_To_New_PC.bat is missing from this folder.
    echo.
    pause
    goto :menu
)
call "Move_To_New_PC.bat"
goto :menu

:not_setup
echo.
echo  This PC has not been set up yet. Choose 1 ^(MES^) or 2 ^(Gateway^) first.
echo.
pause
goto :menu
