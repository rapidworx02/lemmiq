# LEMMIQ V2.4 — Messenger + Social IQ

LEMMIQ V2.4 is a full private-beta upgrade for the existing Android + browser/PWA + Render deployment.

## What is included

### Messenger
- Chats search
- All / Unread / Groups filters
- Group creation by LEMMIQ username
- Group name/photo, members, multiple admins, files and voice notes
- Group Q modes: OFF / ASSIST / SUMMARY
- Group Suggest Reply, Catch me up, and Ask Q
- Message time on every direct/group message
- Today / Yesterday / weekday / full-date separators
- Inline voice-call history
- Reply to a message
- Reactions
- Forward
- Edit own recent message
- Delete for me
- Delete for everyone
- Pin, favourite, archive, mute and draft saving
- Search inside a direct conversation
- Block and report controls

### Voice messages
- Android recorder
- Browser/PWA recorder
- Play/pause
- 1× / 1.5× / 2× playback
- Optional automatic server transcription
- Q voice-note summary and suggested reply when a transcript is available

### Voice calls
- LiveKit/WebRTC 1-to-1 call beta
- Android ↔ Android
- Android ↔ browser
- Browser ↔ browser while both browser clients are available
- Incoming Android call notification through FCM
- Ringing state before answer
- Incoming ringtone
- Outgoing ringback
- Connected state only after the other participant joins
- Connected-call timer
- Answer / Decline / Mute / Speaker / End
- Android defaults to the normal earpiece, not loudspeaker
- Bluetooth/headset is preferred when Android exposes it as a communication device
- Speaker button manually switches to loudspeaker
- 45-second no-answer timeout
- Call events appear in direct-chat history
- Profile photo appears on call UI when available

### Profile
- Add/change/remove profile photo
- Profile photos appear in chats, groups, Status and call surfaces
- Initials remain the fallback

### Updates / Status
- Text Status
- Photo Status
- Video Status
- 24-hour expiry
- Seen/unseen state
- Own view count
- Delete own Status
- Reply to another user's Status → opens direct chat with a draft

### LEMMIQ Trust
- Completed Fact/Scam checks are saved
- Search previous checks
- Open a saved result
- Delete one result
- Clear history
- Same exact claim can reuse a recent saved result
- Refresh check for newer evidence

### Q / Social IQ
- User-triggered scan of recent LEMMIQ conversations
- Extracts explicit promises, follow-ups, plans, deadlines and other important communication context
- Social IQ brief shows remembered items
- User can delete memory items
- Q remains assistive; it does not autonomously message people

### Existing features retained
- Personal Chat AI OFF / ASSIST / AUTO
- Business Agent beta
- Notification Intelligence
- Money/Activity correction/reset controls
- Android FCM message notifications
- LEMMIQ self-notification exclusion
- Mobile safe-area fixes

## Deliberately not claimed as complete in V2.4

These remain later work:
- end-to-end encryption
- native iOS app / iOS CallKit background calling
- video calls
- group calls
- public Channels
- disappearing messages
- full linked-device/session revocation UI
- production-grade typing/online/last-seen presence
- fully enforced contact-aware privacy rules across every media endpoint

V2.4 remains a private beta.

---

# Upgrade steps

## 1. Back up your current project

Open Command Prompt:

```cmd
cd C:\Users\pc\LEMMIQ
git add .
git commit -m "Backup before LEMMIQ V2.4"
```

If Git says there is nothing to commit, continue.

## 2. Extract the V2.4 ZIP

Extract `LEMMIQ_V2_4_MESSENGER_SOCIAL_IQ.zip`.

Copy the contents of the extracted project folder over:

```text
C:\Users\pc\LEMMIQ
```

Keep these local files from your existing setup:

```text
android\local.properties
android\app\google-services.json
```

Do not put service-account JSON, LiveKit secrets, API keys, `.env`, or `local.properties` into GitHub.

