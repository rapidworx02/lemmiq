@echo off
setlocal
cd /d "%~dp0"

echo ===============================================
echo LEMMIQ V2.8.2 - Manual Tester Release APK
echo ===============================================

echo.
if not exist "keystore.properties" (
  echo ERROR: android\keystore.properties is missing.
  echo Keep your existing private signing file in this folder.
  exit /b 1
)

if not exist "upload-keystore.jks" (
  echo ERROR: android\upload-keystore.jks is missing.
  echo Keep your existing LEMMIQ upload keystore in this folder.
  exit /b 1
)

where gradle >nul 2>nul
if errorlevel 1 (
  echo ERROR: Gradle is not on PATH.
  echo Example PowerShell setup:
  echo   $env:JAVA_HOME = "C:\Program Files\Android\Android Studio\jbr"
  echo   $env:Path = "$env:JAVA_HOME\bin;C:\Gradle\gradle-9.6.0\bin;" + $env:Path
  exit /b 1
)

echo Building release-signed APK for manual testing...
gradle :app:assembleRelease --stacktrace
if errorlevel 1 exit /b 1

set SRC=%CD%\app\build\outputs\apk\release\app-release.apk
set OUT=%CD%\app\build\outputs\manual
if not exist "%SRC%" (
  echo ERROR: Release APK was not found at:
  echo %SRC%
  exit /b 1
)
if not exist "%OUT%" mkdir "%OUT%"
copy /Y "%SRC%" "%OUT%\LEMMIQ-v2.8.2-manual-release.apk" >nul

echo.
echo SUCCESS
echo Manual tester APK:
echo %OUT%\LEMMIQ-v2.8.2-manual-release.apk
echo.
echo IMPORTANT: This APK is signed with your LEMMIQ upload key, but because it
 echo is installed outside Google Play, Android/Play Protect can still show an
 echo unknown-source or app-scan warning. There is no safe file that bypasses
 echo Play Protect. Google Play internal testing is the normal way to get a
 echo Play-distributed build after you create a Play Console account.
exit /b 0
