@echo off
cd /d %~dp0

echo ===================================================
echo  Formlabs MES
echo ===================================================
echo.
echo  This script is retired - it pointed at "app.py", which
echo  hasn't been the entry point since the app was reorganised,
echo  and it tried to download and silently install Python from
echo  the internet, which is not something to run on a managed
echo  or work-owned PC.
echo.
echo  Use these instead:
echo.
echo    Setup_On_New_PC.bat   - first-time setup on a new machine
echo                            (venv, dependencies, database restore)
echo.
echo    run_mes.bat           - start the app on a PC that's already
echo                            been set up
echo.
pause
