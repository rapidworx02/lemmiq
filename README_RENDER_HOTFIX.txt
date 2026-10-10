LEMMIQ V2.10.5 Render Hotfix

Cause:
backend/app/v2104_q_features.py converted Render DATABASE_URL to plain
postgresql://. SQLAlchemy therefore selected the psycopg2 driver, but the
LEMMIQ backend uses psycopg v3 (postgresql+psycopg://).

Fix:
Replace:
backend/app/v2104_q_features.py

with the file in this hotfix.

No database reset is required.
Do not convert or delete Q wallet data.

Then:
git add backend/app/v2104_q_features.py
git commit -m "Fix V2.10.5 Render PostgreSQL driver"
git push origin main

Render should redeploy automatically.
