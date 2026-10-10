"""LEMMIQ V2.10.5 — backend-controlled Q feature pricing by tier.

All feature prices default to 0 Q. Pricing is authoritative on the server and
uses the user's active subscription tier; clients do not get to choose a tier.
Master Admin can edit feature/tier rules without releasing a new app.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from .database import Base, SessionLocal
from .models import User
from .v28 import (
    QAdminRole, QSubscriptionLot, PACKAGE_PLANS, Q_MICROS,
    _ledger, _user_to_system,
)
from .admin_rbac import require_admin_access

FEATURES = {
    "SUGGEST_REPLY": "Suggest Reply",
    "CHAT_SUMMARY": "Chat Summary",
    "Q_CHAT": "Q Chat",
    "Q_ADVANCED": "Q Advanced",
    "Q_VISION": "Q Vision",
    "Q_PREDICT_ANALYSIS": "Q Predict Analysis",
    "TRUST_CHECK": "Trust / Fact Check",
    "BUSINESS_AGENT": "Business Agent",
    "DOCUMENT_ANALYSIS": "Document Analysis",
    "Q_TO_Q": "Q-to-Q Coordination",
    "VOICE_TRANSCRIPTION": "Voice Transcription",
    "SMART_MEMORY": "Smart Memory",
    "AUTO_MESSAGE": "Auto Message / Auto Reply",
}
TIERS = ["FREE", "STARTER_10", "PLUS_50", "PRO_100", "PREMIUM_500", "ELITE_1000"]


def utcnow():
    return datetime.now(timezone.utc)


class QFeatureSetting(Base):
    __tablename__ = "q_feature_settings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    charging_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class QFeature(Base):
    __tablename__ = "q_features"
    feature_key: Mapped[str] = mapped_column(String(80), primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    default_cost_micros: Mapped[int] = mapped_column(BigInteger, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class QFeatureTierRule(Base):
    __tablename__ = "q_feature_tier_rules"
    __table_args__ = (UniqueConstraint("feature_key", "tier_key", name="uq_q_feature_tier"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    feature_key: Mapped[str] = mapped_column(String(80), index=True)
    tier_key: Mapped[str] = mapped_column(String(40), index=True)
    cost_micros: Mapped[int] = mapped_column(BigInteger, default=0)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    included_uses_daily: Mapped[int | None] = mapped_column(Integer, nullable=True)
    included_uses_monthly: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class QFeatureUsage(Base):
    __tablename__ = "q_feature_usage"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    feature_key: Mapped[str] = mapped_column(String(80), index=True)
    tier_key: Mapped[str] = mapped_column(String(40), index=True)
    quoted_micros: Mapped[int] = mapped_column(BigInteger, default=0)
    charged_micros: Mapped[int] = mapped_column(BigInteger, default=0)
    status: Mapped[str] = mapped_column(String(32), default="SUCCESS", index=True)
    reference: Mapped[str] = mapped_column(String(180), default="")
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class QFeatureAudit(Base):
    __tablename__ = "q_feature_admin_audit"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    admin_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    feature_key: Mapped[str] = mapped_column(String(80), default="GLOBAL")
    tier_key: Mapped[str | None] = mapped_column(String(40), nullable=True)
    change_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RuleUpdate(BaseModel):
    q_cost: float = Field(default=0, ge=0, le=1_000_000)
    enabled: bool = True
    included_uses_daily: int | None = Field(default=None, ge=0)
    included_uses_monthly: int | None = Field(default=None, ge=0)


class GlobalUpdate(BaseModel):
    charging_enabled: bool = False


def _seed(db: Session):
    settings = db.get(QFeatureSetting, 1)
    if not settings:
        db.add(QFeatureSetting(id=1, charging_enabled=False))
    for key, name in FEATURES.items():
        if not db.get(QFeature, key):
            db.add(QFeature(feature_key=key, name=name, enabled=True, default_cost_micros=0))
    db.flush()
    existing = {(x.feature_key, x.tier_key) for x in db.scalars(select(QFeatureTierRule)).all()}
    for key in FEATURES:
        for tier in TIERS:
            if (key, tier) not in existing:
                db.add(QFeatureTierRule(feature_key=key, tier_key=tier, cost_micros=0, enabled=True))


def _tier_code(db: Session, user_id: int) -> str:
    now = utcnow()
    lots = db.scalars(select(QSubscriptionLot).where(QSubscriptionLot.user_id == user_id, QSubscriptionLot.expires_at > now)).all()
    if not lots:
        return "FREE"
    best = max(lots, key=lambda x: PACKAGE_PLANS.get(x.package_code, {}).get("price_usd", 0))
    return best.package_code if best.package_code in TIERS else "FREE"


def _quote(db: Session, user_id: int, feature_key: str):
    _seed(db)
    key = feature_key.strip().upper()
    feature = db.get(QFeature, key)
    if not feature:
        raise HTTPException(404, "Unknown Q feature")
    tier = _tier_code(db, user_id)
    rule = db.scalar(select(QFeatureTierRule).where(QFeatureTierRule.feature_key == key, QFeatureTierRule.tier_key == tier))
    settings = db.get(QFeatureSetting, 1)
    configured = rule.cost_micros if rule else feature.default_cost_micros
    charge = configured if (settings and settings.charging_enabled and feature.enabled and (rule.enabled if rule else True)) else 0
    return {
        "feature_key": key,
        "feature_name": feature.name,
        "tier_key": tier,
        "q_cost": round(charge / Q_MICROS, 6),
        "configured_q_cost": round(configured / Q_MICROS, 6),
        "enabled": bool(feature.enabled and (rule.enabled if rule else True)),
        "charging_enabled": bool(settings and settings.charging_enabled),
        "included_uses_daily": rule.included_uses_daily if rule else None,
        "included_uses_monthly": rule.included_uses_monthly if rule else None,
    }


def record_feature_usage(db: Session, user_id: int, feature_key: str, *, status: str = "SUCCESS", reference: str = "", metadata: dict | None = None, charge: bool = False):
    """Record feature usage. Current integrations call with charge=False.

    The pricing tables are ready for future paid usage. When a feature is wired
    to preflight billing, call with charge=True only after cost confirmation.
    """
    q = _quote(db, user_id, feature_key)
    charged = 0
    quoted = int(round(float(q["q_cost"]) * Q_MICROS))
    if charge and status == "SUCCESS" and quoted > 0:
        _user_to_system(db, user_id, "PROFIT", quoted, "AI_FEATURE_FEE", reference=reference, note=f"{q['feature_name']} · {q['tier_key']}")
        charged = quoted
    elif status == "SUCCESS":
        # 0 Q feature-use events remain visible in Q Activity without misleading
        # wording such as beta/free testing.
        _ledger(db, "FEATURE_USAGE", 0, from_user=user_id, to_system="PROFIT", reference=reference or q["feature_key"], note=q["feature_name"])
    db.add(QFeatureUsage(
        user_id=user_id, feature_key=q["feature_key"], tier_key=q["tier_key"],
        quoted_micros=quoted, charged_micros=charged, status=status[:32],
        reference=reference[:180], metadata_json=json.dumps(metadata or {}, ensure_ascii=False)[:8000],
    ))
    return {**q, "charged_q": round(charged / Q_MICROS, 6)}


def register_v2105_q_features(app, current_user, get_db):
    router = APIRouter(prefix="/v2105", tags=["LEMMIQ V2.10.5 Q Feature Pricing"])

    def require_feature_read(u: User = Depends(current_user), db: Session = Depends(get_db)):
        role = db.get(QAdminRole, u.id)
        if not role or not role.active:
            raise HTTPException(403, "Admin access required")
        require_admin_access(db, u.id, role.role, "Q_FEATURE_PRICING", "READ")
        return u

    def require_feature_full(u: User = Depends(current_user), db: Session = Depends(get_db)):
        role = db.get(QAdminRole, u.id)
        if not role or not role.active:
            raise HTTPException(403, "Admin access required")
        require_admin_access(db, u.id, role.role, "Q_FEATURE_PRICING", "FULL")
        return u

    @app.on_event("startup")
    def _feature_startup():
        db = SessionLocal()
        try:
            _seed(db); db.commit()
        finally:
            db.close()

    @router.get("/q-features/catalog")
    def catalog(u: User = Depends(current_user), db: Session = Depends(get_db)):
        rows = [_quote(db, u.id, key) for key in FEATURES]
        db.commit()
        return rows

    @router.get("/q-features/{feature_key}/quote")
    def quote(feature_key: str, u: User = Depends(current_user), db: Session = Depends(get_db)):
        data = _quote(db, u.id, feature_key); db.commit(); return data

    @router.get("/admin/q-features")
    def admin_list(_u: User = Depends(require_feature_read), db: Session = Depends(get_db)):
        _seed(db)
        settings = db.get(QFeatureSetting, 1)
        rules = db.scalars(select(QFeatureTierRule).order_by(QFeatureTierRule.feature_key, QFeatureTierRule.tier_key)).all()
        return {
            "charging_enabled": bool(settings and settings.charging_enabled),
            "rules": [{
                "feature_key": r.feature_key, "tier_key": r.tier_key,
                "q_cost": round(r.cost_micros / Q_MICROS, 6), "enabled": r.enabled,
                "included_uses_daily": r.included_uses_daily,
                "included_uses_monthly": r.included_uses_monthly,
            } for r in rules],
        }

    @router.put("/admin/q-features/settings")
    def admin_settings(body: GlobalUpdate, u: User = Depends(require_feature_full), db: Session = Depends(get_db)):
        _seed(db); row = db.get(QFeatureSetting, 1); row.charging_enabled = body.charging_enabled; row.updated_at = utcnow()
        db.add(QFeatureAudit(admin_user_id=u.id, feature_key="GLOBAL", change_json=json.dumps({"charging_enabled": body.charging_enabled})))
        db.commit(); return {"charging_enabled": row.charging_enabled}

    @router.put("/admin/q-features/{feature_key}/{tier_key}")
    def admin_update(feature_key: str, tier_key: str, body: RuleUpdate, u: User = Depends(require_feature_full), db: Session = Depends(get_db)):
        _seed(db); key = feature_key.strip().upper(); tier = tier_key.strip().upper()
        if key not in FEATURES: raise HTTPException(404, "Unknown feature key")
        if tier not in TIERS: raise HTTPException(422, "Unknown tier")
        row = db.scalar(select(QFeatureTierRule).where(QFeatureTierRule.feature_key == key, QFeatureTierRule.tier_key == tier))
        if not row:
            row = QFeatureTierRule(feature_key=key, tier_key=tier); db.add(row)
        row.cost_micros = int(round(body.q_cost * Q_MICROS)); row.enabled = body.enabled
        row.included_uses_daily = body.included_uses_daily; row.included_uses_monthly = body.included_uses_monthly; row.updated_at = utcnow()
        db.add(QFeatureAudit(admin_user_id=u.id, feature_key=key, tier_key=tier, change_json=json.dumps(body.model_dump())))
        db.commit(); return _quote(db, u.id, key) | {"edited_tier_key": tier, "edited_q_cost": body.q_cost}

    @router.get("/q-features/activity")
    def my_usage(limit: int = 100, u: User = Depends(current_user), db: Session = Depends(get_db)):
        limit = max(1, min(limit, 250))
        rows = db.scalars(select(QFeatureUsage).where(QFeatureUsage.user_id == u.id).order_by(QFeatureUsage.id.desc()).limit(limit)).all()
        return [{
            "id": r.id, "feature_key": r.feature_key, "tier_key": r.tier_key,
            "quoted_q": round(r.quoted_micros / Q_MICROS, 6), "charged_q": round(r.charged_micros / Q_MICROS, 6),
            "status": r.status, "reference": r.reference, "created_at": r.created_at.isoformat(),
        } for r in rows]

    app.include_router(router)
