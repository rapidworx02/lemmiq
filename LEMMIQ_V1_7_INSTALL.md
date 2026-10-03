# LEMMIQ V1.7 – GitHub + Render installation and testing

This package is the V1.6.4 app and the V1.6.5 Trust HTTP 500 backend hotfix, plus V1.7.

## What actually works in the code

- LEMMIQ 1-to-1 chat with photo, video, supported documents and contact cards.
- Android photo/video/document chooser. Contact chooser uses Android's ACTION_PICK; it does not require unrestricted contacts permissions.
- Authenticated download of shared media; photo is shown inline, and video/files open through a compatible app on the phone. 20 MB limit per upload.
- FCM token registration, data-only push, system notifications, registration on token refresh, and best-effort unregistration on logout. This requires **your own Firebase configuration**.
- Separate, opt-in WhatsApp and SMS *notification preview* intelligence: locally encrypted per-message snippets, select sources, 1/7/30-day retention, delete and optional on-demand inclusion in Q. Suggested reply can be copied; NO automatic WhatsApp/SMS sending.
- Existing Trust / Fact Check, AI Assist / Auto, Q, Activity and Money are retained.

NOT included: a complete WhatsApp/SMS history reader, live integration with WhatsApp chats that are open, WhatsApp/SMS sending, media transcoding, complete E2EE, calls, production malware scanning or guaranteed background delivery under every Android device's battery restrictions.

## 1. Update the EXISTING repository

Extract the ZIP. Copy its `android/`, `backend/` and `render.yaml` into your existing local LEMMIQ repository, typically `C:\Users\pc\LEMMIQ`.

Keep your current `android/local.properties`! It contains your real Render backend URL and Android SDK path. Do not commit API keys, Firebase service accounts or your `.env`.

This release adds new files to both Android and backend, so **do not update only `LemmiqApp.kt`**.

From Command Prompt in the repository root:

```cmd
cd C:\Users\pc\LEMMIQ
git status
git add android backend render.yaml LEMMIQ_V1_7_INSTALL.md
git commit -m "LEMMIQ V1.7 media push external chat intelligence"
git push origin main
```

If you get GitHub HTTP 403, authenticate as an account with write access to the repository `rapidworx02/lemmiq` or accept its collaborator invite.

## 2. Existing Render service

Let your existing `lemmiq-api` auto-deploy. Open its `/health` endpoint:

```
https://YOUR-ACTUAL-SERVICE.onrender.com/health
```

It should return version `1.7.0`. This does not require replacing your PostgreSQL database.

The backend creates **two additional database tables** on startup: `message_attachments` and `push_devices`. Existing user, message and insight tables remain. Back up the PostgreSQL data before deploying; the beta currently uses `create_all`, not Alembic migrations.

### Cloud media storage is necessary on Render

**Render's local filesystem is ephemeral.** To keep photo/video/files across restarts, configure a private S3-compatible object store such as Cloudflare R2. A storage provider may charge according to its plan and usage.

In R2, create a **private bucket** (for example `lemmiq-beta-media`) and scoped object-read/write credentials. Set the following in **Render → lemmiq-api → Environment**:

```
MEDIA_BUCKET=your-private-bucket
MEDIA_ENDPOINT=https://YOUR_ACCOUNT_ID.r2.cloudflarestorage.com
MEDIA_ACCESS_KEY_ID=your-R2-access-key-id
MEDIA_SECRET_ACCESS_KEY=your-R2-secret-access-key
MEDIA_REGION=auto
```

Never publish this bucket or create public media URLs. LEMMIQ accesses the bucket from the server and checks chat membership before streaming an attachment to a user.

Without these variables, media uploading returns a clear `503 Media storage not configured`. Ordinary text messaging still works. If you test the backend **locally** without Render, set `LEMMIQ_LOCAL_MEDIA=true` and leave the bucket variables empty; this writes under `backend/media_local` for development only.

The backend accepts JPEG, PNG, WebP; MP4, WebM, MOV; PDF, TXT, CSV, ZIP, DOCX and XLSX, each at most 20 MB. Some HEIC and other file types are not yet supported.

## 3. Optional: set up FCM push notifications

Firebase Cloud Messaging is a separate **configuration**, not something GitHub or Render automatically supplies.

1. Open the Firebase console, create/select a Firebase project and add an **Android app** with package name `com.lemmiq.app`.
2. Download the Android Firebase configuration file `google-services.json`.
3. Put it in `C:\Users\pc\LEMMIQ\android\app\google-services.json`. It is excluded from Git in this ZIP; keep it on the computer where you build the APK.
4. In Firebase project settings, create a **service account private key** for Firebase Admin. Download the JSON securely, then encode it in base64 in Windows PowerShell:

