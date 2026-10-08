# LEMMIQ V2.10.3

This update is built on the integrated V2.10.2 Android source and carries forward the working 6-tab navigation and chat-photo fixes.

## Included in the Android build

- Q Predict no longer sends **Analyse this market** to the generic Q home.
  - Analysis runs inside the selected market modal.
  - Sends Q the market question, crowd YES/NO, predictor count, user position, close time, resolution time, rule and source.
  - Explicitly tells Q to produce an independent analysis and not treat crowd percentage as probability.
  - Supports follow-up **Ask Q about this market…** while staying attached to the market.
  - Q analysis never controls settlement.
- Q Predict timing is clearer:
  - `Prediction closes`
  - `Resolution`
  - `Source`
  - `Resolution rule`
- Old wording such as `at the Q Predict resolution time` is displayed with the actual configured resolution timestamp when available.
- Q Predict now exposes:
  - My predictions
  - Recent results
  - Leaderboard
- Resolved markets show result, resolved time, source value, user position and payout when supplied by the server.
- Chats:
  - Unread filter shows live total.
  - Chat/group rows show timestamps and unread badges more clearly.
  - Chats bottom tab shows total unread badge.
  - Muted chats retain the unread count and show mute state.
- Floating Q button:
  - hidden while a direct/group chat is actively open, so it cannot cover the send/composer control.
- More:
  - removed the large `Tools, privacy and account` explanatory hero.
  - added a compact Notifications destination.
- Notification Center:
  - keeps a local history of received LEMMIQ push events even after the Android notification is dismissed.
  - mark all read / clear controls.
- Android push system:
  - dedicated channels for Messages, Calls, Q Economy, Q Predict, Q Assistant and System/Security.
  - foreground app no longer automatically suppresses message notifications.
  - FCM token refresh continues to auto-register.
  - supports data push types for Q Daily, wallet/transfer/referral/package, Q Predict results/close/watch, Q-to-Q and Q analysis.
  - notification taps route to direct/group chat, Q Economy, Q Predict market, Q Assistant or Notification Center where data is supplied.

## Browser/PWA patch included

`backend/web/v2103.css`:
- removes the oversized More hero block.
- hides the global Q orb while a chat thread is open so Send remains unobstructed.
- service worker cache is bumped to V2.10.3.

## Important backend requirement for proactive engagement notifications

The Android client is now ready to receive these event types, but server-side code must emit them. This package does not contain your current Python backend source, so it cannot safely add those server events automatically.

Recommended FCM data event types:

- `q_daily_ready` — title: `Your Daily Q is ready to claim`
- `q_credit` — e.g. `+2 Q added to your wallet`
- `q_transfer`
- `q_referral`
- `q_package`
- `q_market`
- `q_predict_close`
- `q_predict_result`
- `q_predict_void`
- `q_predict_watch`
- `q_to_q`
- `q_analysis`

Do not send `Q received` before a manual claim actually credits the wallet.

## Version

- versionCode: 53
- versionName: 2.10.3
