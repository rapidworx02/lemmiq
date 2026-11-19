"""LEMMIQ V2.13.11: names, official broadcasts, controlled category market refill.

New routes are intentionally separate from existing chat, creator and Q ledgers.
Broadcasts send genuine private chat messages from the configured official account.
Market refill only uses previously reviewed, admin-approved drafts.
"""
from __future__ import annotations
import asyncio
import logging
import os
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func, select
from sqlalchemy.orm import Mapped, Session, mapped_column
from .database import Base, SessionLocal
from .models import User, Chat, ChatSetting, Message, PushDevice
from .v28 import QAdminRole
from .v29 import PredictMarket, PredictConfig, _require_admin
from .v2123_support import official_user, ensure_official_chat
from . import push_service

LOG=logging.getLogger('lemmiq.v21311')
MAIN_LOOP=None

PROTECTED=(
    'lemmiq','qeconomy','qpredict','qcreators','qcreator','qexchange',
    'qwallet','qair','qrewards','qmarket','qagent','qassistant','qofficial',
    'lemmiqwallet','lemmiqsupport','businessagent','factcheck','scamcheck',
)
SINGLE_RESERVED={'support','admin','official','system','masteradmin','moderator'}
CONFUSABLE=str.maketrans({'0':'o','1':'i','3':'e','4':'a','5':'s','7':'t','@':'a','$':'s'})

def canonical_username(name: str) -> str:
    raw=unicodedata.normalize('NFKC',str(name or '')).casefold()
    # Strip separators and detect common leetspeak impersonation; alphabet-only
    # comparison is intentionally conservative on generic non-brand terms.
    return ''.join(c for c in raw.translate(CONFUSABLE) if c.isalnum())

def username_reserved(name: str) -> bool:
    raw=unicodedata.normalize('NFKC',str(name or '')).casefold()
    plain=''.join(c for c in raw if c.isalnum())
    cand=canonical_username(raw)
    return any(term in cand or term in plain for term in PROTECTED) or cand in SINGLE_RESERVED or plain in SINGLE_RESERVED

def enforce_username(name: str, db: Session|None = None, actor:User|None = None):
    if not username_reserved(name):return
    if actor is not None and db is not None:
        role=db.get(QAdminRole,actor.id)
        if role and role.active and role.role=='MASTER_ADMIN':return
    raise HTTPException(422,'Username Not Available: reserved for official LEMMIQ accounts or platform features')

def utcnow():return datetime.now(timezone.utc)

def admin_required(db,u):
    role=db.get(QAdminRole,u.id)
    if not role or not role.active or role.role!='MASTER_ADMIN':
        raise HTTPException(403,'Master Admin required')
    _require_admin(db,u,'FULL','Q_PREDICT')

class Campaign(Base):
    __tablename__='v21311_broadcast_campaigns'
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    creator_id:Mapped[int]=mapped_column(ForeignKey('users.id'))
    audience:Mapped[str]=mapped_column(String(20),default='ALL')
    kind:Mapped[str]=mapped_column(String(20),default='UPDATE')
    content:Mapped[str]=mapped_column(Text)
    status:Mapped[str]=mapped_column(String(20),default='DRAFT')
    max_recipient_id:Mapped[int]=mapped_column(Integer,default=0)
    last_user_id:Mapped[int]=mapped_column(Integer,default=0)
    delivered:Mapped[int]=mapped_column(Integer,default=0)
    skipped:Mapped[int]=mapped_column(Integer,default=0)
    scheduled_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)
    published_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    finished_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)

class Delivery(Base):
    __tablename__='v21311_broadcast_deliveries'
    __table_args__=(UniqueConstraint('campaign_id','recipient_id',name='uq_v21311_campaign_recipient'),)
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    campaign_id:Mapped[int]=mapped_column(ForeignKey('v21311_broadcast_campaigns.id'),index=True)
    recipient_id:Mapped[int]=mapped_column(ForeignKey('users.id'),index=True)
    message_id:Mapped[int]=mapped_column(ForeignKey('messages.id'))
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)

class BroadcastIn(BaseModel):
    text:str=Field(min_length=5,max_length=3900)
    audience:str=Field(default='ALL')
    kind:str=Field(default='UPDATE')
    scheduled_at:datetime|None=None

class MarketApprove(BaseModel):
    note:str=Field(min_length=8,max_length=240)

class LiveCapIn(BaseModel):
    global_live_cap:int=Field(ge=10,le=500)

