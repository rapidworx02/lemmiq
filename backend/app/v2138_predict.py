"""LEMMIQ V2.13.8: non-redeemable Demo USDT prediction engine and locked Real-mode specification.

SECURITY: Demo balances have zero monetary value and never touch Q Economy or a blockchain.
Real-mode USDT deposits, stakes and withdrawals are deliberately NOT implemented/activated.
No admin UI toggle or environment variable enables real wagering in this module.
"""
from __future__ import annotations
import secrets
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_DOWN
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, select, text
from sqlalchemy.orm import Mapped, Session, mapped_column
from .database import Base
from .models import User
from .v29 import PredictMarket, _require_admin

MICRO = 1_000_000
MAX_DEMO_AMOUNT = 1_000_000_000 * MICRO

def now(): return datetime.now(timezone.utc)
def aware(dt): return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
def as_units(value): return round(int(value) / MICRO, 6)

def micros(value):
    try:
        amount = Decimal(str(value))
        if not amount.is_finite() or amount <= 0 or amount > 1_000_000:
            raise ValueError()
        if amount != amount.quantize(Decimal('0.01')):
            raise ValueError()
        return int(amount * MICRO)
    except (ValueError, InvalidOperation, TypeError):
        raise HTTPException(422, 'Enter a positive amount with no more than two decimal places')

class DemoConfig(Base):
    __tablename__ = 'v2138_predict_config'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    grant_micros: Mapped[int] = mapped_column(BigInteger, default=1000*MICRO)
    profit_fee_bps: Mapped[int] = mapped_column(Integer, default=1000)
    deposit_fee_micros: Mapped[int] = mapped_column(BigInteger, default=MICRO)
    withdrawal_fee_micros: Mapped[int] = mapped_column(BigInteger, default=MICRO)
    requested_mode: Mapped[str] = mapped_column(String(30), default='DEMO')
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class DemoWallet(Base):
    __tablename__ = 'v2138_demo_wallets'
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), primary_key=True)
    available_micros: Mapped[int] = mapped_column(BigInteger, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class DemoPool(Base):
    __tablename__ = 'v2138_demo_pools'
    market_id: Mapped[int] = mapped_column(ForeignKey('q_predict_markets.id'), primary_key=True)
    fee_bps: Mapped[int] = mapped_column(Integer, default=1000) # Snapshot when first stake opens the pool
    yes_micros: Mapped[int] = mapped_column(BigInteger, default=0)
    no_micros: Mapped[int] = mapped_column(BigInteger, default=0)
    settled_at: Mapped[datetime|None] = mapped_column(DateTime(timezone=True), nullable=True)

class DemoPosition(Base):
    __tablename__ = 'v2138_demo_positions'
    __table_args__ = (UniqueConstraint('user_id','market_id','outcome',name='uq_v2138_demo_user_market_side'),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    market_id: Mapped[int] = mapped_column(ForeignKey('q_predict_markets.id'), index=True)
    outcome: Mapped[str] = mapped_column(String(6))
    stake_micros: Mapped[int] = mapped_column(BigInteger, default=0)
    payout_micros: Mapped[int] = mapped_column(BigInteger, default=0)
    fee_micros: Mapped[int] = mapped_column(BigInteger, default=0)
    status: Mapped[str] = mapped_column(String(12), default='OPEN')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class DemoEntry(Base):
    __tablename__ = 'v2138_demo_ledger'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    txid: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    from_account: Mapped[str] = mapped_column(String(80), index=True)
    to_account: Mapped[str] = mapped_column(String(80), index=True)
    amount_micros: Mapped[int] = mapped_column(BigInteger)
    kind: Mapped[str] = mapped_column(String(24))
    market_id: Mapped[int|None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class DemoResolution(Base):
    __tablename__ = 'v2138_demo_resolutions'
    market_id: Mapped[int] = mapped_column(ForeignKey('q_predict_markets.id'),primary_key=True)
    outcome: Mapped[str] = mapped_column(String(8))
    evidence: Mapped[str] = mapped_column(String(500))
    resolved_by: Mapped[int] = mapped_column(ForeignKey('users.id'))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),default=now)

class DemoRequest(Base):
    __tablename__ = 'v2138_demo_stake_requests'
    __table_args__ = (UniqueConstraint('user_id','request_key',name='uq_v2138_user_request'),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    request_key: Mapped[str] = mapped_column(String(64))
    market_id: Mapped[int] = mapped_column(Integer)
    amount_micros: Mapped[int] = mapped_column(BigInteger)
    outcome: Mapped[str] = mapped_column(String(6))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class RealWalletPlaceholder(Base):
    __tablename__ = 'v2138_real_wallets_locked'
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'),primary_key=True)
    available_micros: Mapped[int] = mapped_column(BigInteger,default=0)
    held_micros: Mapped[int] = mapped_column(BigInteger,default=0)
    # Always zero. No deposit addresses, chains, keys, real assets or payouts in 2.13.8.

class AdminAudit(Base):
    __tablename__ = 'v2138_predict_admin_audit'
    id: Mapped[int] = mapped_column(Integer,primary_key=True)
    admin_user_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    action: Mapped[str] = mapped_column(String(50))
    detail: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),default=now)

