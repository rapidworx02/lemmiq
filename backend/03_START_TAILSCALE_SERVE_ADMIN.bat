@echo off
setlocal
cd /d "%~dp0"

echo ==========================================
echo LEMMIQ - Tailscale Serve
echo ==========================================
echo IMPORTANT:
echo Run this BAT as Administrator.
echo Tailscale must already be installed and signed in.
echo.

where tailscale >nul 2>nul
if errorlevel 1 (
  echo ERROR: tailscale command was not found.
  echo Install Tailscale for Windows first.
  pause
  exit /b 1
)

echo Publishing local LEMMIQ port 8080 privately to your tailnet...
tailscale serve --bg http://127.0.0.1:8080

echo.
echo Current Tailscale Serve status:
tailscale serve status

echo.
echo Copy the HTTPS URL shown above.
echo Put it in android\local.properties as:
echo lemmiq.apiBaseUrl=https://YOUR-TAILSCALE-SERVE-NAME.ts.net
echo.
pause
