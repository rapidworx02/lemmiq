@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo ERROR: Backend is not set up yet.
  echo Run 01_SETUP_WINDOWS.bat first.
  pause
  exit /b 1
)

if not exist ".env" (
  echo ERROR: backend\.env does not exist.
  echo Copy .env.example to .env and fill in the values.
  pause
  exit /b 1
)

call ".venv\Scripts\activate.bat"

echo ==========================================
echo Starting LEMMIQ local backend
echo ==========================================
echo Local health test:
echo   http://127.0.0.1:8080/health
echo.
echo This build intentionally listens only on localhost.
echo Tailscale Serve will expose it privately over HTTPS.
echo Keep this window open.
echo.

python -m uvicorn app.main:app --host 127.0.0.1 --port 8080
pause
