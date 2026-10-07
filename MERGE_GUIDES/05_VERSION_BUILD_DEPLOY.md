# 05 — Version, GitHub, Render and Android build

## A. Version bump

In:

```text
android/app/build.gradle.kts
```

set:

```kotlin
versionCode = 50
versionName = "2.10"
```

Also search the repo for literal `2.9` / `2.9.0` in app-config/version responses and update only the application version fields to `2.10` / `2.10.0`. Do not change Q Predict market rules or historical release text.

## B. Manual GitHub upload order

Because you are uploading manually, do this in two passes.

### Pass 1 — add new files
Upload these first:

```text
backend/app/v210.py
backend/app/call_state_guard_v210.py
backend/web/v210.css
backend/web/v210.js
android/app/src/main/java/com/lemmiq/app/CallDeclineV210.kt
android/app/src/main/java/com/lemmiq/app/LemmiqMediaViewerActivity.kt
```

Commit message:

```text
Add LEMMIQ v2.10 support files
```

### Pass 2 — edit existing files
Use the merge guides to edit:

```text
backend/app/main.py
backend/web/index.html
backend/web/sw.js
backend call handlers
android/app/src/main/AndroidManifest.xml
android/app/build.gradle.kts
android/.../LemmiqCallActivity.kt
android/.../LemmiqPushService.kt
android/.../LemmiqApp.kt or your current navigation/chat-media file
```

Commit message:

```text
LEMMIQ v2.10 Q Predict call media and responsive fixes
```

## C. Render

If Render auto-deploy is enabled, wait for the deploy to finish.

Check:

```text
https://lemmiq-api.onrender.com/v210/version
```

Expected version: `2.10.0`.

Then open the web/PWA once in a normal browser tab. Because `sw.js` is bumped to a new cache, the old mobile layout should no longer remain stuck in cache.

If an installed PWA still shows the old layout, close it completely and reopen it after the service-worker activation finishes.

## D. Android build

From your existing Windows project:

```powershell
cd C:\Users\pc\LEMMIQ\android
.\gradlew clean
.\gradlew assembleDebug
```

Test the debug APK first.

For Play/release bundle using your existing signing setup:

```powershell
.\build-play-bundle.cmd
```

or your current release Gradle task if that script has changed.

## E. Do not ship until these critical tests pass

- incoming call Decline terminates for caller and callee
- stale connected event cannot resurrect a declined call
- Q Predict Analyse returns a visible response and retry works
- Q Predict mobile browser uses full width
- six bottom tabs are visible/reachable
- More opens Profile/Trust/Business/Settings etc.
- chat photo opens full screen in Android and browser/PWA
- Q FAB is translucent and does not cover nav/content
