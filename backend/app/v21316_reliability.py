"""LEMMIQ V2.13.16 reliability: ephemeral WebSocket tickets, private DM thumbnails,
small authenticated Q Predict admin QR metadata. No changes to wallet, payment or Q ledger.

Tickets are intentionally stored in the current process; use ONE backend instance/worker.
Before horizontal scaling, replace this state with a shared atomic TTL store (e.g. Redis).
"""
from __future__ import annotations
import base64
import hashlib
import io
import os
import secrets
import threading
import time
from collections import OrderedDict
from datetime import datetime, timezone
from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response, JSONResponse
from sqlalchemy.orm import Session

from .models import User, Message, MessageMeta, MessageHidden, MessageAttachment
from . import media_store
from .v21312_predict_q_qr import PredictQrReference, _make_png, _active_treasury
from .v21310_predict_q import _admin

_TICKET_TTL_SECONDS = 30.0
_MAX_TICKETS = 2000
_lock = threading.Lock()
_tickets: OrderedDict[str, tuple[int, float]] = OrderedDict()


def _digest(raw: str) -> str:
    return hashlib.sha256(raw.encode('ascii')).hexdigest()


def issue_ws_ticket(uid: int) -> str:
    """Use unpredictable one-use ticket instead of a login JWT in an access-log URL."""
    raw = secrets.token_urlsafe(36)
    expiry = time.monotonic() + _TICKET_TTL_SECONDS
    with _lock:
        now = time.monotonic()
        for key, (_, expires) in list(_tickets.items()):
            if expires <= now:
                _tickets.pop(key, None)
        while len(_tickets) >= _MAX_TICKETS:
            _tickets.popitem(last=False)
        _tickets[_digest(raw)] = (uid, expiry)
    return raw


def redeem_ws_ticket(raw: str | None) -> int | None:
    """Consume ticket before websocket accept. Replay always fails."""
    if not raw or len(raw) > 128:
        return None
    try:
        key = _digest(raw)
    except UnicodeEncodeError:
        return None
    with _lock:
        data = _tickets.pop(key, None)
    return data[0] if data is not None and data[1] > time.monotonic() else None


def _check_admin(db: Session, u: User):
    _admin(db, u)


def register_v21316_reliability(app, current_user, get_db):
    router = APIRouter(prefix='/v21316', tags=['LEMMIQ V2.13.16 reliability'])

    @router.post('/ws-ticket')
    def ws_ticket(u: User = Depends(current_user)):
        ticket = issue_ws_ticket(u.id)
        return JSONResponse({'ticket': ticket, 'expires_in_seconds': int(_TICKET_TTL_SECONDS)},
                            headers={'Cache-Control': 'no-store'})

    @router.get('/media/thumb/{mid}')
    def direct_thumbnail(mid: int, u: User = Depends(current_user),
                         db: Session = Depends(get_db)):
        # Match the private direct-message membership boundary; no public media URLs.
        msg = db.get(Message, mid)
        if not msg:
            raise HTTPException(404, 'Photo unavailable')
        from .models import Chat
        chat = db.get(Chat, msg.chat_id)
        if not chat or u.id not in (chat.user1_id, chat.user2_id):
            raise HTTPException(404, 'Photo unavailable')
        # Legacy paid Q Creator chat content remains inside Professional Inbox.
        from .v2134_professional import is_legacy_paid_thread
        if is_legacy_paid_thread(db, msg.chat_id):
            raise HTTPException(404, 'Photo unavailable')
        if db.get(MessageHidden, {'message_id': mid, 'user_id': u.id}):
            raise HTTPException(404, 'Photo unavailable')
        meta = db.get(MessageMeta, mid)
        if meta and meta.deleted_for_everyone:
            raise HTTPException(404, 'Photo unavailable')
        attachment = db.get(MessageAttachment, mid)
        if not attachment or not attachment.object_key or not (
            attachment.kind == 'PHOTO' or
            (attachment.mime_type or '').lower().startswith('image/') or
            (attachment.original_name or '').lower().endswith(('.jpg','.jpeg','.png','.webp'))
        ):
            raise HTTPException(404, 'Photo unavailable')
        data = media_store.thumbnail(attachment.object_key)
        return Response(data, media_type='image/webp', headers={
            'Cache-Control':'private, max-age=3600',
            'X-Content-Type-Options':'nosniff',
            'Vary':'Authorization',
        })

    @router.get('/predict/qr/admin/{network}/summary')
    def qr_summary(network: str, u: User = Depends(current_user),
                   db: Session = Depends(get_db)):
        _check_admin(db, u)
        treasury = _active_treasury(db, network)
        saved = db.get(PredictQrReference, network)
        valid = bool(saved and saved.receiving_address == treasury.address)
        return JSONResponse({
            'network':network, 'receiving_address':treasury.address,
            'checkout_qr_png_b64': _make_png(treasury.address),
            'has_custom_reference': valid,
            'custom_qr_used_for_checkout':False,
        }, headers={'Cache-Control':'no-store'})

    @router.get('/predict/qr/admin/{network}/reference')
    def qr_reference(network: str, u: User = Depends(current_user),
                     db: Session = Depends(get_db)):
        _check_admin(db, u)
        treasury = _active_treasury(db, network)
        saved = db.get(PredictQrReference, network)
        if not saved or saved.receiving_address != treasury.address:
            raise HTTPException(404, 'No current QR reference')
        try:
            data = base64.b64decode(saved.png_b64, validate=True)
        except Exception:
            raise HTTPException(422, 'Corrupt QR reference')
        if len(data) > 1_000_000:
            raise HTTPException(413, 'QR reference too large')
        return Response(data, media_type='image/png',headers={
            'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff'})

    app.include_router(router)
