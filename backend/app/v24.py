import os, re, json, uuid
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select, or_, func
from sqlalchemy.orm import Session
from .models import (User, Chat, Message, MessageAttachment, VoiceNote,
    LemmiqGroup, GroupMember, GroupSetting, GroupRead, GroupMessage, GroupMessageAttachment, GroupVoiceNote,
    CallRecord, StatusPost, StatusView, SocialMemory,
    MessageMeta, MessageReaction, MessageHidden, ChatPreference, UserPrivacy, UserBlock, UserReport)
from . import media_store, push_service, transcription

router=APIRouter()
_get_db=_current_user=_push=_push_tokens=_user_json=_msg_json=None

def dep_db():
    yield from _get_db()

def install(get_db,current_user,push,push_tokens,user_json,msg_json):
    global _get_db,_current_user,_push,_push_tokens,_user_json,_msg_json
    _get_db=get_db;_current_user=current_user;_push=push;_push_tokens=push_tokens;_user_json=user_json;_msg_json=msg_json

def gmember(db,gid,uid):
    g=db.get(LemmiqGroup,gid);m=db.get(GroupMember,{"group_id":gid,"user_id":uid})
    if not g or not m:raise HTTPException(404,"Group not found")
    return g,m

def gadmin(db,gid,uid):
    g,m=gmember(db,gid,uid)
    if m.role!="ADMIN":raise HTTPException(403,"Group admin required")
    return g,m

def gattach(db,mid):
    a=db.get(GroupMessageAttachment,mid)
    if not a:return None
    v=db.get(GroupVoiceNote,mid)
    return {"kind":a.kind,"name":a.original_name,"mime_type":a.mime_type,"size_bytes":a.size_bytes,
            "media_id":a.message_id if a.object_key else None,
            "duration_ms":v.duration_ms if v else None,"transcript":v.transcript if v else None}

def gmjson(db,m):
    sender=db.get(User,m.sender_id)
    return {"id":m.id,"group_id":m.group_id,"sender_id":m.sender_id,
            "sender":_user_json(sender) if sender else None,"text":m.text,
            "created_at":m.created_at.isoformat(),"ai_generated":m.ai_generated,"attachment":gattach(db,m.id)}

def gjson(db,g,uid):
    members=db.scalars(select(GroupMember).where(GroupMember.group_id==g.id).order_by(GroupMember.joined_at.asc())).all()
    s=db.get(GroupSetting,{"group_id":g.id,"user_id":uid})
    if not s:s=GroupSetting(group_id=g.id,user_id=uid);db.add(s);db.commit();db.refresh(s)
    last=db.scalar(select(GroupMessage).where(GroupMessage.group_id==g.id).order_by(GroupMessage.id.desc()).limit(1))
    read=db.get(GroupRead,{"group_id":g.id,"user_id":uid});last_read=read.last_read_message_id if read else 0
    unread=int(db.scalar(select(func.count()).select_from(GroupMessage).where(GroupMessage.group_id==g.id,GroupMessage.id>last_read,GroupMessage.sender_id!=uid)) or 0)
    out=[]
    for m in members:
        x=db.get(User,m.user_id)
        if x:out.append({**_user_json(x),"role":m.role})
    return {"id":g.id,"name":g.name,"created_by":g.created_by,"has_photo":bool(g.photo_key),
            "photo_url":f"/v24/groups/{g.id}/photo" if g.photo_key else None,"member_count":len(members),
            "role":next((x.role for x in members if x.user_id==uid),"MEMBER"),"ai_mode":s.ai_mode,"tone":s.tone,
            "last_message":last.text if last else None,"updated_at":g.updated_at.isoformat(),"unread":unread,"members":out}

async def gpush(db,gid,payload,exclude=None):
    for m in db.scalars(select(GroupMember).where(GroupMember.group_id==gid)).all():
        if m.user_id!=exclude:await _push(m.user_id,payload)

def do_transcribe(payload,filename,mime):
    if os.getenv("LEMMIQ_VOICE_TRANSCRIPTION","true").lower()!="true":return ""
    return transcription.transcribe(payload,filename,mime)

def utc_dt(value):
    if value is None:return None
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


class GroupCreate(BaseModel):
    name:str=Field(min_length=1,max_length=100);member_ids:list[int]=Field(default_factory=list,max_length=100)
class GroupSettingIn(BaseModel): ai_mode:str;tone:str="Natural"
class UserIdIn(BaseModel): user_id:int
class RoleIn(BaseModel): role:str
class TextIn(BaseModel): text:str=Field(min_length=1,max_length=4000)
class AskIn(BaseModel): question:str=Field(min_length=1,max_length=1600)
class CallStartIn(BaseModel):
    chat_id:int
    call_type:str="VOICE"
class SocialMemoryIn(BaseModel):
    chat_id:int|None=None;memory_type:str="IMPORTANT";title:str=Field(min_length=1,max_length=160);detail:str="";source_message_id:int|None=None

class MessageEditIn(BaseModel):
    text:str=Field(min_length=1,max_length=4000)
class ReactionIn(BaseModel):
    emoji:str=Field(min_length=1,max_length=16)
class ReplyIn(BaseModel):
    text:str=Field(min_length=1,max_length=4000)
    reply_to_message_id:int
class ForwardIn(BaseModel):
    chat_ids:list[int]=Field(default_factory=list,max_length=20)
class ChatPrefIn(BaseModel):
    pinned:bool|None=None
    archived:bool|None=None
    favourite:bool|None=None
    muted_minutes:int|None=Field(default=None,ge=0,le=525600)
    draft_text:str|None=Field(default=None,max_length=4000)
class PrivacyIn(BaseModel):
    profile_photo:str="EVERYONE"
    last_seen:str="EVERYONE"
    status_visibility:str="EVERYONE"
class ReportIn(BaseModel):
    reason:str=Field(default="OTHER",max_length=60)
    details:str=Field(default="",max_length=2000)


