# LEMMIQ V2.2 — Push Notifications + Self-Notification Filter

## Fixes

### New-message notifications
When LEMMIQ is in the background, a new message can now show:
- sender name
- message preview
- notification-centre card
- launcher badge/count where supported by the Android launcher
- one active notification per chat

Opening a chat clears that chat's local notification.

### Push diagnostics
Open:

`Me → Enable / refresh message push alerts`

Possible status messages include:
- Push ready
- Firebase app config missing: add google-services.json
- Render Firebase credentials are not configured
- No phone token registered yet
- registration errors

### LEMMIQ never reads LEMMIQ
V2.2 applies hard guards so Notification Intelligence cannot consume LEMMIQ's own notifications:
- self package excluded from app allowlist
- Select All cannot add LEMMIQ
- NotificationListenerService rejects LEMMIQ notifications immediately
- WhatsApp/SMS intelligence remains limited to supported external messaging packages

This prevents feedback loops and duplicate Q context.

## Firebase is required for background Android push

### Android Firebase config
Firebase Android package must be:

`com.lemmiq.app`

Download `google-services.json` from Firebase and place it at:

`android/app/google-services.json`

Do not commit this file publicly.

### Render Firebase credentials
Create/download a Firebase service-account JSON key for the same Firebase project.

Base64 encode it and set this Render environment variable:

`FIREBASE_SERVICE_ACCOUNT_B64`

Do not store the service-account JSON in GitHub.

### Android permission
Android 13+ requires notification permission. V2.2 requests it after login when Firebase is configured.

You can retry from:

`Me → Enable / refresh message push alerts`

Also check:
`Android Settings → Apps → LEMMIQ → Notifications`

On Samsung, make sure app-icon badges are enabled in launcher notification settings.

## Upgrade

```cmd
cd C:\Users\pc\LEMMIQ
git add .
git commit -m "LEMMIQ V2.2 push and self notification filter"
git push origin main
```

Wait for Render, then verify:

`https://YOUR-RENDER-URL/health`

Expected version: `2.2.0`

Then rebuild Android from Android Studio.

Version:
- versionCode 23
- versionName 2.2.0

## Test
1. Phone A: LEMMIQ → Me → Enable / refresh message push alerts.
2. Confirm status says `Push ready`.
3. Put Phone A on the home screen or lock it.
4. From Phone B or LEMMIQ Web, send Phone A a message.
5. Phone A should receive a notification.
6. Open the chat; that chat's notification should clear.

Render Free cold starts can delay the backend before FCM is sent.
