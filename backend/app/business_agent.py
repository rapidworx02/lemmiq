import io
import json
import os
import re
from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy import select, or_
from sqlalchemy.orm import Session

from .models import (
    User, Chat, Message, BusinessProfile, BusinessKnowledge,
    BusinessChatSetting, BusinessCustomerMemory,
)


def _anthropic():
    key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not key:
        return None
    from anthropic import Anthropic
    return Anthropic(api_key=key)


def _model():
    return os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")


def profile_for(db: Session, uid: int, create: bool = True):
    p = db.get(BusinessProfile, uid)
    if not p and create:
        p = BusinessProfile(user_id=uid)
        db.add(p)
        db.commit()
        db.refresh(p)
    return p


def chat_setting_for(db: Session, uid: int, cid: int, create: bool = True):
    row = db.get(BusinessChatSetting, {"user_id": uid, "chat_id": cid})
    if not row and create:
        row = BusinessChatSetting(user_id=uid, chat_id=cid)
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def customer_memory_for(db: Session, uid: int, cid: int, create: bool = True):
    row = db.get(BusinessCustomerMemory, {"user_id": uid, "chat_id": cid})
    if not row and create:
        row = BusinessCustomerMemory(user_id=uid, chat_id=cid)
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def profile_json(p: BusinessProfile):
    return {
        "enabled": p.enabled,
        "business_name": p.business_name or "",
        "business_type": p.business_type or "",
        "description": p.description or "",
        "website": p.website or "",
        "phone": p.phone or "",
        "email": p.email or "",
        "hours": p.hours or "",
        "service_area": p.service_area or "",
        "tone": p.tone or "Professional",
        "currency": p.currency or "AUD",
        "auto_threshold": p.auto_threshold,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


def knowledge_json(k: BusinessKnowledge):
    return {
        "id": k.id,
        "category": k.category,
        "title": k.title,
        "content": k.content,
        "source": k.source,
        "approved": k.approved,
        "active": k.active,
        "created_at": k.created_at.isoformat() if k.created_at else None,
        "updated_at": k.updated_at.isoformat() if k.updated_at else None,
    }


def chat_setting_json(s: BusinessChatSetting):
    return {
        "enabled": s.enabled,
        "mode": s.mode,
        "customer_label": s.customer_label or "",
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
    }


def memory_json(m: BusinessCustomerMemory):
    return {
        "notes": m.notes or "",
        "tags": m.tags or "",
        "updated_at": m.updated_at.isoformat() if m.updated_at else None,
    }


def ensure_chat_member(db: Session, uid: int, cid: int):
    c = db.get(Chat, cid)
    if not c or uid not in (c.user1_id, c.user2_id):
        raise ValueError("Chat not found")
    return c


def _recent_chat(db: Session, cid: int, limit: int = 50):
    rows = db.scalars(
        select(Message).where(Message.chat_id == cid).order_by(Message.id.desc()).limit(limit)
    ).all()[::-1]
    out = []
    for m in rows:
        sender = db.get(User, m.sender_id)
        out.append(f"{sender.display_name if sender else 'Unknown'}: {m.text}")
    return out


def _knowledge(db: Session, uid: int, limit: int = 80):
    return db.scalars(
        select(BusinessKnowledge)
        .where(
            BusinessKnowledge.user_id == uid,
            BusinessKnowledge.active.is_(True),
            BusinessKnowledge.approved.is_(True),
        )
        .order_by(BusinessKnowledge.updated_at.desc())
        .limit(limit)
    ).all()


def _fallback_reply(profile: BusinessProfile, knowledge: list[BusinessKnowledge], incoming: str):
    t = incoming.lower()
    # Conservative deterministic matching, used only when Claude is not configured.
    matches = []
    words = {x for x in re.findall(r"[a-z0-9]{3,}", t)}
    for k in knowledge:
        score = sum(1 for x in words if x in (k.title + " " + k.content).lower())
        if score:
            matches.append((score, k))
    matches.sort(key=lambda x: x[0], reverse=True)
    if matches:
        k = matches[0][1]
        return {
            "reply": k.content[:900],
            "confidence": min(82, 50 + matches[0][0] * 5),
            "requires_review": True,
            "reason": "Matched approved business knowledge. Anthropic is not configured, so review before sending.",
            "sources": [{"id": k.id, "title": k.title, "category": k.category}],
        }
    name = profile.business_name or "our business"
    return {
        "reply": f"Thanks for contacting {name}. I want to make sure I give you the correct information, so I’ll confirm this and get back to you.",
        "confidence": 35,
        "requires_review": True,
        "reason": "No approved business knowledge matched this enquiry.",
        "sources": [],
    }


def business_reply(db: Session, uid: int, cid: int, incoming: str | None = None):
    ensure_chat_member(db, uid, cid)
    profile = profile_for(db, uid)
    setting = chat_setting_for(db, uid, cid)
    memory = customer_memory_for(db, uid, cid)
    knowledge = _knowledge(db, uid)
    history = _recent_chat(db, cid, 50)
    if incoming is None:
        incoming = next((line.split(": ", 1)[1] for line in reversed(history) if line), "")

    if not profile.enabled:
        return {
            "reply": "",
            "confidence": 0,
            "requires_review": True,
            "reason": "Business Beta is disabled in the Business tab.",
            "sources": [],
        }

    client = _anthropic()
    if not client:
        return _fallback_reply(profile, knowledge, incoming or "")

    knowledge_text = "\n\n".join(
        f"[KB {k.id} | {k.category} | {k.title} | source={k.source}]\n{k.content}"
        for k in knowledge
    )
    prompt = f"""You are LEMMIQ Business Agent for the business owner using this messenger.
Draft ONE customer-facing reply grounded strictly in the approved business knowledge and the current conversation.

BUSINESS PROFILE
Name: {profile.business_name}
Type: {profile.business_type}
Description: {profile.description}
Hours: {profile.hours}
Service area: {profile.service_area}
Website: {profile.website}
Tone: {profile.tone}
Currency: {profile.currency}

CUSTOMER MEMORY (owner-maintained; may be blank)
{memory.notes}
Tags: {memory.tags}

APPROVED BUSINESS KNOWLEDGE
{knowledge_text[:24000] if knowledge_text else 'No approved knowledge has been added.'}

RECENT CHAT
{chr(10).join(history)[-12000:]}

LATEST CUSTOMER MESSAGE
{incoming or ''}

Rules:
- Never invent prices, stock, availability, warranties, discounts, bookings, policies, delivery times, completed actions or guarantees.
- If the business knowledge does not support the answer, say that it needs confirmation and ask the minimum useful follow-up question.
- Do not claim to have checked a booking system, inventory, payment, calendar or CRM unless that fact appears in the supplied context.
- Match the business tone and the customer's language where practical.
- Keep the reply concise and natural.
- Confidence is the strength of grounding in approved business knowledge, not certainty.
- Set requires_review=false ONLY when the reply is directly supported by approved knowledge, contains no unsupported promise/action, and no important ambiguity remains. Otherwise set it true.

Return JSON only:
{{
  "reply":"customer-facing reply",
  "confidence":0,
  "requires_review":true,
  "reason":"short grounding explanation",
  "sources":[{{"id":1,"title":"source title","category":"PRICING"}}]
}}
"""
    try:
        m = client.messages.create(
            model=_model(), max_tokens=850, temperature=0,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = "".join(x.text for x in m.content if getattr(x, "type", "") == "text").strip()
        raw = raw.removeprefix("```json").removesuffix("```").strip()
        data = json.loads(raw)
        data["reply"] = str(data.get("reply", ""))[:1800]
        data["confidence"] = max(0, min(int(data.get("confidence", 0)), 100))
        valid_ids = {k.id: k for k in knowledge}
        sources = []
        for s in data.get("sources", [])[:8]:
            try:
                sid = int(s.get("id"))
            except Exception:
                continue
            if sid in valid_ids:
                k = valid_ids[sid]
                sources.append({"id": k.id, "title": k.title, "category": k.category})
        data["sources"] = sources
        data["requires_review"] = bool(data.get("requires_review", True))
        data["reason"] = str(data.get("reason", ""))[:500]
        return data
    except Exception:
        return _fallback_reply(profile, knowledge, incoming or "")


def extract_document(filename: str, content_type: str, payload: bytes):
    name = (filename or "document").lower()
    mime = (content_type or "").lower().split(";")[0]
    text = ""
    if mime in {"text/plain", "text/markdown", "text/csv"} or name.endswith((".txt", ".md", ".csv")):
        text = payload.decode("utf-8", errors="replace")
    elif mime == "application/pdf" or name.endswith(".pdf"):
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(payload))
        text = "\n".join((page.extract_text() or "") for page in reader.pages[:80])
    elif mime == "application/vnd.openxmlformats-officedocument.wordprocessingml.document" or name.endswith(".docx"):
        from docx import Document
        doc = Document(io.BytesIO(payload))
        text = "\n".join(p.text for p in doc.paragraphs)
    else:
        raise ValueError("Use TXT, MD, CSV, PDF or DOCX")
    text = re.sub(r"\x00", "", text).strip()
    if not text:
        raise ValueError("No readable text was found in this document")
    return text[:60000]


def learn_candidates(db: Session, uid: int, cid: int):
    ensure_chat_member(db, uid, cid)
    owner = db.get(User, uid)
    rows = db.scalars(
        select(Message).where(Message.chat_id == cid).order_by(Message.id.desc()).limit(120)
    ).all()[::-1]
    # Learn only from messages the business owner actually typed. AI-generated replies and customer messages
    # are deliberately excluded so they cannot silently become business truth.
    owner_lines = [m.text for m in rows if m.sender_id == uid and not m.ai_generated and m.text.strip()]
    if len(owner_lines) < 1:
        return []
    client = _anthropic()
    if not client:
        return []
    prompt = f"""You are LEMMIQ Business Learning Assistant.
The business owner account is {owner.display_name if owner else 'the current user'}.
Below are ONLY messages manually written by that business owner in a customer chat.
Identify reusable BUSINESS facts explicitly stated in those messages.
Do not infer facts. Do not include customer personal details. Do not include one-off negotiation unless it clearly states a reusable business rule.
Candidates are NEVER saved automatically; the owner will review them.

OWNER-WRITTEN MESSAGES:
{chr(10).join(owner_lines)[-16000:]}

Return JSON only:
{{"candidates":[{{"category":"FAQ|SERVICE|PRICING|POLICY|HOURS|AREA|OTHER","title":"short title","content":"reusable factual business statement"}}]}}
"""
    try:
        m = client.messages.create(model=_model(), max_tokens=900, temperature=0,
            messages=[{"role":"user","content":prompt}])
        raw = "".join(x.text for x in m.content if getattr(x,"type","")=="text").strip()
        raw = raw.removeprefix("```json").removesuffix("```").strip()
        data = json.loads(raw)
        out = []
        allowed = {"FAQ","SERVICE","PRICING","POLICY","HOURS","AREA","OTHER"}
        for c in data.get("candidates", [])[:10]:
            cat = str(c.get("category", "OTHER")).upper()
            if cat not in allowed: cat = "OTHER"
            title = str(c.get("title", "")).strip()[:120]
            content = str(c.get("content", "")).strip()[:1800]
            if title and content:
                out.append({"category":cat,"title":title,"content":content})
        return out
    except Exception:
        return []
