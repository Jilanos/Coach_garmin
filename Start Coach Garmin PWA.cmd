@echo off
setlocal
cd /d "%~dp0"

set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" set "PYTHON_EXE=python"

echo Starting Coach Garmin PWA server...
start "Coach Garmin PWA" "%PYTHON_EXE%" -m coach_garmin web serve --web-root web --data-dir data

timeout /t 2 /nobreak >nul
start "" "http://127.0.0.1:5284/?v=20260413"

endlocal
