# V21311_RELEASE: verified user notices and independent redemption companion
"""LEMMIQ V2.13.10 - isolated Q Predict wallet and USDT purchase orders.

This is a controlled-development module, NOT a globally enabled wagering launch.
- Q Predict balances NEVER move to or from Q Economy wallets.
- All on-chain transfers are signed outside this service; no private keys stored here.
- Real USDT purchases and Q wagering require explicit environment permission AND
  an allowlisted team account. Public access requires separate regulated launch work.
- Demo v2138 balances and legacy Q Predict positions remain untouched.
"""
from __future__ import annotations
import hashlib
import json
import os
import re
import secrets
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_CEILING
from typing import Literal
import requests
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func, select
from sqlalchemy.orm import Mapped, Session, mapped_column
from .database import Base
from .models import User
from .v28 import QEconomyConfig, QPaymentWallet, QPaymentOrder
from .v29 import PredictMarket, _require_admin

MICRO=1_000_000
TRANSFER_TOPIC='0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef'
BSC_USDT='0x55d398326f99059ff775485246999027b3197955'
TRON_USDT='TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t'
BSC_CHAIN=56
MIN_BSC_CONFIRMATIONS=20
MIN_TRON_CONFIRMATIONS=20
Q_BUY_BPS=500
Q_SELL_BPS=500  # reserved for the future authorized sell flow
Q_WIN_FEE_BPS=1000


def now():return datetime.now(timezone.utc)
def value(n):return float(Decimal(int(n))/Decimal(MICRO))
def fmt_decimal(n):return str((Decimal(int(n))/Decimal(MICRO)).quantize(Decimal('0.000001')))
def _num(v, max_value=100000):
    try:
        d=Decimal(str(v))
        if not d.is_finite() or d<=0 or d>max_value or d != d.quantize(Decimal('0.000001')):raise ValueError()
        return int(d*MICRO)
    except (InvalidOperation,TypeError,ValueError):raise HTTPException(422,'Enter a positive amount with at most six decimal places')

def _team_ids():return {int(x) for x in os.getenv('LEMMIQ_PREDICT_Q_TEAM_IDS','').split(',') if x.strip().isdigit()}
def _real_cricket312():
    from .cricket312 import real_cricket_allowed
    return real_cricket_allowed()
def _team_gate(u,feature):
    if u.id not in _team_ids():raise HTTPException(403,'Q Predict real-value functions are restricted to approved, verified users')
    if os.getenv('LEMMIQ_PREDICT_Q_'+feature+'_ENABLED','false').lower()!='true':
        raise HTTPException(423,feature.lower()+' has not been enabled for the controlled test')
def _admin(db,u):
    if _require_admin(db,u,'FULL','Q_PREDICT') != 'MASTER_ADMIN':raise HTTPException(403,'Master Admin required')

