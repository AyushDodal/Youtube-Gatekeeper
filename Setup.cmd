@echo off
setlocal
cd /d "%~dp0"
where python >nul 2>&1
if errorlevel 1 (
  echo Install Python 3.11 or newer and add it to PATH.
  exit /b 1
)
if not exist .venv\Scripts\python.exe python -m venv .venv
if errorlevel 1 exit /b 1
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 exit /b 1
pushd frontend
call npm.cmd ci
if errorlevel 1 (
  popd
  exit /b 1
)
call npm.cmd run build
if errorlevel 1 (
  popd
  exit /b 1
)
popd
if not exist .env copy .env.example .env >nul
echo Setup complete. Set OLLAMA_MODEL in .env, then run Start.cmd as administrator.
echo Start-preview.cmd runs a clearly labeled simulation without administrator rights.
