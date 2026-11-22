"""V3.1.0 Q action centre. Read models only for financial activity.
Business acknowledgements/replies are ordinary messages, never ledger operations.
"""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import logging
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import Integer, String, Text, DateTime, Boolean, ForeignKey, UniqueConstraint, select, or_, func, update
from sqlalchemy.orm import Mapped, mapped_column
from .database import Base
from .models import User, Chat, Message, BusinessProfile, BusinessChatSetting, UserBlock, AutoReplyReceipt

log=logging.getLogger(__name__)
def now(): return datetime.now(timezone.utc)
def aware(t): return t if t.tzinfo else t.replace(tzinfo=timezone.utc)
ACK='Thank you for your message. Your enquiry needs a team member to review it before we can provide an answer.'
class ActionPrefs310(Base):
    __tablename__='q_action_prefs310'
    user_id:Mapped[int]=mapped_column(ForeignKey('users.id'),primary_key=True)
    economy:Mapped[bool]=mapped_column(Boolean,default=True)
    results:Mapped[bool]=mapped_column(Boolean,default=True)
    creators:Mapped[bool]=mapped_column(Boolean,default=False)
    markets:Mapped[bool]=mapped_column(Boolean,default=False)
    acknowledgement:Mapped[bool]=mapped_column(Boolean,default=True)
class Action310(Base):
    __tablename__='q_actions310'
    __table_args__=(UniqueConstraint('user_id','event_key',name='uq_q_actions310_user_event'),)
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    user_id:Mapped[int]=mapped_column(ForeignKey('users.id'),index=True)
    event_key:Mapped[str]=mapped_column(String(160))
    category:Mapped[str]=mapped_column(String(20),index=True)
    title:Mapped[str]=mapped_column(String(200))
    body:Mapped[str]=mapped_column(Text,default='')
    status:Mapped[str]=mapped_column(String(24),default='INFO')
    chat_id:Mapped[int|None]=mapped_column(Integer,nullable=True)
    trigger_id:Mapped[int|None]=mapped_column(Integer,nullable=True)
    ack_id:Mapped[int|None]=mapped_column(Integer,nullable=True)
    reply_id:Mapped[int|None]=mapped_column(Integer,nullable=True)
    draft:Mapped[str]=mapped_column(Text,default='')
    reason:Mapped[str]=mapped_column(String(240),default='')
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now,index=True)
    read_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)

class PrefsIn(BaseModel):
    economy:bool=True
    results:bool=True
    creators:bool=False
    markets:bool=False
    acknowledgement:bool=True
class DecisionIn(BaseModel):
    action:str
    text:str=Field(default='',max_length=1800)

def prefs(db,uid):
    row=db.get(ActionPrefs310,uid)
    return {k: bool(getattr(row,k)) if row else v for k,v in PrefsIn().model_dump().items()}
def get_event(db,uid,key): return db.scalar(select(Action310).where(Action310.user_id==uid,Action310.event_key==key))
def emit(db,uid,key,category,title,body,**kwargs):
    old=get_event(db,uid,key)
    if old:return old
    # SAVEPOINT keeps a concurrent duplicate from aborting the caller's transaction.
    from sqlalchemy.exc import IntegrityError
    try:
        with db.begin_nested():
            row=Action310(user_id=uid,event_key=key,category=category,title=title,body=body,**kwargs)
            db.add(row);db.flush()
        return row
    except IntegrityError:
        return get_event(db,uid,key)

