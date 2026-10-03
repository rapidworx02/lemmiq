
import os
import re
import uuid
from datetime import datetime, timezone, timedelta
from typing import Callable

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select, or_, func
from sqlalchemy.orm import Session

from .models import (
    User, Message, MessageAttachment, VoiceNote,
    LemmiqGroup, GroupMember, GroupSetting, GroupRead, GroupMessage, GroupMessageAttachment, GroupVoiceNote,
    CallRecord
)
from . import media_store, push_service

router = APIRouter()

_get_db=None
_current_user=None
_push=None
_push_tokens=None
_user_json=None

def install_dependencies(get_db, current_user, push, push_tokens, user_json):
    global _get_db,_current_user,_push,_push_tokens,_user_json
    _get_db=get_db; _current_user=current_user; _push=push; _push_tokens=push_tokens; _user_json=user_json

def dep_db():
    yield from _get_db()

def dep_user(authorization: str = ""):
    # unused; routes use Depends(_current_user) installed at registration time
    raise RuntimeError

def ensure_group_member(db:Session,gid:int,uid:int):
    group=db.get(LemmiqGroup,gid)
    member=db.get(GroupMember,{"group_id":gid,"user_id":uid})
    if not group or not member:
        raise HTTPException(404,"Group not found")
    return group,member

def ensure_group_admin(db:Session,gid:int,uid:int):
    group,member=ensure_group_member(db,gid,uid)
    if member.role!="ADMIN":
        raise HTTPException(403,"Group admin required")
    return group,member

def group_attachment_json(db:Session,message_id:int):
    a=db.get(GroupMessageAttachment,message_id)
    if not a:return None
    voice=db.get(GroupVoiceNote,message_id)
    return {
        "kind":a.kind,"name":a.original_name,"mime_type":a.mime_type,"size_bytes":a.size_bytes,
        "media_id":a.message_id if a.object_key else None,
        "duration_ms":voice.duration_ms if voice else None,
        "transcript":voice.transcript if voice else None,
    }

def group_message_json(db:Session,m:GroupMessage):
    sender=db.get(User,m.sender_id)
    return {
        "id":m.id,"group_id":m.group_id,"sender_id":m.sender_id,
        "sender":_user_json(sender) if sender else None,
        "text":m.text,"created_at":m.created_at.isoformat(),
        "ai_generated":m.ai_generated,"attachment":group_attachment_json(db,m.id)
    }

def group_json(db:Session,g:LemmiqGroup,uid:int):
    members=db.scalars(
        select(GroupMember).where(GroupMember.group_id==g.id).order_by(GroupMember.joined_at.asc())
    ).all()
    setting=db.get(GroupSetting,{"group_id":g.id,"user_id":uid})
    if not setting:
        setting=GroupSetting(group_id=g.id,user_id=uid)
        db.add(setting);db.commit();db.refresh(setting)
    last=db.scalar(select(GroupMessage).where(GroupMessage.group_id==g.id).order_by(GroupMessage.id.desc()).limit(1))
    read=db.get(GroupRead,{"group_id":g.id,"user_id":uid})
    last_read=read.last_read_message_id if read else 0
    unread=int(db.scalar(select(func.count()).select_from(GroupMessage).where(
        GroupMessage.group_id==g.id,GroupMessage.id>last_read,GroupMessage.sender_id!=uid
    )) or 0)
    return {
        "id":g.id,"name":g.name,"created_by":g.created_by,"has_photo":bool(g.photo_key),
        "member_count":len(members),"role":next((m.role for m in members if m.user_id==uid),"MEMBER"),
        "ai_mode":setting.ai_mode,"tone":setting.tone,"unread":unread,
        "last_message":last.text if last else None,"updated_at":g.updated_at.isoformat(),
        "members":[{**_user_json(db.get(User,m.user_id)),"role":m.role} for m in members if db.get(User,m.user_id)]
    }

