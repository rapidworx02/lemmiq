"""V2.13.5 — private creator-to-fan attachments, Q PPV, audit and quarantine.

Approved professional creators can send photo/video in an existing professional
thread. Raw media never appears in JSON or unauthenticated public URLs.
This is a beta safety baseline (file signature checks, audit, reports, quarantine),
NOT a replacement for a production image/video content moderation provider.
Explicit material is prohibited in the mainstream LEMMIQ app.
"""
from __future__ import annotations
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, select, func
from sqlalchemy.orm import Session, Mapped, mapped_column
from .database import Base
from .models import User, UserBlock
from . import media_store
from .v2131_exclusives import ALLOWED_MIME
from .v213_creators import create_payment, creator_ready, admin_only, q, to_micros, CreatorPayment
from .v2134_professional import ProfessionalMessage, ProfessionalThread, require_thread, blocked

def now(): return datetime.now(timezone.utc)

class CreatorDirectMedia(Base):
    __tablename__='v2135_creator_direct_media'
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    message_id:Mapped[int]=mapped_column(ForeignKey('v2134_professional_messages.id'),unique=True,index=True)
    thread_id:Mapped[str]=mapped_column(ForeignKey('v2134_professional_threads.id'),index=True)
    creator_id:Mapped[int]=mapped_column(ForeignKey('users.id'),index=True)
    fan_id:Mapped[int]=mapped_column(ForeignKey('users.id'),index=True)
    object_key:Mapped[str]=mapped_column(String(240))
    mime_type:Mapped[str]=mapped_column(String(40))
    kind:Mapped[str]=mapped_column(String(10))
    size_bytes:Mapped[int]=mapped_column(BigInteger)
    price_micros:Mapped[int]=mapped_column(BigInteger,default=0)
    status:Mapped[str]=mapped_column(String(20),default='VISIBLE',index=True)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now,index=True)

class CreatorDirectUnlock(Base):
    __tablename__='v2135_creator_direct_unlocks'
    __table_args__=(UniqueConstraint('fan_id','media_id',name='uq_v2135_fan_media'),)
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    fan_id:Mapped[int]=mapped_column(ForeignKey('users.id'),index=True)
    media_id:Mapped[int]=mapped_column(ForeignKey('v2135_creator_direct_media.id'),index=True)
    payment_id:Mapped[int]=mapped_column(ForeignKey('v213_creator_payments.id'))

class CreatorDirectAudit(Base):
    __tablename__='v2135_creator_direct_audits'
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    admin_id:Mapped[int]=mapped_column(ForeignKey('users.id'),index=True)
    creator_id:Mapped[int]=mapped_column(ForeignKey('users.id'),index=True)
    media_id:Mapped[int]=mapped_column(ForeignKey('v2135_creator_direct_media.id'),index=True)
    action:Mapped[str]=mapped_column(String(28))
    reason:Mapped[str]=mapped_column(String(240),default='')
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class CreatorDirectReport(Base):
    __tablename__='v2135_creator_direct_reports'
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    media_id:Mapped[int]=mapped_column(ForeignKey('v2135_creator_direct_media.id'),index=True)
    reporter_id:Mapped[int]=mapped_column(ForeignKey('users.id'),index=True)
    reason:Mapped[str]=mapped_column(String(100))
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class BuyIn(BaseModel):
    request_key:str
class ReportIn(BaseModel):
    reason:str
class ReviewIn(BaseModel):
    action:str
    reason:str=''

def media_purchased(db,media_id,fan_id):
    return bool(db.scalar(select(CreatorDirectUnlock.id).join(CreatorPayment,CreatorPayment.id==CreatorDirectUnlock.payment_id).where(
        CreatorDirectUnlock.media_id==media_id,CreatorDirectUnlock.fan_id==fan_id,CreatorPayment.status=='CAPTURED')))

def media_info(db,media,uid):
    bought=media_purchased(db,media.id,uid)
    owner=uid==media.creator_id
    allowed=bool(owner or (media.kind=='FREE') or bought)
    return {'id':media.id,'kind':media.kind,'media_kind':'VIDEO' if media.mime_type.startswith('video/') else 'PHOTO',
            'price_q':q(media.price_micros),'unlocked':allowed,'status':media.status,
            'created_at':media.created_at.isoformat(),
            'media_url':f'/v2135/media/{media.id}/file' if allowed and media.status=='VISIBLE' else None}