class StakeIn(BaseModel):
    market_id: int = Field(gt=0)
    outcome: Literal['YES','NO']
    amount: Decimal = Field(gt=0,le=250)
    request_key: str = Field(min_length=12,max_length=64,pattern=r'^[A-Za-z0-9_-]+$')

class ConfigIn(BaseModel):
    requested_mode: Literal['DEMO','REAL'] = 'DEMO'
    grant: Decimal = Field(default=Decimal('1000'),ge=100,le=10000)
    profit_fee_percent: Decimal = Field(default=Decimal('10'),ge=0,le=20)
    deposit_fee: Decimal = Field(default=Decimal('1'),ge=0,le=100)
    withdrawal_fee: Decimal = Field(default=Decimal('1'),ge=0,le=100)


class ResolveDemoIn(BaseModel):
    outcome: Literal['YES','NO','VOID']
    evidence: str = Field(min_length=10,max_length=500)

def _config(db):
    c=db.get(DemoConfig,1)
    if not c:
        # Unique ID, one initial configuration. Sequential startup normally initializes this.
        db.execute(text("INSERT INTO v2138_predict_config (id,grant_micros,profit_fee_bps,deposit_fee_micros,withdrawal_fee_micros,requested_mode,updated_at) VALUES (1,1000000000,1000,1000000,1000000,'DEMO',CURRENT_TIMESTAMP) ON CONFLICT (id) DO NOTHING"))
        c=db.get(DemoConfig,1)
    return c


def _record(db, source, dest, amount, kind, market_id=None):
    assert amount >= 0
    if amount == 0:return
    db.add(DemoEntry(txid='DEMO-'+secrets.token_hex(16),from_account=source,to_account=dest,amount_micros=amount,kind=kind,market_id=market_id))


def _wallet(db, uid):
    c=_config(db)
    # Both PostgreSQL and SQLite support ON CONFLICT DO NOTHING. Exactly one grant.
    r=db.execute(text('INSERT INTO v2138_demo_wallets (user_id,available_micros,created_at,updated_at) VALUES (:uid,:grant,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP) ON CONFLICT (user_id) DO NOTHING'), {'uid':uid,'grant':c.grant_micros})
    if r.rowcount:
        _record(db,'DEMO_ISSUANCE',f'DEMO_USER:{uid}',c.grant_micros,'WELCOME')
    db.flush()
    return db.scalar(select(DemoWallet).where(DemoWallet.user_id==uid).with_for_update())


def _settle_due(db):
    resolutions=db.scalars(select(DemoResolution)).all()
    settled=0
    for r in resolutions:
        m=db.get(PredictMarket,r.market_id)
        if not m:continue
        pool=db.scalar(select(DemoPool).where(DemoPool.market_id==m.id).with_for_update())
        if not pool or pool.settled_at:continue
        positions=db.scalars(select(DemoPosition).where(DemoPosition.market_id==m.id,DemoPosition.status=='OPEN')).all()
        total=pool.yes_micros+pool.no_micros
        if not positions:
            pool.settled_at=now();continue
        result=r.outcome
        winner_pool=pool.yes_micros if result=='YES' else pool.no_micros if result=='NO' else 0
        loser_pool=total-winner_pool
        if winner_pool<=0:result='VOID'
        paid=fees=0
        for p in positions:
            payout=fee=0
            if result=='VOID':payout=p.stake_micros;p.status='VOID'
            elif p.outcome==result:
                gross_profit=(loser_pool*p.stake_micros)//winner_pool
                fee=(gross_profit*pool.fee_bps)//10000
                payout=p.stake_micros+gross_profit-fee
                p.status='WON'
            else:p.status='LOST'
            p.payout_micros=payout;p.fee_micros=fee
            if payout:
                w=db.scalar(select(DemoWallet).where(DemoWallet.user_id==p.user_id).with_for_update())
                if not w:raise RuntimeError('Demo participant wallet missing')
                w.available_micros+=payout;w.updated_at=now()
                _record(db,f'DEMO_POOL:{m.id}',f'DEMO_USER:{p.user_id}',payout,'PAYOUT' if result!='VOID' else 'REFUND',m.id)
            paid+=payout;fees+=fee
        if fees:_record(db,f'DEMO_POOL:{m.id}','DEMO_FEE',fees,'FEE',m.id)
        dust=total-paid-fees
        if dust<0:raise RuntimeError('Demo pool settlement imbalance')
        if dust:_record(db,f'DEMO_POOL:{m.id}','DEMO_ROUNDING',dust,'ROUNDING',m.id)
        pool.settled_at=now();settled+=1
    return settled


