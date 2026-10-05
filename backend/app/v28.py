"""LEMMIQ V2.8 Q Economy Beta.

Centralised Q ledger + wallet, usage mining, referrals, subscription lots,
manual USDT (TRC20/BEP20) payment approval, Q Marketplace, escrow, and
browser-first admin controls.

Q is an internal utility unit in V2.8. Cash-out is deliberately disabled.
"""
from __future__ import annotations

import base64
import hashlib
import io
import os
import re
import secrets
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import RedirectResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from .database import Base
from .models import User

Q_MICROS = 1_000_000
USD_MICROS = 1_000_000
MAX_Q = 1_000_000_000 * Q_MICROS

SYSTEM_OPENING_Q = {
    "USAGE_MINING": 6_000_000,
    "MARKET_REWARDS": 2_000_000,
    "REFERRALS": 1_000_000,
    "PROMOTIONS": 1_000_000,
    "PROFIT": 0,
    "ESCROW": 0,
    "LOCKED_RESERVE": 990_000_000,
}

PACKAGE_PLANS = {
    "STARTER_10": {"name": "Q Starter", "price_usd": 10, "daily_rate_bps": 25},
    "PLUS_50": {"name": "Q Plus", "price_usd": 50, "daily_rate_bps": 50},
    "PRO_100": {"name": "Q Pro", "price_usd": 100, "daily_rate_bps": 75},
    "PREMIUM_500": {"name": "Q Premium", "price_usd": 500, "daily_rate_bps": 100},
    "ELITE_1000": {"name": "Q Elite", "price_usd": 1000, "daily_rate_bps": 125},
}

NETWORKS = {"TRC20", "BEP20"}
ADMIN_ROLES = {
    "MASTER_ADMIN", "FINANCE_ADMIN", "MARKETPLACE_ADMIN",
    "SUPPORT_ADMIN", "RISK_ADMIN", "READ_ONLY",
}


def utcnow():
    return datetime.now(timezone.utc)


