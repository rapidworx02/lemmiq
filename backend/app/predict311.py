"""V3.1.1 read-only prediction presentation. No wallet mutations."""
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, or_, and_
from .v29 import PredictMarket
from .v2138_predict import DemoPosition, DemoPool, DemoResolution
from .v21310_predict_q import Position, Pool, Resolution, _team_ids


def units(n): return float(Decimal(int(n or 0))/Decimal(1000000))
def iso(d): return (d if d.tzinfo else d.replace(tzinfo=timezone.utc)).isoformat() if d else None

def models(demo): return (DemoPosition,DemoPool,DemoResolution) if demo else (Position,Pool,Resolution)

def aggregate(db,ids,demo):
    pos,pool,_=models(demo)
    if not ids:return {}
    pools={p.market_id:p for p in db.scalars(select(pool).where(pool.market_id.in_(ids))).all()}
    counts=dict(db.execute(select(pos.market_id,func.count(func.distinct(pos.user_id))).where(pos.market_id.in_(ids)).group_by(pos.market_id)).all())
    return {i:{'yes_pool':units(pools[i].yes_micros) if i in pools else 0,'no_pool':units(pools[i].no_micros) if i in pools else 0,'participants':int(counts.get(i,0))} for i in ids}

def enrich(db,rows,demo):
    stats=aggregate(db,[r['id'] for r in rows],demo)
    for row in rows:row.update(stats[row['id']])
    return rows

def history(db,uid,demo,status='recent',days=30,offset=0,limit=20,market_id=None):
    pos,pool,res=models(demo); now=datetime.now(timezone.utc)
    settled=pool.settled_at.is_not(None)
    live=and_(PredictMarket.status.in_(['LIVE','SUSPENDED']),PredictMarket.close_at>now)
    pred=[pos.user_id==uid]
    if market_id is not None:pred.append(pos.market_id==market_id)
    else:
        if status=='recent':pred.append(settled)
        elif status=='active':pred.extend([pool.settled_at.is_(None),live])
        else:pred.extend([pool.settled_at.is_(None),~live])
        if days and status=='recent':pred.append(pool.settled_at>=now-timedelta(days=days))
    # Page by distinct market, not individual sides. Both sides are included.
    q=select(pos.market_id,func.max(pos.created_at).label('last_stake'),func.max(pool.settled_at).label('settled')).join(PredictMarket,PredictMarket.id==pos.market_id).outerjoin(pool,pool.market_id==pos.market_id).where(*pred).group_by(pos.market_id)
    ordered=q.order_by(func.max(pool.settled_at).desc().nulls_last(),func.max(pos.created_at).desc(),pos.market_id.desc())
    ids=[r[0] for r in db.execute(ordered.offset(offset).limit(limit+1)).all()];more=len(ids)>limit;ids=ids[:limit]
    if not ids:return {'items':[],'has_more':False,'summary':{'markets':0,'stake':0,'returned':0,'net':0}}
    grouped={}
    for p,m,pl,r in db.execute(select(pos,PredictMarket,pool,res).join(PredictMarket,PredictMarket.id==pos.market_id).outerjoin(pool,pool.market_id==pos.market_id).outerjoin(res,res.market_id==pos.market_id).where(pos.user_id==uid,pos.market_id.in_(ids))).all():
        x=grouped.setdefault(m.id,{'market_id':m.id,'question':m.question,'category':m.category,'market_status':m.status,'close_at':iso(m.close_at),'settled_at':iso(pl.settled_at) if pl else None,'result':r.outcome if r and pl and pl.settled_at else None,'evidence':r.evidence if r and pl and pl.settled_at else None,'positions':[]})
        x['positions'].append({'side':p.outcome,'stake':units(p.stake_micros),'returned':units(p.payout_micros),'fee':units(p.fee_micros),'status':p.status})
    for x in grouped.values():
        if x['settled_at'] and all(p['status']=='VOID' for p in x['positions']):x['settlement_status']='REFUNDED'
        elif x['settled_at']:x['settlement_status']='SETTLED'
        else:x['settlement_status']='PENDING'
    totals=db.execute(select(func.count(func.distinct(pos.market_id)),func.coalesce(func.sum(pos.stake_micros),0),func.coalesce(func.sum(pos.payout_micros),0)).join(PredictMarket,PredictMarket.id==pos.market_id).outerjoin(pool,pool.market_id==pos.market_id).where(*pred)).one()
    return {'items':[grouped[i] for i in ids if i in grouped],'has_more':more,'summary':{'markets':totals[0],'stake':units(totals[1]),'returned':units(totals[2]),'net':units(totals[2]-totals[1]) if status=='recent' else None}}

def register_predict311(app,current_user,get_db):
    router=APIRouter(prefix='/v311/predict')
    @router.get('/history')
    def mine(wallet:str='DEMO',status:str='recent',days:int=Query(30,ge=0,le=3650),offset:int=Query(0,ge=0),limit:int=Query(20,ge=1,le=50),market_id:int|None=None,u=Depends(current_user),db=Depends(get_db)):
        if wallet not in ('DEMO','REAL_Q') or status not in ('active','awaiting','recent'):raise HTTPException(422,'Invalid wallet or history status')
        if wallet=='REAL_Q' and u.id not in _team_ids():raise HTTPException(403,'Verification required')
        return history(db,u.id,wallet=='DEMO',status,days,offset,limit,market_id)
    @router.get('/pools')
    def pools(wallet:str='DEMO',ids:str=Query('',max_length=1000),u=Depends(current_user),db=Depends(get_db)):
        if wallet not in ('DEMO','REAL_Q'):raise HTTPException(422,'Invalid wallet')
        if wallet=='REAL_Q' and u.id not in _team_ids():raise HTTPException(403,'Verification required')
        try: wanted=list(dict.fromkeys(int(x) for x in ids.split(',') if x))
        except ValueError:raise HTTPException(422,'Invalid market IDs')
        if len(wanted)>100:raise HTTPException(422,'Too many markets')
        if not wanted:return {}
        q=select(PredictMarket.id).where(PredictMarket.id.in_(wanted),PredictMarket.status.in_(['LIVE','CLOSED','SUSPENDED','RESOLVING','RESOLVED','VOID']))
        if wallet=='REAL_Q':q=q.where(~PredictMarket.template_code.startswith('CRICKET_V21314_'))
        valid=db.scalars(q).all()
        return aggregate(db,valid,wallet=='DEMO')
    app.include_router(router)
