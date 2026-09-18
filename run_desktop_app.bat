@echo off
title BorsTerminal Desktop Launcher
echo ========================================================
echo   BorsTerminal Ultimate - Standalone Desktop App
echo ========================================================

set ROOT=%~dp0
cd /d "%ROOT%"

set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

python bootstrap_first_run.py
python start_dashboard.py --port 8000
pause
