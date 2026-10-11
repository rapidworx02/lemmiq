# LEMMIQ V2.10.7.1 — Admin Permissions / True Read-Only

Built directly on the stable V2.10.7 backend.

## Security changes
- MASTER_ADMIN is the only role that can grant or change admin access.
- Master Admin searches a normal LEMMIQ account by @username.
- Each admin section gets NONE / READ / WRITE / FULL.
- READ_ONLY is hard-capped to READ on the server. Even if a database row says WRITE/FULL, mutations are rejected.
- Backend permissions are authoritative; hiding buttons is only a UX layer.
- Existing legacy admin roles keep conservative compatibility defaults until Master Admin explicitly saves a section matrix.
- Permission changes are written to the existing Q Admin audit log.
- MASTER_ADMIN cannot be granted, demoted or disabled from the delegated-access editor.

## Sections
- Overview & Analytics
- Users & Packages
- Q Economy & Treasury
- Q Feature Pricing
- Q Predict
- Q Marketplace
- Payments / USDT
- Packages & Referrals
- Audit Logs
- System / Q Settings
- Admin Team & Roles — Master only

## Permission meaning
- NONE: no section access
- READ: view only
- WRITE: normal operational changes
- FULL: high-risk/destructive/config actions

Examples:
- Payments WRITE: approve/reject submitted payments
- Payments FULL: also manage receiving wallets/QR
- Users WRITE: pause/resume packages
- Users FULL: wallet corrections and stop/cancel packages
- Q Predict WRITE: draft/publish markets
- Q Predict FULL: resolve/void/settle and change Predict config
- Q Economy FULL: treasury transfer
- System Settings FULL: global Q/settings changes

## Scope
This patch intentionally does NOT add:
- Q Usage Analytics
- AUTO Message analytics
- wallet QR redesign
- stuck-call recovery

Those remain separate updates so the stable V2.10.7 baseline is easier to protect.