class QSystemWallet(Base):
    __tablename__ = "q_system_wallets"
    key: Mapped[str] = mapped_column(String(40), primary_key=True)
    label: Mapped[str] = mapped_column(String(100))
    balance_micros: Mapped[int] = mapped_column(BigInteger, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class QUserWallet(Base):
    __tablename__ = "q_user_wallets"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    balance_micros: Mapped[int] = mapped_column(BigInteger, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class QLedgerEntry(Base):
    __tablename__ = "q_ledger_entries"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tx_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    kind: Mapped[str] = mapped_column(String(40), index=True)
    from_system_key: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    from_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    to_system_key: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    to_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    amount_micros: Mapped[int] = mapped_column(BigInteger)
    usd_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reference: Mapped[str] = mapped_column(String(120), default="")
    note: Mapped[str] = mapped_column(String(240), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class QEconomyConfig(Base):
    __tablename__ = "q_economy_config"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    q_price_microusd: Mapped[int] = mapped_column(BigInteger, default=50_000)  # US$0.05/Q
    marketplace_fee_bps: Mapped[int] = mapped_column(Integer, default=500)
    basic_daily_micros: Mapped[int] = mapped_column(BigInteger, default=2 * Q_MICROS)
    signup_bonus_micros: Mapped[int] = mapped_column(BigInteger, default=100 * Q_MICROS)
    referral_referrer_micros: Mapped[int] = mapped_column(BigInteger, default=25 * Q_MICROS)
    referral_referred_micros: Mapped[int] = mapped_column(BigInteger, default=25 * Q_MICROS)
    cashout_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class QDailyClaim(Base):
    __tablename__ = "q_daily_claims"
    __table_args__ = (UniqueConstraint("user_id", "claim_date", name="uq_q_daily_user_date"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    claim_date: Mapped[date] = mapped_column(Date, index=True)
    amount_micros: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class QReferral(Base):
    __tablename__ = "q_referrals"
    __table_args__ = (UniqueConstraint("referred_user_id", name="uq_q_referral_referred"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    referrer_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    referred_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    code: Mapped[str] = mapped_column(String(40), index=True)
    referrer_reward_micros: Mapped[int] = mapped_column(BigInteger, default=0)
    referred_reward_micros: Mapped[int] = mapped_column(BigInteger, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class QAdminRole(Base):
    __tablename__ = "q_admin_roles"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    role: Mapped[str] = mapped_column(String(30), default="READ_ONLY")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class QPaymentWallet(Base):
    __tablename__ = "q_payment_wallets"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    network: Mapped[str] = mapped_column(String(16), index=True)
    package_code: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    label: Mapped[str] = mapped_column(String(100), default="")
    address: Mapped[str] = mapped_column(String(160))
    qr_image_b64: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class QPaymentOrder(Base):
    __tablename__ = "q_payment_orders"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_code: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    package_code: Mapped[str] = mapped_column(String(32), index=True)
    network: Mapped[str] = mapped_column(String(16), index=True)
    wallet_id: Mapped[int] = mapped_column(ForeignKey("q_payment_wallets.id"))
    expected_usdt_micros: Mapped[int] = mapped_column(BigInteger)
    submitted_tx_hash: Mapped[str | None] = mapped_column(String(120), nullable=True, unique=True)
    status: Mapped[str] = mapped_column(String(20), default="CREATED", index=True)
    user_note: Mapped[str] = mapped_column(String(240), default="")
    admin_note: Mapped[str] = mapped_column(String(240), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class QSubscriptionLot(Base):
    __tablename__ = "q_subscription_lots"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    payment_order_id: Mapped[int] = mapped_column(ForeignKey("q_payment_orders.id"), unique=True)
    package_code: Mapped[str] = mapped_column(String(32), index=True)
    purchase_usd_micros: Mapped[int] = mapped_column(BigInteger)
    daily_rate_bps: Mapped[int] = mapped_column(Integer)
    cap_usd_micros: Mapped[int] = mapped_column(BigInteger)
    accrued_usd_micros: Mapped[int] = mapped_column(BigInteger, default=0)
    accrued_q_micros: Mapped[int] = mapped_column(BigInteger, default=0)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_accrual_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", index=True)


class QMarketListing(Base):
    __tablename__ = "q_market_listings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    seller_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(60), default="OTHER", index=True)
    condition: Mapped[str] = mapped_column(String(40), default="SERVICE")
    price_micros: Mapped[int] = mapped_column(BigInteger)
    inventory: Mapped[int] = mapped_column(Integer, default=1)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class QMarketOrder(Base):
    __tablename__ = "q_market_orders"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_code: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("q_market_listings.id"), index=True)
    buyer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    seller_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    total_micros: Mapped[int] = mapped_column(BigInteger)
    fee_bps: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="PAID", index=True)
    dispute_note: Mapped[str] = mapped_column(String(300), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class QTransferIn(BaseModel):
    username: str = Field(min_length=3, max_length=40)
    amount_q: float = Field(gt=0, le=10_000_000)
    note: str = Field(default="", max_length=160)


class QReferralIn(BaseModel):
    code: str = Field(min_length=4, max_length=40)


class PaymentOrderIn(BaseModel):
    package_code: str
    network: str


class PaymentSubmitIn(BaseModel):
    tx_hash: str = Field(min_length=20, max_length=120)
    note: str = Field(default="", max_length=240)


class AdminPaymentWalletIn(BaseModel):
    network: str
    package_code: str | None = None
    label: str = Field(default="", max_length=100)
    address: str = Field(min_length=20, max_length=160)
    active: bool = True


class AdminRoleIn(BaseModel):
    username: str = Field(min_length=3, max_length=40)
    role: str = Field(min_length=3, max_length=30)
    active: bool = True


class AdminConfigIn(BaseModel):
    q_price_usd: float | None = Field(default=None, gt=0, le=100000)
    marketplace_fee_percent: float | None = Field(default=None, ge=0, le=25)
    basic_daily_q: float | None = Field(default=None, ge=0, le=1000)
    signup_bonus_q: float | None = Field(default=None, ge=0, le=100000)
    referral_referrer_q: float | None = Field(default=None, ge=0, le=100000)
    referral_referred_q: float | None = Field(default=None, ge=0, le=100000)


class TreasuryTransferIn(BaseModel):
    from_wallet: str
    to_wallet: str
    amount_q: float = Field(gt=0, le=1_000_000_000)
    reason: str = Field(min_length=3, max_length=200)


class ListingIn(BaseModel):
    title: str = Field(min_length=2, max_length=120)
    description: str = Field(default="", max_length=4000)
    category: str = Field(default="OTHER", max_length=60)
    condition: str = Field(default="SERVICE", max_length=40)
    price_q: float = Field(gt=0, le=100_000_000)
    inventory: int = Field(default=1, ge=1, le=100000)


class ListingUpdateIn(ListingIn):
    active: bool = True


class BuyIn(BaseModel):
    quantity: int = Field(default=1, ge=1, le=1000)


class DisputeIn(BaseModel):
    note: str = Field(min_length=3, max_length=300)


class ResolveDisputeIn(BaseModel):
    outcome: str
    note: str = Field(default="", max_length=240)


def _q(v_micros: int) -> float:
    return round(v_micros / Q_MICROS, 6)


def _usd(v_micros: int) -> float:
    return round(v_micros / USD_MICROS, 6)


def _now():
    return datetime.now(timezone.utc)


def _txid(prefix: str) -> str:
    return f"{prefix}-{_now().strftime('%Y%m%d%H%M%S')}-{secrets.token_hex(5).upper()}"


def _config(db: Session) -> QEconomyConfig:
    row = db.get(QEconomyConfig, 1)
    if not row:
        row = QEconomyConfig(id=1)
        db.add(row)
        db.flush()
    return row


def _system(db: Session, key: str) -> QSystemWallet:
    row = db.get(QSystemWallet, key)
    if not row:
        raise HTTPException(500, f"Q system wallet missing: {key}")
    return row


def _raw_user_wallet(db: Session, uid: int) -> QUserWallet:
    row = db.get(QUserWallet, uid)
    if not row:
        row = QUserWallet(user_id=uid, balance_micros=0)
        db.add(row)
        db.flush()
    return row


def _ledger(
    db: Session,
    kind: str,
    amount: int,
    *,
    from_system: str | None = None,
    from_user: int | None = None,
    to_system: str | None = None,
    to_user: int | None = None,
    usd_cents: int | None = None,
    reference: str = "",
    note: str = "",
):
    db.add(
        QLedgerEntry(
            tx_id=_txid(kind[:10].upper()),
            kind=kind,
            from_system_key=from_system,
            from_user_id=from_user,
            to_system_key=to_system,
            to_user_id=to_user,
            amount_micros=amount,
            usd_cents=usd_cents,
            reference=reference[:120],
            note=note[:240],
        )
    )


def _system_to_user(db: Session, system_key: str, uid: int, amount: int, kind: str, reference: str = "", note: str = "", usd_cents: int | None = None):
    if amount <= 0:
        return
    sw = _system(db, system_key)
    uw = _raw_user_wallet(db, uid)
    if sw.balance_micros < amount:
        raise HTTPException(409, f"{system_key} treasury does not have enough Q")
    sw.balance_micros -= amount
    sw.updated_at = _now()
    uw.balance_micros += amount
    uw.updated_at = _now()
    _ledger(db, kind, amount, from_system=system_key, to_user=uid, reference=reference, note=note, usd_cents=usd_cents)


def _user_to_system(db: Session, uid: int, system_key: str, amount: int, kind: str, reference: str = "", note: str = ""):
    if amount <= 0:
        return
    uw = _raw_user_wallet(db, uid)
    sw = _system(db, system_key)
    if uw.balance_micros < amount:
        raise HTTPException(409, "Not enough Q")
    uw.balance_micros -= amount
    uw.updated_at = _now()
    sw.balance_micros += amount
    sw.updated_at = _now()
    _ledger(db, kind, amount, from_user=uid, to_system=system_key, reference=reference, note=note)


def _system_to_system(db: Session, from_key: str, to_key: str, amount: int, kind: str, reference: str = "", note: str = ""):
    if from_key == to_key:
        raise HTTPException(422, "Source and destination wallets must differ")
    a, b = _system(db, from_key), _system(db, to_key)
    if a.balance_micros < amount:
        raise HTTPException(409, f"{from_key} does not have enough Q")
    a.balance_micros -= amount
    b.balance_micros += amount
    a.updated_at = b.updated_at = _now()
    _ledger(db, kind, amount, from_system=from_key, to_system=to_key, reference=reference, note=note)


def _user_to_user(db: Session, from_uid: int, to_uid: int, amount: int, kind: str, note: str = ""):
    if from_uid == to_uid:
        raise HTTPException(422, "Cannot transfer Q to yourself")
    a, b = _raw_user_wallet(db, from_uid), _raw_user_wallet(db, to_uid)
    if a.balance_micros < amount:
        raise HTTPException(409, "Not enough Q")
    a.balance_micros -= amount
    b.balance_micros += amount
    a.updated_at = b.updated_at = _now()
    _ledger(db, kind, amount, from_user=from_uid, to_user=to_uid, note=note)


def _ensure_user_wallet(db: Session, uid: int) -> QUserWallet:
    existing = db.get(QUserWallet, uid)
    if existing:
        return existing
    row = _raw_user_wallet(db, uid)
    cfg = _config(db)
    bonus = max(0, cfg.signup_bonus_micros)
    if bonus:
        _system_to_user(db, "PROMOTIONS", uid, bonus, "SIGNUP_BONUS", reference=f"user:{uid}", note="V2.8 signup Q")
    return row


def _referral_code(u: User) -> str:
    sig = hashlib.sha256(f"LEM-Q-{u.id}-{u.username}".encode()).hexdigest()[:6].upper()
    return f"Q{u.id}-{sig}"


def _referrer_from_code(db: Session, code: str) -> User:
    m = re.fullmatch(r"Q(\d+)-([A-F0-9]{6})", code.strip().upper())
    if not m:
        raise HTTPException(404, "Referral code not found")
    u = db.get(User, int(m.group(1)))
    if not u or _referral_code(u) != code.strip().upper():
        raise HTTPException(404, "Referral code not found")
    return u


def _plan_json(code: str, cfg: QEconomyConfig):
    p = PACKAGE_PLANS[code]
    price_usd = p["price_usd"]
    daily_usd = price_usd * p["daily_rate_bps"] / 10_000
    daily_q_at_reference = daily_usd / (cfg.q_price_microusd / USD_MICROS)
    return {
        "code": code,
        "name": p["name"],
        "price_usd": price_usd,
        "daily_rate_percent": p["daily_rate_bps"] / 100,
        "daily_usd_reference": round(daily_usd, 6),
        "daily_q_at_current_reference": round(daily_q_at_reference, 6),
        "valid_days": 365,
        "cap_percent": 200,
        "cap_usd": price_usd * 2,
        "cap_q_at_current_reference": round((price_usd * 2) / (cfg.q_price_microusd / USD_MICROS), 6),
    }


def _subscription_json(row: QSubscriptionLot, cfg: QEconomyConfig):
    p = PACKAGE_PLANS.get(row.package_code, {"name": row.package_code})
    remaining = max(0, row.cap_usd_micros - row.accrued_usd_micros)
    return {
        "id": row.id,
        "package_code": row.package_code,
        "package_name": p["name"],
        "purchase_usd": _usd(row.purchase_usd_micros),
        "daily_rate_percent": row.daily_rate_bps / 100,
        "accrued_usd_reference": _usd(row.accrued_usd_micros),
        "accrued_q": _q(row.accrued_q_micros),
        "cap_usd": _usd(row.cap_usd_micros),
        "remaining_cap_usd": _usd(remaining),
        "status": row.status,
        "started_at": row.started_at.isoformat(),
        "expires_at": row.expires_at.isoformat(),
        "last_accrual_date": row.last_accrual_date.isoformat(),
        "current_q_reference_usd": cfg.q_price_microusd / USD_MICROS,
    }


def _accrue_user_packages(db: Session, uid: int):
    cfg = _config(db)
    today = _now().date()
    rows = db.scalars(select(QSubscriptionLot).where(QSubscriptionLot.user_id == uid, QSubscriptionLot.status == "ACTIVE")).all()
    for row in rows:
        end_date = min(today, row.expires_at.date())
        days = (end_date - row.last_accrual_date).days
        if days <= 0:
            if today >= row.expires_at.date() and row.accrued_usd_micros < row.cap_usd_micros:
                row.status = "EXPIRED"
            continue
        daily_usd_micros = (row.purchase_usd_micros * row.daily_rate_bps) // 10_000
        remaining = max(0, row.cap_usd_micros - row.accrued_usd_micros)
        owed_usd = min(remaining, daily_usd_micros * days)
        q_amount = (owed_usd * Q_MICROS) // max(1, cfg.q_price_microusd)
        if owed_usd > 0 and q_amount > 0:
            _system_to_user(
                db, "USAGE_MINING", uid, q_amount, "PACKAGE_ACCRUAL",
                reference=f"subscription:{row.id}",
                note=f"{days} day package accrual",
                usd_cents=int(round(owed_usd / 10_000)),
            )
            row.accrued_usd_micros += owed_usd
            row.accrued_q_micros += q_amount
        row.last_accrual_date = end_date
        if row.accrued_usd_micros >= row.cap_usd_micros:
            row.status = "CAP_REACHED"
        elif today >= row.expires_at.date():
            row.status = "EXPIRED"


def _wallet_summary(db: Session, u: User):
    _ensure_user_wallet(db, u.id)
    _accrue_user_packages(db, u.id)
    cfg = _config(db)
    w = _raw_user_wallet(db, u.id)
    today_claimed = db.scalar(select(func.count()).select_from(QDailyClaim).where(QDailyClaim.user_id == u.id, QDailyClaim.claim_date == _now().date())) or 0
    role = db.get(QAdminRole, u.id)
    subs = db.scalars(select(QSubscriptionLot).where(QSubscriptionLot.user_id == u.id).order_by(QSubscriptionLot.id.desc())).all()
    return {
        "balance_q": _q(w.balance_micros),
        "balance_usd_reference": round(_q(w.balance_micros) * cfg.q_price_microusd / USD_MICROS, 4),
        "q_reference_usd": cfg.q_price_microusd / USD_MICROS,
        "cashout_enabled": bool(cfg.cashout_enabled),
        "cashout_note": "Cash-out is not enabled in LEMMIQ V2.8.",
        "basic_daily_q": _q(cfg.basic_daily_micros),
        "basic_claimed_today": bool(today_claimed),
        "signup_bonus_q": _q(cfg.signup_bonus_micros),
        "referral_code": _referral_code(u),
        "referral_reward_q": _q(cfg.referral_referrer_micros),
        "admin_role": role.role if role and role.active else None,
        "packages": [_subscription_json(x, cfg) for x in subs],
        "plans": [_plan_json(code, cfg) for code in PACKAGE_PLANS],
    }


def _require_roles(db: Session, u: User, *allowed: str) -> QAdminRole:
    role = _admin_role(db, u.id)
    if not role or role.role not in allowed:
        raise HTTPException(403, "This admin role does not have permission for that action")
    return role


def _admin_role(db: Session, uid: int) -> QAdminRole | None:
    row = db.get(QAdminRole, uid)
    return row if row and row.active else None


def _listing_json(db: Session, row: QMarketListing):
    seller = db.get(User, row.seller_id)
    cfg = _config(db)
    return {
        "id": row.id,
        "seller": {"id": seller.id, "username": seller.username, "display_name": seller.display_name} if seller else None,
        "title": row.title,
        "description": row.description,
        "category": row.category,
        "condition": row.condition,
        "price_q": _q(row.price_micros),
        "price_usd_reference": round(_q(row.price_micros) * cfg.q_price_microusd / USD_MICROS, 4),
        "inventory": row.inventory,
        "active": row.active,
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
    }


def _market_order_json(db: Session, row: QMarketOrder):
    listing = db.get(QMarketListing, row.listing_id)
    return {
        "id": row.id,
        "order_code": row.order_code,
        "listing": _listing_json(db, listing) if listing else None,
        "buyer_id": row.buyer_id,
        "seller_id": row.seller_id,
        "quantity": row.quantity,
        "total_q": _q(row.total_micros),
        "fee_percent": row.fee_bps / 100,
        "status": row.status,
        "dispute_note": row.dispute_note,
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
    }


def _payment_wallet_json(row: QPaymentWallet):
    return {
        "id": row.id,
        "network": row.network,
        "package_code": row.package_code,
        "label": row.label,
        "address": row.address,
        "active": row.active,
        "qr_url": f"/v28/payment-wallets/{row.id}/qr",
        "custom_qr": bool(row.qr_image_b64),
    }


def _explorer(network: str, tx_hash: str | None):
    if not tx_hash:
        return None
    if network == "TRC20":
        return f"https://tronscan.org/#/transaction/{tx_hash}"
    return f"https://bscscan.com/tx/{tx_hash}"


def _payment_order_json(db: Session, row: QPaymentOrder):
    wallet = db.get(QPaymentWallet, row.wallet_id)
    plan = PACKAGE_PLANS.get(row.package_code, {})
    return {
        "id": row.id,
        "order_code": row.order_code,
        "user_id": row.user_id,
        "package_code": row.package_code,
        "package_name": plan.get("name", row.package_code),
        "network": row.network,
        "expected_usdt": row.expected_usdt_micros / 1_000_000,
        "wallet": _payment_wallet_json(wallet) if wallet else None,
        "tx_hash": row.submitted_tx_hash,
        "explorer_url": _explorer(row.network, row.submitted_tx_hash),
        "status": row.status,
        "user_note": row.user_note,
        "admin_note": row.admin_note,
        "created_at": row.created_at.isoformat(),
        "submitted_at": row.submitted_at.isoformat() if row.submitted_at else None,
        "reviewed_at": row.reviewed_at.isoformat() if row.reviewed_at else None,
    }


def _validate_payment_address(network: str, address: str):
    network = network.upper()
    if network == "TRC20":
        if not re.fullmatch(r"T[1-9A-HJ-NP-Za-km-z]{33}", address):
            raise HTTPException(422, "Invalid TRC20 address format")
    elif network == "BEP20":
        if not re.fullmatch(r"0x[a-fA-F0-9]{40}", address):
            raise HTTPException(422, "Invalid BEP20 address format")
    else:
        raise HTTPException(422, "Network must be TRC20 or BEP20")


def register_v28(app, current_user, get_db):
    router = APIRouter(prefix="/v28", tags=["LEMMIQ V2.8 Q Economy"])

    def require_admin(u: User = Depends(current_user), db: Session = Depends(get_db)):
        role = _admin_role(db, u.id)
        if not role:
            raise HTTPException(403, "Admin access required")
        return u

    def require_master(u: User = Depends(require_admin), db: Session = Depends(get_db)):
        role = _admin_role(db, u.id)
        if not role or role.role != "MASTER_ADMIN":
            raise HTTPException(403, "Master Admin access required")
        return u

    @app.on_event("startup")
    def v28_startup():
        from .database import SessionLocal, engine
        Base.metadata.create_all(bind=engine)
        db = SessionLocal()
        try:
            for key, opening_q in SYSTEM_OPENING_Q.items():
                if not db.get(QSystemWallet, key):
                    db.add(QSystemWallet(key=key, label=key.replace("_", " ").title(), balance_micros=opening_q * Q_MICROS))
                    _ledger(db, "GENESIS", opening_q * Q_MICROS, to_system=key, reference="V2.8_GENESIS")
            _config(db)
            db.commit()

            username = os.getenv("LEMMIQ_MASTER_ADMIN_USERNAME", "").strip().lower()
            if username:
                user = db.scalar(select(User).where(User.username == username))
                if user:
                    role = db.get(QAdminRole, user.id)
                    if not role:
                        db.add(QAdminRole(user_id=user.id, role="MASTER_ADMIN", active=True))
                    else:
                        role.role, role.active = "MASTER_ADMIN", True
                    db.commit()
        finally:
            db.close()

    @app.get("/admin", include_in_schema=False)
    def v28_admin_redirect():
        return RedirectResponse("/web/#admin")

    @router.get("/config")
    def config(db: Session = Depends(get_db)):
        cfg = _config(db)
        return {
            "version": "2.8.0",
            "q_reference_usd": cfg.q_price_microusd / USD_MICROS,
            "marketplace_fee_percent": cfg.marketplace_fee_bps / 100,
            "cashout_enabled": bool(cfg.cashout_enabled),
            "max_supply_q": 1_000_000_000,
            "initial_unlocked_q": 10_000_000,
            "plans": [_plan_json(code, cfg) for code in PACKAGE_PLANS],
            "networks": sorted(NETWORKS),
        }

    @router.get("/wallet")
    def wallet(u: User = Depends(current_user), db: Session = Depends(get_db)):
        data = _wallet_summary(db, u)
        db.commit()
        return data

    @router.get("/wallet/ledger")
    def wallet_ledger(limit: int = 100, u: User = Depends(current_user), db: Session = Depends(get_db)):
        limit = max(1, min(limit, 250))
        rows = db.scalars(
            select(QLedgerEntry).where(
                (QLedgerEntry.from_user_id == u.id) | (QLedgerEntry.to_user_id == u.id)
            ).order_by(QLedgerEntry.id.desc()).limit(limit)
        ).all()
        return [{
            "id": x.id, "tx_id": x.tx_id, "kind": x.kind, "amount_q": _q(x.amount_micros),
            "direction": "OUT" if x.from_user_id == u.id else "IN",
            "other_user_id": x.to_user_id if x.from_user_id == u.id else x.from_user_id,
            "system_wallet": x.to_system_key if x.from_user_id == u.id else x.from_system_key,
            "usd_cents": x.usd_cents, "reference": x.reference, "note": x.note,
            "created_at": x.created_at.isoformat(),
        } for x in rows]

    @router.post("/wallet/claim-daily")
    def claim_daily(u: User = Depends(current_user), db: Session = Depends(get_db)):
        _ensure_user_wallet(db, u.id)
        today = _now().date()
        if db.scalar(select(func.count()).select_from(QDailyClaim).where(QDailyClaim.user_id == u.id, QDailyClaim.claim_date == today)):
            raise HTTPException(409, "Basic Q already claimed today")
        cfg = _config(db)
        amount = max(0, cfg.basic_daily_micros)
        _system_to_user(db, "USAGE_MINING", u.id, amount, "BASIC_DAILY", reference=today.isoformat(), note="Daily LEMMIQ activity reward")
        db.add(QDailyClaim(user_id=u.id, claim_date=today, amount_micros=amount))
        db.commit()
        return _wallet_summary(db, u)

    @router.post("/wallet/transfer")
    def transfer(body: QTransferIn, u: User = Depends(current_user), db: Session = Depends(get_db)):
        target = db.scalar(select(User).where(User.username == body.username.strip().lower()))
        if not target:
            raise HTTPException(404, "LEMMIQ user not found")
        amount = int(round(body.amount_q * Q_MICROS))
        _ensure_user_wallet(db, u.id)
        _ensure_user_wallet(db, target.id)
        _user_to_user(db, u.id, target.id, amount, "USER_TRANSFER", note=body.note)
        db.commit()
        return {"ok": True, "balance": _wallet_summary(db, u)}

    @router.post("/referrals/claim")
    def claim_referral(body: QReferralIn, u: User = Depends(current_user), db: Session = Depends(get_db)):
        if db.scalar(select(func.count()).select_from(QReferral).where(QReferral.referred_user_id == u.id)):
            raise HTTPException(409, "A referral has already been claimed for this account")
        if (_now() - u.created_at.replace(tzinfo=u.created_at.tzinfo or timezone.utc)) > timedelta(days=14):
            raise HTTPException(409, "Referral codes can only be claimed by new accounts")
        referrer = _referrer_from_code(db, body.code)
        if referrer.id == u.id:
            raise HTTPException(422, "You cannot refer yourself")
        cfg = _config(db)
        _ensure_user_wallet(db, referrer.id)
        _ensure_user_wallet(db, u.id)
        _system_to_user(db, "REFERRALS", referrer.id, cfg.referral_referrer_micros, "REFERRAL_REWARD", reference=f"referred:{u.id}")
        _system_to_user(db, "REFERRALS", u.id, cfg.referral_referred_micros, "REFERRAL_WELCOME", reference=f"referrer:{referrer.id}")
        db.add(QReferral(
            referrer_user_id=referrer.id, referred_user_id=u.id, code=body.code.strip().upper(),
            referrer_reward_micros=cfg.referral_referrer_micros,
            referred_reward_micros=cfg.referral_referred_micros,
        ))
        db.commit()
        return {"ok": True, "wallet": _wallet_summary(db, u)}

    @router.get("/referrals")
    def referrals(u: User = Depends(current_user), db: Session = Depends(get_db)):
        rows = db.scalars(select(QReferral).where(QReferral.referrer_user_id == u.id).order_by(QReferral.id.desc())).all()
        return {
            "code": _referral_code(u),
            "count": len(rows),
            "earned_q": _q(sum(x.referrer_reward_micros for x in rows)),
            "items": [{"user_id": x.referred_user_id, "reward_q": _q(x.referrer_reward_micros), "created_at": x.created_at.isoformat()} for x in rows],
        }

    @router.post("/payments/orders")
    def create_payment_order(body: PaymentOrderIn, u: User = Depends(current_user), db: Session = Depends(get_db)):
        code = body.package_code.strip().upper()
        network = body.network.strip().upper()
        if code not in PACKAGE_PLANS:
            raise HTTPException(422, "Unknown package")
        if network not in NETWORKS:
            raise HTTPException(422, "Network must be TRC20 or BEP20")
        wallet = db.scalar(select(QPaymentWallet).where(
            QPaymentWallet.active.is_(True), QPaymentWallet.network == network,
            QPaymentWallet.package_code == code
        ).order_by(QPaymentWallet.id.desc()).limit(1))
        if not wallet:
            wallet = db.scalar(select(QPaymentWallet).where(
                QPaymentWallet.active.is_(True), QPaymentWallet.network == network,
                QPaymentWallet.package_code.is_(None)
            ).order_by(QPaymentWallet.id.desc()).limit(1))
        if not wallet:
            raise HTTPException(409, f"No active {network} payment wallet is configured for this package")
        price = PACKAGE_PLANS[code]["price_usd"]
        row = QPaymentOrder(
            order_code=f"LQ-{_now().strftime('%Y%m%d')}-{secrets.token_hex(4).upper()}",
            user_id=u.id, package_code=code, network=network, wallet_id=wallet.id,
            expected_usdt_micros=price * 1_000_000, status="CREATED",
        )
        db.add(row); db.commit(); db.refresh(row)
        return _payment_order_json(db, row)

    @router.post("/payments/orders/{order_id}/submit")
    def submit_payment(order_id: int, body: PaymentSubmitIn, u: User = Depends(current_user), db: Session = Depends(get_db)):
        row = db.get(QPaymentOrder, order_id)
        if not row or row.user_id != u.id:
            raise HTTPException(404, "Payment order not found")
        if row.status not in ("CREATED", "REJECTED"):
            raise HTTPException(409, "This payment order cannot be submitted")
        tx_hash = body.tx_hash.strip()
        duplicate = db.scalar(select(QPaymentOrder).where(QPaymentOrder.submitted_tx_hash == tx_hash, QPaymentOrder.id != row.id))
        if duplicate:
            raise HTTPException(409, "This transaction hash has already been submitted")
        row.submitted_tx_hash = tx_hash
        row.user_note = body.note.strip()
        row.status = "PENDING"
        row.submitted_at = _now()
        row.admin_note = ""
        db.commit()
        return _payment_order_json(db, row)

    @router.get("/payments/orders")
    def my_payment_orders(u: User = Depends(current_user), db: Session = Depends(get_db)):
        rows = db.scalars(select(QPaymentOrder).where(QPaymentOrder.user_id == u.id).order_by(QPaymentOrder.id.desc())).all()
        return [_payment_order_json(db, x) for x in rows]

    @router.get("/payment-wallets/{wallet_id}/qr")
    def payment_qr(wallet_id: int, db: Session = Depends(get_db)):
        row = db.get(QPaymentWallet, wallet_id)
        if not row or not row.active:
            raise HTTPException(404, "Payment wallet not found")
        if row.qr_image_b64:
            raw = base64.b64decode(row.qr_image_b64)
            return Response(raw, media_type="image/png", headers={"Cache-Control": "no-store"})
        try:
            import qrcode
            img = qrcode.make(row.address)
            buf = io.BytesIO(); img.save(buf, format="PNG")
            return Response(buf.getvalue(), media_type="image/png", headers={"Cache-Control": "no-store"})
        except Exception:
            raise HTTPException(503, "QR generator is unavailable; copy the wallet address instead")

    @router.get("/market/listings")
    def market_listings(q: str = "", category: str = "", u: User = Depends(current_user), db: Session = Depends(get_db)):
        stmt = select(QMarketListing).where(QMarketListing.active.is_(True), QMarketListing.inventory > 0)
        if q.strip():
            like = f"%{q.strip().lower()}%"
            stmt = stmt.where(func.lower(QMarketListing.title).like(like))
        if category.strip():
            stmt = stmt.where(QMarketListing.category == category.strip().upper())
        rows = db.scalars(stmt.order_by(QMarketListing.id.desc()).limit(250)).all()
        return [_listing_json(db, x) for x in rows]

    @router.get("/market/my-listings")
    def my_listings(u: User = Depends(current_user), db: Session = Depends(get_db)):
        rows = db.scalars(select(QMarketListing).where(QMarketListing.seller_id == u.id).order_by(QMarketListing.id.desc())).all()
        return [_listing_json(db, x) for x in rows]

    @router.post("/market/listings")
    def create_listing(body: ListingIn, u: User = Depends(current_user), db: Session = Depends(get_db)):
        row = QMarketListing(
            seller_id=u.id, title=body.title.strip(), description=body.description.strip(),
            category=body.category.strip().upper() or "OTHER", condition=body.condition.strip().upper() or "SERVICE",
            price_micros=int(round(body.price_q * Q_MICROS)), inventory=body.inventory, active=True,
        )
        db.add(row); db.commit(); db.refresh(row)
        return _listing_json(db, row)

    @router.put("/market/listings/{listing_id}")
    def update_listing(listing_id: int, body: ListingUpdateIn, u: User = Depends(current_user), db: Session = Depends(get_db)):
        row = db.get(QMarketListing, listing_id)
        if not row or row.seller_id != u.id:
            raise HTTPException(404, "Listing not found")
        row.title = body.title.strip(); row.description = body.description.strip()
        row.category = body.category.strip().upper() or "OTHER"; row.condition = body.condition.strip().upper() or "SERVICE"
        row.price_micros = int(round(body.price_q * Q_MICROS)); row.inventory = body.inventory
        row.active = body.active; row.updated_at = _now()
        db.commit()
        return _listing_json(db, row)

    @router.post("/market/listings/{listing_id}/buy")
    def buy_listing(listing_id: int, body: BuyIn, u: User = Depends(current_user), db: Session = Depends(get_db)):
        listing = db.get(QMarketListing, listing_id)
        if not listing or not listing.active or listing.inventory < body.quantity:
            raise HTTPException(404, "Listing unavailable")
        if listing.seller_id == u.id:
            raise HTTPException(422, "You cannot buy your own listing")
        total = listing.price_micros * body.quantity
        cfg = _config(db)
        _ensure_user_wallet(db, u.id)
        _user_to_system(db, u.id, "ESCROW", total, "MARKET_ESCROW_IN", reference=f"listing:{listing.id}")
        listing.inventory -= body.quantity
        listing.updated_at = _now()
        order = QMarketOrder(
            order_code=f"QM-{_now().strftime('%Y%m%d')}-{secrets.token_hex(4).upper()}",
            listing_id=listing.id, buyer_id=u.id, seller_id=listing.seller_id,
            quantity=body.quantity, total_micros=total, fee_bps=cfg.marketplace_fee_bps, status="PAID",
        )
        db.add(order); db.commit(); db.refresh(order)
        return _market_order_json(db, order)

    @router.get("/market/orders")
    def my_market_orders(u: User = Depends(current_user), db: Session = Depends(get_db)):
        rows = db.scalars(select(QMarketOrder).where(
            (QMarketOrder.buyer_id == u.id) | (QMarketOrder.seller_id == u.id)
        ).order_by(QMarketOrder.id.desc())).all()
        return [_market_order_json(db, x) for x in rows]

    @router.post("/market/orders/{order_id}/accept")
    def accept_market(order_id: int, u: User = Depends(current_user), db: Session = Depends(get_db)):
        row = db.get(QMarketOrder, order_id)
        if not row or row.seller_id != u.id:
            raise HTTPException(404, "Order not found")
        if row.status != "PAID":
            raise HTTPException(409, "Order cannot be accepted")
        row.status = "ACCEPTED"; row.updated_at = _now(); db.commit()
        return _market_order_json(db, row)

    @router.post("/market/orders/{order_id}/delivered")
    def delivered_market(order_id: int, u: User = Depends(current_user), db: Session = Depends(get_db)):
        row = db.get(QMarketOrder, order_id)
        if not row or row.seller_id != u.id:
            raise HTTPException(404, "Order not found")
        if row.status not in ("PAID", "ACCEPTED"):
            raise HTTPException(409, "Order cannot be marked delivered")
        row.status = "DELIVERED"; row.updated_at = _now(); db.commit()
        return _market_order_json(db, row)

    def release_market_order(db: Session, row: QMarketOrder):
        fee = (row.total_micros * row.fee_bps) // 10_000
        seller_amount = row.total_micros - fee
        _system_to_user(db, "ESCROW", row.seller_id, seller_amount, "MARKET_SELLER_PAYOUT", reference=row.order_code)
        if fee:
            _system_to_system(db, "ESCROW", "PROFIT", fee, "MARKETPLACE_FEE", reference=row.order_code)
        row.status = "COMPLETED"; row.updated_at = _now()

    @router.post("/market/orders/{order_id}/complete")
    def complete_market(order_id: int, u: User = Depends(current_user), db: Session = Depends(get_db)):
        row = db.get(QMarketOrder, order_id)
        if not row or row.buyer_id != u.id:
            raise HTTPException(404, "Order not found")
        if row.status not in ("ACCEPTED", "DELIVERED"):
            raise HTTPException(409, "Order cannot be completed")
        release_market_order(db, row); db.commit()
        return _market_order_json(db, row)

    @router.post("/market/orders/{order_id}/cancel")
    def cancel_market(order_id: int, u: User = Depends(current_user), db: Session = Depends(get_db)):
        row = db.get(QMarketOrder, order_id)
        if not row or row.buyer_id != u.id:
            raise HTTPException(404, "Order not found")
        if row.status != "PAID":
            raise HTTPException(409, "Only an unaccepted order can be cancelled")
        _system_to_user(db, "ESCROW", row.buyer_id, row.total_micros, "MARKET_REFUND", reference=row.order_code)
        listing = db.get(QMarketListing, row.listing_id)
        if listing:
            listing.inventory += row.quantity; listing.updated_at = _now()
        row.status = "CANCELLED"; row.updated_at = _now(); db.commit()
        return _market_order_json(db, row)

    @router.post("/market/orders/{order_id}/dispute")
    def dispute_market(order_id: int, body: DisputeIn, u: User = Depends(current_user), db: Session = Depends(get_db)):
        row = db.get(QMarketOrder, order_id)
        if not row or u.id not in (row.buyer_id, row.seller_id):
            raise HTTPException(404, "Order not found")
        if row.status in ("COMPLETED", "CANCELLED", "REFUNDED"):
            raise HTTPException(409, "Order is already closed")
        row.status = "DISPUTED"; row.dispute_note = body.note.strip(); row.updated_at = _now(); db.commit()
        return _market_order_json(db, row)

    @router.get("/admin/me")
    def admin_me(u: User = Depends(require_admin), db: Session = Depends(get_db)):
        role = _admin_role(db, u.id)
        return {"id": u.id, "username": u.username, "display_name": u.display_name, "role": role.role}

    @router.get("/admin/roles")
    def admin_roles(u: User = Depends(require_admin), db: Session = Depends(get_db)):
        rows = db.scalars(select(QAdminRole).order_by(QAdminRole.created_at, QAdminRole.user_id)).all()
        out = []
        for row in rows:
            user = db.get(User, row.user_id)
            if not user:
                continue
            out.append({
                "user_id": row.user_id, "username": user.username, "display_name": user.display_name,
                "role": row.role, "active": row.active, "created_at": row.created_at.isoformat(),
            })
        return {"roles": sorted(ADMIN_ROLES), "items": out}

    @router.post("/admin/roles")
    def admin_set_role(body: AdminRoleIn, u: User = Depends(require_master), db: Session = Depends(get_db)):
        username = body.username.strip().lower()
        role_name = body.role.strip().upper()
        if role_name not in ADMIN_ROLES:
            raise HTTPException(422, "Unknown admin role")
        target = db.scalar(select(User).where(User.username == username))
        if not target:
            raise HTTPException(404, "LEMMIQ user not found")
        row = db.get(QAdminRole, target.id)
        if not row:
            row = QAdminRole(user_id=target.id, role=role_name, active=body.active)
            db.add(row)
        else:
            if target.id == u.id and (role_name != "MASTER_ADMIN" or not body.active):
                raise HTTPException(409, "Master Admin cannot demote or disable the currently signed-in Master Admin")
            row.role = role_name
            row.active = body.active
        db.commit()
        return {"ok": True, "user_id": target.id, "username": target.username, "role": row.role, "active": row.active}

    @router.get("/admin/economy")
    def admin_economy(u: User = Depends(require_admin), db: Session = Depends(get_db)):
        users = db.scalars(select(User.id)).all()
        for uid in users:
            try:
                _accrue_user_packages(db, uid)
            except HTTPException:
                # Do not fail the dashboard if the mining treasury is temporarily depleted.
                break
        db.commit()
        cfg = _config(db)
        system = db.scalars(select(QSystemWallet).order_by(QSystemWallet.key)).all()
        circulation = db.scalar(select(func.coalesce(func.sum(QUserWallet.balance_micros), 0))) or 0
        active_subs = db.scalar(select(func.count()).select_from(QSubscriptionLot).where(QSubscriptionLot.status == "ACTIVE")) or 0
        pending = db.scalar(select(func.count()).select_from(QPaymentOrder).where(QPaymentOrder.status == "PENDING")) or 0
        received = db.scalar(select(func.coalesce(func.sum(QPaymentOrder.expected_usdt_micros), 0)).where(QPaymentOrder.status == "APPROVED")) or 0
        accrued = db.scalar(select(func.coalesce(func.sum(QSubscriptionLot.accrued_usd_micros), 0))) or 0
        caps = db.scalar(select(func.coalesce(func.sum(QSubscriptionLot.cap_usd_micros), 0))) or 0
        market_volume = db.scalar(select(func.coalesce(func.sum(QMarketOrder.total_micros), 0)).where(QMarketOrder.status == "COMPLETED")) or 0
        return {
            "q_reference_usd": cfg.q_price_microusd / USD_MICROS,
            "max_supply_q": 1_000_000_000,
            "initial_unlocked_q": 10_000_000,
            "circulating_q": _q(circulation),
            "system_wallets": [{"key": x.key, "label": x.label, "balance_q": _q(x.balance_micros)} for x in system],
            "subscriptions": {
                "active": int(active_subs), "pending_payments": int(pending),
                "approved_usdt": round(received / 1_000_000, 6),
                "accrued_usd_reference": _usd(accrued), "maximum_package_caps_usd": _usd(caps),
            },
            "market": {"completed_volume_q": _q(market_volume)},
            "cashout_enabled": bool(cfg.cashout_enabled),
        }

    @router.get("/admin/payment-wallets")
    def admin_payment_wallets(u: User = Depends(require_admin), db: Session = Depends(get_db)):
        rows = db.scalars(select(QPaymentWallet).order_by(QPaymentWallet.id.desc())).all()
        return [_payment_wallet_json(x) for x in rows]

    @router.post("/admin/payment-wallets")
    def admin_add_payment_wallet(body: AdminPaymentWalletIn, u: User = Depends(require_master), db: Session = Depends(get_db)):
        network = body.network.strip().upper()
        _validate_payment_address(network, body.address.strip())
        code = body.package_code.strip().upper() if body.package_code else None
        if code and code not in PACKAGE_PLANS:
            raise HTTPException(422, "Unknown package code")
        row = QPaymentWallet(
            network=network, package_code=code, label=body.label.strip(),
            address=body.address.strip(), active=body.active,
        )
        db.add(row); db.commit(); db.refresh(row)
        return _payment_wallet_json(row)

    @router.put("/admin/payment-wallets/{wallet_id}")
    def admin_update_payment_wallet(wallet_id: int, body: AdminPaymentWalletIn, u: User = Depends(require_master), db: Session = Depends(get_db)):
        row = db.get(QPaymentWallet, wallet_id)
        if not row:
            raise HTTPException(404, "Payment wallet not found")
        network = body.network.strip().upper(); _validate_payment_address(network, body.address.strip())
        code = body.package_code.strip().upper() if body.package_code else None
        if code and code not in PACKAGE_PLANS:
            raise HTTPException(422, "Unknown package code")
        row.network = network; row.package_code = code; row.label = body.label.strip()
        row.address = body.address.strip(); row.active = body.active; row.updated_at = _now()
        db.commit(); return _payment_wallet_json(row)

    @router.post("/admin/payment-wallets/{wallet_id}/qr")
    async def admin_upload_qr(wallet_id: int, file: UploadFile = File(...), u: User = Depends(require_master), db: Session = Depends(get_db)):
        row = db.get(QPaymentWallet, wallet_id)
        if not row:
            raise HTTPException(404, "Payment wallet not found")
        raw = await file.read()
        if len(raw) > 600_000:
            raise HTTPException(413, "QR image must be under 600 KB")
        if not (file.content_type or "").startswith("image/"):
            raise HTTPException(422, "QR upload must be an image")
        row.qr_image_b64 = base64.b64encode(raw).decode()
        row.updated_at = _now(); db.commit()
        return _payment_wallet_json(row)

    @router.get("/admin/payment-orders")
    def admin_payment_orders(status: str = "", u: User = Depends(require_admin), db: Session = Depends(get_db)):
        stmt = select(QPaymentOrder)
        if status.strip():
            stmt = stmt.where(QPaymentOrder.status == status.strip().upper())
        rows = db.scalars(stmt.order_by(QPaymentOrder.id.desc()).limit(500)).all()
        out = []
        for row in rows:
            item = _payment_order_json(db, row)
            user = db.get(User, row.user_id)
            item["user"] = {"id": user.id, "username": user.username, "display_name": user.display_name} if user else None
            out.append(item)
        return out

    @router.post("/admin/payment-orders/{order_id}/approve")
    def admin_approve_payment(order_id: int, u: User = Depends(require_admin), db: Session = Depends(get_db)):
        _require_roles(db, u, "MASTER_ADMIN", "FINANCE_ADMIN")
        row = db.get(QPaymentOrder, order_id)
        if not row:
            raise HTTPException(404, "Payment order not found")
        if row.status != "PENDING" or not row.submitted_tx_hash:
            raise HTTPException(409, "Only a submitted pending payment can be approved")
        if db.scalar(select(QSubscriptionLot).where(QSubscriptionLot.payment_order_id == row.id)):
            raise HTTPException(409, "Package already activated for this payment")
        plan = PACKAGE_PLANS[row.package_code]
        now = _now()
        lot = QSubscriptionLot(
            user_id=row.user_id, payment_order_id=row.id, package_code=row.package_code,
            purchase_usd_micros=plan["price_usd"] * USD_MICROS,
            daily_rate_bps=plan["daily_rate_bps"],
            cap_usd_micros=plan["price_usd"] * 2 * USD_MICROS,
            accrued_usd_micros=0, accrued_q_micros=0,
            started_at=now, expires_at=now + timedelta(days=365),
            last_accrual_date=now.date(), status="ACTIVE",
        )
        row.status = "APPROVED"; row.reviewed_at = now; row.reviewed_by = u.id
        db.add(lot); db.commit(); db.refresh(lot)
        return {"ok": True, "payment": _payment_order_json(db, row), "subscription": _subscription_json(lot, _config(db))}

    @router.post("/admin/payment-orders/{order_id}/reject")
    def admin_reject_payment(order_id: int, body: DisputeIn, u: User = Depends(require_admin), db: Session = Depends(get_db)):
        _require_roles(db, u, "MASTER_ADMIN", "FINANCE_ADMIN")
        row = db.get(QPaymentOrder, order_id)
        if not row:
            raise HTTPException(404, "Payment order not found")
        if row.status != "PENDING":
            raise HTTPException(409, "Only pending payments can be rejected")
        row.status = "REJECTED"; row.admin_note = body.note.strip(); row.reviewed_at = _now(); row.reviewed_by = u.id
        db.commit(); return _payment_order_json(db, row)

    @router.put("/admin/config")
    def admin_config(body: AdminConfigIn, u: User = Depends(require_master), db: Session = Depends(get_db)):
        cfg = _config(db)
        if body.q_price_usd is not None:
            cfg.q_price_microusd = int(round(body.q_price_usd * USD_MICROS))
        if body.marketplace_fee_percent is not None:
            cfg.marketplace_fee_bps = int(round(body.marketplace_fee_percent * 100))
        if body.basic_daily_q is not None:
            cfg.basic_daily_micros = int(round(body.basic_daily_q * Q_MICROS))
        if body.signup_bonus_q is not None:
            cfg.signup_bonus_micros = int(round(body.signup_bonus_q * Q_MICROS))
        if body.referral_referrer_q is not None:
            cfg.referral_referrer_micros = int(round(body.referral_referrer_q * Q_MICROS))
        if body.referral_referred_q is not None:
            cfg.referral_referred_micros = int(round(body.referral_referred_q * Q_MICROS))
        cfg.updated_at = _now(); db.commit()
        return config(db)

    @router.post("/admin/treasury/transfer")
    def admin_treasury_transfer(body: TreasuryTransferIn, u: User = Depends(require_master), db: Session = Depends(get_db)):
        from_key, to_key = body.from_wallet.strip().upper(), body.to_wallet.strip().upper()
        if from_key not in SYSTEM_OPENING_Q or to_key not in SYSTEM_OPENING_Q:
            raise HTTPException(422, "Unknown Q system wallet")
        amount = int(round(body.amount_q * Q_MICROS))
        _system_to_system(db, from_key, to_key, amount, "ADMIN_TREASURY", reference=f"admin:{u.id}", note=body.reason)
        db.commit()
        return {"ok": True}

    @router.get("/admin/ledger")
    def admin_ledger(limit: int = 250, u: User = Depends(require_admin), db: Session = Depends(get_db)):
        limit = max(1, min(limit, 1000))
        rows = db.scalars(select(QLedgerEntry).order_by(QLedgerEntry.id.desc()).limit(limit)).all()
        return [{
            "id": x.id, "tx_id": x.tx_id, "kind": x.kind, "amount_q": _q(x.amount_micros),
            "from_system": x.from_system_key, "from_user": x.from_user_id,
            "to_system": x.to_system_key, "to_user": x.to_user_id,
            "reference": x.reference, "note": x.note, "created_at": x.created_at.isoformat(),
        } for x in rows]

    @router.get("/admin/market/orders")
    def admin_market_orders(u: User = Depends(require_admin), db: Session = Depends(get_db)):
        rows = db.scalars(select(QMarketOrder).order_by(QMarketOrder.id.desc()).limit(500)).all()
        return [_market_order_json(db, x) for x in rows]

    @router.post("/admin/market/orders/{order_id}/resolve")
    def admin_resolve_market(order_id: int, body: ResolveDisputeIn, u: User = Depends(require_admin), db: Session = Depends(get_db)):
        _require_roles(db, u, "MASTER_ADMIN", "MARKETPLACE_ADMIN", "RISK_ADMIN")
        row = db.get(QMarketOrder, order_id)
        if not row or row.status != "DISPUTED":
            raise HTTPException(404, "Open dispute not found")
        outcome = body.outcome.strip().upper()
        if outcome == "BUYER":
            _system_to_user(db, "ESCROW", row.buyer_id, row.total_micros, "DISPUTE_REFUND", reference=row.order_code, note=body.note)
            listing = db.get(QMarketListing, row.listing_id)
            if listing:
                listing.inventory += row.quantity; listing.updated_at = _now()
            row.status = "REFUNDED"
        elif outcome == "SELLER":
            release_market_order(db, row)
        else:
            raise HTTPException(422, "Outcome must be BUYER or SELLER")
        row.updated_at = _now(); db.commit()
        return _market_order_json(db, row)

    app.include_router(router)
