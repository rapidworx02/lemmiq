# V21311_RELEASE
# V2138_COMBINED
# V21356_STUDIO_DELETE
"""LEMMIQ V2.13.4: separate creator identity + dedicated professional inbox.

The professional chat is stored outside Chat/Message. Fan-facing endpoints never
serialize the creator owner's personal User row, ID, username, or profile photo.
Payments reuse the existing V2.13 hold/settle/commission ledger. Adult-explicit
content is NOT made available by this module.
"""
from __future__ import annotations
import hashlib, re, secrets
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, select, func, or_
from sqlalchemy.orm import Mapped, Session, mapped_column
from .database import Base
from .models import User, UserBlock
from . import media_store
from .v213_creators import (
    CreatorProfile, CreatorRequest, CreatorPayment, CreatorFollow, CreatorPost,
    create_payment, settle_held, refund, charge_ready, creator_ready, earnings,
    q, now, to_micros,
)


def utcnow(): return datetime.now(timezone.utc)
def aware(d): return d.replace(tzinfo=timezone.utc) if d and d.tzinfo is None else d

class CreatorIdentity(Base):
    __tablename__='v2134_creator_identities'
    owner_id:Mapped[int]=mapped_column(ForeignKey('users.id'),primary_key=True)
    public_id:Mapped[str]=mapped_column(String(48),unique=True,index=True)
    handle:Mapped[str]=mapped_column(String(32),unique=True,index=True)
    stage_name:Mapped[str]=mapped_column(String(80))
    avatar_key:Mapped[Optional[str]]=mapped_column(String(240),nullable=True)
    avatar_mime:Mapped[str]=mapped_column(String(50),default='image/jpeg')
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)
    updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)

class ProfessionalThread(Base):
    __tablename__='v2134_professional_threads'
    id:Mapped[str]=mapped_column(String(48),primary_key=True)
    creator_id:Mapped[int]=mapped_column(ForeignKey('users.id'),index=True)
    fan_id:Mapped[int]=mapped_column(ForeignKey('users.id'),index=True)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)
    updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)
    __table_args__=(UniqueConstraint('creator_id','fan_id',name='uq_v2134_creator_fan'),)

class ProfessionalPass(Base):
    __tablename__='v2134_professional_passes'
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    request_id:Mapped[int]=mapped_column(ForeignKey('v213_creator_requests.id'),unique=True,index=True)
    thread_id:Mapped[str]=mapped_column(ForeignKey('v2134_professional_threads.id'),index=True)
    status:Mapped[str]=mapped_column(String(28),default='ACTIVE')
    max_messages:Mapped[int]=mapped_column(Integer,default=3)
    fan_sent:Mapped[int]=mapped_column(Integer,default=0)
    creator_sent:Mapped[int]=mapped_column(Integer,default=0)
    expires_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)

class ProfessionalMessage(Base):
    __tablename__='v2134_professional_messages'
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    thread_id:Mapped[str]=mapped_column(ForeignKey('v2134_professional_threads.id'),index=True)
    role:Mapped[str]=mapped_column(String(10))  # FAN or CREATOR, never personal user id
    kind:Mapped[str]=mapped_column(String(20),default='TEXT')
    body:Mapped[str]=mapped_column(Text,default='')
    offer_id:Mapped[Optional[int]]=mapped_column(ForeignKey('v2134_professional_offers.id'),nullable=True)
    request_id:Mapped[Optional[int]]=mapped_column(ForeignKey('v213_creator_requests.id'),nullable=True)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow,index=True)

class ProfessionalOffer(Base):
    __tablename__='v2134_professional_offers'
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    thread_id:Mapped[str]=mapped_column(ForeignKey('v2134_professional_threads.id'),index=True)
    item_id:Mapped[int]=mapped_column(Integer,index=True)
    creator_id:Mapped[int]=mapped_column(ForeignKey('users.id'))
    fan_id:Mapped[int]=mapped_column(ForeignKey('users.id'))
    price_micros:Mapped[int]=mapped_column(BigInteger)
    request_key:Mapped[str]=mapped_column(String(80),unique=True)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)

class ProfessionalTerms(Base):
    __tablename__='v2134_professional_terms'
    creator_id:Mapped[int]=mapped_column(ForeignKey('users.id'),primary_key=True)
    messages:Mapped[int]=mapped_column(Integer,default=3)
    hours:Mapped[int]=mapped_column(Integer,default=48)