def _b58decode(address):
    alphabet='123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
    if not 33<=len(address)<=35 or any(c not in alphabet for c in address):raise HTTPException(422,'Invalid TRON address')
    n=0
    for c in address:n=n*58+alphabet.index(c)
    data=n.to_bytes((n.bit_length()+7)//8,'big')
    data=b'\0'*(len(address)-len(address.lstrip('1')))+data
    if len(data)!=25 or data[0]!=0x41 or hashlib.sha256(hashlib.sha256(data[:-4]).digest()).digest()[:4]!=data[-4:]:
        raise HTTPException(422,'Invalid TRON address checksum')
    return data[1:21].hex()

def _address(net,addr):
    addr=str(addr or '').strip()
    if net=='BEP20':
        if not re.fullmatch(r'0x[0-9a-fA-F]{40}',addr):raise HTTPException(422,'Invalid BSC address')
        return addr.lower()
    if net=='TRC20':
        _b58decode(addr);return addr
    raise HTTPException(422,'Supported networks: TRC20, BEP20')

def _hash(net,tx):
    raw=str(tx).strip()
    if net=='BEP20' and not re.fullmatch(r'0x[0-9a-fA-F]{64}',raw):raise HTTPException(422,'Invalid BSC transaction hash')
    if net=='TRC20' and not re.fullmatch(r'[0-9a-fA-F]{64}',raw):raise HTTPException(422,'Invalid TRON transaction ID')
    return raw.lower()

class Wallet(Base):
    __tablename__='v21310_predict_q_wallets'
    user_id:Mapped[int]=mapped_column(ForeignKey('users.id'),primary_key=True)
    available:Mapped[int]=mapped_column(BigInteger,default=0)
    updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class Treasury(Base):
    __tablename__='v21310_predict_q_treasury'
    network:Mapped[str]=mapped_column(String(12),primary_key=True)
    address:Mapped[str]=mapped_column(String(80))
    active:Mapped[bool]=mapped_column(Boolean,default=True)
    updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class Order(Base):
    __tablename__='v21310_predict_q_buy_orders'
    id:Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True)
    code:Mapped[str]=mapped_column(String(40),unique=True,index=True)
    user_id:Mapped[int]=mapped_column(ForeignKey('users.id'),index=True)
    network:Mapped[str]=mapped_column(String(12))
    q_micros:Mapped[int]=mapped_column(BigInteger)
    reference_price_microusd:Mapped[int]=mapped_column(BigInteger)
    buy_bps:Mapped[int]=mapped_column(Integer,default=Q_BUY_BPS)
    expected_usdt_micros:Mapped[int]=mapped_column(BigInteger)
    receiving_address:Mapped[str]=mapped_column(String(80))
    sender_address:Mapped[str]=mapped_column(String(80))
    tx_hash:Mapped[str|None]=mapped_column(String(80),unique=True,nullable=True)
    status:Mapped[str]=mapped_column(String(20),default='CREATED',index=True)
    expires_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
    reviewer_id:Mapped[int|None]=mapped_column(Integer,nullable=True)
    notes:Mapped[str]=mapped_column(String(260),default='')
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
    updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class Entry(Base):
    __tablename__='v21310_predict_q_ledger'
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    txid:Mapped[str]=mapped_column(String(70),unique=True,index=True)
    source:Mapped[str]=mapped_column(String(90))
    destination:Mapped[str]=mapped_column(String(90))
    amount_micros:Mapped[int]=mapped_column(BigInteger)
    unit:Mapped[str]=mapped_column(String(12),default='Q')
    kind:Mapped[str]=mapped_column(String(40))
    reference:Mapped[str]=mapped_column(String(60))
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class Position(Base):
    __tablename__='v21310_predict_q_positions'
    __table_args__=(UniqueConstraint('user_id','market_id','outcome',name='uq_21310_predict_q_position'),)
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    user_id:Mapped[int]=mapped_column(ForeignKey('users.id'),index=True)
    market_id:Mapped[int]=mapped_column(ForeignKey('q_predict_markets.id'),index=True)
    outcome:Mapped[str]=mapped_column(String(6))
    stake_micros:Mapped[int]=mapped_column(BigInteger,default=0)
    payout_micros:Mapped[int]=mapped_column(BigInteger,default=0)
    fee_micros:Mapped[int]=mapped_column(BigInteger,default=0)
    status:Mapped[str]=mapped_column(String(12),default='OPEN')
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class Pool(Base):
    __tablename__='v21310_predict_q_pools'
    market_id:Mapped[int]=mapped_column(ForeignKey('q_predict_markets.id'),primary_key=True)
    yes_micros:Mapped[int]=mapped_column(BigInteger,default=0)
    no_micros:Mapped[int]=mapped_column(BigInteger,default=0)
    fee_bps:Mapped[int]=mapped_column(Integer,default=Q_WIN_FEE_BPS)
    settled_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)

class RequestId(Base):
    __tablename__='v21310_predict_q_request_keys'
    __table_args__=(UniqueConstraint('user_id','request_key',name='uq_21310_predict_q_request_key'),)
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    user_id:Mapped[int]=mapped_column(ForeignKey('users.id'))
    request_key:Mapped[str]=mapped_column(String(64))
    market_id:Mapped[int]=mapped_column(Integer)
    amount_micros:Mapped[int]=mapped_column(BigInteger)
    outcome:Mapped[str]=mapped_column(String(6))

class Resolution(Base):
    __tablename__='v21310_predict_q_resolutions'
    market_id:Mapped[int]=mapped_column(ForeignKey('q_predict_markets.id'),primary_key=True)
    outcome:Mapped[str]=mapped_column(String(6))
    evidence:Mapped[str]=mapped_column(String(500))
    admin_id:Mapped[int]=mapped_column(Integer)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class Audit(Base):
    __tablename__='v21310_predict_q_admin_audit'
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    admin_id:Mapped[int]=mapped_column(Integer)
    action:Mapped[str]=mapped_column(String(50))
    details_json:Mapped[str]=mapped_column(Text)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class QuoteIn(BaseModel):
    q_amount:Decimal=Field(gt=0,le=100000)
    network:Literal['TRC20','BEP20']