def queue_review(db,chat,owner,trigger,decision,reason,draft=''):
    """Caller owns transaction. Serialize per chat, maintain one current pending review."""
    db.scalar(select(Chat).where(Chat.id==chat.id).with_for_update())
    setting=db.get(BusinessChatSetting,{'user_id':owner,'chat_id':chat.id})
    profile=db.get(BusinessProfile,owner)
    if setting:db.refresh(setting)
    if profile:db.refresh(profile)
    if not setting or not setting.enabled or setting.mode!='AUTO' or not profile or not profile.enabled:return None,None
    if db.get(AutoReplyReceipt,trigger.id):return None,None
    if db.get(UserBlock,{'blocker_id':owner,'blocked_id':trigger.sender_id}) or db.get(UserBlock,{'blocker_id':trigger.sender_id,'blocked_id':owner}):return None,None
    latest=db.scalar(select(Message.id).where(Message.chat_id==chat.id,Message.sender_id!=owner).order_by(Message.id.desc()).limit(1))
    if latest!=trigger.id:return None,None
    existing=get_event(db,owner,f'business:{trigger.id}')
    if existing:return existing,None
    pending=db.scalars(select(Action310).where(Action310.user_id==owner,Action310.chat_id==chat.id,Action310.status=='PENDING')).all()
    ack_ids=[r.ack_id for r in pending if r.ack_id]
    q=select(Message.id).where(Message.chat_id==chat.id,Message.sender_id==owner,Message.id>trigger.id)
    if ack_ids:q=q.where(~Message.id.in_(ack_ids))
    if db.scalar(q.limit(1)):return None,None
    for r in pending:r.status='SUPERSEDED'
    sender=db.get(User,trigger.sender_id)
    # Do not copy sensitive customer text (e.g. credentials) into a second store.
    safe_draft=str(draft or '')[:1800]
    row=emit(db,owner,f'business:{trigger.id}','BUSINESS','Customer enquiry needs review',
        f'{sender.display_name if sender else "Customer"} sent a message that needs your attention. Open the conversation for the original message.',
        status='PENDING',chat_id=chat.id,trigger_id=trigger.id,draft=safe_draft,reason=reason[:240])
    if row is None:return None,None
    ack=None
    if prefs(db,owner)['acknowledgement'] and not pending:
        ack=Message(chat_id=chat.id,sender_id=owner,text=ACK,ai_generated=True)
        chat.updated_at=now();db.add(ack);db.flush();row.ack_id=ack.id
    return row,ack

def reconcile_reviews(db,uid):
    rows=db.scalars(select(Action310).where(Action310.user_id==uid,Action310.status=='PENDING')).all()
    for r in rows:
        q=select(Message.id).where(Message.chat_id==r.chat_id,Message.sender_id==uid,Message.id>r.trigger_id)
        if r.ack_id:q=q.where(Message.id!=r.ack_id)
        # Ignore acknowledgements created for any review in this conversation.
        q=q.where(~Message.id.in_(select(Action310.ack_id).where(Action310.user_id==uid,Action310.chat_id==r.chat_id,Action310.ack_id.is_not(None))))
        if db.scalar(q.limit(1)):
            db.execute(update(Action310).where(Action310.id==r.id,Action310.status=='PENDING').values(status='RESOLVED'))


