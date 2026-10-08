LEMMIQ V2.10.2 — INTEGRATED ANDROID SOURCE

This package was built from the actual Android source archive supplied by the user.
Unlike the earlier helper-only patches, the real native source has been edited directly.

Integrated fixes:
1. Native bottom navigation now has 6 tabs:
   Chats · Updates · Q Economy · Q Predict · Calls · More
2. More tab is directly wired into the existing Home() navigation state.
3. More contains Trust / Fact Check, Business Agent, Activity, Money, Me / Profile,
   Settings and Privacy & Security.
4. Removed the hidden "Profile, Trust, Business & Settings" shortcut from the Q sheet.
5. Floating Q button is more transparent.
6. Direct-chat image attachments are detected by kind, MIME type OR filename extension.
   This fixes JPG/PNG/WEBP files that arrived as generic FILE attachments.
7. Chat photos use only 4dp coloured bubble padding.
8. Tapping a chat photo opens a full-screen viewer with pinch zoom, pan, double-tap zoom,
   tap-to-hide controls and Android Back/Close.
9. Group chat image attachments also render inline and open full-screen.
10. Call Decline is wired into the real LemmiqCallActivity with terminal-state guards and
    a bounded backend decline request so a slow connection cannot freeze the button.
11. Android version is now versionCode 52 / versionName 2.10.2.
12. Call screen version text now uses BuildConfig.VERSION_NAME.

FILES DIRECTLY MODIFIED:
- android/app/build.gradle.kts
- android/app/src/main/java/com/lemmiq/app/LemmiqApp.kt
- android/app/src/main/java/com/lemmiq/app/V24Ui.kt
- android/app/src/main/java/com/lemmiq/app/LemmiqChatMediaV2102.kt
- android/app/src/main/java/com/lemmiq/app/LemmiqCallActivity.kt
- android/app/src/main/java/com/lemmiq/app/CallDeclineV2102.kt

The package also includes the rest of the supplied current Android source unchanged so the
folder can be copied over the existing android/app tree without manually merging helpers.
