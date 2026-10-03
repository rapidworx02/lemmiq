# LEMMIQ V2 Web Beta — Universal Browser / PWA

LEMMIQ V2 adds a responsive browser application on top of the existing V1.8 Android + FastAPI + PostgreSQL platform.

## Architecture

```
Android native app ──────┐
                         │
Browser / PWA ───────────┼── HTTPS / WebSocket ── FastAPI ── PostgreSQL
                         │                       ├─ Claude / Q
iPhone / iPad browser ───┘                       ├─ LEMMIQ Trust
                                                 └─ Business Agent
```

The web application is served directly by the existing FastAPI Render service. You do **not** need Vercel or a second frontend server for this beta.

## Browser features in V2

- Register / login
- Same LEMMIQ account as Android
- Direct chats
- Realtime WebSocket messaging while the web app is open
- Q suggested replies
- Discard / edit / send suggestion
- Chat summaries
- File/photo/video uploads through existing V1.7 media API
- Download private chat attachments
- LEMMIQ Trust
- Q Chat Agent
- Personal style profile
- Business profile
- Business Knowledge Base
- Business document upload
- Per-customer Business Agent settings
- Business Agent reply drafts
- Activity / detected-money dashboard
- PWA installation on supported browsers
- Mobile, tablet and desktop responsive UI

## Important platform difference

The browser/PWA **cannot read WhatsApp, SMS, banking or other app notifications**.

Keep the Android native app as the enhanced companion for:
- NotificationListenerService
- WhatsApp / SMS notification intelligence
- detected bank/payment alerts
- deeper Android background integrations
- native Firebase push

Synced structured events can then be viewed from the web dashboard.

iPhone/iPad users can use the web/PWA for LEMMIQ messaging, Q, Trust and Business Agent, but iOS does not provide the same broad cross-app notification listener capability as Android.

---

# Upgrade existing GitHub + Render deployment

## 1. Back up your existing repository

Before replacing files:

```cmd
cd C:\Users\pc\LEMMIQ
git status
git add .
git commit -m "Backup before LEMMIQ V2 Web Beta"
```

If there are no changes, Git may say there is nothing to commit.

## 2. Replace project files

Extract `LEMMIQ_V2_WEB_BETA.zip`.

Copy the contents of its `LEMMIQ_V2_WEB_BETA` folder over your existing:

`C:\Users\pc\LEMMIQ`

Keep your local Android `local.properties` if Windows asks about it.

## 3. Push to GitHub

```cmd
cd C:\Users\pc\LEMMIQ
git add .
git commit -m "LEMMIQ V2 Web Beta"
git push origin main
```

## 4. Render redeploy

Your existing Render service should automatically redeploy from GitHub.

No second Render service is needed.

The Docker build now copies:

`backend/web`

into the same container.

## 5. Test health

Open:

`https://YOUR-RENDER-SERVICE.onrender.com/health`

Expected:

```json
{"ok":true,"name":"LEMMIQ","version":"2.0.0"}
```

## 6. Open the web app

Open the root Render URL:

`https://YOUR-RENDER-SERVICE.onrender.com`

It automatically redirects to:

`/web/`

You should see the LEMMIQ browser login screen.

Use an existing Android LEMMIQ account or create a new account.

## 7. Test browser messaging

Use:
- one Android phone logged into one account
- Chrome/Safari/desktop browser logged into a second account

Send messages both ways.

Realtime WebSocket delivery works while both clients are connected.

## 8. Install as an app

### Android Chrome

Open LEMMIQ in Chrome.

Use:
- browser menu → Install app
- or the `Install app` button when Chrome exposes the PWA install prompt

### iPhone / iPad

Open LEMMIQ in Safari.

Tap:
- Share
- Add to Home Screen
- Add

LEMMIQ then launches in a standalone PWA window.

## 9. Optional custom domain

In Render, open the LEMMIQ web service and add a custom domain such as:

`app.lemmiq.com`

Update your DNS records exactly as Render instructs.

Because the frontend and API are same-origin, no Android/web API code needs to change for the browser app.

Your Android native build can continue using the Render service URL, or later use the custom API domain.

---

# Existing environment variables

V2 uses the same backend environment variables as V1.8:

- `DATABASE_URL`
- `LEMMIQ_JWT_SECRET`
- `ANTHROPIC_API_KEY`
- `ANTHROPIC_MODEL`
- `TAVILY_API_KEY`
- media storage variables from V1.7
- Firebase service-account variable for Android background notifications

No new API key is required for the web beta.

---

# Testing order

1. `/health` returns V2.0.0
2. Root URL opens web login
3. Login with an existing account
4. Chats load
5. Send a normal message
6. Receive a WebSocket message
7. Generate a Q reply
8. Fact / Scam Check
9. Ask Q
10. Business profile
11. Add business knowledge
12. Upload a business PDF/DOCX/TXT/CSV
13. Enable Business Agent for a customer chat
14. Generate Business Agent reply
15. Activity dashboard
16. Install PWA on Android
17. Add to Home Screen on iPhone

---

# Current limitations

- The current messaging architecture is not end-to-end encrypted.
- The PWA does not capture other apps' notifications.
- Browser background messaging/push is not yet equivalent to the native Android FCM implementation.
- Voice/video calling is not included in V2 Web Beta yet.
- Render Free services can cold-start.
- Media sharing still relies on the V1.7 media-storage configuration.
- The web beta is designed for testing, not a public production launch.
