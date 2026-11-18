"""LEMMIQ V2.13.7 — provider-independent cricket fixtures and review-only draft generation.
Data source is opt-in: operator must have permission to reuse fixtures commercially.
No automatic Q settlement or staking activation in this module.
"""
from __future__ import annotations
import json, logging, os, time
from datetime import datetime, timezone, timedelta
from urllib.parse import urlsplit
import requests
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from .models import User
from .v29 import PredictMarketIn, PredictMarket, _create_market, _require_admin

log = logging.getLogger('lemmiq.v2137')
_cache = {'at': 0.0, 'items': [], 'error': ''}
MAX_ITEMS = 500

def _source_url():
    url = os.environ.get('LEMMIQ_CRICKET_FEED_URL','').strip()
    if not url: return ''
    u = urlsplit(url)
    if u.scheme != 'https' or not u.hostname or u.username or u.password or u.port or u.fragment:
        raise ValueError('Cricket source must be an HTTPS URL without credentials or fragment')
    # Explicit hostname allowlist: never send server requests to internal/private hosts.
    hosts = {x.strip().lower() for x in os.environ.get('LEMMIQ_CRICKET_ALLOWED_HOSTS','').split(',') if x.strip()}
    if not hosts or u.hostname.lower() not in hosts:
        raise ValueError('Cricket source hostname not in LEMMIQ_CRICKET_ALLOWED_HOSTS')
    return url

def _iso(value):
    if not value: return None
    try:
        if isinstance(value,(int,float)):
            return datetime.fromtimestamp(value/1000 if value>1e11 else value,tz=timezone.utc)
        d=datetime.fromisoformat(str(value).replace('Z','+00:00'))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except (ValueError,OverflowError,TypeError):return None

def _normalize(x):
    if not isinstance(x,dict): return None
    a=str(x.get('teamAName') or x.get('team_a') or '').strip()[:90]
    b=str(x.get('teamBName') or x.get('team_b') or '').strip()[:90]
    when=_iso(x.get('startTimeUtc') or x.get('start_time') or x.get('startTime'))
    mid=str(x.get('sourceMatchId') or x.get('id') or '').strip()[:70]
    if not (a and b and a.casefold()!=b.casefold() and when and mid): return None
    return {
        'id':mid, 'series':str(x.get('seriesName') or x.get('series') or 'Cricket')[:120],
        'category':str(x.get('category') or 'OTHER').upper()[:32],
        'format':str(x.get('format') or '').upper()[:12],
        'team_a':a, 'team_b':b, 'start_at':when.isoformat(),
        'status':str(x.get('status') or 'UPCOMING').upper()[:24],
        'venue':str(x.get('venue') or '')[:120], 'country':str(x.get('country') or '')[:80],
    }

def fixtures(force=False):
    now=time.monotonic()
    if not force and now-_cache['at']<900: return list(_cache['items'])
    url=_source_url()
    if not url: return []
    r=requests.get(url,timeout=12,allow_redirects=False,headers={'User-Agent':'LEMMIQ-Fixture-Importer/2.13.7','Accept':'application/json'})
    r.raise_for_status()
    if len(r.content)>1_500_000:raise ValueError('Cricket fixture response too large')
    payload=r.json()
    rows=payload if isinstance(payload,list) else payload.get('matches',payload.get('data',[]))
    if not isinstance(rows,list):raise ValueError('Fixture source must return a JSON list')
    uniq={}
    for x in rows[:MAX_ITEMS]:
        m=_normalize(x)
        if m:uniq[m['id']]=m
    result=sorted(uniq.values(),key=lambda m:m['start_at'])
    _cache.update(at=now,items=result,error='')
    return list(result)


