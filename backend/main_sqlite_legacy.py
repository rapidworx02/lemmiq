import os, sqlite3, hashlib, hmac, secrets, asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
import jwt
from fastapi import FastAPI, HTTPException, Depends, Header, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

BASE=Path(__file__).resolve().parent
DB=BASE/"lemmiq.db"
SECRET=os.getenv("LEMMIQ_JWT_SECRET","CHANGE_ME_"+("x"*40))
app=FastAPI(title="LEMMIQ Server",version="1.0.0")
app.add_middleware(CORSMiddleware,allow_origins=["*"],allow_credentials=True,allow_methods=["*"],allow_headers=["*"])
connections={}

def now(): return datetime.now(timezone.utc).isoformat()
def db():
    c=sqlite3.connect(DB,check_same_thread=False);c.row_factory=sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL");c.execute("PRAGMA foreign_keys=ON");return c
def init():
    c=db();c.executescript("""
    CREATE TABLE IF NOT EXISTS users(
      id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE COLLATE NOCASE,
      display_name TEXT NOT NULL, avatar TEXT, password_hash TEXT NOT NULL, salt TEXT NOT NULL, created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS chats(
      id INTEGER PRIMARY KEY AUTOINCREMENT,user1_id INTEGER,user2_id INTEGER,created_at TEXT,updated_at TEXT,
      UNIQUE(user1_id,user2_id));
    CREATE TABLE IF NOT EXISTS chat_settings(
      chat_id INTEGER,user_id INTEGER,category TEXT DEFAULT 'FRIEND',ai_mode TEXT DEFAULT 'ASSIST',
      tone TEXT DEFAULT 'Natural',PRIMARY KEY(chat_id,user_id));
    CREATE TABLE IF NOT EXISTS messages(
      id INTEGER PRIMARY KEY AUTOINCREMENT,chat_id INTEGER,sender_id INTEGER,text TEXT,created_at TEXT,
      read_at TEXT,ai_generated INTEGER DEFAULT 0);
    CREATE TABLE IF NOT EXISTS moments(
      id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,text TEXT,created_at TEXT,expires_at TEXT);
    CREATE INDEX IF NOT EXISTS idx_msg_chat ON messages(chat_id,id);
    """);c.commit();c.close()
@app.on_event("startup")
def start(): init()

def hp(p,s=None):
    salt=bytes.fromhex(s) if s else secrets.token_bytes(16)
    return hashlib.pbkdf2_hmac("sha256",p.encode(),salt,150000).hex(),salt.hex()
def token(uid):
    return jwt.encode({"sub":str(uid),"exp":datetime.now(timezone.utc)+timedelta(days=30)},SECRET,algorithm="HS256")
def uid_from(t):
    try:return int(jwt.decode(t,SECRET,algorithms=["HS256"])["sub"])
    except: raise HTTPException(401,"Invalid or expired token")
def current(authorization:str=Header(default="")):
    if not authorization.startswith("Bearer "):raise HTTPException(401,"Missing bearer token")
    uid=uid_from(authorization[7:]);c=db()
    r=c.execute("SELECT id,username,display_name,avatar FROM users WHERE id=?",(uid,)).fetchone();c.close()
    if not r:raise HTTPException(401,"User not found")
    return dict(r)
def user(r):return {"id":r["id"],"username":r["username"],"display_name":r["display_name"],"avatar":r["avatar"]}
def member(c,cid,uid):
    ch=c.execute("SELECT * FROM chats WHERE id=?",(cid,)).fetchone()
    if not ch or uid not in (ch["user1_id"],ch["user2_id"]):raise HTTPException(404,"Chat not found")
    return ch
def settings(c,cid,uid):
    r=c.execute("SELECT * FROM chat_settings WHERE chat_id=? AND user_id=?",(cid,uid)).fetchone()
    if not r:
        c.execute("INSERT OR IGNORE INTO chat_settings(chat_id,user_id) VALUES(?,?)",(cid,uid));c.commit()
        r=c.execute("SELECT * FROM chat_settings WHERE chat_id=? AND user_id=?",(cid,uid)).fetchone()
    return r
