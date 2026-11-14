"""LEMMIQ V2.12.2 — Edit with Q; authorised in-chat source photo -> private draft.

Does not change the original message, attachment, Q wallet schema or existing image-send
endpoint. New drafts use ImageDraft and are sent only by explicit POST /v212/images/{id}/send.
"""
from __future__ import annotations
import asyncio
import base64
import binascii
import io
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import ForeignKey, Integer, String, DateTime, select, func
from sqlalchemy.orm import Session, Mapped, mapped_column

from .database import Base
from .models import (User, Chat, UserBlock, Message, MessageAttachment, MessageMeta,
                     MessageHidden, LemmiqGroup, GroupMember, GroupMessage, GroupMessageAttachment)
from . import media_store
from .v212_image_gen import ImageDraft, _json, _moderate_text, _moderate_image
from .v2105_q_features import charge_feature_for_user, finish_feature_charge, _quote
from .v28 import _system_to_user

log = logging.getLogger("lemmiq.image_edit")
MAX_SOURCE_BYTES = 12 * 1024 * 1024
MAX_OUTPUT_BYTES = 15 * 1024 * 1024
PROVIDER_TIMEOUT = 150
SIZES = {"1024x1024", "1024x1536", "1536x1024"}


def utcnow():
    return datetime.now(timezone.utc)


class ImageEditOrigin(Base):
    __tablename__ = "q_image_edit_origin_v2122"
    image_id: Mapped[int] = mapped_column(ForeignKey("q_image_drafts_v212.id"), primary_key=True)
    source_kind: Mapped[str] = mapped_column(String(10))
    source_message_id: Mapped[int] = mapped_column(Integer)
    source_owner_id: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class EditIn(BaseModel):
    prompt: str = Field(min_length=5, max_length=1500)
    size: str = "1024x1024"
    source_kind: str  # direct or group
    source_message_id: int = Field(gt=0)
    request_id: str = Field(min_length=16, max_length=64)


def enabled():
    return os.getenv("LEMMIQ_IMAGE_EDIT_ENABLED", "false").strip().lower() == "true"


def configured():
    return bool(os.getenv("OPENAI_API_KEY", "").strip()) and media_store.configured()


def limits():
    try:
        n = int(os.getenv("LEMMIQ_IMAGE_EDIT_DAILY_LIMIT", "3"))
    except ValueError:
        n = 3
    return max(1, min(30, n))


def settings():
    return {"enabled": enabled(), "configured": configured(), "model": os.getenv(
        "LEMMIQ_IMAGE_EDIT_MODEL", "gpt-image-2.5-flare"), "daily_limit": limits()}


def validate(body: EditIn):
    body.prompt = body.prompt.strip()
    body.source_kind = body.source_kind.lower().strip()
    if len(body.prompt) < 5 or body.size not in SIZES or body.source_kind not in ("direct", "group"):
        raise HTTPException(422, "Invalid image-edit request")
    try:
        uuid.UUID(body.request_id)
    except (ValueError, TypeError):
        raise HTTPException(422, "request_id must be UUID")
    return body


def source_attachment(db: Session, uid: int, kind: str, mid: int):
    """Return authorised image attachment. Reject deleted/hidden or inaccessible photos."""
    if kind == "direct":
        msg = db.get(Message, mid)
        if not msg:
            raise HTTPException(404, "Chat photo not found")
        c = db.get(Chat, msg.chat_id)
        if not c or uid not in (c.user1_id, c.user2_id):
            raise HTTPException(404, "Chat photo not found")
        other = c.user2_id if c.user1_id == uid else c.user1_id
        if db.get(UserBlock, {"blocker_id": uid, "blocked_id": other}) or db.get(
                UserBlock, {"blocker_id": other, "blocked_id": uid}):
            raise HTTPException(403, "Chat unavailable")
        meta = db.get(MessageMeta, mid)
        if (meta and meta.deleted_for_everyone) or db.get(MessageHidden, {"user_id": uid, "message_id": mid}):
            raise HTTPException(404, "Chat photo unavailable")
        a = db.get(MessageAttachment, mid)
    else:
        msg = db.get(GroupMessage, mid)
        if not msg or not db.get(GroupMember, {"group_id": msg.group_id, "user_id": uid}):
            raise HTTPException(404, "Group photo not found")
        a = db.get(GroupMessageAttachment, mid)
    if not a or not a.object_key or (a.mime_type or "").lower().split(";")[0] not in (
            "image/png", "image/jpeg", "image/webp"):
        raise HTTPException(422, "Choose a posted PNG, JPEG or WebP photo")
    if a.size_bytes and a.size_bytes > MAX_SOURCE_BYTES:
        raise HTTPException(413, "Source photo is too large to edit")
    return a, msg.sender_id


