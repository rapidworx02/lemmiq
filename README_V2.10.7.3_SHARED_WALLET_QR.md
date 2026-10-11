# LEMMIQ V2.10.7.3 — Shared Wallet QR

Built on the working V2.10.7.2 Q Usage Analytics release.

## Main change
LEMMIQ now uses only two receiving wallets for subscription payments:

- one shared USDT TRC20 wallet
- one shared USDT BEP20 wallet

The same two addresses are used by:
- Q Starter
- Q Plus
- Q Pro
- Q Premium
- Q Elite

## QR behavior
Each shared wallet has:
- Save / Replace
- QR
- Copy address
- Upload custom QR

If no custom QR is uploaded, LEMMIQ automatically generates the QR from the wallet address.

## Existing payment history
Old package-specific wallet rows are NOT deleted.
Existing payment orders continue referencing the wallet used when the order was created.

For NEW payment orders:
1. LEMMIQ first uses the shared wallet for the selected network.
2. Until a shared wallet is configured, it safely falls back to the old package-specific wallet.

This means the update can be deployed without breaking existing payment orders.

## Admin permissions
- PAYMENTS READ: view wallet addresses, QR and copy address
- PAYMENTS FULL: save/replace shared wallets and upload custom QR
- READ_ONLY remains unable to edit

## No database migration
The existing q_payment_wallets.package_code column already supports NULL.
A NULL package_code is used to represent a shared wallet for all packages.
