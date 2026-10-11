LEMMIQ V2.10.7 FORCE BACKEND ROLLBACK

WHY THIS PACKAGE EXISTS
The previous rollback did not actually reach the GitHub main backend.
The public main.py was still reporting V2.10.8 and still registering v2108.
This package uses a force/mirror restore for backend/app, while preserving legacy
v28.js / v29.js browser files required by the older web shell.

DO NOT MANUALLY DELETE backend\web.

FASTEST METHOD
1. Extract LEMMIQ_V2.10.7_FORCE_BACKEND_ROLLBACK.zip.
2. Open the extracted folder.
3. Double-click:
   FORCE_ROLLBACK_TO_V2107.cmd

The script:
- creates BACKUP_BEFORE_FORCE_V2107.zip
- mirrors backend/app to the clean V2.10.7 source
- removes V2.10.8-only Python files automatically
- mirrors backend/migrations
- overlays V2.10.7 web files WITHOUT deleting v28.js/v29.js and static assets
- removes v2108.js/v2108.css
- verifies main.py says V2.10.7
- verifies register_v2108 is gone
- verifies v28.js and v29.js are still present

WHEN THE SCRIPT FINISHES SUCCESSFULLY
Run:

cd /d C:\Users\pc\LEMMIQ
git add -A backend
git commit -m "Force restore LEMMIQ backend to stable V2.10.7"
git push origin main

WAIT FOR RENDER

Then open:
https://lemmiq-api.onrender.com/app-config

It MUST show:
"version": "2.10.7"

If it still says 2.10.8, stop testing Q Admin. Render/GitHub is still deploying the wrong source.

BROWSER RESET AFTER RENDER SHOWS 2.10.7
1. Close every LEMMIQ tab.
2. Clear site data for lemmiq-api.onrender.com once.
3. Open:
   https://lemmiq-api.onrender.com/web/
4. Sign in.
5. Open More > Q Admin.

The rollback web cache is:
lemmiq-v2107-rollback-1

IMPORTANT
Do not re-apply any V2.10.8 Q Admin hotfix ZIP after this rollback.
Those files are intentionally removed.
