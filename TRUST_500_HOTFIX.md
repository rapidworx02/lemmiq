# LEMMIQ V1.6.5 Trust backend hotfix

This is a **backend-only reliability patch** for the HTTP 500 returned by `/trust/check`.
It does not claim to diagnose your exact Render failure: read Render logs for the traceback.

## Apply

Copy these two files into the existing GitHub repository:
- `backend/app/trust.py`
- `backend/app/main.py`

Commit and push; Render automatically redeploys. No Android Studio build or reinstall needed.

## What changed

- Strict validation of model-generated JSON (including missing/null/non-numeric confidence and malformed source lists).
- Prevent third-party search/model errors from surfacing as generic HTTP 500 errors.
- Show actual retrieved evidence URLs, not model-invented citations.
- Return `UNVERIFIED` with confidence 0 when no evidence is available.
- Log external service failures by error class; never log private message text or API keys intentionally.

## Test

Use the **already installed V1.6.4 APK** after Render shows deploy success.
Tap Fact / Scam Check on an incoming message. If an API key is invalid or search is down,
LEMMIQ should show `UNVERIFIED` instead of HTTP 500. This is a graceful fallback,
not confirmation that the external fact-checking service is working.

To diagnose the original error, look at Render → lemmiq-api → Logs right after tapping.
Copy only the exception class and traceback, never your keys or private message text.
