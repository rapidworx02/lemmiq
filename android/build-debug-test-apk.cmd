@echo off
setlocal
cd /d "%~dp0"
where gradle >nul 2>nul
if errorlevel 1 (
  echo ERROR: Gradle is not on PATH.
  exit /b 1
)
gradle :app:assembleDebug --stacktrace
if errorlevel 1 exit /b 1
echo Debug APK:
echo %CD%\app\build\outputs\apk\debug\app-debug.apk
exit /b 0
