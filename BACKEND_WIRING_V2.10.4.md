# LEMMIQ V2.10.4 backend wiring

## 1. Q feature pricing by tier

Copy these files into `backend/app/`:

- `v2104_q_features.py`
- `v2104_q_predict_contract.py`
- `v2104_predict_router.py`

The Q feature pricing module creates its own V2.10.4 tables in the existing `DATABASE_URL`, seeds every supported feature/tier at **0 Q**, and creates a global `charging_enabled=false` safety switch.

Supported tiers:

- `FREE`
- `STARTER_10`
- `PLUS_50`
- `PRO_100`
- `PREMIUM_500`
- `ELITE_1000`

Suggested feature keys are already seeded, including `Q_CHAT`, `Q_VISION`, `Q_PREDICT_ANALYSIS`, `TRUST_CHECK`, `BUSINESS_AGENT`, `DOCUMENT_ANALYSIS`, `Q_TO_Q`, `VOICE_TRANSCRIPTION`, `CHAT_SUMMARY`, `SUGGEST_REPLY`, and `SMART_MEMORY`.

### Main FastAPI app

Add:

```python
from .v2104_q_features import router as v2104_q_features_router
from .v2104_predict_router import router as v2104_predict_router

app.include_router(v2104_q_features_router)
app.include_router(v2104_predict_router)
```

If SQLAlchemy is not already installed, add it to your backend requirements.

Set a Render secret for admin pricing edits:

```text
LEMMIQ_MASTER_ADMIN_KEY=<long-random-secret>
```

List current feature/tier rules:

```text
GET /v2104/admin/q-features
Header: X-LEMMIQ-Master-Key: <secret>
```

Global feature charging remains OFF by default. Read or change it later:

```text
GET /v2104/admin/q-features/settings
PUT /v2104/admin/q-features/settings
Header: X-LEMMIQ-Master-Key: <secret>
Content-Type: application/json

{"charging_enabled": false}
```

When `charging_enabled=false`, user-facing quotes remain `0 Q` even if you preconfigure future non-zero tier prices.

Change a tier price later without an app release:

```text
PUT /v2104/admin/q-features/Q_VISION/PLUS_50
Header: X-LEMMIQ-Master-Key: <secret>
Content-Type: application/json

{
  "q_cost": 0,
  "enabled": true,
  "included_uses_daily": null,
  "included_uses_monthly": null,
  "discount_percent": 0
}
```

Keep all costs at `0` for now. The user UI should simply display `0 Q`; do not add beta/free wording.

## 2. Log feature usage now, even at 0 Q

In each existing backend feature handler, quote the feature using the authenticated user's current tier and record a usage row after completion.

```python
from decimal import Decimal
from .v2104_q_features import quote_feature, record_feature_usage

quote = quote_feature("Q_VISION", current_tier_key)
# current cost is 0 Q

# run feature...

record_feature_usage(
    user_id=current_user.id,
    feature_key="Q_VISION",
    tier_key=current_tier_key,
    quoted_cost=quote.q_cost,
    charged_cost=Decimal("0"),
    status="SUCCESS",
    reference=f"vision:{vision_id}",
)
```

For future paid usage, the existing Q wallet service should perform an atomic debit only after a successful billable action (or debit/reserve + automatic refund on failure). Also create the corresponding user-facing `q_ledger` entry.

## 3. Q Predict: Q wallet replaces Predict Credits

Do **not** convert the old 10,000 Predict Credit wallet or historical PC balances into Q. They were test credits and should remain historical only.

New Q Predict movements must use the existing V2.8 Q wallet and existing Q ledger:

- `Q_PREDICT_STAKE` = outgoing Q
- `Q_PREDICT_PAYOUT` = incoming Q
- `Q_PREDICT_REFUND` = incoming Q
- `Q_PREDICT_FEE` = outgoing Q / admin profit accounting as applicable

`v2104_q_predict_contract.py` contains the stake/refund/payout transaction rules. `v2104_predict_router.py` exposes the new Android stake endpoint:

```text
POST /v2104/predict/markets/{market_id}/stake
{"outcome":"YES","amount_q":10}
```

### Important

The uploaded source available to this update contained the Android app and web frontend, but not the current V2.8/V2.9 Python wallet/market repositories. Therefore the adapter is intentionally not guessed.

Wire `configure_q_predict(...)` to your existing authenticated Q-wallet and Q-Predict repository functions. Only then set `QPredictControls(enabled=True)` and make `/v29/predict/home` return:

```json
{
  "real_q_enabled": true,
  "minimum_stake_q": 1,
  "maximum_stake_q": 100
}
```

and market payloads should use:

```json
{
  "yes_pool_q": 25,
  "no_pool_q": 40,
  "pool_q": 65,
  "my_positions": [{"outcome":"NO","stake_q":10,"payout_q":0,"fee_q":0,"status":"OPEN"}]
}
```

Until that server adapter is connected, V2.10.4 deliberately disables new prediction staking instead of silently falling back to Predict Credits.

## 4. Q Predict analysis history

Android V2.10.4 now keeps versioned Q Predict analysis history per logged-in user on the device. The Q page exposes those saved analyses so reopening a response does not rerun AI.

For cross-device history later, mirror successful analyses to a server table using the same fields:

- user_id
- market_id
- market question
- answer
- references/source snapshot
- analysed_at
- version
- follow-up text

## 5. Q Activity

The Android and PWA Activity views read the existing `/v28/wallet/ledger`. Once backend feature handlers begin writing 0-Q usage and Q Predict writes the Q ledger kinds above, they automatically appear in Q Activity.
