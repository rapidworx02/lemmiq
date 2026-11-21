"""LEMMIQ V3.0.6: market lifecycle operations and calling policy.
Existing settlement and treasury routes are deliberately not replaced.
"""
from datetime import datetime, timezone
from typing import Literal
import json
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import Boolean, Integer, ForeignKey, select, case, and_, func
from sqlalchemy.orm import Mapped, mapped_column, Session
from .database import Base
from .v29 import PredictMarket, _require_admin
from .v2138_predict import AdminAudit, DemoResolution, _settle_due
from .v2105_q_features import _tier_code

class CallPolicy306(Base):
    __tablename__ = 'v306_call_policy'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    paid_only: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

class Archive306(Base):
    __tablename__ = 'v306_predict_archive'
    market_id: Mapped[int] = mapped_column(ForeignKey('q_predict_markets.id'), primary_key=True)

class Action306(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=100)
    action: Literal['SUSPEND','RESUME','CLOSE','VOID_DEMO','ARCHIVE']
    reason: str = Field(min_length=8, max_length=500)

class Policy306In(BaseModel):
    paid_only: bool
    reason: str = Field(min_length=8,max_length=500)

def utcnow(): return datetime.now(timezone.utc)
def aware(dt): return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
def cricket(m): return str(m.template_code or '').startswith('CRICKET_V21314_')
def audit(db, uid, action, detail):
    db.add(AdminAudit(admin_user_id=uid, action=action, detail=json.dumps(detail, ensure_ascii=False)))
def master(db,u):
    if _require_admin(db,u,'FULL','Q_PREDICT') != 'MASTER_ADMIN':
        raise HTTPException(403,'Master Admin required')
def calling_allowed(db,u):
    policy=db.get(CallPolicy306,1)
    if policy and policy.paid_only and _tier_code(db,u.id) not in {'STARTER_10','PLUS_50','PRO_100','PREMIUM_500','ELITE_1000'}:
        raise HTTPException(403,'An active Q Starter Pack or higher is required to make calls.')

