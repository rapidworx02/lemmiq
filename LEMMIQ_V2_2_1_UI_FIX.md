# LEMMIQ V2.2.1 — Android Header + Mobile Web Bottom Navigation Fix

This is a UI hotfix on top of V2.2.

## Android native fix

The chat header now respects Android's status-bar / camera-cutout safe area.

Before:
- contact name could sit under the time/status icons.

After:
- the entire chat toolbar is padded below the Android status bar.
- the composer also respects the bottom navigation/gesture safe area.

## Web / Safari / Chrome fix

The mobile web bottom navigation now supports all **7** current LEMMIQ tabs:

- Chats
- Q
- Trust
- Biz
- Activity
- Money
- Me

V2.2 still used a 6-column mobile grid, so the seventh `Me` item wrapped onto a hidden second row.

V2.2.1 changes the mobile nav to 7 columns and adds browser/PWA safe-area padding.

It also uses `100dvh` where appropriate so mobile browser chrome changes are handled better.

## Update

Extract this ZIP and copy the contents over your existing project.

Keep:
- `android/local.properties`
- `android/app/google-services.json` if already configured

Then:

```cmd
cd C:\Users\pc\LEMMIQ
git add .
git commit -m "LEMMIQ V2.2.1 mobile safe area fixes"
git push origin main
```

Wait for Render and verify:

`https://YOUR-RENDER-URL/health`

Expected version:

`2.2.1`

Then open Android Studio:

- Sync Gradle
- Run

Android version:
- versionCode 24
- versionName 2.2.1

## Browser cache

The service-worker cache version was bumped.

After Render redeploys:
- reload LEMMIQ in the browser
- if an old layout remains, close and reopen the browser/PWA once

The `Me` icon should now remain inside the single bottom navigation row.
