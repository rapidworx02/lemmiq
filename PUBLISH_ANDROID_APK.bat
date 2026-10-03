@echo off
setlocal
cd /d "%~dp0"

set "RELEASE_APK=android\app\build\outputs\apk\release\app-release.apk"
set "DEBUG_APK=android\app\build\outputs\apk\debug\app-debug.apk"
set "TARGET=backend\web\downloads\LEMMIQ.apk"

if exist "%RELEASE_APK%" (
  set "SOURCE=%RELEASE_APK%"
) else if exist "%DEBUG_APK%" (
  set "SOURCE=%DEBUG_APK%"
) else (
  echo.
  echo No APK found.
  echo Build the app first in Android Studio:
  echo   Build ^> Build APK(s)
  echo.
  echo Expected one of:
  echo   %RELEASE_APK%
  echo   %DEBUG_APK%
  pause
  exit /b 1
)

if not exist "backend\web\downloads" mkdir "backend\web\downloads"
copy /Y "%SOURCE%" "%TARGET%" >nul

echo.
echo LEMMIQ APK copied to:
echo   %TARGET%
echo.
echo Next:
echo   git add .
echo   git commit -m "Publish LEMMIQ Android APK"
echo   git push origin main
echo.
echo After Render redeploys, testers can use:
echo   https://YOUR-RENDER-SERVICE.onrender.com/download/android
echo.
pause
