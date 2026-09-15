@echo off
cd /d %~dp0

rem Day-to-day launcher for the FastAPI + React replacement, side by side
rem with run_mes.bat's Streamlit app - same venv, same .env, same database,
rem different port (8000 here, 8501 there), so both can run against the
rem same plant at once while this is still being trialed. Must go through
rem the venv for the same reason run_mes.bat does: Setup_On_New_PC.bat
rem installs everything INTO venv\, so a bare "py -m uvicorn" would reach
rem for the system Python instead and fail with "No module named uvicorn"
rem on any PC where the packages were never installed system-wide.

if not exist venv\Scripts\python.exe (
    echo [ERROR] No venv folder here yet.
    echo         Run Setup_On_New_PC.bat once first - it creates the virtual
    echo         environment and installs the dependencies.
    pause
    exit /b 1
)

rem Deliberately venv\Scripts\python.exe -m uvicorn, not "call activate.bat"
rem then a bare "uvicorn" - activate.bat bakes in the ABSOLUTE path the venv
rem was first created at (its own VIRTUAL_ENV= line), so a venv created
rem before this project last moved folders silently prepends a PATH entry
rem that no longer exists, and every bare command name after it - streamlit
rem in run_mes.bat's case, uvicorn here - resolves to nothing. Calling the
rem interpreter by its path relative to this launcher sidesteps that
rem entirely: it only depends on venv\ still being where this .bat file is,
rem which is the one thing a moved folder never breaks.

rem The React build has to exist before uvicorn can serve it - api/main.py
rem only mounts frontend\dist at all if the folder is there, and serves API
rem routes with no frontend behind them otherwise. Checked here rather than
rem built here: shelling out to npm on every launch would mean this
rem launcher needs Node.js installed and working too, for a build step that
rem only has to happen again after the frontend's own source changes.
if not exist frontend\dist\index.html (
    echo [ERROR] The frontend hasn't been built yet - frontend\dist\index.html is missing.
    echo         From the frontend\ folder, run:
    echo             npm install
    echo             npm run build
    echo         Then run this launcher again.
    pause
    exit /b 1
)

rem HTTPS if certs\mes.crt / mes.key exist (setup\generate_tls_cert.py writes
rem them - the same certificate run_mes.bat already uses), plain HTTP
rem otherwise. Doesn't generate or check them here - that's what
rem generate_tls_cert.py and START_HERE.bat option 8 are for.
set "SSL_ARGS="
if exist certs\mes.crt if exist certs\mes.key set "SSL_ARGS=--ssl-certfile certs\mes.crt --ssl-keyfile certs\mes.key"
if not defined SSL_ARGS echo [!] No HTTPS certificate - running on plain HTTP. See START_HERE.bat option 8.

rem setup\_preflight.py already works out the LAN IP/hostname and the right
rem http/https scheme (same logic Check_This_PC.bat uses) - reused here so
rem whoever starts this sees the address to give the phones immediately,
rem instead of having to run Check_This_PC.bat separately just to find it.
echo.
venv\Scripts\python.exe setup\_preflight.py --address-only
echo.

venv\Scripts\python.exe -m uvicorn api.main:app --host 0.0.0.0 --port 8000 %SSL_ARGS%
pause