CATS=('CRYPTO','ECONOMY','TECH_AI','ENTERTAINMENT','WEATHER','LEMMIQ')
SPORTS=('INTERNATIONAL','DOMESTIC','LEAGUES')

def category_key(m:PredictMarket):
    c=str(m.category or '').upper()
    if c!='SPORTS':return c
    from .v21310_predict_q import _classification
    sub=_classification(m)
    return f'SPORTS:{sub}'

def inventory(db):
    current=utcnow()
    rows=db.scalars(select(PredictMarket).where(PredictMarket.status=='LIVE',PredictMarket.close_at>current)).all()
    counts={k:0 for k in list(CATS)+['SPORTS:'+x for x in SPORTS]}
    for m in rows:
        k=category_key(m)
        if k in counts:counts[k]+=1
    return counts

def refill(db,uid):
    """Publish only pre-approved REVIEW/DRAFT markets, subject to configured system cap."""
    cfg=db.get(PredictConfig,1)
    if not cfg: return {'published':[],'reason':'Predict configuration missing'}
    # Coordinate concurrent refill workers using the persisted config row lock.
    db.execute(select(PredictConfig).where(PredictConfig.id==1).with_for_update()).first()
    counts=inventory(db)
    live_all=int(db.scalar(select(func.count()).select_from(PredictMarket).where(PredictMarket.status=='LIVE')) or 0)
    cap=max(0,int(cfg.max_live_markets or 0)-live_all)
    if cap<=0:return {'published':[],'counts':counts,'reason':'Global live-market cap reached; Admin must increase cap explicitly'}
    candidates=db.scalars(select(PredictMarket).where(PredictMarket.status.in_(['REVIEW','DRAFT']),
         PredictMarket.approved_by_user_id.is_not(None),PredictMarket.close_at>utcnow()+timedelta(minutes=30))
         .order_by(PredictMarket.close_at.asc()).limit(500)).all()
    published=[]
    for m in candidates:
        k=category_key(m)
        if k not in counts or counts[k]>=10 or cap<=0:continue
        # Never auto-publish unsigned, unverifiable, blank or high-risk templates.
        if len(str(m.resolution_rule or '').strip())<20:continue
        m.status='LIVE';m.updated_at=utcnow()
        counts[k]+=1;cap-=1;published.append(m.id)
    return {'published':published,'counts':counts,'remaining_global_slots':cap}

def campaign_dict(c):
    return {'id':c.id,'audience':c.audience,'kind':c.kind,'content':c.content,
      'status':c.status,'delivered':c.delivered,'skipped':c.skipped,'created_at':c.created_at.isoformat(),
      'scheduled_at':c.scheduled_at.isoformat() if c.scheduled_at else None}

def process_batch(campaign_id:int,batch_size:int=80):
    """Idempotent scan by User.id; transactions lock campaign row to avoid duplicate delivery.
       No all-user data is exposed to broadcast clients.
    """
    notices=[]
    with SessionLocal() as db:
        c=db.scalar(select(Campaign).where(Campaign.id==campaign_id).with_for_update())
        if not c or c.status not in ('QUEUED','SENDING'):return 0
        if c.scheduled_at:
            when=c.scheduled_at.replace(tzinfo=timezone.utc) if c.scheduled_at.tzinfo is None else c.scheduled_at
            if when>utcnow():return 0
        official=official_user(db)
        if not official:raise RuntimeError('Verified @lemmiq support account missing; broadcast halted')
        c.status='SENDING'
        users=db.scalars(select(User).where(User.id>c.last_user_id,User.id<=c.max_recipient_id)
             .order_by(User.id.asc()).limit(batch_size)).all()
        if not users:
            c.status='DONE';c.finished_at=utcnow();db.commit();return 0
        allowed_ids=None
        if c.audience=='VERIFIED':
            from .v21310_predict_q import _team_ids
            allowed_ids=_team_ids()
        for user in users:
            c.last_user_id=user.id
            if user.id==official.id or (allowed_ids is not None and user.id not in allowed_ids):
                c.skipped+=1;continue
            if c.audience=='CREATORS':
                from .v2134_professional import CreatorIdentity
                if not db.scalar(select(CreatorIdentity.owner_id).where(CreatorIdentity.owner_id==user.id)):
                    c.skipped+=1;continue
            if db.scalar(select(Delivery.id).where(Delivery.campaign_id==c.id,Delivery.recipient_id==user.id)):
                continue
            a,b=sorted((official.id,user.id))
            chat=db.scalar(select(Chat).where(Chat.user1_id==a,Chat.user2_id==b))
            if not chat:
                chat=Chat(user1_id=a,user2_id=b)
                db.add(chat);db.flush()
                db.add_all([ChatSetting(chat_id=chat.id,user_id=a),ChatSetting(chat_id=chat.id,user_id=b)])
            text={'UPDATE':'📢 LEMMIQ Update','MAINTENANCE':'🔧 LEMMIQ Service Notice','COMMUNITY':'💜 LEMMIQ Community'}.get(c.kind,'📢 LEMMIQ Announcement')+'\n\n'+c.content
            msg=Message(chat_id=chat.id,sender_id=official.id,text=text,ai_generated=False)
            db.add(msg);db.flush()
            db.add(Delivery(campaign_id=c.id,recipient_id=user.id,message_id=msg.id))
            chat.updated_at=utcnow();c.delivered+=1
            tokens=[d.token for d in db.scalars(select(PushDevice).where(PushDevice.user_id==user.id)).all()]
            from .main import msg_json
            data=msg_json(msg,db)
            notices.append((user.id,tokens,chat.id,text,data))
        if users[-1].id>=c.max_recipient_id:c.status='DONE';c.finished_at=utcnow()
        db.commit()
    for recipient_id,tokens,chat_id,text,data in notices:
        try:push_service.notify(tokens,'LEMMIQ Official',chat_id,text,1)
        except Exception:LOG.exception('Push failed; chat message already delivered')
        if MAIN_LOOP and MAIN_LOOP.is_running():
            try:
                from .main import push
                asyncio.run_coroutine_threadsafe(push(recipient_id,{'type':'message','data':data}),MAIN_LOOP)
            except Exception:LOG.exception('WebSocket broadcast delivery failed')
    return len(users)

