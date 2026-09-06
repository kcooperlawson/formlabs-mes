@echo off
rem ===================================================================
rem  Kept only so older instructions and older zips still work.
rem
rem  Setup now lives behind one door: START_HERE.bat, which asks whether
rem  this PC is the MES/Logger or a Device Gateway and installs the
rem  right one. This file just opens that door.
rem
rem  (The version of this file before 2026-09-05 was corrupt: a block of
rem  restore logic was duplicated after the :launch label, so on a good
rem  run it printed syntax errors and then tried to restore the database
rem  a second time. That is why setup "worked sometimes" on a new PC.)
rem ===================================================================
cd /d "%~dp0"
echo.
echo  Setup moved to START_HERE.bat - opening it now.
echo.
call "START_HERE.bat"