def register_v2138_predict(app,current_user,get_db):
    router=APIRouter(prefix='/v2138/predict',tags=['Q Predict Demo / Real Locked'])

    @router.get('/home')
    def home(u:User=Depends(current_user),db:Session=Depends(get_db)):
        _settle_due(db)
        w=_wallet(db,u.id)
        rows=db.scalars(select(PredictMarket).where(PredictMarket.status=='LIVE').order_by(PredictMarket.close_at).limit(150)).all()
        rows=[m for m in rows if aware(m.close_at)>now()][:100]
        positions=db.scalars(select(DemoPosition).where(DemoPosition.user_id==u.id).order_by(DemoPosition.id.desc()).limit(100)).all()
        positions_by={}
        for p in positions:positions_by.setdefault(p.market_id,[]).append({'outcome':p.outcome,'stake':as_units(p.stake_micros),'payout':as_units(p.payout_micros),'status':p.status})
        pools={x.market_id:x for x in db.scalars(select(DemoPool).where(DemoPool.market_id.in_([m.id for m in rows]))).all()} if rows else {}
        markets=[{'id':m.id,'question':m.question,'category':m.category,'status':m.status,'close_at':m.close_at.isoformat(),'resolution_rule':m.resolution_rule,
                  'yes_pool':as_units(pools[m.id].yes_micros) if m.id in pools else 0,'no_pool':as_units(pools[m.id].no_micros) if m.id in pools else 0,
                  'my_positions':positions_by.get(m.id,[])} for m in rows]
        from .predict311 import enrich
        enrich(db,markets,True)
        pending=db.scalars(select(DemoPosition).where(DemoPosition.user_id==u.id,DemoPosition.status=='OPEN')).all()
        locked=sum(p.stake_micros for p in pending)
        ledger=db.scalars(select(DemoEntry).where((DemoEntry.from_account==f'DEMO_USER:{u.id}')|(DemoEntry.to_account==f'DEMO_USER:{u.id}')).order_by(DemoEntry.id.desc()).limit(25)).all()
        db.commit()
        return {'mode':'DEMO','unit':'DEMO_USDT','real_mode':'LOCKED','available':as_units(w.available_micros),'locked':as_units(locked),
                'markets':markets,'my_positions':[{'market_id':p.market_id,'outcome':p.outcome,'stake':as_units(p.stake_micros),'payout':as_units(p.payout_micros),'status':p.status} for p in positions],
                'history':[{'kind':x.kind,'amount':as_units(x.amount_micros),'direction':'IN' if x.to_account==f'DEMO_USER:{u.id}' else 'OUT','at':x.created_at.isoformat()} for x in ledger],
                'fee_percent':_config(db).profit_fee_bps/100}

    @router.post('/demo/stake')
    def demo_stake(body:StakeIn,u:User=Depends(current_user),db:Session=Depends(get_db)):
        amount=micros(body.amount)
        if amount>250*MICRO:raise HTTPException(422,'Maximum demo stake is 250 Demo USDT')
        w=_wallet(db,u.id)
        duplicate=db.scalar(select(DemoRequest).where(DemoRequest.user_id==u.id,DemoRequest.request_key==body.request_key))
        if duplicate:
            if duplicate.market_id!=body.market_id or duplicate.amount_micros!=amount or duplicate.outcome!=body.outcome:
                raise HTTPException(409,'An idempotency key cannot be reused for a different prediction')
            db.commit();return {'accepted':True,'duplicate':True,'available':as_units(w.available_micros)}
        m=db.scalar(select(PredictMarket).where(PredictMarket.id==body.market_id).with_for_update())
        if not m or m.status!='LIVE' or aware(m.close_at)<=now():raise HTTPException(409,'This demo market is not open')
        if amount>w.available_micros:raise HTTPException(409,'Insufficient Demo USDT')
        pool=db.scalar(select(DemoPool).where(DemoPool.market_id==m.id).with_for_update())
        if not pool:
            pool=DemoPool(market_id=m.id,yes_micros=0,no_micros=0,fee_bps=_config(db).profit_fee_bps);db.add(pool);db.flush()
        if pool.settled_at:raise HTTPException(409,'Market already settled')
        opposing=db.scalar(select(DemoPosition).where(DemoPosition.user_id==u.id,DemoPosition.market_id==m.id,DemoPosition.outcome!=body.outcome))
        if opposing and opposing.stake_micros>0:raise HTTPException(409,'You already selected the other outcome')
        p=db.scalar(select(DemoPosition).where(DemoPosition.user_id==u.id,DemoPosition.market_id==m.id,DemoPosition.outcome==body.outcome).with_for_update())
        if not p:
            p=DemoPosition(user_id=u.id,market_id=m.id,outcome=body.outcome,stake_micros=0);db.add(p)
        p.stake_micros+=amount
        if body.outcome=='YES':pool.yes_micros+=amount
        else:pool.no_micros+=amount
        w.available_micros-=amount;w.updated_at=now()
        _record(db,f'DEMO_USER:{u.id}',f'DEMO_POOL:{m.id}',amount,'STAKE',m.id)
        db.add(DemoRequest(user_id=u.id,request_key=body.request_key,market_id=m.id,amount_micros=amount,outcome=body.outcome))
        db.commit()
        return {'accepted':True,'duplicate':False,'available':as_units(w.available_micros)}

    @router.get('/admin/config')
    def admin_config(u:User=Depends(current_user),db:Session=Depends(get_db)):
        _require_admin(db,u,'READ')
        c=_config(db)
        db.commit()
        return {'requested_mode':c.requested_mode,'effective_mode':'DEMO','real_gate':'LOCKED_NOT_IMPLEMENTED',
                'demo_starting_credit':as_units(c.grant_micros),'profit_fee_percent':c.profit_fee_bps/100,
                'deposit_fee':as_units(c.deposit_fee_micros),'withdrawal_fee':as_units(c.withdrawal_fee_micros),
                'real_payments_available':False,'real_staking_available':False,'demo_available':True}

    @router.put('/admin/config')
    def save_config(body:ConfigIn,u:User=Depends(current_user),db:Session=Depends(get_db)):
        _require_admin(db,u,'FULL')
        c=_config(db)
        c.grant_micros=micros(body.grant)
        c.profit_fee_bps=int(Decimal(body.profit_fee_percent)*100)
        c.deposit_fee_micros=0 if body.deposit_fee==0 else micros(body.deposit_fee)
        c.withdrawal_fee_micros=0 if body.withdrawal_fee==0 else micros(body.withdrawal_fee)
        c.requested_mode='REAL_PENDING' if body.requested_mode=='REAL' else 'DEMO'
        c.updated_at=now()
        db.add(AdminAudit(admin_user_id=u.id,action='PREDICT_CONFIG',detail=f'REAL_REQUESTED={c.requested_mode}; demo={as_units(c.grant_micros)}; profit_bps={c.profit_fee_bps}'))
        db.commit()
        return admin_config(u,db)

    @router.post('/admin/settle-demo')
    def settle_demo(u:User=Depends(current_user),db:Session=Depends(get_db)):
        _require_admin(db,u,'WRITE')
        count=_settle_due(db);db.commit()
        return {'settled_demo_markets':count,'note':'Only markets already officially resolved or voided in the source market system can settle.'}

    @router.post('/admin/demo/markets/{market_id}/resolve')
    def resolve_demo(market_id:int,body:ResolveDemoIn,u:User=Depends(current_user),db:Session=Depends(get_db)):
        _require_admin(db,u,'FULL')
        m=db.get(PredictMarket,market_id)
        if not m:raise HTTPException(404,'Market not found')
        if aware(m.close_at)>now():raise HTTPException(409,'Cannot resolve a demo market before its scheduled close')
        if db.get(DemoResolution,market_id):raise HTTPException(409,'Demo result already recorded; resolution is immutable')
        # External evidence must be reviewed by the admin; this is NOT automatic settlement.
        db.add(DemoResolution(market_id=market_id,outcome=body.outcome,evidence=body.evidence.strip(),resolved_by=u.id))
        db.add(AdminAudit(admin_user_id=u.id,action='DEMO_RESOLVE',detail=f'market_id={market_id}; outcome={body.outcome}; evidence={body.evidence}'))
        db.flush();count=_settle_due(db);db.commit()
        return {'resolved':True,'settled_demo_markets':count}

    @router.get('/admin/demo/pending')
    def demo_pending(u:User=Depends(current_user),db:Session=Depends(get_db)):
        _require_admin(db,u,'READ')
        pools=db.scalars(select(DemoPool).where(DemoPool.settled_at.is_(None))).all()
        return [{'market_id':p.market_id,'question':db.get(PredictMarket,p.market_id).question,'closed':aware(db.get(PredictMarket,p.market_id).close_at)<=now(),
                 'yes_pool':as_units(p.yes_micros),'no_pool':as_units(p.no_micros)} for p in pools if db.get(PredictMarket,p.market_id)]

    @router.post('/real/deposit')
    @router.post('/real/withdraw')
    @router.post('/real/stake')
    def locked_real(u:User=Depends(current_user)):
        raise HTTPException(423,'Real USDT operation is locked: licensing, jurisdiction checks, regulated payment custody and independent security validation are not completed.')

    app.include_router(router)
