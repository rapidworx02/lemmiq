# LEMMIQ V2.10.3 push event contract

Use FCM data messages. Include a stable `event_id` so clients can deduplicate.

## Daily Q available

```json
{
  "type": "q_daily_ready",
  "event_id": "daily-q-USERID-2026-10-08",
  "title": "Your Daily Q is ready to claim",
  "body": "Open Q Economy to claim today's Q.",
  "deep_link": "q-economy"
}
```

## Q credited

```json
{
  "type": "q_credit",
  "event_id": "ledger-TXID",
  "title": "+2 Q added to your wallet",
  "body": "Your Daily Q claim was credited.",
  "deep_link": "q-economy"
}
```

## Q Predict result

```json
{
  "type": "q_predict_result",
  "event_id": "predict-result-MARKETID",
  "market_id": "123",
  "title": "Q Predict market resolved",
  "body": "BTC ≥ US$86,000 resolved NO. Tap to view your result.",
  "deep_link": "q-predict/123"
}
```

## Messaging

Continue sending `chat` / `group` with `chat_id` / `group_id`, sender/group name, body and authoritative `unread_count`.

The server read/unread state should remain the source of truth. Dismissing an Android notification must not mark a conversation read.
