from __future__ import annotations

from fastapi import HTTPException

ACTIVE_CALL_STATES = {"calling", "ringing", "connecting", "connected"}
TERMINAL_CALL_STATES = {"declined", "ended", "missed", "failed"}
ALL_CALL_STATES = {"idle", *ACTIVE_CALL_STATES, *TERMINAL_CALL_STATES}


def normalize_call_state(value: str | None) -> str:
    state = (value or "idle").strip().lower()
    return state if state in ALL_CALL_STATES else state


def is_terminal_call_state(value: str | None) -> bool:
    return normalize_call_state(value) in TERMINAL_CALL_STATES


def can_call_transition(current: str | None, target: str | None) -> bool:
    """V2.10 terminal-state rule: terminal calls never return to an active state."""
    current_state = normalize_call_state(current)
    target_state = normalize_call_state(target)

    if current_state in TERMINAL_CALL_STATES and target_state in ACTIVE_CALL_STATES:
        return False
    if current_state == "declined" and target_state not in TERMINAL_CALL_STATES:
        return False
    if current_state == "ended" and target_state not in TERMINAL_CALL_STATES:
        return False
    return True


def require_call_transition(call_id: str, current: str | None, target: str | None) -> None:
    if not can_call_transition(current, target):
        raise HTTPException(
            status_code=409,
            detail={
                "error": "terminal_call_state",
                "call_id": call_id,
                "current_state": normalize_call_state(current),
                "requested_state": normalize_call_state(target),
            },
        )


def decline_event(call_id: str, caller_id: str | int | None = None, callee_id: str | int | None = None) -> dict:
    """Canonical realtime/FCM payload for a declined call."""
    payload = {
        "type": "call_declined",
        "call_id": str(call_id),
        "state": "declined",
        "terminal": True,
    }
    if caller_id is not None:
        payload["caller_id"] = str(caller_id)
    if callee_id is not None:
        payload["callee_id"] = str(callee_id)
    return payload
