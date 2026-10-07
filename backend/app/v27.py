import base64
import json
import logging
import os
import re
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from . import media_store
from .chat_agent import daily_brief
from .models import QCoordinationRequest, SocialMemory, User, VisionMemory

MAX_VISION_BYTES = 15 * 1024 * 1024
VISION_MIME = {"image/jpeg", "image/png", "image/webp", "image/gif"}
logger = logging.getLogger("lemmiq.v27")

COORDINATION_HINTS = (
    "availability", "available", "find a time", "what time", "when can",
    "coordinate", "meeting", "meet", "dinner", "lunch", "catch up",
    "plan with", "which day", "which time", "poll", "vote", "works for everyone",
)

class VisionAskIn(BaseModel):
    question: str = Field(min_length=1, max_length=1600)

class VisionSaveIn(BaseModel):
    saved: bool = True

class CoordinationCreateIn(BaseModel):
    target_user_ids: list[int] = Field(min_length=1, max_length=8)
    kind: str = Field(default="PLAN", max_length=24)
    prompt: str = Field(min_length=1, max_length=1200)
    options: list[str] = Field(default_factory=list, max_length=20)

class CoordinationResponseIn(BaseModel):
    choice: str = Field(default="", max_length=160)
    note: str = Field(default="", max_length=600)

def _client():
    key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not key:
        raise HTTPException(503, "Q Vision needs ANTHROPIC_API_KEY on the server.")
    from anthropic import Anthropic
    return Anthropic(api_key=key)

def _model():
    return os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")

def _read_object(key: str) -> bytes:
    out = bytearray()
    for part in media_store.stream(key):
        out.extend(part)
        if len(out) > MAX_VISION_BYTES:
            raise HTTPException(413, "Vision image is too large")
    return bytes(out)

def _json_text(message):
    raw = "".join(x.text for x in message.content if getattr(x, "type", "") == "text").strip()
    fence = chr(96) * 3
    if raw.startswith(fence + "json"):
        raw = raw[len(fence + "json"):].strip()
    if raw.endswith(fence):
        raw = raw[:-3].strip()
    return json.loads(raw)

def _sniff_image_mime(data: bytes, declared: str = "") -> str:
    """Return the actual supported image MIME from file signatures.

    Android content providers sometimes report image/jpeg for PNG content.
    Q Vision must send a media_type that matches the actual base64 bytes.
    """
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    clean = (declared or "").split(";")[0].strip().lower()
    return clean if clean in VISION_MIME else ""


def _vision_ai(data: bytes, mime: str, question: str, prior: dict | None = None):
    mime = _sniff_image_mime(data, mime)
    if mime not in VISION_MIME:
        raise HTTPException(415, "Q Vision could not identify a supported image format.")
    encoded = base64.b64encode(data).decode("ascii")
    prior_text = ""
    if prior:
        prior_text = "\nPREVIOUS SAVED ANALYSIS:\n" + json.dumps(prior, ensure_ascii=False)[:7000] + "\n"
    prompt = """You are Q Vision inside LEMMIQ.
Analyse the supplied image and answer the user's request.
Be practical and concise. Do not identify real people in photos.
If text is visible, extract useful text accurately. If uncertain, say so.
Never invent serial numbers, prices, diagnoses, legal conclusions, or exact product models.

%s
USER REQUEST:
%s

Return JSON only:
{
  "title":"short useful title",
  "category":"DOCUMENT|SCREENSHOT|PRODUCT|VEHICLE|EQUIPMENT|FOOD|PLACE|RECEIPT|OTHER",
  "summary":"direct answer to the user's request",
  "extracted_text":"useful visible text, or empty string",
  "details":["detail 1","detail 2"],
  "suggested_actions":["Ask another question","Save","Share"]
}
""" % (prior_text, question)
    try:
        m = _client().messages.create(
            model=_model(), max_tokens=1200, temperature=0,
            messages=[{"role":"user","content":[
                {"type":"image","source":{"type":"base64","media_type":mime,"data":encoded}},
                {"type":"text","text":prompt},
            ]}],
        )
        result = _json_text(m)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Q Vision provider analysis failed")
        raise HTTPException(502, "Q Vision couldn't analyse this image right now. Please retry.")
    result["category"] = str(result.get("category") or "OTHER").upper()[:32]
    result["title"] = str(result.get("title") or "Vision scan")[:160]
    result["summary"] = str(result.get("summary") or "")
    result["extracted_text"] = str(result.get("extracted_text") or "")
    if not isinstance(result.get("details"), list):
        result["details"] = []
    if not isinstance(result.get("suggested_actions"), list):
        result["suggested_actions"] = []
    return result

