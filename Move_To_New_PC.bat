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

rem venv\Scripts\python.exe directly, not "call activate.bat" then a bare
rem "python" - activate.bat bakes in the ABSOLUTE path the venv was first
rem created at (its own VIRTUAL_ENV= line), so a venv created before this
rem project last moved folders silently prepends a PATH entry that no
rem longer exists, and "python" then resolves to the SYSTEM Python instead -
rem which fails on "No module named 'dotenv'" the moment it imports utils.py.
set "VPY=venv\Scripts\python.exe"

echo [1/6] Backing up the database (pg_dump)...
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
rem BACKUP_LINE looks like "BACKUP_OK:mes_backup_20260830_121500.sql" - pull
rem the timestamp back out of it for the zip name instead of shelling out to
rem python a second time.
for /f "tokens=2 delims=:" %%f in ("%BACKUP_LINE%") do set DUMP_NAME=%%f
set STAMP=%DUMP_NAME:mes_backup_=%
set STAMP=%STAMP:.sql=%

echo [2/6] Offline packages...
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
    rem Best-effort: pgserver's compiled wheel doesn't exist for every Python
    rem release yet, so a failure here isn't fatal the way one in the main
    rem requirements.txt is - a PC on a newer Python just falls back to
    rem downloading it fresh if it ever runs option 9, same as any package
    rem missing from wheels\ already does.
    if exist requirements-portable.txt (
        "%VPY%" -m pip download -r requirements-portable.txt -d wheels >nul 2>&1
    )
    echo     Done.
)

:stage
echo [3/6] Staging a clean copy of the project...
set STAGE=%~dp0_MOVE_PACKAGE
if exist "%STAGE%" rmdir /s /q "%STAGE%"
mkdir "%STAGE%"

rem Only what runs ships. tests\ is the release check, dev\ is the
rem screenshot and document tooling, docs\ is the handbook sources and their
rem figures - none of it is needed on the floor PC, and together they are most
rem of the folder by size. The finished PDFs are printed from docs\ on this
rem PC, not served by the app. Transfer archives in backups\ (*.tgz) are not
rem database backups and do not ship; the .sql dumps do. node_modules is
rem npm's own cache of frontend\'s build tooling - the work PC runs the
rem already-built frontend\dist, never `npm run build` itself, so shipping
rem it is dozens of megabytes for something never opened.
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

echo [4/6] Compressing to a single zip file...
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

rem The zip at this point holds the FULL database backup - resin specs
rem (sku/resin_code included - the app's own manage_resins gating means
rem nothing once it's a raw pg_dump file), production logs, everything.
rem Compress-Archive has no password/encryption option at all, so left
rem as a plain .zip it would travel completely unprotected to wherever
rem this file goes next (USB drive, cloud upload, ...). Encrypting it
rem here, unconditionally, means there is never a build of this package
rem that skips that step.
echo [5/6] Password-protecting the package (AES-256)...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Unlock_Move_Package.ps1" -Mode Encrypt -Path "%ZIPNAME%"
if errorlevel 1 (
    echo.
    echo [ERROR] Encrypting the package failed or was cancelled - see the
    echo         message above. The plain, UNPROTECTED zip is still at:
    echo             %ZIPNAME%
    echo         Do not copy that file anywhere as-is. Re-run this script
    echo         to try again.
    rmdir /s /q "%STAGE%"
    pause
    exit /b 1
)
set "ZIPNAME=%ZIPNAME%.enc"

echo [6/6] Cleaning up...
rmdir /s /q "%STAGE%"

echo.
echo ===================================================
echo  DONE.
echo.
echo  Copy BOTH of these files, together in the same folder,
echo  to your work PC (USB drive, cloud drive, network share -
echo  however you'd normally move files):
echo.
echo     %ZIPNAME%
echo     Unlock_Move_Package.bat
echo.
echo  On the work PC: run Unlock_Move_Package.bat first and
echo  enter the password you just set - it produces the real
echo  .zip. Extract THAT ^(right-click -^> Extract All^), then run
echo  START_HERE.bat from inside that folder and choose 1
echo  ^(MES / Logger^) or 2 ^(Device Gateway^).
echo ===================================================
pause
