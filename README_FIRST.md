# LEMMIQ V2.10 UPDATE PACK

Baseline: **LEMMIQ V2.9**
Target: **LEMMIQ V2.10.0**
Android target version: **versionName = 2.10**, **versionCode = 50**

This is an **additive overlay/merge pack**, not a replacement for the whole V2.9 repository. It is designed this way so your existing chats, Q Economy, Q Predict, Trust, Business Agent, calling, media, auth and database code are not overwritten.

## Included fixes

1. Q Predict: `Q · Analyse this market` becomes a real Q analysis flow.
2. Q Predict analysis can optionally use Tavily current-web context, then Anthropic Q analysis, matching the existing LEMMIQ Trust/Q provider direction.
3. Bottom navigation becomes: **Chats · Updates · Q Economy · Q Predict · Calls · More**.
4. More contains Profile, Trust / Fact Check, Business Agent, Activity, Money, Settings, Privacy & Security and Android download.
5. The hidden `Profile, Trust, Business & Settings` link is removed from the Q assistant sheet.
6. Floating Q button is more transparent/glass-like and sits above the bottom nav.
7. Browser/PWA Q Predict responsive layout is fixed: full mobile width, readable cards, scrollable category rail and no giant blank right side.
8. Q Economy tabs become mobile-scrollable and content gets bottom safe-area padding.
9. Browser/PWA chat photos open full-screen with zoom/pan; chat-photo bubble padding is reduced.
10. Android full-screen chat-photo viewer is added.
11. Call decline gets an idempotent terminal-state guard and cleanup helper so DECLINED/ENDED cannot race back into CONNECTING/CONNECTED.
12. Browser/PWA content gets safe padding for six bottom tabs and device safe-area insets.

## Files you can add directly

- `backend/app/v210.py`
- `backend/app/call_state_guard_v210.py`
- `backend/web/v210.css`
- `backend/web/v210.js`
- `android/app/src/main/java/com/lemmiq/app/CallDeclineV210.kt`
- `android/app/src/main/java/com/lemmiq/app/LemmiqMediaViewerActivity.kt`

## Existing files that need small merges

- `backend/app/main.py`
- `backend/web/index.html`
- `backend/web/sw.js`
- your existing backend call state/decline/answer/connect handlers
- `android/app/src/main/AndroidManifest.xml`
- `android/app/build.gradle.kts`
- `android/app/src/main/java/com/lemmiq/app/LemmiqCallActivity.kt`
- `android/app/src/main/java/com/lemmiq/app/LemmiqPushService.kt`
- the Android Compose/navigation code in `LemmiqApp.kt` (or wherever your bottom nav is currently defined)
- the Android chat image `onClick` / bubble padding code

Follow the guides in `MERGE_GUIDES/` in order.

## Important

Do **not** replace your current V2.9 `app.js`, `styles.css`, `main.py`, `LemmiqApp.kt`, `Api.kt` or `LemmiqCallActivity.kt` wholesale with a guessed file. This pack adds new files and only asks you to make small controlled merges into your working V2.9 files.
