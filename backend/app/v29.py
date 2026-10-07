"""LEMMIQ V2.9 — Q Predict test markets + analytics tracking.

Q Predict uses isolated Predict Credits (PC) only. Predict Credits cannot be
bought, sold, transferred, converted to Q, used in Q Market, or withdrawn.
Real-Q staking is deliberately disabled in this build.

The market engine supports:
- pooled YES / NO test-credit markets
- admin-reviewed AI/automation drafts
- deterministic automatic resolution for supported source adapters
- user discussion, watchlist, history and leaderboard
- simulated platform fee on winning *profit* only
- passive monetisation tracking and Q supply/demand simulation dashboards
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import math
import os
import secrets
from datetime import date, datetime, timedelta, timezone
from typing import Any

import requests
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import BigInteger, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, and_, func, or_, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from .database import Base, SessionLocal
from .models import User
from .v28 import (
    QAdminRole,
    QLedgerEntry,
    QMarketOrder,
    QSystemWallet,
    QUserWallet,
    QEconomyConfig,
)

log = logging.getLogger("lemmiq.v29")

PC_MICROS = 1_000_000
DEFAULT_STARTING_PC = 10_000
DEFAULT_FEE_BPS = 500  # 5% of winner profit, not stake
ALLOWED_OUTCOMES = {"YES", "NO"}
PREDICT_ADMIN_ROLES = {"MASTER_ADMIN", "RISK_ADMIN", "FINANCE_ADMIN", "READ_ONLY"}
PREDICT_WRITE_ROLES = {"MASTER_ADMIN", "RISK_ADMIN"}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _pc(v: int) -> float:
    return round(v / PC_MICROS, 6)


def _pc_micros(v: float) -> int:
    return int(round(float(v) * PC_MICROS))


def _txid(prefix: str) -> str:
    return f"{prefix}-{utcnow().strftime('%Y%m%d%H%M%S')}-{secrets.token_hex(5).upper()}"


class PredictConfig(Base):
    __tablename__ = "q_predict_config"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    test_mode: Mapped[bool] = mapped_column(Boolean, default=True)
    real_q_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    starting_credits_micros: Mapped[int] = mapped_column(BigInteger, default=DEFAULT_STARTING_PC * PC_MICROS)
    fee_bps: Mapped[int] = mapped_column(Integer, default=DEFAULT_FEE_BPS)
    test_treasury_micros: Mapped[int] = mapped_column(BigInteger, default=0)
    discovery_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    auto_drafting: Mapped[bool] = mapped_column(Boolean, default=True)
    auto_publish: Mapped[bool] = mapped_column(Boolean, default=False)
    auto_settlement: Mapped[bool] = mapped_column(Boolean, default=True)
    max_live_markets: Mapped[int] = mapped_column(Integer, default=30)
    max_new_markets_per_day: Mapped[int] = mapped_column(Integer, default=10)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PredictWallet(Base):
    __tablename__ = "q_predict_wallets"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    balance_micros: Mapped[int] = mapped_column(BigInteger, default=0)
    lifetime_won_micros: Mapped[int] = mapped_column(BigInteger, default=0)
    lifetime_staked_micros: Mapped[int] = mapped_column(BigInteger, default=0)
    markets_won: Mapped[int] = mapped_column(Integer, default=0)
    markets_resolved: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PredictLedger(Base):
    __tablename__ = "q_predict_ledger"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tx_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    market_id: Mapped[int | None] = mapped_column(ForeignKey("q_predict_markets.id"), nullable=True, index=True)
    kind: Mapped[str] = mapped_column(String(40), index=True)
    delta_micros: Mapped[int] = mapped_column(BigInteger)
    note: Mapped[str] = mapped_column(String(240), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class PredictMarket(Base):
    __tablename__ = "q_predict_markets"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    market_key: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    question: Mapped[str] = mapped_column(String(260))
    category: Mapped[str] = mapped_column(String(40), default="TRENDING", index=True)
    template_code: Mapped[str] = mapped_column(String(60), default="MANUAL", index=True)
    status: Mapped[str] = mapped_column(String(24), default="REVIEW", index=True)
    resolution_source_name: Mapped[str] = mapped_column(String(120), default="Admin")
    resolution_source_url: Mapped[str] = mapped_column(String(500), default="")
    resolution_rule: Mapped[str] = mapped_column(Text, default="")
    source_type: Mapped[str] = mapped_column(String(40), default="MANUAL", index=True)
    source_config_json: Mapped[str] = mapped_column(Text, default="{}")
    close_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    resolve_after: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    result: Mapped[str | None] = mapped_column(String(12), nullable=True)
    yes_pool_micros: Mapped[int] = mapped_column(BigInteger, default=0)
    no_pool_micros: Mapped[int] = mapped_column(BigInteger, default=0)
    participant_count: Mapped[int] = mapped_column(Integer, default=0)
    comment_count: Mapped[int] = mapped_column(Integer, default=0)
    trend_score: Mapped[int] = mapped_column(Integer, default=50)
    resolution_confidence: Mapped[int] = mapped_column(Integer, default=100)
    agent_reason: Mapped[str] = mapped_column(Text, default="")
    generated_by: Mapped[str] = mapped_column(String(40), default="ADMIN")
    auto_resolve: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    approved_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    resolved_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PredictPosition(Base):
    __tablename__ = "q_predict_positions"
    __table_args__ = (UniqueConstraint("user_id", "market_id", "outcome", name="uq_predict_user_market_outcome"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    market_id: Mapped[int] = mapped_column(ForeignKey("q_predict_markets.id"), index=True)
    outcome: Mapped[str] = mapped_column(String(8), index=True)
    stake_micros: Mapped[int] = mapped_column(BigInteger, default=0)
    payout_micros: Mapped[int] = mapped_column(BigInteger, default=0)
    fee_micros: Mapped[int] = mapped_column(BigInteger, default=0)
    status: Mapped[str] = mapped_column(String(20), default="OPEN", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PredictTrade(Base):
    __tablename__ = "q_predict_trades"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    market_id: Mapped[int] = mapped_column(ForeignKey("q_predict_markets.id"), index=True)
    outcome: Mapped[str] = mapped_column(String(8), index=True)
    amount_micros: Mapped[int] = mapped_column(BigInteger)
    probability_before: Mapped[float] = mapped_column(Float, default=50.0)
    probability_after: Mapped[float] = mapped_column(Float, default=50.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class PredictComment(Base):
    __tablename__ = "q_predict_comments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    market_id: Mapped[int] = mapped_column(ForeignKey("q_predict_markets.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    text: Mapped[str] = mapped_column(String(1000))
    hidden: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class PredictWatch(Base):
    __tablename__ = "q_predict_watchlist"
    __table_args__ = (UniqueConstraint("user_id", "market_id", name="uq_predict_watch"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    market_id: Mapped[int] = mapped_column(ForeignKey("q_predict_markets.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PredictResolution(Base):
    __tablename__ = "q_predict_resolutions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    market_id: Mapped[int] = mapped_column(ForeignKey("q_predict_markets.id"), unique=True, index=True)
    outcome: Mapped[str] = mapped_column(String(12))
    source_value: Mapped[str] = mapped_column(String(400), default="")
    evidence_json: Mapped[str] = mapped_column(Text, default="{}")
    note: Mapped[str] = mapped_column(String(500), default="")
    resolved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ShadowMonetisationEvent(Base):
    __tablename__ = "q_shadow_monetisation_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    feature: Mapped[str] = mapped_column(String(60), index=True)
    estimated_cost_microusd: Mapped[int] = mapped_column(BigInteger, default=0)
    simulated_q_micros: Mapped[int] = mapped_column(BigInteger, default=0)
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    note: Mapped[str] = mapped_column(String(240), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class QSimulationSnapshot(Base):
    __tablename__ = "q_supply_demand_snapshots"
    snapshot_date: Mapped[date] = mapped_column(Date, primary_key=True)
    actual_price_microusd: Mapped[int] = mapped_column(BigInteger)
    simulated_price_microusd: Mapped[int] = mapped_column(BigInteger)
    demand_score: Mapped[float] = mapped_column(Float, default=0)
    supply_score: Mapped[float] = mapped_column(Float, default=0)
    raw_change_percent: Mapped[float] = mapped_column(Float, default=0)
    applied_change_percent: Mapped[float] = mapped_column(Float, default=0)
    details_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PredictStakeIn(BaseModel):
    outcome: str
    amount_pc: float = Field(gt=0, le=10_000_000)


class PredictCommentIn(BaseModel):
    text: str = Field(min_length=1, max_length=1000)


class PredictMarketIn(BaseModel):
    question: str = Field(min_length=8, max_length=260)
    category: str = Field(default="TRENDING", max_length=40)
    template_code: str = Field(default="MANUAL", max_length=60)
    close_at: datetime
    resolve_after: datetime | None = None
    resolution_source_name: str = Field(default="Admin", max_length=120)
    resolution_source_url: str = Field(default="", max_length=500)
    resolution_rule: str = Field(min_length=5, max_length=3000)
    source_type: str = Field(default="MANUAL", max_length=40)
    source_config: dict[str, Any] = Field(default_factory=dict)
    trend_score: int = Field(default=50, ge=0, le=100)
    resolution_confidence: int = Field(default=100, ge=0, le=100)
    auto_resolve: bool = False


class PredictResolveIn(BaseModel):
    outcome: str
    source_value: str = Field(default="", max_length=400)
    note: str = Field(default="", max_length=500)


class PredictConfigIn(BaseModel):
    starting_credits_pc: float | None = Field(default=None, ge=100, le=1_000_000)
    fee_percent: float | None = Field(default=None, ge=0, le=20)
    discovery_enabled: bool | None = None
    auto_drafting: bool | None = None
    auto_publish: bool | None = None
    auto_settlement: bool | None = None
    max_live_markets: int | None = Field(default=None, ge=1, le=500)
    max_new_markets_per_day: int | None = Field(default=None, ge=1, le=100)


FEATURE_ESTIMATES = {
    "Q_AGENT": (10_000, 0.25),      # US$0.0100 estimated / 0.25Q simulated
    "Q_VISION": (30_000, 1.00),
    "TRUST": (20_000, 0.50),
    "CHAT_SUMMARY": (15_000, 0.25),
    "Q_TO_Q": (10_000, 0.50),
    "BUSINESS_AGENT": (20_000, 2.00),
}


def track_shadow_event(db: Session, user_id: int | None, feature: str, *, success: bool = True, note: str = ""):
    """Record analysis-only monetisation data. Never debits Q."""
    feature = (feature or "OTHER").upper()[:60]
    cost, fee_q = FEATURE_ESTIMATES.get(feature, (10_000, 0.25))
    db.add(ShadowMonetisationEvent(
        user_id=user_id,
        feature=feature,
        estimated_cost_microusd=cost,
        simulated_q_micros=_pc_micros(fee_q),
        success=bool(success),
        note=(note or "")[:240],
    ))


def _config(db: Session) -> PredictConfig:
    row = db.get(PredictConfig, 1)
    if not row:
        row = PredictConfig(id=1)
        db.add(row)
        db.flush()
    return row


def _wallet(db: Session, uid: int) -> PredictWallet:
    row = db.get(PredictWallet, uid)
    if row:
        return row
    cfg = _config(db)
    row = PredictWallet(user_id=uid, balance_micros=cfg.starting_credits_micros)
    db.add(row)
    db.flush()
    db.add(PredictLedger(
        tx_id=_txid("PC-START"), user_id=uid, kind="STARTING_CREDITS",
        delta_micros=cfg.starting_credits_micros, note="Q Predict testing balance",
    ))
    return row


def _admin_role(db: Session, uid: int) -> str | None:
    r = db.get(QAdminRole, uid)
    return r.role if r and r.active else None


def _require_admin(db: Session, u: User, write: bool = False):
    role = _admin_role(db, u.id)
    allowed = PREDICT_WRITE_ROLES if write else PREDICT_ADMIN_ROLES
    if role not in allowed:
        raise HTTPException(403, "Q Predict admin permission required")
    return role


def _probabilities(m: PredictMarket) -> tuple[float, float]:
    total = m.yes_pool_micros + m.no_pool_micros
    if total <= 0:
        return 50.0, 50.0
    yes = round(m.yes_pool_micros * 100 / total, 1)
    return yes, round(100 - yes, 1)


def _market_json(db: Session, m: PredictMarket, viewer_id: int | None = None, include_comments: bool = False):
    yes, no = _probabilities(m)
    pos = []
    watched = False
    if viewer_id:
        pos = db.scalars(select(PredictPosition).where(PredictPosition.market_id == m.id, PredictPosition.user_id == viewer_id)).all()
        watched = bool(db.scalar(select(func.count()).select_from(PredictWatch).where(PredictWatch.market_id == m.id, PredictWatch.user_id == viewer_id)))
    out = {
        "id": m.id, "market_key": m.market_key, "question": m.question,
        "category": m.category, "template_code": m.template_code, "status": m.status,
        "yes_percent": yes, "no_percent": no,
        "yes_pool_pc": _pc(m.yes_pool_micros), "no_pool_pc": _pc(m.no_pool_micros),
        "pool_pc": _pc(m.yes_pool_micros + m.no_pool_micros),
        "participants": m.participant_count, "comments": m.comment_count,
        "trend_score": m.trend_score, "resolution_confidence": m.resolution_confidence,
        "resolution_source_name": m.resolution_source_name,
        "resolution_source_url": m.resolution_source_url,
        "resolution_rule": m.resolution_rule, "source_type": m.source_type,
        "close_at": m.close_at.isoformat(), "resolve_after": m.resolve_after.isoformat(),
        "result": m.result, "auto_resolve": bool(m.auto_resolve),
        "generated_by": m.generated_by, "agent_reason": m.agent_reason,
        "watched": watched,
        "my_positions": [{
            "outcome": p.outcome, "stake_pc": _pc(p.stake_micros), "payout_pc": _pc(p.payout_micros),
            "fee_pc": _pc(p.fee_micros), "status": p.status,
        } for p in pos],
        "created_at": m.created_at.isoformat(), "updated_at": m.updated_at.isoformat(),
    }
    res = db.scalar(select(PredictResolution).where(PredictResolution.market_id == m.id))
    out["resolution"] = ({
        "outcome": res.outcome, "source_value": res.source_value,
        "note": res.note, "resolved_at": res.resolved_at.isoformat(),
    } if res else None)
    if include_comments:
        rows = db.scalars(select(PredictComment).where(PredictComment.market_id == m.id, PredictComment.hidden == False).order_by(PredictComment.created_at.asc()).limit(250)).all()
        users = {x.user_id: db.get(User, x.user_id) for x in rows}
        out["discussion"] = [{
            "id": x.id, "text": x.text, "created_at": x.created_at.isoformat(),
            "user": ({"id": users[x.user_id].id, "username": users[x.user_id].username, "display_name": users[x.user_id].display_name} if users.get(x.user_id) else None),
        } for x in rows]
    return out


def _ledger(db: Session, uid: int, kind: str, delta: int, market_id: int | None = None, note: str = ""):
    db.add(PredictLedger(tx_id=_txid(kind[:10]), user_id=uid, market_id=market_id, kind=kind, delta_micros=delta, note=note[:240]))


def _dedupe_key(template: str, source: dict[str, Any], close_at: datetime) -> str:
    raw = json.dumps({"t": template, "s": source, "d": close_at.strftime("%Y-%m-%dT%H")}, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def _create_market(db: Session, body: PredictMarketIn, *, creator_id: int | None = None, generated_by: str = "ADMIN", status: str = "REVIEW", reason: str = ""):
    close_at = body.close_at.astimezone(timezone.utc) if body.close_at.tzinfo else body.close_at.replace(tzinfo=timezone.utc)
    resolve_after = body.resolve_after or close_at
    resolve_after = resolve_after.astimezone(timezone.utc) if resolve_after.tzinfo else resolve_after.replace(tzinfo=timezone.utc)
    if close_at <= utcnow() + timedelta(minutes=5):
        raise HTTPException(422, "Market close time must be at least 5 minutes in the future")
    key_source = dict(body.source_config or {})
    if body.template_code.upper().strip() == "MANUAL":
        # Manual markets may share a deadline; include their actual contract text in the dedupe signature.
        key_source = {"question": body.question.strip().lower(), "source": body.resolution_source_name.strip().lower()}
    key = _dedupe_key(body.template_code, key_source, close_at)
    existing = db.scalar(select(PredictMarket).where(PredictMarket.market_key == key))
    if existing:
        return existing
    m = PredictMarket(
        market_key=key, question=body.question.strip(), category=body.category.upper().strip()[:40],
        template_code=body.template_code.upper().strip()[:60], status=status,
        resolution_source_name=body.resolution_source_name.strip(), resolution_source_url=body.resolution_source_url.strip(),
        resolution_rule=body.resolution_rule.strip(), source_type=body.source_type.upper().strip()[:40],
        source_config_json=json.dumps(body.source_config, ensure_ascii=False), close_at=close_at, resolve_after=resolve_after,
        trend_score=body.trend_score, resolution_confidence=body.resolution_confidence,
        agent_reason=reason[:5000], generated_by=generated_by[:40], auto_resolve=bool(body.auto_resolve),
        created_by_user_id=creator_id,
    )
    db.add(m); db.flush()
    return m


def _stake(db: Session, u: User, m: PredictMarket, outcome: str, amount_micros: int):
    cfg = _config(db)
    if not cfg.enabled or not cfg.test_mode or cfg.real_q_enabled:
        raise HTTPException(409, "Q Predict test-credit mode is not available")
    if m.status != "LIVE" or utcnow() >= m.close_at:
        raise HTTPException(409, "This market is closed")
    outcome = outcome.upper()
    if outcome not in ALLOWED_OUTCOMES:
        raise HTTPException(422, "Outcome must be YES or NO")
    w = _wallet(db, u.id)
    if amount_micros <= 0 or w.balance_micros < amount_micros:
        raise HTTPException(409, "Not enough Predict Credits")
    before_yes, _ = _probabilities(m)
    existing_positions = db.scalars(select(PredictPosition).where(PredictPosition.user_id == u.id, PredictPosition.market_id == m.id)).all()
    had_any = bool(existing_positions)
    if any(x.outcome != outcome and x.stake_micros > 0 for x in existing_positions):
        raise HTTPException(409, "You already predicted the other side of this market. Test mode keeps one outcome per user per market.")
    p = next((x for x in existing_positions if x.outcome == outcome), None)
    if not p:
        p = PredictPosition(user_id=u.id, market_id=m.id, outcome=outcome)
        db.add(p); db.flush()
    p.stake_micros += amount_micros; p.updated_at = utcnow()
    w.balance_micros -= amount_micros; w.lifetime_staked_micros += amount_micros; w.updated_at = utcnow()
    if outcome == "YES": m.yes_pool_micros += amount_micros
    else: m.no_pool_micros += amount_micros
    if not had_any: m.participant_count += 1
    m.updated_at = utcnow()
    after_yes, _ = _probabilities(m)
    db.add(PredictTrade(user_id=u.id, market_id=m.id, outcome=outcome, amount_micros=amount_micros, probability_before=before_yes, probability_after=after_yes))
    _ledger(db, u.id, "MARKET_STAKE", -amount_micros, m.id, f"{outcome} on {m.question[:120]}")


def _settle_market(db: Session, m: PredictMarket, outcome: str, source_value: str = "", note: str = "", resolver_id: int | None = None, evidence: dict | None = None):
    if m.status in {"RESOLVED", "VOID", "CANCELLED"}:
        return
    outcome = outcome.upper()
    if outcome not in {"YES", "NO", "VOID"}:
        raise HTTPException(422, "Outcome must be YES, NO or VOID")
    cfg = _config(db)
    positions = db.scalars(select(PredictPosition).where(PredictPosition.market_id == m.id)).all()
    if outcome == "VOID":
        for p in positions:
            w = _wallet(db, p.user_id)
            w.balance_micros += p.stake_micros; w.updated_at = utcnow()
            p.payout_micros = p.stake_micros; p.status = "VOID"; p.updated_at = utcnow()
            _ledger(db, p.user_id, "MARKET_VOID_REFUND", p.stake_micros, m.id, "Market voided; stake returned")
        m.status = "VOID"; m.result = "VOID"
    else:
        winning_pool = m.yes_pool_micros if outcome == "YES" else m.no_pool_micros
        losing_pool = m.no_pool_micros if outcome == "YES" else m.yes_pool_micros
        # If nobody backed the eventual winner, all stakes are returned. This avoids orphaned test-credit pools.
        if winning_pool <= 0:
            for p in positions:
                w = _wallet(db, p.user_id); w.balance_micros += p.stake_micros; w.updated_at = utcnow()
                p.payout_micros = p.stake_micros; p.status = "VOID"; p.updated_at = utcnow()
                _ledger(db, p.user_id, "MARKET_NO_WINNER_REFUND", p.stake_micros, m.id, "No winning-side participants")
            outcome = "VOID"; m.status = "VOID"; m.result = "VOID"
        else:
            winners_by_user: set[int] = set()
            resolved_users: set[int] = set()
            for p in positions:
                resolved_users.add(p.user_id)
                if p.outcome == outcome:
                    gross_profit = (losing_pool * p.stake_micros) // winning_pool
                    fee = (gross_profit * cfg.fee_bps) // 10_000
                    payout = p.stake_micros + gross_profit - fee
                    w = _wallet(db, p.user_id)
                    w.balance_micros += payout; w.lifetime_won_micros += gross_profit - fee; w.updated_at = utcnow()
                    p.payout_micros = payout; p.fee_micros = fee; p.status = "WON"; p.updated_at = utcnow()
                    cfg.test_treasury_micros += fee
                    winners_by_user.add(p.user_id)
                    _ledger(db, p.user_id, "MARKET_PAYOUT", payout, m.id, f"{outcome} resolved; simulated fee {_pc(fee)} PC")
                else:
                    p.status = "LOST"; p.payout_micros = 0; p.updated_at = utcnow()
            for uid in resolved_users:
                w = _wallet(db, uid); w.markets_resolved += 1
                if uid in winners_by_user: w.markets_won += 1
            m.status = "RESOLVED"; m.result = outcome
    m.resolved_at = utcnow(); m.resolved_by_user_id = resolver_id; m.updated_at = utcnow()
    db.add(PredictResolution(market_id=m.id, outcome=m.result or outcome, source_value=source_value[:400], evidence_json=json.dumps(evidence or {}, ensure_ascii=False)[:16000], note=note[:500]))


def _coingecko_price(coin_id: str, currency: str = "usd") -> float:
    r = requests.get(
        "https://api.coingecko.com/api/v3/simple/price",
        params={"ids": coin_id, "vs_currencies": currency}, timeout=12,
        headers={"User-Agent": "LEMMIQ-QPredict/2.9"},
    )
    r.raise_for_status()
    return float(r.json()[coin_id][currency])


def _resolve_from_source(db: Session, m: PredictMarket) -> tuple[str, str, dict]:
    cfg = json.loads(m.source_config_json or "{}")
    if m.source_type == "COINGECKO_PRICE":
        coin = cfg.get("coin_id", "bitcoin"); currency = cfg.get("currency", "usd")
        value = _coingecko_price(coin, currency)
        target = float(cfg["target"]); op = cfg.get("operator", ">=")
        yes = value >= target if op == ">=" else value > target if op == ">" else value <= target if op == "<=" else value < target
        return ("YES" if yes else "NO", f"{coin} {currency.upper()} {value:.4f}", {"value": value, "target": target, "operator": op, "coin_id": coin, "currency": currency})
    if m.source_type == "LEMMIQ_METRIC":
        metric = str(cfg.get("metric", "registered_users"))
        target = int(cfg.get("target", 0)); op = cfg.get("operator", ">=")
        if metric == "registered_users": value = int(db.scalar(select(func.count()).select_from(User)) or 0)
        elif metric == "q_market_orders": value = int(db.scalar(select(func.count()).select_from(QMarketOrder)) or 0)
        elif metric == "q_market_completed": value = int(db.scalar(select(func.count()).select_from(QMarketOrder).where(QMarketOrder.status == "COMPLETED")) or 0)
        else: raise RuntimeError(f"Unsupported LEMMIQ metric: {metric}")
        yes = value >= target if op == ">=" else value > target if op == ">" else value <= target if op == "<=" else value < target
        return ("YES" if yes else "NO", f"{metric}={value}", {"metric": metric, "value": value, "target": target, "operator": op})
    raise RuntimeError("This market requires admin resolution")


def _round_market_target(value: float) -> float:
    if value >= 100_000: step = 5_000
    elif value >= 10_000: step = 1_000
    elif value >= 1_000: step = 100
    elif value >= 100: step = 10
    else: step = 1
    return round(value / step) * step


def _has_open_candidate(db: Session, template_code: str, signature: dict[str, Any]) -> bool:
    rows = db.scalars(select(PredictMarket).where(
        PredictMarket.template_code == template_code,
        PredictMarket.status.in_(["REVIEW", "LIVE", "CLOSED", "RESOLVING"]),
    )).all()
    for row in rows:
        if row.status == "LIVE" and row.close_at <= utcnow():
            continue
        try:
            cfg = json.loads(row.source_config_json or "{}")
        except Exception:
            cfg = {}
        if all(cfg.get(k) == v for k, v in signature.items()):
            return True
    return False


def _auto_candidates(db: Session) -> list[PredictMarket]:
    cfg = _config(db)
    if not (cfg.enabled and cfg.test_mode and cfg.discovery_enabled and cfg.auto_drafting): return []
    today_count = int(db.scalar(select(func.count()).select_from(PredictMarket).where(PredictMarket.created_at >= datetime.combine(utcnow().date(), datetime.min.time(), tzinfo=timezone.utc))) or 0)
    slots = max(0, cfg.max_new_markets_per_day - today_count)
    if slots <= 0: return []
    created: list[PredictMarket] = []
    close = utcnow().replace(minute=0, second=0, microsecond=0) + timedelta(hours=24)
    for coin_id, label, category in [("bitcoin", "BTC", "CRYPTO"), ("ethereum", "ETH", "CRYPTO")]:
        if len(created) >= slots: break
        if _has_open_candidate(db, "CRYPTO_PRICE_ABOVE_24H", {"coin_id": coin_id, "currency": "usd"}):
            continue
        try:
            current = _coingecko_price(coin_id)
            target = _round_market_target(current * 1.01)
            body = PredictMarketIn(
                question=f"Will {label} be at or above US${target:,.0f} at the Q Predict resolution time?",
                category=category, template_code="CRYPTO_PRICE_ABOVE_24H", close_at=close,
                resolve_after=close, resolution_source_name="CoinGecko", resolution_source_url="https://www.coingecko.com/",
                resolution_rule=f"YES if CoinGecko reports {label} USD price >= US${target:,.0f} when the market resolves; otherwise NO.",
                source_type="COINGECKO_PRICE", source_config={"coin_id": coin_id, "currency": "usd", "operator": ">=", "target": target},
                trend_score=82, resolution_confidence=98, auto_resolve=True,
            )
            m = _create_market(db, body, generated_by="Q_PREDICT_AGENT", status="LIVE" if cfg.auto_publish else "REVIEW", reason=f"Deterministic 24-hour crypto template. Reference price at draft: {current:.4f} USD.")
            if cfg.auto_publish and m.status == "REVIEW": m.status = "LIVE"
            created.append(m)
        except Exception as e:
            log.warning("Q Predict crypto draft failed for %s: %s", coin_id, e)

    if len(created) < slots and not _has_open_candidate(db, "LEMMIQ_USERS_7D", {"metric": "registered_users"}):
        user_count = int(db.scalar(select(func.count()).select_from(User)) or 0)
        target = max(10, int(math.ceil((user_count + max(5, user_count * .05)) / 10) * 10))
        close7 = utcnow().replace(minute=0, second=0, microsecond=0) + timedelta(days=7)
        body = PredictMarketIn(
            question=f"Will LEMMIQ reach {target:,} registered users within 7 days?", category="LEMMIQ",
            template_code="LEMMIQ_USERS_7D", close_at=close7, resolve_after=close7,
            resolution_source_name="LEMMIQ database", resolution_rule=f"YES if registered users >= {target:,} at resolution; otherwise NO.",
            source_type="LEMMIQ_METRIC", source_config={"metric":"registered_users","operator":">=","target":target},
            trend_score=68, resolution_confidence=100, auto_resolve=True,
        )
        m = _create_market(db, body, generated_by="Q_PREDICT_AGENT", status="LIVE" if cfg.auto_publish else "REVIEW", reason="Internal growth market generated from the live user count.")
        created.append(m)

    if len(created) < slots and not _has_open_candidate(db, "QMARKET_COMPLETED_7D", {"metric": "q_market_completed"}):
        completed = int(db.scalar(select(func.count()).select_from(QMarketOrder).where(QMarketOrder.status == "COMPLETED")) or 0)
        target = max(10, int(math.ceil((completed + 5) / 5) * 5))
        close7 = utcnow().replace(minute=0, second=0, microsecond=0) + timedelta(days=7)
        body = PredictMarketIn(
            question=f"Will Q Market reach {target:,} completed orders within 7 days?", category="LEMMIQ",
            template_code="QMARKET_COMPLETED_7D", close_at=close7, resolve_after=close7,
            resolution_source_name="LEMMIQ Q Market database", resolution_rule=f"YES if completed Q Market orders >= {target:,} at resolution; otherwise NO.",
            source_type="LEMMIQ_METRIC", source_config={"metric":"q_market_completed","operator":">=","target":target},
            trend_score=62, resolution_confidence=100, auto_resolve=True,
        )
        created.append(_create_market(db, body, generated_by="Q_PREDICT_AGENT", status="LIVE" if cfg.auto_publish else "REVIEW", reason="Internal marketplace activity market."))
    return created


def _settle_due(db: Session) -> dict[str, int]:
    cfg = _config(db); now = utcnow(); closed = resolved = failed = 0
    for m in db.scalars(select(PredictMarket).where(PredictMarket.status == "LIVE", PredictMarket.close_at <= now)).all():
        m.status = "CLOSED"; m.updated_at = now; closed += 1
    if cfg.auto_settlement:
        rows = db.scalars(select(PredictMarket).where(PredictMarket.status.in_(["CLOSED", "RESOLVING"]), PredictMarket.resolve_after <= now, PredictMarket.auto_resolve == True)).all()
        for m in rows:
            try:
                m.status = "RESOLVING"; db.flush()
                outcome, value, evidence = _resolve_from_source(db, m)
                _settle_market(db, m, outcome, value, "Automatically resolved from the configured source.", None, evidence)
                resolved += 1
            except Exception as e:
                m.status = "CLOSED"; m.updated_at = now; failed += 1
                log.warning("Q Predict auto resolution failed for %s: %s", m.id, e)
    return {"closed": closed, "resolved": resolved, "failed": failed}


def _range_start(period: str) -> datetime:
    now = utcnow(); p=(period or "7d").lower()
    if p in {"today","day","1d"}: return now.replace(hour=0,minute=0,second=0,microsecond=0)
    if p in {"7d","week","weekly"}: return now-timedelta(days=7)
    if p in {"month","monthly","30d"}: return now-timedelta(days=30)
    if p in {"quarter","quarterly","90d"}: return now-timedelta(days=90)
    if p in {"year","yearly","365d"}: return now-timedelta(days=365)
    return now-timedelta(days=7)


def _supply_demand_snapshot(db: Session, persist: bool = True):
    cfgq = db.get(QEconomyConfig, 1)
    if not cfgq: return None
    start = utcnow()-timedelta(days=7)
    rows = db.scalars(select(QLedgerEntry).where(QLedgerEntry.created_at >= start)).all()
    issuance_kinds={"SIGNUP_BONUS","BASIC_DAILY","PACKAGE_ACCRUAL","REFERRAL_REWARD","REFERRAL_WELCOME","REFERRAL_PACKAGE_REWARD","PROMOTION"}
    issued=sum(x.amount_micros for x in rows if x.kind in issuance_kinds and x.to_user_id)
    market_spend=sum(x.amount_micros for x in rows if x.kind.startswith("MARKET_") and x.from_user_id)
    profit_in=sum(x.amount_micros for x in rows if x.to_system_key=="PROFIT")
    unique_spenders=len({x.from_user_id for x in rows if x.from_user_id and (x.to_system_key=="PROFIT" or x.kind.startswith("MARKET_"))})
    circulation=float(db.scalar(select(func.coalesce(func.sum(QUserWallet.balance_micros),0))) or 0)
    # Normalised weekly pressure: demand uses spend/profit/unique spender signals; supply uses issuance relative to circulation.
    demand_score=(market_spend+profit_in)/max(1,circulation)*100 + min(5.0,unique_spenders/100)
    supply_score=issued/max(1,circulation)*100
    raw=(demand_score-supply_score)*0.5
    applied=max(-5.0,min(5.0,raw))
    previous=db.scalar(select(QSimulationSnapshot).order_by(QSimulationSnapshot.snapshot_date.desc()).limit(1))
    base=previous.simulated_price_microusd if previous else cfgq.q_price_microusd
    simulated=max(1,int(round(base*(1+applied/100))))
    details={"issued_q":issued/PC_MICROS,"market_spend_q":market_spend/PC_MICROS,"profit_wallet_in_q":profit_in/PC_MICROS,"unique_spenders":unique_spenders,"circulating_user_q":circulation/PC_MICROS,"smoothing":0.5,"weekly_cap_percent":5}
    if persist:
        snap=db.get(QSimulationSnapshot,utcnow().date())
        if not snap:
            snap=QSimulationSnapshot(snapshot_date=utcnow().date(),actual_price_microusd=cfgq.q_price_microusd,simulated_price_microusd=simulated)
            db.add(snap)
        snap.actual_price_microusd=cfgq.q_price_microusd;snap.simulated_price_microusd=simulated;snap.demand_score=demand_score;snap.supply_score=supply_score;snap.raw_change_percent=raw;snap.applied_change_percent=applied;snap.details_json=json.dumps(details)
    return {"mode":"SIMULATION_ONLY","actual_price_usd":cfgq.q_price_microusd/1_000_000,"simulated_price_usd":simulated/1_000_000,"demand_score":round(demand_score,4),"supply_score":round(supply_score,4),"raw_change_percent":round(raw,4),"applied_change_percent":round(applied,4),"details":details}


_scheduler_task: asyncio.Task | None = None


async def _scheduler():
    # Lightweight single-process beta scheduler. It never auto-publishes unless Master Admin enables that switch.
    last_agent: datetime | None = None
    while True:
        try:
            with SessionLocal() as db:
                _settle_due(db)
                cfg = _config(db)
                now = utcnow()
                if cfg.discovery_enabled and cfg.auto_drafting and (last_agent is None or now-last_agent >= timedelta(hours=6)):
                    _auto_candidates(db); last_agent=now
                _supply_demand_snapshot(db, persist=True)
                db.commit()
        except Exception:
            log.exception("Q Predict scheduler iteration failed")
        await asyncio.sleep(300)


def register_v29(app, current_user, get_db):
    router = APIRouter(prefix="/v29", tags=["LEMMIQ V2.9 Q Predict"])

    @app.on_event("startup")
    async def _start_predict_scheduler():
        global _scheduler_task
        if _scheduler_task is None or _scheduler_task.done():
            _scheduler_task = asyncio.create_task(_scheduler())

    @router.get("/predict/home")
    def home(category: str = "", u: User = Depends(current_user), db: Session = Depends(get_db)):
        _settle_due(db)
        w=_wallet(db,u.id);cfg=_config(db)
        stmt=select(PredictMarket).where(PredictMarket.status.in_(["LIVE","CLOSED","RESOLVING","RESOLVED"]))
        if category.strip() and category.upper() not in {"ALL","TRENDING"}: stmt=stmt.where(PredictMarket.category==category.upper().strip())
        rows=db.scalars(stmt.order_by(PredictMarket.trend_score.desc(),PredictMarket.created_at.desc()).limit(80)).all()
        live=[x for x in rows if x.status=="LIVE" and x.close_at>utcnow()]
        resolved=[x for x in rows if x.status in {"RESOLVED","VOID"}]
        db.commit()
        return {
            "mode":"TEST_CREDITS_ONLY","real_q_enabled":False,
            "wallet":{"balance_pc":_pc(w.balance_micros),"starting_pc":_pc(cfg.starting_credits_micros),"lifetime_won_pc":_pc(w.lifetime_won_micros),"lifetime_staked_pc":_pc(w.lifetime_staked_micros),"markets_won":w.markets_won,"markets_resolved":w.markets_resolved},
            "fee_percent":cfg.fee_bps/100,
            "notice":"Predict Credits are test-only and cannot be bought, transferred, converted to Q, used in Q Market or withdrawn.",
            "live":[_market_json(db,x,u.id) for x in live],
            "resolved":[_market_json(db,x,u.id) for x in resolved[:20]],
            "categories":["TRENDING","CRYPTO","ECONOMY","TECH_AI","SPORTS","ENTERTAINMENT","WEATHER","LEMMIQ"],
        }

    @router.get("/predict/markets/{market_id}")
    def market_detail(market_id:int,u:User=Depends(current_user),db:Session=Depends(get_db)):
        m=db.get(PredictMarket,market_id)
        if not m:raise HTTPException(404,"Prediction market not found")
        return _market_json(db,m,u.id,True)

    @router.post("/predict/markets/{market_id}/stake")
    def stake(market_id:int,body:PredictStakeIn,u:User=Depends(current_user),db:Session=Depends(get_db)):
        m=db.get(PredictMarket,market_id)
        if not m:raise HTTPException(404,"Prediction market not found")
        _stake(db,u,m,body.outcome,_pc_micros(body.amount_pc));db.commit();db.refresh(m)
        return {"market":_market_json(db,m,u.id),"wallet_balance_pc":_pc(_wallet(db,u.id).balance_micros)}

    @router.post("/predict/markets/{market_id}/watch")
    def toggle_watch(market_id:int,u:User=Depends(current_user),db:Session=Depends(get_db)):
        if not db.get(PredictMarket,market_id):raise HTTPException(404,"Market not found")
        row=db.scalar(select(PredictWatch).where(PredictWatch.market_id==market_id,PredictWatch.user_id==u.id))
        if row:db.delete(row);watched=False
        else:db.add(PredictWatch(user_id=u.id,market_id=market_id));watched=True
        db.commit();return {"watched":watched}

    @router.post("/predict/markets/{market_id}/comments")
    def comment(market_id:int,body:PredictCommentIn,u:User=Depends(current_user),db:Session=Depends(get_db)):
        m=db.get(PredictMarket,market_id)
        if not m:raise HTTPException(404,"Market not found")
        row=PredictComment(market_id=market_id,user_id=u.id,text=body.text.strip());db.add(row);m.comment_count+=1;m.updated_at=utcnow();db.commit();db.refresh(row)
        return {"id":row.id,"text":row.text,"created_at":row.created_at.isoformat(),"user":{"id":u.id,"username":u.username,"display_name":u.display_name}}

    @router.get("/predict/my")
    def my_predictions(u:User=Depends(current_user),db:Session=Depends(get_db)):
        ps=db.scalars(select(PredictPosition).where(PredictPosition.user_id==u.id).order_by(PredictPosition.updated_at.desc()).limit(200)).all()
        return [{"market":_market_json(db,db.get(PredictMarket,p.market_id),u.id),"outcome":p.outcome,"stake_pc":_pc(p.stake_micros),"payout_pc":_pc(p.payout_micros),"status":p.status} for p in ps if db.get(PredictMarket,p.market_id)]

    @router.get("/predict/leaderboard")
    def leaderboard(u:User=Depends(current_user),db:Session=Depends(get_db)):
        rows=db.scalars(select(PredictWallet).where(PredictWallet.markets_resolved>0).order_by(PredictWallet.lifetime_won_micros.desc()).limit(100)).all()
        out=[]
        for i,w in enumerate(rows,1):
            user=db.get(User,w.user_id);acc=(w.markets_won*100/w.markets_resolved) if w.markets_resolved else 0
            out.append({"rank":i,"user":{"id":w.user_id,"username":user.username if user else "","display_name":user.display_name if user else f"User #{w.user_id}"},"accuracy_percent":round(acc,1),"net_won_pc":_pc(w.lifetime_won_micros),"resolved":w.markets_resolved})
        return out

    @router.post("/predict/wallet/reset")
    def reset_wallet(u:User=Depends(current_user),db:Session=Depends(get_db)):
        cfg=_config(db);w=_wallet(db,u.id)
        open_count=int(db.scalar(select(func.count()).select_from(PredictPosition).join(PredictMarket,PredictPosition.market_id==PredictMarket.id).where(PredictPosition.user_id==u.id,PredictMarket.status.in_(["LIVE","CLOSED","RESOLVING"]))) or 0)
        if open_count:raise HTTPException(409,"Resolve your open test positions before resetting Predict Credits")
        if w.balance_micros>=cfg.starting_credits_micros:raise HTTPException(409,"Your Predict Credits are already at or above the test starting balance")
        delta=cfg.starting_credits_micros-w.balance_micros;w.balance_micros=cfg.starting_credits_micros;w.updated_at=utcnow();_ledger(db,u.id,"TEST_BALANCE_RESET",delta,None,"Testing refill")
        db.commit();return {"balance_pc":_pc(w.balance_micros)}

    @router.get("/predict/admin/overview")
    def admin_overview(period:str="7d",u:User=Depends(current_user),db:Session=Depends(get_db)):
        _require_admin(db,u);start=_range_start(period);cfg=_config(db)
        counts={s:int(db.scalar(select(func.count()).select_from(PredictMarket).where(PredictMarket.status==s)) or 0) for s in ["REVIEW","LIVE","CLOSED","RESOLVING","RESOLVED","VOID"]}
        volume=int(db.scalar(select(func.coalesce(func.sum(PredictTrade.amount_micros),0)).where(PredictTrade.created_at>=start)) or 0)
        predictors=int(db.scalar(select(func.count(func.distinct(PredictTrade.user_id))).where(PredictTrade.created_at>=start)) or 0)
        comments=int(db.scalar(select(func.count()).select_from(PredictComment).where(PredictComment.created_at>=start)) or 0)
        return {"period":period,"counts":counts,"volume_pc":_pc(volume),"active_predictors":predictors,"comments":comments,"test_treasury_pc":_pc(cfg.test_treasury_micros),"fee_percent":cfg.fee_bps/100,"real_q_enabled":False,"mode":"TEST_CREDITS_ONLY"}

    @router.get("/predict/admin/markets")
    def admin_markets(status:str="",u:User=Depends(current_user),db:Session=Depends(get_db)):
        _require_admin(db,u);stmt=select(PredictMarket)
        if status.strip():stmt=stmt.where(PredictMarket.status==status.upper().strip())
        return [_market_json(db,x,None) for x in db.scalars(stmt.order_by(PredictMarket.created_at.desc()).limit(300)).all()]

    @router.post("/predict/admin/markets")
    def admin_create_market(body:PredictMarketIn,u:User=Depends(current_user),db:Session=Depends(get_db)):
        _require_admin(db,u,True);m=_create_market(db,body,creator_id=u.id,generated_by="ADMIN",status="REVIEW");db.commit();db.refresh(m);return _market_json(db,m,None)

    @router.post("/predict/admin/markets/{market_id}/publish")
    def admin_publish_market(market_id:int,u:User=Depends(current_user),db:Session=Depends(get_db)):
        _require_admin(db,u,True);m=db.get(PredictMarket,market_id)
        if not m:raise HTTPException(404,"Market not found")
        if m.status not in {"REVIEW","DRAFT"}:raise HTTPException(409,"Only review/draft markets can be published")
        live=int(db.scalar(select(func.count()).select_from(PredictMarket).where(PredictMarket.status=="LIVE")) or 0)
        if live>=_config(db).max_live_markets:raise HTTPException(409,"Maximum live markets reached")
        m.status="LIVE";m.approved_by_user_id=u.id;m.updated_at=utcnow();db.commit();return _market_json(db,m,None)

    @router.post("/predict/admin/markets/{market_id}/resolve")
    def admin_resolve_market(market_id:int,body:PredictResolveIn,u:User=Depends(current_user),db:Session=Depends(get_db)):
        _require_admin(db,u,True);m=db.get(PredictMarket,market_id)
        if not m:raise HTTPException(404,"Market not found")
        _settle_market(db,m,body.outcome,body.source_value,body.note,u.id,{"manual":True});db.commit();return _market_json(db,m,None)

    @router.post("/predict/admin/markets/{market_id}/void")
    def admin_void_market(market_id:int,u:User=Depends(current_user),db:Session=Depends(get_db)):
        _require_admin(db,u,True);m=db.get(PredictMarket,market_id)
        if not m:raise HTTPException(404,"Market not found")
        _settle_market(db,m,"VOID","","Voided by Q Predict Admin",u.id,{"manual":True});db.commit();return _market_json(db,m,None)

    @router.post("/predict/admin/agent/run")
    def admin_run_agent(u:User=Depends(current_user),db:Session=Depends(get_db)):
        _require_admin(db,u,True);rows=_auto_candidates(db);db.commit();return {"created":len(rows),"markets":[_market_json(db,x,None) for x in rows]}

    @router.post("/predict/admin/settle-due")
    def admin_settle_due(u:User=Depends(current_user),db:Session=Depends(get_db)):
        _require_admin(db,u,True);out=_settle_due(db);db.commit();return out

    @router.get("/predict/admin/config")
    def admin_config(u:User=Depends(current_user),db:Session=Depends(get_db)):
        _require_admin(db,u);c=_config(db);return {"starting_credits_pc":_pc(c.starting_credits_micros),"fee_percent":c.fee_bps/100,"discovery_enabled":c.discovery_enabled,"auto_drafting":c.auto_drafting,"auto_publish":c.auto_publish,"auto_settlement":c.auto_settlement,"max_live_markets":c.max_live_markets,"max_new_markets_per_day":c.max_new_markets_per_day,"test_treasury_pc":_pc(c.test_treasury_micros),"test_mode":c.test_mode,"real_q_enabled":False}

    @router.put("/predict/admin/config")
    def admin_save_config(body:PredictConfigIn,u:User=Depends(current_user),db:Session=Depends(get_db)):
        _require_admin(db,u,True);c=_config(db)
        if body.starting_credits_pc is not None:c.starting_credits_micros=_pc_micros(body.starting_credits_pc)
        if body.fee_percent is not None:c.fee_bps=int(round(body.fee_percent*100))
        for k in ["discovery_enabled","auto_drafting","auto_publish","auto_settlement","max_live_markets","max_new_markets_per_day"]:
            v=getattr(body,k)
            if v is not None:setattr(c,k,v)
        c.test_mode=True;c.real_q_enabled=False;c.updated_at=utcnow();db.commit();return admin_config(u,db)

    @router.get("/admin/operations")
    def operations(period:str="7d",u:User=Depends(current_user),db:Session=Depends(get_db)):
        _require_admin(db,u);start=_range_start(period)
        users=int(db.scalar(select(func.count()).select_from(User).where(User.created_at>=start)) or 0) if hasattr(User,"created_at") else int(db.scalar(select(func.count()).select_from(User)) or 0)
        packages=0
        try:
            from .v28 import QSubscriptionLot,QPaymentOrder,QReferral
            packages=int(db.scalar(select(func.count()).select_from(QSubscriptionLot).where(QSubscriptionLot.started_at>=start)) or 0)
            approved_usdt=float(db.scalar(select(func.coalesce(func.sum(QPaymentOrder.expected_usdt_micros),0)).where(QPaymentOrder.status=="APPROVED",QPaymentOrder.reviewed_at>=start)) or 0)/1_000_000
            referrals=int(db.scalar(select(func.count()).select_from(QReferral).where(QReferral.created_at>=start)) or 0)
        except Exception:
            approved_usdt=0;referrals=0
        q_entries=int(db.scalar(select(func.count()).select_from(QLedgerEntry).where(QLedgerEntry.created_at>=start)) or 0)
        market_orders=int(db.scalar(select(func.count()).select_from(QMarketOrder).where(QMarketOrder.created_at>=start)) or 0)
        return {"period":period,"new_users":users,"new_packages":packages,"approved_usdt":round(approved_usdt,2),"q_ledger_events":q_entries,"q_market_orders":market_orders,"new_referrals":referrals}

    @router.get("/admin/monetisation")
    def monetisation(period:str="7d",u:User=Depends(current_user),db:Session=Depends(get_db)):
        _require_admin(db,u);start=_range_start(period)
        rows=db.scalars(select(ShadowMonetisationEvent).where(ShadowMonetisationEvent.created_at>=start)).all()
        by={}
        for x in rows:
            d=by.setdefault(x.feature,{"feature":x.feature,"requests":0,"success":0,"estimated_cost_usd":0.0,"simulated_q":0.0})
            d["requests"]+=1;d["success"]+=1 if x.success else 0;d["estimated_cost_usd"]+=x.estimated_cost_microusd/1_000_000;d["simulated_q"]+=_pc(x.simulated_q_micros)
        cost=sum(x.estimated_cost_microusd for x in rows)/1_000_000;simq=sum(x.simulated_q_micros for x in rows)/PC_MICROS
        qcfg=db.get(QEconomyConfig,1);qprice=(qcfg.q_price_microusd/1_000_000 if qcfg else .05)
        return {"mode":"TRACKING_ONLY","charges_enabled":False,"period":period,"requests":len(rows),"estimated_ai_cost_usd":round(cost,4),"simulated_q_fees":round(simq,4),"simulated_fee_reference_usd":round(simq*qprice,4),"features":list(by.values())}

    @router.get("/admin/q-simulation")
    def q_simulation(u:User=Depends(current_user),db:Session=Depends(get_db)):
        _require_admin(db,u);current=_supply_demand_snapshot(db,True);db.commit();history=db.scalars(select(QSimulationSnapshot).order_by(QSimulationSnapshot.snapshot_date.desc()).limit(90)).all()
        return {"current":current,"history":[{"date":x.snapshot_date.isoformat(),"actual_price_usd":x.actual_price_microusd/1_000_000,"simulated_price_usd":x.simulated_price_microusd/1_000_000,"change_percent":x.applied_change_percent} for x in reversed(history)]}

    @router.get("/admin/treasury/{wallet_key}")
    def treasury_detail(wallet_key:str,period:str="30d",u:User=Depends(current_user),db:Session=Depends(get_db)):
        _require_admin(db,u);key=wallet_key.upper();w=db.get(QSystemWallet,key)
        if not w:raise HTTPException(404,"Treasury wallet not found")
        start=_range_start(period)
        rows=db.scalars(select(QLedgerEntry).where(QLedgerEntry.created_at>=start,or_(QLedgerEntry.from_system_key==key,QLedgerEntry.to_system_key==key)).order_by(QLedgerEntry.created_at.desc()).limit(500)).all()
        sent=sum(x.amount_micros for x in rows if x.from_system_key==key);received=sum(x.amount_micros for x in rows if x.to_system_key==key)
        return {"wallet":key,"balance_q":_pc(w.balance_micros),"sent_q":_pc(sent),"received_q":_pc(received),"net_q":_pc(received-sent),"transactions":len(rows),"last_transaction":rows[0].created_at.isoformat() if rows else None,"ledger":[{"id":x.id,"kind":x.kind,"amount_q":_pc(x.amount_micros),"direction":"OUT" if x.from_system_key==key else "IN","reference":x.reference,"note":x.note,"created_at":x.created_at.isoformat()} for x in rows]}

    app.include_router(router)
