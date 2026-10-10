"""LEMMIQ V2.10.6 additive endpoints: Q Thread read model.

The Q Thread is intentionally derived from existing Q-to-Q coordination rows.
It gives users a chat-like assistant inbox without copying personal chat text
into a second server-side store.
"""
import json
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .models import QCoordinationRequest, QThreadState, User

def _aware(dt):
    if dt is None:return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)

def _user(u):
    return {"id":u.id,"username":u.username,"display_name":u.display_name} if u else None

def register_v2106(app,current_user,get_db):
    router=APIRouter()

    @router.get("/v2106/q/thread")
    def q_thread(u=Depends(current_user),db:Session=Depends(get_db)):
        state=db.get(QThreadState,u.id)
        last_seen=_aware(state.last_seen_at) if state else None
        first_load_cutoff=datetime.now(timezone.utc)-timedelta(days=7)
        rows=db.scalars(select(QCoordinationRequest).where(
            or_(QCoordinationRequest.initiator_id==u.id,QCoordinationRequest.target_user_id==u.id)
        ).order_by(QCoordinationRequest.updated_at.desc()).limit(250)).all()
        out=[]
        for r in rows:
            initiator=db.get(User,r.initiator_id);target=db.get(User,r.target_user_id)
            other=target if r.initiator_id==u.id else initiator
            try:options=json.loads(r.options_json or "[]")
            except Exception:options=[]
            try:response=json.loads(r.response_json or "{}")
            except Exception:response={}
            mine=r.initiator_id==u.id
            ts=_aware(r.updated_at or r.created_at)
            if last_seen is None:
                # On first upgrade do not mark an entire historical Q-to-Q archive unread.
                # Surface only recent active/replied coordination as new attention.
                unread=bool(ts and ts>=first_load_cutoff and r.status in {"PENDING","RESPONDED"})
            else:
                unread=bool(ts and ts>last_seen)
            if mine:
                if r.status=="PENDING":
                    title=f"Waiting for {other.display_name if other else 'contact'}"
                    body=f"Q is waiting for a response to: {r.prompt}"
                elif r.status=="RESPONDED":
                    title=f"{other.display_name if other else 'Contact'} replied"
                    detail=(response.get("choice") or response.get("note") or "Response received").strip()
                    body=f"{detail} · {r.prompt}"
                elif r.status=="CLOSED":
                    title="Q-to-Q plan closed";body=r.prompt
                else:
                    title="Q-to-Q update";body=r.prompt
            else:
                if r.status=="PENDING":
                    title=f"{initiator.display_name if initiator else 'A contact'}'s Q needs your response"
                    body=r.prompt
                elif r.status=="RESPONDED":
                    detail=(response.get("choice") or response.get("note") or "Response sent").strip()
                    title="You responded to Q";body=f"{detail} · {r.prompt}"
                elif r.status=="CLOSED":
                    title="Q-to-Q request closed";body=r.prompt
                else:
                    title="Q-to-Q update";body=r.prompt
            out.append({
                "id":f"q2q-{r.id}-{r.status}","kind":"Q_TO_Q","title":title,"body":body,
                "created_at":ts.isoformat() if ts else r.created_at.isoformat(),"unread":unread,
                "request_id":r.id,"request_key":r.request_key,"status":r.status,"mine":mine,
                "other_user":_user(other),"options":options,"response":response,
                "can_respond":(not mine and r.status=="PENDING"),
                "can_cancel":(mine and r.status=="PENDING"),
            })
        return {"unread_count":sum(1 for x in out if x["unread"]),"items":out}

    @router.post("/v2106/q/thread/read")
    def q_thread_read(u=Depends(current_user),db:Session=Depends(get_db)):
        row=db.get(QThreadState,u.id)
        now=datetime.now(timezone.utc)
        if not row:
            row=QThreadState(user_id=u.id,last_seen_at=now,updated_at=now);db.add(row)
        else:
            row.last_seen_at=now;row.updated_at=now
        db.commit()
        return {"ok":True,"read_at":now.isoformat()}

    app.include_router(router)