class BuySubmit(BaseModel):
    tx_hash:str=Field(min_length=64,max_length=66)
class TreasuryIn(BaseModel):
    address:str=Field(min_length=34,max_length=80)
    active:bool=True
class StakeIn(BaseModel):
    market_id:int=Field(gt=0)
    outcome:Literal['YES','NO']
    amount_q:Decimal=Field(gt=0,le=1000)
    request_key:str=Field(min_length=12,max_length=64,pattern=r'^[A-Za-z0-9_-]+$')
class SettleIn(BaseModel):
    outcome:Literal['YES','NO','VOID']
    evidence:str=Field(min_length=10,max_length=500)
class RejectIn(BaseModel):
    reason:str=Field(min_length=8,max_length=240)

def _wallet(db,uid):
    from sqlalchemy import text
    db.execute(text('INSERT INTO v21310_predict_q_wallets (user_id,available,updated_at) VALUES (:i,0,CURRENT_TIMESTAMP) ON CONFLICT (user_id) DO NOTHING'),{'i':uid})
    db.flush()
    return db.scalar(select(Wallet).where(Wallet.user_id==uid).with_for_update())

def _entry(db,src,dst,n,kind,reference,unit='Q'):
    if n<0:raise RuntimeError('Negative ledger movement')
    if n:db.add(Entry(txid='PQ-'+secrets.token_hex(16),source=src,destination=dst,amount_micros=n,kind=kind,reference=reference,unit=unit))

def _audit(db,uid,action,obj):db.add(Audit(admin_id=uid,action=action,details_json=json.dumps(obj,sort_keys=True)))

def _reference(db):
    cfg=db.get(QEconomyConfig,1)
    price=int(cfg.q_price_microusd) if cfg else 0
    if price<=0:raise HTTPException(503,'Q Economy reference price is not configured')
    return price

def _quote(price,q_micros):
    # Reference is micro-USD/Q; charge a fixed +5% buy premium and round UP
    # to six USDT decimals, so orders cannot underpay through rounding.
    return (price*q_micros*(10_000+Q_BUY_BPS)+(MICRO*10_000)-1)//(MICRO*10_000)

def _quote_json(price,q_micros,network):
    micro=_quote(price,q_micros)
    return {'network':network,'q_amount':value(q_micros),'reference_usdt_per_q':value(price),
            'buy_usdt_per_q':value(price)*(1+Q_BUY_BPS/10000),
            'buy_premium_percent':Q_BUY_BPS/100,'expected_usdt':value(micro),
            'sell_discount_percent':Q_SELL_BPS/100,
            'disclosure':'Quote locks the rate for 15 minutes once an order is created. Q Predict Q cannot transfer to Q Economy.'}

def _order_json(o):
    return {'id':o.id,'code':o.code,'network':o.network,'q_amount':value(o.q_micros),
            'reference_usdt_per_q':value(o.reference_price_microusd),'buy_premium_percent':o.buy_bps/100,
            'expected_usdt':value(o.expected_usdt_micros),'receiving_address':o.receiving_address,
            'sender_address':o.sender_address,'tx_hash':o.tx_hash,'status':o.status,
            'user_id':o.user_id,'expires_at':o.expires_at.isoformat(),'created_at':o.created_at.isoformat(),
            'notes':o.notes}

def _rpc(method,params):
    url=os.getenv('LEMMIQ_PREDICT_Q_BSC_RPC_URL','https://bsc-dataseed-public.bnbchain.org').strip()
    from urllib.parse import urlparse
    p=urlparse(url)
    if p.scheme!='https' or p.username or p.password or not p.hostname or p.fragment:
        raise HTTPException(503,'Trusted HTTPS BSC RPC URL required')
    try:
        r=requests.post(url,json={'jsonrpc':'2.0','id':1,'method':method,'params':params},timeout=12,allow_redirects=False)
        r.raise_for_status();obj=r.json()
        if not isinstance(obj,dict) or 'error' in obj or 'result' not in obj:raise ValueError('Bad JSON RPC reply')
        return obj['result']
    except (requests.RequestException,ValueError):raise HTTPException(503,'BSC proof unavailable; no Q credited')