## 3. Check android/local.properties

It should still contain your Android SDK path and Render URL, for example:

```properties
sdk.dir=C\:\\Users\\pc\\AppData\\Local\\Android\\Sdk
lemmiq.apiBaseUrl=https://lemmiq-api.onrender.com
```

## 4. Push V2.4 to GitHub

```cmd
cd C:\Users\pc\LEMMIQ
git add .
git commit -m "LEMMIQ V2.4 Messenger and Social IQ"
git push origin main
```

Render should auto-deploy from the connected GitHub repository.

## 5. Keep the existing Render variables

Keep your current values for:

```text
DATABASE_URL
LEMMIQ_JWT_SECRET
ANTHROPIC_API_KEY
ANTHROPIC_MODEL
TAVILY_API_KEY

MEDIA_BUCKET
MEDIA_ENDPOINT
MEDIA_ACCESS_KEY_ID
MEDIA_SECRET_ACCESS_KEY
MEDIA_REGION

FIREBASE_SERVICE_ACCOUNT_B64
```

## 6. Add LiveKit variables for voice calling

Create/use your LiveKit Cloud project and copy its project URL, API key and API secret.

Render → `lemmiq-api` → Environment:

```text
LIVEKIT_URL=<your LiveKit project URL>
LIVEKIT_API_KEY=<your LiveKit API key>
LIVEKIT_API_SECRET=<your LiveKit API secret>
```

The API secret belongs on Render only.

V2.4 uses LiveKit Android's `2.+` SDK line with JitPack configured in the Android project.

## 7. Add optional voice-transcription variables

For automatic voice-note transcription:

```text
OPENAI_API_KEY=<your OpenAI API key>
LEMMIQ_VOICE_TRANSCRIPTION=true
LEMMIQ_TRANSCRIPTION_MODEL=gpt-4o-mini-transcribe
```

If you leave `OPENAI_API_KEY` blank or set:

```text
LEMMIQ_VOICE_TRANSCRIPTION=false
```

voice recording, sending and playback still work, but automatic transcript/Q voice summary will not.

Never put `OPENAI_API_KEY` inside the Android app.

## 8. Redeploy and check health

After Render becomes Live, open:

```text
https://lemmiq-api.onrender.com/health
```

Expected:

```json
{"ok":true,"name":"LEMMIQ","version":"2.4.0"}
```

Also refresh the browser app:

```text
https://lemmiq-api.onrender.com/web/
```

If the PWA appears stale, close/reopen it once. V2.4 uses a new service-worker cache.

## 9. Database upgrade

V2.4 creates its new tables automatically on startup.

It also includes a compatibility migration for V2.3 voice-note tables so the new `transcribed_at` fields are added when those tables already exist.

Do not delete your existing PostgreSQL database.

---

# Android Studio steps

## 10. Open the Android project

Android Studio:

```text
C:\Users\pc\LEMMIQ\android
```

V2.4 Android version:

```text
versionCode 40
versionName 2.4.0
```

## 11. Sync Gradle

Choose:

```text
File → Sync Project with Gradle Files
```

V2.4 adds:
- LiveKit Android
- Coil Compose for profile/status images
- JitPack repository

Use JDK 17 in Android Studio.

## 12. Run on your phone

Connect the phone and press:

```text
Run ▶
```

Allow:
- Notifications
- Microphone

For Android background call alerts, go to:

```text
LEMMIQ → Me → Enable / refresh message push alerts
```

Target status:

```text
● Push ready
```

---

# Recommended test order

## A. Browser ASSIST

Open a direct chat with AI mode `ASSIST`.

Test:

```text
✨ Suggest reply
→ Discard
→ Edit
→ Send
```

Nothing should auto-send in ASSIST.

## B. Chat timeline

Send messages on two different dates if test data allows.

Check:
- time on message
- Today / Yesterday / weekday / date separators
- read mark
- edited marker

## C. Message actions

