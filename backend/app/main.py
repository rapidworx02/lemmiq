from .trust import check_text, media_capabilities
import os, hashlib, hmac, secrets
from datetime import datetime, timedelta, timezone
from typing import Dict, Set
import jwt
from fastapi import FastAPI, HTTPException, Depends, Header, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from sqlalchemy import or_, select, func
from sqlalchemy.orm import Session
from .database import Base, engine, SessionLocal
from .models import User, Chat, ChatSetting, Message, Moment, InsightEvent
from .chat_agent import daily_brief, needs_reply, communication_profile, search_memory, summarize_chat, ask_agent
from .insights import CATEGORIES, DIRECTIONS, event_json, list_events, brief as insight_brief

SECRET = os.getenv("LEMMIQ_JWT_SECRET", "")
if len(SECRET) < 32 or SECRET.startswith("CHANGE_"):
    raise RuntimeError("Set a long random LEMMIQ_JWT_SECRET in backend/.env before starting the server")
app = FastAPI(title="LEMMIQ Server", version="1.6.1")
connections: Dict[int, Set[WebSocket]] = {}

@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)

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
    return {"id": u.id, "username": u.username, "display_name": u.display_name, "avatar": u.avatar}

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

def msg_json(m: Message):
    return {"id": m.id, "chat_id": m.chat_id, "sender_id": m.sender_id, "text": m.text,
            "created_at": m.created_at.isoformat(), "read_at": m.read_at.isoformat() if m.read_at else None,
            "ai_generated": m.ai_generated}

def chat_json(db: Session, c: Chat, uid: int):
    oid = c.user2_id if c.user1_id == uid else c.user1_id
    other = db.get(User, oid)
    s = get_settings(db, c.id, uid)
    last = db.scalar(select(Message).where(Message.chat_id == c.id).order_by(Message.id.desc()).limit(1))
    unread = db.scalar(select(func.count()).select_from(Message).where(Message.chat_id == c.id, Message.sender_id != uid, Message.read_at.is_(None))) or 0
    return {"id": c.id, "other_user": user_json(other), "category": s.category, "ai_mode": s.ai_mode, "tone": s.tone,
            "last_message": last.text if last else None, "updated_at": c.updated_at.isoformat(), "unread": int(unread)}

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

@app.get("/health")
def health():
    return {"ok": True, "name": "LEMMIQ", "version": "1.6.1"}

@app.post("/register")
def register(body: Register, db: Session = Depends(get_db)):
    username = body.username.strip().lower()
    if not username.replace("_", "").isalnum():
        raise HTTPException(400, "Username can only use letters, numbers and underscore")
    if db.scalar(select(User).where(func.lower(User.username) == username)):
        raise HTTPException(409, "Username already taken")
    ph, salt = hp(body.password)
    u = User(username=username, display_name=body.display_name.strip(), password_hash=ph, salt=salt)
    db.add(u); db.commit(); db.refresh(u)
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
    rows = db.scalars(select(Message).where(Message.chat_id == cid).order_by(Message.id.asc()).limit(500)).all()
    return [msg_json(m) for m in rows]

@app.post("/chats/{cid}/messages")
async def send(cid: int, body: Msg, u: User = Depends(current_user), db: Session = Depends(get_db)):
    c = ensure_member(db, cid, u.id)
    m = Message(chat_id=cid, sender_id=u.id, text=body.text.strip())
    c.updated_at = datetime.now(timezone.utc)
    db.add(m); db.commit(); db.refresh(m)
    data = msg_json(m)
    oid = c.user2_id if c.user1_id == u.id else c.user1_id
    await push(oid, {"type":"message","data":data}); await push(u.id, {"type":"message","data":data})
    s = get_settings(db, cid, oid)
    if s.ai_mode == "AUTO" and not sensitive(body.text):
        hist = db.scalars(select(Message).where(Message.chat_id == cid).order_by(Message.id.desc()).limit(50)).all()[::-1]
        lines = []
        for x in hist:
            sender = db.get(User, x.sender_id)
            lines.append(f"{sender.display_name}: {x.text}")
        try:
            reply = ai_reply(s.category, s.tone, "\n".join(lines), body.text)
            auto = Message(chat_id=cid, sender_id=oid, text=reply, ai_generated=True)
            c.updated_at = datetime.now(timezone.utc)
            db.add(auto); db.commit(); db.refresh(auto)
            ad = msg_json(auto)
            await push(oid, {"type":"message","data":ad}); await push(u.id, {"type":"message","data":ad})
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

@app.post("/trust/check")
def trust_check(body: TrustIn, u: User = Depends(current_user)):
    return check_text(body.text)

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
        return summarize_chat(db, u.id, cid)
    except ValueError:
        raise HTTPException(404, "Chat not found")

@app.post("/agent/ask")
def agent_ask(body: AgentAskIn, u: User = Depends(current_user), db: Session = Depends(get_db)):
    return ask_agent(db, u.id, body.question, body.days)


class InsightIn(BaseModel):
    client_event_id: str = Field(min_length=8, max_length=80)
    category: str = Field(max_length=20)
    source: str = Field(max_length=80)
    title: str = Field(max_length=100)
    detail: str = Field(default="",max_length=220)
    amount_cents: int | None = Field(default=None, ge=0, le=100_000_000_000)
    direction: str = Field(default="UNKNOWN", max_length=12)
    occurred_at: datetime

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

@app.delete("/insights/events")
def delete_insights(u:User=Depends(current_user),db:Session=Depends(get_db)):
    for e in db.scalars(select(InsightEvent).where(InsightEvent.user_id==u.id)).all(): db.delete(e)
    db.commit()
    return {"deleted":True}
