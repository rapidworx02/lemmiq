@echo off
setlocal
set "ROOT=C:\Users\pc\LEMMIQ"
cd /d "%~dp0"
echo.
echo LEMMIQ V2.12 -- AI Image Generation updater
if not exist "%ROOT%\backend\app\main.py" (
  echo Project not found: %ROOT%
  exit /b 1
)
echo === Dry-run compatibility check ===
py -3 APPLY_V2.12.py --repo "%ROOT%" --dry-run
if errorlevel 1 (echo Dry-run failed. Your files are unchanged.&exit /b 1)
choice /M "Apply the update and create a source backup"
if errorlevel 2 exit /b 0
py -3 APPLY_V2.12.py --repo "%ROOT%"
if errorlevel 1 exit /b 1
echo.
echo Update applied. NOTE: AI image generation stays OFF until configured on Render.
echo Review git diff and run Android Gradle build from %ROOT%\android.
endlocal