Use the message `⋯` menu.

Test:
- Reply
- Reaction
- Forward
- Edit
- Delete for me
- Delete for everyone

## D. Chats page

Test:
- search
- All
- Unread
- Groups
- pin
- favourite
- archive
- draft

## E. Profile photo

Me → Profile photo → Change.

Check it in:
- Chats
- direct chat header
- group/member surfaces
- Status
- call screen

## F. Groups

Create a group by usernames.

Test:
- send messages
- file
- voice note
- unread count
- add/remove member
- make another admin
- group photo
- Suggest Reply
- Catch me up
- Ask Q

Group AUTO is intentionally unavailable.

## G. Voice notes

Android:
1. Tap `🎙`
2. Speak
3. Tap `■`
4. Recipient plays it
5. Try playback speed
6. Tap Q

With `OPENAI_API_KEY` configured, the backend should save a transcript and Q should be able to summarise it.

## H. Calls

Use two different LEMMIQ accounts/devices.

Caller:
- should show `Ringing…`
- should hear ringback
- must not show Connected just because its own LiveKit connection succeeded

Receiver:
- receives incoming-call alert/ringtone
- taps Answer

After receiver joins:
- both show Connected
- timer starts
- Android should use normal earpiece by default
- Speaker manually changes to loudspeaker
- test Mute and End

Also test no answer for approximately 45 seconds.

## I. Status

Test:
- text
- photo
- video
- view from second account
- own view count
- reply from second account
- delete own Status

## J. Trust history

Run a Fact/Scam Check, then reopen Trust.

Check:
- saved history
- search
- reopen
- delete
- clear
- same claim reuse
- Refresh check

## K. Social IQ

Q → Social IQ → Scan.

Use conversations containing explicit wording such as:

```text
I'll send the quote tomorrow.
Remind me to call John on Monday.
We agreed to meet at 7 PM.
```

Check extracted items. Delete any memory the user does not want retained.

---

# Troubleshooting

### Calling says LiveKit is not configured
Check all three on Render:

```text
LIVEKIT_URL
LIVEKIT_API_KEY
LIVEKIT_API_SECRET
```

### No Android incoming call alert
Check:
- `android/app/google-services.json`
- `FIREBASE_SERVICE_ACCOUNT_B64`
- Android notification permission
- LEMMIQ Me screen says `Push ready`

### Call stays Ringing
The other LEMMIQ user must actually answer/join the LiveKit room. A caller's own room connection is no longer treated as an answered call.

### Call starts on loudspeaker
V2.4 explicitly requests the normal earpiece route on Android. If a specific phone/ROM still forces speaker, send the model/Android version and screenshot so its audio-device routing can be handled separately.

### Voice message has no transcript
Check:

```text
OPENAI_API_KEY
LEMMIQ_VOICE_TRANSCRIPTION=true
```

Voice messages still work without transcription.

### Photo/file/voice upload returns media storage error
Check your private R2/S3 settings on Render.

### Browser still shows old interface
Open `/web/` in a fresh tab or remove/re-add the installed PWA once so the V2.4 service-worker shell replaces the old cache.

---

# Validation completed before packaging

- FastAPI/Python source compilation: passed
- Browser/PWA JavaScript syntax check: passed
- Backend smoke tests passed for:
  - registration/direct chat
  - reply/reaction/edit
  - pin/favourite/draft
  - search
  - groups/unread
  - Status
  - privacy preference endpoint
  - block enforcement
  - delete-for-me
  - profile avatar
  - direct/group voice upload
  - Status media/view
  - LiveKit-not-configured fallback
- V2.3 → V2.4 voice-table migration smoke test: passed
- Kotlin structural/brace validation: passed
- LiveKit integration follows the current Android SDK 2.x dependency/repository pattern.

The Android project cannot be fully Gradle/device-compiled in this build environment, so Android Studio sync/build on your PC is the final native compilation check.
