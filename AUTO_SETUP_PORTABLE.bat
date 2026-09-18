@echo off
chcp 65001 >nul
title BorsTerminal FTS - 1-Click Automated Portable Creator
cd /d "%~dp0"
echo =====================================================================
echo    BorsTerminal Ultimate - 1-Click Automated Portable Setup v2.1
echo =====================================================================
echo.
python auto_setup_portable.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [!] مشکلی رخ داد یا برنامه متوقف شد.
)
echo.
pause
