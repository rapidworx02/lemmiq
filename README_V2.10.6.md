# LEMMIQ V2.10.6 — Q Workflow + Video Calling + Stability UX

V2.10.6 is an additive upgrade on the working V2.10.5 Q-wallet/Q-Predict backend. It keeps the current Render API as the default and does **not** introduce the deferred Private Q / E2EE architecture.

## Main changes

### 1. Q Thread inside Chats
- Adds a synthetic **Q · LEMMIQ Assistant** thread to Chats.
- Q-to-Q requests and replies appear as readable assistant cards instead of technical `0/1 responses` states.
- Human-readable states include **Waiting for <person>**, **<person> replied**, **Q needs your response**, and closed/completed states.
- The Q Thread has an unread badge and participates in the total Chats unread count.
- Opening the Q Thread marks its Q events read.
- Q-to-Q requests/replies send a phone push through the **Q Assistant** notification channel and deep-link to the Q Thread.
- The Q Thread is a derived view of Q-to-Q coordination records; it does not copy private chat message text into a second store.
- On first upgrade, only recent active/replied Q-to-Q activity is marked unread so old history does not flood the badge.

### 2. Q Personal Assistant improvements
- **Today** is expandable and shows the actual conversations that may need replies plus relevant follow-ups/promises where available.
- Adds **Talk to Q** on Android and web/PWA.
  - Android also exposes Talk to Q from the contextual in-chat Q sheet.
  - Android uses the device speech-recognition activity and sends the recognised text through the existing Q pipeline.
  - Web/PWA uses browser SpeechRecognition when supported.
- Q-to-Q cards use understandable user-facing statuses.

- The floating/contextual Q control in an active Android chat is smaller and raised above the composer; the web global Q orb is hidden while a chat/Q Thread is open so it cannot cover Send.

### 3. Q Economy UX
- The top tab strip is horizontally scrollable so **Packages** stays on one line.
- Q Activity supports time periods: **Today · Week · Month · Year · All**.
- Direction filters remain: **All · Incoming · Outgoing**.
- Wallet **Recent activity** also gets Today/Week/Month/Year/All filters.
- Feature usage continues to display `0 Q` where current tier pricing is zero; no “free during beta” wording is added.
- The existing backend-controlled tier-pricing system from V2.10.5 is preserved.

### 4. 1-to-1 video calling
V2.10.6 extends the existing LiveKit voice-call stack instead of creating a second call system.

Implemented:
- Start video call from a direct chat.
- Incoming video-call UI and push metadata.
- Camera permission handling.
- Local camera preview.
- Remote participant video rendering.
- Camera on/off.
- Front/rear camera switch.
- Mute/unmute.
- Speaker/audio route control.
- Existing single-active-call and decline/end cleanup logic retained.
- Call history distinguishes **Voice call** and **Video call**.
- Web/PWA voice/video calling uses the existing LiveKit JS client.

Not included in this release:
- group video rooms;
- Teams/Zoom-style scheduled meetings;
- screen sharing;
- recording;
- live voice→video upgrade during an already-connected voice call.

These can be added after 1-to-1 video calling is proven stable.

### 5. Q Predict stability retained
- Main LEMMIQ Q wallet remains authoritative for new Q Predict stakes.
- No legacy test-credit balance is converted into Q.
- Android Q Predict removes remaining user-facing legacy credit terminology from normal new-market flows.
- Saved analysis/retry/history functionality from V2.10.4/V2.10.5 is preserved.
- The V2.10.5 Render PostgreSQL psycopg-v3 hotfix is included in the package.

### 6. Domain preparation retained
Android already reads the API base URL from configuration:
- environment: `LEMMIQ_API_BASE_URL`
- or local property: `lemmiq.apiBaseUrl`
- default remains `https://lemmiq-api.onrender.com`

V2.10.6 does **not** switch to `api.lemmiq.com`. That should happen only after DNS/SSL are configured and verified.

## Backend/database changes

Additive only:
- `call_records.call_type` (`VOICE` / `VIDEO`)
- `q_thread_states` read-cursor table for Q Thread unread state
- new `/v2106/q/thread` and `/v2106/q/thread/read` endpoints
- `/v24/calls/start` accepts `call_type`
- `/v24/calls/status` advertises video support

No Q-wallet reset or Predict Credit → Q conversion is performed by V2.10.6.

## Version
- Android `versionCode = 56`
- Android `versionName = 2.10.6`
- Server `/app-config` reports `2.10.6`
- PWA cache: `lemmiq-v2106-shell-1`

## Validation completed before packaging

Passed in the build environment:
- Python compilation of all backend modules.
- FastAPI startup against a fresh SQLite test database.
- `/app-config` reports 2.10.6.
- V2.10.6 Q Thread routes, V2.4 call routes and Q Predict routes register correctly.
- Q-to-Q request → recipient Q Thread → response → initiator Q Thread flow was exercised successfully.
- JavaScript syntax checks for `app.js`, `v2104.js`, `v2105.js`, `v2106.js` and `sw.js`.
- HTML parse/duplicate-ID sanity check.
- Current LiveKit Android API usage was checked against the SDK API used by the project.

### Android build validation note
The uploaded source snapshot does not include the root Gradle wrapper/settings project, so a full Android APK compile cannot be executed in this build container. Run `gradlew assembleDebug` in the actual local LEMMIQ repository before installation. The deployment steps below include this explicitly.

## LiveKit setup
No new LiveKit project is required for V2.10.6. Continue using the existing:
- `LIVEKIT_URL`
- `LIVEKIT_API_KEY`
- `LIVEKIT_API_SECRET`

The current access token already allows publish/subscribe. Camera tracks use the same LiveKit room as voice.
