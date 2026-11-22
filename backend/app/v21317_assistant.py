"""LEMMIQ V2.13.17: lightweight, opt-out in-app Q digests.

No generative AI calls, no automatic push, no chat-text copying and no wallet access.
Uses one scheduler per backend process; deploy on one worker/instance only.
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func, or_, select, update
from sqlalchemy.orm import Mapped, Session, mapped_column

from .database import Base, SessionLocal
from .models import User, Chat, Message

log = logging.getLogger(__name__)


def utcnow():
    return datetime.now(timezone.utc)


def aware(v):
    if not v:
        return None
    return v if v.tzinfo is not None else v.replace(tzinfo=timezone.utc)


class QAssistantPrefs317(Base):
    __tablename__ = 'v21317_q_assistant_prefs'
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    frequency: Mapped[str] = mapped_column(String(12), default='LOW', nullable=False)
    quiet_start: Mapped[int] = mapped_column(Integer, default=22, nullable=False)
    quiet_end: Mapped[int] = mapped_column(Integer, default=8, nullable=False)
    timezone_name: Mapped[str] = mapped_column(String(64), default='UTC', nullable=False)


class QAssistantDigest317(Base):
    __tablename__ = 'v21317_q_assistant_digests'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(110), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


def unread_conversations(db: Session, uid: int) -> int:
    # A single grouped query; no private message contents or sender details are read.
    statement = (
        select(func.count(func.distinct(Chat.id)))
        .select_from(Chat)
        .join(Message, Message.chat_id == Chat.id)
        .where(or_(Chat.user1_id == uid, Chat.user2_id == uid),
               Message.sender_id != uid, Message.read_at.is_(None))
    )
    return int(db.scalar(statement) or 0)


def _quiet_hour(pref: QAssistantPrefs317 | None, now: datetime) -> bool:
    start = pref.quiet_start if pref else 22
    end = pref.quiet_end if pref else 8
    try:
        clock = now.astimezone(ZoneInfo(pref.timezone_name if pref else 'UTC')).hour
    except (ZoneInfoNotFoundError, ValueError, KeyError):
        clock = now.hour
    if start == end:
        return False
    return (start <= clock < end) if start < end else (clock >= start or clock < end)


def create_digest_if_due(db: Session, uid: int, now: datetime | None = None) -> bool:
    now = now or utcnow()
    pref = db.get(QAssistantPrefs317, uid)
    if pref and (not pref.enabled or pref.frequency == 'OFF'):
        return False
    if _quiet_hour(pref, now):
        return False
    user = db.get(User, uid)
    if user is None or (aware(user.created_at) and now - aware(user.created_at) < timedelta(hours=24)):
        return False
    last = db.scalar(select(QAssistantDigest317.created_at).where(
        QAssistantDigest317.user_id == uid).order_by(QAssistantDigest317.created_at.desc()).limit(1))
    interval = timedelta(hours=24) if pref and pref.frequency == 'DAILY' else timedelta(hours=72)
    if last and now - aware(last) < interval:
        return False
    unread = unread_conversations(db, uid)
    if unread < 1:
        return False
    db.add(QAssistantDigest317(user_id=uid, title='Your LEMMIQ catch-up',
        body=f'You have {unread} conversation{"s" if unread != 1 else ""} with unread messages. Open Unread in Chats to catch up.',
        created_at=now))
    return True


_scan_cursor_v300 = 0

def scheduled_scan() -> int:
    global _scan_cursor_v300
    # Bounded rotating batch; deployment remains single worker.
    with SessionLocal() as db:
        ids = db.scalars(select(User.id).where(User.id > _scan_cursor_v300).order_by(User.id).limit(500)).all()
        if not ids:
            _scan_cursor_v300 = 0
            ids = db.scalars(select(User.id).order_by(User.id).limit(500)).all()
        if ids:
            _scan_cursor_v300 = int(ids[-1]) if len(ids) == 500 else 0
        sent = 0
        for uid in ids:
            try:
                from .action310 import sync_activity, reconcile_reviews
                sync_activity(db,int(uid));reconcile_reviews(db,int(uid));db.commit()
                if create_digest_if_due(db, int(uid)):
                    db.commit()
                    sent += 1
            except Exception:
                db.rollback()
                log.exception('Q assistant digest generation failed for user id %s', uid)
        return sent


def assistant_items(db: Session, uid: int) -> list[dict]:
    rows = db.scalars(select(QAssistantDigest317).where(
        QAssistantDigest317.user_id == uid).order_by(QAssistantDigest317.created_at.desc()).limit(20)).all()
    return [{
        'id': f'assistant-{x.id}', 'kind': 'ASSISTANT', 'title': x.title,
        'body': x.body, 'created_at': aware(x.created_at).isoformat(),
        'unread': x.read_at is None, 'status': 'DIGEST', 'mine': False,
        'can_respond': False, 'can_cancel': False, 'options': [],
    } for x in rows]


def mark_assistant_read(db: Session, uid: int) -> None:
    db.execute(update(QAssistantDigest317).where(
        QAssistantDigest317.user_id == uid, QAssistantDigest317.read_at.is_(None))
        .values(read_at=utcnow()))


class PrefsInput317(BaseModel):
    enabled: bool = True
    frequency: str = Field(default='LOW', max_length=12)
    quiet_start: int = Field(default=22, ge=0, le=23)
    quiet_end: int = Field(default=8, ge=0, le=23)
    timezone_name: str = Field(default='UTC', max_length=64)


def prefs_json(p):
    return dict(enabled=p.enabled if p else True,
                frequency=p.frequency if p else 'LOW',
                quiet_start=p.quiet_start if p else 22,
                quiet_end=p.quiet_end if p else 8,
                timezone_name=p.timezone_name if p else 'UTC',
                push_enabled=False)


def register_v21317_assistant(app, current_user, get_db):
    router = APIRouter(prefix='/v21317/q', tags=['LEMMIQ Q assistant preferences'])

    @router.get('/preferences')
    def get_preferences(u: User = Depends(current_user), db: Session = Depends(get_db)):
        return prefs_json(db.get(QAssistantPrefs317, u.id))

    @router.put('/preferences')
    def put_preferences(body: PrefsInput317, u: User = Depends(current_user), db: Session = Depends(get_db)):
        if body.frequency not in ('OFF', 'LOW', 'DAILY'):
            raise HTTPException(422, 'Frequency must be OFF, LOW or DAILY')
        try:
            ZoneInfo(body.timezone_name)
        except (ZoneInfoNotFoundError, ValueError, KeyError):
            raise HTTPException(422, 'Invalid timezone')
        pref = db.get(QAssistantPrefs317, u.id)
        if pref is None:
            pref = QAssistantPrefs317(user_id=u.id)
            db.add(pref)
        pref.enabled = body.enabled
        pref.frequency = body.frequency
        pref.quiet_start = body.quiet_start
        pref.quiet_end = body.quiet_end
        pref.timezone_name = body.timezone_name
        db.commit()
        return prefs_json(pref)

    @router.get('/catch-up')
    def manual_catchup(u: User = Depends(current_user), db: Session = Depends(get_db)):
        count = unread_conversations(db, u.id)
        return {'unread_conversations': count, 'title': 'Your LEMMIQ catch-up',
                'body': f'You have {count} conversation{"s" if count != 1 else ""} with unread messages.' if count else 'You are caught up on personal conversations.'}

    app.include_router(router)

    async def _periodic():
        await asyncio.sleep(60)
        while True:
            try:
                await asyncio.to_thread(scheduled_scan)
            except Exception:
                log.exception('Q assistant scheduled scan failed')
            await asyncio.sleep(3600)

    @app.on_event('startup')
    async def start_q_assistant_317():
        if os.getenv('LEMMIQ_Q_ASSISTANT_SCHEDULER_ENABLED', 'true').lower() not in ('0', 'false', 'off'):
            app.state.v21317_assistant_task = asyncio.create_task(_periodic())

    @app.on_event('shutdown')
    async def stop_q_assistant_317():
        task = getattr(app.state, 'v21317_assistant_task', None)
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
# V300_INSTALLED