def units(n):return f'{Decimal(int(n or 0))/Decimal(1000000):,.6f}'.rstrip('0').rstrip('.')
def sync_activity(db,uid,include_discovery=True):
    """Bounded lookback; source rows are authoritative and already committed.
    No staking, payout, pricing, balance updates or AI provider calls here.
    """
    from .v29 import PredictMarket
    from .v2138_predict import DemoPosition, DemoPool
    from .v21310_predict_q import Position, Pool
    from .v28 import QLedgerEntry, QUserWallet
    from .v21317_assistant import QAssistantPrefs317, _quiet_hour
    from .v213_creators import CreatorProfile
    from .v2134_professional import CreatorIdentity
    p=prefs(db,uid);t=now();cut=t-timedelta(days=7)
    old=db.get(QAssistantPrefs317,uid)
    enabled=not old or (old.enabled and old.frequency!='OFF')
    try:tz=ZoneInfo(old.timezone_name if old else 'UTC')
    except Exception:tz=timezone.utc
    local=t.astimezone(tz);day=local.date().isoformat()
    start=local.replace(hour=0,minute=0,second=0,microsecond=0).astimezone(timezone.utc)
    # Participant-only lifecycle alerts, one per market + unit + state; never promotional.
    if p['results']:
        for pos,pool,unit in ((DemoPosition,DemoPool,'Demo USDT'),(Position,Pool,'Q Predict Q')):
            joined=db.execute(select(pos,PredictMarket,pool).join(PredictMarket,PredictMarket.id==pos.market_id).outerjoin(pool,pool.market_id==pos.market_id).where(pos.user_id==uid,or_(PredictMarket.updated_at>=cut,pool.settled_at>=cut)).order_by(PredictMarket.updated_at.desc()).limit(200)).all()
            grouped={}
            for x,m,pl in joined:grouped.setdefault(m.id,(m,pl,[]))[2].append(x)
            for mid,(m,pl,positions) in grouped.items():
                key=f'predict:{"Demo Q" if unit=="Demo USDT" else unit}:{mid}'
                if pl and pl.settled_at and all(x.status in ('WON','LOST','VOID') for x in positions):
                    body=m.question+'\n'+'\n'.join(f'{x.outcome}: {x.status} | stake {units(x.stake_micros)} {unit} | payout {units(x.payout_micros)} {unit}' for x in positions)
                    emit(db,uid,key+':settled','PREDICT','Your prediction has settled',body)
                elif m.status in ('CLOSED','RESOLVING','RESOLVED','VOID') and any(x.status=='OPEN' for x in positions):
                    emit(db,uid,key+':closed','PREDICT','Your prediction market is closed',m.question+'\nAwaiting settlement in '+unit+'.')
    if not enabled or (old and _quiet_hour(old,t)):return
    # Daily wallet flow: credits/debits, not investment income. Exclude self-transfers.
    if p['economy']:
        w=db.get(QUserWallet,uid)
        if w:
            credits=db.scalar(select(func.coalesce(func.sum(QLedgerEntry.amount_micros),0)).where(QLedgerEntry.to_user_id==uid,or_(QLedgerEntry.from_user_id.is_(None),QLedgerEntry.from_user_id!=uid),QLedgerEntry.created_at>=start)) or 0
            debits=db.scalar(select(func.coalesce(func.sum(QLedgerEntry.amount_micros),0)).where(QLedgerEntry.from_user_id==uid,or_(QLedgerEntry.to_user_id.is_(None),QLedgerEntry.to_user_id!=uid),QLedgerEntry.created_at>=start)) or 0
            if credits or debits:
                received=db.execute(select(QLedgerEntry.kind,func.sum(QLedgerEntry.amount_micros)).where(QLedgerEntry.to_user_id==uid,or_(QLedgerEntry.from_user_id.is_(None),QLedgerEntry.from_user_id!=uid),QLedgerEntry.created_at>=start).group_by(QLedgerEntry.kind)).all()
                spent=db.execute(select(QLedgerEntry.kind,func.sum(QLedgerEntry.amount_micros)).where(QLedgerEntry.from_user_id==uid,or_(QLedgerEntry.to_user_id.is_(None),QLedgerEntry.to_user_id!=uid),QLedgerEntry.created_at>=start).group_by(QLedgerEntry.kind)).all()
                rewards=sum(v for k,v in received if k in {'BASIC_DAILY','REFERRAL_REWARD','REFERRAL_WELCOME','SIGNUP_BONUS'} or k.endswith('_REWARD'))
                body=f'Q Economy only | {day} ({tz})\nReceived: {units(credits)} Q\nOf which identified rewards: {units(rewards)} Q\nSpent / sent: {units(debits)} Q\nNet activity: {units(credits-debits)} Q\nCurrent balance: {units(w.balance_micros)} Q\nCredits can include transfers, purchases and refunds; not all are earnings.'
                body+='\n\nReceived by ledger category:\n'+'\n'.join(f'{k.replace("_"," ")}: +{units(v)} Q' for k,v in sorted(received,key=lambda x:-x[1])[:8])
                body+='\n\nSpent / sent by ledger category:\n'+'\n'.join(f'{k.replace("_"," ")}: -{units(v)} Q' for k,v in sorted(spent,key=lambda x:-x[1])[:8])
                row=emit(db,uid,'economy:'+day,'ECONOMY','Your Q Economy today',body)
                if row:row.body=body  # same card, no repeated unread alert
    if not include_discovery:return
    if p['creators'] and not get_event(db,uid,'creators:'+day):
        rows=db.execute(select(CreatorProfile,CreatorIdentity).join(CreatorIdentity,CreatorIdentity.owner_id==CreatorProfile.user_id).where(CreatorProfile.status=='APPROVED',CreatorProfile.level=='MAINSTREAM',CreatorProfile.adult_requested.is_(False),CreatorProfile.created_at>=t-timedelta(hours=24),CreatorProfile.user_id!=uid).order_by(CreatorProfile.created_at.desc()).limit(5)).all()
        if rows:emit(db,uid,'creators:'+day,'CREATORS','New public creators','\n'.join(f'{i.stage_name} (@{i.handle}) | {c.category}' for c,i in rows))
    if p['markets'] and not get_event(db,uid,'markets:'+day):
        # No calls to stake, no prices or odds, no personal targeting; demo cricket discovery only.
        rows=db.scalars(select(PredictMarket).where(PredictMarket.status=='LIVE',PredictMarket.created_at>=t-timedelta(hours=24),PredictMarket.close_at>t,PredictMarket.template_code.startswith('CRICKET_V21314_')).order_by(PredictMarket.created_at.desc()).limit(5)).all()
        if rows:emit(db,uid,'markets:'+day,'PREDICT','New demo prediction markets','\n'.join(x.question for x in rows))

