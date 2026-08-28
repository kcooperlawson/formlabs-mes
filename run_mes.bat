@echo off  
cd /d %~dp0  
python -m streamlit run home.py --server.address=0.0.0.0
pause