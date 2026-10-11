"""LEMMIQ V2.10.7.4 — global Q feature pricing and wallet charging.

Pricing is deliberately GLOBAL: the same Q price applies to every package/tier.
Tier remains attached to usage analytics only. Package benefits come from how
much Q users earn, not from cheaper AI prices.

Charging is OFF by default. When Master Admin enables charging, paid feature
calls use the main LEMMIQ Q wallet and move the fee to the PROFIT wallet.
Failed operations refund any reserved/charged Q.
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
    _ledger, _raw_user_wallet, _system_to_user, _user_to_system,
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

# User-approved single global price model. Charging remains OFF until Admin enables it.
DEFAULT_GLOBAL_Q = {
    "Q_CHAT": 0.25,
    "Q_ADVANCED": 1.00,
    "Q_VISION": 2.00,
    "TRUST_CHECK": 1.00,
    "CHAT_SUMMARY": 0.50,
    "Q_TO_Q": 0.50,
    "BUSINESS_AGENT": 5.00,
    "SUGGEST_REPLY": 0.20,
    "SMART_MEMORY": 0.20,
    "VOICE_TRANSCRIPTION": 0.25,
    "DOCUMENT_ANALYSIS": 2.00,
    "Q_PREDICT_ANALYSIS": 1.00,
    # AUTO can run without a user tap, so it stays 0 Q until explicitly changed.
    "AUTO_MESSAGE": 0.00,
}


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
    """Legacy compatibility table.

    V2.10.7.4 mirrors the same global price into every tier row so old clients
    continue to work, but the server no longer derives different prices by tier.
    """
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


class QFeaturePricingMeta(Base):
    __tablename__ = "q_feature_pricing_meta"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    pricing_model: Mapped[str] = mapped_column(String(20), default="GLOBAL")
    seeded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RuleUpdate(BaseModel):
    q_cost: float = Field(default=0, ge=0, le=1_000_000)
    enabled: bool = True
    included_uses_daily: int | None = Field(default=None, ge=0)
    included_uses_monthly: int | None = Field(default=None, ge=0)


class GlobalFeatureUpdate(BaseModel):
    q_cost: float = Field(default=0, ge=0, le=1_000_000)
    enabled: bool = True


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

    existing_rules = {(x.feature_key, x.tier_key): x for x in db.scalars(select(QFeatureTierRule)).all()}
    for key in FEATURES:
        for tier in TIERS:
            if (key, tier) not in existing_rules:
                row = QFeatureTierRule(feature_key=key, tier_key=tier, cost_micros=0, enabled=True)
                db.add(row)
                existing_rules[(key, tier)] = row
    db.flush()

    # One-time migration to GLOBAL pricing. Preserve any existing non-zero
    # configured value; otherwise seed the approved starting rate.
    meta = db.get(QFeaturePricingMeta, 1)
    if not meta:
        for key in FEATURES:
            feature = db.get(QFeature, key)
            rules = [existing_rules[(key, tier)] for tier in TIERS]
            existing_nonzero = [r.cost_micros for r in rules if r.cost_micros > 0]
            chosen = feature.default_cost_micros if feature.default_cost_micros > 0 else (
                existing_nonzero[0] if existing_nonzero
                else int(round(DEFAULT_GLOBAL_Q.get(key, 0) * Q_MICROS))
            )
            feature.default_cost_micros = chosen
            feature.updated_at = utcnow()
            for rule in rules:
                rule.cost_micros = chosen
                rule.enabled = feature.enabled
                rule.included_uses_daily = None
                rule.included_uses_monthly = None
                rule.updated_at = utcnow()
        db.add(QFeaturePricingMeta(id=1, pricing_model="GLOBAL"))


def _tier_code(db: Session, user_id: int) -> str:
    now = utcnow()
    lots = db.scalars(select(QSubscriptionLot).where(
        QSubscriptionLot.user_id == user_id, QSubscriptionLot.expires_at > now
    )).all()
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
    tier = _tier_code(db, user_id)  # analytics only
    settings = db.get(QFeatureSetting, 1)
    configured = max(0, int(feature.default_cost_micros or 0))
    charge = configured if (settings and settings.charging_enabled and feature.enabled) else 0
    return {
        "feature_key": key,
        "feature_name": feature.name,
        "tier_key": tier,
        "pricing_model": "GLOBAL",
        "q_cost": round(charge / Q_MICROS, 6),
        "configured_q_cost": round(configured / Q_MICROS, 6),
        "enabled": bool(feature.enabled),
        "charging_enabled": bool(settings and settings.charging_enabled),
        "included_uses_daily": None,
        "included_uses_monthly": None,
    }


def begin_feature_charge(db: Session, user_id: int, feature_key: str, *, reference: str = "") -> dict:
    """Preflight a feature and reserve/deduct its global Q price.

    If charging is OFF or the configured price is 0 Q, no wallet debit occurs.
    When charging is ON, insufficient Q raises 409 BEFORE the AI/provider call.
    """
    quote = _quote(db, user_id, feature_key)
    if not quote["enabled"]:
        raise HTTPException(409, f"{quote['feature_name']} is currently disabled")
    quoted = int(round(float(quote["q_cost"]) * Q_MICROS))
    charged = 0
    if quoted > 0:
        wallet = _raw_user_wallet(db, user_id)
        if wallet.balance_micros < quoted:
            raise HTTPException(
                409,
                f"Not enough Q. {quote['feature_name']} costs {quoted / Q_MICROS:.6f} Q and your balance is {wallet.balance_micros / Q_MICROS:.6f} Q",
            )
        _user_to_system(
            db, user_id, "PROFIT", quoted, "AI_FEATURE_FEE",
            reference=(reference or quote["feature_key"])[:120],
            note=f"{quote['feature_name']} · global price",
        )
        charged = quoted
    return {
        **quote,
        "quoted_micros": quoted,
        "charged_micros": charged,
        "reference": (reference or quote["feature_key"])[:180],
    }


def finish_feature_charge(
    db: Session,
    reservation: dict,
    success: bool,
    *,
    metadata: dict | None = None,
    status: str | None = None,
) -> dict:
    user_id = int(reservation.get("user_id") or 0)
    # Older callers may not include user_id in reservation; require it from the
    # internal field set by charge_feature_for_user below.
    if not user_id:
        user_id = int(reservation["_user_id"])
    charged = int(reservation.get("charged_micros") or 0)
    quoted = int(reservation.get("quoted_micros") or 0)
    final_charged = charged if success else 0

    if charged > 0 and not success:
        _system_to_user(
            db, "PROFIT", user_id, charged, "AI_FEATURE_REFUND",
            reference=reservation.get("reference", "")[:120],
            note=f"{reservation.get('feature_name','AI feature')} failed; Q refunded",
        )
    elif success and charged == 0:
        _ledger(
            db, "FEATURE_USAGE", 0, from_user=user_id, to_system="PROFIT",
            reference=reservation.get("reference", "")[:120],
            note=reservation.get("feature_name", reservation.get("feature_key", "Q feature")),
        )

    db.add(QFeatureUsage(
        user_id=user_id,
        feature_key=reservation["feature_key"],
        tier_key=reservation.get("tier_key", "FREE"),
        quoted_micros=quoted,
        charged_micros=final_charged,
        status=(status or ("SUCCESS" if success else "FAILED"))[:32],
        reference=reservation.get("reference", "")[:180],
        metadata_json=json.dumps(metadata or {}, ensure_ascii=False)[:8000],
    ))
    return {
        **reservation,
        "charged_q": round(final_charged / Q_MICROS, 6),
        "success": bool(success),
    }


def charge_feature_for_user(db: Session, user_id: int, feature_key: str, *, reference: str = "") -> dict:
    reservation = begin_feature_charge(db, user_id, feature_key, reference=reference)
    reservation["_user_id"] = user_id
    return reservation


def record_feature_usage(
    db: Session,
    user_id: int,
    feature_key: str,
    *,
    status: str = "SUCCESS",
    reference: str = "",
    metadata: dict | None = None,
    charge: bool = False,
):
    """Compatibility helper used by older integrations."""
    if charge:
        reservation = charge_feature_for_user(db, user_id, feature_key, reference=reference)
        return finish_feature_charge(
            db, reservation, status.upper() == "SUCCESS",
            metadata=metadata, status=status,
        )

    q = _quote(db, user_id, feature_key)
    quoted = int(round(float(q["q_cost"]) * Q_MICROS))
    if status.upper() == "SUCCESS":
        _ledger(
            db, "FEATURE_USAGE", 0, from_user=user_id, to_system="PROFIT",
            reference=reference or q["feature_key"], note=q["feature_name"],
        )
    db.add(QFeatureUsage(
        user_id=user_id, feature_key=q["feature_key"], tier_key=q["tier_key"],
        quoted_micros=quoted, charged_micros=0, status=status[:32],
        reference=reference[:180], metadata_json=json.dumps(metadata or {}, ensure_ascii=False)[:8000],
    ))
    return {**q, "charged_q": 0}


def register_v2105_q_features(app, current_user, get_db):
    router = APIRouter(prefix="/v2105", tags=["LEMMIQ Global Q Feature Pricing"])

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
        from .database import engine
        Base.metadata.create_all(bind=engine)
        db = SessionLocal()
        try:
            _seed(db)
            db.commit()
        finally:
            db.close()

    @router.get("/q-features/catalog")
    def catalog(u: User = Depends(current_user), db: Session = Depends(get_db)):
        rows = [_quote(db, u.id, key) for key in FEATURES]
        db.commit()
        return rows

    @router.get("/q-features/{feature_key}/quote")
    def quote(feature_key: str, u: User = Depends(current_user), db: Session = Depends(get_db)):
        data = _quote(db, u.id, feature_key)
        db.commit()
        return data

    @router.get("/admin/q-features")
    def admin_list(_u: User = Depends(require_feature_read), db: Session = Depends(get_db)):
        _seed(db)
        settings = db.get(QFeatureSetting, 1)
        features = []
        for key, name in FEATURES.items():
            row = db.get(QFeature, key)
            features.append({
                "feature_key": key,
                "feature_name": name,
                "q_cost": round((row.default_cost_micros or 0) / Q_MICROS, 6),
                "enabled": bool(row.enabled),
            })
        # Legacy rules are mirrored for old clients but always identical by tier.
        rules = []
        for item in features:
            for tier in TIERS:
                rules.append({
                    "feature_key": item["feature_key"],
                    "tier_key": tier,
                    "q_cost": item["q_cost"],
                    "enabled": item["enabled"],
                    "included_uses_daily": None,
                    "included_uses_monthly": None,
                })
        return {
            "charging_enabled": bool(settings and settings.charging_enabled),
            "pricing_model": "GLOBAL",
            "same_price_all_packages": True,
            "features": features,
            "rules": rules,
        }

    @router.put("/admin/q-features/settings")
    def admin_settings(body: GlobalUpdate, u: User = Depends(require_feature_full), db: Session = Depends(get_db)):
        _seed(db)
        row = db.get(QFeatureSetting, 1)
        row.charging_enabled = body.charging_enabled
        row.updated_at = utcnow()
        db.add(QFeatureAudit(
            admin_user_id=u.id, feature_key="GLOBAL",
            change_json=json.dumps({"charging_enabled": body.charging_enabled, "pricing_model": "GLOBAL"})
        ))
        db.commit()
        return {"charging_enabled": row.charging_enabled, "pricing_model": "GLOBAL"}

    @router.put("/admin/q-features/{feature_key}")
    def admin_update_global_feature(feature_key: str, body: GlobalFeatureUpdate, u: User = Depends(require_feature_full), db: Session = Depends(get_db)):
        _seed(db)
        key = feature_key.strip().upper()
        if key not in FEATURES:
            raise HTTPException(404, "Unknown feature key")
        feature = db.get(QFeature, key)
        cost = int(round(body.q_cost * Q_MICROS))
        feature.default_cost_micros = cost
        feature.enabled = bool(body.enabled)
        feature.updated_at = utcnow()
        for row in db.scalars(select(QFeatureTierRule).where(QFeatureTierRule.feature_key == key)).all():
            row.cost_micros = cost
            row.enabled = feature.enabled
            row.included_uses_daily = None
            row.included_uses_monthly = None
            row.updated_at = utcnow()
        db.add(QFeatureAudit(
            admin_user_id=u.id, feature_key=key, tier_key=None,
            change_json=json.dumps({"q_cost": body.q_cost, "enabled": body.enabled, "pricing_model": "GLOBAL"})
        ))
        db.commit()
        return {"feature_key": key, "feature_name": feature.name, "q_cost": body.q_cost, "enabled": feature.enabled, "pricing_model": "GLOBAL"}

    @router.put("/admin/q-features/{feature_key}/{tier_key}")
    def admin_update_legacy(feature_key: str, tier_key: str, body: RuleUpdate, u: User = Depends(require_feature_full), db: Session = Depends(get_db)):
        # Compatibility: old clients can still call the tier route, but a change
        # is intentionally applied globally to every package.
        key = feature_key.strip().upper()
        if key not in FEATURES:
            raise HTTPException(404, "Unknown feature key")
        if tier_key.strip().upper() not in TIERS:
            raise HTTPException(422, "Unknown tier")
        payload = GlobalFeatureUpdate(q_cost=body.q_cost, enabled=body.enabled)
        # Inline same logic to keep FastAPI dependencies simple.
        _seed(db)
        feature = db.get(QFeature, key)
        cost = int(round(payload.q_cost * Q_MICROS))
        feature.default_cost_micros = cost
        feature.enabled = payload.enabled
        feature.updated_at = utcnow()
        for row in db.scalars(select(QFeatureTierRule).where(QFeatureTierRule.feature_key == key)).all():
            row.cost_micros = cost
            row.enabled = feature.enabled
            row.included_uses_daily = None
            row.included_uses_monthly = None
            row.updated_at = utcnow()
        db.add(QFeatureAudit(
            admin_user_id=u.id, feature_key=key, tier_key=None,
            change_json=json.dumps({"q_cost": body.q_cost, "enabled": body.enabled, "pricing_model": "GLOBAL", "legacy_tier_request": tier_key})
        ))
        db.commit()
        return {
            "feature_key": key, "feature_name": feature.name, "edited_tier_key": "ALL",
            "edited_q_cost": body.q_cost, "q_cost": body.q_cost,
            "configured_q_cost": body.q_cost, "pricing_model": "GLOBAL",
        }

    @router.get("/q-features/activity")
    def my_usage(limit: int = 100, u: User = Depends(current_user), db: Session = Depends(get_db)):
        limit = max(1, min(limit, 250))
        rows = db.scalars(
            select(QFeatureUsage).where(QFeatureUsage.user_id == u.id)
            .order_by(QFeatureUsage.id.desc()).limit(limit)
        ).all()
        return [{
            "id": r.id, "feature_key": r.feature_key, "tier_key": r.tier_key,
            "quoted_q": round(r.quoted_micros / Q_MICROS, 6),
            "charged_q": round(r.charged_micros / Q_MICROS, 6),
            "status": r.status, "reference": r.reference,
            "created_at": r.created_at.isoformat(),
        } for r in rows]

    app.include_router(router)
