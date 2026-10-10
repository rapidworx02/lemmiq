# LEMMIQ V2.10.8 — Admin Safety + Q Usage + Call Recovery

Main changes:
- Fixes stale voice/video call state using client heartbeats, server stale-session reconciliation and a clear-stuck-call recovery endpoint.
- READ_ONLY admin is now server-enforced read-only.
- Master Admin can assign section-by-section NONE / READ / WRITE / FULL permissions to a selected @username.
- Detailed Q Usage Analytics by user, feature and period, including AUTO_MESSAGE separately.
- CSV export for Q usage analytics.
- All Q package TRC20/BEP20 wallet slots now expose Save/Replace, QR, Upload QR and Copy actions once an address exists.
- AUTO Message / AUTO Reply is added as a separate Q feature key and tracked at 0 Q by default.
- Carries forward V2.10.7 Q Predict contrast and web composer fixes.

Security:
UI restrictions are not the authority. V2.10.8 enforces permissions server-side for V2.8 admin endpoints.
MASTER_ADMIN bypasses section checks. READ_ONLY cannot mutate admin data.
