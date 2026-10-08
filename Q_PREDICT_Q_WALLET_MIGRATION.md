# Q Predict PC → Q migration notes

### Authoritative Q wallet
`q_user_wallets.balance_micros`

### Authoritative Q ledger
`q_ledger_entries`

### Prediction escrow
`q_system_wallets.key = PREDICT_ESCROW`

### Historical PC wallet
`q_predict_wallets` — retained for legacy history only.

### Market currency marker
`q_predict_markets.wallet_unit`

Existing markets receive `PC` once during migration. New markets are `Q`.

### No conversion
There is no `PC -> Q` balance conversion. A user with 10,000 PC and 125 Q before migration still has 125 Q after migration. Their legacy PC balance remains historical and is no longer used for new stakes.

### Atomic stake transaction
Q debit, escrow credit, position update, market pool update and trade creation share the same SQLAlchemy DB transaction. If the request fails before commit, the Q debit is rolled back with the position update.

### Q settlement
Winner payout = original stake + proportional share of losing pool - fee on profit.
VOID = original stake returned.
No winning-side participants = market treated as VOID and stakes returned.

### Compatibility
The backend returns temporary `*_pc` numeric aliases for the old browser renderer, but on Q markets those aliases carry the same Q numeric value only so the V2.10.5 UI patch can render Q correctly. They are not a second wallet.
