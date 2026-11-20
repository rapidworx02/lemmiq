"""LEMMIQ 2.13.14 — cricket Test/ODI/T20 performance-market drafts.

All new markets are binary YES/NO, manual-scorecard-resolution, and DEMO ONLY.
Nothing in this module enables real-value Q wagering, payments, or automatic settlement.
Fixture reuse requires an operator-authorised cricket feed, or an admin-entered fixture
with an official scorecard URL. Published drafts still need independent admin review.
"""
from __future__ import annotations
import hashlib
import os
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from .models import User
from .v29 import PredictMarket, PredictMarketIn, _create_market, _dedupe_key, _require_admin
from .v2137_cricket import fixtures, _iso
from .v2138_predict import DemoResolution, AdminAudit as DemoAdminAudit, _settle_due, aware

CODES = (
    'TEAM_INNINGS_RUNS', 'BATTER_RUNS', 'BOWLER_WICKETS', 'PLAYER_CENTURY',
    'DAY_WICKETS', 'FIRST_INNINGS_LEAD', 'MATCH_DRAW', 'DAY_RUNS',
)
TEMPLATES = [
    {'code':'TEAM_INNINGS_RUNS','name':'Team innings runs','default_threshold':300,'needs_team':True,'needs_player':False,'test_only':False},
    {'code':'BATTER_RUNS','name':'Batter runs','default_threshold':50,'needs_team':True,'needs_player':True,'test_only':False},
    {'code':'BOWLER_WICKETS','name':'Bowler wickets','default_threshold':3,'needs_team':True,'needs_player':True,'test_only':False},
    {'code':'PLAYER_CENTURY','name':'Any batter century (team)','default_threshold':100,'needs_team':True,'needs_player':False,'test_only':False},
    {'code':'DAY_WICKETS','name':'Wickets on a Test-match day','default_threshold':7,'needs_team':False,'needs_player':False,'test_only':True},
    {'code':'FIRST_INNINGS_LEAD','name':'Test first-innings lead','default_threshold':0,'needs_team':True,'needs_player':False,'test_only':True},
    {'code':'MATCH_DRAW','name':'Test match draw','default_threshold':0,'needs_team':False,'needs_player':False,'test_only':True},
    {'code':'DAY_RUNS','name':'Runs on a Test-match day','default_threshold':250,'needs_team':False,'needs_player':False,'test_only':True},
]
PREFIX = 'CRICKET_V21314_'

def utcnow(): return datetime.now(timezone.utc)

def _official_url(url: str) -> str:
    s = str(url or '').strip()
    p = urlsplit(s)
    if (len(s) > 450 or p.scheme != 'https' or not p.hostname or p.username or
            p.password or p.fragment or p.hostname.lower() in ('localhost','127.0.0.1') or
            p.hostname.endswith(('.localhost','.local'))):
        raise HTTPException(422,'An HTTPS official scorecard/result URL is required before drafting')
    return s

def _fmt(fmt: str) -> str:
    v = str(fmt or '').strip().upper().replace(' ','')
    return {'TESTMATCH':'TEST','TESTS':'TEST','T20I':'T20','ODI':'ODI','TEST':'TEST','T20':'T20'}.get(v,'')

def _fixture_from_feed(match_id: str):
    try: rows = fixtures(force=True)
    except Exception as exc: raise HTTPException(503,'Licensed cricket fixture feed unavailable; enter fixture manually') from exc
    for m in rows:
        if m['id'] == match_id:
            return m
    raise HTTPException(404,'Fixture not found in current authorised feed; enter official fixture manually')

class FixtureInput(BaseModel):
    match_id: str = Field(default='',max_length=70)
    team_a: str = Field(default='',max_length=90)
    team_b: str = Field(default='',max_length=90)
    series: str = Field(default='',max_length=120)
    format: str = Field(default='TEST',max_length=20)
    start_at: str = Field(default='',max_length=42)  # ISO 8601 with explicit UTC offset
    official_url: str = Field(min_length=12,max_length=450)

