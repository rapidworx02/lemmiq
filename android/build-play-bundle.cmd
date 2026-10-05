@echo off
setlocal
cd /d "%~dp0"

if not exist keystore.properties (
  echo Missing android\keystore.properties
  echo Copy keystore.properties.example to keystore.properties and enter your upload-key details.
  exit /b 1
)
if not exist upload-keystore.jks (
  echo Missing android\upload-keystore.jks
  echo Run create-upload-key.cmd first or place your existing upload keystore here.
  exit /b 1
)
if not exist app\google-services.json (
  echo Missing android\app\google-services.json
  echo LEMMIQ push notifications require the Firebase configuration in the Play build.
  exit /b 1
)

where gradle >nul 2>nul
if errorlevel 1 (
  echo Gradle was not found on PATH.
  echo Open the Android project in Android Studio and use Build - Generate App Bundles,
  echo or install Gradle 9.6 and try again.
  exit /b 1
)

echo Building signed LEMMIQ V2.7.1 Android App Bundle...
gradle clean :app:bundleRelease --stacktrace
if errorlevel 1 exit /b 1

echo.
echo SUCCESS
echo AAB: %CD%\app\build\outputs\bundle\release\app-release.aab
endlocal
