"""Guest support only. Separate capability from authenticated messenger sessions."""
from __future__ import annotations
import hashlib,hmac,secrets,time,threading,json
from datetime import datetime,timedelta,timezone
from collections import OrderedDict,deque
from fastapi import APIRouter,Depends,HTTPException,Header,Request,Response,BackgroundTasks
from pydantic import BaseModel,Field
from sqlalchemy import String,Text,Integer,DateTime,ForeignKey,select,func
from sqlalchemy.orm import Mapped,mapped_column,Session
from .database import Base
from .models import User
from .v28 import QAdminRole,QAdminAuditLog
from .v2123_support import UserCredentialRevisionV2123,official_user

def now():return datetime.now(timezone.utc)
def aware(t):return t.replace(tzinfo=timezone.utc) if t.tzinfo is None else t
def digest(x):return hashlib.sha256(x.encode()).hexdigest()
class Ticket(Base):
    __tablename__='v301_guest_support_tickets'
    id:Mapped[str]=mapped_column(String(36),primary_key=True)
    secret:Mapped[str]=mapped_column(String(64))
    username:Mapped[str]=mapped_column(String(40),default='')
    topic:Mapped[str]=mapped_column(String(32))
    status:Mapped[str]=mapped_column(String(16),default='OPEN',index=True)
    created:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
    updated:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now,index=True)
    expires:Mapped[datetime]=mapped_column(DateTime(timezone=True))
    reset_user:Mapped[int|None]=mapped_column(Integer,nullable=True)
    reset_admin:Mapped[int|None]=mapped_column(Integer,nullable=True)
    reset_revision:Mapped[int|None]=mapped_column(Integer,nullable=True)
    reset_expires:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
class Entry(Base):
    __tablename__='v301_guest_support_messages'
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    ticket_id:Mapped[str]=mapped_column(ForeignKey('v301_guest_support_tickets.id'),index=True)
    sender:Mapped[str]=mapped_column(String(12))
    text:Mapped[str]=mapped_column(Text)
    created:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class New(BaseModel):
    username:str=Field(default='',max_length=40)
    topic:str=Field(max_length=32)
    text:str=Field(min_length=4,max_length=2000)
class MessageIn(BaseModel):text:str=Field(min_length=1,max_length=2000)
class Approve(BaseModel):
    username:str=Field(min_length=3,max_length=40)
    reason:str=Field(min_length=20,max_length=300)
    admin_password:str=Field(min_length=6,max_length=128)
class Reset(BaseModel):password:str=Field(min_length=8,max_length=128)
class Gate:
    def __init__(self):self.buckets=OrderedDict();self.lock=threading.Lock()
    def check(self,key,limit,seconds):
        with self.lock:
            t=time.monotonic();q=self.buckets.get(key,deque());self.buckets[key]=q;self.buckets.move_to_end(key)
            while q and q[0]<=t-seconds:q.popleft()
            if len(q)>=limit:raise HTTPException(429,'Too many requests. Try again later.')
            q.append(t)
            while len(self.buckets)>4096:self.buckets.popitem(last=False)
gate=Gate()
def ip(req):return req.client.host if req.client else 'unknown'
def admin_only(db,u):
    role=db.get(QAdminRole,u.id)
    if not role or not role.active or role.role!='MASTER_ADMIN':raise HTTPException(403,'Master Admin required')
def protected(db,u):
    r=db.get(QAdminRole,u.id);o=official_user(db)
    return bool(r or (o and o.id==u.id) or u.username.lower()=='lemmiq')
def row(db,tid,lock=False):
    stmt=select(Ticket).where(Ticket.id==tid)
    if lock:stmt=stmt.with_for_update()
    return db.scalar(stmt)
def guest(db,tid,key,lock=False):
    t=row(db,tid,lock)
    if not t or len(key)>128 or not hmac.compare_digest(t.secret,digest(key)) or aware(t.expires)<=now():raise HTTPException(404,'Ticket or access code invalid or expired')
    return t
