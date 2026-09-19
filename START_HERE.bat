@echo off
rem ===================================================================
rem  Formlabs MES - the one thing you double-click on any PC.
rem
rem  This is deliberately the ONLY entry point. Everything else lives in
rem  setup\ and is called from here, so there is never a question of
rem  "which .bat do I run on this machine".
rem ===================================================================
title Formlabs MES
cd /d "%~dp0"

:menu
cls
echo.
echo  ===================================================
echo   FORMLABS MES
echo  ===================================================
echo.
if exist "venv\Scripts\python.exe" (
    echo   This PC:  set up  ^(venv is present^)
) else (
    echo   This PC:  NOT set up yet  ^(no venv^)
)
echo.
echo   INSTALL - do once per PC
echo     1  Install the MES / Logger   ^(bundled database - nothing else to install^)
echo     2  Install the Device Gateway ^(this PC only talks to machines^)
echo    14  Install the MES on this PC's own PostgreSQL  ^(only if you need one^)
echo.
echo   RUN - every day
echo     3  Start the MES / Logger
echo     4  Start the Device Gateway
echo     9  Start the MES - always the bundled database
echo    12  Check the Device Gateway ^(can this PC reach the database and the machines?^)
echo    15  Let a Device Gateway PC reach this PC's database
echo.
echo     5  Diagnose this PC ^(what is missing, what is wrong^)
echo     6  Package this project for another PC
echo.
echo   UPDATE
echo     7  Apply an update ^(from the updates folder^)
echo    16  Host updates for other PCs ^(serves what is in dist\^)
echo    13  Repair the updater ^(only if 7 stops on "the backup failed"^)
echo.
echo   SECURITY
if exist "certs\mes.crt" (
    echo     8  HTTPS certificate ^(present - renew it^)
) else (
    echo     8  HTTPS certificate ^(NOT set up - the MES is running on plain HTTP^)
)
echo.
echo   ACCOUNTS
echo    10  Create an admin login  ^(this PC's PostgreSQL^)
echo    11  Create an admin login  ^(bundled/portable database^)
echo.
echo     Q  Quit
echo.
set "PICK="
set /p "PICK=  Choose and press Enter: "

if /i "%PICK%"=="1" goto :install_mes
if /i "%PICK%"=="2" goto :install_gw
if /i "%PICK%"=="3" goto :run_mes
if /i "%PICK%"=="4" goto :run_gw
if /i "%PICK%"=="5" goto :diagnose
if /i "%PICK%"=="6" goto :package
if /i "%PICK%"=="7" goto :update
if /i "%PICK%"=="8" goto :tls_cert
if /i "%PICK%"=="9" goto :run_mes_portable
if /i "%PICK%"=="10" goto :create_admin
if /i "%PICK%"=="11" goto :create_admin_portable
if /i "%PICK%"=="12" goto :check_gw
if /i "%PICK%"=="13" goto :repair_updater
if /i "%PICK%"=="14" goto :install_mes_postgres
if /i "%PICK%"=="15" goto :gateway_access
if /i "%PICK%"=="16" goto :host_updates
if /i "%PICK%"=="Q" goto :eof
goto :menu

:install_mes
rem The standard install: the database is the one bundled with the app
rem (pgserver, out of pgdata\), so there is no PostgreSQL to install, no
rem service, no password to invent, and nothing for IT to approve.
rem run_mes_portable.bat already does every step this needs - Python, the
rem venv, the packages, the frontend check - so it does them here too, and
rem stops before starting the app.
call "run_mes_portable.bat" --install-only
echo.
pause
goto :menu

:install_mes_postgres
rem The other way: this PC's own PostgreSQL install. Still supported, and
rem still what a PC that already has one should use - but not the path
rem anybody has to take any more.
call "setup\install_mes.bat"
echo.
pause
goto :menu

:install_gw
call "setup\install_gateway.bat"
echo.
pause
goto :menu

:run_mes
rem One "start the app" for both kinds of PC. A PC whose .env names a real
rem database uses it (that's an install done through option 14, or an older
rem PC that predates the bundled database); every other PC uses the bundled
rem one. Nobody has to remember which kind of PC they're sitting at, and a
rem move package that lands on either kind starts the same way.
rem Option 9 forces the bundled database whatever .env says.
set "HAS_DBURL="
if exist ".env" (
    for /f "usebackq tokens=1,* delims==" %%a in (`findstr /b /c:"DB_URL=" ".env" 2^>nul`) do (
        if not "%%b"=="" if /i not "%%b"=="auto" set "HAS_DBURL=1"
    )
)
if not defined HAS_DBURL (
    echo.
    echo  Using the bundled database ^(no DB_URL in .env^).
    goto :run_mes_portable
)

rem Inlined from what used to be a separate run_mes_api.bat, so this file
rem really is the only thing anyone opens. Launches uvicorn against this
rem PC's own PostgreSQL (.env's DB_URL).
if not exist venv\Scripts\python.exe (
    echo.
    echo  [ERROR] No venv folder here yet. Choose 1 above first - it
    echo          creates the virtual environment and installs everything.
    pause
    goto :menu
)

