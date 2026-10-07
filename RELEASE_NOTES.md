# LEMMIQ V2.10 release notes

V2.10 is a stability + mobile UX release built on V2.9.

### Q Predict
- Fixes non-working `Q · Analyse this market`.
- Q analysis receives the visible market question, pool/sentiment data, predictor count, close time, resolution rule/source and current context where available.
- Q explains YES factors, NO factors, uncertainty and what matters before resolution.
- Q analysis cannot settle a market and cannot override the published resolution rule.

### Navigation
- Persistent nav target: Chats · Updates · Q Economy · Q Predict · Calls · More.
- More restores Profile, Trust / Fact Check, Business Agent, Activity, Money, Settings, Privacy & Security and app download.
- Removes the hidden secondary-navigation link from the Q assistant sheet.

### Calls
- Decline becomes terminal and idempotent.
- Local ringer stops immediately.
- Backend decline must notify the caller and reject later answer/connect events.
- LiveKit/WebRTC cleanup, listeners, timers, foreground service and audio focus are part of decline cleanup.

### Chat media
- Chat photos open full screen.
- Pinch zoom / pan on web/PWA; platform zoom on Android viewer.
- Large coloured padding around photo bubbles is reduced.

### Browser/PWA
- Fixes Q Predict narrow-column/blank-right-side mobile rendering.
- Prediction cards become readable mobile cards.
- Category and Q Economy tab rails are horizontally scrollable.
- Six-tab bottom nav and safe-area spacing.
- Floating Q becomes semi-transparent/glass-like.
