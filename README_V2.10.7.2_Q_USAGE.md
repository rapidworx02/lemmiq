# LEMMIQ V2.10.7.2 — Q Usage Analytics

Built on the working V2.10.7.1 Admin RBAC baseline.

Adds:
- Q Usage Analytics permission section (`Q_USAGE`)
- Today / 7d / 30d / 90d / 1 year / custom date filters
- username, tier and feature filters
- per-user Q/AI usage, current tier, actions/day, success/failure
- estimated provider cost, simulated Q, charged Q
- P50/P90/P95 package-planning markers
- feature totals and tier totals
- CSV export
- privacy-safe output: no message text, prompts, images or raw metadata
- AUTO Message tracked separately as `AUTO_MESSAGE`
- Suggest Reply tracked separately as `SUGGEST_REPLY`
- counts of personal/business chats with AUTO enabled

No new analytics table is required; it reads existing usage/shadow-billing tables.
Q feature charging is NOT enabled by this update.