```powershell
[Convert]::ToBase64String([IO.File]::ReadAllBytes('C:\PATH\TO\firebase-service-account.json'))
```

5. Add that base64 text to **Render → lemmiq-api → Environment → `FIREBASE_SERVICE_ACCOUNT_B64`**. Do not commit the service account to GitHub. Delete unneeded local copies of the service account JSON after securely storing it.
6. Redeploy Render.
7. On the phone, open LEMMIQ → Me → **Enable / refresh message push alerts** and allow Android notifications.
8. Open LEMMIQ on two separate phones. Background phone B, then send a message from phone A. Phone B should get a generic LEMMIQ notification; tap it to open the app.

When `google-services.json` is absent, the Android project deliberately skips the Google services Gradle plugin; the Firebase client will be unavailable, but normal messaging can still run. When the backend Firebase service account is absent, server messages still work without FCM.

Push is data-only with a generic preview and is best effort. Delivery can be delayed by Render Free cold starts, Android Doze, battery restrictions, lack of network, or a force-stopped app. FCM is **not** a replacement for a reliable server/infrastructure design.

## 4. Build the Android APK

Open `C:\Users\pc\LEMMIQ\android` in Android Studio. Open `android/local.properties`, preserving `sdk.dir`, and set:

```properties
lemmiq.apiBaseUrl=https://YOUR-ACTUAL-SERVICE.onrender.com
```

Do not use brackets/Markdown link syntax or a trailing slash. Sync the Android project using its specified SDK/Gradle/JDK versions; then Run on your phone.

**Important:** The supplied project does not contain the Gradle wrapper scripts/JAR. If your existing working repository already has `gradlew`, `gradlew.bat` and `gradle/wrapper/gradle-wrapper.jar`, keep those files. Otherwise generate a Gradle 9.6 wrapper from a local compatible Gradle installation before building. An Android Gradle build was not performed in this delivery environment.

## 5. Test photo, video, file and contact sharing

- Create/login on two test phones and open the same LEMMIQ chat.
- Tap **+** at the left side of the text composer → Photo, Video, File or Contact.
- Select a photo. Verify the recipient sees the inline photo and can open it.
- Select a small MP4/PDF; verify the recipient can tap **Open / share**.
- Select a phone contact through the Android picker, review the confirmation dialog and tap Share. The other user should receive its name and phone number.
- Try unsupported and oversized files; the app should display an error.

All shared media and contact cards are **server-readable**, not E2EE. Use sample/test data during the beta.

## 6. Test WhatsApp and SMS intelligence

- In LEMMIQ → Activity, first grant Android Notification Access if necessary.
- Find **Universal Chat Intelligence** and switch **Capture new external previews** on. This is *separate* from the existing Money/Activity switches.
- Enable WhatsApp and/or SMS. Use the official WhatsApp, WhatsApp Business, Google Messages or supported Samsung SMS app.
- Choose 24-hour / 7-day / 30-day retention.
- Have another person send a **NEW** plain-text WhatsApp or SMS message while that chat is **not open** on your device, and ensure Android actually displays a notification with text. Existing chat history will not be imported.
- Tap **View recent previews**, then **Suggest reply**. Review the proposed draft, and use **Copy reply** to paste into the original app. LEMMIQ cannot send it.
- Optional: enable **Allow Q to use selected snippets**, then ask Q about recent incoming messages in the Agent tab. A maximum of 30 bounded snippets are included only when you tap Ask Q. The chat notification snippets themselves are not bulk-synced into the Activity server database.
- Use **Delete** to clear stored previews, or switch capture off.

The local preview database is encrypted using Android Keystore AES-GCM; notification titles or message bodies may be unavailable if the source app hides them or the conversation is open. Group notifications, OTPs, password reset and authentication texts are excluded by basic rules. Do not use the service to collect information without appropriate consent.

## 7. Verification checklist

- Render `/health` = `1.7.0`.
- Existing text messaging and Fact / Scam Check work.
- Cloud media bucket configured; a photo survives a Render restart.
- FCM device token registered; notification appears with the recipient app in background.
- WhatsApp/SMS opt-in produces a local preview for a **new** notification and never auto-sends.
- Q external context remains off until separately enabled.

## Known limits / security TODOs before public launch

- Add proper E2EE architecture, media encryption at rest, migration framework, malware scanning, account deletion, file retention and upload quotas.
- Add rate limiting and device/session management.
- Replace in-memory WebSocket registry if deploying more than one Render instance.
- Obtain legal/privacy review for handling other apps' notifications and ensure platform distribution policies are met.
- Test Android background behaviour on multiple manufacturers and OS versions.
