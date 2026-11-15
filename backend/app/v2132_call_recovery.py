"""LEMMIQ V2.13.2: safe recovery of abandoned 1:1 call sessions.

Only the logged-in user's call records can be inspected or reset. The reset is
explicit, not a feature for ending other users' unrelated conversations.
No changes to the existing call table or secret configuration are required.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import DateTime, ForeignKey, Integer, String, or_, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from .database import Base
from .models import CallRecord, User

logger = logging.getLogger("lemmiq.call_recovery")
ACTIVE = ("RINGING", "CONNECTING", "CONNECTED")


def utcnow():
    return datetime.now(timezone.utc)


def aware(value):
    """SQLite may return naive UTC datetime; PostgreSQL normally returns aware."""
    if value is None:
        return utcnow()
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


class CallRecoveryAuditV2132(Base):
    __tablename__ = "v2132_call_recovery_audit"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    call_id: Mapped[str] = mapped_column(String(64), index=True)
    action: Mapped[str] = mapped_column(String(24))
    prior_status: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ResetInput(BaseModel):
    confirm: bool = False


def my_calls(db, uid: int, lock: bool = False):
    stmt = select(CallRecord).where(
        or_(CallRecord.caller_id == uid, CallRecord.callee_id == uid),
        CallRecord.status.in_(ACTIVE),
    ).order_by(CallRecord.started_at.desc())
    if lock:
        stmt = stmt.with_for_update()
    return db.scalars(stmt).all()


def as_public_call(db, rec, uid: int):
    other_id = rec.callee_id if rec.caller_id == uid else rec.caller_id
    other = db.get(User, other_id)
    return {
        "id": rec.id,
        "status": rec.status,
        "call_type": rec.call_type or "VOICE",
        "chat_id": rec.chat_id,
        "peer_display_name": other.display_name if other else "LEMMIQ user",
        "started_at": aware(rec.started_at).isoformat(),
    }


def mark_terminal(db, rec, actor: int, action: str, final_status: str):
    if rec.status not in ACTIVE:
        return False
    db.add(CallRecoveryAuditV2132(
        actor_id=actor, call_id=rec.id, action=action,
        prior_status=rec.status,
    ))
    rec.status = final_status
    rec.ended_at = utcnow()
    return True


async def live_rooms(names: list[str]):
    """Returns present room names, or None if LiveKit is unreachable.

    NEVER clear a call just because the room service request failed.
    """
    if not names or not all(os.getenv(k) for k in ("LIVEKIT_URL", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET")):
        return None
    try:
        from livekit import api
        async with api.LiveKitAPI() as lk:
            result = await lk.room.list_rooms(api.ListRoomsRequest(names=names))
            return {room.name for room in result.rooms}
    except Exception as exc:
        logger.warning("LiveKit stale-call check unavailable: %s", exc)
        return None


async def delete_rooms(names: list[str]):
    """LiveKit DeleteRoom disconnects participants, unlike a DB status reset alone."""
    if not names:
        return []
    errors = []
    try:
        from livekit import api
        async with api.LiveKitAPI() as lk:
            for name in names:
                try:
                    await lk.room.delete_room(api.DeleteRoomRequest(room=name))
                except Exception as exc:
                    # A room may already be absent; preserve the authoritative DB reset.
                    logger.warning("Unable to terminate LiveKit room %s: %s", name, exc)
                    errors.append(name)
    except Exception as exc:
        logger.warning("LiveKit room teardown unavailable: %s", exc)
        errors.extend(names)
    return errors


async def notify_ended(rows, push):
    for call in rows:
        for uid in (call.caller_id, call.callee_id):
            try:
                await push(uid, {
                    "type": "call_ended", "call_id": call.id,
                    "status": call.status, "reason": "call_recovery",
                })
            except Exception as exc:
                logger.warning("Unable to notify user %s for call recovery: %s", uid, exc)


def register_v2132_call_recovery(app, current_user, get_db, push):
    router = APIRouter(prefix="/v2132/calls", tags=["LEMMIQ V2.13.2 Call Recovery"])

    @router.get("/active")
    def active(u: User = Depends(current_user), db: Session = Depends(get_db)):
        rows = my_calls(db, u.id)
        return {"active_count": len(rows), "active": [as_public_call(db, x, u.id) for x in rows]}

    @router.post("/reconcile")
    async def reconcile(u: User = Depends(current_user), db: Session = Depends(get_db)):
        """Automatically resolve records that are provably stale.

        Old RINGING/CONNECTING calls expire. A CONNECTED call is only cleared
        early after LiveKit positively reports its room absent (90-second grace).
        If LiveKit is unreachable, preserve recent CONNECTED records.
        """
        db.execute(select(User.id).where(User.id == u.id).with_for_update()).all()
        rows = my_calls(db, u.id, lock=True)
        now = utcnow()
        potentially_absent = [x for x in rows if x.status == "CONNECTED"
                              and now - aware(x.started_at) >= timedelta(seconds=90)]
        rooms = await live_rooms([x.room_name for x in potentially_absent])
        resolved = []
        for x in rows:
            age = now - aware(x.started_at)
            reason = None
            status = "ENDED"
            if x.status == "RINGING" and age >= timedelta(minutes=2):
                reason, status = "AUTO_RING_TIMEOUT", "MISSED"
            elif x.status == "CONNECTING" and age >= timedelta(minutes=3):
                reason = "AUTO_CONNECT_TIMEOUT"
            elif x.status == "CONNECTED" and age >= timedelta(hours=6):
                reason = "AUTO_MAX_AGE"
            elif x.status == "CONNECTED" and rooms is not None and x.room_name not in rooms and age >= timedelta(seconds=90):
                reason = "AUTO_ROOM_ABSENT"
            if reason and mark_terminal(db, x, u.id, reason, status):
                resolved.append(x)
        db.commit()
        await notify_ended(resolved, push)
        current = my_calls(db, u.id)
        return {"ok": True, "resolved_count": len(resolved),
                "active_count": len(current), "active": [as_public_call(db, x, u.id) for x in current]}

    @router.post("/reset")
    async def reset(body: ResetInput, u: User = Depends(current_user), db: Session = Depends(get_db)):
        if not body.confirm:
            raise HTTPException(422, "Confirm that all your LEMMIQ calls should be ended")
        # Same user row lock used by v24/calls/start; prevents a new start racing a reset.
        db.execute(select(User.id).where(User.id == u.id).with_for_update()).all()
        rows = my_calls(db, u.id, lock=True)
        changed = []
        for x in rows:
            final = "MISSED" if x.status == "RINGING" else "ENDED"
            if mark_terminal(db, x, u.id, "USER_FORCE_RESET", final):
                changed.append(x)
        db.commit()
        await notify_ended(changed, push)
        errors = await delete_rooms(list({x.room_name for x in changed}))
        return {"ok": True, "ended_count": len(changed),
                "livekit_teardown_failed": bool(errors),
                "message": "Call status reset. Any connected peer will be disconnected."
                           if changed else "No active server calls were found."}

    app.include_router(router)