def _vision_json(row: VisionMemory):
    try:
        analysis = json.loads(row.analysis_json or "{}")
    except Exception:
        analysis = {}
    try:
        history = json.loads(row.history_json or "[]")
    except Exception:
        history = []
    return {
        "id": row.id, "title": row.title, "category": row.category,
        "summary": row.summary, "extracted_text": row.extracted_text,
        "analysis": analysis, "history": history, "saved": bool(row.saved),
        "mime_type": row.mime_type, "original_name": row.original_name,
        "media_url": f"/v27/vision/{row.id}/media",
        "created_at": row.created_at.isoformat(), "updated_at": row.updated_at.isoformat(),
    }

def _is_coordination(prompt: str, options: list[str]):
    q = (prompt or "").lower()
    if len([x for x in options if str(x).strip()]) >= 2:
        return True
    return any(h in q for h in COORDINATION_HINTS)

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
        "id": row.id, "request_key": row.request_key, "kind": row.kind,
        "prompt": row.prompt, "options": options, "response": response,
        "status": row.status, "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(), "expires_at": row.expires_at.isoformat(),
        "initiator": {"id":initiator.id,"username":initiator.username,"display_name":initiator.display_name} if initiator else None,
        "target": {"id":target.id,"username":target.username,"display_name":target.display_name} if target else None,
        "mine": row.initiator_id == viewer_id,
    }