async def push_group_event(db:Session,gid:int,payload:dict,exclude_uid:int|None=None):
    members=db.scalars(select(GroupMember).where(GroupMember.group_id==gid)).all()
    for m in members:
        if exclude_uid is not None and m.user_id==exclude_uid:continue
        await _push(m.user_id,payload)

def push_group_fcm(db:Session,g:LemmiqGroup,sender:User,text:str,exclude_uid:int,background:BackgroundTasks):
    members=db.scalars(select(GroupMember).where(GroupMember.group_id==g.id)).all()
    for m in members:
        if m.user_id==exclude_uid:continue
        background.add_task(
            push_service.notify_data,_push_tokens(db,m.user_id),
            {"type":"group","group_id":g.id,"group_name":g.name,
             "sender_name":sender.display_name,"body":text[:180]}
        )

class GroupCreate(BaseModel):
    name:str=Field(min_length=1,max_length=100)
    member_ids:list[int]=Field(default_factory=list,max_length=100)

class GroupMemberIn(BaseModel):
    user_id:int

class GroupMemberRoleIn(BaseModel):
    role:str

class GroupSettingIn(BaseModel):
    ai_mode:str
    tone:str="Natural"

class TextIn(BaseModel):
    text:str=Field(min_length=1,max_length=4000)

class GroupAskIn(BaseModel):
    question:str=Field(min_length=1,max_length=1200)

@router.get("/groups")
def list_groups(u=Depends(lambda: None),db:Session=Depends(dep_db)):
    raise RuntimeError("dependency placeholder")

