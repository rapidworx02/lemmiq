# LEMMIQ V2.3 — Groups + Voice Messages + Voice Calling Beta

V2.3 builds directly on V2.2.1 and retains:
- Android + browser/PWA access
- Personal Chat Intelligence OFF / ASSIST / AUTO
- Business Agent
- LEMMIQ Trust
- Notification Intelligence
- editable/resettable Money and Activity data
- Firebase background message notifications
- self-notification exclusion
- Android/mobile-browser safe-area fixes

## New V2.3 features

### 1. LEMMIQ Groups

Create groups by searching LEMMIQ usernames.

Included:
- group name
- optional group photo
- multiple members
- ADMIN / MEMBER roles
- add/remove members
- promote/demote admins
- group messages
- photo/video/file attachments
- voice messages
- group push notifications on Android
- group unread counts
- Q “Catch me up”
- Ask Q about a group
- group AI modes: OFF / ASSIST / SUMMARY
- group ASSIST: Q draft → Discard / Edit / Send
- no group AUTO replies in V2.3

### 2. Voice messages

Android:
- tap microphone to start recording
- tap stop square to finish/send
- voice playback
- 1× / 1.5× / 2× speed

Browser/PWA:
- tap microphone to record
- MediaRecorder uploads audio
- compatible browsers may create a live speech transcript while recording
- voice playback
- Q voice-note summary/reply when a transcript exists

Important:
- Android native V2.3 records the audio correctly but does not yet perform local speech-to-text for the sender.
- Q voice summary requires a stored transcript. Voice notes recorded in compatible browsers may include one.
- A future transcription provider/on-device transcription can make this universal.

### 3. One-to-one voice calling beta

Provider: LiveKit Cloud / WebRTC.

Supported beta paths:
- Android → Android
- Android → browser
- browser → Android
- browser → browser while LEMMIQ is open

Included:
- call button in direct chats
- incoming Android call notification
- incoming browser call prompt while connected
- Answer / Decline
- microphone mute
- Android speaker toggle
- End call
- call history
- LiveKit server-side token generation
- no LiveKit secret in Android/browser

Not included yet:
- video calling
- group calls
- PSTN/normal phone-number calls
- WhatsApp calling
- iPhone native CallKit background calling
- guaranteed Safari incoming calls while Safari is closed

## 4. Mobile browser ASSIST fix

When a direct chat is in ASSIST:
- “✨ Suggest reply” remains visible
- Q only drafts
- user chooses Discard / Edit / Send
- ASSIST never auto-sends
- AUTO is still the direct-chat auto-reply mode

---

# Upgrade from your current GitHub project

## Step 1 — Back up

```cmd
cd C:\Users\pc\LEMMIQ
git add .
git commit -m "Backup before LEMMIQ V2.3"
```

If Git says nothing to commit, continue.

## Step 2 — Extract the V2.3 ZIP

Copy everything inside:

`LEMMIQ_V2_3`

over:

`C:\Users\pc\LEMMIQ`

Keep your local:
- `android/local.properties`
- `android/app/google-services.json`

Do not upload private Firebase service-account JSON files or LiveKit secrets to GitHub.

## Step 3 — Push

```cmd
cd C:\Users\pc\LEMMIQ
git add .
git commit -m "LEMMIQ V2.3 groups voice and calls"
git push origin main
```

Render should redeploy automatically.

## Step 4 — Check backend

Open:

`https://YOUR-RENDER-URL/health`

Expected:

```json
{"ok":true,"name":"LEMMIQ","version":"2.3.0"}
```

The V2.3 database additions are new tables, so `create_all()` can create them without modifying the existing message tables.

---

# LiveKit setup for voice calls

Voice messages do NOT need LiveKit.
Only real-time calling needs it.

## Step 5 — Create a LiveKit Cloud project

Create/sign in to LiveKit Cloud and create a project.

From the LiveKit project settings copy:
- Project URL
- API key
- API secret

Your project URL normally uses a secure WebSocket LiveKit URL supplied by LiveKit.

## Step 6 — Add the three secrets to Render

Open:

`Render → lemmiq-api → Environment`

Add:

```text
LIVEKIT_URL=<your LiveKit project URL>
LIVEKIT_API_KEY=<your LiveKit API key>
LIVEKIT_API_SECRET=<your LiveKit API secret>
```

Save.

Render redeploys.

Never put the API secret in Android, browser JavaScript, GitHub, `local.properties`, or `google-services.json`.

