@echo off
cd /d "%~dp0"
echo ===================================================
echo   IMPORT RESIN LIST
echo ===================================================
echo.
if not exist "resin_export.json" (
    echo resin_export.json is missing from this folder - nothing to import.
    pause
    exit /b 1
)
echo Run this AFTER the app is already open (START_HERE.bat), so it
echo attaches to that same database instead of starting a second one.
echo.
venv\Scripts\python.exe import_resins.py
echo.
pause
