# LEMMIQ V1.6.1 — GitHub + Render deployment

This is the V1.6 codebase (branded Android app, Q Chat Agent, Trust, Activity and notification-derived Money Agent), configured for GitHub + Render + PostgreSQL instead of desktop/Tailscale hosting.

## 1. Start from the extracted ZIP

Extract the ZIP and open the `LEMMIQ_V1_6_RENDER` directory. It contains `android`, `backend`, and `render.yaml` at the root.

**If an older LEMMIQ database exists on your desktop:** this process creates a **new, empty** Render PostgreSQL database. It does not migrate old users, chats or insights. Do not assume data will carry over.

## 2. GitHub (Windows CMD)

Create a **private**, empty GitHub repo, for example `lemmiq`. From the extracted project root:

```cmd
git init
git add .
git commit -m "LEMMIQ V1.6.1 GitHub Render"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/lemmiq.git
git push -u origin main
```

If you are updating an existing repo rather than starting a new one, copy the updated project files into your existing working tree and run `git add .`, `git commit`, `git push`. Do not run a second `git init` or `git remote add` unnecessarily. Confirm Git's author name/email if it reports "Author identity unknown":

```cmd
git config --global user.name "YOUR_NAME"
git config --global user.email "YOUR_GITHUB_EMAIL"
```

Make sure your remote URL is an actual repo you own and GitHub authentication is configured; otherwise `Repository not found` is not a LEMMIQ problem.

## 3. Render Blueprint

Render Dashboard → **New → Blueprint** → connect your `lemmiq` repository → confirm `render.yaml`.

This configuration requests:

- `lemmiq-api`: Docker FastAPI web service, **Free** by default;
- `lemmiq-db`: PostgreSQL, **Free** by default;
- `DATABASE_URL`: automatically linked from PostgreSQL;
- `LEMMIQ_JWT_SECRET`: generated automatically;
- `ANTHROPIC_API_KEY`: secret to enter;
- `TAVILY_API_KEY`: optional secret for current-web fact-checking;
- `ANTHROPIC_MODEL`: model ID in the configuration.

For an **existing Blueprint**, secrets specified with `sync: false` might require manual entry under Render → `lemmiq-api` → Environment. Leave `DATABASE_URL` as the automatically supplied Postgres connection string. Do not set `DATABASE_URL` to SQLite.

Render Free web services can sleep while inactive, causing slow initial requests/realtime reconnects. For quicker, more reliable testing upgrade the web service's compute plan when you choose to pay. **Free PostgreSQL expires after 30 days and has no backups**; export test data or upgrade before expiry.

## 4. Check health

Wait for `lemmiq-api` to deploy and the database to be healthy. Open your real URL:

`https://YOUR-RENDER-SERVICE.onrender.com/health`

Expected JSON includes `"ok":true` and `"version":"1.6.1"`.

If deployment fails, open Render service → Events/Logs and review the first error. Common problems: missing API credentials, invalid database setting, or missing secret.

## 5. Android app

In Android Studio open the **`android`** folder, not the project root. Let it create `android/local.properties`; preserve the existing `sdk.dir=...` line and ADD:

```properties
lemmiq.apiBaseUrl=https://YOUR-REAL-RENDER-SERVICE.onrender.com
```

No slash at the end, do not copy example text literally, and do not commit `local.properties` to GitHub. The default is an intentionally invalid URL until configured. This Render APK requires HTTPS; cleartext HTTP is disabled.

Sync Gradle (JDK 17, compile/target SDK 37) and build/run on your Android device. The `Me` page includes your configured API URL to help diagnose routing.

**Note:** This ZIP contains Gradle config but the inherited V1.6 package does not include Gradle wrapper scripts/JAR. If your Android Studio requires them, use an installed compatible Gradle or generate the wrapper from your local Gradle installation before compiling. The Android APK has not been compiled in this environment.

## 6. Two-phone smoke test

Install the same APK on two phones, create two separate accounts (new Render DB), search the other username, send messages and check WebSocket connection while apps are open. Test Q brief, Assist, Trust, Activity and opt-in notification categories, then Money with a test notification or a manually entered transaction. Each phone can use any internet connection; Tailscale is **not** required.

Notification access must be granted explicitly by the user and selected apps/categories must be enabled. Local-only notification data remains on the device; events are sent to Render only if the separate sync setting is enabled. Avoid uploading actual banking/medical/private notifications to this beta.

## 7. Future updates

To update backend code: `git add . && git commit -m "Update LEMMIQ" && git push` → Render auto-deploys. A change to Android UI/code requires a new APK and reinstallation; backend-only updates typically do not.

## Beta limitations

- Messages are **not end-to-end encrypted**; server can read them.
- Free Render web service can spin down; WebSocket and AI responsiveness may suffer.
- Free Render PostgreSQL has a 30-day lifetime and no backups.
- Notification-derived amounts are *detected*, not verified bank records.
- No background push when the app is killed; no definitive AI-generated media detector.
- No production hardening (full rate limiting, account lifecycle, comprehensive moderation or robust horizontal WebSocket scaling).
- Existing desktop SQLite data is **not** automatically migrated.
