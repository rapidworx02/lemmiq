# LEMMIQ V2.10 changed / added files

## New files

### Backend
- `backend/app/v210.py`
  - `/v210/version`
  - `/v210/q-predict/analyse`
  - optional Tavily current context
  - Anthropic market analysis
  - same-origin + basic rate guard

- `backend/app/call_state_guard_v210.py`
  - terminal call-state transition rules
  - canonical `call_declined` event payload

### Browser / PWA
- `backend/web/v210.css`
  - six-tab mobile nav sizing
  - More sheet
  - Q Predict/Q Economy responsive fixes
  - transparent glass Q FAB
  - full-screen image viewer styles
  - image bubble padding reduction

- `backend/web/v210.js`
  - More tab + sheet
  - removes hidden Profile/Trust/Business/Settings Q-sheet link
  - Q Predict Analyse action
  - responsive DOM tagging
  - PWA full-screen photo viewer
  - Q FAB transparency class

### Android
- `android/app/src/main/java/com/lemmiq/app/CallDeclineV210.kt`
  - idempotent decline helper
  - terminal-state race guard
  - structured cleanup callbacks

- `android/app/src/main/java/com/lemmiq/app/LemmiqMediaViewerActivity.kt`
  - full-screen chat-photo viewer
  - HTTPS/content URI support
  - pinch zoom

## Existing files to edit
- `backend/app/main.py`
- existing backend call handlers/model/service
- `backend/web/index.html`
- `backend/web/sw.js`
- `android/app/src/main/AndroidManifest.xml`
- `android/app/build.gradle.kts`
- `android/app/src/main/java/com/lemmiq/app/LemmiqCallActivity.kt`
- `android/app/src/main/java/com/lemmiq/app/LemmiqPushService.kt`
- Android bottom-navigation / chat-media code, normally in `LemmiqApp.kt` or related Compose files