def register_v306_admin(app,current_user,get_db):
    router=APIRouter(prefix='/v306/admin')
    @router.get('/markets')
    def markets(q:str=Query('',max_length=260),category:str=Query('',max_length=40),status:str=Query('',max_length=24),page:int=Query(1,ge=1,le=100000),limit:int=Query(50,ge=1,le=100),u=Depends(current_user),db:Session=Depends(get_db)):
        _require_admin(db,u,'READ','Q_PREDICT')
        access='READ'
        for level in ('WRITE','FULL'):
            try: _require_admin(db,u,level,'Q_PREDICT');access=level
            except HTTPException as e:
                if e.status_code!=403:raise
                break
        is_cricket=PredictMarket.template_code.startswith('CRICKET_V21314_',autoescape=True)
        effective=case(
            (Archive306.market_id.is_not(None),'ARCHIVED'),
            (and_(is_cricket,DemoResolution.outcome=='VOID'),'VOID'),
            (and_(is_cricket,DemoResolution.market_id.is_not(None)),'RESOLVED'),
            (and_(PredictMarket.status.in_(['LIVE','SUSPENDED']),PredictMarket.close_at<=utcnow()),'CLOSED'),
            else_=PredictMarket.status)
        base=select(PredictMarket,effective.label('effective_status')).outerjoin(Archive306,Archive306.market_id==PredictMarket.id).outerjoin(DemoResolution,DemoResolution.market_id==PredictMarket.id)
        q=q.strip();category=category.strip();status=status.strip().upper()
        if q:
            if q.lstrip('#').isdigit():
                digits=q.lstrip('#');base=base.where(PredictMarket.id==int(digits) if len(digits)<=10 and int(digits)<=2147483647 else False)
            else:
                pattern=q.replace('\\','\\\\').replace('%','\\%').replace('_','\\_');base=base.where(PredictMarket.question.ilike('%'+pattern+'%',escape='\\'))
        if category:base=base.where(PredictMarket.category==category)
        if status:base=base.where(effective==status)
        total=int(db.scalar(select(func.count()).select_from(base.subquery())) or 0)
        pages=max(1,(total+limit-1)//limit);page=min(page,pages)
        rows=db.execute(base.order_by(PredictMarket.id.desc()).offset((page-1)*limit).limit(limit)).all()
        cats=db.scalars(select(PredictMarket.category).distinct().order_by(PredictMarket.category)).all()
        return {'access':access,'markets':[dict(id=m.id,question=m.question,category=m.category,status=st,close_at=aware(m.close_at).isoformat(),demo_only=cricket(m),template=m.template_code,official_url=m.resolution_source_url) for m,st in rows], 'limit':limit,'page':page,'pages':pages,'total':total,'categories':cats}

    @router.post('/markets/action')
    def action(body:Action306,u=Depends(current_user),db:Session=Depends(get_db)):
        _require_admin(db,u,'WRITE' if body.action in ('SUSPEND','RESUME') else 'FULL','Q_PREDICT')
        reason=body.reason.strip()
        if len(reason)<8: raise HTTPException(422,'Reason must contain at least 8 characters')
        ids=sorted(set(body.ids))
        if any(i<=0 for i in ids):raise HTTPException(422,'Invalid market ID')
        rows=db.scalars(select(PredictMarket).where(PredictMarket.id.in_(ids)).order_by(PredictMarket.id).with_for_update()).all()
        if len(rows)!=len(ids):raise HTTPException(404,'One or more markets not found')
        for m in rows:
            before=m.status; deadline=aware(m.close_at); due=deadline<=utcnow(); r=db.get(DemoResolution,m.id)
            if db.get(Archive306,m.id):raise HTTPException(409,f'Market #{m.id} is archived')
            if body.action=='SUSPEND' and before=='LIVE' and not due and not r:m.status='SUSPENDED'
            elif body.action=='RESUME' and before=='SUSPENDED' and not due and not r:m.status='LIVE'
            elif body.action=='CLOSE' and before in ('LIVE','SUSPENDED') and not r:m.status='CLOSED'
            elif body.action=='VOID_DEMO' and cricket(m) and before in ('LIVE','SUSPENDED','CLOSED') and not r:
                m.status='CLOSED'
                db.add(DemoResolution(market_id=m.id,outcome='VOID',evidence=reason,resolved_by=u.id))
            elif body.action=='ARCHIVE' and (before in ('RESOLVED','VOID') or (cricket(m) and r is not None)):
                db.add(Archive306(market_id=m.id))
            else:raise HTTPException(409,f'Market #{m.id}: {body.action} not allowed in {before}')
            m.updated_at=utcnow()
            audit(db,u.id,'V306_'+body.action,{'market_id':m.id,'before':before,'after':m.status,'reason':reason})
        if body.action=='VOID_DEMO':db.flush();_settle_due(db)
        db.commit()
        return {'ok':True,'ids':ids,'action':body.action}
    @router.get('/calling')
    def get_calling(u=Depends(current_user),db:Session=Depends(get_db)):
        master(db,u);p=db.get(CallPolicy306,1);return {'paid_only':bool(p and p.paid_only)}
    @router.put('/calling')
    def set_calling(body:Policy306In,u=Depends(current_user),db:Session=Depends(get_db)):
        master(db,u);reason=body.reason.strip()
        if len(reason)<8:raise HTTPException(422,'Reason required')
        p=db.scalar(select(CallPolicy306).where(CallPolicy306.id==1).with_for_update())
        old=bool(p and p.paid_only)
        if not p:p=CallPolicy306(id=1,paid_only=False);db.add(p)
        p.paid_only=body.paid_only;audit(db,u.id,'V306_CALL_POLICY',{'before':old,'after':p.paid_only,'reason':reason});db.commit()
        return {'paid_only':body.paid_only}
    app.include_router(router)
