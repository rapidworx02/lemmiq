# LEMMIQ V2.10.7 — Web/PWA Readability Hotfix

This release is intentionally small and stability-focused on top of V2.10.6.

## Fixes
1. Q Predict market cards/charts on desktop/web
   - Forces market cards back to the dark LEMMIQ glass theme.
   - Restores readable titles, percentages, pool/predictor details and labels.
   - Prevents light-card + light-text washout.
   - Keeps YES/NO emphasis readable.
   - Adds Windows/Chrome contrast safety.

2. Chat composer on desktop/web
   - Message box now expands to use the available width.
   - Microphone, attachment, Q and Send controls are compact fixed-size buttons.
   - Removes the oversized microphone/control area seen on desktop.

3. PWA cache
   - Cache bumped to lemmiq-v2107-shell-1 so the visual fix is not hidden by an old service worker.

## Version
- Android versionCode: 57
- Android versionName: 2.10.7
- Backend/app-config: 2.10.7

No Q wallet, Q Predict settlement, LiveKit, Q Thread, video-call or database logic is changed in this hotfix.
