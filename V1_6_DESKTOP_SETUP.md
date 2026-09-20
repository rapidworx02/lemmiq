# LEMMIQ V1.6 — Windows Desktop + Tailscale testing

## What is implemented

- Existing 1:1 messenger and per-chat OFF/ASSIST/AUTO, Moments, Q Chat Agent and manual fact/scam check.
- New on-device NotificationListenerService. **Off by default**. User must grant Android notification access, select specific source apps and select categories. No historical notification import.
- Local recognition of payment alerts, bills, deliveries, schedule/travel changes and basic scam signals; ignores authentication codes; dedup and per-account local SQLite with 1/7/30-day retention.
- LEMMIQ Money: detected spending/incoming payments, editable manual-transaction addition via local input (no bank balance). It doesn't verify transaction completeness.
- Q Activity dashboard: source allowlist, categories, retention, explicit optional structured-event syncing, review and delete.
- Q Chat Agent can incorporate **only opt-in synced structured events** along with chat history; source text is treated as untrusted context, not instructions.
- Branded launcher icon from the approved LEMMIQ logo and new gradient headers, dashboard cards and five-tab navigation.

## Requirements

- Windows PC (Python 3.11 or 3.12, Android Studio and JDK 17).
- Android test phone with Android 8+ and Tailscale installed for outside-home access.
- LEMMIQ backend running on your PC and Tailscale Serve, not Render.
- Anthropic API key for actual AI generation and Tavily API key for live-evidence fact checks. API usage may incur costs even when hosting is free.

## Step 1 — extract

Extract the ZIP to `C:\LEMMIQ\LEMMIQ_V1_6`.

## Step 2 — backend dependencies

Open `backend`; run `01_SETUP_WINDOWS.bat` once. When it finishes, edit `backend\.env`:

```
DATABASE_URL=
LEMMIQ_JWT_SECRET=replace-with-at-least-32-random-characters
ANTHROPIC_API_KEY=your-key
ANTHROPIC_MODEL=claude-sonnet-4-6
TAVILY_API_KEY=your-key
```

Keep `DATABASE_URL=` blank for SQLite. If the `.env` file already exists, don't overwrite it.

## Step 3 — local server

Run `02_START_BACKEND_LOCAL.bat` and keep it open. Test on PC:

`http://127.0.0.1:8080/health`

Expected: `"version":"1.6.0"`.

## Step 4 — private HTTPS access

Sign into Tailscale on PC and each test phone. Run `03_START_TAILSCALE_SERVE_ADMIN.bat` as administrator. Copy the HTTPS URL shown by `tailscale serve status`, such as `https://your-desktop.your-tailnet.ts.net`.

With Tailscale connected, open `https://YOUR-TAILSCALE-URL/health` in a phone browser. Turn Wi-Fi off and try again over mobile data. Do not open port 8080 on your router or use Tailscale Funnel; use Serve only for private testers.

## Step 5 — configure Android

Android Studio → Open → `LEMMIQ_V1_6\android` (not the app subfolder).

In `android/local.properties`, **keep the existing `sdk.dir`** and add:

`lemmiq.apiBaseUrl=https://YOUR-TAILSCALE-URL`

No trailing slash. Sync Gradle using JDK 17 and installed Android SDK 37. Run on your phone or Build > Build APK(s).

## Step 6 — two-phone messaging test

Install the same APK on two Android devices on the tailnet. Register separate users, start a chat, send and receive messages, test ASSIST, Q, and manual Trust Check. Confirm `Me` shows your Tailscale URL. With phone 1 on 5G, verify messages still arrive while the app remains open.

## Step 7 — explicitly enable selected notifications

In LEMMIQ open `Activity`:

1. Tap **Open notification access settings**, grant access to LEMMIQ, and return.
2. Turn **Capture permitted alerts** on.
3. Select categories (e.g. Payments + Deliveries).
4. Tap **Choose apps**, search for and tick a banking or shopping app you wish to include.
5. Have that app create a *new* ordinary payment or delivery notification. Tap Refresh.
6. Check the event card. Unknown notification formats may not match; Android or the source app can hide the text.

Test a payment safely with the **Money → Add manual transaction** field if your bank isn't sending alerts. Do not conduct an actual purchase just for this test.

## Step 8 — optional Q cross-agent insights

Activity → **Include structured events in Q** ON. Pending stored structured events will sync to your own desktop backend. Raw notification bodies are *not* uploaded, but eligible categories contain brief redacted details (e.g. delivery wording). The desktop database is server-readable. Open Agent and ask: “Summarise my selected phone activity” or “What detected spending alerts do I have?”.

With sync OFF, the on-device Money/Activity dashboards still work; Q on the server only sees messenger history. OFF does not delete previously synced data: use **Delete all my phone insight data** to erase both local and server copies.

## Stop and limitations

Stop remote access with `04_STOP_TAILSCALE_SERVE_ADMIN.bat`; close the backend CMD when finished. The desktop must remain on, online and awake for access outside home.

Known limitations: there is no account verification / E2EE, Android background FCM push, real C2PA image verification, comprehensive anti-phishing reputation feed, live bank connections, full account transaction records, calendar write access, or true payment confirmation. Notifications can be missing or duplicates and some Android versions redact sensitive alerts. Only the selected heuristics are implemented. This is a private test build, not a production-ready financial or security app.
