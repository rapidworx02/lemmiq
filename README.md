# V1.6.1 deployment: GitHub + Render

**Use [`GITHUB_RENDER_V1_6_1_SETUP.md`](GITHUB_RENDER_V1_6_1_SETUP.md).** Previous desktop/Tailscale guides remain only for optional local testing.

# LEMMIQ V1.0.1 — GitHub + Render + PostgreSQL

LEMMIQ is the AI-native messenger build using the same deployment pattern as TruckPilotAI:

**Android app → Render FastAPI backend → Render PostgreSQL → Anthropic AI**

## Included working features

- Account registration and login
- Persistent Android session
- Username/name search
- One-to-one chats
- Real-time WebSocket delivery while the app is active
- PostgreSQL persistence on Render
- Unread counts
- Read receipt storage
- Per-chat categories
- AI modes: OFF / ASSIST / AUTO
- Partner, Dating, Bestie, Friend, Family, Work, Customer, Sales, Study and Custom agents
- Per-chat tone
- AI suggested replies
- Server-side Auto Mode
- 50-message AI context
- Basic sensitive-topic Auto pause
- 24-hour text Moments
- Agents and Profile screens
- Anthropic key stored only on backend

## Deploy backend with GitHub + Render

### 1. Create GitHub repo

Create a private GitHub repo called, for example:

`lemmiq`

From the extracted project folder:

```bash
git init
git add .
git commit -m "LEMMIQ v1.0.1 Render PostgreSQL"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/lemmiq.git
git push -u origin main
```

### 2. Create Render Blueprint

Render Dashboard → **New +** → **Blueprint** → connect the GitHub repo.

Render reads `render.yaml` and creates:

- `lemmiq-api` web service
- `lemmiq-db` PostgreSQL database

When Render asks for the unsynced secret, enter:

`ANTHROPIC_API_KEY`

Render automatically generates `LEMMIQ_JWT_SECRET`.

### 3. Test Render backend

After deploy, you will get a URL similar to:

`https://lemmiq-api.onrender.com`

Open:

`https://lemmiq-api.onrender.com/health`

Expected:

```json
{"ok":true,"name":"LEMMIQ","version":"1.0.1"}
```

### 4. Put Render URL into Android

Open:

`android/app/build.gradle.kts`

Find:

```kotlin
buildConfigField("String", "API_BASE_URL", "\"https://YOUR-RENDER-SERVICE.onrender.com\"")
```

Replace it with your actual Render URL.

Then **Sync Gradle**.

### 5. Open Android app

Android Studio → Open → choose the `android` folder.

Use:
- JDK 17
- Android SDK API 37

Run on your phone.

### 6. Test two real users

Phone A: create `rohit`

Phone B: create `eva2`

Phone A:

Chats → + → search `eva2` → send message.

If both apps are open, WebSocket delivery should be immediate.

### 7. Test AI Assist

Open chat → ⚙ → choose category → set **ASSIST** → choose tone.

After an incoming message, tap **Suggest reply**.

### 8. Test Auto Mode

Open recipient's chat → ⚙ → **AUTO**.

Normal incoming messages can receive an automatic server-side AI response.

V1 pauses Auto Mode for obvious sensitive words around passwords/OTPs, banking/payment, legal, medical emergencies, breakup/divorce escalation, sexual content, loans/contracts and credit cards.

### 9. Seed optional demo users

Render web service → Shell:

```bash
python -m app.seed_demo
```

Creates:

- eva
- john
- maya

Password: `password123`

## Local development

From `backend`:

```bash
python -m venv .venv
```

Windows:

```bat
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8080
```

Without `DATABASE_URL`, backend falls back to local SQLite for development only.

## Important private-beta limitations

Before public launch we still need:

- End-to-end encryption
- FCM background notifications
- Photos/video/voice notes
- Block/report/moderation
- Account deletion
- Rate limiting and abuse protection
- Device/session management
- AI-memory review/delete controls
- Stronger Auto Mode safety classifier
- Privacy policy and terms

Do not treat this V1 as secure for sensitive/private conversations yet because message bodies are still server-readable.


# LEMMIQ Trust Layer — V1.1

Incoming messages now include **Fact / Scam Check**. The backend combines scam/link heuristics, optional Tavily current-web search, and Claude evidence synthesis. Results use SUPPORTED, LIKELY FALSE, MISLEADING, UNVERIFIED, SCAM RISK or SUSPICIOUS plus an evidence-confidence score and sources.

Add these Render secrets:

```text
TAVILY_API_KEY=...
ANTHROPIC_API_KEY=...
```

Without Tavily, current factual claims are not treated as verified; the app returns UNVERIFIED unless scam/link heuristics are strong.

AI-generated photo/media detection is deliberately not presented as definitive. `/trust/media-capabilities` explains the production plan: C2PA/Content Credentials provenance + source lookup + metadata + forensic signals + detector signals.


# LEMMIQ V1.2 — Chat Agent

V1.2 keeps the V1.1 Trust Layer and adds a cross-chat personal communication agent.

## New V1.2 features

- Q / Ask LEMMIQ main tab
- Daily Chat Brief
- Needs Reply detection
- Ask questions across recent messenger history
- Searchable chat memory
- Per-conversation AI summary
- Personal communication style profile
- Recent-message cross-chat context
- Evidence references in Ask LEMMIQ answers
- Server-side privacy guardrails: style analysis avoids sensitive-trait inference

## New backend endpoints

- `GET /agent/brief`
- `GET /agent/needs-reply`
- `GET /agent/profile?days=30`
- `GET /agent/search?q=...`
- `GET /agent/chats/{chat_id}/summary`
- `POST /agent/ask`

## Example Ask LEMMIQ prompts

- `Who is waiting for a reply?`
- `What did John say about Saturday?`
- `Find the message about the invoice.`
- `Summarise what is important today.`
- `What follow-ups do I have?`

## Privacy

V1.2 analyses message history stored on the LEMMIQ server. It is still a private beta and is **not end-to-end encrypted**.

Before a public launch, add:
- explicit opt-in controls for cross-chat analysis
- per-chat exclusion
- memory retention controls
- delete AI memory / account deletion
- end-to-end encryption architecture
- background push notifications
- production moderation / abuse controls

## Render

No new database service is required. Deploy this version to the existing GitHub + Render + PostgreSQL stack.

Required secrets remain:
- `ANTHROPIC_API_KEY`
- `TAVILY_API_KEY` for current-web Trust checks
- `LEMMIQ_JWT_SECRET`
- `DATABASE_URL`


# V1.2.1 — Desktop / Tailscale Test Build

This update removes the need for Render during private testing. See `DESKTOP_TAILSCALE_GUIDE.md`.
It also fixes the Android Chat Agent API methods, makes the API URL configurable through `android/local.properties`, auto-loads `backend/.env`, and fixes the Windows backend startup command.


# V1.6 Desktop/Notification Intelligence update
Read `V1_6_DESKTOP_SETUP.md` for exact private testing instructions, privacy limitations and new features.
