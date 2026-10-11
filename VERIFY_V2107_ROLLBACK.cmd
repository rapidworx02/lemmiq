@echo off
cd /d C:\Users\pc\LEMMIQ
echo ===== MAIN VERSION =====
findstr /n /C:"FastAPI(title=" backend\app\main.py
findstr /n /C:"\"version\": \"2.10.7\"" backend\app\main.py
echo.
echo ===== V2.10.8 MUST NOT APPEAR BELOW =====
findstr /n /i "register_v2108 admin_permissions" backend\app\main.py
echo.
echo ===== V2.10.8 FILE CHECK =====
if exist backend\app\v2108.py (echo BAD: v2108.py exists) else (echo OK: v2108.py absent)
if exist backend\app\admin_permissions.py (echo BAD: admin_permissions.py exists) else (echo OK: admin_permissions.py absent)
echo.
echo ===== REQUIRED LEGACY WEB FILES =====
if exist backend\web\v28.js (echo OK: v28.js present) else (echo BAD: v28.js missing)
if exist backend\web\v29.js (echo OK: v29.js present) else (echo BAD: v29.js missing)
if exist backend\web\v28.css (echo OK: v28.css present) else (echo BAD: v28.css missing)
if exist backend\web\v29.css (echo OK: v29.css present) else (echo BAD: v29.css missing)
echo.
pause
