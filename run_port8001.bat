@echo off
rem BorsTerminal_Ultimate - smart launcher (port 8001)
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
python bootstrap_first_run.py
python start_dashboard.py --port 8001
pause
