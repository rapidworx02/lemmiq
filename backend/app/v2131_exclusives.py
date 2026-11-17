# V21354_CREATOR_AUTOPUBLISH
"""LEMMIQ V2.13.1 — moderated Creator Media Library, Exclusive Gallery, Chat PPV.

Mainstream/non-explicit only. Admin auditing is logged and disclosed to creators.
Only authenticated endpoints serve media; object keys never appear in JSON.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint, func, select, update
from sqlalchemy.orm import Mapped, Session, mapped_column

from .database import Base
from .models import User, Chat, Message, UserBlock
from . import media_store
from .v28 import QAdminRole, QUserWallet, _audit
from .v213_creators import (
    CreatorProfile, CreatorPost, CreatorPayment, CreatorSubscription, CreatorConfig, CreatorFollow,
    Q_MICROS, admin_only, can_read, charge_ready, creator_ready,
    create_payment, now, q, to_micros,
)

ALLOWED_MIME={
    'image/jpeg': ('PHOTO',20*1024*1024,lambda b:b.startswith(b'\xff\xd8\xff')),
    'image/png': ('PHOTO',20*1024*1024,lambda b:b.startswith(b'\x89PNG\r\n\x1a\n')),
    'image/webp': ('PHOTO',20*1024*1024,lambda b:b[:4]==b'RIFF' and b[8:12]==b'WEBP'),
    'video/mp4': ('VIDEO',100*1024*1024,lambda b:b[4:8]==b'ftyp'),
    'video/webm': ('VIDEO',100*1024*1024,lambda b:b.startswith(b'\x1a\x45\xdf\xa3')),
}


class CreatorMediaAsset(Base):
    __tablename__='v2131_creator_assets'
    id: Mapped[int]=mapped_column(Integer,primary_key=True)
    creator_id: Mapped[int]=mapped_column(ForeignKey('users.id'),index=True)
    title: Mapped[str]=mapped_column(String(140))
    kind: Mapped[str]=mapped_column(String(16))
    level: Mapped[str]=mapped_column(String(16),default='MAINSTREAM')
    mime_type: Mapped[str]=mapped_column(String(80))
    object_key: Mapped[str]=mapped_column(String(240))
    size_bytes: Mapped[int]=mapped_column(BigInteger)
    review: Mapped[str]=mapped_column(String(16),default='PENDING',index=True)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now,index=True)


class CreatorGalleryItem(Base):
    __tablename__='v2131_creator_gallery'
    id: Mapped[int]=mapped_column(Integer,primary_key=True)
    creator_id: Mapped[int]=mapped_column(ForeignKey('users.id'),index=True)
    title: Mapped[str]=mapped_column(String(140))
    teaser: Mapped[str]=mapped_column(String(240),default='')
    kind: Mapped[str]=mapped_column(String(16))
    visibility: Mapped[str]=mapped_column(String(16),default='PPV')
    price_micros: Mapped[int]=mapped_column(BigInteger,default=0)
    review: Mapped[str]=mapped_column(String(16),default='PENDING',index=True)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now,index=True)


class CreatorGalleryAsset(Base):
    __tablename__='v2131_gallery_assets'
    __table_args__=(UniqueConstraint('item_id','asset_id',name='uq_v2131_gallery_asset'),)
    id: Mapped[int]=mapped_column(Integer,primary_key=True)
    item_id: Mapped[int]=mapped_column(ForeignKey('v2131_creator_gallery.id'),index=True)
    asset_id: Mapped[int]=mapped_column(ForeignKey('v2131_creator_assets.id'),index=True)
    position: Mapped[int]=mapped_column(Integer,default=0)


class CreatorGalleryUnlock(Base):
    __tablename__='v2131_gallery_unlocks'
    __table_args__=(UniqueConstraint('fan_id','item_id',name='uq_v2131_gallery_unlock'),)
    id: Mapped[int]=mapped_column(Integer,primary_key=True)
    fan_id: Mapped[int]=mapped_column(ForeignKey('users.id'),index=True)
    item_id: Mapped[int]=mapped_column(ForeignKey('v2131_creator_gallery.id'),index=True)
    payment_id: Mapped[int]=mapped_column(ForeignKey('v213_creator_payments.id'))
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)


class CreatorPrivateOffer(Base):
    __tablename__='v2131_private_offers'
    __table_args__=(UniqueConstraint('creator_id','client_key',name='uq_v2131_offer_key'),)
    id: Mapped[int]=mapped_column(Integer,primary_key=True)
    creator_id: Mapped[int]=mapped_column(ForeignKey('users.id'),index=True)
    fan_id: Mapped[int]=mapped_column(ForeignKey('users.id'),index=True)
    chat_id: Mapped[int]=mapped_column(ForeignKey('chats.id'),index=True)
    item_id: Mapped[int]=mapped_column(ForeignKey('v2131_creator_gallery.id'),index=True)
    price_micros: Mapped[int]=mapped_column(BigInteger)
    client_key: Mapped[str]=mapped_column(String(80))
    message_id: Mapped[Optional[int]]=mapped_column(ForeignKey('messages.id'),nullable=True)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)


class CreatorOfferUnlock(Base):
    __tablename__='v2131_offer_unlocks'
    __table_args__=(UniqueConstraint('fan_id','offer_id',name='uq_v2131_offer_unlock'),)
    id: Mapped[int]=mapped_column(Integer,primary_key=True)
    fan_id: Mapped[int]=mapped_column(ForeignKey('users.id'),index=True)
    offer_id: Mapped[int]=mapped_column(ForeignKey('v2131_private_offers.id'),index=True)
    payment_id: Mapped[int]=mapped_column(ForeignKey('v213_creator_payments.id'))
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)


class CreatorMediaAudit(Base):
    __tablename__='v2131_creator_media_audits'
    id: Mapped[int]=mapped_column(Integer,primary_key=True)
    admin_id: Mapped[int]=mapped_column(ForeignKey('users.id'),index=True)
    creator_id: Mapped[int]=mapped_column(ForeignKey('users.id'),index=True)
    source_type: Mapped[str]=mapped_column(String(20))
    source_id: Mapped[int]=mapped_column(Integer)
    reason: Mapped[str]=mapped_column(String(100),default='Content safety and policy review')
    accessed_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now,index=True)


class GalleryIn(BaseModel):
    title: str=Field(min_length=3,max_length=140)
    teaser: str=Field(default='',max_length=240)
    kind: str
    visibility: str='PPV'
    price_q: float=0
    asset_ids: list[int]=Field(min_length=1,max_length=20)

class UnlockIn(BaseModel):
    request_key: str=Field(min_length=12,max_length=80)

class SendOfferIn(BaseModel):
    item_id: int
    price_q: float
    client_key: str=Field(min_length=12,max_length=80)

class ReviewIn(BaseModel):
    action: str
    reason: str=Field(min_length=8,max_length=300)


def asset_json(a):
    return {'id':a.id,'title':a.title,'kind':a.kind,'level':a.level,'review':a.review,
            'size_bytes':a.size_bytes,'created_at':a.created_at.isoformat()}


def linked_asset_ids(db,item_id):
    return db.scalars(select(CreatorGalleryAsset.asset_id).where(CreatorGalleryAsset.item_id==item_id)
                      .order_by(CreatorGalleryAsset.position)).all()


def active_subscription(db,fan,creator):
    s=db.scalar(select(CreatorSubscription).where(CreatorSubscription.fan_id==fan,CreatorSubscription.creator_id==creator))
    if not s:return False
    expiry=s.expires_at
    return (expiry if expiry.tzinfo else expiry.replace(tzinfo=timezone.utc))>now()


def gallery_can_read(db,item,uid):
    if item.creator_id==uid:return True
    if item.review!='APPROVED':return False
    prof=db.get(CreatorProfile,item.creator_id)
    if not prof or prof.status!='APPROVED':return False
    if item.visibility=='SUBSCRIBERS' and active_subscription(db,uid,item.creator_id):return True
    if db.scalar(select(CreatorGalleryUnlock.id).where(CreatorGalleryUnlock.fan_id==uid,CreatorGalleryUnlock.item_id==item.id)):
        return True
    # A private PPV purchase also unlocks the same approved gallery item.
    return bool(db.scalar(select(CreatorOfferUnlock.id).join(CreatorPrivateOffer,CreatorPrivateOffer.id==CreatorOfferUnlock.offer_id)
                          .where(CreatorOfferUnlock.fan_id==uid,CreatorPrivateOffer.item_id==item.id)))


def gallery_json(db,item,uid):
    unlocked=gallery_can_read(db,item,uid)
    return {'id':item.id,'creator_id':item.creator_id,'title':item.title,'teaser':item.teaser,
            'kind':item.kind,'visibility':item.visibility,'price_q':q(item.price_micros),
            'review':item.review if item.creator_id==uid else 'APPROVED',
            'unlocked':unlocked,'media_count':len(linked_asset_ids(db,item.id)),
            'created_at':item.created_at.isoformat()}


def offer_json(db,offer,uid):
    item=db.get(CreatorGalleryItem,offer.item_id)
    return {'id':offer.id,'creator_id':offer.creator_id,'fan_id':offer.fan_id,'chat_id':offer.chat_id,
            'item_id':offer.item_id,'title':item.title if item else 'Unavailable',
            'kind':item.kind if item else 'MEDIA','price_q':q(offer.price_micros),
            'unlocked':bool(item and gallery_can_read(db,item,uid)),
            'created_at':offer.created_at.isoformat()}


def stable_lock_wallet(db,uid):
    # PostgreSQL row lock serializes purchases with different request keys.
    # SQLite tests use the usual transactional constraints; production uses PostgreSQL.
    from .v28 import _ensure_user_wallet
    _ensure_user_wallet(db,uid)
    db.execute(select(QUserWallet.user_id).where(QUserWallet.user_id==uid).with_for_update()).all()


def private_stream(key,mime):
    return StreamingResponse(media_store.stream(key),media_type=mime,headers={
        'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff',
        'Content-Security-Policy':"default-src 'none'; sandbox",
        'X-Robots-Tag':'noindex, nofollow, noarchive',
        'Referrer-Policy':'no-referrer',
    })


def register_v2131_exclusives(app,current_user,get_db,push,msg_json):
    router=APIRouter(prefix='/v2131/exclusives',tags=['Q Creators Exclusive Media'])

    @app.on_event('startup')
    def v2131_startup():
        from .database import engine
        Base.metadata.create_all(bind=engine)
        # One-time, idempotent legacy-pending-content activation; never restore REJECTED items.
        from .database import SessionLocal
        with SessionLocal() as session:
            approved=set(session.scalars(select(CreatorProfile.user_id).where(
                CreatorProfile.status=='APPROVED')).all())
            if approved:
                session.execute(update(CreatorMediaAsset).where(
                    CreatorMediaAsset.creator_id.in_(approved),CreatorMediaAsset.review=='PENDING'
                ).values(review='APPROVED'))
                session.execute(update(CreatorPost).where(
                    CreatorPost.creator_id.in_(approved),CreatorPost.review=='PENDING'
                ).values(review='APPROVED'))
                pending=session.scalars(select(CreatorGalleryItem).where(
                    CreatorGalleryItem.creator_id.in_(approved),CreatorGalleryItem.review=='PENDING'
                )).all()
                for item in pending:
                    ids=linked_asset_ids(session,item.id)
                    if ids and all((asset:=session.get(CreatorMediaAsset,aid)) and
                                   asset.review=='APPROVED' for aid in ids):
                        item.review='APPROVED'
                session.commit()

    @router.get('/library')
    def my_library(u:User=Depends(current_user),db:Session=Depends(get_db)):
        rows=db.scalars(select(CreatorMediaAsset).where(CreatorMediaAsset.creator_id==u.id)
                        .order_by(CreatorMediaAsset.id.desc()).limit(200)).all()
        return [asset_json(a) for a in rows]

    @router.post('/library/upload')
    async def upload_library(file:UploadFile=File(...),title:str=Form(...),level:str=Form('MAINSTREAM'),
                             u:User=Depends(current_user),db:Session=Depends(get_db)):
        creator_ready(db,u.id)
        name=title.strip()
        if len(name)<3 or len(name)>140:raise HTTPException(422,'Media title must be 3–140 characters')
        if level.upper() not in ('MAINSTREAM','GLAMOUR'):
            raise HTTPException(422,'Explicit media is not enabled in this LEMMIQ application')
        mime=(file.content_type or '').lower().split(';')[0]
        if mime not in ALLOWED_MIME:raise HTTPException(415,'Supported: JPG, PNG, WebP, MP4 and WebM')
        kind,size,signature=ALLOWED_MIME[mime]
        data=await file.read(size+1)
        if len(data)<12 or len(data)>size:raise HTTPException(413,'Invalid media size')
        if not signature(data):raise HTTPException(415,'File signature does not match content type')
        a=CreatorMediaAsset(creator_id=u.id,title=name,level=level.upper(),kind=kind,mime_type=mime,
                            object_key=media_store.store(data),size_bytes=len(data),review='APPROVED')
        db.add(a);db.commit();db.refresh(a)
        return asset_json(a)

    @router.get('/library/{asset_id}/media')
    def my_preview(asset_id:int,u:User=Depends(current_user),db:Session=Depends(get_db)):
        a=db.get(CreatorMediaAsset,asset_id)
        if not a or a.creator_id!=u.id:raise HTTPException(404,'Media unavailable')
        return private_stream(a.object_key,a.mime_type)

    @router.post('/gallery')
    def create_gallery(body:GalleryIn,u:User=Depends(current_user),db:Session=Depends(get_db)):
        creator_ready(db,u.id)
        kind=body.kind.upper();visibility=body.visibility.upper()
        if kind not in ('PHOTO','VIDEO','ALBUM') or visibility not in ('PPV','SUBSCRIBERS'):
            raise HTTPException(422,'Invalid exclusive item type or visibility')
        unique_ids=list(dict.fromkeys(body.asset_ids))
        if len(unique_ids)!=len(body.asset_ids):raise HTTPException(422,'Duplicate media in item')
        if kind!='ALBUM' and len(unique_ids)!=1:raise HTTPException(422,'Single photo/video items require exactly one media file')
        if kind=='ALBUM' and len(unique_ids)<2:raise HTTPException(422,'Albums need at least two files')
        assets=[db.get(CreatorMediaAsset,aid) for aid in unique_ids]
        if any(not a or a.creator_id!=u.id or a.review!='APPROVED' for a in assets):
            raise HTTPException(403,'Every file must belong to you and be available for publishing')
        if kind in ('PHOTO','VIDEO') and assets[0].kind!=kind:
            raise HTTPException(422,'Selected media does not match item type')
        price=to_micros(body.price_q,allow_zero=True)
        if visibility=='PPV' and price<=0:raise HTTPException(422,'PPV content requires a Q price')
        if visibility=='SUBSCRIBERS' and price:raise HTTPException(422,'Subscriber-included content has no extra PPV charge')
        item=CreatorGalleryItem(creator_id=u.id,title=body.title.strip(),teaser=body.teaser.strip(),
                                kind=kind,visibility=visibility,price_micros=price,review='APPROVED')
        db.add(item);db.flush()
        for i,a in enumerate(assets):db.add(CreatorGalleryAsset(item_id=item.id,asset_id=a.id,position=i))
        db.commit();db.refresh(item)
        return gallery_json(db,item,u.id)

    @router.get('/gallery/mine')
    def my_gallery(u:User=Depends(current_user),db:Session=Depends(get_db)):
        rows=db.scalars(select(CreatorGalleryItem).where(CreatorGalleryItem.creator_id==u.id)
                        .order_by(CreatorGalleryItem.id.desc()).limit(100)).all()
        return [gallery_json(db,item,u.id) for item in rows]

    @router.get('/profile/{creator_id}/gallery')
    def profile_gallery(creator_id:int,u:User=Depends(current_user),db:Session=Depends(get_db)):
        profile=db.get(CreatorProfile,creator_id)
        if not profile or (profile.status!='APPROVED' and creator_id!=u.id):
            raise HTTPException(404,'Creator unavailable')
        stmt=select(CreatorGalleryItem).where(CreatorGalleryItem.creator_id==creator_id)
        if creator_id!=u.id:stmt=stmt.where(CreatorGalleryItem.review=='APPROVED')
        rows=db.scalars(stmt.order_by(CreatorGalleryItem.id.desc()).limit(100)).all()
        return [gallery_json(db,item,u.id) for item in rows]

    @router.get('/gallery/{item_id}/assets')
    def gallery_media_list(item_id:int,u:User=Depends(current_user),db:Session=Depends(get_db)):
        item=db.get(CreatorGalleryItem,item_id)
        if not item:raise HTTPException(404,'Gallery item not found')
        if not gallery_can_read(db,item,u.id):raise HTTPException(403,'Unlock content before viewing')
        rows=db.scalars(select(CreatorGalleryAsset).where(CreatorGalleryAsset.item_id==item_id)
                        .order_by(CreatorGalleryAsset.position)).all()
        return [{'id':r.asset_id,'kind':db.get(CreatorMediaAsset,r.asset_id).kind} for r in rows]

    @router.get('/gallery/{item_id}/assets/{asset_id}/media')
    def gallery_media(item_id:int,asset_id:int,u:User=Depends(current_user),db:Session=Depends(get_db)):
        item=db.get(CreatorGalleryItem,item_id)
        if not item or not gallery_can_read(db,item,u.id):raise HTTPException(403,'Content is locked')
        linked=db.scalar(select(CreatorGalleryAsset.id).where(CreatorGalleryAsset.item_id==item_id,CreatorGalleryAsset.asset_id==asset_id))
        a=db.get(CreatorMediaAsset,asset_id)
        if not linked or not a or a.review!='APPROVED':raise HTTPException(404,'Approved media unavailable')
        return private_stream(a.object_key,a.mime_type)

    @router.post('/gallery/{item_id}/unlock')
    def unlock_gallery(item_id:int,body:UnlockIn,u:User=Depends(current_user),db:Session=Depends(get_db)):
        item=db.get(CreatorGalleryItem,item_id)
        if not item or item.review!='APPROVED' or item.visibility!='PPV':raise HTTPException(404,'PPV item unavailable')
        creator_ready(db,item.creator_id)
        stable_lock_wallet(db,u.id)
        if gallery_can_read(db,item,u.id):return {'unlocked':True,'charged_q':0}
        payment,created=create_payment(db,u.id,item.creator_id,'GALLERY',item.id,item.price_micros,body.request_key)
        if created:db.add(CreatorGalleryUnlock(fan_id=u.id,item_id=item.id,payment_id=payment.id))
        elif payment.status=='REFUNDED':raise HTTPException(409,'Previous payment refunded; use a new transaction key')
        elif not db.scalar(select(CreatorGalleryUnlock.id).where(CreatorGalleryUnlock.fan_id==u.id,CreatorGalleryUnlock.item_id==item.id)):
            db.add(CreatorGalleryUnlock(fan_id=u.id,item_id=item.id,payment_id=payment.id))
        db.commit()
        return {'unlocked':True,'charged_q':q(payment.gross_micros) if created else 0}

    @router.get('/chats')
    def own_chats(u:User=Depends(current_user),db:Session=Depends(get_db)):
        raise HTTPException(410,'Use Professional Inbox for creator PPV offers')
        rows=db.scalars(select(Chat).where((Chat.user1_id==u.id)|(Chat.user2_id==u.id))
                        .order_by(Chat.updated_at.desc()).limit(100)).all()
        out=[]
        for c in rows:
            uid=c.user2_id if c.user1_id==u.id else c.user1_id
            x=db.get(User,uid)
            if x:out.append({'chat_id':c.id,'other_id':uid,'username':x.username,'display_name':x.display_name})
        return out

    @router.post('/chats/{chat_id}/offers')
    async def send_offer(chat_id:int,body:SendOfferIn,u:User=Depends(current_user),db:Session=Depends(get_db)):
        # V2134_CREATOR_PRIVATE_OFFERS_ONLY: send via professional thread, never personal Chats
        raise HTTPException(410,'Use Professional Inbox for creator PPV offers')
        c=db.get(Chat,chat_id)
        if not c or u.id not in (c.user1_id,c.user2_id):raise HTTPException(404,'Chat not found')
        fan=c.user2_id if c.user1_id==u.id else c.user1_id
        if db.get(UserBlock,{'blocker_id':u.id,'blocked_id':fan}) or db.get(UserBlock,{'blocker_id':fan,'blocked_id':u.id}):
            raise HTTPException(403,'Cannot send paid offers to a blocked user')
        if not (active_subscription(db,fan,u.id) or db.scalar(select(CreatorFollow.id).where(
                CreatorFollow.fan_id==fan,CreatorFollow.creator_id==u.id))):
            raise HTTPException(403,'Fan must follow or subscribe before receiving paid media offers')
        item=db.get(CreatorGalleryItem,body.item_id)
        if not item or item.creator_id!=u.id or item.review!='APPROVED':
            raise HTTPException(404,'Approved gallery item not found')
        price=to_micros(body.price_q)
        previous=db.scalar(select(CreatorPrivateOffer).where(CreatorPrivateOffer.creator_id==u.id,CreatorPrivateOffer.client_key==body.client_key))
        if previous:
            if (previous.chat_id,previous.item_id,previous.price_micros)!=(chat_id,item.id,price):
                raise HTTPException(409,'Offer request key already used for another offer')
            return offer_json(db,previous,u.id)
        offer=CreatorPrivateOffer(creator_id=u.id,fan_id=fan,chat_id=chat_id,item_id=item.id,
                                  price_micros=price,client_key=body.client_key)
        db.add(offer);db.flush()
        m=Message(chat_id=chat_id,sender_id=u.id,text=f'[[QCREATORS_PPV:{offer.id}]]')
        c.updated_at=now()
        db.add(m);db.flush();offer.message_id=m.id
        db.commit();db.refresh(m)
        payload=msg_json(m,db)
        await push(fan,{'type':'message','data':payload})
        await push(u.id,{'type':'message','data':payload})
        return offer_json(db,offer,u.id)

    @router.get('/offers/inbox')
    def offers_inbox(u:User=Depends(current_user),db:Session=Depends(get_db)):
        rows=db.scalars(select(CreatorPrivateOffer).where(CreatorPrivateOffer.fan_id==u.id)
                        .order_by(CreatorPrivateOffer.id.desc()).limit(100)).all()
        return [offer_json(db,x,u.id) for x in rows if db.get(CreatorGalleryItem,x.item_id).review=='APPROVED']

    @router.get('/offers/{offer_id}')
    def offer_details(offer_id:int,u:User=Depends(current_user),db:Session=Depends(get_db)):
        o=db.get(CreatorPrivateOffer,offer_id)
        if not o or u.id not in (o.creator_id,o.fan_id):raise HTTPException(404,'Offer not found')
        return offer_json(db,o,u.id)

    @router.post('/offers/{offer_id}/unlock')
    def unlock_offer(offer_id:int,body:UnlockIn,u:User=Depends(current_user),db:Session=Depends(get_db)):
        offer=db.get(CreatorPrivateOffer,offer_id)
        if not offer or offer.fan_id!=u.id:raise HTTPException(404,'Private offer not found')
        item=db.get(CreatorGalleryItem,offer.item_id)
        if not item or item.review!='APPROVED':raise HTTPException(404,'Content unavailable')
        creator_ready(db,offer.creator_id)
        stable_lock_wallet(db,u.id)
        if gallery_can_read(db,item,u.id):return {'unlocked':True,'charged_q':0,'item_id':item.id}
        payment,created=create_payment(db,u.id,offer.creator_id,'DM_PPV',offer.id,offer.price_micros,body.request_key)
        if created:db.add(CreatorOfferUnlock(fan_id=u.id,offer_id=offer.id,payment_id=payment.id))
        elif payment.status=='REFUNDED':raise HTTPException(409,'Previous payment refunded; use a new transaction key')
        elif not db.scalar(select(CreatorOfferUnlock.id).where(CreatorOfferUnlock.fan_id==u.id,CreatorOfferUnlock.offer_id==offer.id)):
            db.add(CreatorOfferUnlock(fan_id=u.id,offer_id=offer.id,payment_id=payment.id))
        db.commit()
        return {'unlocked':True,'charged_q':q(payment.gross_micros) if created else 0,'item_id':item.id}

    def admin_media_log(db,u,creator_id,stype,sid):
        db.add(CreatorMediaAudit(admin_id=u.id,creator_id=creator_id,source_type=stype,source_id=sid))
        _audit(db,u.id,'CREATOR_MEDIA_INSPECT',target_user_id=creator_id,
               after={'source_type':stype,'source_id':sid},reason='Authorised creator safety review')
        db.commit()

    @router.get('/admin/media')
    def audit_media(limit:int=100,offset:int=0,u:User=Depends(current_user),db:Session=Depends(get_db)):
        admin_only(db,u)
        lim=min(200,max(1,limit));off=min(10000,max(0,offset))
        assets=db.scalars(select(CreatorMediaAsset).order_by(CreatorMediaAsset.id.desc()).offset(off).limit(lim)).all()
        posts=db.scalars(select(CreatorPost).where(CreatorPost.object_key!='').order_by(CreatorPost.id.desc()).offset(off).limit(lim)).all()
        galleries=db.scalars(select(CreatorGalleryItem).order_by(CreatorGalleryItem.id.desc()).offset(off).limit(lim)).all()
        def owner(uid):
            x=db.get(User,uid);return x.username if x else str(uid)
        return {'library':[dict(asset_json(a),creator_id=a.creator_id,username=owner(a.creator_id)) for a in assets],
                'gallery':[{'id':i.id,'creator_id':i.creator_id,'username':owner(i.creator_id),'title':i.title,
                            'kind':i.kind,'visibility':i.visibility,'review':i.review,
                            'price_q':q(i.price_micros),'asset_ids':linked_asset_ids(db,i.id),
                            'created_at':i.created_at.isoformat()} for i in galleries],
                'posts':[{'id':p.id,'creator_id':p.creator_id,'username':owner(p.creator_id),'title':p.title,'kind':p.kind,
                          'review':p.review,'visibility':p.visibility,'created_at':p.created_at.isoformat()} for p in posts],
                'next_offset':off+lim}

    @router.get('/admin/review-queue')
    def review_queue(u:User=Depends(current_user),db:Session=Depends(get_db)):
        admin_only(db,u)
        assets=db.scalars(select(CreatorMediaAsset).where(CreatorMediaAsset.review=='PENDING')
                          .order_by(CreatorMediaAsset.id.desc()).limit(100)).all()
        gallery=db.scalars(select(CreatorGalleryItem).where(CreatorGalleryItem.review=='PENDING')
                           .order_by(CreatorGalleryItem.id.desc()).limit(100)).all()
        return {'assets':[dict(asset_json(a),creator_id=a.creator_id) for a in assets],
                'gallery':[{'id':i.id,'creator_id':i.creator_id,'title':i.title,'kind':i.kind,'visibility':i.visibility,
                            'price_q':q(i.price_micros),'asset_ids':linked_asset_ids(db,i.id)} for i in gallery]}

    @router.post('/admin/assets/{asset_id}/review')
    def review_asset(asset_id:int,body:ReviewIn,u:User=Depends(current_user),db:Session=Depends(get_db)):
        admin_only(db,u)
        a=db.get(CreatorMediaAsset,asset_id)
        if not a:raise HTTPException(404,'Media missing')
        action=body.action.upper()
        if action not in ('APPROVE','REJECT'):raise HTTPException(422,'Use APPROVE or REJECT')
        old=a.review;a.review='APPROVED' if action=='APPROVE' else 'REJECTED'
        # If a previously approved file is removed for safety, linked galleries
        # must also be removed from sale until a fresh compliance review.
        linked=db.scalars(select(CreatorGalleryAsset.item_id).where(CreatorGalleryAsset.asset_id==a.id)).all()
        if action=='REJECT' and linked:
            db.execute(update(CreatorGalleryItem).where(CreatorGalleryItem.id.in_(linked)).values(review='REJECTED'))
            _audit(db,u.id,'CREATOR_LINKED_GALLERY_SUSPEND',target_user_id=a.creator_id,
                   after={'asset_id':a.id,'gallery_ids':linked},reason=body.reason)
        _audit(db,u.id,'CREATOR_MEDIA_REVIEW',target_user_id=a.creator_id,
               before={'review':old},after={'asset_id':a.id,'review':a.review},reason=body.reason)
        db.commit();return {'review':a.review}

    @router.post('/admin/gallery/{item_id}/review')
    def review_gallery(item_id:int,body:ReviewIn,u:User=Depends(current_user),db:Session=Depends(get_db)):
        admin_only(db,u)
        item=db.get(CreatorGalleryItem,item_id)
        if not item:raise HTTPException(404,'Gallery item missing')
        action=body.action.upper()
        if action not in ('APPROVE','REJECT'):raise HTTPException(422,'Use APPROVE or REJECT')
        if action=='APPROVE':
            for aid in linked_asset_ids(db,item.id):
                a=db.get(CreatorMediaAsset,aid)
                if not a or a.review!='APPROVED':raise HTTPException(409,'Approve all linked assets first')
            creator_ready(db,item.creator_id)
        old=item.review;item.review='APPROVED' if action=='APPROVE' else 'REJECTED'
        _audit(db,u.id,'CREATOR_GALLERY_REVIEW',target_user_id=item.creator_id,
               before={'review':old},after={'item_id':item.id,'review':item.review},reason=body.reason)
        db.commit();return {'review':item.review}

    @router.get('/admin/assets/{asset_id}/media')
    def admin_asset_media(asset_id:int,u:User=Depends(current_user),db:Session=Depends(get_db)):
        admin_only(db,u)
        a=db.get(CreatorMediaAsset,asset_id)
        if not a:raise HTTPException(404,'Media unavailable')
        admin_media_log(db,u,a.creator_id,'LIBRARY',a.id)
        return private_stream(a.object_key,a.mime_type)

    @router.get('/admin/posts/{post_id}/media')
    def admin_post_media(post_id:int,u:User=Depends(current_user),db:Session=Depends(get_db)):
        admin_only(db,u)
        p=db.get(CreatorPost,post_id)
        if not p or not p.object_key:raise HTTPException(404,'Media unavailable')
        admin_media_log(db,u,p.creator_id,'POST',p.id)
        return private_stream(p.object_key,p.mime_type)

    @router.get('/admin/access-log')
    def access_log(limit:int=100,u:User=Depends(current_user),db:Session=Depends(get_db)):
        admin_only(db,u)
        rows=db.scalars(select(CreatorMediaAudit).order_by(CreatorMediaAudit.id.desc()).limit(min(200,max(1,limit)))).all()
        return [{'id':r.id,'admin_id':r.admin_id,'creator_id':r.creator_id,'source_type':r.source_type,
                 'source_id':r.source_id,'reason':r.reason,'accessed_at':r.accessed_at.isoformat()} for r in rows]

    app.include_router(router)
