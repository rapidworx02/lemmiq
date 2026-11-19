"""LEMMIQ v2.13.11: controlled Q Predict Q redemption / manually verified USDT payout.

The Q balance is HELD when the request is created and is never sent to Q Economy.
No blockchain signing occurs here. Admin must transfer USDT from a separate external
wallet, then submit the outgoing tx hash; settlement verifies the actual token receipt.
Default OFF and allowlisted team-only until jurisdiction & custody approvals exist.
"""
from __future__ import annotations
import secrets
import os
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import DateTime, ForeignKey, Integer, BigInteger, String, select, func
from sqlalchemy.orm import Mapped, Session, mapped_column
from .database import Base
from .models import User
from .v28 import QPaymentOrder
from .v21310_predict_q import (Wallet, Treasury, Order, _team_ids, _team_gate,
   _admin, _wallet, _entry, _reference, _num, _address, _hash, _verify_transfer,
   _audit, now, value, MICRO, Q_SELL_BPS)

class SellOrder(Base):
    __tablename__='v21311_predict_q_sell_orders'
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    code:Mapped[str]=mapped_column(String(50),unique=True,index=True)
    user_id:Mapped[int]=mapped_column(ForeignKey('users.id'),index=True)
    network:Mapped[str]=mapped_column(String(12))
    destination:Mapped[str]=mapped_column(String(90))
    q_micros:Mapped[int]=mapped_column(BigInteger)
    reference_price_microusd:Mapped[int]=mapped_column(BigInteger)
    payout_usdt_micros:Mapped[int]=mapped_column(BigInteger)
    treasury_address:Mapped[str]=mapped_column(String(90))
    tx_hash:Mapped[str|None]=mapped_column(String(90),nullable=True,unique=True)
    status:Mapped[str]=mapped_column(String(16),default='PENDING')
    reviewer_id:Mapped[int|None]=mapped_column(Integer,nullable=True)
    notes:Mapped[str]=mapped_column(String(280),default='')
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
    updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class SellQuoteIn(BaseModel):
    amount_q:Decimal=Field(gt=0,le=100000)
    network:Literal['TRC20','BEP20']

class SellRequestIn(SellQuoteIn):
    destination:str=Field(min_length=34,max_length=90)

class CompleteIn(BaseModel):
    tx_hash:str=Field(min_length=64,max_length=66)

class RejectIn(BaseModel):
    reason:str=Field(min_length=8,max_length=240)

NOTICE=("Verification Required\n\nQ Predict Q wallets are fully separate from Q Economy.\n\n"
 "Buying Q, staking, selling Q and withdrawing USDT are available only to approved, verified users, "
 "subject to applicable authorization.\n\nYour account is not currently enabled for these services. "
 "Please contact LEMMIQ Support for eligibility information.")

def _sell_micro(price,q_micro):
    return (price*q_micro*(10000-Q_SELL_BPS))//(MICRO*10000)

def _json(row):
    return {'id':row.id,'code':row.code,'network':row.network,'destination':row.destination,
      'q_amount':value(row.q_micros),'reference_usdt_per_q':value(row.reference_price_microusd),
      'sell_discount_percent':5,'payout_usdt':value(row.payout_usdt_micros),
      'status':row.status,'tx_hash':row.tx_hash,'notes':row.notes,
      'created_at':row.created_at.isoformat(),'user_id':row.user_id}

