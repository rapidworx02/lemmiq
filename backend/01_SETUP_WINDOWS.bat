@echo off
setlocal
cd /d "%~dp0"

echo ==========================================
echo LEMMIQ V1.2.1 - Windows backend setup
echo ==========================================

where python >nul 2>nul
if errorlevel 1 (
  echo ERROR: Python was not found in PATH.
  echo Install Python 3.11 or 3.12, then run this file again.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo Creating Python virtual environment...
  python -m venv .venv
)

call ".venv\Scripts\activate.bat"

echo Updating pip...
python -m pip install --upgrade pip

echo Installing backend requirements...
pip install -r requirements.txt

if not exist ".env" (
  copy ".env.example" ".env" >nul
  echo.
  echo Created backend\.env
  echo Open it in Notepad and add your ANTHROPIC_API_KEY,
  echo TAVILY_API_KEY and a long LEMMIQ_JWT_SECRET.
) else (
  echo backend\.env already exists - leaving it unchanged.
)

echo.
echo Setup complete.
echo Next: edit backend\.env, then run 02_START_BACKEND_LOCAL.bat
pause