rem Deliberately venv\Scripts\python.exe -m uvicorn, not "call activate.bat"
rem then a bare "uvicorn" - activate.bat bakes in the ABSOLUTE path the venv
rem was first created at (its own VIRTUAL_ENV= line), so a venv created
rem before this project last moved folders silently prepends a dead PATH
rem entry, and every bare command name after it - uvicorn included -
rem resolves to nothing. Calling the interpreter by its path relative to
rem this file sidesteps that entirely: it only depends on venv\ still
rem being where this .bat is, which a moved folder never breaks.

rem The React build has to exist before uvicorn can serve it - api/main.py
rem only mounts frontend\dist at all if the folder is there, and serves API
rem routes with no frontend behind them otherwise. Checked here rather than
rem built here: shelling out to npm on every launch would mean this menu
rem needs Node.js installed and working too, for a build step that only
rem has to happen again after the frontend's own source changes.
if not exist frontend\dist\index.html (
    echo.
    echo  [ERROR] The frontend hasn't been built yet - frontend\dist\index.html
    echo          is missing. From the frontend\ folder, run:
    echo              npm install
    echo              npm run build
    echo          Then choose 3 again.
    pause
    goto :menu
)

rem HTTPS if certs\mes.crt / mes.key exist (option 8 below writes them),
rem plain HTTP otherwise.
set "SSL_ARGS="
if exist certs\mes.crt if exist certs\mes.key set "SSL_ARGS=--ssl-certfile certs\mes.crt --ssl-keyfile certs\mes.key"
if not defined SSL_ARGS echo  [!] No HTTPS certificate - running on plain HTTP. See option 8 above.

rem setup\_preflight.py works out the LAN IP/hostname and the right
rem http/https scheme (same logic option 5 and Check_This_PC.bat use) -
rem reused here so whoever starts this sees the address to give the
rem phones immediately, with nothing else to run first.
echo.
venv\Scripts\python.exe setup\_preflight.py --address-only
echo.

rem Started in a loop so the app can restart itself after applying an update:
rem it asks the server to stop and leaves updates\.restart-requested behind,
rem and this starts it again. See setup\self_restart.py - nothing tries to
rem kill or relaunch a server on its own any more.
set "MES_SUPERVISED=1"

:run_mes_loop
if exist "updates\.restart-requested" del /q "updates\.restart-requested" >nul 2>&1
venv\Scripts\python.exe -m uvicorn api.main:app --host 0.0.0.0 --port 8000 %SSL_ARGS%
if not exist "updates\.restart-requested" goto :run_mes_done
echo.
echo  Update applied - restarting the app...
timeout /t 3 /nobreak >nul
goto :run_mes_loop

:run_mes_done
set "MES_SUPERVISED="
pause
goto :menu

:run_mes_portable
call "run_mes_portable.bat"
goto :menu

:create_admin
if not exist "venv\Scripts\python.exe" goto :not_setup
echo.
venv\Scripts\python.exe "setup\create_admin_login.py"
echo.
pause
goto :menu

:create_admin_portable
rem Same venv this PC's regular install (option 1) also uses, but that
rem install only ever pulls in requirements.txt - pgserver lives in
rem requirements-portable.txt, the same extra option 9 installs on its own
rem first run. A PC that only ever chose 1 needs it added here too, or
rem this fails on an import error instead of a useful message.
if not exist "venv\Scripts\python.exe" goto :not_setup
venv\Scripts\python.exe -c "import pgserver" >nul 2>&1
if errorlevel 1 (
    echo.
    echo  Installing the bundled-database package - only needed once...
    venv\Scripts\python.exe -m pip install -r requirements-portable.txt
    if errorlevel 1 (
        echo.
        echo  [ERROR] Could not install requirements-portable.txt. Check your
        echo          internet connection and try again.
        pause
        goto :menu
    )
)
echo.
venv\Scripts\python.exe "setup\create_admin_login.py" --portable
echo.
pause
goto :menu

