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
streamlit run Home.py --server.address=0.0.0.0
pause