def register_v21311_redeem(app,current_user,get_db):
    router=APIRouter(prefix='/v21311/redeem',tags=['Q Predict authorized withdrawal and quote'])

    @router.get('/status')
    def status(u:User=Depends(current_user)):
        eligible=u.id in _team_ids()
        return {'eligible':eligible,'buy_allowed':eligible and os.getenv('LEMMIQ_PREDICT_Q_PAYMENTS_ENABLED','false').lower()=='true',
          'sell_allowed':eligible and os.getenv('LEMMIQ_PREDICT_Q_WITHDRAWALS_ENABLED','false').lower()=='true',
          'wagering_allowed':eligible and os.getenv('LEMMIQ_PREDICT_Q_WAGERING_ENABLED','false').lower()=='true',
          'networks':[{'id':'TRC20','label':'USDT - TRON (TRC20)'},{'id':'BEP20','label':'USDT - BNB Smart Chain (BEP20)'}],
          'verification_message':NOTICE,'support_username':'lemmiq','supports_actual_withdrawal':True}

    @router.post('/quote')
    def quote(body:SellQuoteIn,u:User=Depends(current_user),db:Session=Depends(get_db)):
        price=_reference(db); q=_num(body.amount_q)
        payout=_sell_micro(price,q)
        return {'q_amount':value(q),'reference_usdt_per_q':value(price),
          'sell_usdt_per_q':value(price)*0.95,'sell_discount_percent':5,
          'payout_usdt':value(payout),'network':body.network,
          'notice':'Indicative quote. Rate is snapshotted when an authorized withdrawal request is created.'}

    @router.get('/mine')
    def mine(u:User=Depends(current_user),db:Session=Depends(get_db)):
        rows=db.scalars(select(SellOrder).where(SellOrder.user_id==u.id).order_by(SellOrder.id.desc()).limit(50)).all()
        return {'requests':[_json(x) for x in rows]}

    @router.post('/requests')
    def create(body:SellRequestIn,u:User=Depends(current_user),db:Session=Depends(get_db)):
        _team_gate(u,'WITHDRAWALS')
        destination=_address(body.network,body.destination)
        treasury=db.get(Treasury,body.network)
        if not treasury or not treasury.active:raise HTTPException(409,'Q Predict payout treasury not configured')
        if destination.lower()==treasury.address.lower():raise HTTPException(422,'Destination cannot be the treasury')
        price=_reference(db);q=_num(body.amount_q);payout=_sell_micro(price,q)
        if payout<2*MICRO:raise HTTPException(422,'Minimum payout is 2 USDT')
        wallet=_wallet(db,u.id)
        if wallet.available<q:raise HTTPException(409,'Insufficient Q Predict Q balance')
        wallet.available-=q;wallet.updated_at=now()
        order=SellOrder(code='PQS-'+secrets.token_hex(10).upper(),user_id=u.id,
          network=body.network,destination=destination,q_micros=q,reference_price_microusd=price,
          payout_usdt_micros=payout,treasury_address=treasury.address)
        db.add(order);db.flush()
        _entry(db,f'USER:{u.id}',f'REDEMPTION_ESCROW:{order.id}',q,'SELL_Q_HOLD',order.code)
        db.commit();return _json(order)

    @router.get('/admin/requests')
    def admin_list(u:User=Depends(current_user),db:Session=Depends(get_db)):
        _admin(db,u)
        rows=db.scalars(select(SellOrder).order_by(SellOrder.id.desc()).limit(150)).all()
        return {'requests':[_json(x) for x in rows]}

    @router.post('/admin/requests/{request_id}/reject')
    def reject(request_id:int,body:RejectIn,u:User=Depends(current_user),db:Session=Depends(get_db)):
        _admin(db,u)
        row=db.scalar(select(SellOrder).where(SellOrder.id==request_id).with_for_update())
        if not row or row.status!='PENDING':raise HTTPException(409,'Only pending withdrawals can be rejected')
        w=_wallet(db,row.user_id);w.available+=row.q_micros;w.updated_at=now()
        _entry(db,f'REDEMPTION_ESCROW:{row.id}',f'USER:{row.user_id}',row.q_micros,'SELL_Q_REFUND',row.code)
        row.status='REJECTED';row.notes=body.reason.strip();row.reviewer_id=u.id;row.updated_at=now()
        _audit(db,u.id,'REJECT_SELL',{'request_id':row.id,'reason':row.notes})
        db.commit();return _json(row)

    @router.post('/admin/requests/{request_id}/complete')
    def complete(request_id:int,body:CompleteIn,u:User=Depends(current_user),db:Session=Depends(get_db)):
        _admin(db,u)
        row=db.scalar(select(SellOrder).where(SellOrder.id==request_id).with_for_update())
        if not row or row.status!='PENDING':raise HTTPException(409,'Only pending withdrawal can be confirmed')
        h=_hash(row.network,body.tx_hash)
        if db.scalar(select(SellOrder.id).where(SellOrder.tx_hash==h)):
            raise HTTPException(409,'Transaction already claimed by another withdrawal')
        if db.scalar(select(Order.id).where(Order.tx_hash==h)) or db.scalar(select(QPaymentOrder.id).where(func.lower(QPaymentOrder.submitted_tx_hash)==h)):
            raise HTTPException(409,'Transaction already claimed as a deposit')
        proof=_verify_transfer(SimpleNamespace(network=row.network,tx_hash=h,sender_address=row.treasury_address,
                             receiving_address=row.destination,expected_usdt_micros=row.payout_usdt_micros))
        row.status='PAID';row.tx_hash=h;row.reviewer_id=u.id;row.updated_at=now()
        _entry(db,f'REDEMPTION_ESCROW:{row.id}','Q_PREDICT_REDEMPTION',row.q_micros,'SELL_Q_COMPLETE',row.code)
        _audit(db,u.id,'COMPLETE_SELL',{'request_id':row.id,'tx_hash':h,'payout_usdt':value(row.payout_usdt_micros),**proof})
        db.commit();return _json(row)

    app.include_router(router)
