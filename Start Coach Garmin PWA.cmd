@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" set "PYTHON_EXE=python"

set "LOG_DIR=%~dp0logs"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%" >nul 2>nul
set "LOG_FILE=%LOG_DIR%\pwa-launch.log"
set "ERR_FILE=%LOG_DIR%\pwa-launch.err.log"
set "SERVER_PID_FILE=%LOG_DIR%\pwa-server.pid"
set "RESET_URL=http://127.0.0.1:5284/reset-cache?next=%%2F%%3Fv%%3D20260414-navfix17%%26v%%3D20260414-navfix17"

echo Starting Coach Garmin PWA server...
echo Launch log: %LOG_FILE%
echo Error log: %ERR_FILE%
echo.

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ErrorActionPreference='Stop';" ^
  "$python = '%PYTHON_EXE%';" ^
  "$log = '%LOG_FILE%';" ^
  "$err = '%ERR_FILE%';" ^
  "$pidFile = '%SERVER_PID_FILE%';" ^
  "$proc = Start-Process -FilePath $python -ArgumentList @('-m','coach_garmin','web','serve','--web-root','web','--data-dir','data') -WorkingDirectory (Get-Location).Path -RedirectStandardOutput $log -RedirectStandardError $err -PassThru;" ^
  "Set-Content -Path $pidFile -Value $proc.Id;"

echo Waiting for the server to become ready...
set "READY=0"
for /l %%i in (1,1,45) do (
  powershell -NoProfile -Command "try { (Invoke-WebRequest -Uri 'http://127.0.0.1:5284/' -UseBasicParsing -TimeoutSec 2).StatusCode } catch { exit 1 }" >nul 2>nul
  if not errorlevel 1 (
    set "READY=1"
    goto :open_browser
  )
  timeout /t 1 /nobreak >nul
)

echo.
echo The PWA server did not become ready in time.
echo Check the log file:
echo   %LOG_FILE%
echo   %ERR_FILE%
echo.
if exist "%LOG_FILE%" type "%LOG_FILE%"
echo.
if exist "%ERR_FILE%" type "%ERR_FILE%"
echo.
pause
exit /b 1

:open_browser
start "" explorer.exe "%RESET_URL%"
echo Browser opened. Keep this terminal open if you want to inspect the server state.
exit /b 0









