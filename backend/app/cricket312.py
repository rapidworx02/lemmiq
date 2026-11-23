"""LEMMIQ V3.1.2: international match-winner dual-wallet automation.

Demo is independent from the verified Q Predict Q wallet. Real Q cricket staking
requires existing team/gate controls plus explicit operator licensing flags; default OFF.
No direct Q Economy, crypto transfer, or externally signed payment changes.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import threading
from datetime import datetime, timedelta, timezone
from typing import Optional

import requests
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, select, func, text
from sqlalchemy.orm import Mapped, Session, mapped_column

from .database import Base, SessionLocal
from .models import User
from .v29 import PredictMarket, PredictMarketIn, _create_market, _require_admin
from .v2138_predict import DemoPool, DemoPosition, DemoResolution, _settle_due as settle_demo, aware
from .v21310_predict_q import (Pool as QPool, Position as QPosition,
                                 Resolution as QResolution, _settle as settle_q)
from .action310 import emit, prefs

LOG = logging.getLogger('lemmiq.cricket312')
PREFIX = 'CRICKET_V312_INTL_WIN'
SOURCE = 'CricketData.org'
API = 'https://api.cricapi.com/v1/'
ADVISORY_LOCK = 312202611
LOCAL_LOCK = threading.Lock()
MAX_ISSUES_PER_USER_DAY = 3

COUNTRIES = frozenset({
 'afghanistan','australia','bangladesh','canada','china','england','fiji',
 'hong kong','india','indonesia','ireland','kenya','malaysia','namibia','nepal',
 'netherlands','new zealand','nigeria','oman','pakistan','papua new guinea',
 'rwanda','scotland','south africa','sri lanka','thailand','uganda',
 'united arab emirates','united states of america','united states','usa',
 'west indies','zimbabwe','bermuda','botswana','germany','italy','jersey',
 'kuwait','singapore','tanzania','japan','bahrain','qatar','saudi arabia',
 'united states of america women'
})
BLOCK = ('rising stars', 'under 19', 'under-19', 'u19', 'u-19', 'academy',
         'domestic', 'provincial', 'super smash', 'big bash', 'premier league',
         'ipl', 'bbl', 'sa20', 'psl', 'tour match', 'warm-up', 'warm up',
         'practice match', 'development', 'legends', 'masters', 'a team',
         'list a', 'first class')
SERIES_SIGNALS = ('t20i', 'international', 'tour of', 'world cup',
                  'test championship', 'the ashes', 'womens ashes',
                  "women's ashes", 'champions trophy')


def now(): return datetime.now(timezone.utc)
def yes(name, default='false'): return os.getenv(name,default).strip().lower() in ('true','1','yes','on')
def allowed():
    return (yes('LEMMIQ_CRICKET_AUTO_ENABLED') and
            yes('LEMMIQ_CRICKET_PROVIDER_AUTHORIZED') and
            bool(os.getenv('LEMMIQ_CRICKET_API_KEY','').strip()))
def real_cricket_allowed():
    # This is an explicit operator attestation, NOT proof of an Australian wagering licence.
    # The dedicated Q wallet also enforces team-id and WAGERING gates per user.
    return (allowed() and yes('LEMMIQ_CRICKET_REAL_Q_LICENSE_CONFIRMED')
            and yes('LEMMIQ_CRICKET_REAL_Q_ENABLED')
            and yes('LEMMIQ_PREDICT_Q_WAGERING_ENABLED'))

def stamp(raw):
    try:
        dt=datetime.fromisoformat(str(raw).replace('Z','+00:00'))
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
    except (ValueError, TypeError):return None

def country(name):
    s=re.sub(r'\s+', ' ',str(name or '').strip().lower())
    if not s or s in ('tbc','tbd','unknown','to be confirmed'):return ''
    if re.search(r'(?:\bu[- ]?\d{2}\b|\bunder[- ]?\d+\b|\b[a-z]+\s+a\b|\ba team\b|\bx[i1]\b)',s):return ''
    if any(x in s for x in ('academy','emerging','rising','development')):return ''
    s=re.sub(r"(?: women's| womens| women| men| men's)$",'',s).strip()
    return s if s in COUNTRIES else ''


def eligibility(obj, at=None):
    """Fail closed. A domestic match with matchType=t20/odi is never enough."""
    at=at or now()
    if not isinstance(obj,dict):return (False,'invalid_fixture')
    match_id=str(obj.get('id') or '')
    if not re.fullmatch(r'[0-9a-fA-F-]{36}',match_id):return (False,'invalid_id')
    teams=obj.get('teams') or []
    if len(teams)!=2 or not all(country(x) for x in teams) or country(teams[0])==country(teams[1]):
        return (False,'not_senior_national_teams')
    name=str(obj.get('name') or '').lower()
    if any(w in name for w in BLOCK):return (False,'non_international_series')
    if not any(w in name for w in SERIES_SIGNALS):return (False,'unverified_international_series')
    fmt=str(obj.get('matchType') or '').lower()
    if fmt not in ('t20','odi','test'):return (False,'unsupported_format')
    start=stamp(obj.get('dateTimeGMT'))
    if start is None:return (False,'missing_start_time')
    if not (at+timedelta(hours=2) <=start<=at+timedelta(days=14)):
        return (False,'outside_publication_window')
    if obj.get('matchStarted') is not False or obj.get('matchEnded') is not False:
        return (False,'already_started_or_uncertain')
    if not obj.get('series_id'):return (False,'missing_series_id')
    return (True,'eligible')


def decision(info, fixture):
    """Only terminal, consistent winner/void conditions return YES/NO/VOID."""
    if not isinstance(info,dict) or str(info.get('id'))!=str(fixture.match_id):return (None,'match_id_mismatch')
    teams=info.get('teams') or []
    if len(teams)!=2 or {str(x).casefold().strip() for x in teams}!={fixture.team_a.casefold(),fixture.team_b.casefold()}:
        return (None,'teams_mismatch')
    if info.get('matchEnded') is not True:return (None,'not_final')
    status=str(info.get('status') or '').lower()
    if any(s in status for s in ('no result','without result','abandoned','washed out','match drawn','drawn match','match tied','tie match','match cancelled')):
        return ('VOID',status)
    if info.get('matchStarted') is not True:return (None,'not_final')
    winner=str(info.get('matchWinner') or '').casefold().strip()
    # Do not trust an unrelated "won" in free-text (e.g. toss won), and
    # reject contradictory winner/status pairs rather than paying out.
    result_text=status.strip()
    if re.search(r'\bwon the toss\b',result_text):return (None,'not_a_final_match_result')
    verified_text=any(result_text.startswith(winner+' '+verb) for verb in ('won','win','beat','defeated'))
    if winner==fixture.team_a.casefold():
        return ('YES',status) if verified_text else (None,'result_description_conflict')
    if winner==fixture.team_b.casefold():
        return ('NO',status) if verified_text else (None,'result_description_conflict')
    return (None,'missing_or_invalid_winner')


class CricketState312(Base):
    __tablename__='v312_cricket_state'
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    utc_date:Mapped[str]=mapped_column(String(10),default='')
    hits_used:Mapped[int]=mapped_column(Integer,default=0)
    provider_hits_today:Mapped[int]=mapped_column(Integer,default=0)
    last_discovery_at:Mapped[Optional[datetime]]=mapped_column(DateTime(timezone=True),nullable=True)
    last_error:Mapped[str]=mapped_column(String(240),default='')

class CricketFixture312(Base):
    __tablename__='v312_cricket_fixtures'
    match_id:Mapped[str]=mapped_column(String(72),primary_key=True)
    market_id:Mapped[int]=mapped_column(ForeignKey('q_predict_markets.id'),unique=True,index=True)
    series_id:Mapped[str]=mapped_column(String(72))
    team_a:Mapped[str]=mapped_column(String(90))
    team_b:Mapped[str]=mapped_column(String(90))
    match_type:Mapped[str]=mapped_column(String(10))
    start_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
    status:Mapped[str]=mapped_column(String(24),default='LIVE')
    last_polled_at:Mapped[Optional[datetime]]=mapped_column(DateTime(timezone=True),nullable=True)
    settled_at:Mapped[Optional[datetime]]=mapped_column(DateTime(timezone=True),nullable=True)
    final_evidence:Mapped[str]=mapped_column(Text,default='')
    last_error:Mapped[str]=mapped_column(String(240),default='')

class CricketIssue312(Base):
    __tablename__='v312_cricket_issues'
    id:Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True)
    match_id:Mapped[str]=mapped_column(String(72),index=True)
    market_id:Mapped[int]=mapped_column(ForeignKey('q_predict_markets.id'),index=True)
    reporter_id:Mapped[Optional[int]]=mapped_column(ForeignKey('users.id'),nullable=True)
    kind:Mapped[str]=mapped_column(String(32),index=True)
    reason:Mapped[str]=mapped_column(Text)
    status:Mapped[str]=mapped_column(String(24),default='OPEN',index=True)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class Report312(BaseModel):
    market_id:int=Field(gt=0)
    reason:str=Field(min_length=15,max_length=1000)

class ResolveIssue312(BaseModel):
    note:str=Field(min_length=10,max_length=500)


def _state(db):
    row=db.get(CricketState312,1)
    if row is None:
        row=CricketState312(id=1);db.add(row);db.flush()
    today=now().date().isoformat()
    if row.utc_date!=today:
        row.utc_date=today;row.hits_used=0;row.provider_hits_today=0
    return row


def budget(db, purpose):
    state=_state(db)
    cap=min(100,max(1,int(os.getenv('LEMMIQ_CRICKET_API_DAILY_BUDGET','80'))))
    reserve=max(0,min(20,cap//4))
    used=max(state.hits_used,state.provider_hits_today)
    if used>=cap or (purpose=='discovery' and used>=cap-reserve):return False
    return True


def provider_call(db,path,params,purpose):
    if not allowed():raise RuntimeError('Cricket data provider not authorised/configured')
    if not budget(db,purpose):raise RuntimeError('Cricket API daily budget exhausted')
    state=_state(db);state.hits_used+=1;db.flush()
    # No redirects; never log the API key or complete request URL.
    response=requests.get(API+path,params={**params,'apikey':os.environ['LEMMIQ_CRICKET_API_KEY']},timeout=12,allow_redirects=False)
    if response.status_code!=200:raise RuntimeError('Cricket provider returned HTTP '+str(response.status_code))
    if len(response.content)>2_000_000:raise RuntimeError('Cricket provider response exceeds size limit')
    data=response.json()
    if not isinstance(data,dict) or data.get('status')!='success':raise RuntimeError('Cricket provider returned an unsuccessful response')
    info=data.get('info') or {}
    try:state.provider_hits_today=max(state.provider_hits_today,int(info.get('hitsToday') or 0))
    except (TypeError,ValueError):pass
    return data.get('data')


def _issue(db,fixture,kind,reason):
    reason=str(reason)[:1000]
    existing=db.scalar(select(CricketIssue312).where(CricketIssue312.market_id==fixture.market_id,CricketIssue312.kind==kind,CricketIssue312.status=='OPEN'))
    if not existing:db.add(CricketIssue312(match_id=fixture.match_id,market_id=fixture.market_id,kind=kind,reason=reason))
    fixture.last_error=reason[:240]


def publish(db, matches):
    if not yes('LEMMIQ_CRICKET_AUTO_PUBLISH'):return 0
    limit=max(1,min(8,int(os.getenv('LEMMIQ_CRICKET_MAX_MATCHES_DAILY','8'))))
    midnight=now().replace(hour=0,minute=0,second=0,microsecond=0)
    count=db.scalar(select(func.count()).select_from(PredictMarket).where(PredictMarket.template_code==PREFIX,PredictMarket.created_at>=midnight)) or 0
    live=db.scalar(select(func.count()).select_from(PredictMarket).where(PredictMarket.template_code==PREFIX,PredictMarket.status=='LIVE')) or 0
    created=0
    for obj in matches:
        ok,why=eligibility(obj)
        if not ok or count>=limit or live>=12:continue
        mid=str(obj['id'])
        if db.get(CricketFixture312,mid):continue
        # A provider may move kickoff; one external match ID must never have two markets.
        if db.scalar(select(PredictMarket.id).where(PredictMarket.template_code==PREFIX,PredictMarket.source_config_json.like('%"match_id": "'+mid+'"%'))):continue
        start=stamp(obj['dateTimeGMT']);team_a,team_b=map(str,obj['teams']);close=start-timedelta(minutes=10)
        spec=PredictMarketIn(question=f'Will {team_a} defeat {team_b} in {str(obj["name"]).split(",",2)[-1].strip()[:130]}?',
            category='SPORTS',template_code=PREFIX,close_at=close,resolve_after=start+timedelta(days=8 if obj['matchType']=='test' else 3),
            resolution_source_name=SOURCE,resolution_source_url='https://cricketdata.org/',
            resolution_rule=f'YES if {team_a} is declared the final match winner; NO if {team_b} wins; VOID for an official draw, tie, abandonment or no result. Settlement only after the provider confirms a final result.',
            source_type='CRICKET_API312',source_config={'match_id':mid,'series_id':obj['series_id'],'series':str(obj['name']).split(',',2)[-1].strip()[:120],'team_a':team_a,'team_b':team_b,'demo_enabled':True,'real_q_requires_authorization':True,'match_type':obj['matchType']},
            trend_score=70,resolution_confidence=0,auto_resolve=False)
        m=_create_market(db,spec,generated_by='CRICKET_AUTO312',status='LIVE',reason='Validated senior national teams and international series. Independent Demo and authorised verified Q wallets.')
        if m.generated_by!='CRICKET_AUTO312':continue
        db.add(CricketFixture312(match_id=mid,market_id=m.id,series_id=str(obj['series_id']),team_a=team_a,team_b=team_b,match_type=obj['matchType'],start_at=start))
        count+=1;live+=1;created+=1
    return created


def _notify(db,market_id,outcome,evidence):
    for pos_cls,unit,key_unit in (
        (DemoPosition,'Demo USDT','Demo Q'),(QPosition,'Q Predict Q','Q Predict Q')):
        entries=db.scalars(select(pos_cls).where(pos_cls.market_id==market_id)).all()
        for p in entries:
            if p.status not in ('WON','LOST','VOID'):continue
            if not prefs(db,p.user_id).get('results',True):continue
            detail=(f'Your {p.outcome} prediction is {p.status}. '
                    f'Stake {p.stake_micros/1_000_000:.2f} {unit}; '
                    f'returned {p.payout_micros/1_000_000:.2f}; '
                    f'fee {p.fee_micros/1_000_000:.2f}. '
                    f'Final result: {outcome}. Evidence: {evidence}')
            emit(db,p.user_id,f'predict:{key_unit}:{market_id}:settled',
                 'PREDICT','Your prediction has settled',detail)


def settle_if_verified(db,fixture,details):
    outcome,reason=decision(details,fixture)
    if outcome is None:
        if reason not in ('not_final','missing_or_invalid_winner'):
            _issue(db,fixture,'RESULT_CONFLICT',reason)
        elif now()-aware(fixture.start_at)>timedelta(days=9 if fixture.match_type=='test' else 3):
            _issue(db,fixture,'RESULT_DELAYED',reason)
        return False
    m=db.scalar(select(PredictMarket).where(PredictMarket.id==fixture.market_id).with_for_update())
    if not m or m.template_code!=PREFIX or m.status=='SUSPENDED':return False
    if aware(m.close_at)>now() or m.status not in ('LIVE','CLOSED','RESOLVING'):return False
    if db.get(DemoResolution,m.id):return False
    # Capture both wallets under the same market lock. Even if future staking is
    # disabled, existing Q stakes must be resolved from the contracted result.
    qpool=db.scalar(select(QPool).where(QPool.market_id==m.id).with_for_update())
    if db.get(QResolution,m.id) or (qpool and qpool.settled_at):
        _issue(db,fixture,'SETTLEMENT_CONFLICT','A separate Q result is already recorded; manual reconciliation required')
        return False
    actor=int(os.getenv('LEMMIQ_CRICKET_SERVICE_USER_ID','0'))
    if actor<=0 or db.get(User,actor) is None:
        _issue(db,fixture,'CONFIGURATION','Set LEMMIQ_CRICKET_SERVICE_USER_ID to an existing dedicated service user before enabling settlement')
        return False
    evidence=('CricketData Match Info; match='+fixture.match_id+'; checked='+now().isoformat()+'; '+
              'winner='+str(details.get('matchWinner') or 'none')+'; status='+str(details.get('status') or ''))[:500]
    db.add(DemoResolution(market_id=m.id,outcome=outcome,evidence=evidence,resolved_by=actor))
    db.flush()
    settle_demo(db)
    pool=db.get(DemoPool,m.id)
    if pool is not None and pool.settled_at is None:raise RuntimeError('Demo settlement did not complete')
    if qpool is not None:
        # The existing Q ledger is authoritative; this is NOT a transfer from Demo.
        qresult=QResolution(market_id=m.id,outcome=outcome,evidence=evidence,admin_id=actor)
        db.add(qresult)
        db.flush()
        settle_q(db,m,qpool,qresult)
        if qpool.settled_at is None:raise RuntimeError('Q Predict Q settlement did not complete')
    m.status='RESOLVED' if outcome!='VOID' else 'VOID';m.result=outcome;m.resolved_at=now();m.updated_at=now()
    fixture.status='SETTLED';fixture.settled_at=now();fixture.final_evidence=evidence;fixture.last_error=''
    _notify(db,m.id,outcome,evidence)
    return True


def _due(db):
    cutoff=now()
    rows=db.scalars(select(CricketFixture312).where(CricketFixture312.status.in_(['LIVE','PENDING']),CricketFixture312.start_at<=cutoff).order_by(CricketFixture312.start_at).limit(30)).all()
    due=[]
    for f in rows:
        m=db.get(PredictMarket,f.market_id)
        if not m or m.status in ('SUSPENDED','VOID','RESOLVED'):continue
        # Adaptive checks: do not waste hundreds of calls during a five-day Test.
        if f.match_type=='test':
            first=timedelta(hours=48);gap=timedelta(hours=6 if cutoff-aware(f.start_at)>timedelta(days=4) else 12)
        elif f.match_type=='odi':first=timedelta(hours=5);gap=timedelta(hours=3)
        else:first=timedelta(hours=2);gap=timedelta(hours=2)
        if cutoff<aware(f.start_at)+first:continue
        if f.last_polled_at and aware(f.last_polled_at)>cutoff-gap:continue
        due.append(f)
    return due[:3]


def _tick(db):
    if not allowed():return {'enabled':False}
    if db.bind.dialect.name=='postgresql':
        lock=db.scalar(text('SELECT pg_try_advisory_xact_lock(:lockid)').bindparams(lockid=ADVISORY_LOCK))
        if not lock:return {'skipped':'another_worker_active'}
    else:
        if not LOCAL_LOCK.acquire(blocking=False):return {'skipped':'another_worker_active'}
    try:
        counts={'polled':0,'settled':0,'published':0,'issues':0}
        # Internal closure never consumes a provider hit.
        active=db.scalars(select(PredictMarket).where(PredictMarket.template_code==PREFIX,
            PredictMarket.status=='LIVE',PredictMarket.close_at<=now())).all()
        for m in active:m.status='CLOSED';m.updated_at=now()
        for f in _due(db):
            if not budget(db,'settlement'):break
            try:
                f.last_polled_at=now();payload=provider_call(db,'match_info',{'id':f.match_id},'settlement')
                if not isinstance(payload,dict):_issue(db,f,'PROVIDER_SCHEMA','Match Info data is not an object');continue
                # SAVEPOINT: a failed payout must not partially record a resolution.
                with db.begin_nested():
                    settled=settle_if_verified(db,f,payload)
                if settled:counts['settled']+=1
                counts['polled']+=1
            except Exception as exc:
                # Do not log request URLs, which include API keys.
                _issue(db,f,'PROVIDER_ERROR',type(exc).__name__)
        state=_state(db)
        interval=timedelta(hours=4)
        if (not state.last_discovery_at or aware(state.last_discovery_at)<now()-interval) and budget(db,'discovery'):
            state.last_discovery_at=now()
            try:
                payload=provider_call(db,'matches',{'offset':0},'discovery')
                if isinstance(payload,list):counts['published']=publish(db,payload)
                else:state.last_error='Matches List data is not an array'
            except Exception as exc:state.last_error=type(exc).__name__
        db.commit()
        return counts
    finally:
        if db.bind.dialect.name!='postgresql':LOCAL_LOCK.release()


async def _loop():
    while True:
        try:
            if allowed():await asyncio.to_thread(_run_once)
        except asyncio.CancelledError:raise
        except Exception:LOG.exception('Cricket automation tick failed (secret URLs are not logged)')
        await asyncio.sleep(300)

def _run_once():
    with SessionLocal() as db:return _tick(db)


def register_cricket312(app,current_user,get_db):
    router=APIRouter(prefix='/v312/cricket',tags=['LEMMIQ V3.1.2 international cricket automation'])
    @router.get('/policy')
    def policy(u=Depends(current_user)):
        return {'mode':'DEMO_USDT_AND_AUTHORIZED_VERIFIED_Q','formats':['T20I','ODI','TEST'],'market_types':['MATCH_WINNER'],
                'max_matches_per_day':min(8,max(1,int(os.getenv('LEMMIQ_CRICKET_MAX_MATCHES_DAILY','8')))),
                'real_q_cricket_enabled':real_cricket_allowed(),'automatic_publishing':allowed() and yes('LEMMIQ_CRICKET_AUTO_PUBLISH')}
    @router.get('/admin/status')
    def admin_status(u=Depends(current_user),db:Session=Depends(get_db)):
        _require_admin(db,u,'READ')
        state=_state(db)
        return {'enabled':allowed(),'auto_publish':yes('LEMMIQ_CRICKET_AUTO_PUBLISH'),
                'commercial_permission_confirmed':yes('LEMMIQ_CRICKET_PROVIDER_AUTHORIZED'),
                'real_q_cricket_enabled':real_cricket_allowed(),
                'quota_used':max(state.hits_used,state.provider_hits_today),'quota_limit':int(os.getenv('LEMMIQ_CRICKET_API_DAILY_BUDGET','80')),
                'last_discovery_at':state.last_discovery_at,'last_error':state.last_error,
                'open_issues':int(db.scalar(select(func.count()).select_from(CricketIssue312).where(CricketIssue312.status=='OPEN')) or 0),
                'tracked_matches':int(db.scalar(select(func.count()).select_from(CricketFixture312)) or 0)}
    @router.get('/admin/issues')
    def issues(u=Depends(current_user),db:Session=Depends(get_db)):
        _require_admin(db,u,'READ')
        rows=db.scalars(select(CricketIssue312).order_by(CricketIssue312.id.desc()).limit(100)).all()
        return [{'id':x.id,'market_id':x.market_id,'match_id':x.match_id,'type':x.kind,'reason':x.reason,'status':x.status,'created_at':x.created_at} for x in rows]
    @router.post('/admin/issues/{issue_id}/close')
    def close_issue(issue_id:int,body:ResolveIssue312,u=Depends(current_user),db:Session=Depends(get_db)):
        _require_admin(db,u,'FULL')
        issue=db.scalar(select(CricketIssue312).where(CricketIssue312.id==issue_id).with_for_update())
        if not issue:raise HTTPException(404,'Issue not found')
        if issue.status!='OPEN':raise HTTPException(409,'Issue is already closed')
        issue.status='CLOSED'
        issue.reason=(issue.reason+' | Review: '+body.note.strip())[:1400]
        remaining=db.scalar(select(func.count()).select_from(CricketIssue312).where(CricketIssue312.market_id==issue.market_id,CricketIssue312.status=='OPEN')) or 0
        if remaining==0:
            fixture=db.get(CricketFixture312,issue.match_id)
            if fixture and fixture.status=='DISPUTED':fixture.status='PENDING'
        db.commit();return {'ok':True,'issue_id':issue_id,'status':'CLOSED'}
    @router.post('/report')
    def report(body:Report312,u=Depends(current_user),db:Session=Depends(get_db)):
        market=db.get(PredictMarket,body.market_id)
        fixture=db.scalar(select(CricketFixture312).where(CricketFixture312.market_id==body.market_id))
        if not market or not fixture:raise HTTPException(404,'Automated international cricket market not found')
        if not (db.scalar(select(DemoPosition.id).where(DemoPosition.market_id==body.market_id,DemoPosition.user_id==u.id).limit(1))
                or db.scalar(select(QPosition.id).where(QPosition.market_id==body.market_id,QPosition.user_id==u.id).limit(1))):
            raise HTTPException(403,'Only participants may report a result issue')
        today=now().replace(hour=0,minute=0,second=0,microsecond=0)
        n=db.scalar(select(func.count()).select_from(CricketIssue312).where(CricketIssue312.reporter_id==u.id,CricketIssue312.created_at>=today)) or 0
        if n>=MAX_ISSUES_PER_USER_DAY:raise HTTPException(429,'Daily result report limit reached')
        db.add(CricketIssue312(match_id=fixture.match_id,market_id=body.market_id,reporter_id=u.id,kind='USER_REPORT',reason=body.reason.strip()))
        if fixture.status in ('LIVE','PENDING') and market.status in ('CLOSED','RESOLVING'):
            fixture.status='DISPUTED'  # Hold pending automatic settlement until admin closes the issue.
        db.commit();return {'accepted':True,'review':'Q Predict support queue'}
    app.include_router(router)
    task={'worker':None}
    @app.on_event('startup')
    async def start_cricket312():
        if allowed() and (task['worker'] is None or task['worker'].done()):
            task['worker']=asyncio.create_task(_loop())
    @app.on_event('shutdown')
    async def stop_cricket312():
        worker=task['worker']
        if worker:
            worker.cancel()
            try:await worker
            except asyncio.CancelledError:pass
