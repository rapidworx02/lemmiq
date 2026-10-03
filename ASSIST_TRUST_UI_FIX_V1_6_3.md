# LEMMIQ V1.6.3 — Assist + Trust UX fix

## Assist
- **Discard** hides the suggestion without sending or editing the message.
- **Edit** copies the suggestion into the normal composer and hides the suggestion card.
- **Send** sends it normally; the suggestion is cleared on a successful send.

## Fact / Scam Check
- Displays a progress dialog immediately when the request starts.
- Displays a dedicated error dialog if the request fails.
- Displays the existing Trust result dialog on a successful response.
- Backend unchanged. If fact checking fails, inspect Render logs and verify that the API keys are set.

## GitHub + installation
Replace these three Android files in your existing repository:
1. `android/app/src/main/java/com/lemmiq/app/LemmiqApp.kt`
2. `android/app/src/main/java/com/lemmiq/app/LemmiqViewModel.kt`
3. `android/app/build.gradle.kts` (version display/build number only)

Keep your existing `android/local.properties`, with your actual Render URL. Sync Gradle, build, and reinstall the APK. No Render backend, PostgreSQL, or environment variable changes are necessary.

Android compilation not performed in this environment.