def register_group_routes(current_user):
    # FastAPI dependency objects must be constructed after current_user is available.
    @router.get("/v23/groups")
    def groups(u=Depends(current_user),db:Session=Depends(dep_db)):
        gids=[x.group_id for x in db.scalars(select(GroupMember).where(GroupMember.user_id==u.id)).all()]
        if not gids:return []
        rows=db.scalars(select(LemmiqGroup).where(LemmiqGroup.id.in_(gids)).order_by(LemmiqGroup.updated_at.desc())).all()
        return [group_json(db,g,u.id) for g in rows]

    @router.post("/v23/groups")
    def create_group(body:GroupCreate,u=Depends(current_user),db:Session=Depends(dep_db)):
        ids=[]
        for x in body.member_ids:
            if x!=u.id and x not in ids:ids.append(x)
        if not ids:
            raise HTTPException(400,"Choose at least one other member")
        valid=db.scalars(select(User).where(User.id.in_(ids))).all()
        if len(valid)!=len(ids):
            raise HTTPException(404,"One or more users were not found")
        g=LemmiqGroup(name=body.name.strip(),created_by=u.id)
        db.add(g);db.flush()
        db.add(GroupMember(group_id=g.id,user_id=u.id,role="ADMIN"))
        db.add(GroupSetting(group_id=g.id,user_id=u.id,ai_mode="ASSIST"))
        db.add(GroupRead(group_id=g.id,user_id=u.id,last_read_message_id=0))
        for uid in ids:
            db.add(GroupMember(group_id=g.id,user_id=uid,role="MEMBER"))
            db.add(GroupSetting(group_id=g.id,user_id=uid,ai_mode="ASSIST"))
            db.add(GroupRead(group_id=g.id,user_id=uid,last_read_message_id=0))
        db.commit();db.refresh(g)
        return group_json(db,g,u.id)

    @router.get("/v23/groups/{gid}")
    def group_detail(gid:int,u=Depends(current_user),db:Session=Depends(dep_db)):
        g,_=ensure_group_member(db,gid,u.id)
        return group_json(db,g,u.id)

    @router.get("/v23/groups/{gid}/messages")
    def group_messages(gid:int,u=Depends(current_user),db:Session=Depends(dep_db)):
        ensure_group_member(db,gid,u.id)
        rows=db.scalars(select(GroupMessage).where(GroupMessage.group_id==gid).order_by(GroupMessage.id.asc()).limit(600)).all()
        return [group_message_json(db,m) for m in rows]

    @router.post("/v23/groups/{gid}/read")
    def mark_group_read(gid:int,u=Depends(current_user),db:Session=Depends(dep_db)):
        ensure_group_member(db,gid,u.id)
        last=int(db.scalar(select(func.max(GroupMessage.id)).where(GroupMessage.group_id==gid)) or 0)
        row=db.get(GroupRead,{"group_id":gid,"user_id":u.id})
        if not row:row=GroupRead(group_id=gid,user_id=u.id,last_read_message_id=last);db.add(row)
        else:row.last_read_message_id=last
        db.commit()
        return {"ok":True,"last_read_message_id":last}

    @router.post("/v23/groups/{gid}/messages")
    async def send_group_message(gid:int,body:TextIn,background:BackgroundTasks,u=Depends(current_user),db:Session=Depends(dep_db)):
        g,_=ensure_group_member(db,gid,u.id)
        m=GroupMessage(group_id=gid,sender_id=u.id,text=body.text.strip())
        g.updated_at=datetime.now(timezone.utc)
        db.add(m);db.commit();db.refresh(m)
        data=group_message_json(db,m)
        await push_group_event(db,gid,{"type":"group_message","group_id":gid,"data":data})
        push_group_fcm(db,g,u,m.text,u.id,background)
        return data

    @router.put("/v23/groups/{gid}/settings")
    def group_settings(gid:int,body:GroupSettingIn,u=Depends(current_user),db:Session=Depends(dep_db)):
        g,_=ensure_group_member(db,gid,u.id)
        if body.ai_mode not in {"OFF","ASSIST","SUMMARY"}:
            raise HTTPException(400,"Group AI mode must be OFF, ASSIST or SUMMARY")
        s=db.get(GroupSetting,{"group_id":gid,"user_id":u.id})
        if not s:s=GroupSetting(group_id=gid,user_id=u.id);db.add(s)
        s.ai_mode=body.ai_mode;s.tone=body.tone[:40]
        db.commit()
        return group_json(db,g,u.id)

    @router.post("/v23/groups/{gid}/members")
    def add_group_member(gid:int,body:GroupMemberIn,u=Depends(current_user),db:Session=Depends(dep_db)):
        g,_=ensure_group_admin(db,gid,u.id)
        if not db.get(User,body.user_id):raise HTTPException(404,"User not found")
        if not db.get(GroupMember,{"group_id":gid,"user_id":body.user_id}):
            db.add(GroupMember(group_id=gid,user_id=body.user_id,role="MEMBER"))
            db.add(GroupSetting(group_id=gid,user_id=body.user_id,ai_mode="ASSIST"))
            db.add(GroupRead(group_id=gid,user_id=body.user_id,last_read_message_id=0))
            db.commit()
        return group_json(db,g,u.id)

    @router.put("/v23/groups/{gid}/members/{uid}")
    def group_member_role(gid:int,uid:int,body:GroupMemberRoleIn,u=Depends(current_user),db:Session=Depends(dep_db)):
        g,_=ensure_group_admin(db,gid,u.id)
        if body.role not in {"ADMIN","MEMBER"}:raise HTTPException(400,"Invalid role")
        row=db.get(GroupMember,{"group_id":gid,"user_id":uid})
        if not row:raise HTTPException(404,"Member not found")
        row.role=body.role;db.commit()
        return group_json(db,g,u.id)

    @router.delete("/v23/groups/{gid}/members/{uid}")
    def remove_group_member(gid:int,uid:int,u=Depends(current_user),db:Session=Depends(dep_db)):
        g,_=ensure_group_admin(db,gid,u.id)
        if uid==g.created_by:raise HTTPException(400,"Group creator cannot be removed")
        row=db.get(GroupMember,{"group_id":gid,"user_id":uid})
        if row:db.delete(row)
        setting=db.get(GroupSetting,{"group_id":gid,"user_id":uid})
        if setting:db.delete(setting)
        read=db.get(GroupRead,{"group_id":gid,"user_id":uid})
        if read:db.delete(read)
        db.commit()
        return {"ok":True}

    @router.post("/v23/groups/{gid}/leave")
    def leave_group(gid:int,u=Depends(current_user),db:Session=Depends(dep_db)):
        g,m=ensure_group_member(db,gid,u.id)
        if u.id==g.created_by:
            admins=db.scalars(select(GroupMember).where(GroupMember.group_id==gid,GroupMember.role=="ADMIN",GroupMember.user_id!=u.id)).all()
            if not admins:raise HTTPException(400,"Make another member admin before the creator leaves")
        db.delete(m)
        s=db.get(GroupSetting,{"group_id":gid,"user_id":u.id})
        if s:db.delete(s)
        read=db.get(GroupRead,{"group_id":gid,"user_id":u.id})
        if read:db.delete(read)
        if u.id==g.created_by:
            next_admin=db.scalar(select(GroupMember).where(GroupMember.group_id==gid,GroupMember.role=="ADMIN",GroupMember.user_id!=u.id).limit(1))
            if next_admin:g.created_by=next_admin.user_id
        db.commit()
        return {"ok":True}

    @router.post("/v23/groups/{gid}/photo")
    async def group_photo(gid:int,file:UploadFile=File(...),u=Depends(current_user),db:Session=Depends(dep_db)):
        g,_=ensure_group_admin(db,gid,u.id)
        mime=(file.content_type or "").split(";")[0].lower()
        if mime not in {"image/jpeg","image/png","image/webp"}:raise HTTPException(415,"Use JPEG, PNG or WebP")
        data=await file.read(5*1024*1024+1)
        if not data or len(data)>5*1024*1024:raise HTTPException(413,"Group photo must be 5 MB or less")
        g.photo_key=media_store.store(data);db.commit()
        return group_json(db,g,u.id)

    @router.get("/v23/groups/{gid}/photo")
    def get_group_photo(gid:int,u=Depends(current_user),db:Session=Depends(dep_db)):
        g,_=ensure_group_member(db,gid,u.id)
        if not g.photo_key:raise HTTPException(404,"Group has no photo")
        return StreamingResponse(media_store.stream(g.photo_key),media_type="image/jpeg",
            headers={"Cache-Control":"private, no-store"})

    @router.post("/v23/groups/{gid}/suggest")
    def group_suggest(gid:int,u=Depends(current_user),db:Session=Depends(dep_db)):
        g,_=ensure_group_member(db,gid,u.id)
        setting=db.get(GroupSetting,{"group_id":gid,"user_id":u.id})
        if setting and setting.ai_mode=="OFF":
            raise HTTPException(400,"Group AI is off")
        rows=db.scalars(select(GroupMessage).where(GroupMessage.group_id==gid).order_by(GroupMessage.id.desc()).limit(60)).all()[::-1]
        incoming=next((m for m in reversed(rows) if m.sender_id!=u.id),None)
        if not incoming:raise HTTPException(400,"No incoming group message")
        history=[]
        for m in rows:
            sender=db.get(User,m.sender_id)
            history.append(f"{sender.display_name if sender else 'Member'}: {m.text}")
        key=os.getenv("ANTHROPIC_API_KEY","").strip()
        if not key:return {"reply":"Got it — I’ll reply properly in a moment."}
        from anthropic import Anthropic
        prompt=f"""You are LEMMIQ Group Assist.
Group: {g.name}
Tone: {(setting.tone if setting else 'Natural')}
Recent group conversation:
{chr(10).join(history)[-16000:]}
Latest message to respond to:
{incoming.text}
Write ONE concise natural reply suitable for this group. Match the language/style. Never invent facts, commitments, money, availability or completed actions. Output only the reply."""
        msg=Anthropic(api_key=key).messages.create(
            model=os.getenv("ANTHROPIC_MODEL","claude-sonnet-4-6"),max_tokens=180,temperature=0.5,
            messages=[{"role":"user","content":prompt}]
        )
        return {"reply":"".join(x.text for x in msg.content if getattr(x,"type","")=="text").strip()}

    @router.post("/v23/groups/{gid}/summary")
    def group_summary(gid:int,u=Depends(current_user),db:Session=Depends(dep_db)):
        g,_=ensure_group_member(db,gid,u.id)
        rows=db.scalars(select(GroupMessage).where(GroupMessage.group_id==gid).order_by(GroupMessage.id.desc()).limit(160)).all()[::-1]
        if not rows:return {"summary":"No group messages yet.","decisions":[],"actions":[]}
        transcript=[]
        for m in rows:
            sender=db.get(User,m.sender_id)
            transcript.append(f"{sender.display_name if sender else 'Member'}: {m.text}")
        key=os.getenv("ANTHROPIC_API_KEY","").strip()
        if not key:
            return {"summary":f"{g.name}: {len(rows)} recent messages.","decisions":[],"actions":[]}
        from anthropic import Anthropic
        import json
        prompt=f"""You are LEMMIQ Group Q. Summarize this group conversation without inventing facts.
Return JSON only:
{{"summary":"short catch-up","decisions":["confirmed group decisions"],"actions":["clear follow-ups"]}}
Conversation:
{chr(10).join(transcript)[-22000:]}"""
        msg=Anthropic(api_key=key).messages.create(
            model=os.getenv("ANTHROPIC_MODEL","claude-sonnet-4-6"),max_tokens=700,temperature=0,
            messages=[{"role":"user","content":prompt}]
        )
        raw="".join(x.text for x in msg.content if getattr(x,"type","")=="text").strip().removeprefix("```json").removesuffix("```").strip()
        try:return json.loads(raw)
        except Exception:return {"summary":raw[:1800],"decisions":[],"actions":[]}

    @router.post("/v23/groups/{gid}/ask")
    def group_ask(gid:int,body:GroupAskIn,u=Depends(current_user),db:Session=Depends(dep_db)):
        g,_=ensure_group_member(db,gid,u.id)
        rows=db.scalars(select(GroupMessage).where(GroupMessage.group_id==gid).order_by(GroupMessage.id.desc()).limit(180)).all()[::-1]
        transcript=[]
        for m in rows:
            sender=db.get(User,m.sender_id)
            transcript.append(f"{sender.display_name if sender else 'Member'}: {m.text}")
        key=os.getenv("ANTHROPIC_API_KEY","").strip()
        if not key:return {"answer":"AI is not configured on the server.","references":[]}
        from anthropic import Anthropic
        import json
        prompt=f"""Answer ONLY from this LEMMIQ group history. If the answer is absent, say so.
QUESTION: {body.question}
GROUP HISTORY:
{chr(10).join(transcript)[-24000:]}
Return JSON only: {{"answer":"concise answer","references":["short supporting lines"]}}"""
        msg=Anthropic(api_key=key).messages.create(
            model=os.getenv("ANTHROPIC_MODEL","claude-sonnet-4-6"),max_tokens=700,temperature=0,
            messages=[{"role":"user","content":prompt}]
        )
        raw="".join(x.text for x in msg.content if getattr(x,"type","")=="text").strip().removeprefix("```json").removesuffix("```").strip()
        try:return json.loads(raw)
        except Exception:return {"answer":raw[:1800],"references":[]}

    @router.post("/v23/groups/{gid}/attachments")
    async def group_attachment(gid:int,background:BackgroundTasks,file:UploadFile=File(...),
                               u=Depends(current_user),db:Session=Depends(dep_db)):
        g,_=ensure_group_member(db,gid,u.id)
        mime=(file.content_type or "").split(";")[0].lower().strip()
        kind={
            "image/jpeg":"PHOTO","image/png":"PHOTO","image/webp":"PHOTO",
            "video/mp4":"VIDEO","video/webm":"VIDEO","video/quicktime":"VIDEO",
            "application/pdf":"FILE","text/plain":"FILE","text/csv":"FILE","application/zip":"FILE"
        }.get(mime)
        if not kind:raise HTTPException(415,"Unsupported group attachment")
        payload=await file.read(20*1024*1024+1)
        if not payload or len(payload)>20*1024*1024:raise HTTPException(413,"File must be 20 MB or less")
        key=media_store.store(payload)
        name=re.sub(r"[^A-Za-z0-9 .()\-]","_",(file.filename or "Attachment").split("/")[-1])[:190]
        m=GroupMessage(group_id=gid,sender_id=u.id,text=f"[{kind.title()}] {name}")
        g.updated_at=datetime.now(timezone.utc);db.add(m);db.flush()
        db.add(GroupMessageAttachment(message_id=m.id,kind=kind,object_key=key,original_name=name,mime_type=mime,size_bytes=len(payload)))
        db.commit();db.refresh(m)
        data=group_message_json(db,m)
        await push_group_event(db,gid,{"type":"group_message","group_id":gid,"data":data})
        push_group_fcm(db,g,u,m.text,u.id,background)
        return data

    @router.get("/v23/group-media/{message_id}")
    def group_media(message_id:int,u=Depends(current_user),db:Session=Depends(dep_db)):
        a=db.get(GroupMessageAttachment,message_id)
        m=db.get(GroupMessage,message_id)
        if not a or not m or not a.object_key:raise HTTPException(404,"Attachment not found")
        ensure_group_member(db,m.group_id,u.id)
        safe=(a.original_name or "file").replace('"',"")
        return StreamingResponse(media_store.stream(a.object_key),media_type=a.mime_type or "application/octet-stream",
            headers={"Content-Disposition":f'attachment; filename="{safe}"',"Cache-Control":"private, no-store"})

    @router.post("/v23/groups/{gid}/voice")
    async def group_voice(gid:int,background:BackgroundTasks,file:UploadFile=File(...),
                          duration_ms:int=Form(0),transcript:str=Form(""),
                          u=Depends(current_user),db:Session=Depends(dep_db)):
        g,_=ensure_group_member(db,gid,u.id)
        mime=(file.content_type or "audio/webm").split(";")[0].lower()
        if not mime.startswith("audio/"):raise HTTPException(415,"Voice note must be audio")
        payload=await file.read(12*1024*1024+1)
        if not payload or len(payload)>12*1024*1024:raise HTTPException(413,"Voice note must be 12 MB or less")
        key=media_store.store(payload)
        m=GroupMessage(group_id=gid,sender_id=u.id,text="🎙 Voice message")
        g.updated_at=datetime.now(timezone.utc);db.add(m);db.flush()
        db.add(GroupMessageAttachment(message_id=m.id,kind="VOICE",object_key=key,original_name="voice-note",mime_type=mime,size_bytes=len(payload)))
        db.add(GroupVoiceNote(message_id=m.id,duration_ms=max(0,min(duration_ms,3600000)),transcript=transcript[:12000]))
        db.commit();db.refresh(m)
        data=group_message_json(db,m)
        await push_group_event(db,gid,{"type":"group_message","group_id":gid,"data":data})
        push_group_fcm(db,g,u,"🎙 Voice message",u.id,background)
        return data

    @router.post("/v23/chats/{cid}/voice")
    async def direct_voice(cid:int,background:BackgroundTasks,file:UploadFile=File(...),
                           duration_ms:int=Form(0),transcript:str=Form(""),
                           u=Depends(current_user),db:Session=Depends(dep_db)):
        # direct membership is checked without importing main helpers
        from .models import Chat
        c=db.get(Chat,cid)
        if not c or u.id not in (c.user1_id,c.user2_id):raise HTTPException(404,"Chat not found")
        mime=(file.content_type or "audio/mp4").split(";")[0].lower()
        if not mime.startswith("audio/"):raise HTTPException(415,"Voice note must be audio")
        payload=await file.read(12*1024*1024+1)
        if not payload or len(payload)>12*1024*1024:raise HTTPException(413,"Voice note must be 12 MB or less")
        key=media_store.store(payload)
        m=Message(chat_id=cid,sender_id=u.id,text="🎙 Voice message")
        c.updated_at=datetime.now(timezone.utc);db.add(m);db.flush()
        db.add(MessageAttachment(message_id=m.id,kind="VOICE",object_key=key,original_name="voice-note",mime_type=mime,size_bytes=len(payload)))
        db.add(VoiceNote(message_id=m.id,duration_ms=max(0,min(duration_ms,3600000)),transcript=transcript[:12000]))
        db.commit();db.refresh(m)
        oid=c.user2_id if c.user1_id==u.id else c.user1_id
        # main msg_json includes VoiceNote metadata after V2.3 patch
        from .main import msg_json
        data=msg_json(m,db)
        await _push(oid,{"type":"message","data":data});await _push(u.id,{"type":"message","data":data})
        background.add_task(push_service.notify,_push_tokens(db,oid),u.display_name,cid,"🎙 Voice message",1)
        return data

    @router.post("/v23/voice/{message_id}/ai")
    def voice_ai(message_id:int,u=Depends(current_user),db:Session=Depends(dep_db)):
        from .models import Chat
        m=db.get(Message,message_id)
        if not m:raise HTTPException(404,"Voice message not found")
        c=db.get(Chat,m.chat_id)
        if not c or u.id not in (c.user1_id,c.user2_id):raise HTTPException(404,"Voice message not found")
        v=db.get(VoiceNote,message_id)
        if not v or not v.transcript.strip():
            raise HTTPException(409,"No transcript is available for this voice note yet")
        key=os.getenv("ANTHROPIC_API_KEY","").strip()
        if not key:
            return {"transcript":v.transcript,"summary":v.transcript[:300],"suggested_reply":""}
        from anthropic import Anthropic
        import json
        prompt=f"""A user received this voice-note transcript:
{v.transcript[:12000]}
Return JSON only:
{{"summary":"1-2 sentence summary","suggested_reply":"one concise natural reply matching the transcript language"}}"""
        msg=Anthropic(api_key=key).messages.create(
            model=os.getenv("ANTHROPIC_MODEL","claude-sonnet-4-6"),max_tokens=350,temperature=0.3,
            messages=[{"role":"user","content":prompt}]
        )
        raw="".join(x.text for x in msg.content if getattr(x,"type","")=="text").strip().removeprefix("```json").removesuffix("```").strip()
        try:data=json.loads(raw)
        except Exception:data={"summary":raw[:700],"suggested_reply":""}
        data["transcript"]=v.transcript
        return data