class IdentityIn(BaseModel):
    handle:str=Field(min_length=3,max_length=32)
    stage_name:str=Field(min_length=2,max_length=80)

class ChatTermsIn(BaseModel):
    messages:int=Field(ge=1,le=25)
    hours:int=Field(ge=1,le=168)

class ChatRequestIn(BaseModel):
    message:str=Field(min_length=3,max_length=900)
    request_key:str=Field(min_length=12,max_length=80)

class TextIn(BaseModel):
    text:str=Field(min_length=1,max_length=4000)

class OfferIn(BaseModel):
    item_id:int
    price_q:float
    request_key:str=Field(min_length=12,max_length=80)

class PurchaseIn(BaseModel):
    request_key:str=Field(min_length=12,max_length=80)


def identity(db,owner): return db.get(CreatorIdentity,owner)
def by_public(db,public): return db.scalar(select(CreatorIdentity).where(CreatorIdentity.public_id==public))

def public_avatar(x):
    if not x or not x.avatar_key: return None
    h=hashlib.sha256(x.avatar_key.encode()).hexdigest()[:12]
    return f'/v2134/avatars/{x.public_id}?v={h}'

def professional_public_for(db,owner):
    """Used by legacy creator profile serializer; NEVER fall back to User identity."""
    x=identity(db,owner)
    return {'username':x.handle if x else 'creator-setup-required',
            'display_name':x.stage_name if x else 'Professional creator',
            'avatar_url':public_avatar(x) if x else None,
            'public_id':x.public_id if x else None}

def professional_card(db,x,fan=None):
    p=db.get(CreatorProfile,x.owner_id)
    if not p or p.status!='APPROVED' or p.level not in ('MAINSTREAM','GLAMOUR'):
        raise HTTPException(404,'Professional creator unavailable')
    follows=db.scalar(select(func.count()).select_from(CreatorFollow).where(CreatorFollow.creator_id==x.owner_id)) or 0
    following=bool(fan and db.scalar(select(CreatorFollow.id).where(CreatorFollow.creator_id==x.owner_id,CreatorFollow.fan_id==fan)))
    return {'public_id':x.public_id,'handle':x.handle,'stage_name':x.stage_name,'avatar_url':public_avatar(x),
            'bio':p.bio,'category':p.category,'level':p.level,'monthly_q':q(p.monthly_micros),
            'chat_q':q(p.chat_micros),'voice_q':q(p.voice_micros),'video_q':q(p.video_micros),
            'followers':follows,'following':following}

def is_legacy_paid_thread(db, chat_id):
    """Old V2.13.3 paid direct chats must not appear in personal inboxes."""
    from sqlalchemy import inspect, text
    if not inspect(db.get_bind()).has_table('v2133_creator_chat_passes'):
        return False
    return bool(db.execute(text('SELECT 1 FROM v2133_creator_chat_passes WHERE chat_id=:c LIMIT 1'), {'c':chat_id}).first())


def protect_personal_direct(db, sender, other):
    """Block new personal Chat creation targeting a published creator account.
    Existing non-legacy personal contacts continue normally; new creator fan
    conversations must use /v2134 and its distinct public professional ID.
    """
    from .models import Chat
    a,b=sorted((sender,other))
    prior=db.scalar(select(Chat).where(Chat.user1_id==a,Chat.user2_id==b))
    if prior and not is_legacy_paid_thread(db,prior.id):return True
    if prior:return False
    # Only incoming NEW personal conversations to a published creator are blocked.
    # A creator may still personally initiate an ordinary conversation by choice.
    p=db.get(CreatorProfile,other)
    # V2138: personal username lookup may open an ordinary direct chat.
    # Never expose the creator's personal account through professional discovery.
    # Existing legacy paid threads remain excluded by the check above.
    # The standard user blocks/privacy checks still apply to the direct-chat API.
    # published creator status no longer blocks independently initiated personal chats.
    return True


def terms_for(db,creator):
    t=db.get(ProfessionalTerms,creator)
    return {'messages':t.messages if t else 3,'hours':t.hours if t else 48}

def require_thread(db,tid,uid):
    x=db.get(ProfessionalThread,tid)
    if not x or uid not in (x.creator_id,x.fan_id):raise HTTPException(404,'Professional conversation not found')
    return x

