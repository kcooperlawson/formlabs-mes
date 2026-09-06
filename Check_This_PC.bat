@echo off
cd /d %~dp0

rem Run this before carrying the machine to the floor, and again after moving
rem to a different PC. It answers one question - is this PC ready to run the
rem plant - and when the answer is no it says exactly what to type.
rem
rem Goes through the venv for the same reason run_mes.bat does: the packages
rem live in venv\, and checking the system Python would report on a set of
rem packages the app will never use.

echo.
if not exist venv\Scripts\activate.bat (
    echo [ERROR] No venv folder here yet.
    echo         Run Setup_On_New_PC.bat once first - it creates the virtual
    echo         environment and installs the dependencies.
    echo.
    pause
    exit /b 1
)

call venv\Scripts\activate.bat
python preflight.py %*
set RESULT=%ERRORLEVEL%

echo.
if %RESULT% NEQ 0 (
    echo  Fix the FAIL lines above, then run this again.
) else (
    echo  Start the app with run_mes.bat.
)
echo.
pause
exit /b %RESULT%
