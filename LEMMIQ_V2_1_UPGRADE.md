# LEMMIQ V2.1 — Cross-Platform Chat Intelligence + User-Controlled Insights

V2.1 builds on V2.0.1 and includes the previously requested data-management controls.

## New in V2.1

### Web / iPhone / Safari Chat Intelligence
Every LEMMIQ browser chat now has:

`⚙ Chat AI`

Users can control the same Personal Chat Intelligence settings as Android:

- OFF
- ASSIST
- AUTO
- Relationship/category
- Tone

The setting is stored in the same PostgreSQL `chat_settings` record used by Android.

This means a user can enable AUTO from Safari/iPhone and the server-side Q Agent can respond even though there is no native iOS app.

If the Business Agent is enabled for that customer chat, Business AUTO keeps priority over Personal AUTO.

### Money / Activity data controls
Detected notification data is now user-editable.

Supported controls:

- Edit individual detected events
- Change category
- Change source/title/description
- Correct amount
- Change incoming/outgoing/unknown direction
- Correct date/time
- Delete an event
- Remove duplicate / incorrect detections
- Reset Money only
- Reset Activity only
- Reset all detected data
- Totals recalculate from the corrected records

### Android native controls
The Android Money and Activity screens now expose the same management concept for the phone's local detected-event database.

When an Android event has already been synced to LEMMIQ cloud, Android also updates/deletes the server copy.

### Web Money screen
The browser/PWA now has a dedicated Money screen instead of only a combined Activity card.

---

# Update steps

## 1. Back up the current Git repository

```cmd
cd C:\Users\pc\LEMMIQ
git add .
git commit -m "Backup before LEMMIQ V2.1"
```

If Git says there is nothing to commit, continue.

## 2. Extract this ZIP

Copy the contents of:

`LEMMIQ_V2_1`

over:

`C:\Users\pc\LEMMIQ`

Keep your existing:

`android/local.properties`

## 3. Push to GitHub

```cmd
cd C:\Users\pc\LEMMIQ
git add .
git commit -m "LEMMIQ V2.1 cross platform controls"
git push origin main
```

## 4. Wait for Render

Render should redeploy automatically.

Open:

`https://YOUR-RENDER-URL/health`

Expected:

```json
{"ok":true,"name":"LEMMIQ","version":"2.1.0"}
```

## 5. Test Safari / browser Chat Intelligence

Open LEMMIQ in Safari/Chrome.

Open a conversation.

Tap:

`⚙ Chat AI`

Choose:
- AUTO
- FRIEND
- Casual

Save.

Refresh Android or reopen the same chat. Both clients use the same server-side chat setting.

## 6. Test server-side AUTO

Account A:
- Set the chat to AUTO from Safari.

Account B:
- Send Account A a normal message.

The backend should generate Account A's reply using the saved category, tone and recent chat context.

## 7. Test Money / Activity management

On Android or web:
- edit an incorrect amount
- remove a duplicate detection
- reset Money only

The displayed totals should recalculate.

## 8. Rebuild Android

V2.1 uses:

- versionCode 22
- versionName 2.1.0

Open:

`C:\Users\pc\LEMMIQ\android`

in Android Studio.

Sync Gradle, connect your phone and press Run.

The new APK installs over your existing LEMMIQ app if the signing key/package remains the same.

---

## Important notes

- Notification-derived finance data remains an estimate, not a complete/verified bank record.
- Android cross-app notification capture remains native-Android-only.
- Safari/browser users can use the cloud Chat Intelligence settings, but Safari cannot read WhatsApp/SMS/banking notifications from other apps.
- Messages are still server-readable; public production E2EE is not implemented yet.
- Calls are not part of V2.1; voice/video remains a separate infrastructure phase.