def load_source(blob_key: str) -> tuple[bytes, str]:
    """Read only authenticated, server-side private object bytes; do not expose media URLs."""
    data = bytearray()
    for part in media_store.stream(blob_key):
        data.extend(part)
        if len(data) > MAX_SOURCE_BYTES:
            raise HTTPException(413, "Photo exceeds 12 MB edit limit")
    blob = bytes(data)
    if blob.startswith(b"\x89PNG\r\n\x1a\n"):
        return blob, "image/png"
    if blob.startswith(b"\xff\xd8\xff"):
        return blob, "image/jpeg"
    if len(blob) >= 12 and blob[:4] == b"RIFF" and blob[8:12] == b"WEBP":
        return blob, "image/webp"
    raise HTTPException(422, "Unsupported or invalid source photo")


def provider_edit(source: bytes, mime: str, prompt: str, size: str, user_id: int) -> bytes:
    """OpenAI Images Edit request using multipart; no client-side credentials."""
    key = os.getenv("OPENAI_API_KEY", "").strip()
    model = os.getenv("LEMMIQ_IMAGE_EDIT_MODEL", "gpt-image-2.5-flare").strip()
    quality = os.getenv("LEMMIQ_IMAGE_EDIT_QUALITY", "medium").strip()
    if not key:
        raise HTTPException(503, "Image editing provider not configured")
    ext = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}[mime]
    fields = {"model": model, "prompt": prompt, "size": size, "quality": quality,
              "output_format": "png", "n": "1", "safety_identifier": f"lemmiq-user-{user_id}"}
    try:
        with httpx.Client(timeout=httpx.Timeout(PROVIDER_TIMEOUT, connect=20)) as client:
            response = client.post("https://api.openai.com/v1/images/edits",
                headers={"Authorization": f"Bearer {key}"}, data=fields,
                files={"image": (f"source.{ext}", io.BytesIO(source), mime)})
            if response.status_code >= 400:
                log.warning("Image edit provider HTTP %d", response.status_code)
                if response.status_code in (400, 422):
                    raise HTTPException(422, "Image edit was rejected. Change prompt or source photo.")
                raise HTTPException(502, "Image edit provider unavailable")
            reply = response.json()
        blob = base64.b64decode(reply["data"][0]["b64_json"], validate=True)
    except httpx.TimeoutException:
        raise HTTPException(504, "Image editing timed out")
    except httpx.TransportError:
        raise HTTPException(502, "Could not reach image editing service")
    except (ValueError, TypeError, KeyError, IndexError, binascii.Error):
        raise HTTPException(502, "Image editing returned an invalid response")
    if not (8 <= len(blob) <= MAX_OUTPUT_BYTES) or not blob.startswith(b"\x89PNG\r\n\x1a\n"):
        raise HTTPException(502, "Edited image has invalid format or size")
    return blob


