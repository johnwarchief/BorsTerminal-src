@echo off
title BorsTerminal Development Launcher
echo ========================================================
echo   BorsTerminal_Ultimate - Development Mode (Hot Reload)
echo ========================================================

set ROOT=%~dp0

echo [..] Starting FastAPI backend on port 8001...
start "Backend (Uvicorn)" cmd /k "cd /d ""%ROOT%"" && python -m uvicorn app:app --port 8001 --reload"

echo [..] Starting Vite frontend on port 5173...
start "Frontend (Vite)" cmd /k "cd /d ""%ROOT%frontend"" && npm run dev"

echo [..] Waiting for Vite frontend and opening standalone desktop window...
python "%ROOT%launch_desktop.py" --port 5173

echo ========================================================
echo [OK] Both servers are running.
echo      Frontend: http://localhost:5173/
echo      Backend:  http://127.0.0.1:8001/
echo ========================================================
pause