def summary(t):return dict(id=t.id,topic=t.topic,status=t.status,username=t.username,updated=t.updated.isoformat(),expires=t.expires.isoformat())
def detail(db,t):
    entries=db.scalars(select(Entry).where(Entry.ticket_id==t.id).order_by(Entry.id).limit(250)).all()
    return {**summary(t),'reset_ready':bool(t.status=='OPEN' and t.reset_user and t.reset_expires and aware(t.reset_expires)>now()),'messages':[dict(sender=e.sender,text=e.text,at=e.created.isoformat()) for e in entries]}
def add(db,t,sender,text):
    text=text.strip()
    if not text:raise HTTPException(422,'Message required')
    if t.status!='OPEN':raise HTTPException(409,'Ticket is closed')
    if db.scalar(select(func.count(Entry.id)).where(Entry.ticket_id==t.id))>=250:raise HTTPException(409,'Ticket message limit reached')
    db.add(Entry(ticket_id=t.id,sender=sender,text=text));t.updated=now()
def revoke(t):t.reset_user=None;t.reset_admin=None;t.reset_revision=None;t.reset_expires=None

def register_v301_support(app,current_user,get_db,hash_password,disconnect=None):
    router=APIRouter(prefix='/v301/support',tags=['Guest support'])
    @router.post('/tickets')
    def create(body:New,request:Request,response:Response,db:Session=Depends(get_db)):
        gate.check(('create',ip(request)),5,3600);gate.check('global-create',100,3600)
        response.headers['Cache-Control']='no-store'
        if body.topic not in {'PASSWORD','USERNAME','LOGIN','SECURITY','OTHER'}:raise HTTPException(422,'Select a support topic')
        if db.scalar(select(func.count(Ticket.id)).where(Ticket.status=='OPEN',Ticket.expires>now()))>=2000:raise HTTPException(503,'Support queue is temporarily full')
        key=secrets.token_urlsafe(32);t=Ticket(id=secrets.token_hex(16),secret=digest(key),username=body.username.strip().lower().lstrip('@'),topic=body.topic,expires=now()+timedelta(days=30))
        db.add(t);db.flush();add(db,t,'GUEST',body.text);db.commit()
        return {'ticket':detail(db,t),'access_code':key}
    @router.get('/tickets/{tid}')
    def read(tid:str,request:Request,response:Response,x_support_key:str=Header(default=''),db:Session=Depends(get_db)):
        gate.check(('read',ip(request)),180,60);response.headers['Cache-Control']='no-store';return detail(db,guest(db,tid,x_support_key))
    @router.post('/tickets/{tid}/messages')
    def reply(tid:str,body:MessageIn,request:Request,response:Response,x_support_key:str=Header(default=''),db:Session=Depends(get_db)):
        gate.check(('reply',ip(request)),30,60);response.headers['Cache-Control']='no-store';t=guest(db,tid,x_support_key,True);add(db,t,'GUEST',body.text);db.commit();return detail(db,t)
    @router.post('/tickets/{tid}/reset')
    def reset(tid:str,body:Reset,request:Request,response:Response,background:BackgroundTasks,x_support_key:str=Header(default=''),db:Session=Depends(get_db)):
        gate.check(('reset',ip(request)),8,300);response.headers['Cache-Control']='no-store';t=guest(db,tid,x_support_key,True)
        if t.status!='OPEN' or not t.reset_user or not t.reset_expires or aware(t.reset_expires)<=now():raise HTTPException(403,'No active recovery authorisation')
        u=db.scalar(select(User).where(User.id==t.reset_user).with_for_update())
        if not u or protected(db,u):raise HTTPException(403,'Account cannot be recovered through guest support')
        rev=db.get(UserCredentialRevisionV2123,u.id)
        if (int(rev.revision) if rev else 0)!=t.reset_revision:raise HTTPException(409,'Account credentials changed; contact support again')
        if not rev:rev=UserCredentialRevisionV2123(user_id=u.id,revision=0);db.add(rev)
        u.password_hash,u.salt=hash_password(body.password);rev.revision=int(rev.revision or 0)+1;rev.reset_at=now()
        uid=u.id
        if t.reset_admin:
            db.add(QAdminAuditLog(admin_user_id=t.reset_admin,action='GUEST_RECOVERY_COMPLETED',target_user_id=uid,before_json='{}',after_json=json.dumps({'ticket_id':t.id,'credential_revision':rev.revision}),reason='Single-use guest recovery completed'))
        revoke(t);t.status='RESOLVED';t.updated=now();db.commit()
        if disconnect:background.add_task(disconnect,uid)
        return {'ok':True,'sessions_revoked':True}
    @router.get('/admin/access')
    def access(u:User=Depends(current_user),db:Session=Depends(get_db)):
        admin_only(db,u);return {'allowed':True}
    @router.get('/admin/tickets')
    def tickets(response:Response,u:User=Depends(current_user),db:Session=Depends(get_db)):
        admin_only(db,u);response.headers['Cache-Control']='no-store';return {'items':[summary(t) for t in db.scalars(select(Ticket).order_by(Ticket.updated.desc()).limit(100)).all()]}
    @router.get('/admin/tickets/{tid}')
    def get_admin(tid:str,response:Response,u:User=Depends(current_user),db:Session=Depends(get_db)):
        admin_only(db,u);response.headers['Cache-Control']='no-store';t=row(db,tid)
        if not t:raise HTTPException(404,'Ticket not found')
        return detail(db,t)
    @router.post('/admin/tickets/{tid}/messages')
    def admin_reply(tid:str,body:MessageIn,u:User=Depends(current_user),db:Session=Depends(get_db)):
        admin_only(db,u);t=row(db,tid,True)
        if not t:raise HTTPException(404,'Ticket not found')
        add(db,t,'SUPPORT',body.text);db.commit();return detail(db,t)
    @router.post('/admin/tickets/{tid}/close')
    def close(tid:str,u:User=Depends(current_user),db:Session=Depends(get_db)):
        admin_only(db,u);t=row(db,tid,True)
        if not t:raise HTTPException(404,'Ticket not found')
        revoke(t);t.status='CLOSED';t.updated=now();db.commit();return detail(db,t)
    @router.post('/admin/tickets/{tid}/authorize')
    def authorize(tid:str,body:Approve,u:User=Depends(current_user),db:Session=Depends(get_db)):
        admin_only(db,u);gate.check(('approve',u.id),8,300)
        if not hmac.compare_digest(hash_password(body.admin_password,u.salt)[0],u.password_hash):raise HTTPException(403,'Admin password verification failed')
        t=row(db,tid,True)
        if not t or t.status!='OPEN' or aware(t.expires)<=now():raise HTTPException(409,'Ticket is not active')
        name=body.username.strip().lower().lstrip('@');target=db.scalar(select(User).where(User.username==name).with_for_update())
        if not target or protected(db,target) or target.id==u.id:raise HTTPException(403,'Account cannot be recovered through guest support')
        if t.username and t.username!=name:raise HTTPException(422,'Ticket username differs; request a new ticket with correct username')
        rev=db.get(UserCredentialRevisionV2123,target.id);t.reset_user=target.id;t.reset_admin=u.id;t.reset_revision=int(rev.revision) if rev else 0;t.reset_expires=now()+timedelta(minutes=15);t.updated=now()
        db.add(QAdminAuditLog(admin_user_id=u.id,action='GUEST_RECOVERY_AUTHORIZED',target_user_id=target.id,before_json='{}',after_json=json.dumps({'ticket_id':t.id,'expires':t.reset_expires.isoformat()}),reason=body.reason.strip()))
        db.commit();return detail(db,t)
    app.include_router(router)
