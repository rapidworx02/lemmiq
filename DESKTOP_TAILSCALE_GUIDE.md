# LEMMIQ V1.2.1 — Desktop + Tailscale Test Hosting

This build is designed for zero-Render testing:

Android phone (any internet connection)
→ Tailscale
→ private HTTPS Tailscale Serve URL
→ Windows desktop
→ FastAPI on 127.0.0.1:8080
→ local SQLite
→ Anthropic / Tavily APIs

## Why this version is safer for testing

The FastAPI server binds only to `127.0.0.1`, so port 8080 is not directly exposed to your home LAN or the public internet.
Tailscale Serve is the only remote entry point and makes the backend available to devices in your tailnet.

## 1. Install Tailscale

Install Tailscale on:
- the Windows desktop hosting LEMMIQ
- every Android test phone

Sign all test devices into the same tailnet/account (or explicitly share/invite devices/users).

## 2. Set up backend

Open:

`LEMMIQ_V1_2/backend`

Double-click:

`01_SETUP_WINDOWS.bat`

Then edit:

`backend/.env`

Example:

```
DATABASE_URL=
LEMMIQ_JWT_SECRET=your-long-random-secret
ANTHROPIC_API_KEY=your-key
ANTHROPIC_MODEL=claude-sonnet-4-6
TAVILY_API_KEY=your-key
```

Leave `DATABASE_URL` blank for SQLite.

## 3. Start backend

Double-click:

`02_START_BACKEND_LOCAL.bat`

Test on the desktop:

`http://127.0.0.1:8080/health`

Expected version: `1.2.1`.

Keep the backend window running.

## 4. Start private HTTPS access through Tailscale

Right-click:

`03_START_TAILSCALE_SERVE_ADMIN.bat`

Choose:

`Run as administrator`

It runs:

`tailscale serve --bg http://127.0.0.1:8080`

Tailscale prints a private HTTPS URL similar to:

`https://your-pc.your-tailnet.ts.net`

Copy that URL.

## 5. Test from Android browser first

Connect Tailscale on the phone.

Open:

`https://your-pc.your-tailnet.ts.net/health`

You should see the LEMMIQ health JSON.

Now turn Wi-Fi OFF and use 4G/5G.

Open the same URL again.

If it still works, remote hosting is ready.

## 6. Configure Android app

Open the Android project in Android Studio.

Android Studio will create:

`android/local.properties`

Keep the existing `sdk.dir=...` line.

Add:

`lemmiq.apiBaseUrl=https://your-pc.your-tailnet.ts.net`

No trailing slash.

Example:

```
sdk.dir=C\:\Users\pc\AppData\Local\Android\Sdk
lemmiq.apiBaseUrl=https://rohit-desktop.example-tailnet.ts.net
```

The file is gitignored, so your machine-specific URL is not committed.

## 7. Build / install

In Android Studio:

- Sync Gradle
- select the Android phone
- Run

The Me screen now displays the configured server URL so you can confirm which backend the APK is using.

## 8. Test outside home

On the phone:

- Wi-Fi OFF
- mobile data ON
- Tailscale ON
- desktop ON
- Tailscale connected on desktop
- `02_START_BACKEND_LOCAL.bat` still running
- Tailscale Serve still enabled

LEMMIQ should continue to connect.

## 9. Test two users

Install the app on two Android devices.

Both devices need Tailscale access to the same tailnet and use the same Serve URL.

Create two accounts and test:
- registration/login
- new direct chat
- realtime message
- Assist mode
- Auto mode
- Ask LEMMIQ
- chat summary
- chat memory search
- Fact / Scam Check

## 10. Stop remote access

Run as Administrator:

`04_STOP_TAILSCALE_SERVE_ADMIN.bat`

Or:

`tailscale serve off`

## Important limitations

- Your desktop must stay powered on and connected to the internet.
- The backend BAT window must remain running.
- Tailscale must remain connected.
- Every private tester must have approved tailnet access.
- This is a private beta architecture, not a public messenger deployment.
- Messages are still server-readable; V1.2.1 is not end-to-end encrypted.
- SQLite is fine for private testing, but PostgreSQL is preferable when scaling.
- There is no Firebase push yet, so background/killed-app notification delivery remains limited.