def chat_json(c,ch,uid):
    oid=ch["user2_id"] if ch["user1_id"]==uid else ch["user1_id"]
    o=c.execute("SELECT id,username,display_name,avatar FROM users WHERE id=?",(oid,)).fetchone()
    s=settings(c,ch["id"],uid)
    lm=c.execute("SELECT text FROM messages WHERE chat_id=? ORDER BY id DESC LIMIT 1",(ch["id"],)).fetchone()
    n=c.execute("SELECT COUNT(*) n FROM messages WHERE chat_id=? AND sender_id<>? AND read_at IS NULL",(ch["id"],uid)).fetchone()["n"]
    return {"id":ch["id"],"other_user":user(o),"category":s["category"],"ai_mode":s["ai_mode"],"tone":s["tone"],
            "last_message":lm["text"] if lm else None,"updated_at":ch["updated_at"],"unread":n}
def sensitive(t):
    t=t.lower()
    ks=["password","otp","bank","transfer","payment","court","lawyer","doctor","hospital","emergency",
        "break up","divorce","pregnant","sex","nude","loan","contract","credit card"]
    return any(k in t for k in ks)
def insert(c,cid,sender,text,ai=False):
    ts=now();cur=c.execute("INSERT INTO messages(chat_id,sender_id,text,created_at,ai_generated) VALUES(?,?,?,?,?)",(cid,sender,text,ts,1 if ai else 0))
    c.execute("UPDATE chats SET updated_at=? WHERE id=?",(ts,cid));c.commit()
    r=c.execute("SELECT * FROM messages WHERE id=?",(cur.lastrowid,)).fetchone()
    return dict(r)|{"ai_generated":bool(r["ai_generated"])}
async def push(uid,payload):
    dead=[]
    for ws in list(connections.get(uid,set())):
        try:await ws.send_json(payload)
        except:dead.append(ws)
    for ws in dead:connections.get(uid,set()).discard(ws)

class Login(BaseModel):
    username:str=Field(min_length=3,max_length=24);password:str=Field(min_length=6,max_length=128)
class Reg(Login):display_name:str=Field(min_length=1,max_length=50)
class Direct(BaseModel):user_id:int
class Msg(BaseModel):text:str=Field(min_length=1,max_length=4000)
class Settings(BaseModel):category:str;ai_mode:str;tone:str
class Moment(BaseModel):text:str=Field(min_length=1,max_length=500)

@app.get("/health")
def health():return {"ok":True,"name":"LEMMIQ","version":"1.0.0"}

@app.post("/register")
def register(b:Reg):
    u=b.username.strip().lower()
    if not u.replace("_","").isalnum():raise HTTPException(400,"Username can only use letters, numbers and underscore")
    h,s=hp(b.password);c=db()
    try:
        cur=c.execute("INSERT INTO users(username,display_name,password_hash,salt,created_at) VALUES(?,?,?,?,?)",(u,b.display_name.strip(),h,s,now()))
        c.commit();uid=cur.lastrowid;r=c.execute("SELECT id,username,display_name,avatar FROM users WHERE id=?",(uid,)).fetchone()
    except sqlite3.IntegrityError:raise HTTPException(409,"Username already taken")
    finally:c.close()
    return {"token":token(uid),"user":user(r)}

@app.post("/login")
def login(b:Login):
    c=db();r=c.execute("SELECT * FROM users WHERE username=? COLLATE NOCASE",(b.username.strip(),)).fetchone();c.close()
    if not r:raise HTTPException(401,"Incorrect username or password")
    got,_=hp(b.password,r["salt"])
    if not hmac.compare_digest(got,r["password_hash"]):raise HTTPException(401,"Incorrect username or password")
    return {"token":token(r["id"]),"user":user(r)}

@app.get("/users/search")
def search(q:str,u=Depends(current)):
    c=db();rs=c.execute("SELECT id,username,display_name,avatar FROM users WHERE id<>? AND (username LIKE ? OR display_name LIKE ?) LIMIT 30",(u["id"],f"%{q}%",f"%{q}%")).fetchall();c.close()
    return [user(r) for r in rs]