def _tron_post(path,payload):
    host=os.getenv('LEMMIQ_PREDICT_Q_TRON_API_BASE','https://api.trongrid.io').rstrip('/')
    from urllib.parse import urlparse
    url=urlparse(host)
    if url.scheme!='https' or not url.hostname or url.username or url.password or url.path not in ('','/') or url.query or url.fragment:
        raise HTTPException(503,'Trusted HTTPS TRON full-node API required')
    try:
        headers={'Content-Type':'application/json'}
        key=os.getenv('LEMMIQ_PREDICT_Q_TRONGRID_API_KEY','').strip()
        if key:headers['TRON-PRO-API-KEY']=key
        res=requests.post(host+path,json=payload,headers=headers,timeout=12,allow_redirects=False)
        res.raise_for_status();data=res.json()
        if not isinstance(data,dict):raise ValueError('Malformed TRON response')
        return data
    except (requests.RequestException,ValueError):raise HTTPException(503,'TRON proof unavailable; no Q credited')

def _verify_bsc(o):
    if int(_rpc('eth_chainId',[]),16)!=BSC_CHAIN:raise HTTPException(503,'Wrong BSC chain')
    receipt=_rpc('eth_getTransactionReceipt',[o.tx_hash])
    if not isinstance(receipt,dict) or receipt.get('status')!='0x1':raise HTTPException(409,'BSC transaction not confirmed/successful')
    height=int(_rpc('eth_blockNumber',[]),16);block=int(receipt.get('blockNumber') or '0x0',16)
    if block<=0 or height-block+1<MIN_BSC_CONFIRMATIONS:raise HTTPException(409,'BSC transaction needs more confirmations')
    matched=[]
    for log in receipt.get('logs',[]):
        topics=log.get('topics') or []
        if str(log.get('address','')).lower()!=BSC_USDT or len(topics)!=3 or str(topics[0]).lower()!=TRANSFER_TOPIC:continue
        sender='0x'+str(topics[1])[-40:].lower();receiver='0x'+str(topics[2])[-40:].lower()
        try:amount=int(log['data'],16)
        except (KeyError,ValueError,TypeError):continue
        if sender==o.sender_address and receiver==o.receiving_address and amount==o.expected_usdt_micros*(10**12):matched.append(log)
    if len(matched)!=1:raise HTTPException(409,'BSC transaction does not contain one matching USDT transfer')
    return {'chain':'BSC','block':block,'confirmations':height-block+1}

def _verify_tron(o):
    # Solidity node serves only confirmed transactions, not mempool transactions.
    info=_tron_post('/walletsolidity/gettransactioninfobyid',{'value':o.tx_hash})
    if (info.get('receipt') or {}).get('result')!='SUCCESS' or not info.get('id'):
        raise HTTPException(409,'TRON transaction has no confirmed successful receipt')
    block=int(info.get('blockNumber') or 0)
    nowblock=_tron_post('/wallet/getnowblock',{})
    height=int(((nowblock.get('block_header') or {}).get('raw_data') or {}).get('number') or 0)
    if block<=0 or height-block+1<MIN_TRON_CONFIRMATIONS:raise HTTPException(409,'TRON transaction needs more confirmations')
    contract=_b58decode(TRON_USDT)
    sender=_b58decode(o.sender_address)
    recipient=_b58decode(o.receiving_address)
    matched=[]
    for event in info.get('log') or []:
        addr=str(event.get('address') or '').lower().removeprefix('0x').removeprefix('41')
        topics=event.get('topics') or []
        if addr!=contract or len(topics)!=3 or '0x'+str(topics[0]).lower().removeprefix('0x')!=TRANSFER_TOPIC:continue
        sender_log=str(topics[1]).lower()[-40:];receiver_log=str(topics[2]).lower()[-40:]
        try:amount=int(str(event['data']).removeprefix('0x'),16)
        except (KeyError,ValueError,TypeError):continue
        if sender_log==sender and receiver_log==recipient and amount==o.expected_usdt_micros:matched.append(event)
    if len(matched)!=1:raise HTTPException(409,'TRON transaction does not contain one matching USDT transfer')
    return {'chain':'TRON','block':block,'confirmations':height-block+1}

def _verify_transfer(o):
    if o.network=='BEP20':return _verify_bsc(o)
    if o.network=='TRC20':return _verify_tron(o)
    raise HTTPException(422,'Unsupported network')

def _classification(m):
    if m.category!='SPORTS':return ''
    try:cfg=json.loads(m.source_config_json or '{}')
    except Exception:cfg={}
    if str(m.template_code or '')=='CRICKET_V312_INTL_WIN':return 'INTERNATIONAL'
    if str(m.template_code or '').startswith('CRICKET_V21314_') and cfg.get('format')=='TEST':return 'INTERNATIONAL'
    series=str(cfg.get('series') or '').lower()
    leagues=('premier league','ipl','big bash','bbl','psl','hundred','cpl','sa20','t20 blast','major league','global t20')
    if any(x in series for x in leagues):return 'LEAGUES'
    if any(x in series for x in ('international','world cup','asia cup','champions trophy','vs ')):return 'INTERNATIONAL'
    return 'DOMESTIC' if series else 'OTHER'

