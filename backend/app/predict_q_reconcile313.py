"""Q Predict optional-proof reconciliation, V3.1.2 hotfix.

An on-chain proof remains mandatory for wallet credit. For a hashless order the
Master Admin may discover a uniquely attributable confirmed transfer through
read-only public indexing APIs. Ambiguous matches fail closed. No private keys.
"""
from __future__ import annotations
import os
import re
import secrets
from datetime import datetime, timezone
from urllib.parse import urlparse

import requests
from fastapi import HTTPException
from sqlalchemy import select
from .v28 import QPaymentOrder
from .v21310_predict_q import (
    Order, TRON_USDT, BSC_USDT, BSC_CHAIN, TRANSFER_TOPIC,
    _address, _hash, _rpc, _b58decode,
)


def aware(dt):
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def checkout_amount(db, network, destination, base_micros):
    """Distinct micro-USDT payment amount (under 0.01 USDT extra).

    An exclusive destination address per order would be stronger; with the
    existing shared treasury this marker reduces order attribution collisions.
    Quote preview is approximate; checkout response always shows exact amount.
    """
    from datetime import timedelta
    cutoff=datetime.now(timezone.utc)-timedelta(days=1)
    existing=set(db.scalars(select(Order.expected_usdt_micros).where(
        Order.network==network,Order.receiving_address==destination,
        Order.created_at>=cutoff)).all())
    for _ in range(100):
        amount=int(base_micros)+secrets.randbelow(9999)+1
        if amount not in existing:return amount
    raise HTTPException(503,'Too many matching deposit references; retry later')


def payment_window(order):
    start=int((aware(order.created_at).timestamp()-20)*1000)
    end=int((aware(order.expires_at).timestamp()+20)*1000)
    return start, end


def extract_tron_events(data, treasury, expected, start_ms, end_ms):
    """Normalize indexed transfers. All attributes must match, including token."""
    if not isinstance(data, list):
        raise HTTPException(503, 'TRON deposit index returned an invalid response')
    hits=[]
    for e in data:
        if not isinstance(e,dict):continue
        token=(e.get('token_info') or {}).get('address','')
        if token!=TRON_USDT or e.get('to')!=treasury:continue
        try:
            quantity=int(e.get('value','-1'))
            timestamp=int(e.get('block_timestamp',0))
        except (ValueError,TypeError):continue
        tx=str(e.get('transaction_id','')).lower()
        if not (re.fullmatch(r'[0-9a-f]{64}',tx) and quantity==expected and start_ms<=timestamp<=end_ms):continue
        sender=str(e.get('from',''))
        try:_address('TRC20',sender)
        except HTTPException:continue
        hits.append({'tx_hash':tx,'sender_address':sender,'timestamp_ms':timestamp})
    return hits


def _tron_history(order):
    base=os.getenv('LEMMIQ_PREDICT_Q_TRON_API_BASE','https://api.trongrid.io').rstrip('/')
    url=urlparse(base)
    if url.scheme!='https' or not url.hostname or url.username or url.password or url.path not in ('','/') or url.query or url.fragment:
        raise HTTPException(503,'Trusted HTTPS TRON deposit index required')
    # Do not use user-controlled addresses/URLs. Q Predict's treasury is admin-configured.
    headers={}
    key=os.getenv('LEMMIQ_PREDICT_Q_TRONGRID_API_KEY','').strip()
    if key:headers['TRON-PRO-API-KEY']=key
    start,end=payment_window(order)
    params={'contract_address':TRON_USDT,'only_confirmed':'true','only_to':'true',
            'min_timestamp':start,'max_timestamp':end,'limit':200}
    results=[]
    for page in range(3):
        try:
            response=requests.get(base+'/v1/accounts/'+order.receiving_address+'/transactions/trc20',
                                  params=params,headers=headers,timeout=12,allow_redirects=False)
            response.raise_for_status()
            if len(response.content)>2_000_000:raise ValueError('Oversized response')
            payload=response.json()
            if not isinstance(payload,dict):raise ValueError('Invalid payload')
        except (requests.RequestException,ValueError) as exc:
            raise HTTPException(503,'TRON deposit index unavailable; no Q credited') from exc
        results.extend(extract_tron_events(payload.get('data'),order.receiving_address,
                                          int(order.expected_usdt_micros),start,end))
        next_cursor=(payload.get('meta') or {}).get('fingerprint')
        if not next_cursor:break
        if page==2:raise HTTPException(409,'TRON history is too busy for automatic matching; manual review required')
        params['fingerprint']=next_cursor
    return results


