# LEMMIQ V2.10.11 — Consolidated Stability + Performance Update

This is the next consolidated build on top of the working **V2.10.7.4 backend/Q Economy** and **V2.10.9 Android** baseline. It folds the recent UI/performance work and the bugs reported during testing into one overlay.

## Android — versionCode 61 / versionName 2.10.11

### Fixed
- **System Back / left-edge swipe:** an open direct chat or group now goes back to Chats instead of exiting the app.
- Back from Q Thread, full Q, More sub-pages and non-Chats tabs now unwinds one in-app level before Android can exit the root screen.
- **Video-call camera toggle:** camera OFF/ON now re-acquires the local LiveKit camera track before updating preview.
- **Reverse camera:** front/rear switching rebinds the preview and updates mirroring.
- **Incoming call controls:** `Answer video` / `Decline` are observable UI state and are cleared immediately after answer/connection/decline/end.
- **Chat-list date/time:** Today shows time, Yesterday shows `Yesterday`, recent messages show weekday, older chats show `d/M/yy` (for example `11/10/26`).
- **Profile photo propagation/cache:** profile photo URLs are versioned, Coil cache keys follow that URL, and upload/remove refreshes Me, Chats, Groups, Status and Calls.

### Performance
- Startup no longer eagerly loads Status + Trust + Social IQ + Moments + Calls + Q Predict all at the same time.
- Messenger shell loads first; heavier tabs refresh when opened.

## Browser / PWA

### UI
- Light theme is the default; optional Dark mode is available under More.
- Narrow mobile composer keeps all controls on-screen: `+ · Mic · Message · Q · Send`.
- Chats list now uses the same Today / Yesterday / weekday / date timestamp logic.

### Photos
- JPG / JPEG / PNG / WebP / GIF message attachments are fetched with the authenticated LEMMIQ session and displayed as real inline previews.
- Works for direct and group chats, incoming/outgoing, existing history and new messages.
- Tap/click opens a full-screen dark viewer.
- Genuine non-image attachments retain the filename/download fallback.

### Performance
- Browser initially loads the newest 60 direct/group messages.
- `Load older messages` fetches the next page only when requested.
- Successful browser sends append the returned message instead of immediately downloading the whole conversation again.
- Backend adds additive indexes for message/group/call/push-device hot paths.
- API responses include `Server-Timing` and `X-LEMMIQ-Server-Ms`; requests >=750 ms are logged as slow requests.

## Optional PWA phone notifications

V2.10.11 adds browser/PWA FCM registration using the same Firebase project as Android.

Set these Render variables to enable it:
- `FIREBASE_WEB_CONFIG_JSON`
- `FIREBASE_WEB_VAPID_KEY`

Keep the existing Firebase Admin credential:
- `FIREBASE_SERVICE_ACCOUNT_JSON` **or** `FIREBASE_SERVICE_ACCOUNT_B64`

After deployment, signed-in users can go to **More → Appearance & notifications → Enable browser notifications**.

The service worker handles background notification display and deep-links notification taps to chats/groups/calls/Q areas.

## Compatibility / safety
- Q Economy rules are not changed.
- Stable `v28.js` / `v29.js` are not replaced by this package.
- Database migration is additive only: indexes are created with `IF NOT EXISTS`; no tables or user data are deleted.
- Existing Android FCM tokens still work. Browser tokens are stored with an internal `WEB:` prefix and stripped before Firebase Admin sends.
