from __future__ import annotations

import os
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import (
    Boolean, Column, DateTime, Integer, MetaData, Numeric, String, Table,
    Text, UniqueConstraint, create_engine, insert, select, update
)
from sqlalchemy.engine import Engine

VERSION = "2.10.4"
router = APIRouter(prefix="/v2104", tags=["LEMMIQ V2.10.4 Q Economy"])

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
}

TIERS = ["FREE", "STARTER_10", "PLUS_50", "PRO_100", "PREMIUM_500", "ELITE_1000"]

metadata = MetaData()

q_feature_settings = Table(
    "q_feature_settings_v2104", metadata,
    Column("id", Integer, primary_key=True),
    Column("settings_key", String(80), nullable=False, unique=True),
    Column("charging_enabled", Boolean, nullable=False, default=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

q_features = Table(
    "q_features_v2104", metadata,
    Column("id", Integer, primary_key=True),
    Column("feature_key", String(80), nullable=False, unique=True),
    Column("name", String(160), nullable=False),
    Column("enabled", Boolean, nullable=False, default=True),
    Column("default_q_cost", Numeric(18, 6), nullable=False, default=0),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

q_feature_tier_rules = Table(
    "q_feature_tier_rules_v2104", metadata,
    Column("id", Integer, primary_key=True),
    Column("feature_key", String(80), nullable=False),
    Column("tier_key", String(80), nullable=False),
    Column("q_cost", Numeric(18, 6), nullable=False, default=0),
    Column("enabled", Boolean, nullable=False, default=True),
    Column("included_uses_daily", Integer, nullable=True),
    Column("included_uses_monthly", Integer, nullable=True),
    Column("discount_percent", Numeric(8, 4), nullable=False, default=0),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("feature_key", "tier_key", name="uq_q_feature_tier_v2104"),
)

q_feature_usage = Table(
    "q_feature_usage_v2104", metadata,
    Column("id", Integer, primary_key=True),
    Column("user_id", Integer, nullable=False, index=True),
    Column("feature_key", String(80), nullable=False, index=True),
    Column("tier_key", String(80), nullable=False),
    Column("quoted_cost", Numeric(18, 6), nullable=False, default=0),
    Column("charged_cost", Numeric(18, 6), nullable=False, default=0),
    Column("status", String(40), nullable=False, default="SUCCESS"),
    Column("reference", String(180), nullable=True),
    Column("metadata_json", Text, nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

q_feature_admin_audit = Table(
    "q_feature_admin_audit_v2104", metadata,
    Column("id", Integer, primary_key=True),
    Column("actor", String(160), nullable=False),
    Column("feature_key", String(80), nullable=False),
    Column("tier_key", String(80), nullable=True),
    Column("change_json", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)


def _database_url() -> str:
    url = os.getenv("DATABASE_URL", "sqlite:///./lemmiq.db").strip()
    # Keep the V2.10.4 compatibility router on the same PostgreSQL driver
    # as the rest of LEMMIQ. Render provides psycopg v3, not psycopg2.
    if url.startswith("postgres://"):
        url = "postgresql+psycopg://" + url[len("postgres://"):]
    elif url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


def build_engine() -> Engine:
    url = _database_url()
    kwargs = {"pool_pre_ping": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    return create_engine(url, **kwargs)


ENGINE = build_engine()


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def init_v2104_q_feature_tables(engine: Engine = ENGINE) -> None:
    metadata.create_all(engine)
    now = now_utc()
    with engine.begin() as conn:
        settings = conn.execute(select(q_feature_settings).where(q_feature_settings.c.settings_key == "GLOBAL")).mappings().first()
        if not settings:
            conn.execute(insert(q_feature_settings).values(
                settings_key="GLOBAL", charging_enabled=False, updated_at=now,
            ))
        existing = {r[0] for r in conn.execute(select(q_features.c.feature_key)).all()}
        for key, name in FEATURES.items():
            if key not in existing:
                conn.execute(insert(q_features).values(
                    feature_key=key, name=name, enabled=True,
                    default_q_cost=Decimal("0"), created_at=now, updated_at=now,
                ))
        existing_rules = {(r[0], r[1]) for r in conn.execute(select(
            q_feature_tier_rules.c.feature_key, q_feature_tier_rules.c.tier_key
        )).all()}
        for key in FEATURES:
            for tier in TIERS:
                if (key, tier) not in existing_rules:
                    conn.execute(insert(q_feature_tier_rules).values(
                        feature_key=key, tier_key=tier, q_cost=Decimal("0"),
                        enabled=True, included_uses_daily=None,
                        included_uses_monthly=None, discount_percent=Decimal("0"), updated_at=now,
                    ))


class FeatureRuleUpdate(BaseModel):
    q_cost: Decimal = Field(default=Decimal("0"), ge=0)
    enabled: bool = True
    included_uses_daily: Optional[int] = Field(default=None, ge=0)
    included_uses_monthly: Optional[int] = Field(default=None, ge=0)
    discount_percent: Decimal = Field(default=Decimal("0"), ge=0, le=100)


class FeatureQuote(BaseModel):
    feature_key: str
    feature_name: str
    tier_key: str
    q_cost: Decimal
    enabled: bool
    charging_enabled: bool = False
    included_uses_daily: Optional[int] = None
    included_uses_monthly: Optional[int] = None


class GlobalChargingUpdate(BaseModel):
    charging_enabled: bool = False


def _master_key_ok(value: Optional[str]) -> bool:
    expected = os.getenv("LEMMIQ_MASTER_ADMIN_KEY", "").strip()
    return bool(expected and value and value == expected)


def require_master(x_lemmiq_master_key: Optional[str]) -> str:
    if not _master_key_ok(x_lemmiq_master_key):
        raise HTTPException(status_code=403, detail="Master Admin key required")
    return "master"


def quote_feature(feature_key: str, tier_key: str, engine: Engine = ENGINE) -> FeatureQuote:
    key = feature_key.strip().upper()
    tier = tier_key.strip().upper() or "FREE"
    with engine.begin() as conn:
        f = conn.execute(select(q_features).where(q_features.c.feature_key == key)).mappings().first()
        if not f:
            raise KeyError(f"Unknown Q feature: {key}")
        r = conn.execute(select(q_feature_tier_rules).where(
            (q_feature_tier_rules.c.feature_key == key) &
            (q_feature_tier_rules.c.tier_key == tier)
        )).mappings().first()
        configured_cost = Decimal(r["q_cost"] if r else f["default_q_cost"] or 0)
        settings = conn.execute(select(q_feature_settings).where(
            q_feature_settings.c.settings_key == "GLOBAL"
        )).mappings().first()
        charging_enabled = bool(settings and settings["charging_enabled"])
        cost = configured_cost if charging_enabled else Decimal("0")
        enabled = bool(f["enabled"] and (r["enabled"] if r else True))
        return FeatureQuote(
            feature_key=key, feature_name=f["name"], tier_key=tier,
            q_cost=cost, enabled=enabled, charging_enabled=charging_enabled,
            included_uses_daily=(r["included_uses_daily"] if r else None),
            included_uses_monthly=(r["included_uses_monthly"] if r else None),
        )


def record_feature_usage(
    user_id: int,
    feature_key: str,
    tier_key: str,
    quoted_cost: Decimal | float | int = 0,
    charged_cost: Decimal | float | int = 0,
    status: str = "SUCCESS",
    reference: str | None = None,
    metadata_json: str | None = None,
    engine: Engine = ENGINE,
) -> None:
    with engine.begin() as conn:
        conn.execute(insert(q_feature_usage).values(
            user_id=user_id, feature_key=feature_key.upper(), tier_key=tier_key.upper(),
            quoted_cost=Decimal(str(quoted_cost)), charged_cost=Decimal(str(charged_cost)),
            status=status, reference=reference, metadata_json=metadata_json, created_at=now_utc(),
        ))


@router.on_event("startup")
def _startup() -> None:
    init_v2104_q_feature_tables()


@router.get("/q-features/catalog", response_model=list[FeatureQuote])
def catalog(tier_key: str = "FREE") -> list[FeatureQuote]:
    init_v2104_q_feature_tables()
    return [quote_feature(k, tier_key) for k in FEATURES]


@router.get("/q-features/{feature_key}/quote", response_model=FeatureQuote)
def quote(feature_key: str, tier_key: str = "FREE") -> FeatureQuote:
    try:
        return quote_feature(feature_key, tier_key)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/admin/q-features/settings")
def admin_settings(x_lemmiq_master_key: Optional[str] = Header(default=None)):
    require_master(x_lemmiq_master_key)
    init_v2104_q_feature_tables()
    with ENGINE.begin() as conn:
        row = conn.execute(select(q_feature_settings).where(
            q_feature_settings.c.settings_key == "GLOBAL"
        )).mappings().first()
        return {"charging_enabled": bool(row and row["charging_enabled"])}


@router.put("/admin/q-features/settings")
def admin_update_settings(
    body: GlobalChargingUpdate,
    x_lemmiq_master_key: Optional[str] = Header(default=None),
):
    actor = require_master(x_lemmiq_master_key)
    init_v2104_q_feature_tables()
    import json
    with ENGINE.begin() as conn:
        conn.execute(update(q_feature_settings).where(
            q_feature_settings.c.settings_key == "GLOBAL"
        ).values(charging_enabled=body.charging_enabled, updated_at=now_utc()))
        conn.execute(insert(q_feature_admin_audit).values(
            actor=actor, feature_key="GLOBAL", tier_key=None,
            change_json=json.dumps({"charging_enabled": body.charging_enabled}),
            created_at=now_utc(),
        ))
    return {"charging_enabled": body.charging_enabled}


@router.get("/admin/q-features")
def admin_list(x_lemmiq_master_key: Optional[str] = Header(default=None)):
    require_master(x_lemmiq_master_key)
    init_v2104_q_feature_tables()
    with ENGINE.begin() as conn:
        rows = conn.execute(select(q_feature_tier_rules).order_by(
            q_feature_tier_rules.c.feature_key, q_feature_tier_rules.c.tier_key
        )).mappings().all()
        return [dict(r) for r in rows]


@router.put("/admin/q-features/{feature_key}/{tier_key}", response_model=FeatureQuote)
def admin_update(
    feature_key: str,
    tier_key: str,
    body: FeatureRuleUpdate,
    x_lemmiq_master_key: Optional[str] = Header(default=None),
):
    actor = require_master(x_lemmiq_master_key)
    key = feature_key.strip().upper()
    tier = tier_key.strip().upper()
    if key not in FEATURES:
        raise HTTPException(status_code=404, detail="Unknown feature key")
    if tier not in TIERS:
        raise HTTPException(status_code=400, detail=f"Unknown tier. Use one of: {', '.join(TIERS)}")
    import json
    with ENGINE.begin() as conn:
        result = conn.execute(update(q_feature_tier_rules).where(
            (q_feature_tier_rules.c.feature_key == key) &
            (q_feature_tier_rules.c.tier_key == tier)
        ).values(
            q_cost=body.q_cost, enabled=body.enabled,
            included_uses_daily=body.included_uses_daily,
            included_uses_monthly=body.included_uses_monthly,
            discount_percent=body.discount_percent, updated_at=now_utc(),
        ))
        if result.rowcount == 0:
            conn.execute(insert(q_feature_tier_rules).values(
                feature_key=key, tier_key=tier, q_cost=body.q_cost, enabled=body.enabled,
                included_uses_daily=body.included_uses_daily,
                included_uses_monthly=body.included_uses_monthly,
                discount_percent=body.discount_percent, updated_at=now_utc(),
            ))
        conn.execute(insert(q_feature_admin_audit).values(
            actor=actor, feature_key=key, tier_key=tier,
            change_json=json.dumps(body.model_dump(mode="json")), created_at=now_utc(),
        ))
    return quote_feature(key, tier)


@router.get("/version")
def version():
    return {"version": VERSION, "name": "LEMMIQ V2.10.4", "q_feature_default_cost": 0}
