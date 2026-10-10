from .trust import check_text, media_capabilities, unavailable_result
import os, hashlib, hmac, secrets, logging, re, json
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Dict, Set
import jwt
from fastapi import FastAPI, HTTPException, Depends, Header, WebSocket, WebSocketDisconnect, UploadFile, File, Form, BackgroundTasks
from pydantic import BaseModel, Field
from fastapi.responses import StreamingResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import or_, select, func
from sqlalchemy.orm import Session
from .database import Base, engine, SessionLocal
from .migrations import apply_compat_migrations
from .models import (User, Chat, ChatSetting, Message, Moment, InsightEvent, MessageAttachment, PushDevice,
    BusinessProfile, BusinessKnowledge, BusinessChatSetting, BusinessCustomerMemory, VoiceNote, TrustHistory,
    MessageMeta, MessageReaction, MessageHidden, ChatPreference, UserPrivacy, UserBlock, AutoReplyReceipt)
from . import media_store, push_service
from .chat_agent import daily_brief, needs_reply, communication_profile, search_memory, summarize_chat, ask_agent
from .insights import CATEGORIES, DIRECTIONS, event_json, list_events, brief as insight_brief
from .business_agent import (profile_for, profile_json, knowledge_json, chat_setting_for,
    chat_setting_json, customer_memory_for, memory_json, business_reply, extract_document, learn_candidates)

SECRET = os.getenv("LEMMIQ_JWT_SECRET", "")
if len(SECRET) < 32 or SECRET.startswith("CHANGE_"):
    raise RuntimeError("Set a long random LEMMIQ_JWT_SECRET in backend/.env before starting the server")
app = FastAPI(title="LEMMIQ Server", version="2.10.8")
connections: Dict[int, Set[WebSocket]] = {}

@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)
    apply_compat_migrations(engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def hp(password: str, salt_hex: str | None = None):
    salt = bytes.fromhex(salt_hex) if salt_hex else secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 180000)
    return digest.hex(), salt.hex()

def make_token(uid: int):
    return jwt.encode({"sub": str(uid), "exp": datetime.now(timezone.utc)+timedelta(days=30)}, SECRET, algorithm="HS256")

def decode_token(token: str):
    try:
        return int(jwt.decode(token, SECRET, algorithms=["HS256"])["sub"])
    except Exception:
        raise HTTPException(401, "Invalid or expired token")

def current_user(authorization: str = Header(default=""), db: Session = Depends(get_db)):
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing bearer token")
    u = db.get(User, decode_token(authorization[7:]))
    if not u:
        raise HTTPException(401, "User not found")
    return u

def user_json(u: User):
    return {"id": u.id, "username": u.username, "display_name": u.display_name, "avatar": u.avatar, "avatar_url": f"/v24/profile/avatar/{u.id}" if u.avatar else None}

def ensure_member(db: Session, cid: int, uid: int):
    c = db.get(Chat, cid)
    if not c or uid not in (c.user1_id, c.user2_id):
        raise HTTPException(404, "Chat not found")
    return c

def get_settings(db: Session, cid: int, uid: int):
    s = db.get(ChatSetting, {"chat_id": cid, "user_id": uid})
    if not s:
        s = ChatSetting(chat_id=cid, user_id=uid)
        db.add(s); db.commit(); db.refresh(s)
    return s

def msg_json(m: Message, db: Session | None = None):
    meta = db.get(MessageMeta, m.id) if db is not None else None
    deleted = bool(meta and meta.deleted_for_everyone)
    effective_text = "This message was deleted" if deleted else ((meta.edited_text if meta and meta.edited_text is not None else m.text) or "")
    data = {"id": m.id, "chat_id": m.chat_id, "sender_id": m.sender_id, "text": effective_text,
            "created_at": m.created_at.isoformat(), "read_at": m.read_at.isoformat() if m.read_at else None,
            "ai_generated": m.ai_generated, "edited_at": meta.edited_at.isoformat() if meta and meta.edited_at else None,
            "deleted_for_everyone": deleted, "reply_to_message_id": meta.reply_to_message_id if meta else None}
    attach = None if deleted else (db.get(MessageAttachment, m.id) if db is not None else None)
    voice = db.get(VoiceNote, m.id) if db is not None and attach and attach.kind == "VOICE" else None
    data["attachment"] = ({"kind": attach.kind, "name": attach.original_name,
        "mime_type": attach.mime_type, "size_bytes": attach.size_bytes,
        "media_id": attach.message_id if attach.object_key else None,
        "contact_name": attach.contact_name, "contact_phone": attach.contact_phone,
        "duration_ms": voice.duration_ms if voice else None, "transcript": voice.transcript if voice else None}
        if attach else None)
    if db is not None:
        reactions = db.scalars(select(MessageReaction).where(MessageReaction.message_id == m.id)).all()
        grouped = {}
        for r in reactions:
            grouped.setdefault(r.emoji, []).append(r.user_id)
        data["reactions"] = [{"emoji": emoji, "user_ids": uids, "count": len(uids)} for emoji, uids in grouped.items()]
        if meta and meta.reply_to_message_id:
            parent = db.get(Message, meta.reply_to_message_id)
            if parent:
                pm = db.get(MessageMeta, parent.id)
                ptext = "This message was deleted" if pm and pm.deleted_for_everyone else ((pm.edited_text if pm and pm.edited_text is not None else parent.text) or "")
                data["reply_to"] = {"id": parent.id, "sender_id": parent.sender_id, "text": ptext[:300]}
            else:
                data["reply_to"] = None
        else:
            data["reply_to"] = None
    return data

def push_tokens(db:Session, uid:int):
    return [x.token for x in db.scalars(select(PushDevice).where(PushDevice.user_id == uid)).all()]

def unread_count_for_user(db:Session, uid:int):
    cids=[c.id for c in db.scalars(select(Chat).where(or_(Chat.user1_id==uid,Chat.user2_id==uid))).all()]
    if not cids:
        return 0
    return int(db.scalar(
        select(func.count()).select_from(Message).where(
            Message.chat_id.in_(cids),
            Message.sender_id != uid,
            Message.read_at.is_(None)
        )
    ) or 0)