The LEMMIQ backend creates short-lived room tokens for authenticated users.

## Step 7 — Firebase remains required for Android incoming-call alerts

Keep:
- `android/app/google-services.json`
- Render `FIREBASE_SERVICE_ACCOUNT_B64`

On Android:
`Me → Enable / refresh message push alerts`

Target:
`● Push ready`

If push is not ready, Android-to-Android calling can still work when both users already know to open the call, but background incoming-call alerts will not be reliable.

---

# Android build

V2.3 Android:
- package: `com.lemmiq.app`
- versionCode: 30
- versionName: 2.3.0
- JDK 17
- target/compile SDK 37
- LiveKit Android SDK 2.x

## Step 8 — Open Android Studio

Open:

`C:\Users\pc\LEMMIQ\android`

Keep your Render URL in:

`android/local.properties`

Example:

```properties
sdk.dir=C\:\\Users\\pc\\AppData\\Local\\Android\\Sdk
lemmiq.apiBaseUrl=https://lemmiq-api.onrender.com
```

## Step 9 — Sync Gradle

The update adds the LiveKit Android SDK and JitPack repository.

Use:

`File → Sync Project with Gradle Files`

Allow Gradle to download the new LiveKit dependency.

## Step 10 — Install

Connect your Android phone and press:

`Run ▶`

Allow:
- notifications
- microphone

The existing app should update in place if the signing key is unchanged.

---

# Test groups

1. Log in.
2. Chats.
3. Tap the `👥` floating button.
4. Enter a group name.
5. Search/select LEMMIQ usernames.
6. Create.
7. Send messages.

For admin testing:
- open group → `⋮`
- add member
- make admin/member
- remove member
- change group photo

For Q:
- `✨ Suggest reply` when Group AI = ASSIST
- `🧠 Catch me up`
- `Q` to ask about group history

---

# Test voice messages

## Android

1. Open a direct or group chat.
2. Tap `🎙`.
3. Speak.
4. Tap `■`.
5. Wait for upload.
6. Recipient taps play.
7. Change playback speed using `1× / 1.5× / 2×`.

R2/S3 media storage must already be configured on Render.

## Browser

1. Open LEMMIQ over HTTPS.
2. Allow microphone.
3. Tap `🎙`.
4. Speak.
5. Tap stop.
6. Voice note uploads.

Browser speech recognition availability differs by browser. If a transcript was captured, the Q button on the voice note can generate a summary/reply.

---

# Test voice calls

## Android → Android

Phone A:
1. Open a direct chat.
2. Tap `📞`.

Phone B:
1. Put LEMMIQ in background.
2. Receive `Incoming LEMMIQ call`.
3. Tap it.
4. Answer.

Test:
- talk both directions
- mute
- speaker
- end

## Browser → Android

Browser:
1. Open direct chat.
2. Tap `📞`.
3. Allow microphone.

Android:
- answer FCM call notification.

## Android → Browser

Keep the recipient’s LEMMIQ web page open and connected.
An incoming-call prompt should appear through the LEMMIQ WebSocket connection.

## Browser → Browser

Both browser sessions must be open/connected for the V2.3 beta incoming prompt.

---

# Troubleshooting

### “LiveKit is not configured”
Check all three Render variables:
- LIVEKIT_URL
- LIVEKIT_API_KEY
- LIVEKIT_API_SECRET

### Android call rings but has no audio
Check:
- microphone permission
- LiveKit project URL/key/secret are from the same LiveKit project
- internet connection
- Android volume/audio route

### Android receives no call alert
Check:
- Firebase `google-services.json`
- Render `FIREBASE_SERVICE_ACCOUNT_B64`
- LEMMIQ → Me → Push ready
- Android notification permission

### Voice note upload fails
Check R2/S3 media variables:
- MEDIA_BUCKET
- MEDIA_ENDPOINT
- MEDIA_ACCESS_KEY_ID
- MEDIA_SECRET_ACCESS_KEY
- MEDIA_REGION

### Browser microphone fails
The browser must use HTTPS and microphone permission must be allowed.

---

# Security / beta notes

- LiveKit API secrets remain server-side only.
- LiveKit room/participant identifiers use opaque IDs rather than user email/phone details.
- V2.3 calling is app-to-app internet calling.
- Current LEMMIQ stored messages are still server-readable; full messenger E2EE remains future work.
- Group AUTO is deliberately disabled.
- This remains a private beta and should be tested before wider distribution.
