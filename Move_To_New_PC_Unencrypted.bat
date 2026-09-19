@echo off
setlocal enabledelayedexpansion
cd /d %~dp0

echo ===================================================
echo  Formlabs MES - Package for Move to New PC (UNENCRYPTED)
echo ===================================================
echo.
echo  This is a one-off variant of Move_To_New_PC.bat with the AES-256
echo  password-protection step (added in 4.01) skipped on purpose, at your
echo  own request. The zip this produces holds a FULL raw database dump -
echo  resin specs (SKU/resin code included), production logs, everything -
echo  with none of the app's normal access control applied to it, and
echo  nothing stopping anyone who gets hold of the file from reading it.
echo  Treat it exactly like you would the live database itself: hand it
echo  directly to the destination PC (USB stick you keep on you, or a
echo  transfer method you already trust) rather than leaving it on a
echo  shared drive or attaching it anywhere plain email/chat would keep a
echo  copy. Move_To_New_PC.bat (the normal, encrypted one) is still here
echo  and is what this project's own docs point people at by default.
echo.
pause

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

set "VPY=venv\Scripts\python.exe"

echo [1/5] Backing up the database (pg_dump)...
set BACKUP_LINE=
for /f "delims=" %%i in ('"%VPY%" _migration_helper.py backup') do set BACKUP_LINE=%%i
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
"%VPY%" -m pip download -r requirements.txt -d wheels
if errorlevel 1 (
    echo.
    echo     [WARNING] Couldn't download some packages - shipping without
    echo               them. Setup on the new PC will fall back to
    echo               downloading from the internet.
    if exist wheels rmdir /s /q wheels
) else (
    if exist requirements-device-gateway.txt (
        "%VPY%" -m pip download -r requirements-device-gateway.txt -d wheels >nul 2>&1
    )
    if exist requirements-portable.txt (
        "%VPY%" -m pip download -r requirements-portable.txt -d wheels >nul 2>&1
    )
    echo     Done.
)

:stage
echo [3/5] Staging a clean copy of the project...
set STAGE=%~dp0_MOVE_PACKAGE
if exist "%STAGE%" rmdir /s /q "%STAGE%"
mkdir "%STAGE%"

robocopy "%~dp0." "%STAGE%" /E ^
    /XD venv .git __pycache__ .idea logs _MOVE_PACKAGE tests dev docs ^
        "Claude outputs" _to_delete pgdata node_modules ^
    /XF combined_code.txt mes_production.db *.pyc *.tgz *.bak *.log ^
        formlabs_mes_move_*.zip Unlock_Move_Package.bat Unlock_Move_Package.ps1 ^
    /NFL /NDL /NJH >nul
if %ERRORLEVEL% GEQ 8 (
    echo.
    echo [ERROR] Copying project files failed - robocopy exit code %ERRORLEVEL%.
    pause
    exit /b 1
)

echo [4/5] Compressing to a single zip file...
set ZIPNAME=%~dp0formlabs_mes_move_%STAMP%_UNENCRYPTED.zip
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
echo  DONE. This file is NOT encrypted - it is a plain zip holding a full,
echo  readable copy of your database. Move it like you'd move the database
echo  itself:
echo.
echo     %ZIPNAME%
echo.
echo  On the work PC: extract it directly (right-click -^> Extract All),
echo  then run START_HERE.bat from inside that folder and choose 1
echo  (MES / Logger) or 2 (Device Gateway).
echo ===================================================
pause
