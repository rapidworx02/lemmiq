"""LEMMIQ V2.8 Q Economy Beta.

Centralised Q ledger + wallet, usage mining, referrals, subscription lots,
manual USDT (TRC20/BEP20) payment approval, Q Marketplace, escrow, and
browser-first admin controls.

Q is an internal utility unit in V2.8.3. Cash-out is deliberately disabled.
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
from fastapi.responses import RedirectResponse, Response, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from .database import Base
from .admin_permissions import permission_level, require_permission, section_for_path
from .models import User
from . import media_store

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
    "PREDICT_ESCROW": 0,
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

REFERRAL_PACKAGE_DEFAULT_Q = {
    "STARTER_10": 10,
    "PLUS_50": 25,
    "PRO_100": 50,
    "PREMIUM_500": 200,
    "ELITE_1000": 400,
}

MARKET_ALLOWED_MIME = {
    "image/jpeg": "PHOTO", "image/png": "PHOTO", "image/webp": "PHOTO",
    "video/mp4": "VIDEO", "video/webm": "VIDEO", "video/quicktime": "VIDEO",
    "application/pdf": "FILE", "text/plain": "FILE", "text/csv": "FILE",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "FILE",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "FILE",
}
MARKET_IMAGE_FILE_MAX = 20 * 1024 * 1024
MARKET_VIDEO_MAX = 100 * 1024 * 1024
MARKET_MAX_ATTACHMENTS = 10


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


class QPackageRule(Base):
    __tablename__ = "q_package_rules"
    package_code: Mapped[str] = mapped_column(String(32), primary_key=True)
    label: Mapped[str] = mapped_column(String(80), default="")
    daily_rate_bps: Mapped[int] = mapped_column(Integer)
    cap_percent: Mapped[int] = mapped_column(Integer, default=200)
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


class QReferralRewardRule(Base):
    __tablename__ = "q_referral_reward_rules"
    package_code: Mapped[str] = mapped_column(String(32), primary_key=True)
    label: Mapped[str] = mapped_column(String(80), default="")
    reward_micros: Mapped[int] = mapped_column(BigInteger, default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class QReferralEarning(Base):
    __tablename__ = "q_referral_earnings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    referrer_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    referred_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(40), index=True)
    package_code: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    payment_order_id: Mapped[int] = mapped_column(ForeignKey("q_payment_orders.id"), unique=True, index=True)
    reward_micros: Mapped[int] = mapped_column(BigInteger, default=0)
    status: Mapped[str] = mapped_column(String(20), default="PAID", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


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


class QSubscriptionOverride(Base):
    __tablename__ = "q_subscription_overrides"
    lot_id: Mapped[int] = mapped_column(ForeignKey("q_subscription_lots.id"), primary_key=True)
    daily_rate_override: Mapped[bool] = mapped_column(Boolean, default=False)
    cap_percent_override: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class QAdminAuditLog(Base):
    __tablename__ = "q_admin_audit_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    admin_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    action: Mapped[str] = mapped_column(String(80), index=True)
    target_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    subscription_lot_id: Mapped[int | None] = mapped_column(ForeignKey("q_subscription_lots.id"), nullable=True, index=True)
    before_json: Mapped[str] = mapped_column(Text, default="{}")
    after_json: Mapped[str] = mapped_column(Text, default="{}")
    reason: Mapped[str] = mapped_column(String(300), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


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


class QMarketMedia(Base):
    __tablename__ = "q_market_media"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("q_market_listings.id"), index=True)
    uploader_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    kind: Mapped[str] = mapped_column(String(16), index=True)
    original_name: Mapped[str] = mapped_column(String(190), default="Attachment")
    mime_type: Mapped[str] = mapped_column(String(120), default="application/octet-stream")
    object_key: Mapped[str] = mapped_column(String(240))
    access_token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    size_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_cover: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


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


class AdminPaymentWalletSlotIn(BaseModel):
    label: str = Field(default="", max_length=100)
    address: str = Field(min_length=20, max_length=160)
    active: bool = True


class PackageRuleUpdateIn(BaseModel):
    daily_rate_percent: float = Field(ge=0, le=10)
    cap_percent: float = Field(ge=0, le=1000)
    apply_to_existing: bool = True
    include_custom: bool = False
    reason: str = Field(default="Package master setting update", max_length=300)


class UserPackageEditIn(BaseModel):
    daily_rate_percent: float | None = Field(default=None, ge=0, le=10)
    cap_percent: float | None = Field(default=None, ge=0, le=1000)
    status: str | None = Field(default=None, max_length=30)
    clear_daily_override: bool = False
    clear_cap_override: bool = False
    reason: str = Field(min_length=3, max_length=300)


class WalletAdjustmentIn(BaseModel):
    amount_q: float = Field(ge=-100_000_000, le=100_000_000)
    reason: str = Field(min_length=3, max_length=300)


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


class ReferralRulesIn(BaseModel):
    starter_10_q: float = Field(ge=0, le=1_000_000)
    plus_50_q: float = Field(ge=0, le=1_000_000)
    pro_100_q: float = Field(ge=0, le=1_000_000)
    premium_500_q: float = Field(ge=0, le=1_000_000)
    elite_1000_q: float = Field(ge=0, le=1_000_000)


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


def validate_signup_referral(db: Session, code: str | None) -> User | None:
    """Validate an optional referral code before account creation."""
    clean = (code or "").strip().upper()
    if not clean:
        return None
    try:
        return _referrer_from_code(db, clean)
    except HTTPException:
        raise HTTPException(400, "Referral code is invalid")


def apply_signup_referral(db: Session, new_user: User, code: str | None) -> None:
    """Apply a valid referral during signup.

    Rewards are issued once, from the REFERRALS treasury, and the new user's
    normal signup bonus is also created through the standard Q wallet path.
    """
    clean = (code or "").strip().upper()
    if not clean:
        return
    if db.scalar(select(func.count()).select_from(QReferral).where(QReferral.referred_user_id == new_user.id)):
        return
    referrer = _referrer_from_code(db, clean)
    if referrer.id == new_user.id:
        raise HTTPException(422, "You cannot refer yourself")
    cfg = _config(db)
    _ensure_user_wallet(db, referrer.id)
    _ensure_user_wallet(db, new_user.id)
    _system_to_user(
        db, "REFERRALS", referrer.id, cfg.referral_referrer_micros,
        "REFERRAL_REWARD", reference=f"referred:{new_user.id}", note="Referral used during signup"
    )
    _system_to_user(
        db, "REFERRALS", new_user.id, cfg.referral_referred_micros,
        "REFERRAL_WELCOME", reference=f"referrer:{referrer.id}", note="Referral welcome reward"
    )
    db.add(QReferral(
        referrer_user_id=referrer.id,
        referred_user_id=new_user.id,
        code=clean,
        referrer_reward_micros=cfg.referral_referrer_micros,
        referred_reward_micros=cfg.referral_referred_micros,
    ))


def _user_json_brief(db: Session, uid: int | None):
    if not uid:
        return None
    u = db.get(User, uid)
    if not u:
        return {"id": uid, "username": "", "display_name": f"User #{uid}"}
    return {"id": u.id, "username": u.username, "display_name": u.display_name}


def _seed_package_rules(db: Session):
    for code, plan in PACKAGE_PLANS.items():
        row = db.get(QPackageRule, code)
        if not row:
            db.add(QPackageRule(
                package_code=code, label=plan["name"],
                daily_rate_bps=plan["daily_rate_bps"], cap_percent=200,
            ))
    db.flush()


def _package_rule(db: Session, code: str) -> QPackageRule:
    row = db.get(QPackageRule, code)
    if not row:
        plan = PACKAGE_PLANS.get(code)
        if not plan:
            raise HTTPException(422, "Unknown package")
        row = QPackageRule(
            package_code=code, label=plan["name"],
            daily_rate_bps=plan["daily_rate_bps"], cap_percent=200,
        )
        db.add(row); db.flush()
    return row


def _package_rule_json(row: QPackageRule):
    plan = PACKAGE_PLANS.get(row.package_code, {})
    return {
        "package_code": row.package_code,
        "name": plan.get("name", row.label or row.package_code),
        "price_usd": plan.get("price_usd", 0),
        "daily_rate_percent": row.daily_rate_bps / 100,
        "cap_percent": row.cap_percent,
        "updated_at": row.updated_at.isoformat(),
    }


def _subscription_override(db: Session, lot_id: int, create: bool = False) -> QSubscriptionOverride | None:
    row = db.get(QSubscriptionOverride, lot_id)
    if not row and create:
        row = QSubscriptionOverride(lot_id=lot_id)
        db.add(row); db.flush()
    return row


def _audit(db: Session, admin_id: int, action: str, *, target_user_id: int | None = None, lot_id: int | None = None, before=None, after=None, reason: str = ""):
    db.add(QAdminAuditLog(
        admin_user_id=admin_id, action=action[:80], target_user_id=target_user_id, subscription_lot_id=lot_id,
        before_json=json.dumps(before or {}, ensure_ascii=False, default=str)[:12000],
        after_json=json.dumps(after or {}, ensure_ascii=False, default=str)[:12000],
        reason=(reason or "")[:300],
    ))


def _package_snapshot(row: QSubscriptionLot, db: Session):
    ov = _subscription_override(db, row.id, False)
    purchase = max(1, row.purchase_usd_micros)
    return {
        "id": row.id, "user_id": row.user_id, "package_code": row.package_code,
        "daily_rate_percent": row.daily_rate_bps / 100,
        "cap_percent": round(row.cap_usd_micros * 100 / purchase, 4),
        "status": row.status,
        "daily_override": bool(ov and ov.daily_rate_override),
        "cap_override": bool(ov and ov.cap_percent_override),
    }


def _referral_rule_json(row: QReferralRewardRule):
    return {
        "package_code": row.package_code,
        "label": row.label or PACKAGE_PLANS.get(row.package_code, {}).get("name", row.package_code),
        "reward_q": _q(row.reward_micros),
        "active": bool(row.active),
    }


def _seed_referral_rules(db: Session):
    for code, reward_q in REFERRAL_PACKAGE_DEFAULT_Q.items():
        if not db.get(QReferralRewardRule, code):
            db.add(QReferralRewardRule(
                package_code=code,
                label=PACKAGE_PLANS[code]["name"],
                reward_micros=int(reward_q * Q_MICROS),
                active=True,
            ))


def _market_media_json(row: QMarketMedia):
    url = f"/v28/market/media/{row.id}/{row.access_token}"
    return {
        "id": row.id, "kind": row.kind, "name": row.original_name,
        "mime_type": row.mime_type, "size_bytes": row.size_bytes,
        "is_cover": bool(row.is_cover), "sort_order": row.sort_order,
        "media_url": url, "download_url": url + "?download=1",
        "created_at": row.created_at.isoformat(),
    }


def _verify_market_bytes(mime: str, payload: bytes):
    if mime == "image/jpeg" and not payload.startswith(b"\xff\xd8\xff"):
        raise HTTPException(415, "File bytes do not match JPEG")
    if mime == "image/png" and not payload.startswith(b"\x89PNG\r\n\x1a\n"):
        raise HTTPException(415, "File bytes do not match PNG")
    if mime == "image/webp" and not (payload.startswith(b"RIFF") and payload[8:12] == b"WEBP"):
        raise HTTPException(415, "File bytes do not match WebP")
    if mime == "application/pdf" and not payload.startswith(b"%PDF-"):
        raise HTTPException(415, "File bytes do not match PDF")
    if mime == "video/mp4" and b"ftyp" not in payload[:32]:
        raise HTTPException(415, "File bytes do not match MP4")


def _active_tier_for_user(db: Session, uid: int) -> str:
    now = _now()
    lots = db.scalars(select(QSubscriptionLot).where(
        QSubscriptionLot.user_id == uid, QSubscriptionLot.expires_at > now
    )).all()
    if not lots:
        return "Free"
    best = max(lots, key=lambda x: PACKAGE_PLANS.get(x.package_code, {}).get("price_usd", 0))
    return PACKAGE_PLANS.get(best.package_code, {}).get("name", best.package_code)


def _award_subscription_referral(db: Session, payment: QPaymentOrder):
    link = db.scalar(select(QReferral).where(QReferral.referred_user_id == payment.user_id))
    if not link:
        return None
    existing = db.scalar(select(QReferralEarning).where(QReferralEarning.payment_order_id == payment.id))
    if existing:
        return existing
    rule = db.get(QReferralRewardRule, payment.package_code)
    if not rule or not rule.active or rule.reward_micros <= 0:
        return None
    earning = QReferralEarning(
        referrer_user_id=link.referrer_user_id, referred_user_id=payment.user_id,
        event_type="PACKAGE_PURCHASE", package_code=payment.package_code,
        payment_order_id=payment.id, reward_micros=rule.reward_micros, status="PENDING",
    )
    db.add(earning)
    treasury = _system(db, "REFERRALS")
    if treasury.balance_micros >= rule.reward_micros:
        _system_to_user(
            db, "REFERRALS", link.referrer_user_id, rule.reward_micros,
            "REFERRAL_PACKAGE_REWARD", reference=f"payment:{payment.id}",
            note=f"Referral reward for {PACKAGE_PLANS.get(payment.package_code, {}).get('name', payment.package_code)}",
        )
        earning.status = "PAID"
        earning.paid_at = _now()
    return earning


def _plan_json(db: Session, code: str, cfg: QEconomyConfig):
    p = PACKAGE_PLANS[code]
    rule = _package_rule(db, code)
    price_usd = p["price_usd"]
    daily_usd = price_usd * rule.daily_rate_bps / 10_000
    cap_usd = price_usd * rule.cap_percent / 100
    daily_q_at_reference = daily_usd / (cfg.q_price_microusd / USD_MICROS)
    return {
        "code": code,
        "name": p["name"],
        "price_usd": price_usd,
        "daily_rate_percent": rule.daily_rate_bps / 100,
        "daily_usd_reference": round(daily_usd, 6),
        "daily_q_at_current_reference": round(daily_q_at_reference, 6),
        "valid_days": 365,
        "cap_percent": rule.cap_percent,
        "cap_usd": round(cap_usd, 6),
        "cap_q_at_current_reference": round(cap_usd / (cfg.q_price_microusd / USD_MICROS), 6),
    }


def _subscription_json(row: QSubscriptionLot, cfg: QEconomyConfig, db: Session | None = None):
    p = PACKAGE_PLANS.get(row.package_code, {"name": row.package_code})
    remaining = max(0, row.cap_usd_micros - row.accrued_usd_micros)
    purchase = max(1, row.purchase_usd_micros)
    cap_percent = row.cap_usd_micros * 100 / purchase
    earned_percent = row.accrued_usd_micros * 100 / purchase
    progress_to_cap = (row.accrued_usd_micros * 100 / row.cap_usd_micros) if row.cap_usd_micros else 0
    ov = _subscription_override(db, row.id, False) if db is not None else None
    return {
        "id": row.id,
        "package_code": row.package_code,
        "package_name": p["name"],
        "purchase_usd": _usd(row.purchase_usd_micros),
        "daily_rate_percent": row.daily_rate_bps / 100,
        "accrued_usd_reference": _usd(row.accrued_usd_micros),
        "accrued_q": _q(row.accrued_q_micros),
        "earned_percent": round(earned_percent, 4),
        "cap_percent": round(cap_percent, 4),
        "progress_to_cap_percent": round(progress_to_cap, 4),
        "cap_usd": _usd(row.cap_usd_micros),
        "remaining_cap_usd": _usd(remaining),
        "status": row.status,
        "daily_rate_override": bool(ov and ov.daily_rate_override),
        "cap_percent_override": bool(ov and ov.cap_percent_override),
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
        "cashout_note": "Cash-out is not enabled in LEMMIQ V2.8.3.",
        "basic_daily_q": _q(cfg.basic_daily_micros),
        "basic_claimed_today": bool(today_claimed),
        "signup_bonus_q": _q(cfg.signup_bonus_micros),
        "referral_code": _referral_code(u),
        "referral_reward_q": _q(cfg.referral_referrer_micros),
        "admin_role": role.role if role and role.active else None,
        "packages": [_subscription_json(x, cfg, db) for x in subs],
        "plans": [_plan_json(db, code, cfg) for code in PACKAGE_PLANS],
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
    media = db.scalars(select(QMarketMedia).where(QMarketMedia.listing_id == row.id).order_by(
        QMarketMedia.is_cover.desc(), QMarketMedia.sort_order, QMarketMedia.id
    )).all()
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
        "media": [_market_media_json(x) for x in media],
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

    def require_admin(request: Request, u: User = Depends(current_user), db: Session = Depends(get_db)):
        role = _admin_role(db, u.id)
        if not role:
            raise HTTPException(403, "Admin access required")
        if role.role == "MASTER_ADMIN":
            return u
        section = section_for_path(request.url.path)
        required = "READ" if request.method.upper() == "GET" else ("FULL" if request.method.upper() == "DELETE" else "WRITE")
        # READ_ONLY is never allowed to mutate anything.
        if role.role == "READ_ONLY" and required != "READ":
            raise HTTPException(403, "Read-only admin cannot edit")
        require_permission(db, u.id, section, required)
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
            _seed_referral_rules(db)
            _seed_package_rules(db)
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
        return RedirectResponse("/web/#q-admin")

    @router.get("/config")
    def config(db: Session = Depends(get_db)):
        cfg = _config(db)
        return {
            "version": "2.8.3",
            "q_reference_usd": cfg.q_price_microusd / USD_MICROS,
            "marketplace_fee_percent": cfg.marketplace_fee_bps / 100,
            "cashout_enabled": bool(cfg.cashout_enabled),
            "max_supply_q": 1_000_000_000,
            "initial_unlocked_q": 10_000_000,
            "plans": [_plan_json(db, code, cfg) for code in PACKAGE_PLANS],
            "referral_package_rewards": [_referral_rule_json(x) for x in db.scalars(select(QReferralRewardRule).order_by(QReferralRewardRule.package_code)).all()],
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
        items = []
        total_paid = 0
        total_pending = 0
        paid_users = 0
        for link in rows:
            referred = db.get(User, link.referred_user_id)
            earnings = db.scalars(select(QReferralEarning).where(
                QReferralEarning.referrer_user_id == u.id,
                QReferralEarning.referred_user_id == link.referred_user_id,
            ).order_by(QReferralEarning.id)).all()
            package_paid = sum(x.reward_micros for x in earnings if x.status == "PAID")
            package_pending = sum(x.reward_micros for x in earnings if x.status == "PENDING")
            pending_orders = db.scalars(select(QPaymentOrder).where(
                QPaymentOrder.user_id == link.referred_user_id, QPaymentOrder.status == "PENDING"
            )).all()
            pending_potential = 0
            for po in pending_orders:
                rule = db.get(QReferralRewardRule, po.package_code)
                if rule and rule.active:
                    pending_potential += rule.reward_micros
            approved_count = db.scalar(select(func.count()).select_from(QPaymentOrder).where(
                QPaymentOrder.user_id == link.referred_user_id, QPaymentOrder.status == "APPROVED"
            )) or 0
            if approved_count:
                paid_users += 1
            signup_paid = link.referrer_reward_micros
            earned = signup_paid + package_paid
            pending = package_pending + pending_potential
            total_paid += earned
            total_pending += pending
            events = [{
                "type": "FREE_SIGNUP", "label": "Free signup referral",
                "reward_q": _q(signup_paid), "status": "PAID",
                "created_at": link.created_at.isoformat(),
            }]
            events += [{
                "type": x.event_type,
                "label": PACKAGE_PLANS.get(x.package_code or "", {}).get("name", x.package_code or x.event_type),
                "package_code": x.package_code, "reward_q": _q(x.reward_micros),
                "status": x.status, "created_at": x.created_at.isoformat(),
                "paid_at": x.paid_at.isoformat() if x.paid_at else None,
            } for x in earnings]
            items.append({
                "user_id": link.referred_user_id,
                "username": referred.username if referred else "",
                "display_name": referred.display_name if referred else "",
                "current_tier": _active_tier_for_user(db, link.referred_user_id),
                "reward_q": _q(earned),
                "pending_q": _q(pending),
                "created_at": link.created_at.isoformat(),
                "events": events,
            })
        return {
            "code": _referral_code(u),
            "count": len(rows),
            "paid_users": paid_users,
            "earned_q": _q(total_paid),
            "pending_q": _q(total_pending),
            "items": items,
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
            raise HTTPException(409, f"No active {network} wallet is configured for {PACKAGE_PLANS[code]['name']}")
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
        if not row:
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

    @router.post("/market/listings/{listing_id}/media")
    async def upload_market_media(listing_id: int, file: UploadFile = File(...), u: User = Depends(current_user), db: Session = Depends(get_db)):
        listing = db.get(QMarketListing, listing_id)
        if not listing or listing.seller_id != u.id:
            raise HTTPException(404, "Listing not found")
        count = db.scalar(select(func.count()).select_from(QMarketMedia).where(QMarketMedia.listing_id == listing_id)) or 0
        if count >= MARKET_MAX_ATTACHMENTS:
            raise HTTPException(409, f"A listing can have up to {MARKET_MAX_ATTACHMENTS} attachments")
        mime = (file.content_type or "").split(";")[0].strip().lower()
        kind = MARKET_ALLOWED_MIME.get(mime)
        if not kind:
            raise HTTPException(415, "Unsupported marketplace file type")
        limit = MARKET_VIDEO_MAX if kind == "VIDEO" else MARKET_IMAGE_FILE_MAX
        payload = await file.read(limit + 1)
        if not payload or len(payload) > limit:
            max_mb = limit // (1024 * 1024)
            raise HTTPException(413, f"File must be between 1 byte and {max_mb} MB")
        _verify_market_bytes(mime, payload)
        original = (file.filename or "Attachment").replace("\\", "/").split("/")[-1]
        original = re.sub(r"[^A-Za-z0-9 .()_\-]", "_", original)[:190] or "Attachment"
        object_key = media_store.store(payload)
        first_media = count == 0
        row = QMarketMedia(
            listing_id=listing.id, uploader_user_id=u.id, kind=kind, original_name=original,
            mime_type=mime, object_key=object_key, access_token=secrets.token_hex(20),
            size_bytes=len(payload), sort_order=int(count), is_cover=first_media and kind == "PHOTO",
        )
        db.add(row); listing.updated_at = _now(); db.commit(); db.refresh(row)
        return _market_media_json(row)

    @router.get("/market/media/{media_id}/{token}")
    def market_media(media_id: int, token: str, download: int = 0, db: Session = Depends(get_db)):
        row = db.get(QMarketMedia, media_id)
        if not row or not secrets.compare_digest(row.access_token, token):
            raise HTTPException(404, "Marketplace media not found")
        safe_name = (row.original_name or "file").replace('"', '').replace("\r", "").replace("\n", "")
        disposition = "attachment" if download or row.kind == "FILE" else "inline"
        return StreamingResponse(
            media_store.stream(row.object_key), media_type=row.mime_type or "application/octet-stream",
            headers={
                "Content-Disposition": f'{disposition}; filename="{safe_name}"',
                "Cache-Control": "private, max-age=3600", "X-Content-Type-Options": "nosniff",
            },
        )

    @router.delete("/market/listings/{listing_id}/media/{media_id}")
    def delete_market_media(listing_id: int, media_id: int, u: User = Depends(current_user), db: Session = Depends(get_db)):
        listing = db.get(QMarketListing, listing_id)
        row = db.get(QMarketMedia, media_id)
        if not listing or listing.seller_id != u.id or not row or row.listing_id != listing_id:
            raise HTTPException(404, "Marketplace attachment not found")
        was_cover = row.is_cover
        object_key = row.object_key
        db.delete(row); db.flush()
        if was_cover:
            replacement = db.scalar(select(QMarketMedia).where(
                QMarketMedia.listing_id == listing_id, QMarketMedia.kind == "PHOTO"
            ).order_by(QMarketMedia.sort_order, QMarketMedia.id).limit(1))
            if replacement:
                replacement.is_cover = True
        listing.updated_at = _now(); db.commit()
        delete_fn = getattr(media_store, "delete", None)
        if callable(delete_fn):
            try:
                delete_fn(object_key)
            except Exception:
                pass
        return {"ok": True}

    @router.post("/market/listings/{listing_id}/media/{media_id}/cover")
    def set_market_cover(listing_id: int, media_id: int, u: User = Depends(current_user), db: Session = Depends(get_db)):
        listing = db.get(QMarketListing, listing_id)
        row = db.get(QMarketMedia, media_id)
        if not listing or listing.seller_id != u.id or not row or row.listing_id != listing_id:
            raise HTTPException(404, "Marketplace attachment not found")
        if row.kind != "PHOTO":
            raise HTTPException(422, "Only a photo can be the cover image")
        for item in db.scalars(select(QMarketMedia).where(QMarketMedia.listing_id == listing_id)).all():
            item.is_cover = item.id == media_id
        listing.updated_at = _now(); db.commit()
        return _listing_json(db, listing)

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

    @router.get("/admin/referral-rules")
    def admin_referral_rules(u: User = Depends(require_admin), db: Session = Depends(get_db)):
        rows = db.scalars(select(QReferralRewardRule).order_by(QReferralRewardRule.package_code)).all()
        return [_referral_rule_json(x) for x in rows]

    @router.put("/admin/referral-rules")
    def admin_save_referral_rules(body: ReferralRulesIn, u: User = Depends(require_master), db: Session = Depends(get_db)):
        values = {
            "STARTER_10": body.starter_10_q, "PLUS_50": body.plus_50_q,
            "PRO_100": body.pro_100_q, "PREMIUM_500": body.premium_500_q,
            "ELITE_1000": body.elite_1000_q,
        }
        for code, value in values.items():
            row = db.get(QReferralRewardRule, code)
            if not row:
                row = QReferralRewardRule(package_code=code, label=PACKAGE_PLANS[code]["name"])
                db.add(row)
            row.reward_micros = int(round(value * Q_MICROS))
            row.active = True
            row.updated_at = _now()
        db.commit()
        return admin_referral_rules(u, db)

    @router.get("/admin/referrals")
    def admin_referral_overview(u: User = Depends(require_admin), db: Session = Depends(get_db)):
        links = db.scalars(select(QReferral)).all()
        earnings = db.scalars(select(QReferralEarning)).all()
        return {
            "total_referred_users": len(links),
            "free_signup_q": _q(sum(x.referrer_reward_micros for x in links)),
            "package_paid_q": _q(sum(x.reward_micros for x in earnings if x.status == "PAID")),
            "package_pending_q": _q(sum(x.reward_micros for x in earnings if x.status == "PENDING")),
            "package_events": len(earnings),
        }

    @router.get("/admin/package-rules")
    def admin_package_rules(u: User = Depends(require_admin), db: Session = Depends(get_db)):
        _seed_package_rules(db); db.commit()
        return [_package_rule_json(_package_rule(db, code)) for code in PACKAGE_PLANS]

    @router.put("/admin/package-rules/{package_code}")
    def admin_update_package_rule(package_code: str, body: PackageRuleUpdateIn, u: User = Depends(require_master), db: Session = Depends(get_db)):
        code = package_code.strip().upper()
        if code not in PACKAGE_PLANS:
            raise HTTPException(404, "Package not found")
        rule = _package_rule(db, code)
        before_rule = _package_rule_json(rule)

        lots = db.scalars(select(QSubscriptionLot).where(QSubscriptionLot.package_code == code)).all()
        if body.apply_to_existing:
            for uid in sorted(set(x.user_id for x in lots if x.status == "ACTIVE")):
                _accrue_user_packages(db, uid)

        rule.daily_rate_bps = int(round(body.daily_rate_percent * 100))
        rule.cap_percent = int(round(body.cap_percent))
        rule.updated_at = _now()
        affected = 0; skipped_custom = 0
        if body.apply_to_existing:
            for lot in lots:
                ov = _subscription_override(db, lot.id, False)
                custom_daily = bool(ov and ov.daily_rate_override)
                custom_cap = bool(ov and ov.cap_percent_override)
                changed = False
                if body.include_custom or not custom_daily:
                    lot.daily_rate_bps = rule.daily_rate_bps; changed = True
                    if ov and body.include_custom: ov.daily_rate_override = False
                elif custom_daily:
                    skipped_custom += 1
                if body.include_custom or not custom_cap:
                    requested_cap = int(lot.purchase_usd_micros * rule.cap_percent / 100)
                    lot.cap_usd_micros = requested_cap; changed = True
                    if ov and body.include_custom: ov.cap_percent_override = False
                elif custom_cap:
                    skipped_custom += 1
                if changed:
                    if lot.status == "CAP_REACHED" and lot.accrued_usd_micros < lot.cap_usd_micros and _now() < lot.expires_at:
                        lot.status = "ACTIVE"
                    if lot.accrued_usd_micros >= lot.cap_usd_micros and lot.status == "ACTIVE":
                        lot.status = "CAP_REACHED"
                    affected += 1
        after_rule = _package_rule_json(rule)
        _audit(db, u.id, "PACKAGE_MASTER_RULE_UPDATE", before=before_rule, after={**after_rule, "affected": affected}, reason=body.reason)
        db.commit()
        return {"ok": True, "rule": after_rule, "affected": affected, "skipped_custom": skipped_custom}

    @router.get("/admin/users")
    def admin_users(q: str = "", package_code: str = "", status: str = "", u: User = Depends(require_admin), db: Session = Depends(get_db)):
        term = q.strip().lower()
        stmt = select(User).order_by(User.id.desc()).limit(500)
        users = db.scalars(stmt).all()
        out = []
        for user in users:
            if term and term not in f"{user.id} {user.username} {user.display_name}".lower():
                continue
            lots = db.scalars(select(QSubscriptionLot).where(QSubscriptionLot.user_id == user.id).order_by(QSubscriptionLot.id.desc())).all()
            if package_code.strip():
                lots = [x for x in lots if x.package_code == package_code.strip().upper()]
            if status.strip():
                lots = [x for x in lots if x.status == status.strip().upper()]
            if (package_code.strip() or status.strip()) and not lots:
                continue
            wallet = db.get(QUserWallet, user.id)
            out.append({
                "user": {"id": user.id, "username": user.username, "display_name": user.display_name},
                "wallet_q": _q(wallet.balance_micros) if wallet else 0,
                "packages": [_subscription_json(x, _config(db), db) for x in lots],
            })
        return out[:250]

    @router.get("/admin/users/{user_id}")
    def admin_user_detail(user_id: int, u: User = Depends(require_admin), db: Session = Depends(get_db)):
        user = db.get(User, user_id)
        if not user:
            raise HTTPException(404, "User not found")
        _accrue_user_packages(db, user.id); db.commit()
        wallet = _raw_user_wallet(db, user.id)
        lots = db.scalars(select(QSubscriptionLot).where(QSubscriptionLot.user_id == user.id).order_by(QSubscriptionLot.id.desc())).all()
        return {
            "user": {"id": user.id, "username": user.username, "display_name": user.display_name},
            "wallet_q": _q(wallet.balance_micros),
            "wallet_usd_reference": round(_q(wallet.balance_micros) * _config(db).q_price_microusd / USD_MICROS, 4),
            "packages": [_subscription_json(x, _config(db), db) for x in lots],
        }

    @router.post("/admin/users/{user_id}/wallet-adjust")
    def admin_adjust_user_wallet(user_id: int, body: WalletAdjustmentIn, u: User = Depends(require_master), db: Session = Depends(get_db)):
        target = db.get(User, user_id)
        if not target:
            raise HTTPException(404, "User not found")
        amount = int(round(body.amount_q * Q_MICROS))
        if amount == 0:
            raise HTTPException(422, "Adjustment cannot be zero")
        before = _q(_raw_user_wallet(db, user_id).balance_micros)
        if amount > 0:
            _system_to_user(db, "PROMOTIONS", user_id, amount, "ADMIN_ADJUSTMENT", reference=f"admin:{u.id}", note=body.reason)
        else:
            _user_to_system(db, user_id, "PROMOTIONS", -amount, "ADMIN_ADJUSTMENT", reference=f"admin:{u.id}", note=body.reason)
        after = _q(_raw_user_wallet(db, user_id).balance_micros)
        _audit(db, u.id, "USER_WALLET_ADJUSTMENT", target_user_id=user_id, before={"balance_q": before}, after={"balance_q": after, "adjustment_q": body.amount_q}, reason=body.reason)
        db.commit()
        return {"ok": True, "balance_q": after}

    @router.put("/admin/subscriptions/{lot_id}")
    def admin_edit_subscription(lot_id: int, body: UserPackageEditIn, u: User = Depends(require_master), db: Session = Depends(get_db)):
        lot = db.get(QSubscriptionLot, lot_id)
        if not lot:
            raise HTTPException(404, "Subscription package not found")
        _accrue_user_packages(db, lot.user_id)
        before = _package_snapshot(lot, db)
        ov = _subscription_override(db, lot.id, True)
        rule = _package_rule(db, lot.package_code)

        if body.clear_daily_override:
            ov.daily_rate_override = False
            lot.daily_rate_bps = rule.daily_rate_bps
        elif body.daily_rate_percent is not None:
            lot.daily_rate_bps = int(round(body.daily_rate_percent * 100))
            ov.daily_rate_override = True

        if body.clear_cap_override:
            ov.cap_percent_override = False
            requested_cap = int(lot.purchase_usd_micros * rule.cap_percent / 100)
            lot.cap_usd_micros = requested_cap
        elif body.cap_percent is not None:
            requested_cap = int(lot.purchase_usd_micros * body.cap_percent / 100)
            lot.cap_usd_micros = requested_cap
            ov.cap_percent_override = True

        if body.status is not None:
            new_status = body.status.strip().upper()
            allowed = {"ACTIVE", "PAUSED", "STOPPED", "ADMIN_CANCELLED"}
            if new_status not in allowed:
                raise HTTPException(422, "Status must be ACTIVE, PAUSED, STOPPED or ADMIN_CANCELLED")
            if new_status == "ACTIVE":
                if _now() >= lot.expires_at:
                    raise HTTPException(409, "Expired package cannot be resumed")
                if lot.accrued_usd_micros >= lot.cap_usd_micros:
                    raise HTTPException(409, "Package has already reached its configured cap")
            lot.status = new_status

        if lot.status == "ACTIVE" and lot.accrued_usd_micros >= lot.cap_usd_micros:
            lot.status = "CAP_REACHED"
        ov.updated_at = _now()
        after = _package_snapshot(lot, db)
        _audit(db, u.id, "USER_PACKAGE_EDIT", target_user_id=lot.user_id, lot_id=lot.id, before=before, after=after, reason=body.reason)
        db.commit()
        return _subscription_json(lot, _config(db), db)

    @router.get("/admin/audit")
    def admin_audit(limit: int = 200, u: User = Depends(require_admin), db: Session = Depends(get_db)):
        rows = db.scalars(select(QAdminAuditLog).order_by(QAdminAuditLog.id.desc()).limit(max(1, min(limit, 500)))).all()
        return [{
            "id": x.id, "admin": _user_json_brief(db, x.admin_user_id), "action": x.action,
            "target_user": _user_json_brief(db, x.target_user_id), "subscription_lot_id": x.subscription_lot_id,
            "before": json.loads(x.before_json or "{}"), "after": json.loads(x.after_json or "{}"),
            "reason": x.reason, "created_at": x.created_at.isoformat(),
        } for x in rows]

    @router.get("/admin/payment-wallet-matrix")
    def admin_payment_wallet_matrix(u: User = Depends(require_admin), db: Session = Depends(get_db)):
        items = []
        for code, plan in PACKAGE_PLANS.items():
            for network in ("TRC20", "BEP20"):
                row = db.scalar(select(QPaymentWallet).where(
                    QPaymentWallet.package_code == code, QPaymentWallet.network == network, QPaymentWallet.active.is_(True)
                ).order_by(QPaymentWallet.id.desc()).limit(1))
                items.append({
                    "slot_key": f"{code}:{network}", "package_code": code, "package_name": plan["name"],
                    "price_usd": plan["price_usd"], "network": network,
                    "wallet": _payment_wallet_json(row) if row else None,
                })
        return items

    @router.put("/admin/payment-wallet-matrix/{package_code}/{network}")
    def admin_set_payment_wallet_slot(package_code: str, network: str, body: AdminPaymentWalletSlotIn, u: User = Depends(require_admin), db: Session = Depends(get_db)):
        code = package_code.strip().upper(); net = network.strip().upper()
        if code not in PACKAGE_PLANS:
            raise HTTPException(404, "Package not found")
        _validate_payment_address(net, body.address.strip())
        previous = db.scalars(select(QPaymentWallet).where(QPaymentWallet.package_code == code, QPaymentWallet.network == net, QPaymentWallet.active.is_(True))).all()
        before = [_payment_wallet_json(x) for x in previous]
        for x in previous:
            x.active = False; x.updated_at = _now()
        row = QPaymentWallet(network=net, package_code=code, label=body.label.strip() or f"{PACKAGE_PLANS[code]['name']} {net}", address=body.address.strip(), active=body.active)
        db.add(row); db.flush()
        _audit(db, u.id, "PAYMENT_WALLET_SLOT_UPDATE", before={"wallets": before}, after=_payment_wallet_json(row), reason=f"{code} {net} receiving wallet")
        db.commit(); db.refresh(row)
        return _payment_wallet_json(row)

    @router.get("/admin/payment-wallets")
    def admin_payment_wallets(u: User = Depends(require_admin), db: Session = Depends(get_db)):
        rows = db.scalars(select(QPaymentWallet).order_by(QPaymentWallet.id.desc())).all()
        return [_payment_wallet_json(x) for x in rows]

    @router.post("/admin/payment-wallets")
    def admin_add_payment_wallet(body: AdminPaymentWalletIn, u: User = Depends(require_admin), db: Session = Depends(get_db)):
        network = body.network.strip().upper()
        _validate_payment_address(network, body.address.strip())
        code = body.package_code.strip().upper() if body.package_code else None
        if not code or code not in PACKAGE_PLANS:
            raise HTTPException(422, "Choose one of the five subscription packages")
        for old_wallet in db.scalars(select(QPaymentWallet).where(
            QPaymentWallet.package_code == code, QPaymentWallet.network == network, QPaymentWallet.active.is_(True)
        )).all():
            old_wallet.active = False; old_wallet.updated_at = _now()
        row = QPaymentWallet(
            network=network, package_code=code, label=body.label.strip(),
            address=body.address.strip(), active=body.active,
        )
        db.add(row); db.commit(); db.refresh(row)
        return _payment_wallet_json(row)

    @router.put("/admin/payment-wallets/{wallet_id}")
    def admin_update_payment_wallet(wallet_id: int, body: AdminPaymentWalletIn, u: User = Depends(require_admin), db: Session = Depends(get_db)):
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
    async def admin_upload_qr(wallet_id: int, file: UploadFile = File(...), u: User = Depends(require_admin), db: Session = Depends(get_db)):
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
        rule = _package_rule(db, row.package_code)
        now = _now()
        lot = QSubscriptionLot(
            user_id=row.user_id, payment_order_id=row.id, package_code=row.package_code,
            purchase_usd_micros=plan["price_usd"] * USD_MICROS,
            daily_rate_bps=rule.daily_rate_bps,
            cap_usd_micros=int(plan["price_usd"] * USD_MICROS * rule.cap_percent / 100),
            accrued_usd_micros=0, accrued_q_micros=0,
            started_at=now, expires_at=now + timedelta(days=365),
            last_accrual_date=now.date(), status="ACTIVE",
        )
        row.status = "APPROVED"; row.reviewed_at = now; row.reviewed_by = u.id
        db.add(lot)
        db.flush()
        _award_subscription_referral(db, row)
        db.commit(); db.refresh(lot)
        return {"ok": True, "payment": _payment_order_json(db, row), "subscription": _subscription_json(lot, _config(db), db)}

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
            "from_system": x.from_system_key, "from_user": x.from_user_id, "from_user_info": _user_json_brief(db, x.from_user_id),
            "to_system": x.to_system_key, "to_user": x.to_user_id, "to_user_info": _user_json_brief(db, x.to_user_id),
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
