@echo off
rem ============================================================
rem  apply_update.bat - BorsTerminal_Ultimate modular updater
rem  Put this file next to BorsTerminal_Update.zip (the patch zip
rem  already contains both) and double-click. It will:
rem    1) stop the running app (graceful, then forced)
rem    2) extract the patch zip in place (flat overlay)
rem    3) stamp Version.txt
rem    4) sync the uninstall registry so Add/Remove Programs agrees
rem    5) relaunch BorsTerminal_Ultimate.exe
rem  User data (market.db, *.lzma, adb/codal configs, logs) is
rem  never part of the patch, so it can never be overwritten.
rem  Note: a patch may replace this script itself. Because the worker has
rem  to be copied to %TEMP% before extraction, it would otherwise always be
rem  the PRE-update version; after extracting, it re-enters the freshly
rem  extracted copy so every fix takes effect on THIS update, not the next.
rem ============================================================
setlocal
rem phase2 dispatch: the worker copy (in %TEMP%) re-enters here with
rem "phase2 <install-dir>" as %1/%2 -- it must skip the front-matter.
if /i "%~1"=="phase2" goto phase2
if /i "%~1"=="phase3" goto phase3
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

echo [1/5] Stopping %EXE% (graceful) ...
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

echo [2/5] Extracting update ...
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

rem The patch may ship a newer copy of this script. The running worker was
rem copied to %TEMP% *before* extraction, so it is always the PRE-update
rem version -- without the re-entry below, any fix here would only reach the
rem user on their NEXT update. WORKER2 is a byte copy of the extracted file,
rem so the chain cannot loop.
set "SELFUPDATE="
if exist "%TARGET%\apply_update.bat" (
  fc /b "%~f0" "%TARGET%\apply_update.bat" >nul 2>&1 || set "SELFUPDATE=1"
)
if not defined SELFUPDATE goto finalize
set "WORKER2=%TEMP%\bors_apply_update_worker2.bat"
copy /y "%TARGET%\apply_update.bat" "%WORKER2%" >nul 2>&1
if not exist "%WORKER2%" goto finalize
echo        extracted a newer apply_update.bat - re-entering it.
cmd /c ""%WORKER2%" phase3 "%TARGET%""
set "RC2=%errorlevel%"
del "%WORKER2%" >nul 2>&1
exit /b %RC2%

:phase3
rem re-entry point for the freshly extracted applier: %~2 is the install dir.
set "TARGET=%~2"
cd /d "%TARGET%" 2>nul

:finalize
echo [3/5] Stamping version marker ...
if not exist "%TARGET%\Version.txt" echo updated>"%TARGET%\Version.txt"

echo [4/5] Syncing Add/Remove Programs ...
rem Add/Remove Programs reads DisplayVersion from the uninstall registry.
rem The Inno installer sets it, but a patch only overlays files, so without
rem this sync the entry would keep advertising the version we just replaced.
set "NEWVER="
for /f "usebackq tokens=2 delims==" %%V in (`findstr /b /i "app_version=" "%TARGET%\Version.txt" 2^>nul`) do set "NEWVER=%%V"
if not defined NEWVER goto noreg
set "UKEY=HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\{8F3A2E7C-1B44-4C2E-9A77-0B0B5C0DE001}_is1"
reg add "%UKEY%" /v DisplayVersion /t REG_SZ /d "%NEWVER%" /f >nul 2>&1
if not errorlevel 1 goto regok
reg add "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\{8F3A2E7C-1B44-4C2E-9A77-0B0B5C0DE001}_is1" /v DisplayVersion /t REG_SZ /d "%NEWVER%" /f >nul 2>&1
:regok
echo        Add/Remove Programs version -^> %NEWVER%
:noreg

echo [5/5] Relaunching ...
if defined BORS_UPDATE_NORELAUNCH (
  echo        BORS_UPDATE_NORELAUNCH is set - skipping start.
  exit /b 0
)
start "" "%TARGET%\%EXE%"
exit /b 0