def register_v27(app, current_user, get_db, push):
    router = APIRouter()
    dep_db = get_db

    @router.get("/v27/q/home")
    def q_home(u=Depends(current_user), db: Session = Depends(dep_db)):
        brief = daily_brief(db, u.id)
        memories = db.scalars(
            select(SocialMemory)
            .where(SocialMemory.user_id == u.id, SocialMemory.resolved == False)
            .order_by(SocialMemory.created_at.desc()).limit(100)
        ).all()
        pending = db.scalars(
            select(QCoordinationRequest)
            .where(or_(QCoordinationRequest.initiator_id == u.id, QCoordinationRequest.target_user_id == u.id),
                   QCoordinationRequest.status == "PENDING")
            .order_by(QCoordinationRequest.created_at.desc()).limit(100)
        ).all()
        valid_pending = []
        for x in pending:
            try:
                opts = json.loads(x.options_json or "[]")
            except Exception:
                opts = []
            if _is_coordination(x.prompt, opts):
                valid_pending.append(x)
        vision_count = len(db.scalars(
            select(VisionMemory.id).where(VisionMemory.user_id == u.id, VisionMemory.saved == True)
        ).all())
        return {
            "today": {
                "summary": brief.get("summary", ""),
                "unread_total": brief.get("unread_total", 0),
                "needs_reply_count": brief.get("needs_reply_count", 0),
                "needs_reply": brief.get("needs_reply", [])[:3],
                "follow_ups": sum(1 for x in memories if x.memory_type in {"FOLLOW_UP","DEADLINE"} and not x.resolved),
                "promises": sum(1 for x in memories if x.memory_type == "PROMISE" and not x.resolved),
            },
            "memory": {"count": len(memories), "vision_count": vision_count},
            "q_to_q": {
                "pending_count": len(valid_pending),
                "incoming_count": sum(1 for x in valid_pending if x.target_user_id == u.id),
                "outgoing_count": sum(1 for x in valid_pending if x.initiator_id == u.id),
            },
        }

    @router.post("/v27/vision")
    async def vision_analyze(
        file: UploadFile = File(...),
        question: str = Form(default="What is in this image? Give me the useful details."),
        save: bool = Form(default=True),
        u=Depends(current_user), db: Session = Depends(dep_db),
    ):
        declared_mime = (file.content_type or "").split(";")[0].strip().lower()
        data = await file.read(MAX_VISION_BYTES + 1)
        if not data:
            raise HTTPException(400, "Image is empty")
        if len(data) > MAX_VISION_BYTES:
            raise HTTPException(413, "Q Vision image limit is 15 MB")
        mime = _sniff_image_mime(data, declared_mime)
        if mime not in VISION_MIME:
            raise HTTPException(415, "Q Vision currently supports JPG, PNG, WEBP and GIF images.")
        analysis = _vision_ai(data, mime, question)
        key = media_store.store(data)
        history = [{"role":"user","text":question},{"role":"q","text":analysis["summary"]}]
        row = VisionMemory(
            user_id=u.id, object_key=key, original_name=(file.filename or "image")[:200],
            mime_type=mime, category=analysis["category"], title=analysis["title"],
            summary=analysis["summary"], extracted_text=analysis["extracted_text"],
            analysis_json=json.dumps(analysis, ensure_ascii=False),
            history_json=json.dumps(history, ensure_ascii=False), saved=save,
        )
        db.add(row)
        try:
            from .v29 import track_shadow_event
            track_shadow_event(db,u.id,"Q_VISION",success=True)
        except Exception:
            pass
        db.commit(); db.refresh(row)
        return _vision_json(row)

    @router.get("/v27/vision")
    def vision_list(q: str = "", category: str = "", saved_only: bool = True, u=Depends(current_user), db: Session = Depends(dep_db)):
        stmt = select(VisionMemory).where(VisionMemory.user_id == u.id)
        if saved_only:
            stmt = stmt.where(VisionMemory.saved == True)
        if category.strip():
            stmt = stmt.where(VisionMemory.category == category.strip().upper())
        rows = db.scalars(stmt.order_by(VisionMemory.updated_at.desc()).limit(200)).all()
        term = q.strip().lower()
        if term:
            rows = [x for x in rows if term in f"{x.title} {x.summary} {x.extracted_text} {x.category}".lower()]
        return [_vision_json(x) for x in rows[:100]]

    @router.get("/v27/vision/{vision_id}")
    def vision_detail(vision_id: int, u=Depends(current_user), db: Session = Depends(dep_db)):
        row = db.get(VisionMemory, vision_id)
        if not row or row.user_id != u.id:
            raise HTTPException(404, "Vision memory not found")
        return _vision_json(row)

    @router.get("/v27/vision/{vision_id}/media")
    def vision_media(vision_id: int, u=Depends(current_user), db: Session = Depends(dep_db)):
        row = db.get(VisionMemory, vision_id)
        if not row or row.user_id != u.id:
            raise HTTPException(404, "Vision memory not found")
        return StreamingResponse(media_store.stream(row.object_key), media_type=row.mime_type, headers={"Cache-Control":"private, no-store"})

    @router.post("/v27/vision/{vision_id}/ask")
    def vision_ask(vision_id: int, body: VisionAskIn, u=Depends(current_user), db: Session = Depends(dep_db)):
        row = db.get(VisionMemory, vision_id)
        if not row or row.user_id != u.id:
            raise HTTPException(404, "Vision memory not found")
        data = _read_object(row.object_key)
        try:
            prior = json.loads(row.analysis_json or "{}")
            history = json.loads(row.history_json or "[]")
        except Exception:
            prior, history = {}, []
        actual_mime = _sniff_image_mime(data, row.mime_type)
        if actual_mime and actual_mime != row.mime_type:
            row.mime_type = actual_mime
        result = _vision_ai(data, actual_mime or row.mime_type, body.question.strip(), prior=prior)
        history += [{"role":"user","text":body.question.strip()},{"role":"q","text":result["summary"]}]
        row.title = result.get("title") or row.title
        row.category = result.get("category") or row.category
        row.summary = result.get("summary") or row.summary
        row.extracted_text = result.get("extracted_text") or row.extracted_text
        row.analysis_json = json.dumps(result, ensure_ascii=False)
        row.history_json = json.dumps(history[-40:], ensure_ascii=False)
        row.updated_at = datetime.now(timezone.utc)
        try:
            from .v29 import track_shadow_event
            track_shadow_event(db,u.id,"Q_VISION",success=True,note="follow-up")
        except Exception:
            pass
        db.commit()
        return _vision_json(row)

    @router.put("/v27/vision/{vision_id}/save")
    def vision_save(vision_id: int, body: VisionSaveIn, u=Depends(current_user), db: Session = Depends(dep_db)):
        row = db.get(VisionMemory, vision_id)
        if not row or row.user_id != u.id:
            raise HTTPException(404, "Vision memory not found")
        row.saved = body.saved; row.updated_at = datetime.now(timezone.utc); db.commit()
        return _vision_json(row)

    @router.delete("/v27/vision/{vision_id}")
    def vision_delete(vision_id: int, u=Depends(current_user), db: Session = Depends(dep_db)):
        row = db.get(VisionMemory, vision_id)
        if not row or row.user_id != u.id:
            raise HTTPException(404, "Vision memory not found")
        db.delete(row); db.commit()
        return {"ok": True}

    @router.post("/v27/q/coordination")
    async def create_coordination(body: CoordinationCreateIn, u=Depends(current_user), db: Session = Depends(dep_db)):
        options = [str(x).strip()[:160] for x in body.options if str(x).strip()][:20]
        if not _is_coordination(body.prompt, options):
            raise HTTPException(400, "Q-to-Q is only for shared planning, availability or polls. Use normal Q for summaries, promises and personal questions.")
        ids = list(dict.fromkeys(int(x) for x in body.target_user_ids if int(x) != u.id))
        if not ids:
            raise HTTPException(400, "Choose at least one other LEMMIQ user")
        targets = db.scalars(select(User).where(User.id.in_(ids))).all()
        if len(targets) != len(ids):
            raise HTTPException(404, "One or more LEMMIQ users were not found")
        norm = re.sub(r"\s+", " ", body.prompt.strip().lower())
        existing = db.scalars(
            select(QCoordinationRequest).where(QCoordinationRequest.initiator_id == u.id,
                                               QCoordinationRequest.status == "PENDING")
            .order_by(QCoordinationRequest.created_at.desc()).limit(100)
        ).all()
        for x in existing:
            if re.sub(r"\s+", " ", x.prompt.strip().lower()) == norm and x.target_user_id in ids:
                raise HTTPException(409, "A matching Q-to-Q plan is already waiting for a response.")
        key = uuid.uuid4().hex; now = datetime.now(timezone.utc); rows = []
        for target in targets:
            row = QCoordinationRequest(
                request_key=key, initiator_id=u.id, target_user_id=target.id,
                kind=(body.kind or "PLAN").strip().upper(), prompt=body.prompt.strip(),
                options_json=json.dumps(options, ensure_ascii=False), response_json="{}",
                status="PENDING", created_at=now, updated_at=now, expires_at=now + timedelta(days=7),
            )
            db.add(row); rows.append(row)
        try:
            from .v29 import track_shadow_event
            track_shadow_event(db,u.id,"Q_TO_Q",success=True,note=f"{len(rows)} participant(s)")
        except Exception:
            pass
        db.commit()
        for row in rows:
            db.refresh(row)
            await push(row.target_user_id, {
                "type":"q_coordination_request","request_id":row.id,"request_key":key,
                "kind":row.kind,"from_user":{"id":u.id,"username":u.username,"display_name":u.display_name},
                "prompt":row.prompt,
            })
        return {"request_key":key,"requests":[_coord_json(db,x,u.id) for x in rows]}

    @router.get("/v27/q/coordination")
    def coordination_list(u=Depends(current_user), db: Session = Depends(dep_db)):
        rows = db.scalars(
            select(QCoordinationRequest).where(
                or_(QCoordinationRequest.initiator_id == u.id, QCoordinationRequest.target_user_id == u.id)
            ).order_by(QCoordinationRequest.created_at.desc()).limit(250)
        ).all()
        valid = []
        for x in rows:
            try:
                opts = json.loads(x.options_json or "[]")
            except Exception:
                opts = []
            if _is_coordination(x.prompt, opts):
                valid.append(x)
        incoming = [x for x in valid if x.target_user_id == u.id]
        outgoing = [x for x in valid if x.initiator_id == u.id]
        return {"inbox":[_coord_json(db,x,u.id) for x in incoming],
                "outbox":[_coord_json(db,x,u.id) for x in outgoing]}

    @router.post("/v27/q/coordination/{request_id}/respond")
    async def respond_coordination(request_id: int, body: CoordinationResponseIn, u=Depends(current_user), db: Session = Depends(dep_db)):
        row = db.get(QCoordinationRequest, request_id)
        if not row or row.target_user_id != u.id:
            raise HTTPException(404, "Coordination request not found")
        if row.status != "PENDING":
            raise HTTPException(409, f"Request is {row.status.lower()}")
        row.response_json = json.dumps({"choice":body.choice.strip(),"note":body.note.strip()}, ensure_ascii=False)
        row.status = "RESPONDED"; row.updated_at = datetime.now(timezone.utc); db.commit()
        await push(row.initiator_id, {
            "type":"q_coordination_response","request_id":row.id,"request_key":row.request_key,
            "from_user":{"id":u.id,"username":u.username,"display_name":u.display_name},
            "response":json.loads(row.response_json),
        })
        return _coord_json(db,row,u.id)

    @router.delete("/v27/q/coordination/{request_key}")
    async def cancel_coordination(request_key: str, u=Depends(current_user), db: Session = Depends(dep_db)):
        rows = db.scalars(
            select(QCoordinationRequest).where(QCoordinationRequest.request_key == request_key,
                                               QCoordinationRequest.initiator_id == u.id)
        ).all()
        if not rows:
            raise HTTPException(404, "Q-to-Q plan not found")
        now = datetime.now(timezone.utc)
        for row in rows:
            if row.status == "PENDING":
                row.status = "CLOSED"; row.updated_at = now
        db.commit()
        for row in rows:
            await push(row.target_user_id, {"type":"q_coordination_closed","request_key":request_key})
        return {"ok": True}

    app.include_router(router)