def process_remaining(campaign_id:int):
    for _ in range(1000):
        try:n=process_batch(campaign_id)
        except Exception:LOG.exception('Broadcast %s interrupted; resume from Admin',campaign_id);return
        if not n:return

def register_v21311_release(app,current_user,get_db):
    router=APIRouter(prefix='/v21311',tags=['LEMMIQ 2.13.11 Announcements and Protection'])

    @router.get('/support/open')
    def open_support(u:User=Depends(current_user),db:Session=Depends(get_db)):
        official=official_user(db)
        if not official:raise HTTPException(503,'Official support chat unavailable')
        if u.id==official.id:raise HTTPException(409,'Support account cannot open a chat with itself')
        a,b=sorted((official.id,u.id))
        chat=db.scalar(select(Chat).where(Chat.user1_id==a,Chat.user2_id==b))
        if not chat:
            chat=Chat(user1_id=a,user2_id=b)
            db.add(chat);db.flush()
            db.add_all([ChatSetting(chat_id=chat.id,user_id=a),ChatSetting(chat_id=chat.id,user_id=b)])
        db.commit()
        return {'chat_id':chat.id,'username':official.username,'display_name':official.display_name}

    @router.get('/admin/reserved-name-conflicts')
    def reserved_conflicts(u:User=Depends(current_user),db:Session=Depends(get_db)):
        admin_required(db,u)
        users=db.scalars(select(User).order_by(User.id).limit(5000)).all()
        from .v2134_professional import CreatorIdentity
        creators=db.scalars(select(CreatorIdentity).limit(5000)).all()
        def is_master(uid):
            role=db.get(QAdminRole,uid)
            return bool(role and role.active and role.role=='MASTER_ADMIN')
        return {'personal':[{'id':x.id,'username':x.username} for x in users if username_reserved(x.username) and not is_master(x.id)],
             'professional':[{'owner_id':x.owner_id,'handle':x.handle} for x in creators if username_reserved(x.handle) and not is_master(x.owner_id)],
             'note':'Review flagged existing names manually; do not change account handles automatically.'}

    @router.get('/admin/broadcasts')
    def broadcasts(u:User=Depends(current_user),db:Session=Depends(get_db)):
        admin_required(db,u)
        rows=db.scalars(select(Campaign).order_by(Campaign.id.desc()).limit(60)).all()
        return {'items':[campaign_dict(x) for x in rows]}

    @router.post('/admin/broadcasts')
    def create_broadcast(body:BroadcastIn,u:User=Depends(current_user),db:Session=Depends(get_db)):
        admin_required(db,u)
        if body.audience not in ('ALL','VERIFIED','CREATORS'):raise HTTPException(422,'Unsupported audience')
        if body.kind not in ('UPDATE','MAINTENANCE','COMMUNITY'):raise HTTPException(422,'Unsupported announcement type')
        if body.scheduled_at is not None:
            ts=body.scheduled_at.replace(tzinfo=timezone.utc) if body.scheduled_at.tzinfo is None else body.scheduled_at
            if ts<utcnow() or ts>utcnow()+timedelta(days=90):raise HTTPException(422,'Schedule must be within 90 days')
        c=Campaign(creator_id=u.id,audience=body.audience,kind=body.kind,content=body.text.strip(),scheduled_at=body.scheduled_at)
        db.add(c);db.commit();db.refresh(c)
        return campaign_dict(c)

    @router.post('/admin/broadcasts/{campaign_id}/publish')
    def publish_broadcast(campaign_id:int,background:BackgroundTasks,u:User=Depends(current_user),db:Session=Depends(get_db)):
        admin_required(db,u)
        c=db.scalar(select(Campaign).where(Campaign.id==campaign_id).with_for_update())
        if not c or c.status!='DRAFT':raise HTTPException(409,'Only drafts can be published')
        if not official_user(db):raise HTTPException(503,'Official support account not configured')
        c.max_recipient_id=int(db.scalar(select(func.max(User.id))) or 0)
        c.published_at=utcnow();c.status='QUEUED';db.commit()
        if not c.scheduled_at:background.add_task(process_remaining,c.id)
        return campaign_dict(c)

    @router.post('/admin/broadcasts/{campaign_id}/resume')
    def resume_broadcast(campaign_id:int,background:BackgroundTasks,u:User=Depends(current_user),db:Session=Depends(get_db)):
        admin_required(db,u)
        c=db.get(Campaign,campaign_id)
        if not c or c.status not in ('QUEUED','SENDING'):raise HTTPException(409,'Broadcast not queued')
        background.add_task(process_remaining,c.id)
        return campaign_dict(c)

    @router.get('/admin/market-refill')
    def refill_status(u:User=Depends(current_user),db:Session=Depends(get_db)):
        admin_required(db,u)
        cfg=db.get(PredictConfig,1)
        return {'target_per_category':10,'counts':inventory(db),
             'auto_enabled':os.getenv('LEMMIQ_PREDICT_AUTO_REFILL_ENABLED','false').lower()=='true',
             'global_live_cap':int(cfg.max_live_markets or 0) if cfg else 0}

    @router.put('/admin/market-refill/global-cap')
    def set_live_cap(body:LiveCapIn,u:User=Depends(current_user),db:Session=Depends(get_db)):
        admin_required(db,u)
        cfg=db.get(PredictConfig,1)
        if not cfg:raise HTTPException(503,'Q Predict configuration missing')
        cfg.max_live_markets=body.global_live_cap
        db.commit()
        return {'global_live_cap':cfg.max_live_markets,'changed_by':u.id}

    @router.post('/admin/market-refill/approve/{market_id}')
    def approve_refill_candidate(market_id:int,body:MarketApprove,u:User=Depends(current_user),db:Session=Depends(get_db)):
        admin_required(db,u)
        market=db.scalar(select(PredictMarket).where(PredictMarket.id==market_id).with_for_update())
        if not market or market.status not in ('REVIEW','DRAFT'):raise HTTPException(409,'Not a draft awaiting approval')
        if len(str(market.resolution_rule or '').strip())<20:raise HTTPException(422,'Settlement rule incomplete')
        market.approved_by_user_id=u.id;market.updated_at=utcnow();db.commit()
        return {'approved_for_refill':market_id,'note':body.note,'auto_publish_later':True}

    @router.post('/admin/market-refill/run')
    def run_refill(u:User=Depends(current_user),db:Session=Depends(get_db)):
        admin_required(db,u)
        out=refill(db,u.id);db.commit();return out

    app.include_router(router)

    @app.on_event('startup')
    async def _v21311_poll():
        global MAIN_LOOP
        MAIN_LOOP=asyncio.get_running_loop()
        async def loop():
            while True:
                await asyncio.sleep(300)
                try:
                    if os.getenv('LEMMIQ_PREDICT_AUTO_REFILL_ENABLED','false').lower()=='true':
                        with SessionLocal() as db:
                            refill(db,0);db.commit()
                    with SessionLocal() as db:
                        pending=db.scalars(select(Campaign.id).where(Campaign.status.in_(('QUEUED','SENDING'))).limit(10)).all()
                    for cid in pending:await asyncio.to_thread(process_remaining,cid)
                except Exception:LOG.exception('Announcement/refill scheduler task failed')
        asyncio.create_task(loop())