@app.get("/chats")
def chats(u=Depends(current)):
    c=db();rs=c.execute("SELECT * FROM chats WHERE user1_id=? OR user2_id=? ORDER BY updated_at DESC",(u["id"],u["id"])).fetchall()
    out=[chat_json(c,r,u["id"]) for r in rs];c.close();return out

@app.post("/chats/direct")
def direct(b:Direct,u=Depends(current)):
    if b.user_id==u["id"]:raise HTTPException(400,"Cannot message yourself")
    a,z=sorted([u["id"],b.user_id]);c=db()
    if not c.execute("SELECT id FROM users WHERE id=?",(b.user_id,)).fetchone():c.close();raise HTTPException(404,"User not found")
    ch=c.execute("SELECT * FROM chats WHERE user1_id=? AND user2_id=?",(a,z)).fetchone()
    if not ch:
        ts=now();cur=c.execute("INSERT INTO chats(user1_id,user2_id,created_at,updated_at) VALUES(?,?,?,?)",(a,z,ts,ts))
        cid=cur.lastrowid;c.execute("INSERT INTO chat_settings(chat_id,user_id) VALUES(?,?)",(cid,a));c.execute("INSERT INTO chat_settings(chat_id,user_id) VALUES(?,?)",(cid,z));c.commit()
        ch=c.execute("SELECT * FROM chats WHERE id=?",(cid,)).fetchone()
    out=chat_json(c,ch,u["id"]);c.close();return out

@app.get("/chats/{cid}/messages")
def messages(cid:int,u=Depends(current)):
    c=db();member(c,cid,u["id"]);rs=c.execute("SELECT * FROM messages WHERE chat_id=? ORDER BY id ASC LIMIT 500",(cid,)).fetchall();c.close()
    return [dict(r)|{"ai_generated":bool(r["ai_generated"])} for r in rs]

def ai_reply(category,tone,history,incoming,auto=False):
    key=os.getenv("ANTHROPIC_API_KEY")
    if not key:
        if category=="WORK":return "Thanks for the update. I’ll check this and get back to you shortly."
        if category in ("PARTNER","DATING"):return "Got you ❤️ I’ll reply properly in a moment."
        if category in ("CUSTOMER","SALES"):return "Thanks for reaching out. I’m checking this now and will update you shortly."
        if category=="FAMILY":return "Sounds good 😊 I’ll confirm shortly."
        return "Got you — I’ll get back to you shortly."
    from anthropic import Anthropic
    client=Anthropic(api_key=key)
    prompt=f"""You are LEMMIQ, an AI communication copilot inside a private messenger.
Category: {category}
Tone: {tone}
Recent conversation:
{history[-14000:]}
Latest incoming:
{incoming}
Write ONE concise natural reply. Match the language/style. Never invent facts, completed actions, money, availability, appointments or promises. Do not manipulate or pressure. Output only the reply."""
    m=client.messages.create(model=os.getenv("ANTHROPIC_MODEL","claude-sonnet-4-6"),max_tokens=180,temperature=0.5,messages=[{"role":"user","content":prompt}])
    return "".join(x.text for x in m.content if getattr(x,"type","")=="text").strip()

@app.post("/chats/{cid}/messages")
async def send(cid:int,b:Msg,u=Depends(current)):
    c=db();ch=member(c,cid,u["id"]);m=insert(c,cid,u["id"],b.text.strip())
    oid=ch["user2_id"] if ch["user1_id"]==u["id"] else ch["user1_id"]
    await push(oid,{"type":"message","data":m});await push(u["id"],{"type":"message","data":m})
    s=settings(c,cid,oid)
    if s["ai_mode"]=="AUTO" and not sensitive(b.text):
        hist=c.execute("SELECT m.text,u.display_name FROM messages m JOIN users u ON u.id=m.sender_id WHERE m.chat_id=? ORDER BY m.id DESC LIMIT 50",(cid,)).fetchall()[::-1]
        h="\n".join(f'{x["display_name"]}: {x["text"]}' for x in hist)
        try:
            r=insert(c,cid,oid,ai_reply(s["category"],s["tone"],h,b.text,True),True)
            await push(oid,{"type":"message","data":r});await push(u["id"],{"type":"message","data":r})
        except Exception as e:print("AI AUTO:",e)
    c.close();return m