def extract_bsc_logs(logs,treasury,expected):
    """Decode matching USDT transfer logs; confirmation and time checked separately."""
    if not isinstance(logs,list):raise HTTPException(503,'BSC node returned invalid transfer logs')
    out=[]
    for event in logs:
        if not isinstance(event,dict) or event.get('removed'):continue
        topics=event.get('topics') or []
        if str(event.get('address','')).lower()!=BSC_USDT or len(topics)!=3:continue
        if str(topics[0]).lower()!=TRANSFER_TOPIC:continue
        if str(topics[2]).lower()[-40:]!=treasury.lower()[-40:]:continue
        try:amount=int(event['data'],16)
        except (KeyError,TypeError,ValueError):continue
        if amount!=expected*10**12:continue
        tx=str(event.get('transactionHash','')).lower()
        sender='0x'+str(topics[1])[-40:].lower()
        if not re.fullmatch(r'0x[0-9a-f]{64}',tx) or not re.fullmatch(r'0x[0-9a-f]{40}',sender):continue
        out.append({'tx_hash':tx,'sender_address':sender,'block':event.get('blockNumber')})
    return out


def _bsc_history(order):
    if int(_rpc('eth_chainId',[]),16)!=BSC_CHAIN:
        raise HTTPException(503,'Wrong BSC chain; no Q credited')
    current=int(_rpc('eth_blockNumber',[]),16)
    # Time-bounded query in manageable chunks. Very old orders require a manual
    # chain lookup rather than unreliable block-time extrapolation.
    age_seconds=(datetime.now(timezone.utc)-aware(order.created_at)).total_seconds()
    if age_seconds>3*3600:raise HTTPException(409,'Order is older than the automatic BSC scan window; manual review required')
    from_block=max(0,current-18000)
    recipient_topic='0x'+order.receiving_address.lower()[2:].rjust(64,'0')
    start,end=payment_window(order)
    hits=[]
    for lower in range(from_block,current+1,2500):
        upper=min(current,lower+2499)
        logs=_rpc('eth_getLogs',[{'address':BSC_USDT,'fromBlock':hex(lower),'toBlock':hex(upper),
                                  'topics':[TRANSFER_TOPIC,None,recipient_topic]}])
        for event in extract_bsc_logs(logs,order.receiving_address,int(order.expected_usdt_micros)):
            # Request the authoritative block timestamp to distinguish orders.
            block=event['block']
            if not block:continue
            details=_rpc('eth_getBlockByNumber',[block,False])
            if not isinstance(details,dict):continue
            try:ms=int(details['timestamp'],16)*1000
            except (KeyError,ValueError,TypeError):continue
            if start<=ms<=end:
                event['timestamp_ms']=ms
                hits.append(event)
    return hits


def candidate_is_unique(db,order,transfer):
    """Shared deposit addresses require one and only one plausible order."""
    ts=datetime.fromtimestamp(transfer['timestamp_ms']/1000,timezone.utc)
    # Match current and historical orders, even if they have been rejected/approved,
    # because a payment cannot be silently assigned to a newer order.
    competing=db.scalars(select(Order.id).where(
        Order.network==order.network,Order.receiving_address==order.receiving_address,
        Order.expected_usdt_micros==order.expected_usdt_micros,
        Order.created_at<=ts,Order.expires_at>=ts
    )).all()
    return len(competing)==1 and competing[0]==order.id


