@echo off
setlocal enabledelayedexpansion
cd /d %~dp0

echo ===================================================
echo  Formlabs MES - Package for Move to New PC
echo ===================================================
echo.

if not exist venv (
    echo [ERROR] No venv folder found here. Run this from the project root,
    echo         on the PC that currently runs the app.
    pause
    exit /b 1
)
if not exist .env (
    echo [ERROR] No .env file found here - can't reach the database without it.
    pause
    exit /b 1
)

call venv\Scripts\activate.bat

echo [1/4] Backing up the database (pg_dump)...
set BACKUP_LINE=
for /f "delims=" %%i in ('python _migration_helper.py backup') do set BACKUP_LINE=%%i
echo     %BACKUP_LINE%
echo %BACKUP_LINE% | findstr /b "BACKUP_OK:" >nul
if errorlevel 1 (
    echo.
    echo [ERROR] Database backup failed - see the logs\ folder for the real
    echo         pg_dump error. Aborting so you don't ship a package with no
    echo         database in it.
    pause
    exit /b 1
)
rem BACKUP_LINE looks like "BACKUP_OK:mes_backup_20260830_121500.sql" - pull
rem the timestamp back out of it for the zip name instead of shelling out to
rem python a second time.
for /f "tokens=2 delims=:" %%f in ("%BACKUP_LINE%") do set DUMP_NAME=%%f
set STAMP=%DUMP_NAME:mes_backup_=%
set STAMP=%STAMP:.sql=%

echo [2/5] Offline packages...
echo.
echo     A work PC often can't reach PyPI - locked-down network, or a proxy
echo     pip doesn't know about. Including the packages in the move package
echo     means setup over there needs no internet at all. It adds a few
echo     hundred MB to the zip and takes a few minutes to download now.
echo.
choice /c YN /m "     Include offline packages in the zip"
if errorlevel 2 (
    echo     Skipping - the new PC will need working internet access for pip.
    if exist wheels rmdir /s /q wheels
    goto :stage
)
echo     Downloading packages for offline install...
if exist wheels rmdir /s /q wheels
pip download -r requirements.txt -d wheels
if errorlevel 1 (
    echo.
    echo     [WARNING] Couldn't download some packages - shipping without
    echo               them. Setup on the new PC will fall back to
    echo               downloading from the internet.
    if exist wheels rmdir /s /q wheels
) else (
    if exist requirements-device-gateway.txt (
        pip download -r requirements-device-gateway.txt -d wheels >nul 2>&1
    )
    echo     Done.
)

:stage
echo [3/5] Staging a clean copy of the project...
set STAGE=%~dp0_MOVE_PACKAGE
if exist "%STAGE%" rmdir /s /q "%STAGE%"
mkdir "%STAGE%"

robocopy "%~dp0." "%STAGE%" /E ^
    /XD venv .git __pycache__ .idea logs _MOVE_PACKAGE ^
    /XF combined_code.txt mes_production.db *.pyc formlabs_mes_move_*.zip ^
    /NFL /NDL /NJH >nul
if %ERRORLEVEL% GEQ 8 (
    echo.
    echo [ERROR] Copying project files failed - robocopy exit code %ERRORLEVEL%.
    pause
    exit /b 1
)

echo [4/5] Compressing to a single zip file...
set ZIPNAME=%~dp0formlabs_mes_move_%STAMP%.zip
if exist "%ZIPNAME%" del "%ZIPNAME%"
powershell -NoProfile -Command "Compress-Archive -Path '%STAGE%\*' -DestinationPath '%ZIPNAME%' -Force"
if not exist "%ZIPNAME%" (
    echo.
    echo [ERROR] Zip creation failed.
    echo         If you included the offline packages, the zip is large and
    echo         Compress-Archive can struggle with it - re-run and answer N,
    echo         or just copy the _MOVE_PACKAGE folder across as a folder.
    pause
    exit /b 1
)

echo [5/5] Cleaning up...
rmdir /s /q "%STAGE%"

echo.
echo ===================================================
echo  DONE.
echo.
echo  Copy this ONE file to your work PC (USB drive, cloud
echo  drive, network share - however you'd normally move a file):
echo.
echo     %ZIPNAME%
echo.
echo  On the work PC: unzip it anywhere, then run
echo  Setup_On_New_PC.bat from inside that folder.
echo ===================================================
pause