def blocked(db,creator,fan):
    return bool(db.get(UserBlock,{'blocker_id':creator,'blocked_id':fan}) or
                db.get(UserBlock,{'blocker_id':fan,'blocked_id':creator}))

def ensure_thread(db,creator,fan):
    if blocked(db,creator,fan):raise HTTPException(403,'This conversation is blocked')
    # Lock participant rows to serialise creation with PostgreSQL.
    db.execute(select(User.id).where(User.id.in_(sorted((creator,fan)))).order_by(User.id).with_for_update()).all()
    t=db.scalar(select(ProfessionalThread).where(ProfessionalThread.creator_id==creator,
                 ProfessionalThread.fan_id==fan))
    if not t:
        t=ProfessionalThread(id='pc_'+secrets.token_hex(16),creator_id=creator,fan_id=fan)
        db.add(t);db.flush()
    return t

def latest_pass(db,thread,lock=False):
    s=select(ProfessionalPass).where(ProfessionalPass.thread_id==thread.id).order_by(ProfessionalPass.id.desc()).limit(1)
    if lock:s=s.with_for_update()
    return db.scalar(s)

def pass_json(p):
    if not p:return None
    return {'status':p.status,'max_messages':p.max_messages,'fan_sent':p.fan_sent,
            'creator_sent':p.creator_sent,'fan_remaining':max(0,p.max_messages-p.fan_sent),
            'creator_remaining':max(0,min(p.fan_sent,p.max_messages)-p.creator_sent),
            'expires_at':p.expires_at.isoformat()}

def close_expired(db,p):
    if not p or p.status!='ACTIVE' or aware(p.expires_at)>utcnow():return False
    r=db.get(CreatorRequest,p.request_id);pay=db.get(CreatorPayment,r.payment_id)
    p.status='EXPIRED'
    if p.creator_sent==0 and pay.status=='HELD':
        refund(db,pay);r.status='CANCELLED'
    else:
        # Partial service: don't silently pay or confiscate; admin review needed.
        r.status='EXPIRED'
    r.updated_at=utcnow()
    return True

def req_json(db,r,uid):
    pay=db.get(CreatorPayment,r.payment_id)
    ix=identity(db,r.creator_id)
    p=db.scalar(select(ProfessionalPass).where(ProfessionalPass.request_id==r.id))
    fan=db.get(User,r.fan_id)
    as_fan=uid==r.fan_id
    return {'id':r.id,'status':r.status,'kind':'CHAT','role':'FAN' if as_fan else 'CREATOR',
            'creator':{'public_id':ix.public_id,'handle':ix.handle,'stage_name':ix.stage_name,'avatar_url':public_avatar(ix)} if ix else None,
            'fan':{'display_name':fan.display_name,'username':fan.username} if fan else None,
            'message':r.message,'legacy_reply':r.creator_reply,'amount_q':q(pay.gross_micros),
            'thread_id':p.thread_id if p else None,'pass':pass_json(p),
            'created_at':r.created_at.isoformat()}

def thread_json(db,t,uid):
    ix=identity(db,t.creator_id)
    if not ix:raise HTTPException(409,'Creator has not created their professional identity')
    fan=db.get(User,t.fan_id)
    role='CREATOR' if uid==t.creator_id else 'FAN'
    p=latest_pass(db,t)
    return {'thread_id':t.id,'role':role,'creator':{'public_id':ix.public_id,'handle':ix.handle,
           'stage_name':ix.stage_name,'avatar_url':public_avatar(ix)},
           'fan':{'display_name':fan.display_name,'username':fan.username} if fan else None,
           'pass':pass_json(p),'is_professional':True,'updated_at':t.updated_at.isoformat()}

def offer_json(db,o,viewer):
    from .v2131_exclusives import CreatorGalleryItem, gallery_can_read
    item=db.get(CreatorGalleryItem,o.item_id)
    return {'id':o.id,'item_id':o.item_id,'title':item.title if item else 'Removed',
            'price_q':q(o.price_micros),'kind':item.kind if item else 'PHOTO',
            'unlocked':bool(item and gallery_can_read(db,item,viewer))}

def message_json(db,m,uid):
    out={'id':m.id,'role':m.role,'kind':m.kind,'body':m.body,
         'created_at':m.created_at.isoformat()}
    if m.kind=='OFFER' and m.offer_id:
        o=db.get(ProfessionalOffer,m.offer_id)
        out['offer']=offer_json(db,o,uid) if o else None
    if m.kind == 'DIRECT_MEDIA':
        from .v2135_direct_media import attach_json
        out['media'] = attach_json(db, m, uid)
    return out


