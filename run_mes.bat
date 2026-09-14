@echo off
cd /d %~dp0

rem Day-to-day launcher. Must go through the venv: Setup_On_New_PC.bat installs
rem every dependency INTO venv\, so launching with a bare "py -m streamlit"
rem uses the system Python instead and fails with "No module named streamlit"
rem on any PC where the packages were never installed system-wide.

if not exist venv\Scripts\activate.bat (
    echo [ERROR] No venv folder here yet.
    echo         Run Setup_On_New_PC.bat once first - it creates the virtual
    echo         environment and installs the dependencies.
    pause
    exit /b 1
)

call venv\Scripts\activate.bat

rem HTTPS if certs\mes.crt / mes.key exist (setup\generate_tls_cert.py writes
rem them), plain HTTP otherwise. Doesn't generate or check them here - that's
rem what generate_tls_cert.py and START_HERE.bat option 8 are for.
set "SSL_ARGS="
if exist certs\mes.crt if exist certs\mes.key set "SSL_ARGS=--server.sslCertFile=certs\mes.crt --server.sslKeyFile=certs\mes.key"
if not defined SSL_ARGS echo [!] No HTTPS certificate - running on plain HTTP. See START_HERE.bat option 8.

streamlit run Home.py --server.address=0.0.0.0 %SSL_ARGS%
pause
