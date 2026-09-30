@echo off
setlocal
cd /d "%~dp0"
set GATEKEEPER_DRY_RUN=true
if not exist .venv\Scripts\python.exe (
  echo Run Setup.cmd first.
  pause
  exit /b 1
)
.venv\Scripts\python.exe -m backend.run
if errorlevel 1 pause
