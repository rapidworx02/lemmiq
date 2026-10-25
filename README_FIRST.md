# LEMMIQ V2.12.0 — Q Create Image

**Source update, not a prebuilt APK.** Prepared 25 October 2026. Intended for the existing `rapidworx02/lemmiq` project, targeting the V2.10.10–V2.10.11 family and Android `versionCode 62`. It is additive and excludes the deferred Q Exchange.

## Features included

| Area | Behaviour |
|---|---|
| Q assistant (PWA/Android) | User enters text prompt, chooses square/portrait/landscape, generates a private image, previews, selects destination, then sends |
| Direct chat (PWA/Android) | `🎨` / `Q Image` entry in composer, private image preview, explicit Send to current chat |
| Group chat | PWA composer generation; Q assistant can share generated image to a selected group on Android |
| Private media | Generated PNGs stored in existing private object storage, never exposed with a public URL |
| Q Economy | Adds `Q_IMAGE` to existing Q feature catalog, ledger and charge/refund hooks; starts at 0 Q until admin sets fee |
| Moderation | Server-side prompt + generated-image moderation before exposing to user |
| Operations | Feature kill switch, configurable daily attempt limit, unique request IDs, single-send guard, 15-minute stale-job refund recovery |
| Existing services | Existing chat/group message attachment models and WebSocket/FCM notification flow remain in use |

**Does not include:** Q Exchange, Q buy/sell, crypto transactions, AI video, image editing, multi-image generation, guaranteed Q returns. Those features are outside this update.

## Important baseline note

The public GitHub main branch checked for this update contains backend V2.10.10, Android `versionCode 60`, Q Economy V2.10.7.4 modules and V2.10.10 browser assets. The local PC version may differ; run the dry-run before applying. The installer does not replace the full app, your existing Gradle files, database or secret configuration. If the dry-run fails, stop rather than forcing it.

## Installation — Windows 11 (CMD)

1. Download this ZIP. Extract all contents, preserving the directories.
2. Confirm existing project folder: `C:\Users\pc\LEMMIQ`.
3. Keep a full project/database backup and check current working branch and uncommitted changes before patching.
4. Double-click `INSTALL_WINDOWS_V2.12.cmd`. It verifies compatibility, asks permission, creates a source backup named `BACKUP_BEFORE_V212_YYYYMMDD_HHMMSS.zip` in your LEMMIQ project, and copies the additions.
5. To run manually:

```bat
cd /d C:\Users\pc\Downloads\LEMMIQ_V2.12_AI_IMAGE_GENERATION
py -3 APPLY_V2.12.py --repo "C:\Users\pc\LEMMIQ" --dry-run
py -3 APPLY_V2.12.py --repo "C:\Users\pc\LEMMIQ"
```

6. Verify source diff:

```bat
cd /d C:\Users\pc\LEMMIQ
git status --short
git diff -- backend/app/main.py backend/app/v2105_q_features.py backend/web/index.html backend/web/sw.js android/app
```

7. Build Android (requires complete local Gradle project, Android SDK and Firebase configuration):

```bat
cd /d C:\Users\pc\LEMMIQ\android
gradlew.bat clean
gradlew.bat assembleDebug
```

8. If the build passes, install on testing phone:

```bat
adb install -r app\build\outputs\apk\debug\app-debug.apk
```

9. After the backend and PWA are reviewed/tested, commit and push:

```bat
cd /d C:\Users\pc\LEMMIQ
git add backend/app/main.py backend/app/v2105_q_features.py backend/app/v212_image_gen.py backend/web/index.html backend/web/sw.js backend/web/v212_image_gen.js backend/web/v212_image_gen.css android/app/build.gradle.kts android/app/src/main/java/com/lemmiq/app/LemmiqApp.kt android/app/src/main/java/com/lemmiq/app/V212ImageGen.kt
git commit -m "LEMMIQ v2.12 Q create image source update"
git push origin main
```

## Render configuration — rollout in this order

