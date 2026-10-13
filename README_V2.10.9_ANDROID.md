# LEMMIQ V2.10.9 — Android Q Economy Integration

This release moves the Android app forward from the stable V2.10.7 Android baseline
and connects it to the working V2.10.7.4 backend/Q Economy APIs.

Android version:
- versionCode: 59
- versionName: 2.10.9

## Why this is a full android/app overlay

The stable V2.10.7 Android app already contains the correct 6-tab navigation,
main-Q Q Predict implementation, Q Thread, notification improvements, media fixes
and LiveKit calling work. V2.10.9 is therefore packaged as a complete `android/app`
overlay rather than a few isolated Kotlin files.

This avoids accidentally mixing the new Q Economy screens with an older Android
snapshot that still has the old navigation or Predict Credits UI.

## V2.10.9 Android changes

### Q Economy
- Connects Android to `/v21074/earning-cycles`.
- Shows the unified 200% earning-cap cycle.
- Shows ACTIVE / COMPLETED package status.
- Shows earning-cap used, remaining amount and source breakdown.
- Shows qualifying rewards waiting for a future package cycle.
- Weekly Active Q status and claim action.

### Q + USDT rebuy / upgrade
- Reads live rebuy eligibility and package options from the backend.
- Same-package rebuy and upgrade flows use backend-configured Q percentages.
- User selects TRC20/BEP20.
- Shows Q applied, Q USD reference value and remaining USDT.
- Creates a hybrid payment order.
- Shows rebuy order history.
- Allows cancellation while the order is still cancellable.
- The old completed package remains in history; backend creates a new earning cycle after approval.

### Q → USDT withdrawal
- Reads the single global withdrawal ON/OFF setting.
- When OFF, Android clearly shows withdrawal is unavailable.
- When ON, user can enter Q amount, TRC20/BEP20 network and destination wallet.
- Shows fee Q, net Q and estimated USDT before submission.
- Enforces the backend minimum net payout in the UI.
- Shows withdrawal history and status.
- Pending user requests can be cancelled; backend releases the locked Q.

### AI Q charging integration
- Android loads the server-authoritative global AI Q feature catalog.
- Same global AI Q price is shown for all package tiers.
- Q home displays Q Chat / Q Vision configured costs and charging ON/OFF state.
- Q Economy shows the broader AI feature price list.
- Backend remains authoritative for charging.
- After successful Ask Q / Q Vision usage, Android refreshes the main Q wallet and Q Activity.
- Insufficient-Q errors from Q Vision are preserved instead of being hidden behind a generic Vision error.
- When backend AI charging is OFF, no AI Q debit is applied.

### Shared USDT payment QR
- Existing package/payment orders continue using the backend shared TRC20/BEP20 wallets.
- Payment QR is tappable.
- Tap opens a large full-screen QR viewer.
- Copy wallet address remains available.
- Copy payment amount and Order ID remain available.

### Calls
- Adds a compatible manual stuck-call recovery action.
- Active RINGING / CONNECTING / CONNECTED history rows can show `End stuck`.
- This uses the current backend call-end API and does NOT depend on the abandoned V2.10.8 heartbeat endpoints.
- Normal LiveKit voice/video calling remains on the stable V2.10.7 implementation.

### Navigation preserved
Exactly:
Chats · Updates · Q Economy · Q Predict · Calls · More

Q Predict remains on the main Q wallet. Do not reintroduce Predict Credits.

## Backend required

Use the working LEMMIQ V2.10.7.4 backend or later compatible backend.

## Important
This package contains the Android `app` module overlay only. Build the APK using
the existing full Android project already in your repository.