def livekit_configured():
    return bool(os.getenv("LIVEKIT_URL","").strip() and os.getenv("LIVEKIT_API_KEY","").strip() and os.getenv("LIVEKIT_API_SECRET","").strip())

def livekit_token(room_name:str,user:User):
    if not livekit_configured():
        raise HTTPException(503,"LiveKit is not configured. Add LIVEKIT_URL, LIVEKIT_API_KEY and LIVEKIT_API_SECRET on Render.")
    from livekit import api
    token=(
        api.AccessToken(os.environ["LIVEKIT_API_KEY"],os.environ["LIVEKIT_API_SECRET"])
        .with_identity(f"u_{user.id}")
        .with_name(f"u_{user.id}")
        .with_grants(api.VideoGrants(room_join=True,room=room_name,can_publish=True,can_subscribe=True))
        .with_ttl(timedelta(hours=2))
    )
    return token.to_jwt()

class CallStartIn(BaseModel):
    chat_id:int

def call_json(db:Session,c:CallRecord,uid:int):
    other_id=c.callee_id if c.caller_id==uid else c.caller_id
    other=db.get(User,other_id)
    return {"id":c.id,"chat_id":c.chat_id,"caller_id":c.caller_id,"callee_id":c.callee_id,
            "other_user":_user_json(other) if other else None,"status":c.status,
            "started_at":c.started_at.isoformat(),
            "answered_at":c.answered_at.isoformat() if c.answered_at else None,
            "ended_at":c.ended_at.isoformat() if c.ended_at else None}

