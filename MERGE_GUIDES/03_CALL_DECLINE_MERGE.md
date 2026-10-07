# 03 — Call decline critical fix

Add:

- `backend/app/call_state_guard_v210.py`
- `android/app/src/main/java/com/lemmiq/app/CallDeclineV210.kt`

This part needs small merges into the current V2.9 call handlers because the existing LiveKit/API objects must remain authoritative.

---

## A. Backend: make DECLINED terminal

In the backend module that changes call state, import:

```python
from .call_state_guard_v210 import (
    require_call_transition,
    decline_event,
)
```

Before every answer/connect/ringing state change:

```python
require_call_transition(str(call.id), call.state, requested_state)
```

For the decline handler, the server order must be:

```python
# 1. lock/load the call row
# 2. if already terminal, return success (idempotent)
# 3. set state = "declined"
# 4. persist/commit BEFORE sending realtime events
# 5. send decline_event(...) to the caller over your existing realtime/FCM path
# 6. invalidate/deny any later LiveKit token/connect transition for this call
```

Canonical payload:

```python
event = decline_event(
    call_id=str(call.id),
    caller_id=call.caller_id,
    callee_id=call.callee_id,
)
```

Reuse your current websocket/FCM event sender. Do not create a second push system just for V2.10.

### Required server rule

If current state is any of:

```text
declined, ended, missed, failed
```

then a later request for:

```text
calling, ringing, connecting, connected
```

must return a conflict / be ignored.

---

## B. Android `LemmiqCallActivity.kt`

Find the incoming-call **Decline** button handler. Replace the current close-only logic with the helper.

Use this shape and map the callback bodies to the existing V2.9 variables/methods in your Activity:

```kotlin
lifecycleScope.launch {
    CallDeclineV210.decline(
        callId = callId,
        stopRingingImmediately = {
            stopRingtone()              // use your existing method
        },
        backendDecline = { id ->
            api.declineCall(id)         // use your existing decline API method
        },
        disconnectRoomAndTracks = {
            // Stop mic/local tracks first if your current implementation exposes them.
            room?.disconnect()          // use your existing LiveKit room reference
        },
        releaseAudioFocus = {
            releaseCallAudioFocus()     // use your existing method
        },
        cancelTimersAndListeners = {
            cancelCallTimers()
            removeCallListeners()
        },
        stopCallForegroundService = {
            stopCallService()
        },
        closeIncomingCallUi = {
            finishAndRemoveTask()
        },
        onBackendFailure = { err ->
            Log.w("LEMMIQ_CALL", "Decline backend acknowledgement failed", err)
        }
    )
}
```

The exact V2.9 method names may differ. Keep your existing methods; only use this ordering/guard.

### Important
`markDeclined()` happens before the network call inside the helper. This is intentional: a slow network cannot allow a late answer/connect callback to resurrect the call.

---

## C. Guard answer/connect callbacks

Anywhere `LemmiqCallActivity.kt`, `LemmiqPushService.kt` or the ViewModel receives a later call event, guard it before connecting:

```kotlin
if (!CallDeclineV210.canTransition(
        callId,
        CallDeclineV210.State.RINGING,
        CallDeclineV210.State.CONNECTING
    )) {
    return
}
```

Better: pass the actual current state when your ViewModel already tracks it.

Also do a fast check:

```kotlin
if (CallDeclineV210.isTerminal(callId)) return
```

before joining a LiveKit room.

---

## D. Caller handling

When `LemmiqPushService.kt` / realtime listener receives:

```text
type = call_declined
```

it must:

1. mark call terminal locally
2. stop caller ringback tone
3. disconnect any pre-created room/tracks
4. clear call notification
5. show `Call declined`
6. leave the call screen / return to previous UI

Example first line:

```kotlin
CallDeclineV210.markDeclined(callId)
```

---

## E. Test cases — all must pass

1. callee declines while both apps are foreground
2. callee declines from incoming-call screen while app is backgrounded
3. decline from lock screen
4. app started from FCM incoming-call notification then decline
5. slow network during decline
6. user taps decline twice
7. duplicate incoming notifications arrive
8. caller connects at nearly the same moment callee declines
9. call declined, then a stale `connected` event arrives — it must be ignored
10. after decline, both users can start/receive a fresh new call normally
