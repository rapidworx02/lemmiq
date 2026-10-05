@echo off
setlocal
cd /d "%~dp0"

if exist upload-keystore.jks (
  echo upload-keystore.jks already exists.
  echo Delete or rename it only if you intentionally want a new Play upload key.
  exit /b 1
)

where keytool >nul 2>nul
if errorlevel 1 (
  echo keytool was not found. Install/use JDK 17 and make sure keytool is on PATH.
  exit /b 1
)

echo Creating the private LEMMIQ Play upload key.
echo Keep this JKS and its passwords safe. Never commit it to GitHub.
keytool -genkeypair -v -keystore upload-keystore.jks -alias lemmiq-upload -keyalg RSA -keysize 2048 -validity 10000

if errorlevel 1 exit /b 1

if not exist keystore.properties copy keystore.properties.example keystore.properties >nul

echo.
echo Upload key created: %CD%\upload-keystore.jks
echo Now edit: %CD%\keystore.properties
echo Then export the public certificate with:
echo keytool -export -rfc -keystore upload-keystore.jks -alias lemmiq-upload -file upload_certificate.pem
endlocal
