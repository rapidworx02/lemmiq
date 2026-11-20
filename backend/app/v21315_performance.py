"""LEMMIQ 2.13.15 — read-only, bounded chat/message APIs.

Batched metadata removes N+1 queries. Old routes remain intact for older clients.
No schema, payment, wallet, identity or creator permission changes.
"""
from __future__ import annotations

import hashlib
from collections import defaultdict
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import bindparam, func, inspect, or_, select, text
from sqlalchemy.orm import Session

from .models import (
    User, Chat, ChatSetting, ChatPreference, Message, MessageMeta, MessageAttachment,
    MessageReaction, MessageHidden, VoiceNote,
)


def _user_json(u: User):
    version = hashlib.sha256((u.avatar or '').encode('utf-8')).hexdigest()[:12] if u.avatar else None
    return {
        'id': u.id, 'username': u.username, 'display_name': u.display_name,
        'avatar': u.avatar,
        'avatar_url': f'/v24/profile/avatar/{u.id}?v={version}' if u.avatar else None,
        'avatar_version': version,
    }


def _legacy_paid_chat_ids(db: Session, chat_ids: list[int]) -> set[int]:
    if not chat_ids or not inspect(db.get_bind()).has_table('v2133_creator_chat_passes'):
        return set()
    stmt = text('SELECT DISTINCT chat_id FROM v2133_creator_chat_passes WHERE chat_id IN :ids')
    stmt = stmt.bindparams(bindparam('ids', expanding=True))
    return {int(r[0]) for r in db.execute(stmt, {'ids': chat_ids}).all()}


def _chat_list(db: Session, uid: int) -> list[dict]:
    chats = db.scalars(
        select(Chat).where(or_(Chat.user1_id == uid, Chat.user2_id == uid))
        .order_by(Chat.updated_at.desc())
    ).all()
    if not chats:
        return []
    ids = [c.id for c in chats]
    # Keep old professional paid chats separate from private direct messages.
    excluded = _legacy_paid_chat_ids(db, ids)
    chats = [c for c in chats if c.id not in excluded]
    if not chats:
        return []
    ids = [c.id for c in chats]
    other_ids = {(c.user2_id if c.user1_id == uid else c.user1_id) for c in chats}
    users = {x.id: x for x in db.scalars(select(User).where(User.id.in_(other_ids))).all()}
    settings = {x.chat_id: x for x in db.scalars(
        select(ChatSetting).where(ChatSetting.user_id == uid, ChatSetting.chat_id.in_(ids))
    ).all()}
    preferences = {x.chat_id: x for x in db.scalars(
        select(ChatPreference).where(ChatPreference.user_id == uid, ChatPreference.chat_id.in_(ids))
    ).all()}

    hidden = select(MessageHidden.message_id).where(MessageHidden.user_id == uid)
    # A single window query finds the latest visible message for every chat.
    ranked = select(
        Message.id.label('message_id'), Message.chat_id.label('chat_id'),
        func.row_number().over(partition_by=Message.chat_id, order_by=Message.id.desc()).label('rn'),
    ).where(Message.chat_id.in_(ids), ~Message.id.in_(hidden)).subquery()
    last_ids = select(ranked.c.message_id).where(ranked.c.rn == 1)
    last_messages = {m.chat_id: m for m in db.scalars(select(Message).where(Message.id.in_(last_ids))).all()}
    lm_ids = [x.id for x in last_messages.values()]
    meta = {x.message_id: x for x in db.scalars(
        select(MessageMeta).where(MessageMeta.message_id.in_(lm_ids))
    ).all()} if lm_ids else {}
    unread = dict(db.execute(
        select(Message.chat_id, func.count(Message.id))
        .where(Message.chat_id.in_(ids), Message.sender_id != uid,
               Message.read_at.is_(None), ~Message.id.in_(hidden))
        .group_by(Message.chat_id)
    ).all())

    result = []
    for c in chats:
        oid = c.user2_id if c.user1_id == uid else c.user1_id
        other = users.get(oid)
        if other is None:
            continue
        s = settings.get(c.id)
        p = preferences.get(c.id)
        last = last_messages.get(c.id)
        m = meta.get(last.id) if last else None
        if last:
            preview = ('This message was deleted' if m and m.deleted_for_everyone
                       else (m.edited_text if m and m.edited_text is not None else last.text) or '')
        else:
            preview = None
        result.append({
            'id': c.id, 'other_user': _user_json(other),
            'category': s.category if s else 'FRIEND',
            'ai_mode': s.ai_mode if s else 'ASSIST',
            'tone': s.tone if s else 'Natural',
            'last_message': preview,
            'updated_at': c.updated_at.isoformat(),
            'unread': int(unread.get(c.id, 0)),
            'pinned': bool(p.pinned) if p else False,
            'archived': bool(p.archived) if p else False,
            'favourite': bool(p.favourite) if p else False,
            'muted_until': p.muted_until.isoformat() if p and p.muted_until else None,
            'draft_text': p.draft_text if p else '',
        })
    return result


