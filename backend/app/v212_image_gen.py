"""LEMMIQ V2.12 AI Image Generation: authenticated private drafts and chat sending.

- OFF by default via LEMMIQ_IMAGE_GEN_ENABLED.
- Q_IMAGE is in existing Q feature catalog, same global pricing/ledger/refund flow.
- Each user's own generated image is private until explicit Send.
- DB row owns idempotency, owner access, attempt limits and single send.
- Existing chat/group attachments and media_store provide private media access.
"""
from __future__ import annotations
import base64
import binascii
from datetime import datetime, timezone, timedelta
import os
import uuid
import logging
import asyncio

import httpx
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import Integer, String, DateTime, ForeignKey, select, func, UniqueConstraint
from sqlalchemy.orm import Session, Mapped, mapped_column

from .database import Base
from .models import (User, UserBlock, Chat, Message, MessageAttachment,
                     LemmiqGroup, GroupMember, GroupMessage, GroupMessageAttachment)
from . import media_store, push_service, v24
from .v2105_q_features import charge_feature_for_user, finish_feature_charge, _quote
from .v28 import _system_to_user

log = logging.getLogger("lemmiq.image_generation")

def utcnow():
    return datetime.now(timezone.utc)

class ImageDraft(Base):
    __tablename__ = "q_image_drafts_v212"
    __table_args__ = (UniqueConstraint("owner_id", "request_key", name="uq_q_image_request_v212"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    request_key: Mapped[str] = mapped_column(String(64))
    prompt: Mapped[str] = mapped_column(String(1800))
    size: Mapped[str] = mapped_column(String(24), default="1024x1024")
    status: Mapped[str] = mapped_column(String(20), default="PENDING", index=True)
    object_key: Mapped[str | None] = mapped_column(String(190), nullable=True)
    image_bytes: Mapped[int] = mapped_column(Integer, default=0)
    charge_micros: Mapped[int] = mapped_column(Integer, default=0)
    sent_kind: Mapped[str | None] = mapped_column(String(12), nullable=True)
    sent_message_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

class GenerateIn(BaseModel):
    prompt: str = Field(min_length=5, max_length=1500)
    size: str = Field(default="1024x1024")
    request_id: str = Field(min_length=16, max_length=64)

class SendIn(BaseModel):
    chat_id: int | None = None
    group_id: int | None = None

SUPPORTED_SIZES = {"1024x1024", "1024x1536", "1536x1024"}
PROVIDER_TIMEOUT_SECONDS = 125
MAX_IMAGE_BYTES = 15 * 1024 * 1024


def active():
    return os.getenv("LEMMIQ_IMAGE_GEN_ENABLED", "false").strip().lower() == "true"

def configured():
    return bool(os.getenv("OPENAI_API_KEY", "").strip()) and media_store.configured()

def _settings():
    return {"enabled": active(), "configured": configured(),
            "model": os.getenv("LEMMIQ_IMAGE_MODEL", "gpt-image-1.5"),
            "max_attempts_per_day": max(1, min(int(os.getenv("LEMMIQ_IMAGE_DAILY_LIMIT", "3")), 30)),
            "sizes": sorted(SUPPORTED_SIZES)}

def _clean_request(x: GenerateIn):
    x.prompt = x.prompt.strip()
    if len(x.prompt) < 5:
        raise HTTPException(422, "Write a more detailed image prompt")
    if x.size not in SUPPORTED_SIZES:
        raise HTTPException(422, "Unsupported image size")
    try:
        uuid.UUID(x.request_id)
    except ValueError:
        raise HTTPException(422, "request_id must be a UUID")
    return x

def _provider_post(endpoint: str, payload: dict, timeout: int) -> dict:
    """Server-only OpenAI call; no API keys ever travel to apps."""
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(503, "Image generation provider is not configured")
    try:
        with httpx.Client(timeout=httpx.Timeout(timeout, connect=15)) as client:
            response = client.post("https://api.openai.com/v1/" + endpoint,
                headers={"Authorization": f"Bearer {api_key}"}, json=payload)
            if response.status_code >= 400:
                log.warning("Image API %s returned HTTP %d", endpoint, response.status_code)
                if response.status_code in (400, 422):
                    raise HTTPException(422, "Image request was not accepted. Please adjust your prompt.")
                raise HTTPException(502, "Image provider temporarily unavailable")
            return response.json()
    except httpx.TimeoutException:
        raise HTTPException(504, "Image provider timed out")
    except (httpx.TransportError, ValueError):
        raise HTTPException(502, "Could not connect to image provider")

def _moderate_text(prompt: str):
    output = _provider_post("moderations", {"model":"omni-moderation-latest", "input":prompt}, 25)
    if not output.get("results"):
        raise HTTPException(502, "Moderation unavailable")
    if bool(output["results"][0].get("flagged")):
        raise HTTPException(422, "Prompt cannot be generated under content guidelines")

def _moderate_image(blob: bytes):
    encoded = base64.b64encode(blob).decode("ascii")
    output = _provider_post("moderations", {"model":"omni-moderation-latest", "input":[{
        "type":"image_url", "image_url":{"url":"data:image/png;base64,"+encoded}}]}, 35)
    if not output.get("results"):
        raise HTTPException(502, "Output moderation unavailable")
    if bool(output["results"][0].get("flagged")):
        raise HTTPException(422, "Generated image failed content review")

def _generate_image(prompt: str, size: str) -> bytes:
    model = os.getenv("LEMMIQ_IMAGE_MODEL", "gpt-image-1.5").strip()
    output = _provider_post("images/generations", {
        "model": model, "prompt": prompt, "size": size,
        "quality": os.getenv("LEMMIQ_IMAGE_QUALITY", "medium"),
        "output_format": "png", "n": 1
    }, PROVIDER_TIMEOUT_SECONDS)
    try:
        raw = output["data"][0]["b64_json"]
        blob = base64.b64decode(raw, validate=True)
    except (KeyError, IndexError, TypeError, ValueError, binascii.Error):
        raise HTTPException(502, "Image provider returned invalid image data")
    if not (8 <= len(blob) <= MAX_IMAGE_BYTES) or blob[:8] != b"\x89PNG\r\n\x1a\n":
        raise HTTPException(502, "Generated image has invalid format or size")
    return blob

def _json(row: ImageDraft) -> dict:
    return {"id": row.id, "prompt": row.prompt, "size": row.size, "status": row.status,
            "image_url": f"/v212/images/{row.id}/file" if row.status in ("READY","SENT") else None,
            "charged_q": round(row.charge_micros / 1000000, 6),
            "created_at": row.created_at.isoformat(), "sent_kind": row.sent_kind,
            "sent_message_id": row.sent_message_id}

def _owner(db: Session, image_id: int, uid: int) -> ImageDraft:
    row = db.get(ImageDraft, image_id)
    if not row or row.owner_id != uid:
        raise HTTPException(404, "Image not found")
    return row

def register_v212_images(app, current_user, get_db, push, msg_json, push_tokens, unread_count_for_user):
    router = APIRouter(prefix="/v212/images", tags=["LEMMIQ AI Image Generation"])

    @router.get("/config")
    def configuration(u: User = Depends(current_user), db: Session = Depends(get_db)):
        quote = _quote(db, u.id, "Q_IMAGE")
        db.commit()
        return {**_settings(), "q_price": quote["q_cost"], "charging_enabled": quote["charging_enabled"]}

    @router.get("/mine")
    def mine(u: User = Depends(current_user), db: Session = Depends(get_db)):
        rows = db.scalars(select(ImageDraft).where(ImageDraft.owner_id==u.id,
                      ImageDraft.status.in_(("READY","SENT")))
                      .order_by(ImageDraft.id.desc()).limit(30)).all()
        return [_json(x) for x in rows]

    @router.post("/generate")
    async def generate(body: GenerateIn, u: User = Depends(current_user), db: Session = Depends(get_db)):
        body = _clean_request(body)
        if not active():
            raise HTTPException(503, "AI image generation is not enabled")
        if not configured():
            raise HTTPException(503, "Image generation is not configured")
        existing = db.scalar(select(ImageDraft).where(ImageDraft.owner_id == u.id,
                             ImageDraft.request_key == body.request_id))
        if existing:
            if existing.prompt == body.prompt and existing.size == body.size and existing.status in ("READY", "SENT"):
                return _json(existing)
            raise HTTPException(409, "Request already submitted; use a new request ID")
        # Moderate before reserving/debiting Q.
        await asyncio.to_thread(_moderate_text, body.prompt)
        # Prevent concurrent reserve races on PostgreSQL. Use Postgres in production.
        db.execute(select(User.id).where(User.id == u.id).with_for_update()).all()
        # Recover orphaned pending operations after a crashed Render worker.
        # Provider timeout is <3 min; use a conservative 15 min reconciliation window.
        stale = db.scalars(select(ImageDraft).where(ImageDraft.owner_id == u.id,
            ImageDraft.status == "PENDING", ImageDraft.created_at < utcnow()-timedelta(minutes=15))
            .with_for_update()).all()
        for orphan in stale:
            if orphan.charge_micros:
                _system_to_user(db, "PROFIT", u.id, orphan.charge_micros,
                    "AI_FEATURE_REFUND", reference="Q-IMAGE:"+orphan.request_key,
                    note="Abandoned image job; automatic recovery")
                orphan.charge_micros = 0
            orphan.status = "FAILED"; orphan.completed_at = utcnow()
        existing = db.scalar(select(ImageDraft).where(ImageDraft.owner_id == u.id,
                             ImageDraft.request_key == body.request_id))
        if existing:
            raise HTTPException(409, "Request already submitted")
        attempts = int(db.scalar(select(func.count()).select_from(ImageDraft).where(
            ImageDraft.owner_id == u.id, ImageDraft.created_at > utcnow()-timedelta(hours=24))) or 0)
        pending = db.scalar(select(ImageDraft).where(ImageDraft.owner_id == u.id,
                           ImageDraft.status == "PENDING"))
        if attempts >= _settings()["max_attempts_per_day"]:
            raise HTTPException(429, "Daily image limit reached")
        if pending:
            raise HTTPException(409, "An image is already generating")
        reservation = charge_feature_for_user(db, u.id, "Q_IMAGE", reference="Q-IMAGE:"+body.request_id)
        draft = ImageDraft(owner_id=u.id, request_key=body.request_id, prompt=body.prompt,
                           size=body.size, status="PENDING", charge_micros=int(reservation.get("charged_micros") or 0))
        db.add(draft)
        try:
            db.commit(); db.refresh(draft)
        except Exception:
            db.rollback()
            raise HTTPException(409, "Could not reserve image generation request")
        try:
            blob = await asyncio.to_thread(_generate_image, body.prompt, body.size)
            await asyncio.to_thread(_moderate_image, blob)
            key = await asyncio.to_thread(media_store.store, blob)
            draft = db.get(ImageDraft, draft.id)
            draft.object_key = key; draft.image_bytes = len(blob)
            draft.status = "READY"; draft.completed_at = utcnow()
            completed = finish_feature_charge(db, reservation, True,
                metadata={"size": body.size, "model": _settings()["model"], "bytes":len(blob)})
            draft.charge_micros = int(completed.get("charged_micros") or 0)
            db.commit(); db.refresh(draft)
            return _json(draft)
        except (Exception, asyncio.CancelledError) as err:
            db.rollback()
            try:
                draft = db.get(ImageDraft, draft.id)
                if draft and draft.status == "PENDING":
                    draft.status = "FAILED"; draft.completed_at = utcnow()
                    finish_feature_charge(db, reservation, False,
                        metadata={"phase":"generate", "reason":type(err).__name__})
                    draft.charge_micros = 0
                    db.commit()
            except Exception:
                db.rollback()
                log.exception("Q refund requires administrator reconciliation for request %s", body.request_id)
            if isinstance(err, asyncio.CancelledError):
                raise
            if isinstance(err, HTTPException):
                raise err
            log.exception("Image generation failed, request %s", body.request_id)
            raise HTTPException(502, "Image generation failed; please try again")

    @router.get("/{image_id}/file")
    def file(image_id: int, u: User = Depends(current_user), db: Session = Depends(get_db)):
        row = _owner(db, image_id, u.id)
        if row.status not in ("READY", "SENT") or not row.object_key:
            raise HTTPException(404, "Image is not ready")
        return StreamingResponse(media_store.stream(row.object_key),media_type="image/png",
                                 headers={"Cache-Control":"private,no-store", "X-Content-Type-Options":"nosniff"})

    @router.post("/{image_id}/send")
    async def send(image_id: int, body: SendIn, background: BackgroundTasks,
                   u: User = Depends(current_user), db: Session = Depends(get_db)):
        if (body.chat_id is None) == (body.group_id is None):
            raise HTTPException(422, "Choose one direct chat or group")
        db.execute(select(User.id).where(User.id == u.id).with_for_update()).all()
        row = _owner(db, image_id, u.id)
        if row.status == "SENT":
            # Prevent duplicate notifications/messages on a retry.
            return {"status":"SENT", "kind":row.sent_kind, "message_id":row.sent_message_id, "duplicate":True}
        if row.status != "READY" or not row.object_key:
            raise HTTPException(409, "Image is not ready")
        now = utcnow()
        if body.chat_id is not None:
            c = db.get(Chat, body.chat_id)
            if not c or u.id not in (c.user1_id, c.user2_id):
                raise HTTPException(404, "Chat not found")
            other = c.user2_id if c.user1_id == u.id else c.user1_id
            if db.get(UserBlock,{"blocker_id":u.id,"blocked_id":other}) or db.get(UserBlock,{"blocker_id":other,"blocked_id":u.id}):
                raise HTTPException(403, "This conversation is blocked")
            m = Message(chat_id=c.id, sender_id=u.id, text="✨ Q-created image", ai_generated=True)
            c.updated_at = now
            db.add(m); db.flush()
            db.add(MessageAttachment(message_id=m.id, kind="PHOTO", object_key=row.object_key,
                original_name="LEMMIQ-Q-Image.png", mime_type="image/png", size_bytes=row.image_bytes))
            row.sent_kind = "chat"; row.sent_message_id = m.id; row.status = "SENT"
            db.commit(); db.refresh(m)
            data = msg_json(m,db)
            await push(other,{"type":"message","data":data})
            await push(u.id,{"type":"message","data":data})
            background.add_task(push_service.notify,push_tokens(db,other),u.display_name,c.id,m.text,unread_count_for_user(db,other))
        else:
            g = db.get(LemmiqGroup, body.group_id)
            if not g or not db.get(GroupMember,{"group_id":body.group_id,"user_id":u.id}):
                raise HTTPException(404, "Group not found")
            m = GroupMessage(group_id=g.id,sender_id=u.id,text="✨ Q-created image", ai_generated=True)
            g.updated_at = now
            db.add(m); db.flush()
            db.add(GroupMessageAttachment(message_id=m.id,kind="PHOTO",object_key=row.object_key,
                original_name="LEMMIQ-Q-Image.png",mime_type="image/png",size_bytes=row.image_bytes))
            row.sent_kind="group"; row.sent_message_id=m.id; row.status="SENT"
            db.commit(); db.refresh(m)
            data = v24.gmjson(db,m)
            await v24.gpush(db,g.id,{"type":"group_message","group_id":g.id,"data":data})
            for member in db.scalars(select(GroupMember).where(GroupMember.group_id==g.id,GroupMember.user_id!=u.id)).all():
                background.add_task(push_service.notify_data,push_tokens(db,member.user_id),{
                    "type":"group","group_id":g.id,"group_name":g.name,"sender_name":u.display_name,"body":m.text})
        return {"status":"SENT","kind":row.sent_kind,"message_id":row.sent_message_id,"duplicate":False}

    app.include_router(router)
