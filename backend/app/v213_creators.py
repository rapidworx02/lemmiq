"""LEMMIQ V2.13 Q Creators — mainstream beta.

Feature boundaries: public professional profiles, follows, moderated mainstream posts,
manual Q subscriptions, paid media, tips, paid requests, escrowed settlements,
creator earnings and platform fees. Explicit content, cash-out and automated live-call
billing are intentionally NOT enabled by this module.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func, select, update
from sqlalchemy.orm import Mapped, Session, mapped_column

from .database import Base
from .models import User
from . import media_store
from .v28 import QAdminRole, QUserWallet, QSystemWallet, Q_MICROS, _ensure_user_wallet, _ledger, _audit


def now():
    return datetime.now(timezone.utc)


def q(amount):
    return round(int(amount or 0) / Q_MICROS, 6)


def to_micros(value, *, allow_zero=False, max_q=100000):
    try:
        d = Decimal(str(value))
        if not d.is_finite() or d != d.quantize(Decimal('0.000001')):
            raise ValueError()
        n = int(d * Q_MICROS)
    except (ValueError, InvalidOperation, OverflowError, TypeError):
        raise HTTPException(422, 'Enter a valid Q amount with up to 6 decimal places')
    if n < 0 or (n == 0 and not allow_zero) or n > max_q * Q_MICROS:
        raise HTTPException(422, f'Q amount must be between {0 if allow_zero else 0.000001} and {max_q}')
    return n


class CreatorConfig(Base):
    __tablename__ = 'v213_creator_config'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    fee_bps: Mapped[int] = mapped_column(Integer, default=2000)
    payments_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class CreatorProfile(Base):
    __tablename__ = 'v213_creator_profiles'
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), primary_key=True)
    bio: Mapped[str] = mapped_column(String(900), default='')
    category: Mapped[str] = mapped_column(String(24), default='LIFESTYLE', index=True)
    level: Mapped[str] = mapped_column(String(16), default='MAINSTREAM')
    adult_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(16), default='PENDING', index=True)
    monthly_micros: Mapped[int] = mapped_column(BigInteger, default=0)
    chat_micros: Mapped[int] = mapped_column(BigInteger, default=0)
    voice_micros: Mapped[int] = mapped_column(BigInteger, default=0)
    video_micros: Mapped[int] = mapped_column(BigInteger, default=0)
    tips_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class CreatorFollow(Base):
    __tablename__ = 'v213_creator_follows'
    __table_args__ = (UniqueConstraint('fan_id','creator_id',name='uq_v213_follow'),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    fan_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    creator_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class CreatorPost(Base):
    __tablename__ = 'v213_creator_posts'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    creator_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    title: Mapped[str] = mapped_column(String(140))
    teaser: Mapped[str] = mapped_column(String(240), default='')
    body: Mapped[str] = mapped_column(Text, default='')
    visibility: Mapped[str] = mapped_column(String(20), default='PUBLIC')
    price_micros: Mapped[int] = mapped_column(BigInteger, default=0)
    level: Mapped[str] = mapped_column(String(16), default='MAINSTREAM')
    kind: Mapped[str] = mapped_column(String(16), default='TEXT')
    mime_type: Mapped[str] = mapped_column(String(80), default='')
    object_key: Mapped[str] = mapped_column(String(240), default='')
    review: Mapped[str] = mapped_column(String(16), default='PENDING', index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)


class CreatorSubscription(Base):
    __tablename__ = 'v213_creator_subscriptions'
    __table_args__ = (UniqueConstraint('fan_id','creator_id',name='uq_v213_subscription'),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    fan_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    creator_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_price_micros: Mapped[int] = mapped_column(BigInteger, default=0)
    last_payment_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class CreatorUnlock(Base):
    __tablename__ = 'v213_creator_unlocks'
    __table_args__ = (UniqueConstraint('fan_id','post_id',name='uq_v213_unlock'),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    fan_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    post_id: Mapped[int] = mapped_column(ForeignKey('v213_creator_posts.id'), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class CreatorEarnings(Base):
    __tablename__ = 'v213_creator_earnings'
    creator_id: Mapped[int] = mapped_column(ForeignKey('users.id'), primary_key=True)
    available_micros: Mapped[int] = mapped_column(BigInteger, default=0)
    lifetime_micros: Mapped[int] = mapped_column(BigInteger, default=0)
    transferred_micros: Mapped[int] = mapped_column(BigInteger, default=0)


class CreatorPayment(Base):
    __tablename__ = 'v213_creator_payments'
    __table_args__ = (UniqueConstraint('fan_id','request_key',name='uq_v213_pay_request'),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    fan_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    creator_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    request_key: Mapped[str] = mapped_column(String(80))
    kind: Mapped[str] = mapped_column(String(24), index=True)
    resource_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gross_micros: Mapped[int] = mapped_column(BigInteger)
    fee_micros: Mapped[int] = mapped_column(BigInteger)
    net_micros: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(16), default='CAPTURED', index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)


class CreatorRequest(Base):
    __tablename__ = 'v213_creator_requests'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    payment_id: Mapped[int] = mapped_column(ForeignKey('v213_creator_payments.id'), unique=True)
    fan_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    creator_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    kind: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(20), default='REQUESTED')
    message: Mapped[str] = mapped_column(String(900), default='')
    creator_reply: Mapped[str] = mapped_column(String(1600), default='')
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ProfileIn(BaseModel):
    bio: str = Field(default='', max_length=900)
    category: str = 'LIFESTYLE'
    level: str = 'MAINSTREAM'
    adult_requested: bool = False
    monthly_q: float = 0
    chat_q: float = 0
    voice_q: float = 0
    video_q: float = 0
    tips_enabled: bool = True


class PostIn(BaseModel):
    title: str = Field(min_length=3, max_length=140)
    teaser: str = Field(default='', max_length=240)
    body: str = Field(default='', max_length=12000)
    visibility: str = 'PUBLIC'
    price_q: float = 0
    level: str = 'MAINSTREAM'


class BuyIn(BaseModel):
    request_key: str = Field(min_length=12, max_length=80)


class TipIn(BuyIn):
    amount_q: float


class RequestIn(BuyIn):
    kind: str
    message: str = Field(default='', max_length=900)
    scheduled_at: Optional[datetime] = None


class RequestActionIn(BaseModel):
    action: str
    reply: str = Field(default='', max_length=1600)


class TransferIn(BaseModel):
    amount_q: float


class ConfigIn(BaseModel):
    fee_percent: float = Field(ge=0, le=40)
    payments_enabled: bool = False


class ReviewIn(BaseModel):
    action: str
    reason: str = Field(min_length=8, max_length=300)


CATEGORIES={'FASHION','LIFESTYLE','FITNESS','MUSIC','ART','EDUCATION','GAMING','GLAMOUR','OTHER'}
VISIBILITY={'PUBLIC','FOLLOWERS','SUBSCRIBERS','PPV'}


def settings(db):
    row=db.get(CreatorConfig, 1)
    if not row:
        row=CreatorConfig(id=1, fee_bps=2000, payments_enabled=False)
        db.add(row);db.flush()
    return row


def system(db,key):
    row=db.get(QSystemWallet,key)
    if not row:
        row=QSystemWallet(key=key,label=key.replace('_',' ').title(),balance_micros=0)
        db.add(row);db.flush()
    return row


def earnings(db,uid):
    row=db.get(CreatorEarnings,uid)
    if not row:
        row=CreatorEarnings(creator_id=uid,available_micros=0,lifetime_micros=0,transferred_micros=0)
        db.add(row);db.flush()
    return row


def admin_only(db,u):
    r=db.get(QAdminRole,u.id)
    if not r or not r.active or r.role!='MASTER_ADMIN':
        raise HTTPException(403,'Master Admin required')


def creator_ready(db,uid):
    p=db.get(CreatorProfile,uid)
    if not p or p.status!='APPROVED':
        raise HTTPException(403,'Creator profile must be approved before publishing or charging')
    return p


def charge_ready(db):
    if not settings(db).payments_enabled:
        raise HTTPException(409,'Creator Q payments are disabled until the Master Admin enables them')


def profile_json(db,p,viewer=None):
    # V2134_PROFESSIONAL_PRIVACY: professional-only public name/avatar
    from .v2134_professional import professional_public_for
    safe=professional_public_for(db,p.user_id)
    subs=db.scalar(select(func.count()).select_from(CreatorSubscription).where(CreatorSubscription.creator_id==p.user_id,CreatorSubscription.expires_at>now())) or 0
    followers=db.scalar(select(func.count()).select_from(CreatorFollow).where(CreatorFollow.creator_id==p.user_id)) or 0
    own=bool(viewer and viewer==p.user_id)
    following=bool(viewer and db.scalar(select(CreatorFollow.id).where(CreatorFollow.creator_id==p.user_id,CreatorFollow.fan_id==viewer)))
    subscribed=bool(viewer and db.scalar(select(CreatorSubscription.id).where(CreatorSubscription.creator_id==p.user_id,CreatorSubscription.fan_id==viewer,CreatorSubscription.expires_at>now())))
    return {'id':p.user_id,'username':safe['username'],'display_name':safe['display_name'],'avatar_url':safe['avatar_url'],'public_id':safe['public_id'],'bio':p.bio,'category':p.category,'level':p.level,'adult_requested':p.adult_requested if own else False,'status':p.status,'monthly_q':q(p.monthly_micros),'chat_q':q(p.chat_micros),'voice_q':q(p.voice_micros),'video_q':q(p.video_micros),'tips_enabled':p.tips_enabled,'followers':followers,'subscribers':subs,'following':following,'subscribed':subscribed,'mine':own}


def can_read(db,post,uid):
    if uid==post.creator_id:return True
    if post.review!='APPROVED' or db.get(CreatorProfile,post.creator_id).status!='APPROVED':return False
    if post.visibility=='PUBLIC':return True
    if post.visibility=='FOLLOWERS':
        return bool(db.scalar(select(CreatorFollow.id).where(CreatorFollow.fan_id==uid,CreatorFollow.creator_id==post.creator_id)))
    if post.visibility=='SUBSCRIBERS':
        return bool(db.scalar(select(CreatorSubscription.id).where(CreatorSubscription.fan_id==uid,CreatorSubscription.creator_id==post.creator_id,CreatorSubscription.expires_at>now())))
    if post.visibility=='PPV':
        return bool(db.scalar(select(CreatorUnlock.id).where(CreatorUnlock.fan_id==uid,CreatorUnlock.post_id==post.id)))
    return False


def post_json(db,post,uid):
    access=can_read(db,post,uid)
    return {'id':post.id,'creator_id':post.creator_id,'title':post.title,'teaser':post.teaser,'body':post.body if access else None,'visibility':post.visibility,'price_q':q(post.price_micros),'kind':post.kind,'level':post.level,'review':post.review if uid==post.creator_id else 'APPROVED','unlocked':access,'media_url':f'/v213/creators/posts/{post.id}/media' if post.object_key and access else None,'created_at':post.created_at.isoformat()}


def debit_user(db,uid,system_key,amount,kind,ref):
    if amount<=0:return
    _ensure_user_wallet(db,uid)
    system(db,system_key)
    r=db.execute(update(QUserWallet).where(QUserWallet.user_id==uid,QUserWallet.balance_micros>=amount).values(balance_micros=QUserWallet.balance_micros-amount,updated_at=now()))
    if r.rowcount!=1:raise HTTPException(409,'Insufficient Q balance')
    db.execute(update(QSystemWallet).where(QSystemWallet.key==system_key).values(balance_micros=QSystemWallet.balance_micros+amount,updated_at=now()))
    _ledger(db,kind,amount,from_user=uid,to_system=system_key,reference=ref)


def from_system(db,key,uid,amount,kind,ref):
    if amount<=0:return
    system(db,key)
    _ensure_user_wallet(db,uid)
    r=db.execute(update(QSystemWallet).where(QSystemWallet.key==key,QSystemWallet.balance_micros>=amount).values(balance_micros=QSystemWallet.balance_micros-amount,updated_at=now()))
    if r.rowcount!=1:raise HTTPException(409,f'Insufficient {key} balance')
    db.execute(update(QUserWallet).where(QUserWallet.user_id==uid).values(balance_micros=QUserWallet.balance_micros+amount,updated_at=now()))
    _ledger(db,kind,amount,from_system=key,to_user=uid,reference=ref)


def shift(db,from_key,to_key,amount,kind,ref):
    if amount<=0:return
    system(db,from_key);system(db,to_key)
    r=db.execute(update(QSystemWallet).where(QSystemWallet.key==from_key,QSystemWallet.balance_micros>=amount).values(balance_micros=QSystemWallet.balance_micros-amount,updated_at=now()))
    if r.rowcount!=1:raise HTTPException(409,'Creator reserve insufficient')
    db.execute(update(QSystemWallet).where(QSystemWallet.key==to_key).values(balance_micros=QSystemWallet.balance_micros+amount,updated_at=now()))
    _ledger(db,kind,amount,from_system=from_key,to_system=to_key,reference=ref)


def create_payment(db,fan,creator,kind,resource,gross,key,hold=False):
    prev=db.scalar(select(CreatorPayment).where(CreatorPayment.fan_id==fan,CreatorPayment.request_key==key))
    if prev:
        if (prev.creator_id,prev.kind,prev.resource_id)!=(creator,kind,resource):
            raise HTTPException(409,'Payment request key was already used for another item')
        return prev,False
    if fan==creator:raise HTTPException(422,'Cannot purchase your own creator service')
    charge_ready(db)
    if gross<=0:raise HTTPException(422,'This item is free')
    fee=(gross*settings(db).fee_bps+5000)//10000
    net=gross-fee
    row=CreatorPayment(fan_id=fan,creator_id=creator,request_key=key,kind=kind,resource_id=resource,gross_micros=gross,fee_micros=fee,net_micros=net,status='HELD' if hold else 'CAPTURED')
    db.add(row);db.flush()
    ref=f'creator:{row.id}'
    if hold:
        debit_user(db,fan,'CREATOR_HOLDS',gross,'CREATOR_HOLD',ref)
    else:
        debit_user(db,fan,'CREATOR_ESCROW',net,'CREATOR_PURCHASE',ref)
        debit_user(db,fan,'CREATOR_FEES',fee,'CREATOR_COMMISSION',ref)
        credit_earnings(db,creator,net)
    return row,True


def credit_earnings(db,creator,net):
    earnings(db,creator)
    db.execute(update(CreatorEarnings).where(CreatorEarnings.creator_id==creator).values(available_micros=CreatorEarnings.available_micros+net,lifetime_micros=CreatorEarnings.lifetime_micros+net))


def settle_held(db,payment):
    if payment.status!='HELD':raise HTTPException(409,'Payment is not pending settlement')
    ref=f'creator:{payment.id}'
    shift(db,'CREATOR_HOLDS','CREATOR_ESCROW',payment.net_micros,'CREATOR_SETTLE',ref)
    shift(db,'CREATOR_HOLDS','CREATOR_FEES',payment.fee_micros,'CREATOR_COMMISSION',ref)
    credit_earnings(db,payment.creator_id,payment.net_micros)
    payment.status='CAPTURED'


def refund(db,payment):
    if payment.status=='REFUNDED':return
    if payment.status=='HELD':
        from_system(db,'CREATOR_HOLDS',payment.fan_id,payment.gross_micros,'CREATOR_REFUND',f'creator:{payment.id}')
    elif payment.status=='CAPTURED':
        # Don't silently claw funds back from an unrelated user wallet; refund
        # requires still-untransferred creator earnings and platform fees.
        row=earnings(db,payment.creator_id)
        r=db.execute(update(CreatorEarnings).where(CreatorEarnings.creator_id==payment.creator_id,CreatorEarnings.available_micros>=payment.net_micros).values(available_micros=CreatorEarnings.available_micros-payment.net_micros,lifetime_micros=CreatorEarnings.lifetime_micros-payment.net_micros))
        if r.rowcount!=1:raise HTTPException(409,'Creator funds already transferred; manual review required')
        from_system(db,'CREATOR_ESCROW',payment.fan_id,payment.net_micros,'CREATOR_REFUND',f'creator:{payment.id}')
        from_system(db,'CREATOR_FEES',payment.fan_id,payment.fee_micros,'CREATOR_FEE_REFUND',f'creator:{payment.id}')
    else:raise HTTPException(409,'Cannot refund payment in this status')
    payment.status='REFUNDED'


def request_json(db,r,uid):
    p=db.get(CreatorPayment,r.payment_id)
    person=db.get(User,r.fan_id) if uid==r.creator_id else None
    from .v2134_professional import professional_public_for
    shown=professional_public_for(db,r.creator_id) if uid!=r.creator_id else None
    return {'id':r.id,'kind':r.kind,'status':r.status,'message':r.message,'reply':r.creator_reply,'name':shown['display_name'] if shown else person.display_name,'username':shown['username'] if shown else person.username,'amount_q':q(p.gross_micros),'created_at':r.created_at.isoformat(),'scheduled_at':r.scheduled_at.isoformat() if r.scheduled_at else None}


def register_v213_creators(app,current_user,get_db):
    router=APIRouter(prefix='/v213/creators',tags=['Q Creators'])

    @app.on_event('startup')
    def v213_startup():
        from .database import engine,SessionLocal
        Base.metadata.create_all(bind=engine)
        with SessionLocal() as db:
            settings(db)
            for key in ('CREATOR_HOLDS','CREATOR_ESCROW','CREATOR_FEES'):system(db,key)
            db.commit()

    @router.get('/config')
    def config(u:User=Depends(current_user),db:Session=Depends(get_db)):
        c=settings(db);db.commit()
        return {'fee_percent':c.fee_bps/100,'payments_enabled':c.payments_enabled,'adult_content_enabled':False,'cashout_enabled':False,'manual_renewal_only':True}

    @router.get('/discover')
    def discover(qtext:str='',category:str='',following:bool=False,limit:int=50,offset:int=0,u:User=Depends(current_user),db:Session=Depends(get_db)):
        from .v2134_professional import CreatorIdentity
        qry=select(CreatorProfile).join(CreatorIdentity,CreatorIdentity.owner_id==CreatorProfile.user_id).where(CreatorProfile.status=='APPROVED',CreatorProfile.level.in_(['MAINSTREAM','GLAMOUR']))
        if category.upper() in CATEGORIES:qry=qry.where(CreatorProfile.category==category.upper())
        if qtext.strip():qry=qry.where((func.lower(CreatorIdentity.handle).contains(qtext.strip().lower()))|(func.lower(CreatorIdentity.stage_name).contains(qtext.strip().lower())))
        if following:qry=qry.join(CreatorFollow,(CreatorFollow.creator_id==CreatorProfile.user_id)&(CreatorFollow.fan_id==u.id))
        rows=db.scalars(qry.order_by(CreatorProfile.updated_at.desc()).offset(min(1000,max(offset,0))).limit(min(100,max(1,limit)))).all()
        return [profile_json(db,x,u.id) for x in rows]

    @router.get('/me')
    def mine(u:User=Depends(current_user),db:Session=Depends(get_db)):
        p=db.get(CreatorProfile,u.id)
        e=earnings(db,u.id);db.commit()
        return {'profile':profile_json(db,p,u.id) if p else None,'earnings':{'available_q':q(e.available_micros),'lifetime_q':q(e.lifetime_micros),'transferred_q':q(e.transferred_micros)}}

    @router.put('/me')
    def upsert(body:ProfileIn,u:User=Depends(current_user),db:Session=Depends(get_db)):
        if body.category.upper() not in CATEGORIES:raise HTTPException(422,'Unsupported creator category')
        if body.level.upper() not in ('MAINSTREAM','GLAMOUR'):raise HTTPException(422,'Explicit content cannot be published in the LEMMIQ app. Request 18+ review separately.')
        prices=[to_micros(x,allow_zero=True,max_q=100000) for x in (body.monthly_q,body.chat_q,body.voice_q,body.video_q)]
        p=db.get(CreatorProfile,u.id)
        if not p:
            p=CreatorProfile(user_id=u.id,status='PENDING')
            db.add(p)
        if p.status=='SUSPENDED':raise HTTPException(403,'Creator account suspended; contact support')
        if p.status=='REJECTED':p.status='PENDING'  # resubmission requires new admin approval
        p.bio=body.bio.strip();p.category=body.category.upper();p.level=body.level.upper()
        p.adult_requested=body.adult_requested;p.monthly_micros,p.chat_micros,p.voice_micros,p.video_micros=prices
        p.tips_enabled=body.tips_enabled;p.updated_at=now()
        db.commit();return profile_json(db,p,u.id)

    @router.get('/profile/{creator_id}')
    def profile(creator_id:int,u:User=Depends(current_user),db:Session=Depends(get_db)):
        p=db.get(CreatorProfile,creator_id)
        if not p or (p.status!='APPROVED' and creator_id!=u.id):raise HTTPException(404,'Creator not found')
        if p.level not in ('MAINSTREAM','GLAMOUR'):raise HTTPException(404,'Profile unavailable')
        posts=db.scalars(select(CreatorPost).where(CreatorPost.creator_id==creator_id).order_by(CreatorPost.id.desc()).limit(100)).all()
        if creator_id!=u.id:posts=[x for x in posts if x.review=='APPROVED']
        return {'profile':profile_json(db,p,u.id),'posts':[post_json(db,x,u.id) for x in posts]}

    @router.post('/profile/{creator_id}/follow')
    def follow(creator_id:int,u:User=Depends(current_user),db:Session=Depends(get_db)):
        creator_ready(db,creator_id)
        if creator_id==u.id:raise HTTPException(422,'Cannot follow yourself')
        if not db.scalar(select(CreatorFollow.id).where(CreatorFollow.creator_id==creator_id,CreatorFollow.fan_id==u.id)):
            db.add(CreatorFollow(creator_id=creator_id,fan_id=u.id));db.commit()
        return {'following':True}

    @router.delete('/profile/{creator_id}/follow')
    def unfollow(creator_id:int,u:User=Depends(current_user),db:Session=Depends(get_db)):
        row=db.scalar(select(CreatorFollow).where(CreatorFollow.creator_id==creator_id,CreatorFollow.fan_id==u.id))
        if row:db.delete(row);db.commit()
        return {'following':False}

    @router.post('/posts')
    def create_post(body:PostIn,u:User=Depends(current_user),db:Session=Depends(get_db)):
        p=creator_ready(db,u.id)
        level=body.level.upper();visibility=body.visibility.upper()
        if level not in ('MAINSTREAM','GLAMOUR') or visibility not in VISIBILITY:raise HTTPException(422,'Unsupported content rating or visibility')
        price=to_micros(body.price_q,allow_zero=True)
        if visibility=='PPV' and price==0:raise HTTPException(422,'Paid media must have a price')
        if visibility!='PPV' and price:raise HTTPException(422,'Only pay-per-view posts can specify a price')
        if not body.body.strip():raise HTTPException(422,'Enter content before submitting')
        post=CreatorPost(creator_id=u.id,title=body.title.strip(),teaser=body.teaser.strip(),body=body.body.strip(),visibility=visibility,price_micros=price,level=level,review='PENDING')
        db.add(post);db.commit();db.refresh(post)
        return post_json(db,post,u.id)

    @router.post('/posts/{post_id}/media')
    async def upload_media(post_id:int,file:UploadFile=File(...),u:User=Depends(current_user),db:Session=Depends(get_db)):
        post=db.get(CreatorPost,post_id)
        if not post or post.creator_id!=u.id:raise HTTPException(404,'Post not found')
        if post.review=='APPROVED':raise HTTPException(409,'Approved posts cannot replace their media; create a new post')
        mime=(file.content_type or '').lower().split(';')[0]
        allowed={'image/jpeg':('PHOTO',20*1024*1024),'image/png':('PHOTO',20*1024*1024),'image/webp':('PHOTO',20*1024*1024),'video/mp4':('VIDEO',100*1024*1024),'video/webm':('VIDEO',100*1024*1024)}
        if mime not in allowed:raise HTTPException(415,'Only JPEG, PNG, WebP, MP4 and WebM are supported')
        kind,max_size=allowed[mime];data=await file.read(max_size+1)
        if len(data)<12 or len(data)>max_size:raise HTTPException(413,'Invalid media size')
        signatures={'image/jpeg':lambda b:b.startswith(b'\xff\xd8\xff'),'image/png':lambda b:b.startswith(b'\x89PNG\r\n\x1a\n'),'image/webp':lambda b:b[:4]==b'RIFF' and b[8:12]==b'WEBP','video/mp4':lambda b:b[4:8]==b'ftyp','video/webm':lambda b:b.startswith(b'\x1a\x45\xdf\xa3')}
        if not signatures[mime](data):raise HTTPException(415,'Media content does not match its declared format')
        post.object_key=media_store.store(data)
        post.mime_type=mime;post.kind=kind;post.review='PENDING';db.commit()
        return {'id':post.id,'kind':kind,'review':'PENDING','message':'Media submitted for moderation'}

    @router.get('/posts/{post_id}/media')
    def media(post_id:int,u:User=Depends(current_user),db:Session=Depends(get_db)):
        post=db.get(CreatorPost,post_id)
        if not post or not post.object_key:raise HTTPException(404,'Media not found')
        # Admin access must use /v2131/exclusives/admin/posts/<id>/media,
        # which enforces Master Admin and writes a per-access audit entry.
        if not can_read(db,post,u.id):
            raise HTTPException(403,'Unlock this content to view the media')
        return StreamingResponse(media_store.stream(post.object_key),media_type=post.mime_type,headers={'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff','Content-Security-Policy':"default-src 'none'; sandbox"})

    @router.post('/profile/{creator_id}/subscribe')
    def subscribe(creator_id:int,body:BuyIn,u:User=Depends(current_user),db:Session=Depends(get_db)):
        p=creator_ready(db,creator_id)
        if p.level not in ('MAINSTREAM','GLAMOUR'):raise HTTPException(403,'Not available in this app')
        sub=db.scalar(select(CreatorSubscription).where(CreatorSubscription.fan_id==u.id,CreatorSubscription.creator_id==creator_id))
        # Explicit expiry check with timezone-normalised value.
        expiry=sub.expires_at if sub else None
        previous=db.scalar(select(CreatorPayment).where(CreatorPayment.fan_id==u.id,CreatorPayment.request_key==body.request_key))
        if previous and (previous.kind,previous.creator_id)==('SUB',creator_id):
            return {'subscribed':bool(expiry and (expiry if expiry.tzinfo else expiry.replace(tzinfo=timezone.utc))>now()),'charged_q':0,'expires_at':expiry.isoformat() if expiry else None,'replayed':True}
        if expiry and (expiry if expiry.tzinfo else expiry.replace(tzinfo=timezone.utc))>now():
            raise HTTPException(409,'Already subscribed; manual renewal is available after expiration')
        row,created=(None,False)
        if p.monthly_micros:
            row,created=create_payment(db,u.id,creator_id,'SUB',creator_id,p.monthly_micros,body.request_key)
        else:
            created=True
        if created:
            expires=now()+timedelta(days=30)
            if not sub:db.add(CreatorSubscription(fan_id=u.id,creator_id=creator_id,expires_at=expires,last_price_micros=p.monthly_micros))
            else:sub.expires_at=expires;sub.last_price_micros=p.monthly_micros;sub.last_payment_id=row.id if row else None;sub.updated_at=now()
            db.commit()
        return {'subscribed':True,'charged_q':q(p.monthly_micros) if created else 0,'expires_at':sub.expires_at.isoformat() if sub else expires.isoformat()}

    @router.post('/posts/{post_id}/unlock')
    def unlock(post_id:int,body:BuyIn,u:User=Depends(current_user),db:Session=Depends(get_db)):
        post=db.get(CreatorPost,post_id)
        if not post or post.review!='APPROVED' or post.visibility!='PPV':raise HTTPException(404,'Paid post unavailable')
        creator_ready(db,post.creator_id)
        if can_read(db,post,u.id):return {'unlocked':True,'charged_q':0}
        row,created=create_payment(db,u.id,post.creator_id,'UNLOCK',post.id,post.price_micros,body.request_key)
        if created:db.add(CreatorUnlock(fan_id=u.id,post_id=post.id));db.commit()
        return {'unlocked':True,'charged_q':q(row.gross_micros) if created else 0}

    @router.post('/profile/{creator_id}/tip')
    def tip(creator_id:int,body:TipIn,u:User=Depends(current_user),db:Session=Depends(get_db)):
        p=creator_ready(db,creator_id)
        if not p.tips_enabled:raise HTTPException(409,'Creator tips unavailable')
        gross=to_micros(body.amount_q)
        row,created=create_payment(db,u.id,creator_id,'TIP',None,gross,body.request_key)
        db.commit()
        return {'payment_id':row.id,'charged_q':q(row.gross_micros) if created else 0}

    @router.post('/profile/{creator_id}/request')
    def request(creator_id:int,body:RequestIn,u:User=Depends(current_user),db:Session=Depends(get_db)):
        p=creator_ready(db,creator_id)
        kind=body.kind.upper()
        if kind=='CHAT':raise HTTPException(410,'Use the Professional Creator Inbox paid chat request instead')
        if kind not in ('CHAT','VOICE','VIDEO'):raise HTTPException(422,'Invalid service')
        amount={'CHAT':p.chat_micros,'VOICE':p.voice_micros,'VIDEO':p.video_micros}[kind]
        if not amount:raise HTTPException(409,'Creator has not enabled this paid service')
        if kind=='CHAT' and len(body.message.strip())<3:raise HTTPException(422,'Describe your paid request')
        if kind in ('VOICE','VIDEO'):
            if not body.scheduled_at:raise HTTPException(422,'Choose a session date and time')
            scheduled=body.scheduled_at.replace(tzinfo=timezone.utc) if not body.scheduled_at.tzinfo else body.scheduled_at
            if scheduled<=now()+timedelta(minutes=5) or scheduled>now()+timedelta(days=60):raise HTTPException(422,'Choose a session within the next 60 days')
        row,created=create_payment(db,u.id,creator_id,kind,None,amount,body.request_key,hold=True)
        req=db.scalar(select(CreatorRequest).where(CreatorRequest.payment_id==row.id))
        if created:
            req=CreatorRequest(payment_id=row.id,fan_id=u.id,creator_id=creator_id,kind=kind,status='REQUESTED',message=body.message.strip(),scheduled_at=body.scheduled_at)
            db.add(req);db.commit();db.refresh(req)
        return request_json(db,req,u.id)

    @router.get('/requests')
    def inbox(u:User=Depends(current_user),db:Session=Depends(get_db)):
        rows=db.scalars(select(CreatorRequest).where((CreatorRequest.fan_id==u.id)|(CreatorRequest.creator_id==u.id)).order_by(CreatorRequest.id.desc()).limit(100)).all()
        return [dict(request_json(db,r,u.id),role='CREATOR' if r.creator_id==u.id else 'FAN') for r in rows]

    @router.post('/requests/{request_id}/action')
    def request_action(request_id:int,body:RequestActionIn,u:User=Depends(current_user),db:Session=Depends(get_db)):
        r=db.get(CreatorRequest,request_id)
        if not r or u.id not in (r.fan_id,r.creator_id):raise HTTPException(404,'Request not found')
        action=body.action.upper();p=db.get(CreatorPayment,r.payment_id)
        if r.kind=='CHAT':raise HTTPException(410,'Open Professional Creator Inbox for paid chat actions')
        if action=='ACCEPT' and u.id==r.creator_id and r.status=='REQUESTED':r.status='ACCEPTED'
        elif action=='REPLY' and u.id==r.creator_id and r.kind=='CHAT' and r.status in ('REQUESTED','ACCEPTED'):
            if len(body.reply.strip())<3:raise HTTPException(422,'Enter your reply')
            r.creator_reply=body.reply.strip();r.status='DELIVERED'
        elif action=='DELIVERED' and u.id==r.creator_id and r.kind in ('VOICE','VIDEO') and r.status=='ACCEPTED':r.status='DELIVERED'
        elif action=='CONFIRM' and u.id==r.fan_id and r.status=='DELIVERED':
            settle_held(db,p);r.status='COMPLETED'
        elif action=='CANCEL' and ((u.id==r.fan_id and r.status=='REQUESTED') or (u.id==r.creator_id and r.status in ('REQUESTED','ACCEPTED'))):
            refund(db,p);r.status='CANCELLED'
        else:raise HTTPException(409,'Action not permitted for this request/status')
        r.updated_at=now();db.commit();return request_json(db,r,u.id)

    @router.get('/earnings')
    def creator_earnings(u:User=Depends(current_user),db:Session=Depends(get_db)):
        p=db.get(CreatorProfile,u.id)
        if not p:raise HTTPException(404,'Professional profile not found')
        w=earnings(db,u.id)
        rows=db.scalars(select(CreatorPayment).where(CreatorPayment.creator_id==u.id).order_by(CreatorPayment.id.desc()).limit(100)).all()
        db.commit()
        return {'available_q':q(w.available_micros),'lifetime_q':q(w.lifetime_micros),'transferred_q':q(w.transferred_micros),'transactions':[{'id':r.id,'kind':r.kind,'gross_q':q(r.gross_micros),'fee_q':q(r.fee_micros),'net_q':q(r.net_micros),'status':r.status,'created_at':r.created_at.isoformat()} for r in rows]}

    @router.post('/earnings/transfer')
    def transfer(body:TransferIn,u:User=Depends(current_user),db:Session=Depends(get_db)):
        creator_ready(db,u.id)
        amount=to_micros(body.amount_q)
        earnings(db,u.id)
        r=db.execute(update(CreatorEarnings).where(CreatorEarnings.creator_id==u.id,CreatorEarnings.available_micros>=amount).values(available_micros=CreatorEarnings.available_micros-amount,transferred_micros=CreatorEarnings.transferred_micros+amount))
        if r.rowcount!=1:raise HTTPException(409,'Insufficient available creator earnings')
        from_system(db,'CREATOR_ESCROW',u.id,amount,'CREATOR_EARNINGS_TRANSFER',f'creator:{u.id}')
        db.commit();return {'transferred_q':q(amount)}

    @router.get('/admin/overview')
    def admin_overview(u:User=Depends(current_user),db:Session=Depends(get_db)):
        admin_only(db,u)
        cfg=settings(db)
        profiles=db.scalars(select(CreatorProfile).order_by(CreatorProfile.created_at.desc()).limit(200)).all()
        posts=db.scalars(select(CreatorPost).where(CreatorPost.review=='PENDING').order_by(CreatorPost.id.desc()).limit(100)).all()
        payments=db.scalars(select(CreatorPayment).order_by(CreatorPayment.id.desc()).limit(100)).all()
        requests=db.scalars(select(CreatorRequest).where(CreatorRequest.status.in_(['REQUESTED','ACCEPTED','DELIVERED'])).order_by(CreatorRequest.id.desc()).limit(100)).all()
        db.commit()
        return {'config':{'fee_percent':cfg.fee_bps/100,'payments_enabled':cfg.payments_enabled},
          'profiles':[dict(profile_json(db,p,u.id),adult_requested=p.adult_requested) for p in profiles],
          'pending_posts':[dict(post_json(db,p,p.creator_id),creator_username=db.get(User,p.creator_id).username) for p in posts],
          'payments':[{'id':x.id,'fan_id':x.fan_id,'creator_id':x.creator_id,'kind':x.kind,'gross_q':q(x.gross_micros),'fee_q':q(x.fee_micros),'net_q':q(x.net_micros),'status':x.status} for x in payments],
          'open_requests':[{'id':r.id,'creator_id':r.creator_id,'fan_id':r.fan_id,'status':r.status,'kind':r.kind} for r in requests],
          'fee_wallet_q':q(system(db,'CREATOR_FEES').balance_micros)}

    @router.put('/admin/config')
    def admin_config(body:ConfigIn,u:User=Depends(current_user),db:Session=Depends(get_db)):
        admin_only(db,u)
        cfg=settings(db);old={'fee_bps':cfg.fee_bps,'payments_enabled':cfg.payments_enabled}
        cfg.fee_bps=int(Decimal(str(body.fee_percent))*100)
        cfg.payments_enabled=body.payments_enabled;cfg.updated_at=now()
        _audit(db,u.id,'CREATOR_CONFIG',before=old,after={'fee_bps':cfg.fee_bps,'payments_enabled':cfg.payments_enabled},reason='Master Admin creator monetisation settings')
        db.commit();return {'ok':True,'fee_percent':cfg.fee_bps/100,'payments_enabled':cfg.payments_enabled}

    @router.post('/admin/profiles/{creator_id}/review')
    def review_creator(creator_id:int,body:ReviewIn,u:User=Depends(current_user),db:Session=Depends(get_db)):
        admin_only(db,u)
        p=db.get(CreatorProfile,creator_id)
        if not p:raise HTTPException(404,'Profile not found')
        if body.action.upper() not in ('APPROVE','REJECT','SUSPEND'):raise HTTPException(422,'Invalid review action')
        before=p.status;p.status={'APPROVE':'APPROVED','REJECT':'REJECTED','SUSPEND':'SUSPENDED'}[body.action.upper()]
        p.updated_at=now();_audit(db,u.id,'CREATOR_PROFILE_REVIEW',target_user_id=creator_id,before={'status':before},after={'status':p.status},reason=body.reason)
        db.commit();return {'ok':True,'status':p.status}

    @router.post('/admin/posts/{post_id}/review')
    def review_post(post_id:int,body:ReviewIn,u:User=Depends(current_user),db:Session=Depends(get_db)):
        admin_only(db,u)
        p=db.get(CreatorPost,post_id)
        if not p:raise HTTPException(404,'Post not found')
        if body.action.upper() not in ('APPROVE','REJECT'):raise HTTPException(422,'Invalid review action')
        creator_ready(db,p.creator_id)
        p.review='APPROVED' if body.action.upper()=='APPROVE' else 'REJECTED'
        _audit(db,u.id,'CREATOR_POST_REVIEW',target_user_id=p.creator_id,before={'review':'PENDING'},after={'post_id':p.id,'review':p.review},reason=body.reason)
        db.commit();return {'ok':True,'review':p.review}

    @router.post('/admin/payments/{payment_id}/refund')
    def admin_refund(payment_id:int,body:ReviewIn,u:User=Depends(current_user),db:Session=Depends(get_db)):
        admin_only(db,u)
        p=db.get(CreatorPayment,payment_id)
        if not p:raise HTTPException(404,'Creator payment not found')
        refund(db,p)
        if p.kind=='UNLOCK' and p.resource_id:
            old=db.scalar(select(CreatorUnlock).where(CreatorUnlock.fan_id==p.fan_id,CreatorUnlock.post_id==p.resource_id))
            if old:db.delete(old)
        # V2.13.1: revoke exclusive/gallery entitlements on refund.
        if p.kind in ('GALLERY','DM_PPV'):
            from .v2131_exclusives import CreatorGalleryUnlock, CreatorOfferUnlock
            if p.kind=='GALLERY':
                access=db.scalar(select(CreatorGalleryUnlock).where(CreatorGalleryUnlock.payment_id==p.id))
            else:
                access=db.scalar(select(CreatorOfferUnlock).where(CreatorOfferUnlock.payment_id==p.id))
            if access:db.delete(access)
        if p.kind=='SUB':
            old=db.scalar(select(CreatorSubscription).where(CreatorSubscription.fan_id==p.fan_id,CreatorSubscription.creator_id==p.creator_id))
            if old and old.last_payment_id==p.id:old.expires_at=now()
        if p.kind in ('CHAT','VOICE','VIDEO'):
            old=db.scalar(select(CreatorRequest).where(CreatorRequest.payment_id==p.id))
            if old:old.status='CANCELLED';old.updated_at=now()
        _audit(db,u.id,'CREATOR_REFUND',target_user_id=p.fan_id,after={'payment_id':p.id,'status':p.status},reason=body.reason)
        db.commit();return {'ok':True,'status':p.status}

    app.include_router(router)
