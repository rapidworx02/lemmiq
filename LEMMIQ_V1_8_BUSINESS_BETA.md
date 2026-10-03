# LEMMIQ V1.8 Business Beta

V1.8 keeps the personal LEMMIQ app and adds an optional Business Beta module for testing. It is not a separate business app.

## New features

- Business profile: name, type, description, website, phone, email, hours, service area, tone and AUTO confidence threshold.
- Approved Knowledge Base with categories: FAQ, Service, Pricing, Policy, Hours, Area and Other.
- Business document ingestion for TXT, MD, CSV, PDF and DOCX, up to 5 MB. Text is extracted into the private knowledge base.
- Per-customer Business Agent settings: OFF / ASSIST / AUTO.
- Owner-controlled customer memory and tags per LEMMIQ chat.
- Business reply drafting grounded in approved knowledge + customer memory + recent chat context.
- Confidence / grounding score, explanation and knowledge sources on Business Agent suggestions.
- Guarded AUTO: Business Agent takes priority over personal Auto when enabled. It auto-sends only if the AI marks the answer as not requiring review AND confidence meets the owner's threshold. Otherwise it waits for the owner.
- Learn from chat: AI proposes reusable business facts from a conversation, but saves nothing until the owner explicitly approves each candidate.
- Existing V1.7 messaging, media sharing, push, WhatsApp/SMS intelligence, Money, Q Agent and Trust remain in the project.

## Deploying over V1.7

Replace the V1.7 project with this V1.8 source and push it to the same GitHub repository:

```cmd
cd C:\Users\pc\LEMMIQ
git add .
git commit -m "LEMMIQ V1.8 Business Beta"
git push origin main
```

Render redeploys the backend automatically. The existing PostgreSQL database can be reused. SQLAlchemy creates the new V1.8 tables on startup:

- `business_profiles`
- `business_knowledge`
- `business_chat_settings`
- `business_customer_memory`

No new Render environment variables are required. Existing `ANTHROPIC_API_KEY` is used by the Business Agent.

V1.8 adds Python packages `pypdf` and `python-docx`, so Render must complete a fresh backend build after the GitHub push.

## Android

Open `android` in Android Studio and retain your existing `android/local.properties`, for example:

```properties
sdk.dir=C\:\\Users\\pc\\AppData\\Local\\Android\\Sdk
lemmiq.apiBaseUrl=https://YOUR-ACTUAL-RENDER-SERVICE.onrender.com
```

Sync Gradle and install the new build. V1.8 uses version name `1.8.0`.

## Testing Business Beta

1. Open **Biz** in the bottom navigation.
2. Enable Business Beta.
3. Enter the business profile and save it.
4. Add approved knowledge manually, or upload a supported business document.
5. Open a customer chat.
6. Tap the briefcase icon in the chat header.
7. Enable Business Agent for that chat and choose ASSIST first.
8. Add only confirmed customer notes/tags if useful.
9. Receive a customer question and tap **Business reply**.
10. Review the generated reply, grounding confidence, reason and knowledge sources.
11. Use Discard, Edit or Send.
12. Test **Learn from chat**. Review every candidate before selecting Approve.
13. Test AUTO only after the knowledge base is accurate. A 90% default threshold is used.

## Important beta limitations

- This is not a replacement for a CRM, booking system, inventory system or accounting package.
- The agent must not invent prices, discounts, stock, bookings, warranties, completion status or guarantees.
- Uploaded documents become extracted text in the Business knowledge database. Keep sensitive or unnecessary personal information out of the knowledge base.
- Customer memory is owner-controlled; do not save passwords, OTPs, card numbers or unnecessary sensitive information.
- AUTO is experimental. Keep ASSIST as the normal test mode until the business knowledge is mature.
- The wider V1.x messenger is still a private beta and is not end-to-end encrypted.