class DraftMarketIn(FixtureInput):
    template: Literal['TEAM_INNINGS_RUNS','BATTER_RUNS','BOWLER_WICKETS','PLAYER_CENTURY',
                      'DAY_WICKETS','FIRST_INNINGS_LEAD','MATCH_DRAW','DAY_RUNS']
    team: str = Field(default='',max_length=90)
    player: str = Field(default='',max_length=90)
    threshold: int = Field(default=0,ge=0,le=1000)
    innings: int = Field(default=1,ge=1,le=2)
    day: int = Field(default=1,ge=1,le=5)

class ImportTestsIn(BaseModel):
    match_id: str = Field(default='',max_length=70)
    official_url: str = Field(min_length=12,max_length=450)
    max_fixtures: int = Field(default=1,ge=1,le=1)

class ResolveDemoStatIn(BaseModel):
    market_id: int = Field(gt=0)
    official_url: str = Field(min_length=12,max_length=450)
    evidence_note: str = Field(min_length=16,max_length=600)
    observed: int | None = Field(default=None,ge=0,le=2500)
    team_a_runs: int | None = Field(default=None,ge=0,le=1500)
    team_b_runs: int | None = Field(default=None,ge=0,le=1500)
    result: Literal['DRAW','DECIDED','TIE','ABANDONED'] | None = None
    void_reason: str = Field(default='',max_length=300)


def _fixture(body: FixtureInput) -> dict:
    if body.match_id.strip():
        m = _fixture_from_feed(body.match_id.strip())
    else:
        a, b, series = body.team_a.strip(),body.team_b.strip(),body.series.strip()
        if not (a and b and a.casefold()!=b.casefold() and series):
            raise HTTPException(422,'Both teams and the series name are required for a manual fixture')
        start_raw = body.start_at.strip()
        if not (start_raw.endswith('Z') or re.search(r'[+-]\d{2}:\d{2}$',start_raw)):
            raise HTTPException(422,'Fixture start time must include a UTC offset (Z or +HH:MM)')
        start = _iso(start_raw)
        if not start: raise HTTPException(422,'Valid ISO-8601 fixture start required')
        fmt = _fmt(body.format)
        if not fmt: raise HTTPException(422,'Format must be TEST, ODI or T20')
        identity = f'{a.casefold()}|{b.casefold()}|{start.isoformat()}|{series.casefold()}'
        m = {'id':'MANUAL-'+hashlib.sha256(identity.encode()).hexdigest()[:26],
             'team_a':a,'team_b':b,'series':series,'start_at':start.isoformat(),
             'format':fmt,'status':'UPCOMING'}
    when = _iso(m.get('start_at'))
    if not when or when <= utcnow()+timedelta(minutes=35):
        raise HTTPException(409,'Fixture has started or is too close to start; pre-match drafts are not permitted')
    if when > utcnow()+timedelta(days=90):
        raise HTTPException(422,'Fixture must start within 90 days')
    if m.get('status','UPCOMING').upper() != 'UPCOMING':
        raise HTTPException(409,'Only upcoming fixtures can be drafted')
    if not _fmt(m.get('format')): raise HTTPException(422,'Fixture format is not supported')
    return {**m,'format':_fmt(m['format']),'start':when}


