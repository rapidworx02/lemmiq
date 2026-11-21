"""LEMMIQ V2.13.18: private, attachment-preserving forwards.

Only normal chat/group messages; never copy professional/PPV objects. Object keys
stay private. New messages have their own attachments and membership boundary.
"""
from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy import select
from .models import (Chat, Message, MessageAttachment, MessageHidden, MessageMeta,
    VoiceNote, UserBlock, LemmiqGroup, GroupMember, GroupMessage,
    GroupMessageAttachment, GroupVoiceNote, ForwardedMessage)
from .v2134_professional import is_legacy_paid_thread


def unavailable():
    return HTTPException(404, 'Message unavailable for forwarding')


def direct_chat(db, cid, uid):
    c = db.get(Chat, cid)
    if not c or uid not in (c.user1_id, c.user2_id) or is_legacy_paid_thread(db, cid):
        raise unavailable()
    other = c.user2_id if uid == c.user1_id else c.user1_id
    if any(db.get(UserBlock, {'blocker_id': x, 'blocked_id': y})
           for x,y in ((uid, other), (other,uid))):
        raise HTTPException(403, 'Chat unavailable')
    return c, other


def group_chat(db, gid, uid):
    g = db.get(LemmiqGroup, gid)
    if not g or not db.get(GroupMember, {'group_id': gid, 'user_id':uid}):
        raise unavailable()
    return g


def restricted(text):
    # Existing paid offer marker is NOT a transferable attachment or message.
    return '[[QCREATORS_' in (text or '').upper()


def source_for(db, mid, uid, source_kind):
    if source_kind == 'direct':
        m = db.get(Message, mid)
        if not m: raise unavailable()
        direct_chat(db, m.chat_id, uid)
        md = db.get(MessageMeta, mid)
        if (md and md.deleted_for_everyone) or db.get(MessageHidden, {'message_id':mid,'user_id':uid}):
            raise unavailable()
        text = md.edited_text if md and md.edited_text is not None else m.text
        a = db.get(MessageAttachment, mid)
        v = db.get(VoiceNote, mid) if a and a.kind == 'VOICE' else None
    elif source_kind == 'group':
        m = db.get(GroupMessage, mid)
        if not m: raise unavailable()
        group_chat(db,m.group_id,uid)
        text = m.text
        a = db.get(GroupMessageAttachment,mid)
        v = db.get(GroupVoiceNote,mid) if a and a.kind == 'VOICE' else None
    else:
        raise HTTPException(422, 'Invalid source type')
    if restricted(m.text) or restricted(text):
        raise HTTPException(403, 'Restricted creator media cannot be forwarded')
    if a:
        # Normal uploads and generated images use private attachments/ keys.
        # Do not let paid or other object-store content cross this trust boundary.
        if a.kind not in {'PHOTO','VIDEO','FILE','VOICE','CONTACT'}:
            raise HTTPException(403, 'This attachment cannot be forwarded')
        if a.kind != 'CONTACT' and (not a.object_key or not a.object_key.startswith('attachments/')):
            raise HTTPException(403, 'This attachment cannot be forwarded')
    return text or '', a, v


def create_forwards(db, mid, uid, chat_ids, group_ids, source_kind='direct'):
    """Validate ALL destinations before writing; the caller commits once."""
    chat_ids=list(dict.fromkeys(chat_ids)); group_ids=list(dict.fromkeys(group_ids))
    if not 1 <= len(chat_ids)+len(group_ids) <= 20:
        raise HTTPException(422,'Choose between 1 and 20 conversations')
    text,a,v=source_for(db,mid,uid,source_kind)
    chats=[direct_chat(db,cid,uid) for cid in chat_ids]
    groups=[group_chat(db,gid,uid) for gid in group_ids]
    if a and a.kind=='CONTACT' and groups:
        raise HTTPException(422,'Contact cards can only be forwarded to personal chats')
    # Group uploads historically allow more MIME types. Never widen private download access.
    if a and source_kind=='group' and chats:
        mime=(a.mime_type or '').lower().split(';')[0]
        allowed={'image/jpeg','image/png','image/webp','image/gif','video/mp4','video/webm','video/quicktime',
                 'application/pdf','text/plain','text/csv','application/zip',
                 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'}
        if mime not in allowed and not (a.kind=='VOICE' and mime.startswith('audio/')):
            raise HTTPException(415,'This group attachment cannot be forwarded to a personal chat')
    now=datetime.now(timezone.utc); direct=[]; group=[]
    for c,other in chats:
        m=Message(chat_id=c.id,sender_id=uid,text=text,ai_generated=False)
        c.updated_at=now;db.add(m);db.flush()
        if a:
            db.add(MessageAttachment(message_id=m.id,kind=a.kind,object_key=a.object_key,
                original_name=a.original_name,mime_type=a.mime_type,size_bytes=a.size_bytes,
                contact_name=getattr(a,'contact_name',None),contact_phone=getattr(a,'contact_phone',None)))
        if v:
            db.add(VoiceNote(message_id=m.id,duration_ms=v.duration_ms,transcript=v.transcript,transcribed_at=v.transcribed_at))
        db.add(ForwardedMessage(kind='direct',message_id=m.id));direct.append((m,other))
    for g in groups:
        m=GroupMessage(group_id=g.id,sender_id=uid,text=text,ai_generated=False)
        g.updated_at=now;db.add(m);db.flush()
        if a:
            db.add(GroupMessageAttachment(message_id=m.id,kind=a.kind,object_key=a.object_key,
                original_name=a.original_name,mime_type=a.mime_type,size_bytes=a.size_bytes))
        if v:
            db.add(GroupVoiceNote(message_id=m.id,duration_ms=v.duration_ms,transcript=v.transcript,transcribed_at=v.transcribed_at))
        db.add(ForwardedMessage(kind='group',message_id=m.id));group.append((m,g))
    db.flush()
    return direct,group
