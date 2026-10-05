# LEMMIQ V2.7.1 — Google Play Internal Testing

This setup keeps the native Android features (including notification intelligence) and distributes LEMMIQ through Google Play instead of direct browser sideloading.

## 1. One-time local upload key

From the repository root:

```cmd
cd android
keytool -genkeypair -v -keystore upload-keystore.jks -alias lemmiq-upload -keyalg RSA -keysize 2048 -validity 10000
copy keystore.properties.example keystore.properties
```

Edit `android\keystore.properties` and enter the real values:

```properties
storeFile=upload-keystore.jks
storePassword=YOUR_KEYSTORE_PASSWORD
keyAlias=lemmiq-upload
keyPassword=YOUR_KEY_PASSWORD
```

Do not commit either `upload-keystore.jks` or `keystore.properties`. They are ignored by Git.

Export the public upload certificate for Play Console:

```cmd
keytool -export -rfc -keystore upload-keystore.jks -alias lemmiq-upload -file upload_certificate.pem
```

The PEM certificate is public; the JKS and passwords are secret.

## 2. Firebase

Keep your existing Firebase file here:

```text
android/app/google-services.json
```

It is deliberately excluded from Git.

## 3. Production API

V2.7.1 defaults to:

```text
https://lemmiq-api.onrender.com
```

You can override it locally in `android/local.properties`:

```properties
lemmiq.apiBaseUrl=https://lemmiq-api.onrender.com
```

or in CI with environment variable `LEMMIQ_API_BASE_URL`.

## 4. Build signed release AAB locally

From the repository root:

```cmd
gradle -p android clean :app:bundleRelease
```

Output:

```text
android/app/build/outputs/bundle/release/app-release.aab
```

V2.7.1 uses:
- package: `com.lemmiq.app`
- versionName: `2.7.1`
- versionCode: `44`

## 5. Create the Play Console app

Create a new app named LEMMIQ. The first uploaded artifact fixes the package ID for that Play Console app, so confirm that it is `com.lemmiq.app`.

Use Play App Signing. For a new app, let Google manage the app-signing key and use your `lemmiq-upload` key only as the upload key.

Go to:
Test and release -> Testing -> Internal testing

Create the release and upload:
`android/app/build/outputs/bundle/release/app-release.aab`

Add tester emails, roll out the internal test, then copy the tester opt-in/share link.

## 6. Point the LEMMIQ website to Google Play

In Render -> LEMMIQ backend -> Environment, add:

```text
ANDROID_PLAY_URL=<your Google Play internal testing opt-in URL>
```

Keep `ANDROID_APK_URL` empty so the website prefers Google Play.

Redeploy Render. The website's Android button will open the Google Play tester install page.

## 7. Optional GitHub Actions signed AAB

The included `.github/workflows/v271-play.yml` can build the signed AAB after these GitHub Actions secrets are added:

- `LEMMIQ_UPLOAD_KEYSTORE_BASE64`
- `LEMMIQ_UPLOAD_STORE_PASSWORD`
- `LEMMIQ_UPLOAD_KEY_ALIAS`
- `LEMMIQ_UPLOAD_KEY_PASSWORD`
- `GOOGLE_SERVICES_JSON_BASE64`

Optional repository variable:
- `LEMMIQ_API_BASE_URL`

To create the Base64 values on Windows PowerShell:

```powershell
[Convert]::ToBase64String([IO.File]::ReadAllBytes("android\upload-keystore.jks")) | Set-Clipboard
[Convert]::ToBase64String([IO.File]::ReadAllBytes("android\app\google-services.json")) | Set-Clipboard
```

Run the workflow manually from GitHub Actions -> LEMMIQ V2.7.1 Play Bundle -> Run workflow.

Download the `LEMMIQ-V2.7.1-PLAY-AAB` artifact and upload the AAB to Play Console.

## 8. Tester install flow

Each tester:
1. Opens the Google Play opt-in link using the Google account you added to the internal tester list.
2. Accepts the test.
3. Opens the Play Store install page.
4. Installs LEMMIQ normally from Google Play.

Do not ask testers to disable Play Protect.

## 9. Before production/open testing

Internal testing is for development validation. Before wider distribution, finish the privacy policy, prominent disclosure/consent for notification access and cross-app intelligence, Play app-content forms, store listing, and required policy declarations.
