# LEMMIQ V2.10.10 — Performance + UI

Built on the working V2.10.7.4 backend/browser baseline. Android V2.10.9 remains separate.

## Main UI changes
- Browser/PWA default theme is now LIGHT.
- Optional Dark Mode toggle is available on login and inside the app.
- Login/front page redesigned so the LEMMIQ message is readable and balanced on desktop/mobile.
- Everyday messenger surfaces are lighter and closer to the Android app.
- Q Predict and Q Admin retain darker specialist styling where useful.
- Mobile chat composer is fixed to keep the Send button fully on-screen:
  + · Mic · Message · Q · Send
- Browser image attachments now render as actual authenticated inline previews rather than filenames.
- Image preview tap/click opens a full-screen dark viewer.

## Performance changes
- Browser initially loads only the latest 60 direct/group messages.
- Older messages load on demand with “Load older messages”.
- New WebSocket messages are appended to the open chat rather than re-downloading the full chat.
- Chat-list refreshes are debounced and short-lived cached.
- Sends/uploads append the returned message immediately instead of re-fetching the full conversation.
- Service worker uses cache-first for versioned static assets and network-first for HTML.
- PostgreSQL/SQLite composite indexes are added for message/group-message/call hot paths.
- Server response timing is exposed through `Server-Timing` and `X-LEMMIQ-Server-Ms`; requests >=750ms are logged.

## PWA phone notifications
V2.10.10 adds optional Firebase Web/PWA push support using the existing FCM backend.

It is OFF until these Render environment variables are configured:
- FIREBASE_WEB_CONFIG_JSON
- FIREBASE_WEB_VAPID_KEY

The Firebase service-account variable already used by Android FCM is still required:
- FIREBASE_SERVICE_ACCOUNT_JSON
  or
- FIREBASE_SERVICE_ACCOUNT_B64

When configured:
- More > Browser notifications lets the signed-in user enable notifications.
- The browser registers a WEB-prefixed FCM token without changing Android registration.
- Background message/group/call events can display native browser/PWA notifications.
- Notification taps deep-link to the relevant chat/group/calls view.

## Compatibility
- Existing Android push tokens continue to work.
- Existing Android app APIs remain compatible.
- V2.10.7.4 Q Economy routes are untouched.
- Stable v28.js / v29.js are untouched.
