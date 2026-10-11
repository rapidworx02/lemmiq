# LEMMIQ V2.10.7.4 — Q Economy Engine

Built on the working V2.10.7.3 line while preserving the stable legacy `v28.js` and `v29.js` browser files.

## 1. Shared subscription wallets — V2.10.7.3 save bug fixed

LEMMIQ still uses exactly two receiving wallets for every subscription pack:
- one shared USDT TRC20 wallet
- one shared USDT BEP20 wallet

The V2.10.7.3 Admin Save / “Use for all packs” Internal Server Error is fixed by storing new shared wallets with the internal sentinel `ALL_PACKS`, instead of requiring a NULL `package_code`. This remains compatible with older production PostgreSQL schemas where `package_code` may still be NOT NULL.

Historical package-specific wallet rows and payment-order wallet references are not deleted.

## 2. Payment-order QR enlargement

The existing payment-order modal is preserved. Tapping the wallet QR now opens a separate large/full-screen lightbox so the payment order remains underneath it. Close with ×, Escape or tap outside the QR.

Existing Copy address / Copy amount / Copy Order ID behavior is untouched.

## 3. Unified 200% package earning cycle

Each package cycle keeps its existing USDT-denominated ceiling (normally 200% of package value).

Qualifying LEMMIQ-generated rewards now consume that cycle:
- PACKAGE_ACCRUAL — normal package daily accrual
- DAILY_ACTIVE — daily/basic Q claim
- WEEKLY_ACTIVE — optional weekly active reward
- REFERRAL — referral rewards
- SIGNUP_WELCOME — signup / welcome rewards
- PACKAGE_BONUS — package-linked bonus

These do NOT consume the package earning cap:
- user-to-user transfers
- purchased/deposited Q
- marketplace proceeds
- Admin wallet corrections
- AI refunds
- withdrawal refunds

When the accumulated qualifying USD-reference value reaches or exceeds the cap, the package becomes `COMPLETED`. The full qualifying reward is still credited if the final reward crosses slightly above 200%.

Spending Q later on AI, rebuy or withdrawal does not reverse earning-cap progress.

Upgrade behavior:
- existing `CAP_REACHED` lots are normalized to `COMPLETED`;
- existing package accrual is preserved and backfilled into the new breakdown;
- old historical referral/signup rewards are not retroactively added, avoiding surprise cap jumps on deployment;
- new qualifying rewards are counted from V2.10.7.4 onward.

## 4. Q + USDT rebuy / upgrade

Default controls:
- first purchase: existing 100% USDT flow
- same-package rebuy: max 40% package value in Q, minimum 60% USDT
- upgrade: max 50% package value in Q, minimum 50% USDT
- no downgrade
- rebuy/upgrade becomes available after the current package is COMPLETED or EXPIRED

Master Admin can change:
- rebuy enabled ON/OFF
- same-package max Q %
- upgrade max Q %
- weekly active Q amount

The Q value is calculated from the current Admin Q reference rate and locked into the hybrid order. Q is moved to `REBUY_RESERVE` while the USDT payment is pending.

On Admin payment approval:
- locked Q settles to the Profit wallet;
- the normal USDT payment order is approved;
- a new package row / new earning cycle is created;
- the old completed package remains unchanged in history.

Relevant ledger events:
- `PACKAGE_REBUY_Q_LOCK`
- `PACKAGE_REBUY_Q_DEBIT`
- `PACKAGE_REBUY_Q_REFUND`
- `PACKAGE_REBUY_USDT`
- `PACKAGE_ACTIVATED`

## 5. Global AI feature Q pricing + real wallet charging engine

AI prices are now GLOBAL — the same price for Free, Starter, Plus, Pro, Premium and Elite. Tier rows remain mirrored only for old-client/database compatibility.

Starting global configured prices:
- Q Chat: 0.25 Q
- Q Advanced: 1 Q
- Q Vision: 2 Q
- Trust Check: 1 Q
- Chat Summary: 0.5 Q
- Q-to-Q: 0.5 Q
- Business Agent: 5 Q
- Suggest Reply: 0.20 Q
- Smart Memory: 0.20 Q
- Voice Transcription: 0.25 Q
- Document Analysis: 2 Q
- Q Predict Analysis: 1 Q
- AUTO Message: 0 Q

The global charging switch remains OFF by default. When ON:
1. server checks the user's main Q wallet before the AI/provider call;
2. insufficient Q blocks the paid operation;
3. Q is debited to the Profit wallet;
4. successful usage is recorded in Q Feature Usage / Q Activity;
5. if the AI operation fails after charging, the fee is refunded automatically.

Currently wired for real preflight/refund charging in this release:
- Q Chat
- Q Vision
- Trust Check
- Chat Summary
- Q-to-Q
- Business Agent
- Suggest Reply
- AUTO Message (configured 0 Q by default)

Smart Memory, Voice Transcription, Document Analysis and Q Predict Analysis have global prices/configuration ready, but should only be charged when their explicit user action path is wired/tested. They are not silently debited by unrelated actions.

Q Predict staking remains separate and already uses the main Q wallet.

## 6. Q -> USDT withdrawal

One global Master Admin switch only:
- OFF: users cannot submit withdrawals
- ON: users can submit withdrawal requests

Defaults:
- withdrawal fee: 10% of requested Q
- fee is deducted in Q
- remaining 90% Q is converted using the Q reference rate locked at submission
- minimum final payout: 10 USDT
- destination networks: TRC20 / BEP20
- gross requested Q is locked immediately in `WITHDRAWAL_RESERVE`

Manual Admin flow:
`PENDING -> APPROVED -> PAID`

Admin can also reject or mark a payout failed. Rejected/failed/cancelled requests release the locked gross Q back to the user.

On PAID:
- 10% Q fee -> Profit wallet
- net redeemed Q -> Locked Reserve (removed from active user circulation)
- final USDT transaction hash is recorded

Ledger events:
- `Q_WITHDRAWAL_LOCK`
- `Q_WITHDRAWAL_FEE`
- `Q_WITHDRAWAL_REDEEMED`
- `Q_WITHDRAWAL_REFUND`

## 7. Withdrawal Admin dashboard

Location:
`Q Admin -> Payments / USDT -> Q -> USDT Withdrawals`

Shows:
- Pending Requests
- Pending USDT Value
- Paid Today
- Fees Collected in Q
- Rejected / Failed
- USDT Sent

Filters:
- Today / Week / Month / Year / All
- status
- network
- @username

Actions according to RBAC:
- PAYMENTS READ: view details + CSV export
- PAYMENTS WRITE: approve, reject, mark failed/release, mark paid + TX hash
- PAYMENTS FULL: all above + global Q Withdrawal ON/OFF switch

Outgoing-USDT CSV export includes request/user, gross Q, fee Q, net Q, locked reference rate, USDT payout, network, destination, status, reviewer and transaction hash.

## 8. New database tables

Created automatically through SQLAlchemy `create_all`:
- `q_economy_v21074_config`
- `q_reward_cap_events`
- `q_weekly_active_claims`
- `q_package_rebuy_orders`
- `q_withdrawal_requests`
- `q_feature_pricing_meta`

No destructive migration is included.

## Stability scope

This is a backend + browser/PWA release.

It intentionally does NOT replace:
- `backend/web/v28.js`
- `backend/web/v29.js`

Do not delete those stable files from the existing repository.

The existing Android app remains API-compatible. Server-side AI charging, when enabled, is enforced for Android API calls as well, but native Android screens for Withdrawal/Rebuy are not added in this package. Test the browser/PWA flow first before a native Android UI patch.
