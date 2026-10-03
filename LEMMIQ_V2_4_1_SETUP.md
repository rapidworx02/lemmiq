# LEMMIQ V2.4.1 — Clean Navigation, Q Home, Calls & Android Download

**Messaging with social IQ.**

This update is built on LEMMIQ V2.4 and fixes the crowded bottom navigation while making Q and voice calls easier to reach.

## What changed in V2.4.1

### 1. Clean 5-tab navigation

The persistent bottom navigation is now:

```text
Chats   Updates   Q   Calls   More
```

Lower-frequency features were moved into **More**:

- Trust / Fact Check
- Business Agent
- Activity
- Money
- Me / Profile

This applies to Android and the responsive browser/PWA.

### 2. Chats: Search or Ask Q

The Chats page now uses a prominent field:

```text
Search chats or ask Q
```

Typing normally filters:
- display name
- username
- group name
- recent message text

Tap the **Q** button beside the field to send the text to LEMMIQ Q instead.

The existing filters remain:
- All
- Unread
- Groups

### 3. Dedicated Q home

Q now has starter actions designed around LEMMIQ:

- Catch me up
- What did I promise?
- Which chats need a reply?
- Find details someone sent me
- Draft a reply
- Summarise this week
- Fact-check something
- Plan something
- Ask about a group

Q continues to use LEMMIQ chat/group context, Social IQ memory, and available voice-note transcripts. It does **not** autonomously send messages.

### 4. Proper Calls tab

Calls is now a primary tab.

It shows:
- completed voice calls
- missed calls
- no-answer calls
- declined calls
- date/time
- call duration when connected
- Call back action

The V2.4 call fixes remain:
- Ringing before Connected
- outgoing ringback
- incoming ringtone
- timer after answer
- Android earpiece by default
- manual Speaker button
- Bluetooth/headset preference
- missed/no-answer handling

### 5. Android APK download link

The web/PWA Android button now uses one stable public path:

```text
/download/android
```

The backend chooses the first available option:

1. `ANDROID_PLAY_URL`
2. `ANDROID_APK_URL`
3. bundled file: `backend/web/downloads/LEMMIQ.apk`

For private beta, option 3 is the easiest because Render can serve the APK directly.

---

# Upgrade steps

## Step 1 — Back up your current project

Command Prompt:

```cmd
cd C:\Users\pc\LEMMIQ
git add .
git commit -m "Backup before LEMMIQ V2.4.1"
```

If Git says there is nothing to commit, continue.

## Step 2 — Extract this ZIP

Extract:

```text
LEMMIQ_V2_4_1_NAV_Q_CALLS_APK.zip
```

Copy the contents of the project folder over:

```text
C:\Users\pc\LEMMIQ
```

Keep your existing local files:

```text
android\local.properties
android\app\google-services.json
```

Do not commit:
- Firebase Admin service-account JSON
- API keys
- LiveKit secrets
- `.env`
- `local.properties`
- signing passwords / keystores

## Step 3 — Check local.properties

Example:

```properties
sdk.dir=C\:\\Users\\pc\\AppData\\Local\\Android\\Sdk
lemmiq.apiBaseUrl=https://lemmiq-api.onrender.com
```

## Step 4 — Push the V2.4.1 source

```cmd
cd C:\Users\pc\LEMMIQ
git add .
git commit -m "LEMMIQ V2.4.1 navigation Q calls APK download"
git push origin main
```

Render should auto-deploy.

## Step 5 — Check the backend

Open:

```text
https://lemmiq-api.onrender.com/health
```

Expected:

```json
{"ok":true,"name":"LEMMIQ","version":"2.4.1"}
```

Then open:

```text
https://lemmiq-api.onrender.com/web/
```

The bottom bar should now show:

```text
Chats | Updates | Q | Calls | More
```

If the old web layout remains, fully close/reopen the installed PWA or refresh the browser. V2.4.1 uses a new service-worker cache.

---

# Android Studio update

## Step 6 — Open Android

Open:

```text
C:\Users\pc\LEMMIQ\android
```

V2.4.1 uses:

```text
versionCode 41
versionName 2.4.1
```

Android Studio:

```text
File → Sync Project with Gradle Files
```

Use JDK 17.