def _message_page(db: Session, cid: int, uid: int, limit: int, before: int | None) -> list[dict]:
    chat = db.get(Chat, cid)
    if not chat or uid not in (chat.user1_id, chat.user2_id):
        raise HTTPException(404, 'Chat not found')
    if cid in _legacy_paid_chat_ids(db, [cid]):
        raise HTTPException(410, 'Legacy paid creator chat moved to Professional Inbox. No personal chat access.')

    hidden = select(MessageHidden.message_id).where(MessageHidden.user_id == uid)
    query = select(Message).where(Message.chat_id == cid, ~Message.id.in_(hidden))
    if before is not None and before > 0:
        query = query.where(Message.id < before)
    rows = list(reversed(db.scalars(query.order_by(Message.id.desc()).limit(min(max(limit, 1), 100))).all()))
    if not rows:
        return []
    ids = [m.id for m in rows]
    meta = {x.message_id: x for x in db.scalars(
        select(MessageMeta).where(MessageMeta.message_id.in_(ids))
    ).all()}
    attachments = {x.message_id: x for x in db.scalars(
        select(MessageAttachment).where(MessageAttachment.message_id.in_(ids))
    ).all()}
    voice_ids = [x.message_id for x in attachments.values() if x.kind == 'VOICE']
    voices = {x.message_id: x for x in db.scalars(
        select(VoiceNote).where(VoiceNote.message_id.in_(voice_ids))
    ).all()} if voice_ids else {}
    reactions: dict[int, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
    for reaction in db.scalars(select(MessageReaction).where(MessageReaction.message_id.in_(ids))).all():
        reactions[reaction.message_id][reaction.emoji].append(reaction.user_id)
    parent_ids = {x.reply_to_message_id for x in meta.values() if x.reply_to_message_id is not None}
    parents = {x.id: x for x in db.scalars(select(Message).where(Message.id.in_(parent_ids))).all()} if parent_ids else {}
    parent_meta = {x.message_id: x for x in db.scalars(
        select(MessageMeta).where(MessageMeta.message_id.in_(parent_ids))
    ).all()} if parent_ids else {}
    result = []
    for m in rows:
        md = meta.get(m.id)
        deleted = bool(md and md.deleted_for_everyone)
        effective_text = 'This message was deleted' if deleted else (
            (md.edited_text if md and md.edited_text is not None else m.text) or ''
        )
        att = None if deleted else attachments.get(m.id)
        v = voices.get(m.id) if att and att.kind == 'VOICE' else None
        parent = parents.get(md.reply_to_message_id) if md and md.reply_to_message_id else None
        pm = parent_meta.get(parent.id) if parent else None
        reply = None
        if parent:
            ptext = ('This message was deleted' if pm and pm.deleted_for_everyone
                     else (pm.edited_text if pm and pm.edited_text is not None else parent.text) or '')
            reply = {'id': parent.id, 'sender_id': parent.sender_id, 'text': ptext[:300]}
        result.append({
            'id': m.id, 'chat_id': m.chat_id, 'sender_id': m.sender_id,
            'text': effective_text,
            'created_at': m.created_at.isoformat(),
            'read_at': m.read_at.isoformat() if m.read_at else None,
            'ai_generated': m.ai_generated,
            'edited_at': md.edited_at.isoformat() if md and md.edited_at else None,
            'deleted_for_everyone': deleted,
            'reply_to_message_id': md.reply_to_message_id if md else None,
            'attachment': ({
                'kind': att.kind, 'name': att.original_name,
                'mime_type': att.mime_type, 'size_bytes': att.size_bytes,
                'media_id': att.message_id if att.object_key else None,
                'contact_name': att.contact_name, 'contact_phone': att.contact_phone,
                'duration_ms': v.duration_ms if v else None,
                'transcript': v.transcript if v else None,
            } if att else None),
            'reactions': [
                {'emoji': emoji, 'user_ids': uids, 'count': len(uids)}
                for emoji, uids in reactions[m.id].items()
            ],
            'reply_to': reply,
        })
    return result


def register_v21315_performance(app, current_user, get_db):
    router = APIRouter(prefix='/v21315', tags=['LEMMIQ fast read API'])

    @router.get('/chats')
    def chats(u: User = Depends(current_user), db: Session = Depends(get_db)):
        return _chat_list(db, u.id)

    @router.get('/chats/{cid}/messages')
    def messages(cid: int, limit: int = 60, before: int | None = None,
                 before_id: int | None = None,
                 u: User = Depends(current_user), db: Session = Depends(get_db)):
        return _message_page(db, cid, u.id, limit, before if before is not None else before_id)

    app.include_router(router)