@app.post("/chats/{cid}/read")
async def read(cid:int,u=Depends(current)):
    c=db();ch=member(c,cid,u["id"]);ts=now()
    c.execute("UPDATE messages SET read_at=? WHERE chat_id=? AND sender_id<>? AND read_at IS NULL",(ts,cid,u["id"]));c.commit();c.close()
    return {"ok":True}

@app.put("/chats/{cid}/settings")
def setsettings(cid:int,b:Settings,u=Depends(current)):
    cats={"PARTNER","DATING","BESTIE","FRIEND","FAMILY","WORK","CUSTOMER","SALES","STUDY","CUSTOM"}
    modes={"OFF","ASSIST","AUTO"}
    if b.category not in cats or b.ai_mode not in modes:raise HTTPException(400,"Invalid settings")
    c=db();ch=member(c,cid,u["id"]);settings(c,cid,u["id"])
    c.execute("UPDATE chat_settings SET category=?,ai_mode=?,tone=? WHERE chat_id=? AND user_id=?",(b.category,b.ai_mode,b.tone[:40],cid,u["id"]));c.commit()
    out=chat_json(c,ch,u["id"]);c.close();return out

@app.post("/chats/{cid}/suggest")
def suggest(cid:int,u=Depends(current)):
    c=db();ch=member(c,cid,u["id"]);s=settings(c,cid,u["id"])
    rs=c.execute("SELECT m.*,us.display_name FROM messages m JOIN users us ON us.id=m.sender_id WHERE m.chat_id=? ORDER BY m.id DESC LIMIT 50",(cid,)).fetchall()[::-1]
    incoming=next((r["text"] for r in reversed(rs) if r["sender_id"]!=u["id"]),None)
    if not incoming:c.close();raise HTTPException(400,"No incoming message")
    h="\n".join(f'{r["display_name"]}: {r["text"]}' for r in rs)
    reply=ai_reply(s["category"],s["tone"],h,incoming);c.close();return {"reply":reply}

@app.get("/moments")
def moments(u=Depends(current)):
    c=db();rs=c.execute("""SELECT m.*,u.id uid,u.username,u.display_name,u.avatar FROM moments m JOIN users u ON u.id=m.user_id WHERE m.expires_at>? ORDER BY m.id DESC LIMIT 100""",(now(),)).fetchall()
    out=[{"id":r["id"],"text":r["text"],"created_at":r["created_at"],"expires_at":r["expires_at"],"user":{"id":r["uid"],"username":r["username"],"display_name":r["display_name"],"avatar":r["avatar"]}} for r in rs]
    c.close();return out

@app.post("/moments")
def postmoment(b:Moment,u=Depends(current)):
    c=db();created=datetime.now(timezone.utc);exp=created+timedelta(hours=24)
    cur=c.execute("INSERT INTO moments(user_id,text,created_at,expires_at) VALUES(?,?,?,?)",(u["id"],b.text.strip(),created.isoformat(),exp.isoformat()));c.commit();mid=cur.lastrowid;c.close()
    return {"id":mid,"user":u,"text":b.text.strip(),"created_at":created.isoformat(),"expires_at":exp.isoformat()}

@app.websocket("/ws")
async def ws(ws:WebSocket,token:str):
    try:uid=uid_from(token)
    except HTTPException:await ws.close(code=4401);return
    await ws.accept();connections.setdefault(uid,set()).add(ws)
    try:
        await ws.send_json({"type":"connected","user_id":uid})
        while True:await ws.receive_text()
    except WebSocketDisconnect:pass
    finally:connections.get(uid,set()).discard(ws)