def _make_spec(f:dict, code:str, *, team:str='', player:str='', threshold:int=0, innings:int=1, day:int=1, official_url:str) -> PredictMarketIn:
    if code not in CODES:raise HTTPException(422,'Unknown cricket market template')
    fmt = f['format']
    if code in ('DAY_WICKETS','FIRST_INNINGS_LEAD','MATCH_DRAW','DAY_RUNS') and fmt!='TEST':
        raise HTTPException(422,'This market template is only available for Test cricket')
    a,b = f['team_a'],f['team_b']
    selected = next((x for x in (a,b) if x.casefold()==str(team).strip().casefold()),'')
    if code in ('TEAM_INNINGS_RUNS','BATTER_RUNS','BOWLER_WICKETS','PLAYER_CENTURY','FIRST_INNINGS_LEAD') and not selected:
        raise HTTPException(422,'Select a team participating in this fixture')
    name = str(player or '').strip()
    if code in ('BATTER_RUNS','BOWLER_WICKETS') and (len(name)<3 or not re.fullmatch(r"[\w \.'-]{3,90}",name,re.UNICODE)):
        raise HTTPException(422,'Provide a real playing-XI player name (verify it against the official team sheet)')
    if code in ('BOWLER_WICKETS','DAY_WICKETS'):
        if threshold<1 or threshold>10:raise HTTPException(422,'Wicket threshold must be 1–10')
    elif code in ('TEAM_INNINGS_RUNS','BATTER_RUNS','DAY_RUNS'):
        if threshold<1 or threshold>700:raise HTTPException(422,'Runs threshold must be 1–700')
    elif code=='PLAYER_CENTURY':threshold=100
    else:threshold=0
    if not (1<=innings<=2 and 1<=day<=5):raise HTTPException(422,'Unsupported innings or day')
    innings_label = 'first' if innings==1 else 'second'
    fixture_label = f"{a} vs {b} ({fmt})"
    if code=='TEAM_INNINGS_RUNS':
        question=f'Will {selected} score at least {threshold} runs in their {innings_label} innings of {fixture_label}?'
        rule=f'YES if {selected} scores {threshold}+ team runs including extras in its {innings_label} innings; NO if its completed innings total is below {threshold}; VOID if innings is not completed or the official result is unavailable.'
    elif code=='BATTER_RUNS':
        question=f'Will {name} ({selected}) score at least {threshold} runs in the {innings_label} innings of {fixture_label}?'
        rule=f'YES if {name} scores {threshold}+ credited batter runs in {selected} {innings_label} innings; NO if below; VOID if not selected, does not bat, innings is abandoned, or official scorecard is unavailable.'
    elif code=='BOWLER_WICKETS':
        opposition=b if selected==a else a
        question=f'Will {name} ({selected}) take at least {threshold} wickets in {opposition} {innings_label} innings ({fmt})?'
        rule=f'YES if {name} is officially credited with {threshold}+ wickets in {opposition} {innings_label} innings; NO if fewer; VOID if player not selected, innings not completed, or scorecard unavailable. Run-outs are not credited to the bowler.'
    elif code=='PLAYER_CENTURY':
        question=f'Will any {selected} batter score a century in their {innings_label} innings of {fixture_label}?'
        rule=f'YES if any {selected} batter records 100+ individual runs in that {innings_label} innings; NO if none; VOID if innings not completed or scorecard unavailable.'
    elif code=='DAY_WICKETS':
        question=f'Will at least {threshold} wickets fall across both teams on Day {day} of {fixture_label}?'
        rule=f'YES if official Day {day} play record shows {threshold}+ total dismissals across innings; NO if fewer and scheduled play is completed; VOID if no play, a materially shortened day or missing reliable day record.'
    elif code=='FIRST_INNINGS_LEAD':
        question=f'Will {selected} have the first-innings lead against {b if selected==a else a} ({fmt})?'
        rule=f'YES if {selected} first-innings total exceeds opposition first-innings total; NO if lower; VOID on equal totals or if either innings is incomplete or scorecard unavailable.'
    elif code=='MATCH_DRAW':
        question=f'Will {a} vs {b} end in an official Test match draw?'
        rule='YES only if the official Test result is DRAW; NO if officially won by either team; VOID on tie, abandonment, no result or inconclusive official records.'
    else:
        question=f'Will at least {threshold} total runs be scored on Day {day} of {fixture_label}?'
        rule=f'YES if combined official scorecard/score-by-day record shows {threshold}+ team runs including extras on scheduled Day {day}; NO if fewer with completed play; VOID if no play, materially shortened day or missing day-by-day score evidence.'
    if len(question)>260:raise HTTPException(422,'Market question too long; shorten player or series name')
    # Settlement has to wait until after the entire match; manual scorecard review is mandatory.
    close_at=f['start']-timedelta(minutes=10)
    resolve_after=f['start']+timedelta(days=8 if fmt=='TEST' else 3)
    config={'match_id':f['id'],'team_a':a,'team_b':b,'series':f['series'],'format':fmt,
            'fixture_start_at':f['start'].isoformat(),'template':code,'team':selected,
            'player':name,'threshold':threshold,'innings':innings,'day':day,
            'demo_only':True,'official_scorecard_required':True}
    return PredictMarketIn(question=question,category='SPORTS',template_code=PREFIX+code,
        close_at=close_at,resolve_after=resolve_after,
        resolution_source_name='Official cricket scorecard — admin verified',
        resolution_source_url=_official_url(official_url),resolution_rule=rule,
        source_type='MANUAL',source_config=config,trend_score=55,
        resolution_confidence=0,auto_resolve=False)


