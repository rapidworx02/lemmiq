# LEMMIQ V2.10.4

V2.10.4 is built on the integrated V2.10.3 Android/PWA source.

## Android changes

- **Q Today details**: Today is now tappable/expandable instead of showing only counts. It exposes detailed `Needs reply`, `Follow-ups due` and `Promises` items when the existing server data contains them.
- **Q Predict analysis reliability**: analysis now has a 55-second timeout, explicit error/retry state, empty-result handling, and cannot remain stuck on `Q is analysing…` indefinitely.
- **Saved Q Predict analysis history**: every successful market analysis is versioned and saved per logged-in Android user. Opening the market restores the latest analysis without another AI call. Q Personal Assistant now has a `Q Predict analyses` history section.
- **Q Economy Activity**: new `Activity` tab with All / Incoming / Outgoing filters, incoming/outgoing totals, feature usage visibility and 0 Q usage display.
- **Tier feature pricing DTO support**: client models understand feature/tier pricing returned by the new backend.
- **Q Predict uses Q terminology and the main Q balance**: separate PC wallet is removed from the active Android UX. Legacy PC values are shown only as `legacy PC` for old historical records.
- **Safe migration rule**: legacy Predict Credits are never converted into real Q.
- **New Q Predict stake endpoint**: Android sends `amount_q` to `/v2104/predict/markets/{id}/stake`. New staking is disabled unless the server explicitly reports `real_q_enabled=true`.

## Backend files

- `backend/app/v2104_q_features.py`
  - backend-controlled Q feature pricing by tier
  - every seeded feature/tier defaults to 0 Q
  - global feature charging switch defaults OFF
  - Master Admin API can edit pricing/tier rules later without app releases
  - feature usage table records quoted/charged cost and status
- `backend/app/v2104_q_predict_contract.py`
  - Q-wallet stake/payout/refund transaction contract
  - limits and fee controls
  - never maps legacy PC to Q
- `backend/app/v2104_predict_router.py`
  - new Q-stake route and status route
  - requires wiring to the existing V2.8 Q wallet + V2.9 market repository before enabling
- `q_feature_defaults_v2104.json`
  - human-readable zero-cost defaults

## Browser/PWA

- New Q Economy `Activity` tab based on the existing `/v28/wallet/ledger`.
- Incoming / outgoing / 0-Q feature usage filtering.
- V2.10.4 cache bump and additive CSS/JS.
- Q Predict static page language is updated toward the shared Q wallet. The existing `v29.js` should be updated server-side together with the Q Predict Q-wallet backend before enabling real Q staking in browser/PWA.

## Version

- Android `versionCode = 54`
- Android `versionName = 2.10.4`
