# LEMMIQ V2.8 — Q Economy Beta

## Core model

- Maximum lifetime supply: **1,000,000,000 Q**
- Initial unlocked treasury: **10,000,000 Q**
- Locked reserve: **990,000,000 Q**
- Starting reference: **1 Q ≈ US$0.05**
- Cash-out: **disabled in V2.8**
- Marketplace fee default: **5% to Q PROFIT wallet**
- No Q burn in V2.8.

## Initial treasury

| System wallet | Opening Q |
|---|---:|
| USAGE_MINING | 6,000,000 |
| MARKET_REWARDS | 2,000,000 |
| REFERRALS | 1,000,000 |
| PROMOTIONS | 1,000,000 |
| PROFIT | 0 |
| ESCROW | 0 |
| LOCKED_RESERVE | 990,000,000 |

## Subscription plans

| Plan | Price | Daily package rate | 200% ceiling | Approx. days to ceiling |
|---|---:|---:|---:|---:|
| Starter | US$10 | 0.25% | US$20 | 800 |
| Plus | US$50 | 0.50% | US$100 | 400 |
| Pro | US$100 | 0.75% | US$200 | ~267 |
| Premium | US$500 | 1.00% | US$1,000 | 200 |
| Elite | US$1,000 | 1.25% | US$2,000 | 160 |

Each purchase is a separate package lot. Package accrual stops at the earlier
of the 200% package ceiling or 365-day expiry.

Daily package value is tracked in USD-equivalent micros. Q credited for an
accrual is calculated using the current Q reference price. This keeps the
package liability ceiling separate from the user's Q wallet balance.

## USDT manual verification

V2.8 supports:
- USDT TRC20
- USDT BEP20
- generic network wallets or package-specific wallets
- automatically generated wallet-address QR
- optional custom QR through the Admin API
- unique payment Order ID
- unique submitted transaction hash
- Pending / Approved / Rejected states
- manual Admin activation

No wallet private key is required or accepted.

## Q Wallet

Every user gets:
- Q balance
- USD reference display
- transaction ledger
- Basic Q daily claim
- Q transfer to another LEMMIQ username
- referral code
- package lots
- USDT payment orders

New wallets receive the configured signup Q bonus once.

## Refer & Earn

- One-level referral model.
- New account claims the referrer's code.
- One referral claim per referred account.
- Referral claim window: first 14 days.
- Referrer and referred-user rewards are configurable.
- Default: 25 Q + 25 Q.
- Funded from REFERRALS treasury.

## Q Marketplace

Users can:
- create listings;
- browse listings;
- price products/services in Q;
- see USD reference value;
- buy using Q;
- use escrow;
- accept/deliver/complete orders;
- cancel unaccepted orders;
- open disputes.

On completion, the seller receives the sale amount minus the configured
marketplace fee. The fee is transferred to the Admin PROFIT wallet.

## Admin

Master Admin is bootstrapped by environment variable:

`LEMMIQ_MASTER_ADMIN_USERNAME=<existing lemmiq username>`

Admin controls:
- Q economy overview
- reference price
- Basic Q
- signup/referral reward values
- marketplace fee
- treasury balances/transfers
- public USDT receiving wallets
- pending payment review
- package activation
- marketplace disputes
- Q ledger

All Q movements are recorded in the ledger.

## Hard safety rules

- Cash-out remains disabled.
- No endpoint mints Q above the predefined 1B genesis supply.
- Treasury moves Q between system wallets; it does not create new Q.
- Private keys/seed phrases are never stored.
- Duplicate payment transaction hashes are rejected.
- One approved payment order creates at most one subscription lot.
- Marketplace buyer funds move into ESCROW before seller payout.