def _draft_one(db:Session, spec:PredictMarketIn, admin_id:int) -> tuple[int,bool]:
    key=_dedupe_key(spec.template_code,spec.source_config,spec.close_at)
    existing=db.scalar(select(PredictMarket.id).where(PredictMarket.market_key==key))
    if existing:return existing,False
    m=_create_market(db,spec,creator_id=admin_id,generated_by='CRICKET_V21314',
                     status='REVIEW',reason='Demo-only cricket stats: validate fixture, playing XI, start time and scorecard before publishing.')
    return m.id,True


def _test_import_specs(f:dict,url:str) -> list[PredictMarketIn]:
    # No player-specific markets without verified playing-XI information.
    return [
        _make_spec(f,'TEAM_INNINGS_RUNS',team=f['team_a'],threshold=300,official_url=url),
        _make_spec(f,'TEAM_INNINGS_RUNS',team=f['team_b'],threshold=300,official_url=url),
        _make_spec(f,'PLAYER_CENTURY',team=f['team_a'],official_url=url),
        _make_spec(f,'FIRST_INNINGS_LEAD',team=f['team_a'],official_url=url),
        _make_spec(f,'MATCH_DRAW',official_url=url),
        _make_spec(f,'DAY_WICKETS',threshold=7,day=1,official_url=url),
        _make_spec(f,'DAY_RUNS',threshold=250,day=1,official_url=url),
    ]


def _resolve_observation(cfg:dict, body:ResolveDemoStatIn) -> str:
    if body.void_reason.strip():
        if len(body.void_reason.strip())<15:raise HTTPException(422,'Give a clear reason (15+ characters) for voiding')
        return 'VOID'
    code=cfg['template']
    if code=='MATCH_DRAW':
        if not body.result:raise HTTPException(422,'Official match result is required')
        return {'DRAW':'YES','DECIDED':'NO','TIE':'VOID','ABANDONED':'VOID'}[body.result]
    if code=='FIRST_INNINGS_LEAD':
        if body.team_a_runs is None or body.team_b_runs is None:
            raise HTTPException(422,'Enter first-innings totals for both teams')
        if body.team_a_runs==body.team_b_runs:return 'VOID'
        lead=cfg['team_a'] if body.team_a_runs>body.team_b_runs else cfg['team_b']
        return 'YES' if lead==cfg['team'] else 'NO'
    if body.observed is None:
        raise HTTPException(422,'Enter the verified official scorecard statistic before settlement')
    target=int(cfg['threshold'])
    return 'YES' if body.observed>=target else 'NO'


