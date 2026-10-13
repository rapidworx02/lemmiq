# LEMMIQ V2.10.10 — Unified Android + Browser UX Fixes

Built on the working V2.10.7.4 backend/Q Economy and V2.10.9 Android integration.

## Android fixes
- Video call Camera button reliably toggles local video ON/OFF.
- Reverse/Switch Camera reliably changes front ↔ rear camera and updates local-preview mirroring.
- Incoming `Answer video` / `Decline` controls disappear immediately after answer/connection.
- Incoming controls are also cleared on decline/end/cleanup.
- Android system edge-swipe / Back now returns from chat/group to Chats instead of immediately closing the app.
- Home back handling returns from Q workspace/Q Thread/More subpages/other tabs before exiting.
- Existing 6-tab navigation and V2.10.9 Q Economy integration remain unchanged.

Android version: `versionCode 60`, `versionName 2.10.10`.

## Browser/PWA fixes
- Default appearance is now the app-like LIGHT theme.
- Optional Dark mode toggle is available under More.
- Direct-chat composer order is now `+ · Mic · Message · Send · Q`.
- Composer has responsive fixed-size controls so Send/Q stay inside narrow mobile screens.
- JPG/JPEG/PNG/WEBP/GIF attachments render as actual authenticated inline photo previews instead of filenames.
- Applies to old/history and new messages, incoming/outgoing and direct/group chats.
- Tapping a photo opens a full-screen dark viewer.
- Non-image attachments keep the download-file fallback.
- PWA service-worker cache bumped for the new assets.

## Backend
No Q Economy business rules were changed. The backend version label is updated to 2.10.10 for this unified release.