def item(r):
    parts=r.event_key.split(':')
    link={"market_id":int(parts[2]),"wallet_mode":"DEMO" if parts[1] in ("Demo Q","Demo USDT") else "REAL_Q"} if len(parts)==4 and parts[0]=="predict" and parts[1] in ("Demo Q","Demo USDT","Q Predict Q") and parts[2].isdigit() else {}
    return dict(**link,id=f'action310-{r.id}',action_id=r.id,kind='ACTION310',category=r.category,title=r.title,body=r.body,status=r.status,created_at=aware(r.created_at).isoformat(),unread=r.read_at is None,chat_id=r.chat_id,draft=r.draft if r.status=='PENDING' else '',reason=r.reason,acknowledged=bool(r.ack_id),mine=False,can_respond=False,can_cancel=False,options=[])
def items310(db,uid):
    # Existing Q thread stays usable if an optional module query fails.
    try:
        with db.begin_nested():sync_activity(db,uid);reconcile_reviews(db,uid)
        db.commit()
    except Exception:log.exception('Q activity sync failed')
    rows=db.scalars(select(Action310).where(Action310.user_id==uid).order_by(Action310.created_at.desc()).limit(100)).all()
    pending=db.scalars(select(Action310).where(Action310.user_id==uid,Action310.status=='PENDING').order_by(Action310.created_at.desc()).limit(100)).all()
    return [item(r) for r in {r.id:r for r in pending+rows}.values()]
def mark310(db,uid):db.execute(update(Action310).where(Action310.user_id==uid,Action310.read_at.is_(None)).values(read_at=now()))

def register_action310(app,current_user,get_db,push,msg_json):
    router=APIRouter(prefix='/v310/q/actions')
    @router.get('/preferences')
    def get_preferences(u=Depends(current_user),db=Depends(get_db)):return prefs(db,u.id)
    @router.put('/preferences')
    def save_preferences(body:PrefsIn,u=Depends(current_user),db=Depends(get_db)):
        row=db.get(ActionPrefs310,u.id)
        if row is None:row=ActionPrefs310(user_id=u.id);db.add(row)
        for k,v in body.model_dump().items():setattr(row,k,v)
        db.commit();return prefs(db,u.id)
    @router.post('/{aid}/decision')
    async def decision(aid:int,body:DecisionIn,u=Depends(current_user),db=Depends(get_db)):
        r=db.scalar(select(Action310).where(Action310.id==aid,Action310.user_id==u.id))
        if not r or r.category!='BUSINESS':raise HTTPException(404,'Review not found')
        c=db.scalar(select(Chat).where(Chat.id==r.chat_id).with_for_update())
        if not c or u.id not in (c.user1_id,c.user2_id):raise HTTPException(404,'Conversation unavailable')
        db.refresh(r)
        reconcile_reviews(db,u.id)
        db.refresh(r)
        if r.status!='PENDING':db.commit();raise HTTPException(409,'Review already resolved or superseded')
        if body.action=='DISMISS':r.status='DISMISSED';db.commit();return item(r)
        if body.action!='SEND' or not body.text.strip():raise HTTPException(422,'Reviewed reply required')
        other=c.user2_id if c.user1_id==u.id else c.user1_id
        if db.get(UserBlock,{'blocker_id':u.id,'blocked_id':other}) or db.get(UserBlock,{'blocker_id':other,'blocked_id':u.id}):raise HTTPException(403,'Conversation blocked')
        latest=db.scalar(select(Message.id).where(Message.chat_id==c.id,Message.sender_id==other).order_by(Message.id.desc()).limit(1))
        if latest!=r.trigger_id:r.status='SUPERSEDED';db.commit();raise HTTPException(409,'New customer message; open conversation')
        setting=db.get(BusinessChatSetting,{'user_id':u.id,'chat_id':c.id});profile=db.get(BusinessProfile,u.id)
        if not setting or not setting.enabled or setting.mode=='OFF' or not profile or not profile.enabled:raise HTTPException(409,'Business Agent disabled; open conversation to reply manually')
        if db.get(AutoReplyReceipt,r.trigger_id):r.status='RESOLVED';db.commit();raise HTTPException(409,'Already answered')
        m=Message(chat_id=c.id,sender_id=u.id,text=body.text.strip(),ai_generated=False);c.updated_at=now();db.add(m);db.flush()
        db.add(AutoReplyReceipt(trigger_message_id=r.trigger_id,responder_user_id=u.id,reply_message_id=m.id));r.reply_id=m.id;r.status='SENT';db.commit();db.refresh(m)
        data=msg_json(m,db);await push(u.id,{'type':'message','data':data});await push(other,{'type':'message','data':data});return item(r)
    app.include_router(router)