:run_gw
if not exist "venv\Scripts\python.exe" goto :not_setup
echo.
echo  Starting the Device Gateway. Close this window to stop it.
echo.
venv\Scripts\python.exe run_gateway.py
echo.
pause
goto :menu

:host_updates
if not exist "venv\Scripts\python.exe" goto :not_setup
echo.
echo  Serves the update packages in dist\ to other PCs - read-only, nothing
echo  else on this PC is reachable through it. On the other PC: IT Admin,
echo  Updates, and enter this PC's address.
echo.
set "UPD_PORT="
set /p "UPD_PORT=  Port to listen on [8443]: "
if not defined UPD_PORT set "UPD_PORT=8443"
set "UPD_TOKEN="
set /p "UPD_TOKEN=  Password for it (Enter for none): "
echo.
if defined UPD_TOKEN (
    venv\Scripts\python.exe "setup\update_server.py" --port %UPD_PORT% --token "%UPD_TOKEN%"
) else (
    venv\Scripts\python.exe "setup\update_server.py" --port %UPD_PORT%
)
echo.
pause
goto :menu

:gateway_access
if not exist "venv\Scripts\python.exe" goto :not_setup
echo.
echo  The bundled database is private to this PC by default. This gives it a
echo  fixed port and a password so a Device Gateway PC on the floor can write
echo  readings into it, and prints the two lines you need ^(one firewall rule
echo  here, one .env line there^).
echo.
choice /c EDC /m "  E = turn it on, D = turn it off, C = just show me how it is"
if errorlevel 3 (
    venv\Scripts\python.exe "setup\portable_lan_access.py"
) else if errorlevel 2 (
    venv\Scripts\python.exe "setup\portable_lan_access.py" --disable
) else (
    venv\Scripts\python.exe "setup\portable_lan_access.py" --enable
)
echo.
pause
goto :menu

:repair_updater
if not exist "venv\Scripts\python.exe" goto :not_setup
echo.
echo  Takes the updater's own files out of the signed package in updates\ so
echo  this PC can accept updates. It does NOT install the update itself -
echo  run option 7 after this. Nothing else is changed, and the database is
echo  not touched.
echo.
venv\Scripts\python.exe "setup\bootstrap_update.py"
echo.
pause
goto :menu

:check_gw
if not exist "venv\Scripts\python.exe" goto :not_setup
echo.
echo  Checking this PC as a Device Gateway: the database login, the encryption
echo  key, and every registered machine's address or COM port. Nothing is changed.
echo.
venv\Scripts\python.exe run_gateway.py --check
echo.
pause
goto :menu

:diagnose
echo.
if not exist "venv\Scripts\python.exe" goto :diagnose_novenv
venv\Scripts\python.exe "setup\_preflight.py"
echo.
pause
goto :menu

:diagnose_novenv
call "setup\_ensure_python.bat" noinstall
if not defined PY_CMD goto :diagnose_nopy
%PY_CMD% "setup\_preflight.py"
echo.
pause
goto :menu

:diagnose_nopy
echo  [X] No Python on this PC at all, and no venv. Choose 1 or 2 first.
echo.
pause
goto :menu

:package
if not exist "Move_To_New_PC.bat" (
    echo.
    echo  Move_To_New_PC.bat is missing from this folder.
    echo.
    pause
    goto :menu
)
call "Move_To_New_PC.bat"
goto :menu

:update
rem Applies a package somebody built at home and carried over. The applier
rem lives here, on this PC; the thing on the USB stick is only files and a
rem list of them, so nothing arriving on a stick ever executes.
if not exist "venv\Scripts\python.exe" goto :not_setup
if not exist "updates" mkdir "updates"
echo.
venv\Scripts\python.exe "setup\apply_update.py"
echo.
pause
goto :menu

:tls_cert
if not exist "venv\Scripts\python.exe" goto :not_setup
echo.
venv\Scripts\python.exe "setup\generate_tls_cert.py"
echo.
pause
goto :menu

:not_setup
echo.
echo  This PC has not been set up yet. Choose 1 ^(MES^) or 2 ^(Gateway^) first.
echo.
pause
goto :menu
