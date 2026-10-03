# LEMMIQ V1.6.2 — Activity app selection fix

Changes:
- Removed nested 280dp vertical scroller; the entire Activity page now scrolls using its parent LazyColumn.
- Removed the `.take(80)` app limit: all Android-visible installed launcher apps appear.
- Added `Select all` and `Clear all`; with a search, these operate on all matching apps instead.
- Added a confirmation before selecting all/matching apps because notification capture is privacy-sensitive.
- Bulk selection uses one SharedPreferences write, preserving other selections outside the search filter.
- Original backend, database, GitHub/Render configuration, branding and other features are unchanged.

## Installing
1. Extract this ZIP to your LEMMIQ GitHub working folder (or replace the existing project files).
2. Keep your own `android/local.properties` with the actual Render URL. It is not included in the ZIP.
3. Android Studio: open `android`, sync Gradle, build and Run or install a freshly built APK.
4. Activity → Choose apps → Select all → confirm, or use search and Select matches.
5. Scroll the entire page to verify that the bottom of the installed app list is reachable.

This is an Android-only UI/prefs change: the existing Render backend does not need a redeploy to support it. The Gradle/Android compilation must be verified in your Android Studio installation.
