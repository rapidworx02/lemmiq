@echo off
setlocal EnableExtensions
set "SOURCE=%~dp0"
set "TARGET=C:\Users\pc\LEMMIQ"

echo.
echo ============================================================
echo   LEMMIQ - FORCE BACKEND ROLLBACK TO V2.10.7
echo ============================================================
echo.
echo Source: %SOURCE%
echo Target: %TARGET%
echo.

if not exist "%TARGET%\backend" (
  echo ERROR: %TARGET%\backend was not found.
  pause
  exit /b 1
)

echo [1/7] Creating backup...
powershell -NoProfile -Command "Compress-Archive -Path '%TARGET%\backend\app','%TARGET%\backend\web','%TARGET%\backend\migrations' -DestinationPath '%TARGET%\BACKUP_BEFORE_FORCE_V2107.zip' -Force"
if errorlevel 1 (
  echo ERROR: Backup failed. Stopping.
  pause
  exit /b 1
)

echo [2/7] Mirroring V2.10.7 backend\app...
robocopy "%SOURCE%backend\app" "%TARGET%\backend\app" /MIR /NFL /NDL /NJH /NJS /NP >nul
if errorlevel 8 (
  echo ERROR: app rollback failed.
  pause
  exit /b 1
)

echo [3/7] Mirroring V2.10.7 backend\migrations...
robocopy "%SOURCE%backend\migrations" "%TARGET%\backend\migrations" /MIR /NFL /NDL /NJH /NJS /NP >nul
if errorlevel 8 (
  echo ERROR: migrations rollback failed.
  pause
  exit /b 1
)

echo [4/7] Overlaying V2.10.7 web files...
REM IMPORTANT: /E instead of /MIR keeps legacy v28.js/v29.js/v28.css/v29.css and static assets.
robocopy "%SOURCE%backend\web" "%TARGET%\backend\web" /E /NFL /NDL /NJH /NJS /NP >nul
if errorlevel 8 (
  echo ERROR: web rollback failed.
  pause
  exit /b 1
)

REM Remove V2.10.8-only browser files if they are still present.
del /q "%TARGET%\backend\web\v2108.js" 2>nul
del /q "%TARGET%\backend\web\v2108.css" 2>nul

echo [5/7] Verifying the rollback...
findstr /C:"version=\"2.10.7\"" "%TARGET%\backend\app\main.py" >nul
if errorlevel 1 (
  echo ERROR: backend\app\main.py is NOT V2.10.7.
  pause
  exit /b 1
)

findstr /C:"register_v2108" "%TARGET%\backend\app\main.py" >nul
if not errorlevel 1 (
  echo ERROR: V2.10.8 registration is still present in main.py.
  pause
  exit /b 1
)

if exist "%TARGET%\backend\app\v2108.py" (
  echo ERROR: backend\app\v2108.py still exists.
  pause
  exit /b 1
)

if exist "%TARGET%\backend\app\admin_permissions.py" (
  echo ERROR: backend\app\admin_permissions.py still exists.
  pause
  exit /b 1
)

if not exist "%TARGET%\backend\web\v28.js" (
  echo ERROR: backend\web\v28.js is missing.
  echo The V2.10.7 web shell requires the existing legacy v28.js file.
  pause
  exit /b 1
)

if not exist "%TARGET%\backend\web\v29.js" (
  echo ERROR: backend\web\v29.js is missing.
  echo The V2.10.7 web shell requires the existing legacy v29.js file.
  pause
  exit /b 1
)

echo [6/7] Running Git checks...
cd /d "%TARGET%"
git status
echo.
git diff --stat
echo.

echo [7/7] Rollback files are ready.
echo.
echo REQUIRED NEXT COMMANDS:
echo   git add -A backend
echo   git commit -m "Force restore LEMMIQ backend to stable V2.10.7"
echo   git push origin main
echo.
echo After Render deploys, /app-config MUST report 2.10.7.
echo.
pause