def register_v2134_professional(app,current_user,get_db,push):
    router=APIRouter(prefix='/v2134',tags=['Q Creator Professional Identity & Chat'])

    @app.on_event('startup')
    def create_tables():
        from .database import engine
        Base.metadata.create_all(bind=engine)

    def who(u,db):
        p=db.get(CreatorProfile,u.id)
        if not p:raise HTTPException(403,'Create a Q Creator profile first')
        if p.status=='SUSPENDED':raise HTTPException(403,'Creator profile suspended')
        return p

    @router.get('/me')
    def my_professional_identity(u:User=Depends(current_user),db:Session=Depends(get_db)):
        p=db.get(CreatorProfile,u.id);x=identity(db,u.id)
        return {'has_creator_profile':bool(p),'creator_status':p.status if p else None,
            'identity':{'public_id':x.public_id,'handle':x.handle,'stage_name':x.stage_name,
                        'avatar_url':public_avatar(x)} if x else None,
            'terms':terms_for(db,u.id)}

    @router.put('/me')
    def upsert_identity(body:IdentityIn,u:User=Depends(current_user),db:Session=Depends(get_db)):
        who(u,db)
        handle=body.handle.strip().lstrip('@').lower()
        if not re.fullmatch(r'[a-z][a-z0-9_.]{2,31}',handle) or '..' in handle:
            raise HTTPException(422,'Professional username must start with a letter, 3–32 characters; letters, digits, _ or .')
        if handle in {'lemmiq','official','support','masteradmin','admin','system','q','creator'}:
            raise HTTPException(422,'Reserved professional username')
        from .v21311_release import enforce_username
        enforce_username(handle, db, u)
        # Separate namespaces, but avoid lookalikes in basic @ searches.
        if db.scalar(select(User.id).where(func.lower(User.username)==handle)):
            raise HTTPException(409,'This username is already in use')
        dup=db.scalar(select(CreatorIdentity).where(CreatorIdentity.handle==handle))
        if dup and dup.owner_id!=u.id:raise HTTPException(409,'Professional username already in use')
        x=identity(db,u.id)
        if not x:
            x=CreatorIdentity(owner_id=u.id,public_id='cr_'+secrets.token_hex(16),
                              handle=handle,stage_name=body.stage_name.strip())
            db.add(x)
        else:
            x.handle=handle;x.stage_name=body.stage_name.strip();x.updated_at=utcnow()
        db.commit()
        return {'public_id':x.public_id,'handle':x.handle,'stage_name':x.stage_name,'avatar_url':public_avatar(x)}

    @router.post('/me/avatar')
    async def upload_avatar(file:UploadFile=File(...),u:User=Depends(current_user),db:Session=Depends(get_db)):
        who(u,db);x=identity(db,u.id)
        if not x:raise HTTPException(409,'Choose your professional username first')
        mime=(file.content_type or '').split(';')[0].lower()
        if mime not in {'image/jpeg','image/png','image/webp'}:raise HTTPException(415,'Use JPEG, PNG or WebP')
        data=await file.read(5*1024*1024+1)
        if not data or len(data)>5*1024*1024:raise HTTPException(413,'Professional photo must be 5 MB or less')
        x.avatar_key=media_store.store(data);x.avatar_mime=mime;x.updated_at=utcnow()
        db.commit()
        return {'avatar_url':public_avatar(x)}

    @router.get('/avatars/{public_id}')
    def avatar(public_id:str,db:Session=Depends(get_db)):
        x=by_public(db,public_id)
        if not x or not x.avatar_key:raise HTTPException(404,'Photo unavailable')
        p=db.get(CreatorProfile,x.owner_id)
        if not p or p.status!='APPROVED':
            raise HTTPException(404,'Photo unavailable')
        return StreamingResponse(media_store.stream(x.avatar_key),media_type=x.avatar_mime,
                     headers={'Cache-Control':'public, max-age=60','X-Content-Type-Options':'nosniff'})

    @router.put('/me/terms')
    def update_terms(body:ChatTermsIn,u:User=Depends(current_user),db:Session=Depends(get_db)):
        who(u,db)
        t=db.get(ProfessionalTerms,u.id)
        if not t:t=ProfessionalTerms(creator_id=u.id);db.add(t)
        t.messages=body.messages;t.hours=body.hours;db.commit()
        return terms_for(db,u.id)

    @router.get('/discover')
    def discover(qtext:str='',following:bool=False,limit:int=50,u:User=Depends(current_user),db:Session=Depends(get_db)):
        s=select(CreatorIdentity).join(CreatorProfile,CreatorProfile.user_id==CreatorIdentity.owner_id).where(
            CreatorProfile.status=='APPROVED',CreatorProfile.level.in_(('MAINSTREAM','GLAMOUR')))
        if following:s=s.join(CreatorFollow,(CreatorFollow.creator_id==CreatorIdentity.owner_id)&(CreatorFollow.fan_id==u.id))
        if qtext.strip():
            term=qtext.strip().lower().lstrip('@')[:60]
            s=s.where(or_(func.lower(CreatorIdentity.handle).contains(term),func.lower(CreatorIdentity.stage_name).contains(term)))
        rows=db.scalars(s.order_by(CreatorIdentity.updated_at.desc()).limit(min(max(limit,1),100))).all()
        return [professional_card(db,x,u.id) for x in rows]

    @router.get('/profiles/{public_id}')
    def view_profile(public_id:str,u:User=Depends(current_user),db:Session=Depends(get_db)):
        x=by_public(db,public_id)
        if not x:raise HTTPException(404,'Professional creator not found')
        return {'profile':professional_card(db,x,u.id),'terms':terms_for(db,x.owner_id)}

    @router.post('/profiles/{public_id}/requests')
    def request_chat(public_id:str,body:ChatRequestIn,u:User=Depends(current_user),db:Session=Depends(get_db)):
        x=by_public(db,public_id)
        if not x:raise HTTPException(404,'Professional creator not found')
        p=creator_ready(db,x.owner_id)
        if u.id==x.owner_id:raise HTTPException(422,'Cannot request your own chat')
        if not p.chat_micros:raise HTTPException(409,'Paid chat is not offered by this creator')
        if blocked(db,x.owner_id,u.id):raise HTTPException(403,'Conversation blocked')
        # Prevent simultaneous unpaid/held duplicate requests and active passes.
        db.execute(select(User.id).where(User.id.in_(sorted((u.id,x.owner_id)))).order_by(User.id).with_for_update()).all()
        prior=db.scalar(select(CreatorRequest).where(CreatorRequest.creator_id==x.owner_id,
            CreatorRequest.fan_id==u.id,CreatorRequest.kind=='CHAT',
            CreatorRequest.status.in_(('REQUESTED','ACCEPTED','ACTIVE'))).order_by(CreatorRequest.id.desc()).limit(1))
        if prior:
            pay=db.get(CreatorPayment,prior.payment_id)
            if pay and pay.request_key==body.request_key:return req_json(db,prior,u.id)
            if prior.status=='ACTIVE':
                pass_row=db.scalar(select(ProfessionalPass).where(ProfessionalPass.request_id==prior.id))
                if not pass_row:raise HTTPException(409,'Move the existing paid chat to Professional Inbox before a new purchase')
                if close_expired(db,pass_row):db.flush()
                else:raise HTTPException(409,'Existing paid chat pass is still active')
            else:raise HTTPException(409,'A request is already awaiting creator acceptance')
        if not body.message.strip() or len(body.message.strip())<3:
            raise HTTPException(422,'Describe your chat request')
        payment,created=create_payment(db,u.id,x.owner_id,'CHAT',None,p.chat_micros,body.request_key,hold=True)
        r=db.scalar(select(CreatorRequest).where(CreatorRequest.payment_id==payment.id))
        if created:
            r=CreatorRequest(payment_id=payment.id,creator_id=x.owner_id,fan_id=u.id,kind='CHAT',
                             status='REQUESTED',message=body.message.strip())
            db.add(r);db.commit();db.refresh(r)
        else:db.commit()
        return req_json(db,r,u.id)

    @router.get('/requests')
    def requests(u:User=Depends(current_user),db:Session=Depends(get_db)):
        rows=db.scalars(select(CreatorRequest).where(CreatorRequest.kind=='CHAT',
            or_(CreatorRequest.creator_id==u.id,CreatorRequest.fan_id==u.id)).order_by(CreatorRequest.id.desc()).limit(100)).all()
        return [req_json(db,r,u.id) for r in rows if identity(db,r.creator_id)]

    def participant(db,rid,uid):
        r=db.get(CreatorRequest,rid)
        if not r or r.kind!='CHAT' or uid not in (r.creator_id,r.fan_id):
            raise HTTPException(404,'Professional request unavailable')
        return r

    @router.post('/requests/{rid}/accept')
    async def accept(rid:int,u:User=Depends(current_user),db:Session=Depends(get_db)):
        r=participant(db,rid,u.id)
        if u.id!=r.creator_id:raise HTTPException(403,'Only creator can accept')
        if not identity(db,u.id):raise HTTPException(409,'Create professional username before accepting')
        if r.status not in ('REQUESTED','ACCEPTED'):raise HTTPException(409,'Request is not pending')
        if r.status=='REQUESTED':r.status='ACCEPTED';r.updated_at=utcnow();db.commit()
        await push(r.fan_id,{'type':'creator_professional_accepted','request_id':r.id})
        return req_json(db,r,u.id)

    @router.post('/requests/{rid}/confirm')
    async def confirm(rid:int,u:User=Depends(current_user),db:Session=Depends(get_db)):
        r=participant(db,rid,u.id)
        if u.id!=r.fan_id:raise HTTPException(403,'Only fan can confirm')
        old=db.scalar(select(ProfessionalPass).where(ProfessionalPass.request_id==r.id))
        if old:return req_json(db,r,u.id)
        if r.status not in ('ACCEPTED','ACTIVE'):raise HTTPException(409,'Creator acceptance required')
        creator_ready(db,r.creator_id)
        if not identity(db,r.creator_id):raise HTTPException(409,'Creator professional identity unavailable')
        pay=db.get(CreatorPayment,r.payment_id)
        if pay.status!='HELD':raise HTTPException(409,'Payment is no longer reserved')
        t=ensure_thread(db,r.creator_id,r.fan_id)
        active=db.scalar(select(ProfessionalPass).where(ProfessionalPass.thread_id==t.id,
            ProfessionalPass.status=='ACTIVE').with_for_update())
        if active and not close_expired(db,active):raise HTTPException(409,'Existing session still active')
        earnings(db,r.creator_id) # create BEFORE message settlement so no nested flush
        opts=terms_for(db,r.creator_id)
        session=ProfessionalPass(request_id=r.id,thread_id=t.id,status='ACTIVE',max_messages=opts['messages'],
            expires_at=utcnow()+timedelta(hours=opts['hours']))
        db.add(session);r.status='ACTIVE';r.updated_at=utcnow();t.updated_at=utcnow()
        db.commit()
        await push(r.creator_id,{'type':'creator_professional_started','request_id':r.id})
        return req_json(db,r,u.id)

    @router.post('/requests/{rid}/cancel')
    def cancel(rid:int,u:User=Depends(current_user),db:Session=Depends(get_db)):
        r=participant(db,rid,u.id)
        if r.status not in ('REQUESTED','ACCEPTED'):
            raise HTTPException(409,'An active session requires a refund/dispute review')
        pay=db.get(CreatorPayment,r.payment_id)
        refund(db,pay);r.status='CANCELLED';r.updated_at=utcnow();db.commit()
        return req_json(db,r,u.id)

    @router.post('/requests/{rid}/open')
    def open_completed(rid:int,u:User=Depends(current_user),db:Session=Depends(get_db)):
        r=participant(db,rid,u.id)
        existing=db.scalar(select(ProfessionalPass).where(ProfessionalPass.request_id==r.id))
        if existing:return req_json(db,r,u.id)
        if r.status!='COMPLETED':
            raise HTTPException(409,'Fan must first confirm any earlier delivered reply before it can be viewed as settled history')
        # A completed old request imports only the agreed request and supplied reply.
        # No normal personal Chat or Message rows are copied or exposed.
        t=ensure_thread(db,r.creator_id,r.fan_id)
        p=ProfessionalPass(request_id=r.id,thread_id=t.id,status='COMPLETED',max_messages=0,
            expires_at=utcnow())
        db.add(p)
        if r.message:db.add(ProfessionalMessage(thread_id=t.id,role='FAN',body=r.message,request_id=r.id))
        if r.creator_reply:db.add(ProfessionalMessage(thread_id=t.id,role='CREATOR',body=r.creator_reply,request_id=r.id))
        t.updated_at=utcnow();db.commit()
        return req_json(db,r,u.id)


    @router.post('/requests/{rid}/legacy-confirm')
    def legacy_confirm(rid:int,u:User=Depends(current_user),db:Session=Depends(get_db)):
        r=participant(db,rid,u.id)
        if u.id!=r.fan_id or r.status!='DELIVERED':
            raise HTTPException(409,'Only fan can confirm an earlier delivered reply')
        pay=db.get(CreatorPayment,r.payment_id)
        if not pay or pay.status!='HELD':raise HTTPException(409,'No payment awaiting settlement')
        settle_held(db,pay);r.status='COMPLETED';r.updated_at=utcnow()
        db.commit()
        return req_json(db,r,u.id)

    @router.get('/inbox')
    def inbox(u:User=Depends(current_user),db:Session=Depends(get_db)):
        ts=db.scalars(select(ProfessionalThread).where(or_(ProfessionalThread.creator_id==u.id,
                  ProfessionalThread.fan_id==u.id)).order_by(ProfessionalThread.updated_at.desc()).limit(100)).all()
        return [thread_json(db,t,u.id) for t in ts]

    @router.get('/chats/{tid}')
    def chat(tid:str,u:User=Depends(current_user),db:Session=Depends(get_db)):
        t=require_thread(db,tid,u.id)
        p=latest_pass(db,t)
        if p and close_expired(db,p):db.commit()
        out=thread_json(db,t,u.id)
        out['messages']=[message_json(db,x,u.id) for x in db.scalars(select(ProfessionalMessage).where(
            ProfessionalMessage.thread_id==tid).order_by(ProfessionalMessage.id.desc()).limit(200)).all()][::-1]
        return out

    @router.post('/chats/{tid}/messages')
    async def send_message(tid:str,body:TextIn,u:User=Depends(current_user),db:Session=Depends(get_db)):
        t=require_thread(db,tid,u.id)
        if blocked(db,t.creator_id,t.fan_id):raise HTTPException(403,'Conversation blocked')
        creator_ready(db,t.creator_id)
        # Lock participants AND conversation for concurrent requests across devices.
        db.execute(select(User.id).where(User.id.in_(sorted((t.creator_id,t.fan_id)))).order_by(User.id).with_for_update()).all()
        db.execute(select(ProfessionalThread.id).where(ProfessionalThread.id==tid).with_for_update()).all()
        p=latest_pass(db,t,lock=True)
        if not p or p.status!='ACTIVE':raise HTTPException(402,'Buy another paid chat pass to continue')
        if close_expired(db,p):db.commit();raise HTTPException(409,'Paid chat pass expired')
        role='CREATOR' if u.id==t.creator_id else 'FAN'
        if role=='FAN':
            if p.fan_sent>=p.max_messages:raise HTTPException(402,'All included fan messages have been sent. Wait for creator replies, then request another pass.')
            p.fan_sent+=1
        else:
            if p.creator_sent>=p.fan_sent or p.creator_sent>=p.max_messages:
                raise HTTPException(402,'No paid creator reply is due yet. Wait for the fan to send their next message.')
            p.creator_sent+=1
            if p.creator_sent==p.max_messages and p.fan_sent==p.max_messages:
                r=db.get(CreatorRequest,p.request_id)
                pay=db.get(CreatorPayment,r.payment_id)
                if pay.status=='HELD':settle_held(db,pay)
                p.status='COMPLETED';r.status='COMPLETED';r.updated_at=utcnow()
        m=ProfessionalMessage(thread_id=t.id,role=role,body=body.text.strip(),request_id=p.request_id)
        db.add(m);t.updated_at=utcnow();db.commit();db.refresh(m)
        other=t.fan_id if u.id==t.creator_id else t.creator_id
        await push(other,{'type':'creator_professional_message','thread_id':tid})
        return {'message':message_json(db,m,u.id),'pass':pass_json(p)}

    # V21342_FAN_FINISH: fan may voluntarily complete a delivered partial pass.
    # Never settle a service with outstanding creator replies or zero delivered replies.
    @router.post('/chats/{tid}/complete')
    def complete_professional_chat(tid:str,u:User=Depends(current_user),db:Session=Depends(get_db)):
        t=require_thread(db,tid,u.id)
        if u.id!=t.fan_id:raise HTTPException(403,'Only the paying fan can confirm completion')
        db.execute(select(User.id).where(User.id.in_(sorted((t.creator_id,t.fan_id)))).order_by(User.id).with_for_update()).all()
        db.execute(select(ProfessionalThread.id).where(ProfessionalThread.id==tid).with_for_update()).all()
        p=latest_pass(db,t,lock=True)
        if not p:raise HTTPException(409,'No paid chat pass exists')
        if p.status=='COMPLETED':return thread_json(db,t,u.id)
        if p.status!='ACTIVE':raise HTTPException(409,'Only an active pass can be completed')
        if close_expired(db,p):db.commit();raise HTTPException(409,'The pass expired; contact support for settlement')
        if p.fan_sent<1 or p.creator_sent<1:
            raise HTTPException(409,'At least one fan message and one creator reply must be delivered')
        if p.creator_sent!=p.fan_sent:
            raise HTTPException(409,'Wait for all outstanding creator replies before completing')
        r=db.get(CreatorRequest,p.request_id)
        payment=db.get(CreatorPayment,r.payment_id)
        if payment.status=='HELD':settle_held(db,payment)
        elif payment.status!='CAPTURED':raise HTTPException(409,'Payment is unavailable for settlement')
        p.status='COMPLETED';r.status='COMPLETED';r.updated_at=utcnow();t.updated_at=utcnow()
        db.commit()
        return thread_json(db,t,u.id)

    @router.post('/chats/{tid}/offers')
    async def offer(tid:str,body:OfferIn,u:User=Depends(current_user),db:Session=Depends(get_db)):
        from .v2131_exclusives import CreatorGalleryItem
        t=require_thread(db,tid,u.id)
        if u.id!=t.creator_id:raise HTTPException(403,'Only the professional creator can send paid media')
        creator_ready(db,t.creator_id)
        if blocked(db,t.creator_id,t.fan_id):raise HTTPException(403,'Conversation blocked')
        item=db.get(CreatorGalleryItem,body.item_id)
        if not item or item.creator_id!=u.id or item.review!='APPROVED':
            raise HTTPException(404,'Approved gallery item unavailable')
        cost=to_micros(body.price_q)
        old=db.scalar(select(ProfessionalOffer).where(ProfessionalOffer.request_key==body.request_key,
                        ProfessionalOffer.creator_id==u.id))
        if old:
            if old.thread_id!=tid or old.item_id!=body.item_id or old.price_micros!=cost:
                raise HTTPException(409,'Duplicate offer key belongs to another offer')
            return offer_json(db,old,u.id)
        o=ProfessionalOffer(thread_id=tid,item_id=body.item_id,creator_id=u.id,fan_id=t.fan_id,
                            price_micros=cost,request_key=body.request_key)
        db.add(o);db.flush()
        db.add(ProfessionalMessage(thread_id=tid,role='CREATOR',kind='OFFER',offer_id=o.id))
        t.updated_at=utcnow();db.commit()
        await push(t.fan_id,{'type':'creator_professional_offer','thread_id':tid})
        return offer_json(db,o,u.id)

    @router.post('/offers/{offer_id}/unlock')
    def unlock(offer_id:int,body:PurchaseIn,u:User=Depends(current_user),db:Session=Depends(get_db)):
        from .v2131_exclusives import (CreatorGalleryItem, CreatorGalleryUnlock, gallery_can_read)
        o=db.get(ProfessionalOffer,offer_id)
        if not o or u.id!=o.fan_id:raise HTTPException(404,'Private offer not found')
        item=db.get(CreatorGalleryItem,o.item_id)
        if not item or item.review not in ('APPROVED','DELETED'):raise HTTPException(404,'Content unavailable')
        creator_ready(db,o.creator_id)
        if blocked(db,o.creator_id,o.fan_id):raise HTTPException(403,'Conversation blocked')
        if gallery_can_read(db,item,u.id):return {'unlocked':True,'charged_q':0}
        if item.review=='DELETED':raise HTTPException(410,'Creator removed this item from sale')
        payment,created=create_payment(db,u.id,o.creator_id,'DM_PPV',o.id,o.price_micros,body.request_key)
        if payment.status!='CAPTURED':raise HTTPException(409,'Payment not valid')
        existing=db.scalar(select(CreatorGalleryUnlock.id).where(
            CreatorGalleryUnlock.fan_id==u.id,CreatorGalleryUnlock.item_id==item.id))
        if not existing:db.add(CreatorGalleryUnlock(fan_id=u.id,item_id=item.id,payment_id=payment.id))
        db.commit()
        return {'unlocked':True,'charged_q':q(payment.gross_micros) if created else 0}

    app.include_router(router)