def _settle(db,m,pool,r):
    if pool.settled_at:return
    positions=db.scalars(select(Position).where(Position.market_id==m.id,Position.status=='OPEN')).all()
    total=pool.yes_micros+pool.no_micros
    winning=pool.yes_micros if r.outcome=='YES' else pool.no_micros if r.outcome=='NO' else 0
    result=r.outcome if winning>0 else 'VOID'
    payout_total=fee_total=0
    for pos in positions:
        pay=fee=0
        if result=='VOID':pay=pos.stake_micros;pos.status='VOID'
        elif pos.outcome==result:
            gross=(total-winning)*pos.stake_micros//winning
            fee=gross*pool.fee_bps//10000
            pay=pos.stake_micros+gross-fee;pos.status='WON'
        else:pos.status='LOST'
        pos.payout_micros=pay;pos.fee_micros=fee;payout_total+=pay;fee_total+=fee
        if pay:
            wallet=_wallet(db,pos.user_id);wallet.available+=pay;wallet.updated_at=now()
            _entry(db,f'POOL:{m.id}',f'USER:{pos.user_id}',pay,'WIN' if pos.status=='WON' else 'REFUND',str(m.id))
    if fee_total:_entry(db,f'POOL:{m.id}','PREDICT_FEE',fee_total,'WIN_PROFIT_FEE',str(m.id))
    dust=total-payout_total-fee_total
    if dust<0:raise RuntimeError('Unbalanced Q Predict pool')
    if dust:_entry(db,f'POOL:{m.id}','PREDICT_ROUNDING',dust,'ROUNDING',str(m.id))
    pool.settled_at=now()