## Step 7 — Test on your phone

Connect your Android phone and press:

```text
Run ▶
```

Confirm the bottom navigation is:

```text
Chats
Updates
Q
Calls
More
```

Open More and confirm:
- Trust
- Business Agent
- Activity
- Money
- Me / Profile

---

# Make the Android download button actually download the APK

There are two supported methods.

## Method A — Easiest for your private beta: Render serves LEMMIQ.apk

### Step 8 — Build an APK

In Android Studio:

```text
Build → Build APK(s)
```

For wider tester distribution, a signed release APK is preferable. For your immediate private testing, the normal test/debug APK can also be used.

Typical debug path:

```text
C:\Users\pc\LEMMIQ\android\app\build\outputs\apk\debug\app-debug.apk
```

A release build is usually under:

```text
C:\Users\pc\LEMMIQ\android\app\build\outputs\apk\release\app-release.apk
```

### Step 9 — Run the included helper

From the LEMMIQ project folder, double-click:

```text
PUBLISH_ANDROID_APK.bat
```

It automatically checks for a release APK first, then debug APK, and copies it to:

```text
backend\web\downloads\LEMMIQ.apk
```

Or manually rename/copy the APK to that path.

### Step 10 — Push the APK

```cmd
cd C:\Users\pc\LEMMIQ
git add backend\web\downloads\LEMMIQ.apk
git commit -m "Publish LEMMIQ Android APK"
git push origin main
```

Wait for Render to redeploy.

### Step 11 — Test the direct link

Open on a phone:

```text
https://lemmiq-api.onrender.com/download/android
```

It should download:

```text
LEMMIQ.apk
```

The same route is used by:
- the top Android app button
- Me/Profile Android install button
- More → Download Android app on web/PWA

Android may ask the tester to allow installation from the browser/download source. That is normal for direct APK beta distribution.

### Updating the APK later

Every time you build a new Android version:

1. Build APK
2. Run `PUBLISH_ANDROID_APK.bat`
3. commit/push
4. Render redeploys

The public link remains exactly the same:

```text
https://lemmiq-api.onrender.com/download/android
```

So you do not need to resend a different URL to testers.

---

## Method B — External APK or Google Play Internal Testing

Instead of committing the APK to the project, set one of these Render environment variables:

```text
ANDROID_PLAY_URL=<your Play testing link>
```

or:

```text
ANDROID_APK_URL=<direct HTTPS APK/download link>
```

Priority is:

```text
ANDROID_PLAY_URL
→ ANDROID_APK_URL
→ bundled backend/web/downloads/LEMMIQ.apk
```

After saving the Render variable, redeploy. `/download/android` will automatically redirect there.

---

# V2.4.1 test checklist

## Navigation

Confirm Android and mobile web/PWA show only:

```text
Chats | Updates | Q | Calls | More
```

No Me overlap should remain.

## Chats

Test:
- Search by contact name
- Search username
- Search group
- All
- Unread
- Groups
- Enter a natural-language question and tap Q

## Q

Try:
- Catch me up
- What did I promise?
- Which chats need a reply?
- Find the address someone sent me
- Summarise this week

Confirm Q does not automatically send a message.

## Calls

Use two different accounts/devices.

Confirm:
- call appears in Calls history
- missed/no-answer/completed label
- duration for completed call
- Call back starts a new call
- Android defaults to earpiece
- Speaker button switches to loudspeaker

## More

Confirm:
- Trust
- Business
- Activity
- Money
- Me

open without bottom-navigation overlap.

## Android download

On another Android phone/browser:

```text
https://lemmiq-api.onrender.com/download/android
```

Confirm the APK downloads and can be opened for installation.

---

# Validation completed before packaging

- Python/FastAPI source syntax: passed
- Existing backend tests: passed
- Web/PWA JavaScript syntax (`node --check`): passed
- No duplicate HTML IDs
- `/app-config` V2.4.1 response tested
- `/download/android` without configuration returns a clear setup error
- bundled `LEMMIQ.apk` download path tested successfully with Android APK MIME type
- Kotlin source structural bracket validation: passed

A full Android Gradle/device compile still needs to be run in Android Studio on your PC because this build environment does not have the Android Gradle toolchain/SDK available.