Existing media storage (`MEDIA_BUCKET`, `MEDIA_ENDPOINT`, `MEDIA_ACCESS_KEY_ID`, `MEDIA_SECRET_ACCESS_KEY`) must work. Never store generated images on Render's ephemeral filesystem in production.

Set the following in **Render → LEMMIQ backend → Environment**:

```dotenv
OPENAI_API_KEY=<YOUR_ACTUAL_SECRET_FROM_PROVIDER>
LEMMIQ_IMAGE_GEN_ENABLED=false
LEMMIQ_IMAGE_MODEL=gpt-image-1.5
LEMMIQ_IMAGE_QUALITY=medium
LEMMIQ_IMAGE_DAILY_LIMIT=3
```

- `OPENAI_API_KEY` stays on the server only. Never put it in browser code, APK source, GitHub, documentation, chat or screenshots.
- Default model uses the supported OpenAI Images endpoint at `/v1/images/generations` and the `omni-moderation-latest` moderation endpoint. OpenAI's `gpt-image-1` legacy model was shut down in October 2026; do not use it.
- Start with `LEMMIQ_IMAGE_GEN_ENABLED=false`; test the deployment, database migration (a single additive `q_image_drafts_v212` table) and authenticated `/v212/images/config` endpoint.
- When ready for a small authorised beta, set `LEMMIQ_IMAGE_GEN_ENABLED=true` and redeploy.
- Q feature `Q_IMAGE` is added to Master Admin's global Q feature settings, seeded at **0 Q** so testing does not unexpectedly debit users. Admin may later set a 2 Q example price under `Q_IMAGE`. It only charges when the **existing global Q charging switch** is enabled. Other Q fee rules are unchanged.
- On Render, ensure PostgreSQL is used for row locking, idempotency and safe Q wallet writes. Do not use SQLite for real charged generation flows.
- Generation is synchronous at this stage, with an upstream request timeout; use low concurrency for private beta. For high scale, replace request-thread generation with a durable queue/worker.

## API endpoints

All endpoints below require the existing LEMMIQ bearer-token session (except no new public endpoints):

```text
GET    /v212/images/config
GET    /v212/images/mine
POST   /v212/images/generate
       {"prompt":"Modern minimalist birthday poster", "size":"1024x1024", "request_id":"<new UUID>"}
GET    /v212/images/{id}/file      (owner only)
POST   /v212/images/{id}/send      {"chat_id":123} OR {"group_id":456}
```

- Generate endpoint returns a private draft record; it does NOT send any chat message.
- Send endpoint checks chat/group membership, respects user blocking in direct chats, and will not create duplicate messages on retry.
- Q usage and refund events use existing Q ledger semantics and Profit Wallet. Any failed generation after debit triggers refund; stale reservations are recovered when the user submits another request after 15 minutes.

## Rollback

Source rollback **before pushing**: `git diff` and the project's backup ZIP cover all patch-touched files. On GitHub, revert the V2.12 commit and redeploy. If Android is already installed, build/install your prior stable APK. Avoid running database-destructive rollback SQL: the added image drafts table is isolated and need not be dropped.

1. Set `LEMMIQ_IMAGE_GEN_ENABLED=false` in Render immediately to disable new generations.
2. Restore previous source files from `BACKUP_BEFORE_V212_*.zip` or revert the V2.12 commit (depending on how you deployed).
3. Build/test the previous Android source.
4. Confirm Q Economy wallet balances, Q Predict, calling, normal chat and attachments all still work.

## Validation and limitations

- Python syntax compiled; browser JavaScript passes Node syntax check; updater self-tests passed.
- Installer anchor locations were checked against the public repository source. **Full Android Gradle compilation, real OpenAI generation, Render deployment, and on-device testing could not be executed here.**
- The generated update is a **source patch** and **not a tested production release**, not an APK. Keep image generation disabled until QA is complete.
- Customer privacy review, media retention cleanup, moderation incidents, model costs, rate limiting under load and billing reconciliation should be completed before public rollout.