def register_v21314_cricket_markets(app,current_user,get_db):
    router=APIRouter(prefix='/v21314/cricket',tags=['Cricket Test/ODI/T20 demo-only performance templates'])

    @router.get('/admin/catalog')
    def catalog(u:User=Depends(current_user)):
        # Every admin mutation also uses server-side admin checks.
        return {'templates':TEMPLATES,'market_mode':'DEMO_ONLY','auto_settlement':False,
                'notice':'Only pre-match, admin-reviewed drafts. Official scorecard evidence required for manual Demo settlement.'}

    @router.get('/admin/fixtures')
    def admin_fixtures(u:User=Depends(current_user),db:Session=Depends(get_db)):
        _require_admin(db,u,'READ')
        try:
            items=fixtures()
            future=[{k:v for k,v in m.items() if k in ('id','series','format','team_a','team_b','start_at','venue','status')}
                    for m in items if _fmt(m.get('format')) and m.get('status')=='UPCOMING'
                    and _iso(m.get('start_at')) and _iso(m['start_at'])>utcnow()+timedelta(minutes=35)]
            return {'configured':bool(os.getenv('LEMMIQ_CRICKET_FEED_URL')),
                    'fixtures':future[:100], 'count':len(future),'error':''}
        except Exception:
            return {'configured':bool(os.getenv('LEMMIQ_CRICKET_FEED_URL')),
                    'fixtures':[], 'count':0, 'error':'Authorised cricket feed unavailable. Enter a verified manual fixture.'}

    @router.get('/admin/markets')
    def admin_markets(u:User=Depends(current_user),db:Session=Depends(get_db)):
        _require_admin(db,u,'READ')
        rows=db.scalars(select(PredictMarket).where(PredictMarket.template_code.like(PREFIX+'%'))
                        .order_by(PredictMarket.id.desc()).limit(80)).all()
        return {'markets':[{'id':m.id,'question':m.question,'status':m.status,
                'template':m.template_code.removeprefix(PREFIX),'close_at':m.close_at.isoformat(),
                'official_url':m.resolution_source_url,'reviewed':m.approved_by_user_id is not None}
                for m in rows]}

    @router.post('/admin/draft')
    def draft(body:DraftMarketIn,u:User=Depends(current_user),db:Session=Depends(get_db)):
        _require_admin(db,u,'WRITE')
        f=_fixture(body)
        spec=_make_spec(f,body.template,team=body.team,player=body.player,
                        threshold=body.threshold,innings=body.innings,day=body.day,
                        official_url=body.official_url)
        mid,created=_draft_one(db,spec,u.id)
        db.commit()
        return {'id':mid,'created':created,'status':'REVIEW','market_mode':'DEMO_ONLY',
                'question':spec.question,'next':'Review and publish through Q Predict Admin; manual scorecard settlement required.'}

    @router.post('/admin/import-tests')
    def import_tests(body:ImportTestsIn,u:User=Depends(current_user),db:Session=Depends(get_db)):
        _require_admin(db,u,'WRITE')
        url=_official_url(body.official_url)
        try:rows=fixtures(force=True)
        except Exception as exc:raise HTTPException(503,'Fixture importer unavailable; configure licensed HTTPS feed') from exc
        eligible=[m for m in rows if (not body.match_id or m.get('id')==body.match_id) and _fmt(m.get('format'))=='TEST' and m.get('status')=='UPCOMING'
                  and _iso(m.get('start_at')) and utcnow()+timedelta(hours=2)<_iso(m['start_at'])<utcnow()+timedelta(days=30)]
        created=[]; existing=[]
        for fixture in eligible[:body.max_fixtures]:
            f={**fixture,'start':_iso(fixture['start_at']),'format':'TEST'}
            for spec in _test_import_specs(f,url):
                mid,is_new=_draft_one(db,spec,u.id)
                (created if is_new else existing).append(mid)
        db.commit()
        return {'drafted':len(created),'market_ids':created,'existing_ids':existing,
                'eligible_test_fixtures':len(eligible), 'status':'REVIEW',
                'note':'7 Demo-only review markets for one upcoming Test; no player props or automatic publication.'}

    @router.post('/admin/resolve-demo-stat')
    def resolve_demo_stat(body:ResolveDemoStatIn,u:User=Depends(current_user),db:Session=Depends(get_db)):
        _require_admin(db,u,'FULL')
        m=db.scalar(select(PredictMarket).where(PredictMarket.id==body.market_id).with_for_update())
        if not m or not m.template_code.startswith(PREFIX):raise HTTPException(404,'V2.13.14 cricket market not found')
        if aware(m.close_at)>utcnow():raise HTTPException(409,'Cannot settle a market before scheduled close')
        if db.get(DemoResolution,m.id):raise HTTPException(409,'Demo result is already recorded')
        official=_official_url(body.official_url)
        if urlsplit(official).hostname.lower()!=urlsplit(m.resolution_source_url).hostname.lower():
            raise HTTPException(422,'Evidence source host differs from draft; independently verify the official scorecard source')
        import json
        cfg=json.loads(m.source_config_json or '{}')
        if not cfg.get('demo_only'):raise HTTPException(409,'Market is not marked Demo-only')
        result=_resolve_observation(cfg,body)
        evidence=f'{official} | {body.evidence_note.strip()} | statistic={body.observed}, first_innings={body.team_a_runs}/{body.team_b_runs}, match_result={body.result}, void={body.void_reason}'
        db.add(DemoResolution(market_id=m.id,outcome=result,evidence=evidence[:500],resolved_by=u.id))
        db.add(DemoAdminAudit(admin_user_id=u.id,action='CRICKET_STAT_DEMO_RESOLVE',detail=f'market={m.id}; result={result}; source={official}'))
        db.flush()
        settled=_settle_due(db)
        db.commit()
        return {'market_id':m.id,'result':result,'recorded':True,'settled_demo_markets':settled,
                'note':'Admin-verified official scorecard, not automated data feed verification.'}

    app.include_router(router)
