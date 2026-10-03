# LEMMIQ V2.0.1 — Android App vs Web/PWA Install Flow

This update separates the two install experiences clearly.

## Native Android app

Use this for the full Android experience:
- WhatsApp notification intelligence
- SMS notification intelligence
- detected payment/bank alerts
- Android background services
- native Firebase push
- all normal LEMMIQ chat / Q / Trust / Business features

The web app now reads these optional Render environment variables:

- `ANDROID_PLAY_URL`
- `ANDROID_APK_URL`

Priority:
1. `ANDROID_PLAY_URL`
2. `ANDROID_APK_URL`

### Recommended: Google Play Internal Testing

Publish the signed Android App Bundle to Google Play Internal Testing, copy the tester install URL, then add in Render:

```text
ANDROID_PLAY_URL=https://play.google.com/...
```

### Temporary testing option: APK download

Upload a signed APK to a private/public release location you control and set:

```text
ANDROID_APK_URL=https://...
```

Do not point this variable at a local Windows file path.

## Web/PWA install

The `Install Web App` button installs the browser/PWA version only.

On Android:
- Chrome → Install app / Add to Home Screen

On iPhone/iPad:
- Safari → Share → Add to Home Screen

The PWA cannot replace/update the native Android APK.

## Updating your own Android phone during development

Open:

`C:\Users\pc\LEMMIQ\android`

in Android Studio, connect your phone, then press Run.

V2.0.1 uses:
- `versionCode = 21`
- `versionName = "2.0.1"`

The Me screen now reads the version from `BuildConfig.VERSION_NAME` instead of showing the old hard-coded V1.6 label.

## GitHub + Render update

```cmd
cd C:\Users\pc\LEMMIQ
git add .
git commit -m "LEMMIQ V2.0.1 Android and Web install flow"
git push origin main
```

Wait for Render to redeploy, then open:

`https://YOUR-RENDER-URL/health`

Expected version: `2.0.1`.

The web page will show separate:
- `Get LEMMIQ for Android`
- `Install Web App`

buttons.