def chat_json(db: Session, c: Chat, uid: int):
    oid = c.user2_id if c.user1_id == uid else c.user1_id
    other = db.get(User, oid)
    s = get_settings(db, c.id, uid)
    pref = db.get(ChatPreference, {"chat_id": c.id, "user_id": uid})
    if not pref:
        pref = ChatPreference(chat_id=c.id, user_id=uid)
        db.add(pref); db.commit(); db.refresh(pref)
    hidden_ids = select(MessageHidden.message_id).where(MessageHidden.user_id == uid)
    last = db.scalar(select(Message).where(Message.chat_id == c.id, ~Message.id.in_(hidden_ids)).order_by(Message.id.desc()).limit(1))
    last_text = None
    if last:
        lm = db.get(MessageMeta, last.id)
        last_text = "This message was deleted" if lm and lm.deleted_for_everyone else ((lm.edited_text if lm and lm.edited_text is not None else last.text) or "")
    unread = db.scalar(select(func.count()).select_from(Message).where(
        Message.chat_id == c.id, Message.sender_id != uid, Message.read_at.is_(None), ~Message.id.in_(hidden_ids)
    )) or 0
    return {"id": c.id, "other_user": user_json(other), "category": s.category, "ai_mode": s.ai_mode, "tone": s.tone,
            "last_message": last_text, "updated_at": c.updated_at.isoformat(), "unread": int(unread),
            "pinned": pref.pinned, "archived": pref.archived, "favourite": pref.favourite,
            "muted_until": pref.muted_until.isoformat() if pref.muted_until else None, "draft_text": pref.draft_text}

def sensitive(text: str):
    t = text.lower()
    keywords = ["password", "otp", "bank", "transfer", "payment", "court", "lawyer", "doctor", "hospital", "emergency",
                "break up", "divorce", "pregnant", "sex", "nude", "loan", "contract", "credit card"]
    return any(k in t for k in keywords)