def register_v2122_image_edit(app, current_user, get_db):
    router = APIRouter(prefix="/v2122/image-edits", tags=["LEMMIQ Edit with Q"])

    @router.get("/config")
    def config(u: User = Depends(current_user), db: Session = Depends(get_db)):
        quote = _quote(db, u.id, "Q_IMAGE_EDIT")
        db.commit()
        return {**settings(), "q_price": quote["q_cost"], "charging_enabled": quote["charging_enabled"]}

    @router.post("/edit")
    async def edit(body: EditIn, u: User = Depends(current_user), db: Session = Depends(get_db)):
        body = validate(body)
        if not enabled():
            raise HTTPException(503, "Edit with Q is not enabled by the server admin")
        if not configured():
            raise HTTPException(503, "Image editing provider or media storage not configured")
        a, original_author_id = source_attachment(db, u.id, body.source_kind, body.source_message_id)
        existing = db.scalar(select(ImageDraft).where(ImageDraft.owner_id == u.id,
                             ImageDraft.request_key == body.request_id))
        if existing:
            trace = db.get(ImageEditOrigin, existing.id)
            if (trace and existing.status in ("READY", "SENT") and existing.prompt == body.prompt
                    and existing.size == body.size and trace.source_kind == body.source_kind
                    and trace.source_message_id == body.source_message_id):
                return _json(existing)
            raise HTTPException(409, "This image-edit request has already been submitted")
        await asyncio.to_thread(_moderate_text, body.prompt)
        # One user cannot create simultaneous charge reservations.
        db.execute(select(User.id).where(User.id == u.id).with_for_update()).all()
        stale = db.scalars(select(ImageDraft).join(ImageEditOrigin,
               ImageEditOrigin.image_id == ImageDraft.id).where(
               ImageDraft.owner_id == u.id, ImageDraft.status == "PENDING",
               ImageDraft.created_at < utcnow()-timedelta(minutes=15)).with_for_update()).all()
        for orphan in stale:
            if orphan.charge_micros:
                _system_to_user(db, "PROFIT", u.id, orphan.charge_micros,
                    "AI_FEATURE_REFUND", reference="Q-EDIT:"+orphan.request_key,
                    note="Expired image-edit operation")
                orphan.charge_micros = 0
            orphan.status = "FAILED"; orphan.completed_at = utcnow()
        active_edit = db.scalar(select(ImageDraft).join(ImageEditOrigin,
            ImageEditOrigin.image_id == ImageDraft.id).where(
            ImageDraft.owner_id == u.id, ImageDraft.status == "PENDING"))
        uses = int(db.scalar(select(func.count()).select_from(ImageEditOrigin).join(
            ImageDraft, ImageDraft.id == ImageEditOrigin.image_id).where(
            ImageDraft.owner_id == u.id, ImageDraft.created_at > utcnow()-timedelta(hours=24))) or 0)
        if active_edit:
            raise HTTPException(409, "Another image edit is running")
        if uses >= limits():
            raise HTTPException(429, "Daily image-edit limit reached")
        # Charge only after verification. Store PENDING row before network call.
        reservation = charge_feature_for_user(db, u.id, "Q_IMAGE_EDIT", reference="Q-EDIT:"+body.request_id)
        draft = ImageDraft(owner_id=u.id, request_key=body.request_id, prompt=body.prompt,
            size=body.size, status="PENDING", charge_micros=int(reservation.get("charged_micros") or 0))
        db.add(draft); db.flush()
        db.add(ImageEditOrigin(image_id=draft.id, source_kind=body.source_kind,
            source_message_id=body.source_message_id, source_owner_id=original_author_id))
        try:
            db.commit(); db.refresh(draft)
        except Exception:
            db.rollback()
            raise HTTPException(409, "Cannot create edit job; please retry")
        try:
            source, mime = await asyncio.to_thread(load_source, a.object_key)
            output = await asyncio.to_thread(provider_edit, source, mime, body.prompt, body.size, u.id)
            await asyncio.to_thread(_moderate_image, output)
            object_key = await asyncio.to_thread(media_store.store, output)
            draft = db.get(ImageDraft, draft.id)
            draft.object_key = object_key; draft.image_bytes = len(output)
            draft.status = "READY"; draft.completed_at = utcnow()
            finish_feature_charge(db, reservation, True,
                metadata={"feature":"Q_IMAGE_EDIT", "size":body.size,
                          "source":body.source_kind, "source_mid":body.source_message_id})
            db.commit(); db.refresh(draft)
            return _json(draft)
        except (Exception, asyncio.CancelledError) as err:
            db.rollback()
            try:
                draft = db.get(ImageDraft, draft.id)
                if draft and draft.status == "PENDING":
                    draft.status = "FAILED"; draft.completed_at = utcnow()
                    finish_feature_charge(db, reservation, False,
                        metadata={"feature":"Q_IMAGE_EDIT", "error_type":type(err).__name__})
                    draft.charge_micros = 0
                    db.commit()
            except Exception:
                db.rollback()
                log.exception("Image-edit refund needs reconciliation, request %s", body.request_id)
            if isinstance(err, asyncio.CancelledError):
                raise
            if isinstance(err, HTTPException):
                raise err
            log.exception("Edit with Q failed (request %s)", body.request_id)
            raise HTTPException(502, "Image edit failed; please try again")

    app.include_router(router)
