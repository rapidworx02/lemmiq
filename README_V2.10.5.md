# LEMMIQ V2.10.5 — Q Predict Main Q Wallet

V2.10.5 completes the server-side migration that V2.10.4 prepared. It is based on the actual backend/app source supplied from the live LEMMIQ repository.

## Main change

Q Predict now uses the existing V2.8 LEMMIQ Q wallet (`q_user_wallets`) and the existing auditable Q ledger (`q_ledger_entries`). New prediction stakes no longer use the separate 10,000 Predict Credit wallet.

### Q Predict money flow

1. User stakes Q.
2. Q moves from the user's Q wallet to the `PREDICT_ESCROW` system wallet in the same database transaction as the prediction position.
3. On settlement:
   - winner: stake + proportional profit - configured fee returns to the user's Q wallet;
   - losing stake funds the winning pool;
   - fee on winning profit moves to the `PROFIT` system wallet;
   - VOID/no-winner outcomes return original Q stakes.
4. Every Q movement is written to the normal Q ledger and therefore appears in Q Activity.

Ledger event types include:
- `Q_PREDICT_STAKE`
- `Q_PREDICT_PAYOUT`
- `Q_PREDICT_REFUND`
- `Q_PREDICT_FEE`
- `Q_PREDICT_ROUNDING`

## Legacy PC safety

Existing Predict Credits are **not converted to Q**.

On the first V2.10.5 database migration:
- existing Q Predict markets are marked `wallet_unit=PC`;
- active legacy PC markets are VOIDed and their PC test stakes are returned to the legacy PC wallet;
- draft/review PC markets are cancelled;
- historical PC rows remain in the database for audit/history;
- new markets are created with `wallet_unit=Q`.

The old `q_predict_wallets` and `q_predict_ledger` tables are retained only for historical compatibility.

## Backend-editable Q Predict controls

Master/Risk Admin can manage:
- Q staking enabled / paused
- minimum stake Q
- maximum stake Q per prediction
- per-user per-market Q exposure limit
- daily Q Predict exposure limit
- weekly Q Predict exposure limit
- platform fee percentage (applied to winning profit, not returned stake)
- auto-drafting, auto-publish, auto-settlement and market limits

Canonical endpoints remain under `/v29/predict/...`. A compatibility `/v2104/predict/.../stake` route remains so the V2.10.4 Android build can still stake Q after the backend upgrade.

## Q feature pricing by tier

V2.10.5 adds server-authoritative feature pricing tables:
- `q_feature_settings`
- `q_features`
- `q_feature_tier_rules`
- `q_feature_usage`
- `q_feature_admin_audit`

Every feature/tier starts at **0 Q**. The user interface should simply show 0 Q where relevant; it does not use “free during beta testing” wording.

The server derives a user's tier from their active subscription package. The client cannot claim a cheaper/premium tier by changing a request parameter.

Feature keys seeded at launch include Q Chat, Q Vision, Q Predict Analysis, Trust Check, Business Agent, document analysis, Q-to-Q, voice transcription, smart memory, chat summary and suggest reply.

Existing shadow-usage tracking now also records successful supported feature usage as a 0 Q `FEATURE_USAGE` Q-ledger event.

## Browser/PWA

V2.10.5 adds a compatibility layer so the existing V2.9 Q Predict browser script receives the real Q numbers while all PC/Predict Credit wording is normalized to Q. The Q Predict header reads the authoritative `/v28/wallet` balance.

The PWA service-worker cache is bumped to `lemmiq-v2105-shell-1`.

## Android

- versionCode: **55**
- versionName: **2.10.5**
- Q Predict staking now posts `amount_q` directly to `/v29/predict/markets/{id}/stake`.
- Q feature catalog uses authenticated `/v2105/q-features/catalog`.

## Tested before packaging

- Python compile of the complete backend app.
- Import of the FastAPI app with all new routes registered.
- Fresh SQLite Q Predict flow: two users stake Q, winner payout and fee reconcile to zero Predict Escrow balance.
- Legacy V2.9 database migration: active PC market becomes VOID, PC stake is returned, and Q mode is enabled without converting PC to Q.

## Regulatory/product note

Q Predict is technically integrated with Q in this version. If Q becomes purchasable, withdrawable, cash-redeemable, or otherwise readily convertible to real-world value, obtain appropriate legal/regulatory advice before public deployment of prediction staking.
