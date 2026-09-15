@echo off
rem ===================================================================
rem  Formlabs MES - Unlock a password-protected move package.
rem
rem  Run this on the NEW PC, in the same folder as the
rem  formlabs_mes_move_*.zip.enc file Move_To_New_PC.bat produced - copy
rem  THIS file there too. It has no dependency on anything else in the
rem  project on purpose: at this stage nothing has been unpacked yet,
rem  so this can't rely on Python, the venv, or even internet access -
rem  only Unlock_Move_Package.ps1 (plain PowerShell / .NET, ships with
rem  every Windows PC) sitting next to it.
rem
rem  Produces the real .zip next to the .enc file. From there: extract
rem  it (right-click -> Extract All) and run START_HERE.bat as usual.
rem ===================================================================
setlocal
cd /d "%~dp0"

if not exist "%~dp0Unlock_Move_Package.ps1" (
    echo.
    echo  [ERROR] Unlock_Move_Package.ps1 is missing from this folder.
    echo          Copy it here alongside this .bat file and the .enc
    echo          package, then run this again.
    pause
    exit /b 1
)

set "ENCFILE="
for /f "delims=" %%f in ('dir /b /o-d "formlabs_mes_move_*.zip.enc" 2^>nul') do (
    if not defined ENCFILE set "ENCFILE=%%f"
)
if not defined ENCFILE (
    echo.
    echo  [ERROR] No formlabs_mes_move_*.zip.enc file found in this folder.
    echo          Copy the .enc file here first, next to this script.
    pause
    exit /b 1
)

echo.
echo  ===================================================
echo   Formlabs MES - Unlock Move Package
echo  ===================================================
echo.
echo  Found: %ENCFILE%
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Unlock_Move_Package.ps1" -Mode Decrypt -Path "%ENCFILE%"
if errorlevel 1 (
    echo.
    echo  [ERROR] Could not unlock the package - see the message above.
    echo          Most often this just means the password was mistyped;
    echo          run this again and re-enter it carefully.
    pause
    exit /b 1
)

echo.
echo  ===================================================
echo   DONE - unlocked.
echo  ===================================================
echo.
echo  Next: extract the .zip file that just appeared in this folder
echo  (right-click it -^> Extract All), then run START_HERE.bat from
echo  inside the extracted folder.
echo.
pause