def register_v21310_predict_q(app,current_user,get_db):
    router=APIRouter(prefix='/v21310/predict',tags=['Q Predict independent Q wallet / gated real USDT'])

    @router.get('/ui-config')
    def ui_config_v300(u:User=Depends(current_user),db:Session=Depends(get_db)):
        # Read-only, no wallet creation or trading data. Existing admin rules remain authoritative.
        try:
            _admin(db,u)
            master=True
        except HTTPException as e:
            if e.status_code!=403:raise
            master=False
        try:price=value(_reference(db))
        except HTTPException:price=None
        wallet = db.get(Wallet, u.id)
        return {'reference_usdt_per_q':price,'master_admin':master,
                'available_q': value(wallet.available) if wallet else 0.0}

    @router.get('/home')
    def home(u:User=Depends(current_user),db:Session=Depends(get_db)):
        w=_wallet(db,u.id)
        price=_reference(db)
        markets=db.scalars(select(PredictMarket).where(PredictMarket.status=='LIVE').order_by(PredictMarket.close_at).limit(150)).all()
        markets=[m for m in markets if (m.close_at.replace(tzinfo=timezone.utc) if not m.close_at.tzinfo else m.close_at)>now()
                 and not str(m.template_code or '').startswith('CRICKET_V21314_') and (not str(m.template_code or '').startswith('CRICKET_V312_INTL_WIN') or _real_cricket312())]  # Demo-only cricket-statistics markets
        positions=db.scalars(select(Position).where(Position.user_id==u.id).order_by(Position.id.desc()).limit(100)).all()
        from sqlalchemy import func
        locked=db.scalar(select(func.coalesce(func.sum(Position.stake_micros),0)).where(Position.user_id==u.id,Position.status=='OPEN')) or 0
        entries=db.scalars(select(Entry).where((Entry.source==f'USER:{u.id}')|(Entry.destination==f'USER:{u.id}')).order_by(Entry.id.desc()).limit(60)).all()
        orders=db.scalars(select(Order).where(Order.user_id==u.id).order_by(Order.id.desc()).limit(40)).all()
        from .predict311 import enrich
        cards=enrich(db,[{'id':m.id,'category':m.category,'subcategory':_classification(m),'question':m.question,'status':m.status,'close_at':m.close_at.isoformat(),'rule':m.resolution_rule} for m in markets[:100]],False) if u.id in _team_ids() else []
        db.commit()
        return {'verified_access':u.id in _team_ids(),'mode':'PREDICT_Q','available_q':value(w.available),'locked_q':value(locked),'reference_usdt_per_q':value(price),
            'buy_usdt_per_q':value(price)*1.05,'sell_usdt_per_q':value(price)*0.95,
            'payments_enabled':os.getenv('LEMMIQ_PREDICT_Q_PAYMENTS_ENABLED','false').lower()=='true' and u.id in _team_ids(),
            'wagering_enabled':os.getenv('LEMMIQ_PREDICT_Q_WAGERING_ENABLED','false').lower()=='true' and u.id in _team_ids(),
            'notice':'Purchases and stakes are available only to approved, verified users, subject to applicable authorization.',
            'wallet_activity':[{'kind':x.kind,'amount_q':value(x.amount_micros),'direction':'IN' if x.destination==f'USER:{u.id}' else 'OUT','at':x.created_at.isoformat()} for x in entries],
            'orders':[_order_json(o) for o in orders],
            'positions':[{'id':p.id,'market_id':p.market_id,'outcome':p.outcome,'stake_q':value(p.stake_micros),'payout_q':value(p.payout_micros),'status':p.status} for p in positions],
            'markets':cards}

    @router.get('/treasury')
    def public_treasury(u:User=Depends(current_user),db:Session=Depends(get_db)):
        # The addresses are shown only to eligible internal team testers to prevent
        # unsolicited payments before the wallet service has been authorized.
        active=u.id in _team_ids() and os.getenv('LEMMIQ_PREDICT_Q_PAYMENTS_ENABLED','false').lower()=='true'
        rows=db.scalars(select(Treasury).where(Treasury.active.is_(True))).all() if active else []
        return {'payments_enabled':active,'networks':[{'network':x.network,'address':x.address} for x in rows],
                'available_networks':['TRC20','BEP20']}

    @router.post('/quote')
    def quote(body:QuoteIn,u:User=Depends(current_user),db:Session=Depends(get_db)):
        return _quote_json(_reference(db),_num(body.q_amount),body.network)

    @router.post('/buy/orders')
    def create(body:QuoteIn,u:User=Depends(current_user),db:Session=Depends(get_db)):
        _team_gate(u,'PAYMENTS')
        vault=db.get(Treasury,body.network)
        if not vault or not vault.active:raise HTTPException(409,'Admin receiving wallet not configured for this network')
        price=_reference(db);q_units=_num(body.q_amount)
        fee=_quote(price,q_units)
        if fee<1_000_000:raise HTTPException(422,'Minimum purchase: 1 USDT')
        order=Order(code='PQ-'+secrets.token_hex(10).upper(),user_id=u.id,network=body.network,
            q_micros=q_units,reference_price_microusd=price,buy_bps=Q_BUY_BPS,
            expected_usdt_micros=fee,receiving_address=vault.address,sender_address='',
            expires_at=now()+timedelta(minutes=15),status='CREATED')
        db.add(order);db.commit();db.refresh(order)
        return _order_json(order)

    @router.post('/buy/orders/{order_id}/submit')
    def submit(order_id:int,body:BuySubmit,u:User=Depends(current_user),db:Session=Depends(get_db)):
        _team_gate(u,'PAYMENTS')
        order=db.scalar(select(Order).where(Order.id==order_id).with_for_update())
        if not order or order.user_id!=u.id:raise HTTPException(404,'Purchase order not found')
        if order.status!='CREATED':raise HTTPException(409,'Order already submitted or processed')
        expiry=order.expires_at.replace(tzinfo=timezone.utc) if order.expires_at.tzinfo is None else order.expires_at
        if now()>expiry:
            raise HTTPException(409,'Quote expired. Contact support before making a payment.')
        if not order.sender_address:
            raise HTTPException(409,'Save the sending wallet address before submitting your transfer')
        h=_hash(order.network,body.tx_hash)
        if db.scalar(select(Order.id).where(Order.tx_hash==h)):raise HTTPException(409,'Transaction already claimed')
        if db.scalar(select(QPaymentOrder.id).where(func.lower(QPaymentOrder.submitted_tx_hash)==h)):
            raise HTTPException(409,'Transaction already used for a Q Economy payment')
        order.tx_hash=h;order.status='PENDING';order.updated_at=now()
        db.commit();return _order_json(order)

    @router.post('/buy/orders/{order_id}/sender')
    def sender_address(order_id:int,body:TreasuryIn,u:User=Depends(current_user),db:Session=Depends(get_db)):
        _team_gate(u,'PAYMENTS')
        order=db.scalar(select(Order).where(Order.id==order_id).with_for_update())
        if not order or order.user_id!=u.id:raise HTTPException(404,'Purchase order not found')
        if order.status!='CREATED':raise HTTPException(409,'Set sender before submitting payment proof')
        sender=_address(order.network,body.address)
        if sender==order.receiving_address:raise HTTPException(409,'Sender and treasury must differ')
        order.sender_address=sender;db.commit();return _order_json(order)

    @router.post('/stake')
    def stake(body:StakeIn,u:User=Depends(current_user),db:Session=Depends(get_db)):
        _team_gate(u,'WAGERING')
        amount=_num(body.amount_q,1000)
        key=db.scalar(select(RequestId).where(RequestId.user_id==u.id,RequestId.request_key==body.request_key))
        if key:
            if key.market_id!=body.market_id or key.amount_micros!=amount or key.outcome!=body.outcome:raise HTTPException(409,'Request key conflict')
            return {'accepted':True,'duplicate':True}
        m=db.scalar(select(PredictMarket).where(PredictMarket.id==body.market_id).with_for_update())
        if not m or m.status!='LIVE' or (m.close_at.replace(tzinfo=timezone.utc) if m.close_at.tzinfo is None else m.close_at)<=now():
            raise HTTPException(409,'Market closed')
        if str(m.template_code or '').startswith('CRICKET_V21314_'):
            raise HTTPException(423,'Cricket performance markets are Demo-only until authorised and independently verified')
        if str(m.template_code or '').startswith('CRICKET_V21314_'):
            raise HTTPException(423,'Legacy cricket statistics remain Demo-only')
        if str(m.template_code or '')=='CRICKET_V312_INTL_WIN' and not _real_cricket312():
            raise HTTPException(423,'Real Q cricket staking requires verified account, authorised operator and an enabled cricket licence gate')
        if db.get(Resolution,m.id):raise HTTPException(409,'Result already recorded')
        w=_wallet(db,u.id)
        if amount>w.available:raise HTTPException(409,'Insufficient Q Predict Q')
        opposite=db.scalar(select(Position).where(Position.market_id==m.id,Position.user_id==u.id,Position.outcome!=body.outcome))
        if opposite and opposite.stake_micros:raise HTTPException(409,'Opposite side already selected')
        pool=db.scalar(select(Pool).where(Pool.market_id==m.id).with_for_update())
        if not pool:pool=Pool(market_id=m.id);db.add(pool);db.flush()
        if pool.settled_at:raise HTTPException(409,'Already settled')
        p=db.scalar(select(Position).where(Position.market_id==m.id,Position.user_id==u.id,Position.outcome==body.outcome).with_for_update())
        if not p:p=Position(user_id=u.id,market_id=m.id,outcome=body.outcome,stake_micros=0);db.add(p)
        p.stake_micros+=amount
        if body.outcome=='YES':pool.yes_micros+=amount
        else:pool.no_micros+=amount
        w.available-=amount;w.updated_at=now()
        db.add(RequestId(user_id=u.id,request_key=body.request_key,market_id=m.id,amount_micros=amount,outcome=body.outcome))
        _entry(db,f'USER:{u.id}',f'POOL:{m.id}',amount,'STAKE',str(m.id))
        db.commit()
        return {'accepted':True,'market_id':m.id,'available_q':value(w.available)}

    @router.get('/admin')
    def admin(u:User=Depends(current_user),db:Session=Depends(get_db)):
        _admin(db,u)
        treasuries=db.scalars(select(Treasury)).all()
        orders=db.scalars(select(Order).order_by(Order.id.desc()).limit(120)).all()
        candidates=db.scalars(select(Pool).where(Pool.settled_at.is_(None)).order_by(Pool.market_id.desc()).limit(100)).all()
        return {'mode':'AUTHORIZED_USERS_ONLY','payments_enabled':os.getenv('LEMMIQ_PREDICT_Q_PAYMENTS_ENABLED','false').lower()=='true',
            'wagering_enabled':os.getenv('LEMMIQ_PREDICT_Q_WAGERING_ENABLED','false').lower()=='true',
            'team_ids':sorted(_team_ids()),'treasury':[{'network':t.network,'address':t.address,'active':t.active} for t in treasuries],
            'orders':[_order_json(x) for x in orders],
            'open_pools':[{'market_id':x.market_id,'pool_q':value(x.yes_micros+x.no_micros)} for x in candidates]}

    @router.put('/admin/treasury/{network}')
    def save_treasury(network:Literal['TRC20','BEP20'],body:TreasuryIn,u:User=Depends(current_user),db:Session=Depends(get_db)):
        _admin(db,u)
        address=_address(network,body.address)
        if db.scalar(select(QPaymentWallet.id).where(func.lower(QPaymentWallet.address)==address.lower(),QPaymentWallet.active.is_(True))):
            raise HTTPException(409,'Use a dedicated Q Predict treasury address, not the Q Economy address')
        existing=db.get(Treasury,network)
        if existing and existing.address!=address:
            pending=db.scalar(select(Order.id).where(Order.network==network,Order.status.in_(['CREATED','PENDING'])).limit(1))
            if pending:raise HTTPException(409,'Cannot rotate treasury with pending orders')
        if not existing:existing=Treasury(network=network,address=address,active=body.active);db.add(existing)
        else:existing.address=address;existing.active=body.active;existing.updated_at=now()
        _audit(db,u.id,'SET_TREASURY',{'network':network,'address':address,'active':body.active})
        db.commit();return {'ok':True,'network':network,'address':address,'active':body.active}

    @router.post('/admin/buy/{order_id}/approve')
    def approve(order_id:int,u:User=Depends(current_user),db:Session=Depends(get_db)):
        _admin(db,u)
        order=db.scalar(select(Order).where(Order.id==order_id).with_for_update())
        if not order:raise HTTPException(404,'Order not found')
        if order.status!='PENDING' or not order.tx_hash or not order.sender_address:raise HTTPException(409,'Order must have a verified sender and submitted transaction')
        proof=_verify_transfer(order) # fail closed if RPC is down
        if db.scalar(select(QPaymentOrder.id).where(func.lower(QPaymentOrder.submitted_tx_hash)==order.tx_hash)):
            raise HTTPException(409,'Transaction already claimed in Q Economy')
        w=_wallet(db,order.user_id);w.available+=order.q_micros;w.updated_at=now()
        _entry(db,'PREDICT_Q_ISSUANCE',f'USER:{order.user_id}',order.q_micros,'BUY_Q',order.code)
        order.status='APPROVED';order.reviewer_id=u.id;order.updated_at=now()
        _audit(db,u.id,'APPROVE_BUY',{'order_id':order.id,'tx_hash':order.tx_hash,**proof})
        db.commit();return _order_json(order)

    @router.post('/admin/buy/{order_id}/reject')
    def reject(order_id:int,body:RejectIn,u:User=Depends(current_user),db:Session=Depends(get_db)):
        _admin(db,u)
        order=db.scalar(select(Order).where(Order.id==order_id).with_for_update())
        if not order or order.status not in {'CREATED','PENDING'}:raise HTTPException(409,'Order cannot be rejected')
        order.status='REJECTED';order.notes=body.reason.strip();order.reviewer_id=u.id;order.updated_at=now()
        _audit(db,u.id,'REJECT_BUY',{'order_id':order.id,'reason':order.notes})
        db.commit();return _order_json(order)

    @router.post('/admin/markets/{market_id}/resolve')
    def resolve(market_id:int,body:SettleIn,u:User=Depends(current_user),db:Session=Depends(get_db)):
        _admin(db,u)
        market=db.scalar(select(PredictMarket).where(PredictMarket.id==market_id).with_for_update())
        if not market:raise HTTPException(404,'Market not found')
        if market.template_code=='CRICKET_V312_INTL_WIN':raise HTTPException(409,'Shared cricket markets must settle via the coordinated two-wallet result engine')
        close=market.close_at.replace(tzinfo=timezone.utc) if market.close_at.tzinfo is None else market.close_at
        if now()<close:raise HTTPException(409,'Cannot settle before market close')
        if db.get(Resolution,market_id):raise HTTPException(409,'Market already settled')
        pool=db.scalar(select(Pool).where(Pool.market_id==market_id).with_for_update())
        if not pool:raise HTTPException(409,'No Q Predict Q positions to settle')
        evidence=body.evidence.strip()
        if len(evidence)<10:raise HTTPException(422,'Official evidence required')
        r=Resolution(market_id=market_id,outcome=body.outcome,evidence=evidence,admin_id=u.id)
        db.add(r);_settle(db,market,pool,r)
        _audit(db,u.id,'RESOLVE_MARKET',{'market_id':market_id,'outcome':body.outcome,'evidence':evidence})
        db.commit();return {'ok':True,'market_id':market_id,'result':body.outcome}

    @router.post('/sell')
    def sell_locked(u:User=Depends(current_user)):
        raise HTTPException(423,'Q Predict Q redemption is not activated; treasury reserve, jurisdiction and withdrawal safeguards are required')

    app.include_router(router)
# V300_INSTALLED
# V302_INSTALLED