def register_routes(current_user):
    # -------- profile photo --------
    @router.post("/v24/profile/avatar")
    async def profile_avatar(file:UploadFile=File(...),u=Depends(current_user),db:Session=Depends(dep_db)):
        mime=(file.content_type or "").split(";")[0].lower()
        if mime not in {"image/jpeg","image/png","image/webp"}:raise HTTPException(415,"Use JPEG, PNG or WebP")
        data=await file.read(5*1024*1024+1)
        if not data or len(data)>5*1024*1024:raise HTTPException(413,"Profile photo must be 5 MB or less")
        u.avatar=media_store.store(data);db.commit();return _user_json(u)

    @router.delete("/v24/profile/avatar")
    def profile_avatar_delete(u=Depends(current_user),db:Session=Depends(dep_db)):
        u.avatar=None;db.commit();return _user_json(u)

    @router.get("/v24/profile/avatar/{uid}")
    def profile_avatar_get(uid:int,db:Session=Depends(dep_db)):
        x=db.get(User,uid)
        if not x or not x.avatar:raise HTTPException(404,"Profile photo not found")
        return StreamingResponse(media_store.stream(x.avatar),media_type="image/jpeg",headers={"Cache-Control":"private,max-age=300"})

    # -------- groups --------
    @router.get("/v24/groups")
    def groups(u=Depends(current_user),db:Session=Depends(dep_db)):
        gids=[x.group_id for x in db.scalars(select(GroupMember).where(GroupMember.user_id==u.id)).all()]
        if not gids:return []
        rows=db.scalars(select(LemmiqGroup).where(LemmiqGroup.id.in_(gids)).order_by(LemmiqGroup.updated_at.desc())).all()
        return [gjson(db,g,u.id) for g in rows]

    @router.post("/v24/groups")
    def create_group(body:GroupCreate,u=Depends(current_user),db:Session=Depends(dep_db)):
        ids=[]
        for x in body.member_ids:
            if x!=u.id and x not in ids:ids.append(x)
        if not ids:raise HTTPException(400,"Choose at least one other member")
        if len(db.scalars(select(User).where(User.id.in_(ids))).all())!=len(ids):raise HTTPException(404,"Member not found")
        g=LemmiqGroup(name=body.name.strip(),created_by=u.id);db.add(g);db.flush()
        for uid,role in [(u.id,"ADMIN")]+[(x,"MEMBER") for x in ids]:
            db.add(GroupMember(group_id=g.id,user_id=uid,role=role));db.add(GroupSetting(group_id=g.id,user_id=uid));db.add(GroupRead(group_id=g.id,user_id=uid))
        db.commit();db.refresh(g);return gjson(db,g,u.id)

    @router.get("/v24/groups/{gid}")
    def group_detail(gid:int,u=Depends(current_user),db:Session=Depends(dep_db)):
        g,_=gmember(db,gid,u.id);return gjson(db,g,u.id)

    @router.get("/v24/groups/{gid}/messages")
    def group_messages(gid:int,u=Depends(current_user),db:Session=Depends(dep_db)):
        gmember(db,gid,u.id);rows=db.scalars(select(GroupMessage).where(GroupMessage.group_id==gid).order_by(GroupMessage.id.asc()).limit(800)).all();return [gmjson(db,m) for m in rows]

    @router.post("/v24/groups/{gid}/read")
    def group_read(gid:int,u=Depends(current_user),db:Session=Depends(dep_db)):
        gmember(db,gid,u.id);last=int(db.scalar(select(func.max(GroupMessage.id)).where(GroupMessage.group_id==gid)) or 0)
        r=db.get(GroupRead,{"group_id":gid,"user_id":u.id})
        if not r:r=GroupRead(group_id=gid,user_id=u.id,last_read_message_id=last);db.add(r)
        else:r.last_read_message_id=last
        db.commit();return {"ok":True}

    @router.post("/v24/groups/{gid}/messages")
    async def group_send(gid:int,body:TextIn,background:BackgroundTasks,u=Depends(current_user),db:Session=Depends(dep_db)):
        g,_=gmember(db,gid,u.id);m=GroupMessage(group_id=gid,sender_id=u.id,text=body.text.strip());g.updated_at=datetime.now(timezone.utc);db.add(m);db.commit();db.refresh(m);data=gmjson(db,m)
        await gpush(db,gid,{"type":"group_message","group_id":gid,"data":data})
        for x in db.scalars(select(GroupMember).where(GroupMember.group_id==gid,GroupMember.user_id!=u.id)).all():
            background.add_task(push_service.notify_data,_push_tokens(db,x.user_id),{"type":"group","group_id":gid,"group_name":g.name,"sender_name":u.display_name,"body":m.text})
        return data

    @router.put("/v24/groups/{gid}/settings")
    def group_settings(gid:int,body:GroupSettingIn,u=Depends(current_user),db:Session=Depends(dep_db)):
        g,_=gmember(db,gid,u.id)
        if body.ai_mode not in {"OFF","ASSIST","SUMMARY"}:raise HTTPException(400,"Use OFF, ASSIST or SUMMARY")
        s=db.get(GroupSetting,{"group_id":gid,"user_id":u.id});s.ai_mode=body.ai_mode;s.tone=body.tone[:40];db.commit();return gjson(db,g,u.id)

    @router.post("/v24/groups/{gid}/members")
    def group_add(gid:int,body:UserIdIn,u=Depends(current_user),db:Session=Depends(dep_db)):
        g,_=gadmin(db,gid,u.id)
        if not db.get(User,body.user_id):raise HTTPException(404,"User not found")
        if not db.get(GroupMember,{"group_id":gid,"user_id":body.user_id}):
            db.add(GroupMember(group_id=gid,user_id=body.user_id));db.add(GroupSetting(group_id=gid,user_id=body.user_id));db.add(GroupRead(group_id=gid,user_id=body.user_id));db.commit()
        return gjson(db,g,u.id)

    @router.put("/v24/groups/{gid}/members/{uid}")
    def group_role(gid:int,uid:int,body:RoleIn,u=Depends(current_user),db:Session=Depends(dep_db)):
        g,_=gadmin(db,gid,u.id)
        if body.role not in {"ADMIN","MEMBER"}:raise HTTPException(400,"Invalid role")
        m=db.get(GroupMember,{"group_id":gid,"user_id":uid})
        if not m:raise HTTPException(404,"Member not found")
        m.role=body.role;db.commit();return gjson(db,g,u.id)

    @router.delete("/v24/groups/{gid}/members/{uid}")
    def group_remove(gid:int,uid:int,u=Depends(current_user),db:Session=Depends(dep_db)):
        g,_=gadmin(db,gid,u.id)
        if uid==g.created_by:raise HTTPException(400,"Group creator cannot be removed")
        for cls in (GroupMember,GroupSetting,GroupRead):
            x=db.get(cls,{"group_id":gid,"user_id":uid})
            if x:db.delete(x)
        db.commit();return {"ok":True}

    @router.post("/v24/groups/{gid}/photo")
    async def group_photo(gid:int,file:UploadFile=File(...),u=Depends(current_user),db:Session=Depends(dep_db)):
        g,_=gadmin(db,gid,u.id);mime=(file.content_type or "").split(";")[0].lower();data=await file.read(5*1024*1024+1)
        if mime not in {"image/jpeg","image/png","image/webp"}:raise HTTPException(415,"Use JPEG, PNG or WebP")
        if not data or len(data)>5*1024*1024:raise HTTPException(413,"Group photo must be 5 MB or less")
        g.photo_key=media_store.store(data);db.commit();return gjson(db,g,u.id)

    @router.get("/v24/groups/{gid}/photo")
    def group_photo_get(gid:int,u=Depends(current_user),db:Session=Depends(dep_db)):
        g,_=gmember(db,gid,u.id)
        if not g.photo_key:raise HTTPException(404,"No group photo")
        return StreamingResponse(media_store.stream(g.photo_key),media_type="image/jpeg")

    @router.post("/v24/groups/{gid}/suggest")
    def group_suggest(gid:int,u=Depends(current_user),db:Session=Depends(dep_db)):
        g,_=gmember(db,gid,u.id);s=db.get(GroupSetting,{"group_id":gid,"user_id":u.id})
        if s and s.ai_mode=="OFF":raise HTTPException(400,"Group AI is off")
        rows=db.scalars(select(GroupMessage).where(GroupMessage.group_id==gid).order_by(GroupMessage.id.desc()).limit(60)).all()[::-1]
        incoming=next((x for x in reversed(rows) if x.sender_id!=u.id),None)
        if not incoming:raise HTTPException(400,"No incoming group message")
        key=os.getenv("ANTHROPIC_API_KEY","").strip()
        if not key:return {"reply":"Got it — I’ll reply properly in a moment."}
        from anthropic import Anthropic
        history="\n".join(f"{db.get(User,m.sender_id).display_name}: {m.text}" for m in rows if db.get(User,m.sender_id))
        prompt=f"Group: {g.name}\nTone: {s.tone if s else 'Natural'}\n{history[-16000:]}\nLatest: {incoming.text}\nWrite ONE concise natural reply. Never invent facts, commitments, money, availability or actions. Output only reply."
        msg=Anthropic(api_key=key).messages.create(model=os.getenv("ANTHROPIC_MODEL","claude-sonnet-4-6"),max_tokens=180,temperature=.4,messages=[{"role":"user","content":prompt}])
        return {"reply":"".join(x.text for x in msg.content if getattr(x,"type","")=="text").strip()}

    @router.post("/v24/groups/{gid}/summary")
    def group_summary(gid:int,u=Depends(current_user),db:Session=Depends(dep_db)):
        g,_=gmember(db,gid,u.id);rows=db.scalars(select(GroupMessage).where(GroupMessage.group_id==gid).order_by(GroupMessage.id.desc()).limit(160)).all()[::-1]
        if not rows:return {"summary":"No group messages yet.","decisions":[],"actions":[]}
        history="\n".join(f"{db.get(User,m.sender_id).display_name}: {m.text}" for m in rows if db.get(User,m.sender_id));key=os.getenv("ANTHROPIC_API_KEY","").strip()
        if not key:return {"summary":f"{g.name}: {len(rows)} recent messages.","decisions":[],"actions":[]}
        from anthropic import Anthropic
        prompt='Summarize without inventing facts. Return JSON only: {"summary":"short catch-up","decisions":[],"actions":[]}\n'+history[-22000:]
        m=Anthropic(api_key=key).messages.create(model=os.getenv("ANTHROPIC_MODEL","claude-sonnet-4-6"),max_tokens=700,temperature=0,messages=[{"role":"user","content":prompt}]);raw="".join(x.text for x in m.content if getattr(x,"type","")=="text").strip().removeprefix("```json").removesuffix("```").strip()
        try:return json.loads(raw)
        except:return {"summary":raw[:1800],"decisions":[],"actions":[]}

    @router.post("/v24/groups/{gid}/ask")
    def group_ask(gid:int,body:AskIn,u=Depends(current_user),db:Session=Depends(dep_db)):
        g,_=gmember(db,gid,u.id);rows=db.scalars(select(GroupMessage).where(GroupMessage.group_id==gid).order_by(GroupMessage.id.desc()).limit(180)).all()[::-1]
        history="\n".join(f"{db.get(User,m.sender_id).display_name}: {m.text}" for m in rows if db.get(User,m.sender_id));key=os.getenv("ANTHROPIC_API_KEY","").strip()
        if not key:return {"answer":"AI is not configured on the server.","references":[]}
        from anthropic import Anthropic
        prompt=f'Answer ONLY from this group history. If absent, say so. QUESTION: {body.question}\nHISTORY:\n{history[-24000:]}\nReturn JSON only: {{"answer":"concise answer","references":[]}}'
        m=Anthropic(api_key=key).messages.create(model=os.getenv("ANTHROPIC_MODEL","claude-sonnet-4-6"),max_tokens=700,temperature=0,messages=[{"role":"user","content":prompt}]);raw="".join(x.text for x in m.content if getattr(x,"type","")=="text").strip().removeprefix("```json").removesuffix("```").strip()
        try:return json.loads(raw)
        except:return {"answer":raw[:1800],"references":[]}

    @router.post("/v24/groups/{gid}/attachments")
    async def group_attachment(gid:int,background:BackgroundTasks,file:UploadFile=File(...),u=Depends(current_user),db:Session=Depends(dep_db)):
        g,_=gmember(db,gid,u.id);mime=(file.content_type or "").split(";")[0].lower();kind="PHOTO" if mime.startswith("image/") else "VIDEO" if mime.startswith("video/") else "FILE";payload=await file.read(20*1024*1024+1)
        if not payload or len(payload)>20*1024*1024:raise HTTPException(413,"File must be 20 MB or less")
        key=media_store.store(payload);name=re.sub(r"[^A-Za-z0-9 .()\-]","_",(file.filename or "Attachment").split("/")[-1])[:190]
        m=GroupMessage(group_id=gid,sender_id=u.id,text=f"[{kind.title()}] {name}");g.updated_at=datetime.now(timezone.utc);db.add(m);db.flush();db.add(GroupMessageAttachment(message_id=m.id,kind=kind,object_key=key,original_name=name,mime_type=mime,size_bytes=len(payload)));db.commit();db.refresh(m);data=gmjson(db,m);await gpush(db,gid,{"type":"group_message","group_id":gid,"data":data})
        for x in db.scalars(select(GroupMember).where(GroupMember.group_id==gid,GroupMember.user_id!=u.id)).all():
            background.add_task(push_service.notify_data,_push_tokens(db,x.user_id),{"type":"group","group_id":gid,"group_name":g.name,"sender_name":u.display_name,"body":m.text})
        return data

    @router.get("/v24/group-media/{mid}")
    def group_media(mid:int,u=Depends(current_user),db:Session=Depends(dep_db)):
        a=db.get(GroupMessageAttachment,mid);m=db.get(GroupMessage,mid)
        if not a or not m or not a.object_key:raise HTTPException(404,"Attachment not found")
        gmember(db,m.group_id,u.id);return StreamingResponse(media_store.stream(a.object_key),media_type=a.mime_type or "application/octet-stream")

    # -------- voice notes --------
    @router.post("/v24/chats/{cid}/voice")
    async def direct_voice(cid:int,background:BackgroundTasks,file:UploadFile=File(...),duration_ms:int=Form(0),u=Depends(current_user),db:Session=Depends(dep_db)):
        c=db.get(Chat,cid)
        if not c or u.id not in (c.user1_id,c.user2_id):raise HTTPException(404,"Chat not found")
        mime=(file.content_type or "audio/webm").split(";")[0].lower();payload=await file.read(12*1024*1024+1)
        if not payload or len(payload)>12*1024*1024:raise HTTPException(413,"Voice note must be 12 MB or less")
        key=media_store.store(payload);transcript=do_transcribe(payload,file.filename or "voice.webm",mime)
        m=Message(chat_id=cid,sender_id=u.id,text="🎙 Voice message");c.updated_at=datetime.now(timezone.utc);db.add(m);db.flush();db.add(MessageAttachment(message_id=m.id,kind="VOICE",object_key=key,original_name="voice-note",mime_type=mime,size_bytes=len(payload)));db.add(VoiceNote(message_id=m.id,duration_ms=max(0,min(duration_ms,3600000)),transcript=transcript,transcribed_at=datetime.now(timezone.utc) if transcript else None));db.commit();db.refresh(m);data=_msg_json(m,db);oid=c.user2_id if c.user1_id==u.id else c.user1_id;await _push(oid,{"type":"message","data":data});await _push(u.id,{"type":"message","data":data});background.add_task(push_service.notify,_push_tokens(db,oid),u.display_name,cid,"🎙 Voice message",1);return data

    @router.post("/v24/groups/{gid}/voice")
    async def group_voice(gid:int,background:BackgroundTasks,file:UploadFile=File(...),duration_ms:int=Form(0),u=Depends(current_user),db:Session=Depends(dep_db)):
        g,_=gmember(db,gid,u.id);mime=(file.content_type or "audio/webm").split(";")[0].lower();payload=await file.read(12*1024*1024+1)
        if not payload or len(payload)>12*1024*1024:raise HTTPException(413,"Voice note must be 12 MB or less")
        key=media_store.store(payload);transcript=do_transcribe(payload,file.filename or "voice.webm",mime)
        m=GroupMessage(group_id=gid,sender_id=u.id,text="🎙 Voice message");g.updated_at=datetime.now(timezone.utc);db.add(m);db.flush();db.add(GroupMessageAttachment(message_id=m.id,kind="VOICE",object_key=key,original_name="voice-note",mime_type=mime,size_bytes=len(payload)));db.add(GroupVoiceNote(message_id=m.id,duration_ms=max(0,min(duration_ms,3600000)),transcript=transcript,transcribed_at=datetime.now(timezone.utc) if transcript else None));db.commit();db.refresh(m);data=gmjson(db,m);await gpush(db,gid,{"type":"group_message","group_id":gid,"data":data})
        for x in db.scalars(select(GroupMember).where(GroupMember.group_id==gid,GroupMember.user_id!=u.id)).all():
            background.add_task(push_service.notify_data,_push_tokens(db,x.user_id),{"type":"group","group_id":gid,"group_name":g.name,"sender_name":u.display_name,"body":"🎙 Voice message"})
        return data

    @router.post("/v24/voice/{mid}/ai")
    def voice_ai(mid:int,u=Depends(current_user),db:Session=Depends(dep_db)):
        m=db.get(Message,mid);v=db.get(VoiceNote,mid)
        if not m or not v:raise HTTPException(404,"Voice message not found")
        c=db.get(Chat,m.chat_id)
        if not c or u.id not in (c.user1_id,c.user2_id):raise HTTPException(404,"Voice message not found")
        if not v.transcript.strip():raise HTTPException(409,"Transcript is not available yet. Configure OPENAI_API_KEY for automatic transcription.")
        key=os.getenv("ANTHROPIC_API_KEY","").strip()
        if not key:return {"transcript":v.transcript,"summary":v.transcript[:300],"suggested_reply":""}
        from anthropic import Anthropic
        prompt=f'Voice transcript:\n{v.transcript[:12000]}\nReturn JSON only: {{"summary":"1-2 sentence summary","suggested_reply":"one concise natural reply matching the transcript language"}}'
        msg=Anthropic(api_key=key).messages.create(model=os.getenv("ANTHROPIC_MODEL","claude-sonnet-4-6"),max_tokens=350,temperature=.3,messages=[{"role":"user","content":prompt}]);raw="".join(x.text for x in msg.content if getattr(x,"type","")=="text").strip().removeprefix("```json").removesuffix("```").strip()
        try:data=json.loads(raw)
        except:data={"summary":raw[:700],"suggested_reply":""}
        data["transcript"]=v.transcript;return data


    # -------- message actions / chat management --------
    def direct_message_for_user(db:Session,mid:int,uid:int):
        m=db.get(Message,mid)
        if not m:raise HTTPException(404,"Message not found")
        c=db.get(Chat,m.chat_id)
        if not c or uid not in (c.user1_id,c.user2_id):raise HTTPException(404,"Message not found")
        return m,c

    @router.put("/v24/messages/{mid}")
    async def edit_message(mid:int,body:MessageEditIn,u=Depends(current_user),db:Session=Depends(dep_db)):
        m,c=direct_message_for_user(db,mid,u.id)
        if m.sender_id!=u.id:raise HTTPException(403,"You can only edit your own message")
        created_at=m.created_at
        if created_at.tzinfo is None:
            created_at=created_at.replace(tzinfo=timezone.utc)
        if (datetime.now(timezone.utc)-created_at).total_seconds()>15*60:
            raise HTTPException(409,"Editing is available for 15 minutes after sending")
        meta=db.get(MessageMeta,mid)
        if not meta:meta=MessageMeta(message_id=mid);db.add(meta)
        if meta.deleted_for_everyone:raise HTTPException(409,"Deleted messages cannot be edited")
        meta.edited_text=body.text.strip();meta.edited_at=datetime.now(timezone.utc);c.updated_at=datetime.now(timezone.utc);db.commit()
        data=_msg_json(m,db)
        other=c.user2_id if c.user1_id==u.id else c.user1_id
        await _push(other,{"type":"message_update","data":data});await _push(u.id,{"type":"message_update","data":data})
        return data

    @router.delete("/v24/messages/{mid}")
    async def delete_message(mid:int,scope:str="me",u=Depends(current_user),db:Session=Depends(dep_db)):
        m,c=direct_message_for_user(db,mid,u.id)
        scope=scope.lower()
        if scope=="everyone":
            if m.sender_id!=u.id:raise HTTPException(403,"You can only delete your own message for everyone")
            meta=db.get(MessageMeta,mid)
            if not meta:meta=MessageMeta(message_id=mid);db.add(meta)
            meta.deleted_for_everyone=True;meta.edited_text=None;meta.edited_at=datetime.now(timezone.utc);db.commit()
            data=_msg_json(m,db);other=c.user2_id if c.user1_id==u.id else c.user1_id
            await _push(other,{"type":"message_update","data":data});await _push(u.id,{"type":"message_update","data":data})
            return {"ok":True,"scope":"everyone","message":data}
        hidden=db.get(MessageHidden,{"message_id":mid,"user_id":u.id})
        if not hidden:db.add(MessageHidden(message_id=mid,user_id=u.id));db.commit()
        return {"ok":True,"scope":"me"}

    @router.post("/v24/messages/{mid}/reaction")
    async def react_message(mid:int,body:ReactionIn,u=Depends(current_user),db:Session=Depends(dep_db)):
        m,c=direct_message_for_user(db,mid,u.id)
        row=db.get(MessageReaction,{"message_id":mid,"user_id":u.id})
        if not row:row=MessageReaction(message_id=mid,user_id=u.id,emoji=body.emoji);db.add(row)
        else:row.emoji=body.emoji
        db.commit();data=_msg_json(m,db);other=c.user2_id if c.user1_id==u.id else c.user1_id
        await _push(other,{"type":"message_update","data":data});await _push(u.id,{"type":"message_update","data":data})
        return data

    @router.delete("/v24/messages/{mid}/reaction")
    async def clear_reaction(mid:int,u=Depends(current_user),db:Session=Depends(dep_db)):
        m,c=direct_message_for_user(db,mid,u.id)
        row=db.get(MessageReaction,{"message_id":mid,"user_id":u.id})
        if row:db.delete(row);db.commit()
        data=_msg_json(m,db);other=c.user2_id if c.user1_id==u.id else c.user1_id
        await _push(other,{"type":"message_update","data":data});await _push(u.id,{"type":"message_update","data":data})
        return data

    @router.post("/v24/chats/{cid}/reply")
    async def reply_message(cid:int,body:ReplyIn,background:BackgroundTasks,u=Depends(current_user),db:Session=Depends(dep_db)):
        c=db.get(Chat,cid)
        if not c or u.id not in (c.user1_id,c.user2_id):raise HTTPException(404,"Chat not found")
        parent=db.get(Message,body.reply_to_message_id)
        if not parent or parent.chat_id!=cid:raise HTTPException(400,"Reply target is not in this chat")
        m=Message(chat_id=cid,sender_id=u.id,text=body.text.strip());c.updated_at=datetime.now(timezone.utc);db.add(m);db.flush()
        db.add(MessageMeta(message_id=m.id,reply_to_message_id=parent.id));db.commit();db.refresh(m)
        data=_msg_json(m,db);other=c.user2_id if c.user1_id==u.id else c.user1_id
        await _push(other,{"type":"message","data":data});await _push(u.id,{"type":"message","data":data})
        background.add_task(push_service.notify,_push_tokens(db,other),u.display_name,cid,m.text,1)
        return data

    @router.post("/v24/messages/{mid}/forward")
    async def forward_message(mid:int,body:ForwardIn,u=Depends(current_user),db:Session=Depends(dep_db)):
        source,_=direct_message_for_user(db,mid,u.id)
        meta=db.get(MessageMeta,mid)
        text="This message was deleted" if meta and meta.deleted_for_everyone else ((meta.edited_text if meta and meta.edited_text is not None else source.text) or "")
        created=[]
        for cid in list(dict.fromkeys(body.chat_ids))[:20]:
            c=db.get(Chat,cid)
            if not c or u.id not in (c.user1_id,c.user2_id):continue
            m=Message(chat_id=cid,sender_id=u.id,text=text);c.updated_at=datetime.now(timezone.utc);db.add(m);db.flush();created.append(_msg_json(m,db))
        db.commit()
        return {"created":created}

    @router.get("/v24/chats/{cid}/search")
    def search_chat(cid:int,q:str,u=Depends(current_user),db:Session=Depends(dep_db)):
        c=db.get(Chat,cid)
        if not c or u.id not in (c.user1_id,c.user2_id):raise HTTPException(404,"Chat not found")
        term=q.strip()
        if len(term)<2:return []
        hidden=select(MessageHidden.message_id).where(MessageHidden.user_id==u.id)
        edited_ids=select(MessageMeta.message_id).where(MessageMeta.edited_text.ilike(f"%{term}%"))
        rows=db.scalars(select(Message).where(
            Message.chat_id==cid,~Message.id.in_(hidden),
            or_(Message.text.ilike(f"%{term}%"),Message.id.in_(edited_ids))
        ).order_by(Message.id.desc()).limit(100)).all()
        return [_msg_json(m,db) for m in rows]

    @router.get("/v24/chats/{cid}/media")
    def chat_media(cid:int,u=Depends(current_user),db:Session=Depends(dep_db)):
        c=db.get(Chat,cid)
        if not c or u.id not in (c.user1_id,c.user2_id):raise HTTPException(404,"Chat not found")
        rows=db.scalars(select(MessageAttachment).join(Message,Message.id==MessageAttachment.message_id).where(Message.chat_id==cid).order_by(Message.id.desc()).limit(300)).all()
        return [{"message_id":a.message_id,"kind":a.kind,"name":a.original_name,"mime_type":a.mime_type,"size_bytes":a.size_bytes} for a in rows]

    @router.get("/v24/chats/{cid}/preferences")
    def chat_preferences(cid:int,u=Depends(current_user),db:Session=Depends(dep_db)):
        c=db.get(Chat,cid)
        if not c or u.id not in (c.user1_id,c.user2_id):raise HTTPException(404,"Chat not found")
        p=db.get(ChatPreference,{"chat_id":cid,"user_id":u.id})
        if not p:p=ChatPreference(chat_id=cid,user_id=u.id);db.add(p);db.commit();db.refresh(p)
        return {"pinned":p.pinned,"archived":p.archived,"favourite":p.favourite,"muted_until":p.muted_until.isoformat() if p.muted_until else None,"draft_text":p.draft_text}

    @router.put("/v24/chats/{cid}/preferences")
    def update_chat_preferences(cid:int,body:ChatPrefIn,u=Depends(current_user),db:Session=Depends(dep_db)):
        c=db.get(Chat,cid)
        if not c or u.id not in (c.user1_id,c.user2_id):raise HTTPException(404,"Chat not found")
        p=db.get(ChatPreference,{"chat_id":cid,"user_id":u.id})
        if not p:p=ChatPreference(chat_id=cid,user_id=u.id);db.add(p)
        if body.pinned is not None:p.pinned=body.pinned
        if body.archived is not None:p.archived=body.archived
        if body.favourite is not None:p.favourite=body.favourite
        if body.muted_minutes is not None:p.muted_until=(datetime.now(timezone.utc)+timedelta(minutes=body.muted_minutes)) if body.muted_minutes>0 else None
        if body.draft_text is not None:p.draft_text=body.draft_text
        db.commit();return {"pinned":p.pinned,"archived":p.archived,"favourite":p.favourite,"muted_until":p.muted_until.isoformat() if p.muted_until else None,"draft_text":p.draft_text}

    @router.get("/v24/privacy")
    def get_privacy(u=Depends(current_user),db:Session=Depends(dep_db)):
        p=db.get(UserPrivacy,u.id)
        if not p:p=UserPrivacy(user_id=u.id);db.add(p);db.commit();db.refresh(p)
        return {"profile_photo":p.profile_photo,"last_seen":p.last_seen,"status_visibility":p.status_visibility}

    @router.put("/v24/privacy")
    def set_privacy(body:PrivacyIn,u=Depends(current_user),db:Session=Depends(dep_db)):
        valid={"EVERYONE","CONTACTS","NOBODY"}
        if body.profile_photo not in valid or body.last_seen not in valid or body.status_visibility not in valid:raise HTTPException(400,"Invalid privacy option")
        p=db.get(UserPrivacy,u.id)
        if not p:p=UserPrivacy(user_id=u.id);db.add(p)
        p.profile_photo=body.profile_photo;p.last_seen=body.last_seen;p.status_visibility=body.status_visibility;db.commit()
        return {"profile_photo":p.profile_photo,"last_seen":p.last_seen,"status_visibility":p.status_visibility}

    @router.post("/v24/users/{uid}/block")
    def block_user(uid:int,u=Depends(current_user),db:Session=Depends(dep_db)):
        if uid==u.id:raise HTTPException(400,"Cannot block yourself")
        if not db.get(User,uid):raise HTTPException(404,"User not found")
        if not db.get(UserBlock,{"blocker_id":u.id,"blocked_id":uid}):db.add(UserBlock(blocker_id=u.id,blocked_id=uid));db.commit()
        return {"ok":True}

    @router.delete("/v24/users/{uid}/block")
    def unblock_user(uid:int,u=Depends(current_user),db:Session=Depends(dep_db)):
        row=db.get(UserBlock,{"blocker_id":u.id,"blocked_id":uid})
        if row:db.delete(row);db.commit()
        return {"ok":True}

    @router.post("/v24/users/{uid}/report")
    def report_user(uid:int,body:ReportIn,u=Depends(current_user),db:Session=Depends(dep_db)):
        if uid==u.id:raise HTTPException(400,"Cannot report yourself")
        if not db.get(User,uid):raise HTTPException(404,"User not found")
        r=UserReport(reporter_id=u.id,reported_user_id=uid,reason=body.reason,details=body.details);db.add(r);db.commit();return {"ok":True}

    # -------- calls --------
    ACTIVE_CALL_STATES={"RINGING","CONNECTING","CONNECTED"}
    TERMINAL_CALL_STATES={"DECLINED","ENDED","MISSED","FAILED"}

    def livekit_ready():
        return bool(os.getenv("LIVEKIT_URL","").strip() and os.getenv("LIVEKIT_API_KEY","").strip() and os.getenv("LIVEKIT_API_SECRET","").strip())

    def token(room,user):
        if not livekit_ready():raise HTTPException(503,"LiveKit is not configured")
        from livekit import api
        return (api.AccessToken(os.environ["LIVEKIT_API_KEY"],os.environ["LIVEKIT_API_SECRET"])
            .with_identity(f"u_{user.id}").with_name(user.display_name[:80])
            .with_grants(api.VideoGrants(room_join=True,room=room,can_publish=True,can_subscribe=True))
            .with_ttl(timedelta(hours=2))).to_jwt()

    def cj(db,c,uid):
        other=db.get(User,c.callee_id if c.caller_id==uid else c.caller_id)
        dur=int(((utc_dt(c.ended_at) or datetime.now(timezone.utc))-(utc_dt(c.answered_at) or utc_dt(c.started_at))).total_seconds()) if c.answered_at else 0
        return {"id":c.id,"chat_id":c.chat_id,"caller_id":c.caller_id,"callee_id":c.callee_id,
                "other_user":_user_json(other) if other else None,"status":c.status,
                "call_type":(getattr(c,"call_type",None) or "VOICE").upper(),
                "duration_seconds":max(0,dur),"started_at":c.started_at.isoformat(),
                "answered_at":c.answered_at.isoformat() if c.answered_at else None,
                "ended_at":c.ended_at.isoformat() if c.ended_at else None,"last_heartbeat_at":c.last_heartbeat_at.isoformat() if getattr(c,"last_heartbeat_at",None) else None}

    def _call_participant_filter(ids):
        return or_(CallRecord.caller_id.in_(ids),CallRecord.callee_id.in_(ids))

    def _expire_stale_calls(db,ids):
        now=datetime.now(timezone.utc)
        # A ringing call should never block either user forever if a client disappeared.
        rows=db.scalars(select(CallRecord).where(
            CallRecord.status=="RINGING",
            _call_participant_filter(ids),
            CallRecord.started_at < now-timedelta(minutes=2)
        )).all()
        for x in rows:
            x.status="MISSED";x.ended_at=now
        # V2.10.8 heartbeat cleanup: a LiveKit call whose client stopped
        # heartbeating must not block new calls forever.
        connected=db.scalars(select(CallRecord).where(
            CallRecord.status.in_({"CONNECTING","CONNECTED"}),
            _call_participant_filter(ids)
        )).all()
        changed=False
        for x in connected:
            hb=utc_dt(getattr(x,"last_heartbeat_at",None))
            started=utc_dt(x.started_at)
            stale=(hb is not None and hb < now-timedelta(seconds=45)) or (hb is None and started < now-timedelta(minutes=2))
            if stale:
                x.status="ENDED";x.ended_at=now;changed=True
        if changed:db.flush()

    @router.get("/v24/calls/status")
    def call_status(u=Depends(current_user)):
        return {"configured":livekit_ready(),"provider":"LiveKit","voice":True,"video":True,"single_active_call":True}

    @router.get("/v24/calls")
    def call_history(u=Depends(current_user),db:Session=Depends(dep_db)):
        rows=db.scalars(select(CallRecord).where(or_(CallRecord.caller_id==u.id,CallRecord.callee_id==u.id)).order_by(CallRecord.started_at.desc()).limit(100)).all()
        return [cj(db,x,u.id) for x in rows]

    @router.get("/v24/chats/{cid}/calls")
    def chat_calls(cid:int,u=Depends(current_user),db:Session=Depends(dep_db)):
        c=db.get(Chat,cid)
        if not c or u.id not in (c.user1_id,c.user2_id):raise HTTPException(404,"Chat not found")
        rows=db.scalars(select(CallRecord).where(CallRecord.chat_id==cid).order_by(CallRecord.started_at.asc()).limit(200)).all()
        return [cj(db,x,u.id) for x in rows]

    @router.get("/v24/calls/{call_id}")
    def call_detail(call_id:str,u=Depends(current_user),db:Session=Depends(dep_db)):
        rec=db.get(CallRecord,call_id)
        if not rec or u.id not in (rec.caller_id,rec.callee_id):raise HTTPException(404,"Call not found")
        return cj(db,rec,u.id)

    @router.post("/v24/calls/start")
    async def call_start(body:CallStartIn,background:BackgroundTasks,u=Depends(current_user),db:Session=Depends(dep_db)):
        if not livekit_ready():raise HTTPException(503,"LiveKit is not configured. Add LIVEKIT_URL, LIVEKIT_API_KEY and LIVEKIT_API_SECRET on Render.")
        c=db.get(Chat,body.chat_id)
        if not c or u.id not in (c.user1_id,c.user2_id):raise HTTPException(404,"Chat not found")
        callee=c.user2_id if c.user1_id==u.id else c.user1_id
        ids=sorted({u.id,callee})

        # Lock both participants before checking active calls. This closes the rapid-double-tap
        # race on PostgreSQL and still works safely when running the local SQLite dev database.
        db.execute(select(User.id).where(User.id.in_(ids)).order_by(User.id).with_for_update()).all()
        _expire_stale_calls(db,ids)
        active=db.scalar(select(CallRecord).where(
            CallRecord.status.in_(ACTIVE_CALL_STATES),
            _call_participant_filter(ids)
        ).order_by(CallRecord.started_at.desc()).limit(1))
        if active:
            same_pair={active.caller_id,active.callee_id}==set(ids)
            db.rollback()
            raise HTTPException(409,"Call already active" if same_pair else "User is already in another call")

        call_type=(body.call_type or "VOICE").strip().upper()
        if call_type not in {"VOICE","VIDEO"}:raise HTTPException(422,"call_type must be VOICE or VIDEO")
        cid=uuid.uuid4().hex;room="call_"+uuid.uuid4().hex
        rec=CallRecord(id=cid,chat_id=c.id,caller_id=u.id,callee_id=callee,room_name=room,status="RINGING",call_type=call_type,last_heartbeat_at=datetime.now(timezone.utc))
        db.add(rec);db.commit();db.refresh(rec)
        caller_avatar=_user_json(u).get("avatar_url")
        event={"type":"incoming_call","call_id":cid,"chat_id":c.id,"caller_name":u.display_name,"caller_id":u.id,"caller_avatar_url":caller_avatar,"call_type":call_type}
        await _push(callee,event)
        background.add_task(push_service.notify_data,_push_tokens(db,callee),{
            "type":"call","call_id":cid,"chat_id":c.id,"caller_name":u.display_name,
            "caller_id":u.id,"caller_avatar_url":caller_avatar or "","call_type":call_type
        })
        return {"call":cj(db,rec,u.id),"ws_url":os.environ.get("LIVEKIT_URL",""),"token":token(room,u),"incoming":False}

    @router.post("/v24/calls/{call_id}/join")
    async def call_join(call_id:str,u=Depends(current_user),db:Session=Depends(dep_db)):
        rec=db.get(CallRecord,call_id)
        if not rec or u.id not in (rec.caller_id,rec.callee_id):raise HTTPException(404,"Call not found")
        if rec.status in TERMINAL_CALL_STATES:raise HTTPException(409,f"Call is {rec.status.lower()}")
        if rec.status not in ACTIVE_CALL_STATES:raise HTTPException(409,"Call is no longer active")
        rec.last_heartbeat_at=datetime.now(timezone.utc)
        if u.id==rec.callee_id and rec.status=="RINGING":
            rec.status="CONNECTED";rec.answered_at=datetime.now(timezone.utc);db.commit()
            await _push(rec.caller_id,{"type":"call_answered","call_id":rec.id,"answered_at":rec.answered_at.isoformat()})
        return {"call":cj(db,rec,u.id),"ws_url":os.environ.get("LIVEKIT_URL",""),"token":token(rec.room_name,u),"incoming":u.id==rec.callee_id}

    @router.post("/v24/calls/{call_id}/heartbeat")
    def call_heartbeat(call_id:str,u=Depends(current_user),db:Session=Depends(dep_db)):
        rec=db.get(CallRecord,call_id)
        if not rec or u.id not in (rec.caller_id,rec.callee_id):raise HTTPException(404,"Call not found")
        if rec.status in TERMINAL_CALL_STATES:return {"ok":False,"status":rec.status}
        rec.last_heartbeat_at=datetime.now(timezone.utc);db.commit()
        return {"ok":True,"status":rec.status}

    @router.get("/v24/calls/active/me")
    def active_call(u=Depends(current_user),db:Session=Depends(dep_db)):
        _expire_stale_calls(db,[u.id]);db.commit()
        rec=db.scalar(select(CallRecord).where(
            CallRecord.status.in_(ACTIVE_CALL_STATES),
            or_(CallRecord.caller_id==u.id,CallRecord.callee_id==u.id)
        ).order_by(CallRecord.started_at.desc()).limit(1))
        return {"active":bool(rec),"call":cj(db,rec,u.id) if rec else None}

    @router.post("/v24/calls/active/clear")
    async def clear_stuck_call(u=Depends(current_user),db:Session=Depends(dep_db)):
        rec=db.scalar(select(CallRecord).where(
            CallRecord.status.in_(ACTIVE_CALL_STATES),
            or_(CallRecord.caller_id==u.id,CallRecord.callee_id==u.id)
        ).order_by(CallRecord.started_at.desc()).limit(1))
        if not rec:return {"ok":True,"cleared":False}
        other=rec.callee_id if u.id==rec.caller_id else rec.caller_id
        rec.status="ENDED";rec.ended_at=datetime.now(timezone.utc);db.commit()
        await _push(other,{"type":"call_ended","call_id":rec.id,"status":"ENDED"})
        return {"ok":True,"cleared":True,"call_id":rec.id}

    @router.post("/v24/calls/{call_id}/decline")
    async def call_decline(call_id:str,u=Depends(current_user),db:Session=Depends(dep_db)):
        rec=db.get(CallRecord,call_id)
        if not rec or u.id!=rec.callee_id:raise HTTPException(404,"Call not found")
        if rec.status in TERMINAL_CALL_STATES:return {"ok":True,"status":rec.status}
        if rec.status=="CONNECTED":raise HTTPException(409,"Call is already connected")
        rec.status="DECLINED";rec.ended_at=datetime.now(timezone.utc);db.commit()
        await _push(rec.caller_id,{"type":"call_declined","call_id":rec.id,"status":"DECLINED"})
        return {"ok":True,"status":"DECLINED"}

    @router.post("/v24/calls/{call_id}/end")
    async def call_end(call_id:str,u=Depends(current_user),db:Session=Depends(dep_db)):
        rec=db.get(CallRecord,call_id)
        if not rec or u.id not in (rec.caller_id,rec.callee_id):raise HTTPException(404,"Call not found")
        if rec.status in TERMINAL_CALL_STATES:return {"ok":True,"status":rec.status}
        other=rec.callee_id if u.id==rec.caller_id else rec.caller_id
        if rec.status in {"RINGING","CONNECTING"}:
            rec.status="MISSED" if u.id==rec.caller_id else "DECLINED"
        else:
            rec.status="ENDED"
        rec.ended_at=datetime.now(timezone.utc);db.commit()
        await _push(other,{"type":"call_ended","call_id":rec.id,"status":rec.status})
        return {"ok":True,"status":rec.status}

    # -------- Status / Updates --------
    def allowed(s,viewer):
        if s.user_id==viewer:return True
        allow={int(x) for x in s.allow_user_ids.split(',') if x.isdigit()};exclude={int(x) for x in s.exclude_user_ids.split(',') if x.isdigit()}
        if viewer in exclude:return False
        if s.visibility=="SELECTED":return viewer in allow
        return True
    def sj(db,s,viewer):
        owner=db.get(User,s.user_id);views=int(db.scalar(select(func.count()).select_from(StatusView).where(StatusView.status_id==s.id)) or 0);seen=db.get(StatusView,{"status_id":s.id,"viewer_id":viewer}) is not None
        return {"id":s.id,"user":_user_json(owner),"kind":s.kind,"text":s.text,"media_url":f"/v24/status/{s.id}/media" if s.media_key else None,"mime_type":s.mime_type,"visibility":s.visibility,"created_at":s.created_at.isoformat(),"expires_at":s.expires_at.isoformat(),"view_count":views if s.user_id==viewer else None,"viewed":seen}
    @router.get("/v24/status")
    def statuses(u=Depends(current_user),db:Session=Depends(dep_db)):
        now=datetime.now(timezone.utc);rows=db.scalars(select(StatusPost).where(StatusPost.expires_at>now).order_by(StatusPost.created_at.desc()).limit(300)).all();return [sj(db,s,u.id) for s in rows if allowed(s,u.id)]
    @router.post("/v24/status/text")
    def status_text(body:TextIn,u=Depends(current_user),db:Session=Depends(dep_db)):
        now=datetime.now(timezone.utc);s=StatusPost(user_id=u.id,kind="TEXT",text=body.text[:1500],created_at=now,expires_at=now+timedelta(hours=24));db.add(s);db.commit();db.refresh(s);return sj(db,s,u.id)
    @router.post("/v24/status/media")
    async def status_media(file:UploadFile=File(...),caption:str=Form(""),u=Depends(current_user),db:Session=Depends(dep_db)):
        mime=(file.content_type or "").split(";")[0].lower();kind="IMAGE" if mime.startswith("image/") else "VIDEO" if mime.startswith("video/") else None
        if not kind:raise HTTPException(415,"Status supports image or video")
        data=await file.read(20*1024*1024+1)
        if not data or len(data)>20*1024*1024:raise HTTPException(413,"Status media must be 20 MB or less")
        now=datetime.now(timezone.utc);s=StatusPost(user_id=u.id,kind=kind,text=caption[:1500],media_key=media_store.store(data),mime_type=mime,created_at=now,expires_at=now+timedelta(hours=24));db.add(s);db.commit();db.refresh(s);return sj(db,s,u.id)
    @router.post("/v24/status/{sid}/view")
    def status_view(sid:int,u=Depends(current_user),db:Session=Depends(dep_db)):
        s=db.get(StatusPost,sid)
        if not s or utc_dt(s.expires_at)<=datetime.now(timezone.utc) or not allowed(s,u.id):raise HTTPException(404,"Status not found")
        if s.user_id!=u.id and not db.get(StatusView,{"status_id":sid,"viewer_id":u.id}):db.add(StatusView(status_id=sid,viewer_id=u.id));db.commit()
        return sj(db,s,u.id)
    @router.get("/v24/status/{sid}/media")
    def status_file(sid:int,u=Depends(current_user),db:Session=Depends(dep_db)):
        s=db.get(StatusPost,sid)
        if not s or not s.media_key or not allowed(s,u.id):raise HTTPException(404,"Status not found")
        return StreamingResponse(media_store.stream(s.media_key),media_type=s.mime_type or "application/octet-stream")
    @router.delete("/v24/status/{sid}")
    def status_delete(sid:int,u=Depends(current_user),db:Session=Depends(dep_db)):
        s=db.get(StatusPost,sid)
        if not s or s.user_id!=u.id:raise HTTPException(404,"Status not found")
        db.delete(s);db.commit();return {"ok":True}

    # -------- Social IQ memory --------
    def mj(db,m):
        c=db.get(Chat,m.chat_id) if m.chat_id else None;other=None
        if c:other=db.get(User,c.user2_id if c.user1_id==m.user_id else c.user1_id)
        return {"id":m.id,"chat_id":m.chat_id,"contact":other.display_name if other else None,"memory_type":m.memory_type,"title":m.title,"detail":m.detail,"source_message_id":m.source_message_id,"due_at":m.due_at.isoformat() if m.due_at else None,"resolved":m.resolved,"created_at":m.created_at.isoformat()}
    @router.get("/v24/social-iq/memories")
    def memories(u=Depends(current_user),db:Session=Depends(dep_db)):
        rows=db.scalars(select(SocialMemory).where(SocialMemory.user_id==u.id,SocialMemory.resolved.is_(False)).order_by(SocialMemory.created_at.desc()).limit(100)).all();return [mj(db,m) for m in rows]
    @router.post("/v24/social-iq/memories")
    def memory_add(body:SocialMemoryIn,u=Depends(current_user),db:Session=Depends(dep_db)):
        if body.chat_id:
            c=db.get(Chat,body.chat_id)
            if not c or u.id not in (c.user1_id,c.user2_id):raise HTTPException(404,"Chat not found")
        m=SocialMemory(user_id=u.id,chat_id=body.chat_id,memory_type=body.memory_type[:24],title=body.title.strip(),detail=body.detail[:2000],source_message_id=body.source_message_id);db.add(m);db.commit();db.refresh(m);return mj(db,m)
    @router.delete("/v24/social-iq/memories/{mid}")
    def memory_delete(mid:int,u=Depends(current_user),db:Session=Depends(dep_db)):
        m=db.get(SocialMemory,mid)
        if not m or m.user_id!=u.id:raise HTTPException(404,"Memory not found")
        db.delete(m);db.commit();return {"ok":True}
    @router.post("/v24/social-iq/scan")
    def memory_scan(u=Depends(current_user),db:Session=Depends(dep_db)):
        cids=[c.id for c in db.scalars(select(Chat).where(or_(Chat.user1_id==u.id,Chat.user2_id==u.id))).all()]
        if not cids:return {"added":0,"items":[]}
        rows=db.scalars(select(Message).where(Message.chat_id.in_(cids)).order_by(Message.id.desc()).limit(240)).all()[::-1];key=os.getenv("ANTHROPIC_API_KEY","").strip()
        if not key:return {"added":0,"items":[],"note":"Anthropic is required for Social IQ extraction."}
        transcript=[]
        for m in rows:
            c=db.get(Chat,m.chat_id);other=db.get(User,c.user2_id if c.user1_id==u.id else c.user1_id);sender=db.get(User,m.sender_id);transcript.append(f"[message_id:{m.id} chat_id:{m.chat_id} contact:{other.display_name} sender:{sender.display_name}] {m.text}")
        from anthropic import Anthropic
        prompt='Extract only explicit PROMISE, FOLLOW_UP, PLAN, ADDRESS, DEADLINE or IMPORTANT communication items. Do not infer sensitive traits. Return JSON only: {"items":[{"message_id":1,"chat_id":1,"type":"FOLLOW_UP","title":"short title","detail":"supported detail"}]}. Max 12.\n'+"\n".join(transcript)[-26000:]
        msg=Anthropic(api_key=key).messages.create(model=os.getenv("ANTHROPIC_MODEL","claude-sonnet-4-6"),max_tokens=1200,temperature=0,messages=[{"role":"user","content":prompt}]);raw="".join(x.text for x in msg.content if getattr(x,"type","")=="text").strip().removeprefix("```json").removesuffix("```").strip()
        try:items=json.loads(raw).get("items",[])
        except:items=[]
        added=[]
        for x in items[:12]:
            mid=int(x.get("message_id") or 0);source=db.get(Message,mid)
            if not source or source.chat_id not in cids:continue
            typ=str(x.get("type") or "IMPORTANT")[:24]
            if db.scalar(select(SocialMemory).where(SocialMemory.user_id==u.id,SocialMemory.source_message_id==mid,SocialMemory.memory_type==typ)):continue
            m=SocialMemory(user_id=u.id,chat_id=source.chat_id,memory_type=typ,title=str(x.get("title") or "Important conversation item")[:160],detail=str(x.get("detail") or "")[:2000],source_message_id=mid);db.add(m);db.flush();added.append(m)
        db.commit();return {"added":len(added),"items":[mj(db,m) for m in added]}
    @router.get("/v24/social-iq/brief")
    def memory_brief(u=Depends(current_user),db:Session=Depends(dep_db)):
        rows=db.scalars(select(SocialMemory).where(SocialMemory.user_id==u.id,SocialMemory.resolved.is_(False)).order_by(SocialMemory.created_at.desc()).limit(40)).all();return {"count":len(rows),"items":[mj(db,m) for m in rows[:12]],"promises":sum(m.memory_type=="PROMISE" for m in rows),"follow_ups":sum(m.memory_type=="FOLLOW_UP" for m in rows)}

def register_v24(app,current_user,get_db,push,push_tokens,user_json,msg_json):
    install(get_db,current_user,push,push_tokens,user_json,msg_json)
    register_routes(current_user)
    app.include_router(router)
