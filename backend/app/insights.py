"""User-scoped, opt-in structured notification insights. Raw notifications are never sent."""
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from .models import InsightEvent

CATEGORIES = {"MONEY", "BILL", "DELIVERY", "WORK", "TRAVEL", "TRUST", "GENERAL"}
DIRECTIONS = {"OUT", "IN", "UNKNOWN"}

def event_json(e):
    return {"id":e.id, "client_event_id":e.client_event_id, "category":e.category,
            "source":e.source, "title":e.title, "detail":e.detail,
            "amount_cents":e.amount_cents, "direction":e.direction,
            "occurred_at":e.occurred_at.isoformat()}

def list_events(db:Session, uid:int, days:int=30, limit:int=150):
    cutoff=datetime.now(timezone.utc)-timedelta(days=max(1,min(90,days)))
    rows=db.scalars(select(InsightEvent).where(InsightEvent.user_id==uid,
      InsightEvent.occurred_at>=cutoff).order_by(InsightEvent.occurred_at.desc()).limit(limit)).all()
    return [event_json(e) for e in rows]

def brief(db:Session,uid:int,days:int=30):
    events=list_events(db,uid,days,500)
    spending=sum(e['amount_cents'] or 0 for e in events if e['category']=='MONEY' and e['direction']=='OUT')
    incoming=sum(e['amount_cents'] or 0 for e in events if e['category']=='MONEY' and e['direction']=='IN')
    breakdown={}
    for e in events: breakdown[e['category']]=breakdown.get(e['category'],0)+1
    return {"spending_cents":spending, "incoming_cents":incoming,
       "transactions":sum(e['category']=='MONEY' for e in events),
       "detected_count":len(events), "categories":breakdown,
       "events":events[:35], "note":"Detected from permitted notification alerts only. Not a complete bank statement or verified balance."}