def discover_payment(db,order):
    if order.status!='PENDING':raise HTTPException(409,'Order is not awaiting verification')
    if order.network=='TRC20':events=_tron_history(order)
    elif order.network=='BEP20':events=_bsc_history(order)
    else:raise HTTPException(422,'Unknown USDT payment network')
    distinct={x['tx_hash']:x for x in events}
    if not distinct:raise HTTPException(409,'No matching confirmed transfer found yet. Retry later or ask support for payment reconciliation.')
    if len(distinct)!=1:raise HTTPException(409,'Multiple matching transfers; obtain payment details for manual review.')
    transfer=next(iter(distinct.values()))
    if not candidate_is_unique(db,order,transfer):
        raise HTTPException(409,'Payment amount matches another order; request TXID or wallet details for manual reconciliation.')
    tx=_hash(order.network,transfer['tx_hash'])
    addr=_address(order.network,transfer['sender_address'])
    from .v21310_predict_q import Order as QOrder
    if db.scalar(select(QOrder.id).where(QOrder.tx_hash==tx,QOrder.id!=order.id)):
        raise HTTPException(409,'Payment is already assigned to another Q Predict order')
    if db.scalar(select(QPaymentOrder.id).where(QPaymentOrder.submitted_tx_hash==tx)):
        raise HTTPException(409,'Payment is already claimed in Q Economy')
    return {'tx_hash':tx,'sender_address':addr}


def _tron_encode(hex20):
    import hashlib
    payload=b'\x41'+bytes.fromhex(hex20)
    data=payload+hashlib.sha256(hashlib.sha256(payload).digest()).digest()[:4]
    alphabet='123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
    number=int.from_bytes(data,'big');result=''
    while number:
        number,mod=divmod(number,58);result=alphabet[mod]+result
    return ('1'*(len(data)-len(data.lstrip(b'\0'))))+result


def sender_from_known_hash(order):
    """For an optional user-supplied TXID, derive sender directly from receipt."""
    if order.network=='TRC20':
        from .v21310_predict_q import _tron_post
        info=_tron_post('/walletsolidity/gettransactioninfobyid',{'value':order.tx_hash})
        if (info.get('receipt') or {}).get('result')!='SUCCESS':
            raise HTTPException(409,'TRON payment is not confirmed')
        start,end=payment_window(order)
        timestamp=int(info.get('blockTimeStamp') or 0)
        if not start<=timestamp<=end:
            raise HTTPException(409,'Transaction time does not match this order')
        matches=[]
        for log in info.get('log') or []:
            topics=log.get('topics') or []
            addr=str(log.get('address','')).lower().removeprefix('0x').removeprefix('41')
            if addr!=_b58decode(TRON_USDT) or len(topics)!=3:continue
            if '0x'+str(topics[0]).lower().removeprefix('0x')!=TRANSFER_TOPIC:continue
            if str(topics[2]).lower()[-40:]!=_b58decode(order.receiving_address):continue
            try:amount=int(str(log['data']).removeprefix('0x'),16)
            except (KeyError,ValueError,TypeError):continue
            if amount!=order.expected_usdt_micros:continue
            matches.append(_tron_encode(str(topics[1])[-40:]))
        if len(matches)!=1:raise HTTPException(409,'TXID does not prove exactly one expected USDT payment')
        return _address('TRC20',matches[0])
    if order.network=='BEP20':
        receipt=_rpc('eth_getTransactionReceipt',[order.tx_hash])
        if not isinstance(receipt,dict) or receipt.get('status')!='0x1':
            raise HTTPException(409,'BSC payment is not confirmed')
        hits=extract_bsc_logs(receipt.get('logs'),order.receiving_address,int(order.expected_usdt_micros))
        if len(hits)!=1:raise HTTPException(409,'TXID does not contain one matching USDT payment')
        block=receipt.get('blockNumber')
        meta=_rpc('eth_getBlockByNumber',[block,False]) if block else None
        if not isinstance(meta,dict):raise HTTPException(503,'Cannot verify payment block time')
        start,end=payment_window(order)
        try:ms=int(meta['timestamp'],16)*1000
        except (KeyError,ValueError,TypeError):raise HTTPException(503,'Cannot verify payment time')
        if not start<=ms<=end:raise HTTPException(409,'Transaction time does not match this order')
        return hits[0]['sender_address']
    raise HTTPException(422,'Unknown payment network')
