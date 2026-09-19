"""Regenerates Repair_Updater.bat from setup/bootstrap_update.py.

    python dev/embed_repair_updater.py

Repair_Updater.bat is the one file a PC too old to accept updates needs
carried to it alongside the package zip - that PC doesn't have
setup/bootstrap_update.py yet, because that file only arrives in an update.
So the .bat carries a base64 copy of it, the same way Unlock_Move_Package.bat
carries its own .ps1 (see tests/test_move_package.py for why that pattern
needs a test: an embedded copy is exactly the kind of thing that quietly
drifts from the real file it was generated from). tests/test_update_system.py
fails if these two ever disagree.
"""
import base64
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
SOURCE = ROOT / "setup" / "bootstrap_update.py"
TARGET = ROOT / "Repair_Updater.bat"

HEADER = r"""@echo off
rem ===================================================================
rem  Formlabs MES - Repair the updater.
rem
rem  Only needed on a PC that stops with "the backup failed" when it
rem  tries to apply an update. That happens on a PC running the bundled
rem  (portable) database on 4.07 or earlier: the updater there can't find
rem  a portable database to back up, and it refuses to go on without a
rem  backup - on purpose.
rem
rem  The fix ships inside the update itself, which is the update that
rem  can't be applied. This file breaks that circle. It is fully
rem  self-contained: setup\bootstrap_update.py is embedded below as
rem  base64, after the :PAYLOAD marker, so this ONE file plus the update
rem  .zip is everything the PC needs. Regenerate it after editing that
rem  file with: python dev\embed_repair_updater.py
rem
rem  What it does: checks the package's signature and checksums with this
rem  PC's own key, replaces the few files the updater itself needs, and
rem  keeps the old copies in rollback\. It does NOT install the update and
rem  never touches the database.
rem
rem  Put this file and the update .zip in the project folder (the one with
rem  START_HERE.bat), run it, then apply the update normally with
rem  START_HERE.bat option 7.
rem ===================================================================
setlocal
cd /d "%~dp0"

if exist "START_HERE.bat" goto :found_project
echo.
echo  [ERROR] This isn't the project folder - START_HERE.bat isn't here.
echo          Put this file next to START_HERE.bat and run it again.
pause
exit /b 1

:found_project
set "PKG=%~1"
if not "%PKG%"=="" goto :have_pkg
if not exist "updates" mkdir "updates"
for /f "delims=" %%f in ('dir /b /o-d "updates\*.zip" 2^>nul') do (
    if not defined PKG set "PKG=updates\%%f"
)
for /f "delims=" %%f in ('dir /b /o-d "mes_update_*.zip" 2^>nul') do (
    if not defined PKG set "PKG=%%f"
)
if defined PKG goto :have_pkg
echo.
echo  [ERROR] No update .zip found. Copy the package into this folder
echo          (or into updates\) and run this again.
pause
exit /b 1

:have_pkg
rem This PC's own interpreter, normally the project venv. MES_PYTHON is an
rem override for a PC whose venv lives somewhere else; `py -3` is the last
rem resort (it needs the cryptography package to check the signature, which
rem the venv always has).
set "VPY=%MES_PYTHON%"
if not "%VPY%"=="" goto :have_python
set "VPY=venv\Scripts\python.exe"
if exist "%VPY%" goto :have_python
where py >nul 2>&1
if not errorlevel 1 (
    set "VPY=py"
    goto :have_python
)
echo.
echo  [ERROR] No Python found - venv\Scripts\python.exe is missing and `py`
echo          isn't on PATH. Run START_HERE.bat first, or set MES_PYTHON to
echo          the python.exe to use.
pause
exit /b 1

:have_python
echo.
echo  ===================================================
echo   Formlabs MES - Repair the updater
echo  ===================================================
echo.
echo  Package: %PKG%
echo.

rem Unpacks the embedded payload below to a temp .py and runs it against
rem this folder, then cleans up - the same self-extraction
rem Unlock_Move_Package.bat does, for the same reason.
powershell -NoProfile -ExecutionPolicy Bypass -Command "$lines = Get-Content -LiteralPath '%~f0'; $i = ($lines | Select-String -Pattern '^:PAYLOAD$').LineNumber; $b64 = ($lines[$i..($lines.Count-1)] -join ''); $bytes = [Convert]::FromBase64String($b64); $tmp = Join-Path $env:TEMP ('_repair_updater_' + [guid]::NewGuid().ToString('N') + '.py'); [IO.File]::WriteAllBytes($tmp, $bytes); & '%VPY%' $tmp '%PKG%' --root '%~dp0.'; $rc = $LASTEXITCODE; Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue; exit $rc"
if errorlevel 1 (
    echo.
    echo  [ERROR] The repair did not run - see the message above.
    pause
    exit /b 1
)

echo.
echo  Next: START_HERE.bat, option 7, to apply the update itself.
echo.
pause
exit /b 0

:PAYLOAD
"""


def main() -> None:
    payload = base64.b64encode(SOURCE.read_bytes()).decode("ascii")
    lines = [payload[i:i + 76] for i in range(0, len(payload), 76)]
    TARGET.write_text(HEADER + "\n".join(lines) + "\n", encoding="utf-8", newline="\r\n")
    print(f"  Wrote {TARGET.relative_to(ROOT)} "
          f"({TARGET.stat().st_size / 1024:.0f} KB, payload {len(lines)} lines)")


if __name__ == "__main__":
    main()
