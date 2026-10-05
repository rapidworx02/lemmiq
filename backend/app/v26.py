import json
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .chat_agent import ask_agent, daily_brief
from .models import QCoordinationRequest, SocialMemory, User


class QDoIn(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


class CoordinationCreateIn(BaseModel):
    target_user_ids: list[int] = Field(min_length=1, max_length=8)
    kind: str = Field(default="PLAN", max_length=24)
    prompt: str = Field(min_length=1, max_length=1200)
    options: list[str] = Field(default_factory=list, max_length=20)


class CoordinationResponseIn(BaseModel):
    choice: str = Field(default="", max_length=160)
    note: str = Field(default="", max_length=600)


def register_v26(app, current_user, get_db, push, user_json):
    router = APIRouter()
    dep_db = get_db

    def _memory_json(db: Session, row: SocialMemory):
        contact = None
        if row.chat_id:
            from .models import Chat
            chat = db.get(Chat, row.chat_id)
            if chat:
                other_id = chat.user2_id if chat.user1_id == row.user_id else chat.user1_id
                other = db.get(User, other_id)
                if other:
                    contact = user_json(other)
        return {
            "id": row.id,
            "type": row.memory_type,
            "title": row.title,
            "detail": row.detail,
            "due_at": row.due_at.isoformat() if row.due_at else None,
            "resolved": bool(row.resolved),
            "created_at": row.created_at.isoformat(),
            "contact": contact,
        }

    def _coord_json(db: Session, row: QCoordinationRequest, viewer_id: int):
        initiator = db.get(User, row.initiator_id)
        target = db.get(User, row.target_user_id)
        try:
            options = json.loads(row.options_json or "[]")
        except Exception:
            options = []
        try:
            response = json.loads(row.response_json or "{}")
        except Exception:
            response = {}
        return {
            "id": row.id,
            "request_key": row.request_key,
            "kind": row.kind,
            "prompt": row.prompt,
            "options": options,
            "response": response,
            "status": row.status,
            "created_at": row.created_at.isoformat(),
            "updated_at": row.updated_at.isoformat(),
            "expires_at": row.expires_at.isoformat(),
            "initiator": user_json(initiator) if initiator else None,
            "target": user_json(target) if target else None,
            "mine": row.initiator_id == viewer_id,
        }

    @router.get("/v26/q/brief")
    def q_daily_brief(u=Depends(current_user), db: Session = Depends(dep_db)):
        brief = daily_brief(db, u.id)
        memories = db.scalars(
            select(SocialMemory)
            .where(SocialMemory.user_id == u.id, SocialMemory.resolved == False)  # noqa: E712
            .order_by(SocialMemory.due_at.asc().nullslast(), SocialMemory.created_at.desc())
            .limit(20)
        ).all()
        due = [_memory_json(db, x) for x in memories]
        promises = [x for x in due if x["type"] == "PROMISE"]
        follow_ups = [x for x in due if x["type"] == "FOLLOW_UP"]
        return {
            "summary": brief.get("summary", ""),
            "unread_total": brief.get("unread_total", 0),
            "needs_reply_count": brief.get("needs_reply_count", 0),
            "needs_reply": brief.get("needs_reply", []),
            "commitments": due,
            "promises": promises,
            "follow_ups": follow_ups,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    @router.post("/v26/q/do")
    def q_do_plan(body: QDoIn, u=Depends(current_user), db: Session = Depends(dep_db)):
        """Plan an agent action without silently performing external side effects.

        V2.6 Do mode may read/summarise automatically. Sending messages or starting
        coordination is returned as an approval-required action.
        """
        question = body.question.strip()
        answer = ask_agent(db, u.id, question, 30, [])
        q = question.lower()
        actions = []

        if any(k in q for k in ("promise", "commitment", "follow up", "follow-up", "what did i say i would")):
            actions.append({
                "type": "SCAN_COMMITMENTS",
                "label": "Scan recent commitments",
                "approval_required": False,
                "permission": "SAFE",
            })
        if any(k in q for k in ("availability", "find a time", "coordinate", "plan with", "meet with", "meeting with")):
            actions.append({
                "type": "Q_TO_Q",
                "label": "Coordinate with LEMMIQ contacts",
                "approval_required": True,
                "permission": "APPROVAL",
            })
        if any(k in q for k in ("reply", "respond", "message", "send")):
            actions.append({
                "type": "DRAFT_REPLY",
                "label": "Prepare a reply",
                "approval_required": False,
                "permission": "SAFE",
            })
            actions.append({
                "type": "SEND_MESSAGE",
                "label": "Send a message",
                "approval_required": True,
                "permission": "APPROVAL",
                "available": False,
                "note": "V2.6 never sends from Q without an explicit in-chat confirmation.",
            })

        return {
            "mode": "DO",
            "answer": answer.get("answer", "") if isinstance(answer, dict) else str(answer),
            "references": answer.get("references", []) if isinstance(answer, dict) else [],
            "actions": actions,
            "policy": {
                "safe": "Read, search, summarise and draft.",
                "approval": "Sending messages, changing plans and Q-to-Q requests.",
                "confirm": "Payments, deleting data, sharing private data and account/security changes.",
            },
        }

    @router.post("/v26/q/coordination")
    async def create_coordination(body: CoordinationCreateIn, u=Depends(current_user), db: Session = Depends(dep_db)):
        ids = list(dict.fromkeys(int(x) for x in body.target_user_ids if int(x) != u.id))
        if not ids:
            raise HTTPException(400, "Choose at least one other LEMMIQ user")
        targets = db.scalars(select(User).where(User.id.in_(ids))).all()
        if len(targets) != len(ids):
            raise HTTPException(404, "One or more LEMMIQ users were not found")

        kind = body.kind.strip().upper() or "PLAN"
        if kind not in {"PLAN", "AVAILABILITY", "POLL"}:
            raise HTTPException(400, "Unsupported coordination type")
        options = [str(x).strip()[:160] for x in body.options if str(x).strip()][:20]
        key = uuid.uuid4().hex
        now = datetime.now(timezone.utc)
        expires = now + timedelta(days=7)

        rows = []
        for target in targets:
            row = QCoordinationRequest(
                request_key=key,
                initiator_id=u.id,
                target_user_id=target.id,
                kind=kind,
                prompt=body.prompt.strip(),
                options_json=json.dumps(options, ensure_ascii=False),
                response_json="{}",
                status="PENDING",
                created_at=now,
                updated_at=now,
                expires_at=expires,
            )
            db.add(row)
            rows.append(row)
        db.commit()
        for row in rows:
            db.refresh(row)
            await push(row.target_user_id, {
                "type": "q_coordination_request",
                "request_id": row.id,
                "request_key": key,
                "kind": kind,
                "from_user": user_json(u),
                "prompt": row.prompt,
            })

        return {
            "request_key": key,
            "count": len(rows),
            "requests": [_coord_json(db, x, u.id) for x in rows],
            "note": "Only the explicit request and options are shared. Private chat memory is not exposed.",
        }

    @router.get("/v26/q/coordination")
    def coordination_list(u=Depends(current_user), db: Session = Depends(dep_db)):
        now = datetime.now(timezone.utc)
        incoming = db.scalars(
            select(QCoordinationRequest)
            .where(QCoordinationRequest.target_user_id == u.id)
            .order_by(QCoordinationRequest.created_at.desc())
            .limit(100)
        ).all()
        outgoing = db.scalars(
            select(QCoordinationRequest)
            .where(QCoordinationRequest.initiator_id == u.id)
            .order_by(QCoordinationRequest.created_at.desc())
            .limit(100)
        ).all()

        changed = False
        for row in incoming + outgoing:
            if row.status == "PENDING" and row.expires_at < now:
                row.status = "EXPIRED"
                row.updated_at = now
                changed = True
        if changed:
            db.commit()

        return {
            "inbox": [_coord_json(db, x, u.id) for x in incoming],
            "outbox": [_coord_json(db, x, u.id) for x in outgoing],
        }

    @router.post("/v26/q/coordination/{request_id}/respond")
    async def respond_coordination(request_id: int, body: CoordinationResponseIn, u=Depends(current_user), db: Session = Depends(dep_db)):
        row = db.get(QCoordinationRequest, request_id)
        if not row or row.target_user_id != u.id:
            raise HTTPException(404, "Coordination request not found")
        if row.status != "PENDING":
            raise HTTPException(409, f"Request is {row.status.lower()}")
        now = datetime.now(timezone.utc)
        if row.expires_at < now:
            row.status = "EXPIRED"
            row.updated_at = now
            db.commit()
            raise HTTPException(409, "Coordination request expired")

        response = {"choice": body.choice.strip(), "note": body.note.strip()}
        row.response_json = json.dumps(response, ensure_ascii=False)
        row.status = "RESPONDED"
        row.updated_at = now
        db.commit()
        await push(row.initiator_id, {
            "type": "q_coordination_response",
            "request_id": row.id,
            "request_key": row.request_key,
            "from_user": user_json(u),
            "response": response,
        })
        return _coord_json(db, row, u.id)

    @router.get("/v26/q/coordination/{request_key}/summary")
    def coordination_summary(request_key: str, u=Depends(current_user), db: Session = Depends(dep_db)):
        rows = db.scalars(
            select(QCoordinationRequest)
            .where(QCoordinationRequest.request_key == request_key, QCoordinationRequest.initiator_id == u.id)
            .order_by(QCoordinationRequest.id.asc())
        ).all()
        if not rows:
            raise HTTPException(404, "Coordination request not found")
        counts = {}
        for row in rows:
            try:
                choice = (json.loads(row.response_json or "{}").get("choice") or "").strip()
            except Exception:
                choice = ""
            if choice:
                counts[choice] = counts.get(choice, 0) + 1
        best = sorted(counts.items(), key=lambda x: (-x[1], x[0]))[0][0] if counts else None
        return {
            "request_key": request_key,
            "total": len(rows),
            "responded": sum(1 for x in rows if x.status == "RESPONDED"),
            "pending": sum(1 for x in rows if x.status == "PENDING"),
            "consensus": best,
            "choice_counts": counts,
            "requests": [_coord_json(db, x, u.id) for x in rows],
        }

    @router.post("/v26/q/coordination/{request_key}/close")
    async def close_coordination(request_key: str, u=Depends(current_user), db: Session = Depends(dep_db)):
        rows = db.scalars(
            select(QCoordinationRequest)
            .where(QCoordinationRequest.request_key == request_key, QCoordinationRequest.initiator_id == u.id)
        ).all()
        if not rows:
            raise HTTPException(404, "Coordination request not found")
        now = datetime.now(timezone.utc)
        for row in rows:
            if row.status == "PENDING":
                row.status = "CLOSED"
                row.updated_at = now
        db.commit()
        for row in rows:
            await push(row.target_user_id, {
                "type": "q_coordination_closed",
                "request_id": row.id,
                "request_key": request_key,
            })
        return {"ok": True}

    app.include_router(router)
