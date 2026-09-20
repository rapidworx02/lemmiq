@echo off
setlocal
echo Stopping Tailscale Serve...
tailscale serve off
echo.
tailscale serve status
pause