def register_call_routes(current_user):
    from .models import Chat

    @router.get("/v23/calls/status")
    def calls_status(u=Depends(current_user)):
        return {"configured":livekit_configured(),"provider":"LiveKit","voice":True,"video":False}

    @router.get("/v23/calls")
    def call_history(u=Depends(current_user),db:Session=Depends(dep_db)):
        rows=db.scalars(select(CallRecord).where(or_(CallRecord.caller_id==u.id,CallRecord.callee_id==u.id)).order_by(CallRecord.started_at.desc()).limit(100)).all()
        return [call_json(db,c,u.id) for c in rows]

    @router.post("/v23/calls/start")
    async def start_call(body:CallStartIn,background:BackgroundTasks,u=Depends(current_user),db:Session=Depends(dep_db)):
        if not livekit_configured():
            raise HTTPException(503,"LiveKit is not configured. Add LIVEKIT_URL, LIVEKIT_API_KEY and LIVEKIT_API_SECRET on Render.")
        c=db.get(Chat,body.chat_id)
        if not c or u.id not in (c.user1_id,c.user2_id):raise HTTPException(404,"Chat not found")
        callee=c.user2_id if c.user1_id==u.id else c.user1_id
        call_id=uuid.uuid4().hex
        room_name="call_"+uuid.uuid4().hex
        rec=CallRecord(id=call_id,chat_id=c.id,caller_id=u.id,callee_id=callee,room_name=room_name,status="RINGING")
        db.add(rec);db.commit()
        event={"type":"incoming_call","call_id":call_id,"chat_id":c.id,"caller_name":u.display_name,"caller_id":u.id}
        await _push(callee,event)
        background.add_task(push_service.notify_data,_push_tokens(db,callee),
            {"type":"call","call_id":call_id,"chat_id":c.id,"caller_name":u.display_name,"caller_id":u.id})
        return {"call":call_json(db,rec,u.id),"ws_url":os.environ.get("LIVEKIT_URL",""),"token":livekit_token(room_name,u),"incoming":False}

    @router.post("/v23/calls/{call_id}/join")
    def join_call(call_id:str,u=Depends(current_user),db:Session=Depends(dep_db)):
        rec=db.get(CallRecord,call_id)
        if not rec or u.id not in (rec.caller_id,rec.callee_id):raise HTTPException(404,"Call not found")
        if rec.status in {"DECLINED","ENDED","MISSED"}:raise HTTPException(409,f"Call is {rec.status.lower()}")
        if u.id==rec.callee_id and rec.status=="RINGING":
            rec.status="CONNECTED";rec.answered_at=datetime.now(timezone.utc);db.commit()
        return {"call":call_json(db,rec,u.id),"ws_url":os.environ.get("LIVEKIT_URL",""),"token":livekit_token(rec.room_name,u),"incoming":u.id==rec.callee_id}

    @router.post("/v23/calls/{call_id}/decline")
    def decline_call(call_id:str,u=Depends(current_user),db:Session=Depends(dep_db)):
        rec=db.get(CallRecord,call_id)
        if not rec or u.id!=rec.callee_id:raise HTTPException(404,"Call not found")
        rec.status="DECLINED";rec.ended_at=datetime.now(timezone.utc);db.commit()
        return {"ok":True}

    @router.post("/v23/calls/{call_id}/end")
    def end_call(call_id:str,u=Depends(current_user),db:Session=Depends(dep_db)):
        rec=db.get(CallRecord,call_id)
        if not rec or u.id not in (rec.caller_id,rec.callee_id):raise HTTPException(404,"Call not found")
        rec.status="ENDED";rec.ended_at=datetime.now(timezone.utc);db.commit()
        return {"ok":True}

def register_v23_routes(app,current_user,get_db,push,push_tokens,user_json):
    install_dependencies(get_db,current_user,push,push_tokens,user_json)
    register_group_routes(current_user)
    register_call_routes(current_user)
    # Remove the placeholder route before include.
    router.routes[:] = [r for r in router.routes if getattr(r,"path","")!="/groups"]
    app.include_router(router)
