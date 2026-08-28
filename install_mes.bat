@echo off
title Formlabs MES SCADA Terminal Launcher
setlocal enabledelayedexpansion

echo ===================================================
echo 🚀 Formlabs MES SCADA Terminal - Auto-Setup & Launch
echo ===================================================
echo.

:: 1. CHECK & AUTOMATE PYTHON INSTALLATION
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ⚠️ Python was not detected on this system!
    echo 📥 Downloading Python 3.11 Installer...
    powershell -Command "Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.11.8/python-3.11.8-amd64.exe' -OutFile 'python_installer.exe'"
    
    echo ⚙️ Running silent background installation of Python...
    python_installer.exe /quiet InstallAllUsers=1 PrependPath=1 Include_test=0
    del python_installer.exe
    
    echo ✅ Python installation complete!
    echo 🔄 Refreshing environment PATH...
    set "PATH=%SystemDrive%\Program Files\Python311;%SystemDrive%\Program Files\Python311\Scripts;%PATH%"
) else (
    echo ✅ Python installation detected.
)

:: 2. VIRTUAL ENVIRONMENT SETUP & DEPENDENCY INSTALLATION
if not exist venv (
    echo 📦 Creating isolated Python virtual environment...
    python -m venv venv
    call venv\Scripts\activate
    echo 📥 Upgrading pip and installing required packages...
    python -m pip install --upgrade pip
    if exist requirements.txt (
        pip install -r requirements.txt
    ) else (
        echo ⚠️ requirements.txt missing! Installing default stack...
        pip install streamlit pandas plotly sqlalchemy psycopg2-binary python-dotenv fpdf extra-streamlit-components requests
    )
) else (
    call venv\Scripts\activate
)

:: 3. LAUNCH STREAMLIT APPLICATION
echo.
echo ⚡ Starting Live SCADA App...
streamlit run app.py

pause