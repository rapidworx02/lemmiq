# LEMMIQ V2.10.6 Video Call Test Checklist

Run this after the backend is live and the V2.10.6 Android APK is installed on two test accounts/devices.

## Baseline
- [ ] Existing voice call still rings, answers and ends correctly.
- [ ] Decline terminates the caller side as well as the callee side.
- [ ] A second simultaneous call attempt is rejected as Busy/Already active.

## Video start / receive
- [ ] Direct chat shows a video-call action.
- [ ] Caller can start VIDEO.
- [ ] Callee sees **Incoming video call**.
- [ ] Android camera permission is requested only when needed.
- [ ] Denying camera still fails gracefully / allows camera-off behavior rather than crashing.

## Connected video
- [ ] Local preview appears.
- [ ] Remote video appears.
- [ ] Camera off hides/stops local camera track.
- [ ] Camera on republishes/re-enables camera.
- [ ] Front/rear switch works.
- [ ] Microphone mute/unmute works.
- [ ] Speaker/audio route works.
- [ ] Bluetooth/wired audio still behaves normally when available.

## Lifecycle / cleanup
- [ ] Decline before connect fully closes call state.
- [ ] Caller hangup closes callee.
- [ ] Callee hangup closes caller.
- [ ] Camera indicator turns off after hangup.
- [ ] Microphone indicator turns off after hangup.
- [ ] Reopening a new call does not reuse stale tracks/listeners.
- [ ] Incoming call works while app is foregrounded.
- [ ] Incoming call works from background/locked state where Android permissions allow.

## History / browser
- [ ] Call history labels VIDEO vs VOICE correctly.
- [ ] Android → browser video works.
- [ ] Browser → Android video works.
- [ ] Browser camera/mic permission denial shows a usable error.

## LiveKit
No additional LiveKit project should be necessary. Confirm existing Render values remain set:
- `LIVEKIT_URL`
- `LIVEKIT_API_KEY`
- `LIVEKIT_API_SECRET`