def draft_fixture_markets(db:Session, creator_id=None):
    rows=fixtures(force=True)
    created=[];now=datetime.now(timezone.utc)
    existing=db.query(PredictMarket).filter(PredictMarket.template_code=='CRICKET_WINNER_V2137').all()
    for m in rows:
        when=_iso(m['start_at'])
        if m['format'] not in {'T20','ODI'} or m['status']!='UPCOMING' or not when or when<now+timedelta(hours=2) or when>now+timedelta(days=14):continue
        if len(created)>=30:break
        question=f"Will {m['team_a']} defeat {m['team_b']} in {m['series']}?"
        if len(question)>260:continue
        source={'match_id':m['id'],'team_a':m['team_a'],'team_b':m['team_b'],'series':m['series']}
        body=PredictMarketIn(
            question=question,category='SPORTS',template_code='CRICKET_WINNER_V2137',
            close_at=when-timedelta(minutes=10),resolve_after=when+timedelta(hours=8),
            resolution_source_name='Official result: manual verification required',
            resolution_rule='YES if named first team is officially declared winner. NO if named opponent wins. VOID on tie, no-result, abandonment, inconclusive official result or disputed feed.',
            source_type='MANUAL',source_config=source,trend_score=60,resolution_confidence=0,auto_resolve=False)
        if any(json.loads(x.source_config_json or '{}').get('match_id')==m['id'] for x in existing):continue
        row=_create_market(db,body,creator_id=creator_id,generated_by='CRICKET_FIXTURE_AGENT',status='REVIEW',reason='Imported candidate; Admin must verify fixture and result rules before publication.')
        created.append(row.id)
    return created

def register_v2137_cricket(app,current_user,get_db,push_tokens):
    from . import push_service
    router=APIRouter(prefix='/v2137',tags=['LEMMIQ V2.13.7'])
    last_test={}

    @router.get('/cricket/fixtures')
    def list_fixtures(u:User=Depends(current_user)):
        try:rows=fixtures()
        except Exception as e:
            log.warning('Cricket feed unavailable: %s',type(e).__name__)
            return {'configured':bool(os.getenv('LEMMIQ_CRICKET_FEED_URL')),'fixtures':[], 'error':'Cricket data temporarily unavailable'}
        future=[m for m in rows if _iso(m['start_at']) > datetime.now(timezone.utc)-timedelta(minutes=10)]
        return {'configured':bool(os.getenv('LEMMIQ_CRICKET_FEED_URL')),'fixtures':future[:250], 'count':len(future), 'note':'Fixtures are informational until verified and published by Admin. Never a settlement source.'}

    @router.post('/cricket/admin/draft')
    def draft_cricket(u:User=Depends(current_user),db:Session=Depends(get_db)):
        _require_admin(db,u,'WRITE')
        try:created=draft_fixture_markets(db,creator_id=u.id)
        except Exception:
            log.exception('Cricket draft import failed')
            raise HTTPException(503,'Fixture provider is unavailable')
        db.commit()
        return {'drafted':len(created),'market_ids':created,'mode':'ADMIN_REVIEW_ONLY'}

    @router.get('/notifications/status')
    def notification_status(u:User=Depends(current_user),db:Session=Depends(get_db)):
        tokens=push_tokens(db,u.id)
        return {'firebase_server':push_service.configured(),'web_devices':sum(1 for t in tokens if t.startswith('WEB:')),'android_devices':sum(1 for t in tokens if not t.startswith('WEB:'))}

    @router.post('/notifications/test')
    def notification_test(u:User=Depends(current_user),db:Session=Depends(get_db)):
        from fastapi import BackgroundTasks
        now=time.monotonic();last=last_test.get(u.id,0)
        if now-last<60:raise HTTPException(429,'Wait one minute before sending another test')
        tokens=push_tokens(db,u.id)
        if not tokens or not push_service.configured():raise HTTPException(409,'No registered push devices or Firebase sender unavailable')
        last_test[u.id]=now
        push_service.notify_data(tokens,{'type':'test','title':'LEMMIQ notification test','body':'Test delivery: your device should show an alert.'})
        return {'attempted_devices':len(tokens),'delivery':'NOT_CONFIRMED','note':'FCM accepted attempts are not proof the device displayed the alert.'}

    app.include_router(router)