def ai_reply(category, tone, history, incoming):
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        if category == "WORK": return "Thanks for the update. I’ll check this and get back to you shortly."
        if category in ("PARTNER", "DATING"): return "Got you ❤️ I’ll reply properly in a moment."
        if category in ("CUSTOMER", "SALES"): return "Thanks for reaching out. I’m checking this now and will update you shortly."
        if category == "FAMILY": return "Sounds good 😊 I’ll confirm shortly."
        return "Got you — I’ll get back to you shortly."
    from anthropic import Anthropic
    client = Anthropic(api_key=key)
    prompt = f"""You are LEMMIQ, an AI communication copilot inside a private messenger.
Category: {category}
Tone: {tone}
Recent conversation:
{history[-14000:]}
Latest incoming:
{incoming}
Write ONE concise natural reply. Match the language/style. Never invent facts, completed actions, money, availability, appointments or promises. Output only the reply."""
    m = client.messages.create(model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6"), max_tokens=180, temperature=0.5, messages=[{"role":"user","content":prompt}])
    return "".join(x.text for x in m.content if getattr(x, "type", "") == "text").strip()

async def push(uid: int, payload: dict):
    dead = []
    for ws in list(connections.get(uid, set())):
        try:
            await ws.send_json(payload)
        except Exception:
            dead.append(ws)
    for ws in dead:
        connections.get(uid, set()).discard(ws)

class Login(BaseModel):
    username: str = Field(min_length=3, max_length=24)
    password: str = Field(min_length=6, max_length=128)
class Register(Login):
    display_name: str = Field(min_length=1, max_length=50)
    referral_code: str | None = Field(default=None, max_length=40)
class Direct(BaseModel):
    user_id: int
class Msg(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
class Settings(BaseModel):
    category: str
    ai_mode: str
    tone: str
class MomentIn(BaseModel):
    text: str = Field(min_length=1, max_length=500)

class AgentAskIn(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    days: int = Field(default=30, ge=1, le=365)
    external_context: list[dict] = Field(default_factory=list,max_length=30)

@app.get("/health")
def health():
    return {"ok": True, "name": "LEMMIQ", "version": "2.10.8"}

@app.get("/me")
def me(u: User = Depends(current_user)):
    return user_json(u)

@app.post("/register")
def register(body: Register, db: Session = Depends(get_db)):
    username = body.username.strip().lower()
    if not username.replace("_", "").isalnum():
        raise HTTPException(400, "Username can only use letters, numbers and underscore")
    if db.scalar(select(User).where(func.lower(User.username) == username)):
        raise HTTPException(409, "Username already taken")

    referral_code = (body.referral_code or "").strip().upper()
    if referral_code:
        from .v28 import validate_signup_referral
        validate_signup_referral(db, referral_code)

    ph, salt = hp(body.password)
    u = User(username=username, display_name=body.display_name.strip(), password_hash=ph, salt=salt)
    db.add(u)
    db.flush()

    if referral_code:
        from .v28 import apply_signup_referral
        apply_signup_referral(db, u, referral_code)

    db.commit()
    db.refresh(u)
    return {"token": make_token(u.id), "user": user_json(u)}

@app.post("/login")
def login(body: Login, db: Session = Depends(get_db)):
    u = db.scalar(select(User).where(func.lower(User.username) == body.username.strip().lower()))
    if not u:
        raise HTTPException(401, "Incorrect username or password")
    got, _ = hp(body.password, u.salt)
    if not hmac.compare_digest(got, u.password_hash):
        raise HTTPException(401, "Incorrect username or password")
    return {"token": make_token(u.id), "user": user_json(u)}

@app.get("/users/search")
def search_users(q: str, u: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(User).where(User.id != u.id, or_(User.username.ilike(f"%{q}%"), User.display_name.ilike(f"%{q}%"))).limit(30)).all()
    return [user_json(x) for x in rows]

@app.get("/chats")
def chats(u: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(Chat).where(or_(Chat.user1_id == u.id, Chat.user2_id == u.id)).order_by(Chat.updated_at.desc())).all()
    return [chat_json(db, c, u.id) for c in rows]

@app.post("/chats/direct")
def direct(body: Direct, u: User = Depends(current_user), db: Session = Depends(get_db)):
    if body.user_id == u.id:
        raise HTTPException(400, "Cannot message yourself")
    if not db.get(User, body.user_id):
        raise HTTPException(404, "User not found")
    if db.get(UserBlock, {"blocker_id": u.id, "blocked_id": body.user_id}) or db.get(UserBlock, {"blocker_id": body.user_id, "blocked_id": u.id}):
        raise HTTPException(403, "This conversation is blocked")
    a, b = sorted([u.id, body.user_id])
    c = db.scalar(select(Chat).where(Chat.user1_id == a, Chat.user2_id == b))
    if not c:
        c = Chat(user1_id=a, user2_id=b)
        db.add(c); db.commit(); db.refresh(c)
        db.add_all([ChatSetting(chat_id=c.id, user_id=a), ChatSetting(chat_id=c.id, user_id=b)])
        db.commit()
    return chat_json(db, c, u.id)

@app.get("/chats/{cid}/messages")
def messages(cid: int, u: User = Depends(current_user), db: Session = Depends(get_db)):
    ensure_member(db, cid, u.id)
    hidden_ids = select(MessageHidden.message_id).where(MessageHidden.user_id == u.id)
    rows = db.scalars(select(Message).where(Message.chat_id == cid, ~Message.id.in_(hidden_ids)).order_by(Message.id.asc()).limit(700)).all()
    return [msg_json(m, db) for m in rows]

@app.post("/chats/{cid}/messages")
async def send(cid: int, body: Msg, background: BackgroundTasks, u: User = Depends(current_user), db: Session = Depends(get_db)):
    c = ensure_member(db, cid, u.id)
    oid = c.user2_id if c.user1_id == u.id else c.user1_id
    if db.get(UserBlock, {"blocker_id": u.id, "blocked_id": oid}) or db.get(UserBlock, {"blocker_id": oid, "blocked_id": u.id}):
        raise HTTPException(403, "This conversation is blocked")
    m = Message(chat_id=cid, sender_id=u.id, text=body.text.strip())
    c.updated_at = datetime.now(timezone.utc)
    db.add(m); db.commit(); db.refresh(m)
    data = msg_json(m, db)
    await push(oid, {"type":"message","data":data}); await push(u.id, {"type":"message","data":data})
    background.add_task(push_service.notify, push_tokens(db, oid), u.display_name, cid, m.text, unread_count_for_user(db, oid))
    # Business Agent AUTO takes priority over the personal Auto agent when enabled for this chat.
    bs = db.get(BusinessChatSetting, {"user_id": oid, "chat_id": cid})
    bp = db.get(BusinessProfile, oid)
    business_handled = False
    if bs and bp and bp.enabled and bs.enabled and bs.mode == "AUTO" and not sensitive(body.text):
        try:
            br = business_reply(db, oid, cid, body.text)
            if br.get("reply") and int(br.get("confidence", 0)) >= int(bp.auto_threshold or 90) and not br.get("requires_review", True):
                if db.get(AutoReplyReceipt, m.id):
                    return data
                auto = Message(chat_id=cid, sender_id=oid, text=br["reply"], ai_generated=True)
                c.updated_at = datetime.now(timezone.utc)
                db.add(auto); db.flush()
                db.add(AutoReplyReceipt(trigger_message_id=m.id,responder_user_id=oid,reply_message_id=auto.id))
                db.commit(); db.refresh(auto)
                try:
                    from .v29 import track_shadow_event
                    track_shadow_event(db, oid, "AUTO_MESSAGE", note=f"business-auto chat:{cid}")
                    db.commit()
                except Exception:
                    db.rollback()
                ad = msg_json(auto, db)
                await push(oid, {"type":"message","data":ad}); await push(u.id, {"type":"message","data":ad})
                background.add_task(push_service.notify, push_tokens(db, u.id), db.get(User, oid).display_name, cid, auto.text, unread_count_for_user(db, u.id))
                business_handled = True
        except Exception as e:
            print("Business AUTO error:", e)
    s = get_settings(db, cid, oid)
    if not business_handled and not (bs and bp and bp.enabled and bs.enabled) and s.ai_mode == "AUTO" and not sensitive(body.text):
        hist = db.scalars(select(Message).where(Message.chat_id == cid).order_by(Message.id.desc()).limit(50)).all()[::-1]
        lines = []
        for x in hist:
            sender = db.get(User, x.sender_id)
            lines.append(f"{sender.display_name}: {x.text}")
        try:
            if db.get(AutoReplyReceipt, m.id):
                return data
            reply = ai_reply(s.category, s.tone, "\n".join(lines), body.text)
            auto = Message(chat_id=cid, sender_id=oid, text=reply, ai_generated=True)
            c.updated_at = datetime.now(timezone.utc)
            db.add(auto); db.flush()
            db.add(AutoReplyReceipt(trigger_message_id=m.id,responder_user_id=oid,reply_message_id=auto.id))
            db.commit(); db.refresh(auto)
            try:
                from .v29 import track_shadow_event
                track_shadow_event(db, oid, "AUTO_MESSAGE", note=f"personal-auto chat:{cid}")
                db.commit()
            except Exception:
                db.rollback()
            ad = msg_json(auto, db)
            await push(oid, {"type":"message","data":ad}); await push(u.id, {"type":"message","data":ad})
            background.add_task(push_service.notify, push_tokens(db, u.id), db.get(User, oid).display_name, cid, auto.text, unread_count_for_user(db, u.id))
        except Exception as e:
            print("AI AUTO error:", e)
    return data

@app.post("/chats/{cid}/read")
def mark_read(cid: int, u: User = Depends(current_user), db: Session = Depends(get_db)):
    ensure_member(db, cid, u.id)
    rows = db.scalars(select(Message).where(Message.chat_id == cid, Message.sender_id != u.id, Message.read_at.is_(None))).all()
    ts = datetime.now(timezone.utc)
    for m in rows:
        m.read_at = ts
    db.commit()
    return {"ok": True}

@app.put("/chats/{cid}/settings")
def update_settings(cid: int, body: Settings, u: User = Depends(current_user), db: Session = Depends(get_db)):
    c = ensure_member(db, cid, u.id)
    cats = {"PARTNER","DATING","BESTIE","FRIEND","FAMILY","WORK","CUSTOMER","SALES","STUDY","CUSTOM"}
    modes = {"OFF","ASSIST","AUTO"}
    if body.category not in cats or body.ai_mode not in modes:
        raise HTTPException(400, "Invalid settings")
    s = get_settings(db, cid, u.id)
    s.category = body.category; s.ai_mode = body.ai_mode; s.tone = body.tone[:40]
    db.commit()
    return chat_json(db, c, u.id)

@app.post("/chats/{cid}/suggest")
def suggest(cid: int, u: User = Depends(current_user), db: Session = Depends(get_db)):
    ensure_member(db, cid, u.id)
    s = get_settings(db, cid, u.id)
    rows = db.scalars(select(Message).where(Message.chat_id == cid).order_by(Message.id.desc()).limit(50)).all()[::-1]
    incoming = next((x.text for x in reversed(rows) if x.sender_id != u.id), None)
    if not incoming:
        raise HTTPException(400, "No incoming message")
    lines=[]
    for x in rows:
        sender=db.get(User,x.sender_id); lines.append(f"{sender.display_name}: {x.text}")
    return {"reply": ai_reply(s.category, s.tone, "\n".join(lines), incoming)}

@app.get("/moments")
def moments(u: User = Depends(current_user), db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    rows = db.scalars(select(Moment).where(Moment.expires_at > now).order_by(Moment.id.desc()).limit(100)).all()
    return [{"id":m.id,"user":user_json(db.get(User,m.user_id)),"text":m.text,"created_at":m.created_at.isoformat(),"expires_at":m.expires_at.isoformat()} for m in rows]

@app.post("/moments")
def post_moment(body: MomentIn, u: User = Depends(current_user), db: Session = Depends(get_db)):
    created = datetime.now(timezone.utc)
    m = Moment(user_id=u.id, text=body.text.strip(), created_at=created, expires_at=created+timedelta(hours=24))
    db.add(m); db.commit(); db.refresh(m)
    return {"id":m.id,"user":user_json(u),"text":m.text,"created_at":m.created_at.isoformat(),"expires_at":m.expires_at.isoformat()}

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket, token: str):
    try:
        uid = decode_token(token)
    except HTTPException:
        await ws.close(code=4401); return
    await ws.accept(); connections.setdefault(uid,set()).add(ws)
    try:
        await ws.send_json({"type":"connected","user_id":uid})
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        connections.get(uid,set()).discard(ws)


class TrustIn(BaseModel):
    text: str = Field(min_length=1, max_length=12000)

def trust_history_json(x: TrustHistory):
    return {"id":x.id,"checked_text":x.checked_text,"status":x.status,"confidence":x.confidence,"summary":x.summary,
            "reasons":json.loads(x.reasons_json or "[]"),"sources":json.loads(x.sources_json or "[]"),"advice":x.advice,
            "checked_at":x.checked_at.isoformat()}

@app.post("/trust/check")
def trust_check(body: TrustIn, refresh: bool=False, u: User = Depends(current_user), db: Session = Depends(get_db)):
    clean=" ".join(body.text.strip().split());digest=hashlib.sha256(clean.lower().encode()).hexdigest();cutoff=datetime.now(timezone.utc)-timedelta(hours=24)
    if not refresh:
        cached=db.scalar(select(TrustHistory).where(TrustHistory.user_id==u.id,TrustHistory.content_hash==digest,TrustHistory.checked_at>=cutoff).order_by(TrustHistory.checked_at.desc()).limit(1))
        if cached:
            out=trust_history_json(cached);out["cached"]=True;return out
    trust_success=True
    try:result=check_text(body.text)
    except Exception:
        trust_success=False
        logging.getLogger("lemmiq.trust").exception("Trust endpoint failed");result=unavailable_result()
    try:
        from .v29 import track_shadow_event
        track_shadow_event(db,u.id,"TRUST",success=trust_success)
    except Exception:
        logging.getLogger("lemmiq.v29").exception("Shadow Trust tracking failed")
    h=TrustHistory(user_id=u.id,content_hash=digest,checked_text=body.text[:12000],status=str(result.get("status","UNVERIFIED")),confidence=int(result.get("confidence",0) or 0),summary=str(result.get("summary","") or ""),reasons_json=json.dumps(result.get("reasons",[]) or []),sources_json=json.dumps(result.get("sources",[]) or []),advice=str(result.get("advice","") or ""));db.add(h);db.commit();db.refresh(h);out=trust_history_json(h);out["cached"]=False;return out

@app.get("/trust/history")
def trust_history(q: str="", u: User = Depends(current_user), db: Session = Depends(get_db)):
    stmt=select(TrustHistory).where(TrustHistory.user_id==u.id)
    if q.strip():stmt=stmt.where(or_(TrustHistory.checked_text.ilike(f"%{q}%"),TrustHistory.summary.ilike(f"%{q}%")))
    rows=db.scalars(stmt.order_by(TrustHistory.checked_at.desc()).limit(100)).all();return [trust_history_json(x) for x in rows]

@app.delete("/trust/history/{hid}")
def delete_trust_history(hid:int,u:User=Depends(current_user),db:Session=Depends(get_db)):
    x=db.get(TrustHistory,hid)
    if not x or x.user_id!=u.id:raise HTTPException(404,"Trust result not found")
    db.delete(x);db.commit();return {"ok":True}

@app.delete("/trust/history")
def clear_trust_history(u:User=Depends(current_user),db:Session=Depends(get_db)):
    rows=db.scalars(select(TrustHistory).where(TrustHistory.user_id==u.id)).all()
    for x in rows:db.delete(x)
    db.commit();return {"ok":True}

@app.get("/trust/media-capabilities")
def trust_media(u: User = Depends(current_user)):
    return media_capabilities()


@app.get("/agent/brief")
def agent_brief(u: User = Depends(current_user), db: Session = Depends(get_db)):
    return daily_brief(db, u.id)

@app.get("/agent/needs-reply")
def agent_needs_reply(u: User = Depends(current_user), db: Session = Depends(get_db)):
    return needs_reply(db, u.id)

@app.get("/agent/profile")
def agent_profile(days: int = 30, u: User = Depends(current_user), db: Session = Depends(get_db)):
    return communication_profile(db, u.id, days=max(1, min(days, 365)))

@app.get("/agent/search")
def agent_search(q: str, u: User = Depends(current_user), db: Session = Depends(get_db)):
    return search_memory(db, u.id, q)

@app.get("/agent/chats/{cid}/summary")
def agent_chat_summary(cid: int, u: User = Depends(current_user), db: Session = Depends(get_db)):
    try:
        result = summarize_chat(db, u.id, cid)
        try:
            from .v29 import track_shadow_event
            track_shadow_event(db, u.id, "CHAT_SUMMARY", note=f"chat:{cid}")
            db.commit()
        except Exception:
            db.rollback()
        return result
    except ValueError:
        raise HTTPException(404, "Chat not found")

@app.post("/agent/ask")
def agent_ask(body: AgentAskIn, u: User = Depends(current_user), db: Session = Depends(get_db)):
    clean=[]
    for x in body.external_context:
        if isinstance(x,dict) and x.get("source") in {"WhatsApp","SMS"}:
            clean.append({"source":x["source"],"contact":str(x.get("contact",""))[:80],
                          "text":str(x.get("text",""))[:500]})
    result = ask_agent(db, u.id, body.question, body.days, clean)
    try:
        from .v29 import track_shadow_event
        track_shadow_event(db, u.id, "Q_AGENT")
        db.commit()
    except Exception:
        db.rollback()
    return result


class InsightIn(BaseModel):
    client_event_id: str = Field(min_length=8, max_length=80)
    category: str = Field(max_length=20)
    source: str = Field(max_length=80)
    title: str = Field(max_length=100)
    detail: str = Field(default="",max_length=220)
    amount_cents: int | None = Field(default=None, ge=0, le=100_000_000_000)
    direction: str = Field(default="UNKNOWN", max_length=12)
    occurred_at: datetime

class InsightEdit(BaseModel):
    category: str = Field(max_length=20)
    source: str = Field(max_length=80)
    title: str = Field(max_length=100)
    detail: str = Field(default="", max_length=220)
    amount_cents: int | None = Field(default=None, ge=0, le=100_000_000_000)
    direction: str = Field(default="UNKNOWN", max_length=12)
    occurred_at: datetime

def apply_insight_edit(e: InsightEvent, body: InsightEdit):
    if body.category not in CATEGORIES or body.direction not in DIRECTIONS:
        raise HTTPException(422, "Unsupported category or direction")
    when = body.occurred_at if body.occurred_at.tzinfo else body.occurred_at.replace(tzinfo=timezone.utc)
    if when > datetime.now(timezone.utc) + timedelta(minutes=5) or when < datetime.now(timezone.utc) - timedelta(days=90):
        raise HTTPException(422, "Event outside allowed window")
    e.category = body.category
    e.source = body.source.strip()[:80]
    e.title = body.title.strip()[:100]
    e.detail = body.detail.strip()[:220]
    e.amount_cents = body.amount_cents
    e.direction = body.direction
    e.occurred_at = when

@app.post("/insights/events")
def ingest_event(body: InsightIn, u: User = Depends(current_user), db: Session = Depends(get_db)):
    if body.category not in CATEGORIES or body.direction not in DIRECTIONS:
        raise HTTPException(422,"Unsupported category or direction")
    when=body.occurred_at if body.occurred_at.tzinfo else body.occurred_at.replace(tzinfo=timezone.utc)
    if when > datetime.now(timezone.utc)+timedelta(minutes=5) or when < datetime.now(timezone.utc)-timedelta(days=90):
        raise HTTPException(422,"Event outside allowed window")
    existing=db.scalar(select(InsightEvent).where(InsightEvent.user_id==u.id,InsightEvent.client_event_id==body.client_event_id))
    if existing: return event_json(existing)
    e=InsightEvent(user_id=u.id,client_event_id=body.client_event_id, category=body.category,
       source=body.source, title=body.title,detail=body.detail,amount_cents=body.amount_cents,
       direction=body.direction,occurred_at=when)
    db.add(e);db.commit();db.refresh(e)
    return event_json(e)

@app.get("/insights/brief")
def get_insights(days:int=30,u:User=Depends(current_user),db:Session=Depends(get_db)):
    return insight_brief(db,u.id,days)

@app.put("/insights/client-events/{client_event_id}")
def update_insight_by_client(client_event_id: str, body: InsightEdit,
                             u: User = Depends(current_user), db: Session = Depends(get_db)):
    e = db.scalar(select(InsightEvent).where(
        InsightEvent.user_id == u.id,
        InsightEvent.client_event_id == client_event_id
    ))
    if not e:
        raise HTTPException(404, "Detected event not found")
    apply_insight_edit(e, body)
    db.commit(); db.refresh(e)
    return event_json(e)

@app.delete("/insights/client-events/{client_event_id}")
def delete_insight_by_client(client_event_id: str,
                             u: User = Depends(current_user), db: Session = Depends(get_db)):
    e = db.scalar(select(InsightEvent).where(
        InsightEvent.user_id == u.id,
        InsightEvent.client_event_id == client_event_id
    ))
    if not e:
        raise HTTPException(404, "Detected event not found")
    db.delete(e); db.commit()
    return {"deleted": True, "client_event_id": client_event_id}

@app.put("/insights/events/{event_id}")
def update_insight_event(event_id: int, body: InsightEdit,
                         u: User = Depends(current_user), db: Session = Depends(get_db)):
    e = db.get(InsightEvent, event_id)
    if not e or e.user_id != u.id:
        raise HTTPException(404, "Detected event not found")
    apply_insight_edit(e, body)
    db.commit(); db.refresh(e)
    return event_json(e)

@app.delete("/insights/events/{event_id}")
def delete_insight_event(event_id: int,
                         u: User = Depends(current_user), db: Session = Depends(get_db)):
    e = db.get(InsightEvent, event_id)
    if not e or e.user_id != u.id:
        raise HTTPException(404, "Detected event not found")
    db.delete(e); db.commit()
    return {"deleted": True, "id": event_id}

@app.delete("/insights/events")
def delete_insights(scope: str = "ALL",
                    u: User = Depends(current_user), db: Session = Depends(get_db)):
    scope = scope.upper().strip()
    if scope not in {"ALL", "MONEY", "ACTIVITY"}:
        raise HTTPException(422, "scope must be ALL, MONEY or ACTIVITY")
    rows = db.scalars(select(InsightEvent).where(InsightEvent.user_id == u.id)).all()
    removed = 0
    for e in rows:
        should_delete = (
            scope == "ALL" or
            (scope == "MONEY" and e.category == "MONEY") or
            (scope == "ACTIVITY" and e.category != "MONEY")
        )
        if should_delete:
            db.delete(e); removed += 1
    db.commit()
    return {"deleted": True, "scope": scope, "count": removed}


# V1.7: Authenticated attachments, contacts, optional push registration and on-demand external reply assistance.
ALLOWED_MIME = {
    "image/jpeg":"PHOTO", "image/png":"PHOTO", "image/webp":"PHOTO",
    "video/mp4":"VIDEO", "video/webm":"VIDEO", "video/quicktime":"VIDEO",
    "application/pdf":"FILE", "text/plain":"FILE", "text/csv":"FILE",
    "application/zip":"FILE", "application/vnd.openxmlformats-officedocument.wordprocessingml.document":"FILE",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet":"FILE",
}
MAX_FILE_BYTES = 20 * 1024 * 1024

@app.post("/chats/{cid}/attachments")
async def upload_attachment(cid: int, background: BackgroundTasks, file: UploadFile = File(...),
                            caption: str = Form(default=""),
                            u: User = Depends(current_user), db: Session = Depends(get_db)):
    c = ensure_member(db,cid,u.id)
    mime=(file.content_type or "").split(";")[0].lower().strip()
    kind=ALLOWED_MIME.get(mime)
    if kind is None:
        raise HTTPException(415,"Unsupported file type. Use JPEG/PNG/WebP, MP4/WebM/MOV, PDF, TXT, CSV, ZIP, DOCX or XLSX.")
    payload=await file.read(MAX_FILE_BYTES + 1)
    if not payload or len(payload)>MAX_FILE_BYTES:
        raise HTTPException(413,"File must be between 1 byte and 20 MB")
    # Verify magic bytes for common content types to avoid trusting client MIME alone.
    if (mime=="image/jpeg" and not payload.startswith(b"\xff\xd8\xff")) or \
       (mime=="image/png" and not payload.startswith(b"\x89PNG\r\n\x1a\n")) or \
       (mime=="application/pdf" and not payload.startswith(b"%PDF-")) or \
       (mime=="application/zip" and not payload.startswith(b"PK\x03\x04")) or \
       (mime=="image/webp" and not (payload.startswith(b"RIFF") and payload[8:12]==b"WEBP")):
        raise HTTPException(415,"File bytes do not match the declared type")
    if mime == "video/mp4" and b"ftyp" not in payload[:16]:
        raise HTTPException(415,"Not an MP4 file")
    object_key=media_store.store(payload)
    original=(file.filename or "Attachment").replace("\\","/").split("/")[-1]
    original=re.sub(r"[^A-Za-z0-9 .()\-]", "_", original)[:190] or "Attachment"
    # Premium media UX: photos/videos show only a user-supplied caption.
    # The original filename remains available in attachment metadata / Media info.
    clean_caption=" ".join((caption or "").strip().split())[:1000]
    message_text=clean_caption if kind in {"PHOTO","VIDEO"} else (clean_caption or ("[File] " + original))
    m=Message(chat_id=cid,sender_id=u.id,text=message_text)
    c.updated_at=datetime.now(timezone.utc)
    db.add(m);db.flush()
    db.add(MessageAttachment(message_id=m.id,kind=kind,object_key=object_key,original_name=original,
                             mime_type=mime,size_bytes=len(payload)))
    db.commit();db.refresh(m)
    data=msg_json(m,db)
    oid=c.user2_id if c.user1_id==u.id else c.user1_id
    await push(oid,{"type":"message","data":data});await push(u.id,{"type":"message","data":data})
    notify_text = m.text or ("📷 Photo" if kind == "PHOTO" else "🎬 Video" if kind == "VIDEO" else "📎 Attachment")
    background.add_task(push_service.notify,push_tokens(db,oid),u.display_name,cid,notify_text,unread_count_for_user(db,oid))
    return data

class ContactShare(BaseModel):
    display_name: str = Field(min_length=1,max_length=120)
    phone: str = Field(min_length=3,max_length=35)

@app.post("/chats/{cid}/contacts")
async def share_contact(cid:int,body:ContactShare,background:BackgroundTasks,
                        u:User=Depends(current_user),db:Session=Depends(get_db)):
    c=ensure_member(db,cid,u.id)
    name=body.display_name.strip();phone=body.phone.strip()
    if not re.fullmatch(r"[+0-9() .\-]{3,35}",phone) or len(re.sub(r"\D","",phone))<3:
        raise HTTPException(422,"Invalid contact phone")
    m=Message(chat_id=cid,sender_id=u.id,text="[Contact] " + name)
    c.updated_at=datetime.now(timezone.utc)
    db.add(m);db.flush()
    db.add(MessageAttachment(message_id=m.id,kind="CONTACT",contact_name=name,contact_phone=phone))
    db.commit();db.refresh(m)
    data=msg_json(m,db)
    oid=c.user2_id if c.user1_id==u.id else c.user1_id
    await push(oid,{"type":"message","data":data});await push(u.id,{"type":"message","data":data})
    background.add_task(push_service.notify,push_tokens(db,oid),u.display_name,cid,m.text,unread_count_for_user(db,oid))
    return data

@app.get("/media/{message_id}")
def private_media(message_id:int,u:User=Depends(current_user),db:Session=Depends(get_db)):
    item=db.get(MessageAttachment,message_id)
    if not item or not item.object_key:
        raise HTTPException(404,"Attachment not found")
    message=db.get(Message,message_id)
    ensure_member(db,message.chat_id,u.id)
    safe_name=(item.original_name or "file").replace('"','').replace('\r','').replace('\n','')
    return StreamingResponse(media_store.stream(item.object_key),media_type=item.mime_type or "application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}"',
                 "Cache-Control":"private, no-store", "X-Content-Type-Options":"nosniff"})

class PushRegister(BaseModel):
    token: str = Field(min_length=20,max_length=300)

@app.get("/push/status")
def push_status(u:User=Depends(current_user),db:Session=Depends(get_db)):
    return {
        "firebase_configured": bool(push_service.configured()),
        "registered_devices": int(db.scalar(
            select(func.count()).select_from(PushDevice).where(PushDevice.user_id==u.id)
        ) or 0)
    }

@app.post("/push/register")
def register_push(body:PushRegister,u:User=Depends(current_user),db:Session=Depends(get_db)):
    existing=db.scalar(select(PushDevice).where(PushDevice.token==body.token))
    if existing:
        existing.user_id=u.id;existing.updated_at=datetime.now(timezone.utc)
    else:
        db.add(PushDevice(user_id=u.id,token=body.token))
    db.commit()
    return {"ok":True}

@app.delete("/push/unregister")
def unregister_push(body:PushRegister,u:User=Depends(current_user),db:Session=Depends(get_db)):
    row=db.scalar(select(PushDevice).where(PushDevice.token==body.token,PushDevice.user_id==u.id))
    if row:db.delete(row);db.commit()
    return {"ok":True}

class ExternalMessage(BaseModel):
    source: str = Field(pattern="^(WhatsApp|SMS)$")
    contact: str = Field(min_length=1,max_length=100)
    text: str = Field(min_length=1,max_length=700)

class ExternalAsk(BaseModel):
    contact: str = Field(min_length=1,max_length=100)
    source: str = Field(pattern="^(WhatsApp|SMS)$")
    tone: str = Field(default="Natural",max_length=40)
    messages: list[ExternalMessage] = Field(min_length=1,max_length=15)

@app.post("/external/suggest")
def external_suggest(body:ExternalAsk,u:User=Depends(current_user)):
    rows=[x for x in body.messages if x.source==body.source and x.contact==body.contact][-15:]
    if not rows:
        raise HTTPException(422,"No matching messages")
    hist="\n".join(f"{x.contact}: {x.text}" for x in rows)
    return {"reply":ai_reply("FRIEND",body.tone,hist,rows[-1].text),
            "note":"Draft only. Review and copy into the original app; LEMMIQ never sends it."}


# ---------------- LEMMIQ V1.8 BUSINESS BETA ----------------
BUSINESS_CATEGORIES = {"FAQ","SERVICE","PRICING","POLICY","HOURS","AREA","OTHER","APPROVED_REPLY"}
BUSINESS_MODES = {"OFF","ASSIST","AUTO"}

class BusinessProfileIn(BaseModel):
    enabled: bool = False
    business_name: str = Field(default="", max_length=120)
    business_type: str = Field(default="", max_length=100)
    description: str = Field(default="", max_length=4000)
    website: str = Field(default="", max_length=300)
    phone: str = Field(default="", max_length=60)
    email: str = Field(default="", max_length=160)
    hours: str = Field(default="", max_length=2000)
    service_area: str = Field(default="", max_length=2000)
    tone: str = Field(default="Professional", max_length=40)
    currency: str = Field(default="AUD", max_length=12)
    auto_threshold: int = Field(default=90, ge=70, le=100)

class BusinessKnowledgeIn(BaseModel):
    category: str = Field(default="OTHER", max_length=24)
    title: str = Field(min_length=1, max_length=120)
    content: str = Field(min_length=1, max_length=60000)
    source: str = Field(default="Manual", max_length=180)
    approved: bool = True
    active: bool = True

class BusinessChatIn(BaseModel):
    enabled: bool = False
    mode: str = Field(default="ASSIST", max_length=12)
    customer_label: str = Field(default="", max_length=80)

class BusinessMemoryIn(BaseModel):
    notes: str = Field(default="", max_length=5000)
    tags: str = Field(default="", max_length=300)

class LearnCandidateIn(BaseModel):
    category: str = Field(default="OTHER", max_length=24)
    title: str = Field(min_length=1, max_length=120)
    content: str = Field(min_length=1, max_length=1800)

@app.get("/business/profile")
def get_business_profile(u:User=Depends(current_user),db:Session=Depends(get_db)):
    return profile_json(profile_for(db,u.id))

@app.put("/business/profile")
def put_business_profile(body:BusinessProfileIn,u:User=Depends(current_user),db:Session=Depends(get_db)):
    p=profile_for(db,u.id)
    for field in ("enabled","business_name","business_type","description","website","phone","email","hours","service_area","tone","currency","auto_threshold"):
        setattr(p,field,getattr(body,field))
    p.updated_at=datetime.now(timezone.utc);db.commit();db.refresh(p)
    return profile_json(p)

@app.get("/business/knowledge")
def get_business_knowledge(u:User=Depends(current_user),db:Session=Depends(get_db)):
    rows=db.scalars(select(BusinessKnowledge).where(BusinessKnowledge.user_id==u.id).order_by(BusinessKnowledge.updated_at.desc()).limit(250)).all()
    return [knowledge_json(x) for x in rows]

@app.post("/business/knowledge")
def add_business_knowledge(body:BusinessKnowledgeIn,u:User=Depends(current_user),db:Session=Depends(get_db)):
    cat=body.category.upper()
    if cat not in BUSINESS_CATEGORIES: raise HTTPException(422,"Unsupported business knowledge category")
    k=BusinessKnowledge(user_id=u.id,category=cat,title=body.title.strip(),content=body.content.strip(),
        source=body.source.strip() or "Manual",approved=body.approved,active=body.active,updated_at=datetime.now(timezone.utc))
    db.add(k);db.commit();db.refresh(k);return knowledge_json(k)

@app.delete("/business/knowledge/{kid}")
def delete_business_knowledge(kid:int,u:User=Depends(current_user),db:Session=Depends(get_db)):
    k=db.get(BusinessKnowledge,kid)
    if not k or k.user_id!=u.id: raise HTTPException(404,"Knowledge item not found")
    db.delete(k);db.commit();return {"deleted":True}

@app.post("/business/knowledge/upload")
async def upload_business_knowledge(file:UploadFile=File(...),u:User=Depends(current_user),db:Session=Depends(get_db)):
    payload=await file.read(5*1024*1024+1)
    if not payload or len(payload)>5*1024*1024: raise HTTPException(413,"Knowledge document must be 1 byte to 5 MB")
    try: text=extract_document(file.filename or "document",file.content_type or "",payload)
    except ValueError as e: raise HTTPException(415,str(e))
    name=(file.filename or "Business document").replace("\\","/").split("/")[-1][:120]
    k=BusinessKnowledge(user_id=u.id,category="OTHER",title=name,content=text,source="Uploaded document",
        approved=True,active=True,updated_at=datetime.now(timezone.utc))
    db.add(k);db.commit();db.refresh(k);return knowledge_json(k)

@app.get("/business/chats/{cid}")
def get_business_chat(cid:int,u:User=Depends(current_user),db:Session=Depends(get_db)):
    ensure_member(db,cid,u.id)
    s=chat_setting_for(db,u.id,cid);m=customer_memory_for(db,u.id,cid)
    return {"setting":chat_setting_json(s),"memory":memory_json(m)}

@app.put("/business/chats/{cid}")
def put_business_chat(cid:int,body:BusinessChatIn,u:User=Depends(current_user),db:Session=Depends(get_db)):
    ensure_member(db,cid,u.id)
    mode=body.mode.upper()
    if mode not in BUSINESS_MODES: raise HTTPException(422,"Invalid business mode")
    s=chat_setting_for(db,u.id,cid);s.enabled=body.enabled;s.mode=mode;s.customer_label=body.customer_label.strip();s.updated_at=datetime.now(timezone.utc)
    db.commit();db.refresh(s);return chat_setting_json(s)

@app.put("/business/chats/{cid}/memory")
def put_business_memory(cid:int,body:BusinessMemoryIn,u:User=Depends(current_user),db:Session=Depends(get_db)):
    ensure_member(db,cid,u.id)
    m=customer_memory_for(db,u.id,cid);m.notes=body.notes.strip();m.tags=body.tags.strip();m.updated_at=datetime.now(timezone.utc)
    db.commit();db.refresh(m);return memory_json(m)

@app.post("/business/chats/{cid}/suggest")
def business_suggest(cid:int,u:User=Depends(current_user),db:Session=Depends(get_db)):
    ensure_member(db,cid,u.id)
    s=chat_setting_for(db,u.id,cid)
    if not s.enabled or s.mode=="OFF": raise HTTPException(409,"Enable Business Agent for this customer chat first")
    rows=db.scalars(select(Message).where(Message.chat_id==cid).order_by(Message.id.desc()).limit(50)).all()[::-1]
    incoming=next((x.text for x in reversed(rows) if x.sender_id!=u.id),None)
    if not incoming: raise HTTPException(400,"No incoming customer message")
    result = business_reply(db,u.id,cid,incoming)
    try:
        from .v29 import track_shadow_event
        track_shadow_event(db, u.id, "BUSINESS_AGENT", note=f"chat:{cid}")
        db.commit()
    except Exception:
        db.rollback()
    return result

@app.post("/business/chats/{cid}/learn")
def business_learn(cid:int,u:User=Depends(current_user),db:Session=Depends(get_db)):
    ensure_member(db,cid,u.id)
    return {"candidates":learn_candidates(db,u.id,cid),"note":"Candidates are not saved until you approve them."}

@app.post("/business/learn/approve")
def approve_business_learning(body:LearnCandidateIn,u:User=Depends(current_user),db:Session=Depends(get_db)):
    cat=body.category.upper()
    if cat not in BUSINESS_CATEGORIES: cat="OTHER"
    k=BusinessKnowledge(user_id=u.id,category=cat,title=body.title.strip(),content=body.content.strip(),source="Approved chat learning",
        approved=True,active=True,updated_at=datetime.now(timezone.utc))
    db.add(k);db.commit();db.refresh(k);return knowledge_json(k)




@app.get("/download/android", include_in_schema=False)
def download_android():
    """Stable public Android install URL used by the web/PWA.
    Priority: Play testing URL -> external APK URL -> bundled private-beta APK.
    """
    target = os.getenv("ANDROID_PLAY_URL", "").strip() or os.getenv("ANDROID_APK_URL", "").strip()
    if target:
        return RedirectResponse(url=target, status_code=307)
    bundled = Path(__file__).resolve().parents[1] / "web" / "downloads" / "LEMMIQ.apk"
    if bundled.exists():
        return FileResponse(
            path=str(bundled),
            media_type="application/vnd.android.package-archive",
            filename="LEMMIQ.apk"
        )
    raise HTTPException(
        status_code=503,
        detail="Android download is not configured. Set ANDROID_PLAY_URL / ANDROID_APK_URL or deploy backend/web/downloads/LEMMIQ.apk."
    )

@app.get("/app-config")
def app_config():
    """Public install metadata for the LEMMIQ web/PWA shell."""
    return {
        "version": "2.10.8",
        "android_download_url": os.getenv("ANDROID_APK_URL", "").strip(),
        "android_play_url": os.getenv("ANDROID_PLAY_URL", "").strip(),
        "android_install_url": "/download/android",
        "android_download_configured": bool(
            os.getenv("ANDROID_PLAY_URL", "").strip()
            or os.getenv("ANDROID_APK_URL", "").strip()
            or (Path(__file__).resolve().parents[1] / "web" / "downloads" / "LEMMIQ.apk").exists()
        ),
        "web_install_enabled": True,
    }

# ---------------- LEMMIQ V2.4 feature routes ----------------
from .v24 import register_v24
register_v24(app,current_user,get_db,push,push_tokens,user_json,msg_json)

# ---------------- LEMMIQ V2.6 Q Agent + Q-to-Q routes ----------------
from .v26 import register_v26
register_v26(app,current_user,get_db,push,user_json)

# ---------------- LEMMIQ V2.7 Q Vision + refined Q routes ----------------
from .v27 import register_v27
register_v27(app,current_user,get_db,push)
from .v2106 import register_v2106
register_v2106(app,current_user,get_db)

# ---------------- LEMMIQ V2.8 Q Economy + Marketplace ----------------
from .v28 import register_v28
register_v28(app,current_user,get_db)

# ---------------- LEMMIQ V2.9/V2.10.6 Q Predict ----------------
from .v29 import register_v29
register_v29(app,current_user,get_db)

# Keep the V2.10.4 Android stake endpoint working while V2.10.5 clients move
# to the canonical /v29/predict Q-wallet route.
from .v2104_predict_router import register_v2104_predict_compat
register_v2104_predict_compat(app,current_user,get_db)

# V2.10.5 server-authoritative Q feature pricing by active subscription tier.
from .v2105_q_features import register_v2105_q_features
register_v2105_q_features(app,current_user,get_db)

# Compatibility catalog for V2.10.4 clients. Prices remain 0 Q there; V2.10.5
# clients use the authenticated /v2105/q-features/catalog endpoint.
from .v2104_q_features import router as v2104_q_features_router
app.include_router(v2104_q_features_router)

# ---------------- LEMMIQ V2.10.8 Admin Analytics / RBAC ----------------
from .v2108 import register_v2108
register_v2108(app,current_user,get_db)

# ---------------- LEMMIQ V2 WEB / PWA ----------------
WEB_DIR = Path(__file__).resolve().parents[1] / "web"

@app.get("/", include_in_schema=False)
def web_root():
    return RedirectResponse(url="/web/")

if WEB_DIR.exists():
    app.mount("/web", StaticFiles(directory=str(WEB_DIR), html=True), name="lemmiq-web")
