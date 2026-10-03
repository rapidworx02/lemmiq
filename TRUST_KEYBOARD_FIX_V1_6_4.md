# LEMMIQ V1.6.4 — Trust + stable composer

## Fact / Scam Check
- Enlarged tap target using a TextButton with minimum 44dp touch height.
- New dedicated Trust HTTP timeout (up to 105 seconds) covers Render cold start, Tavily, and Claude.
- Existing loading/error dialogs remain; timeout gets a clearer error message.
- Trust result source URLs are clickable where HTTPS is present. Links open through the phone's URL handler.
- Backend endpoint stays `POST /trust/check`; no Render/backend change required.

## WhatsApp-style chat position
- Messages rendered bottom-anchored (`reverseLayout=true`, reverse message order).
- Scroll state survives typing and is only moved on new message IDs while near the bottom.
- Composer uses IME padding; activity requests `adjustResize`.
- Typing characters does not explicitly scroll the chat list.
- AI suggestion Discard, Edit, and Send are retained.

## GitHub files to update
1. `android/app/src/main/java/com/lemmiq/app/LemmiqApp.kt`
2. `android/app/src/main/java/com/lemmiq/app/LemmiqViewModel.kt`
3. `android/app/src/main/java/com/lemmiq/app/Api.kt`
4. `android/app/src/main/AndroidManifest.xml`
5. `android/app/build.gradle.kts`

Keep `android/local.properties` with your real Render URL. Rebuild and reinstall APK; GitHub push alone does not update an installed Android app.

## Validation
Source assertions and ZIP validation performed. Android Gradle compilation requires a local JDK 17 / Android SDK 37 installation and is not claimed here. Since the Trust backend uses third-party web/AI services, actual response times and behaviour need device testing.