def attach_json(db,message,uid):
    if message.kind!='DIRECT_MEDIA':return None
    media=db.scalar(select(CreatorDirectMedia).where(CreatorDirectMedia.message_id==message.id))
    return media_info(db,media,uid) if media else None

def register_v2135_direct_media(app,current_user,get_db,push):
    router=APIRouter(prefix='/v2135',tags=['Professional creator direct media'])
    @app.on_event('startup')
    def create_tables():
        from .database import engine
        Base.metadata.create_all(bind=engine)

    def media_for(db,mid,uid):
        media=db.get(CreatorDirectMedia,mid)
        if not media or uid not in (media.creator_id,media.fan_id):raise HTTPException(404,'Media unavailable')
        if blocked(db,media.creator_id,media.fan_id):raise HTTPException(403,'Conversation blocked')
        return media

    @router.post('/chats/{tid}/media')
    async def upload(tid:str,file:UploadFile=File(...),kind:str=Form('FREE'),price_q:float=Form(0),
                     u:User=Depends(current_user),db:Session=Depends(get_db)):
        t=require_thread(db,tid,u.id)
        if u.id!=t.creator_id:raise HTTPException(403,'Only a creator can send creator media')
        creator_ready(db,u.id)
        if blocked(db,t.creator_id,t.fan_id):raise HTTPException(403,'Conversation blocked')
        # Send within an existing professional thread; no personal messaging fallback.
        mode=kind.strip().upper()
        if mode not in ('FREE','PPV'):raise HTTPException(422,'Choose FREE or PPV')
        price=to_micros(price_q,allow_zero=True)
        if (mode=='PPV' and price<=0) or (mode=='FREE' and price!=0):
            raise HTTPException(422,'FREE requires 0 Q; PPV requires a positive price')
        mime=(file.content_type or '').lower().split(';')[0]
        if mime not in ALLOWED_MIME:raise HTTPException(415,'Supported: JPEG, PNG, WebP, MP4 and WebM')
        media_kind,max_size,check=ALLOWED_MIME[mime]
        content=await file.read(max_size+1)
        if len(content)<12 or len(content)>max_size:raise HTTPException(413,'Media exceeds upload limit')
        if not check(content):raise HTTPException(415,'File signature does not match selected media type')
        # Limited anti-spam gate for unrequested/free media in existing threads.
        db.execute(select(ProfessionalThread.id).where(ProfessionalThread.id==tid).with_for_update()).all()
        recent=db.scalar(select(func.count()).select_from(CreatorDirectMedia).where(
            CreatorDirectMedia.thread_id==tid,CreatorDirectMedia.created_at>=now()-timedelta(minutes=10))) or 0
        if recent>=8:raise HTTPException(429,'Please wait before sending more creator media')
        # Verified approved creators only. No claim of AI content classification.
        # Keep original private media so authorised moderators can review it later.
        key=media_store.store(content)
        msg=ProfessionalMessage(thread_id=tid,role='CREATOR',kind='DIRECT_MEDIA',body='')
        db.add(msg);db.flush()
        media=CreatorDirectMedia(message_id=msg.id,thread_id=tid,creator_id=t.creator_id,
            fan_id=t.fan_id,object_key=key,mime_type=mime,kind=mode,size_bytes=len(content),
            price_micros=price,status='VISIBLE')
        db.add(media);t.updated_at=now();db.commit();db.refresh(media)
        await push(t.fan_id,{'type':'creator_professional_message','thread_id':tid})
        return {'message_id':msg.id,'media':media_info(db,media,u.id)}

    @router.get('/media/{mid}/file')
    def serve(mid:int,u:User=Depends(current_user),db:Session=Depends(get_db)):
        media=media_for(db,mid,u.id)
        if media.status!='VISIBLE':raise HTTPException(404,'This media is unavailable')
        unlocked=media.kind=='FREE' or u.id==media.creator_id or media_purchased(db,mid,u.id)
        if not unlocked:raise HTTPException(403,'Pay Q to unlock this media')
        return StreamingResponse(media_store.stream(media.object_key),media_type=media.mime_type,
            headers={'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff'})

    @router.post('/media/{mid}/unlock')
    def unlock(mid:int,body:BuyIn,u:User=Depends(current_user),db:Session=Depends(get_db)):
        media=media_for(db,mid,u.id)
        if u.id!=media.fan_id:raise HTTPException(403,'Only the fan may buy media')
        if media.status!='VISIBLE':raise HTTPException(404,'Media unavailable')
        if media.kind!='PPV':return {'unlocked':True,'charged_q':0}
        # Serialize concurrent attempts across devices on the same fan row.
        db.execute(select(User.id).where(User.id==u.id).with_for_update()).all()
        existing=db.scalar(select(CreatorDirectUnlock).where(CreatorDirectUnlock.fan_id==u.id,
            CreatorDirectUnlock.media_id==mid))
        if existing and db.get(CreatorPayment,existing.payment_id).status=='CAPTURED':
            return {'unlocked':True,'charged_q':0}
        payment,created=create_payment(db,u.id,media.creator_id,'DIRECT_PPV',mid,media.price_micros,body.request_key)
        if payment.status!='CAPTURED':raise HTTPException(409,'Payment not settled')
        if existing:existing.payment_id=payment.id
        else:db.add(CreatorDirectUnlock(fan_id=u.id,media_id=mid,payment_id=payment.id))
        db.commit()
        return {'unlocked':True,'charged_q':q(payment.gross_micros) if created else 0}

    @router.post('/media/{mid}/report')
    def report(mid:int,body:ReportIn,u:User=Depends(current_user),db:Session=Depends(get_db)):
        media=media_for(db,mid,u.id)
        if u.id!=media.fan_id:raise HTTPException(403,'Only the recipient may report this media')
        reason=body.reason.strip()[:100]
        if len(reason)<4:raise HTTPException(422,'Provide a report reason')
        db.add(CreatorDirectReport(media_id=mid,reporter_id=u.id,reason=reason))
        media.status='QUARANTINED'  # Fail closed pending human review
        db.commit();return {'status':'QUARANTINED'}

    @router.get('/admin/media')
    def admin_media(limit:int=100,u:User=Depends(current_user),db:Session=Depends(get_db)):
        admin_only(db,u)
        rows=db.scalars(select(CreatorDirectMedia).order_by(CreatorDirectMedia.id.desc()).limit(min(max(limit,1),200))).all()
        return [{'id':m.id,'creator_id':m.creator_id,'fan_id':m.fan_id,'kind':m.kind,'status':m.status,
                 'mime_type':m.mime_type,'price_q':q(m.price_micros),'size_bytes':m.size_bytes,
                 'created_at':m.created_at.isoformat()} for m in rows]

    @router.get('/admin/media/{mid}/file')
    def admin_file(mid:int,u:User=Depends(current_user),db:Session=Depends(get_db)):
        admin_only(db,u)
        media=db.get(CreatorDirectMedia,mid)
        if not media:raise HTTPException(404,'Media missing')
        db.add(CreatorDirectAudit(admin_id=u.id,creator_id=media.creator_id,media_id=mid,action='VIEW'))
        db.commit()
        return StreamingResponse(media_store.stream(media.object_key),media_type=media.mime_type,
           headers={'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff'})

    @router.post('/admin/media/{mid}/review')
    def review(mid:int,body:ReviewIn,u:User=Depends(current_user),db:Session=Depends(get_db)):
        admin_only(db,u)
        media=db.get(CreatorDirectMedia,mid)
        if not media:raise HTTPException(404,'Media missing')
        action=body.action.upper()
        if action not in ('QUARANTINE','RESTORE'):raise HTTPException(422,'Use QUARANTINE or RESTORE')
        media.status='QUARANTINED' if action=='QUARANTINE' else 'VISIBLE'
        db.add(CreatorDirectAudit(admin_id=u.id,creator_id=media.creator_id,media_id=mid,
            action=action,reason=body.reason[:240]))
        db.commit();return {'status':media.status}

    @router.get('/admin/audit')
    def audit(u:User=Depends(current_user),db:Session=Depends(get_db)):
        admin_only(db,u)
        rows=db.scalars(select(CreatorDirectAudit).order_by(CreatorDirectAudit.id.desc()).limit(200)).all()
        return [{'id':r.id,'admin_id':r.admin_id,'media_id':r.media_id,'action':r.action,
                 'reason':r.reason,'time':r.created_at.isoformat()} for r in rows]

    app.include_router(router)
