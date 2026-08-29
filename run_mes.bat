@echo off  
cd /d %~dp0  
py -m streamlit run home.py --server.address=0.0.0.0
pause