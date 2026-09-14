@echo off
rem ============================================================
rem  apply_update.bat - BorsTerminal_Ultimate modular updater
rem  Put this file next to BorsTerminal_Update.zip (the patch zip
rem  already contains both) and double-click. It will:
rem    1) stop the running app (graceful, then forced)
rem    2) extract the patch zip in place (flat overlay)
rem    3) stamp Version.txt
rem    4) relaunch BorsTerminal_Ultimate.exe
rem  User data (market.db, *.lzma, adb/codal configs, logs) is
rem  never part of the patch, so it can never be overwritten.
rem ============================================================
setlocal
rem phase2 dispatch: the worker copy (in %TEMP%) re-enters here with
rem "phase2 <install-dir>" as %1/%2 -- it must skip the front-matter.
if /i "%~1"=="phase2" goto phase2
set "TARGET=%~dp0"
set "ZIP=%~dp0BorsTerminal_Update.zip"
if not exist "%ZIP%" (
  echo [ERR] %ZIP% not found.
  echo       Keep apply_update.bat and BorsTerminal_Update.zip together.
  pause
  exit /b 1
)
rem Re-run from %TEMP% so extraction can safely overwrite this file.
set "WORKER=%TEMP%\bors_apply_update_worker.bat"
copy /y "%~f0" "%WORKER%" >nul
if "%TARGET:~-1%"=="\" set "TARGET=%TARGET:~0,-1%"
cmd /c ""%WORKER%" phase2 "%TARGET%""
set "RC=%errorlevel%"
del "%WORKER%" >nul 2>&1
echo.
echo Update finished with code %RC%. This window can be closed.
pause
exit /b %RC%

:phase2
setlocal
set "TARGET=%~2"
cd /d "%TARGET%" || exit /b 1
set "ZIP=%TARGET%\BorsTerminal_Update.zip"
set "EXE=BorsTerminal_Ultimate.exe"

echo [1/4] Stopping %EXE% (graceful) ...
taskkill /IM "%EXE%" >nul 2>&1
set /a TRIES=0
:waitloop
tasklist /FI "IMAGENAME eq %EXE%" 2>nul | find /I "%EXE%" >nul
if errorlevel 1 goto stopped
set /a TRIES+=1
if %TRIES% GEQ 8 goto forcekill
ping -n 2 127.0.0.1 >nul
goto waitloop
:forcekill
echo        still running - force closing ...
taskkill /F /IM "%EXE%" >nul 2>&1
ping -n 3 127.0.0.1 >nul
:stopped
echo        app stopped.

echo [2/4] Extracting update ...
where tar >nul 2>&1
if errorlevel 1 goto ps_extract
tar -xf "%ZIP%"
if errorlevel 1 goto ps_extract
goto extract_done
:ps_extract
powershell -NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -LiteralPath '%ZIP%' -DestinationPath '%TARGET%\.' -Force"
if errorlevel 1 (
  echo [ERR] extraction failed - update aborted, old files intact.
  exit /b 1
)
:extract_done
if not exist "%TARGET%\_internal" (
  echo [ERR] extraction produced no _internal folder - update aborted.
  exit /b 1
)

echo [3/4] Stamping version marker ...
if not exist "%TARGET%\Version.txt" echo updated>"%TARGET%\Version.txt"

echo [4/4] Relaunching ...
if defined BORS_UPDATE_NORELAUNCH (
  echo        BORS_UPDATE_NORELAUNCH is set - skipping start.
  exit /b 0
)
start "" "%TARGET%\%EXE%"
exit /b 0
