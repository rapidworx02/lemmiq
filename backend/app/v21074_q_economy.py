"""LEMMIQ V2.10.7.4 — unified Q Economy controls.

This module adds the next Q Economy layer without replacing the stable V2.8/V2.9
routers:
- unified package earning-cap accounting for qualifying LEMMIQ rewards;
- Q + USDT package rebuy / upgrade;
- Q -> USDT withdrawal requests with manual admin settlement;
- weekly active-Q claim plumbing (admin amount defaults to 0 Q);
- read-only/admin reporting for earning cycles and outgoing USDT.

Withdrawal is deliberately OFF by default. AI feature charging remains controlled
by v2105_q_features and is also OFF by default.
"""
from __future__ import annotations

import csv
import io
import json
import secrets
from collections import defaultdict
from datetime import datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from .database import Base, SessionLocal, engine
from .models import User
from .admin_rbac import require_admin_access
from .v28 import (
    PACKAGE_PLANS, NETWORKS, Q_MICROS, USD_MICROS,
    QAdminRole, QEconomyConfig, QLedgerEntry, QPaymentOrder, QSubscriptionLot,
    QSystemWallet, QUserWallet,
    _audit, _config, _ledger, _now, _payment_order_json, _q, _raw_user_wallet,
    _shared_payment_wallet, _legacy_payment_wallet, _subscription_json,
    _system_to_system, _system_to_user, _user_json_brief, _user_to_system,
    _validate_payment_address,
)

ALL_PACKS = "ALL_PACKS"
QUALIFYING_REWARD_KIND_TO_SOURCE = {
    "BASIC_DAILY": "DAILY_ACTIVE",
    "WEEKLY_ACTIVE": "WEEKLY_ACTIVE",
    "SIGNUP_BONUS": "SIGNUP_WELCOME",
    "REFERRAL_REWARD": "REFERRAL",
    "REFERRAL_WELCOME": "SIGNUP_WELCOME",
    "REFERRAL_PACKAGE_REWARD": "REFERRAL",
    "PACKAGE_BONUS": "PACKAGE_BONUS",
}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _aware_dt(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


class QEconomyV21074Config(Base):
    __tablename__ = "q_economy_v21074_config"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    withdrawal_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    withdrawal_fee_bps: Mapped[int] = mapped_column(Integer, default=1000)  # fixed product default: 10%
    min_withdraw_usdt_micros: Mapped[int] = mapped_column(BigInteger, default=10 * USD_MICROS)
    rebuy_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    rebuy_same_max_bps: Mapped[int] = mapped_column(Integer, default=4000)
    upgrade_max_bps: Mapped[int] = mapped_column(Integer, default=5000)
    weekly_active_micros: Mapped[int] = mapped_column(BigInteger, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class QRewardCapEvent(Base):
    __tablename__ = "q_reward_cap_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    subscription_lot_id: Mapped[int | None] = mapped_column(ForeignKey("q_subscription_lots.id"), nullable=True, index=True)
    source: Mapped[str] = mapped_column(String(40), index=True)
    ledger_kind: Mapped[str] = mapped_column(String(60), index=True)
    q_micros: Mapped[int] = mapped_column(BigInteger, default=0)
    usd_micros: Mapped[int] = mapped_column(BigInteger, default=0)
    reference: Mapped[str] = mapped_column(String(160), default="")
    note: Mapped[str] = mapped_column(String(240), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class QWeeklyActiveClaim(Base):
    __tablename__ = "q_weekly_active_claims"
    __table_args__ = (UniqueConstraint("user_id", "week_key", name="uq_q_weekly_active_claim"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    week_key: Mapped[str] = mapped_column(String(12), index=True)
    amount_micros: Mapped[int] = mapped_column(BigInteger, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class QPackageRebuyOrder(Base):
    __tablename__ = "q_package_rebuy_orders"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    rebuy_code: Mapped[str] = mapped_column(String(48), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    source_lot_id: Mapped[int] = mapped_column(ForeignKey("q_subscription_lots.id"), index=True)
    payment_order_id: Mapped[int] = mapped_column(ForeignKey("q_payment_orders.id"), unique=True, index=True)
    target_package_code: Mapped[str] = mapped_column(String(32), index=True)
    action: Mapped[str] = mapped_column(String(16), index=True)  # REBUY / UPGRADE
    q_locked_micros: Mapped[int] = mapped_column(BigInteger)
    q_value_usd_micros: Mapped[int] = mapped_column(BigInteger)
    usdt_due_micros: Mapped[int] = mapped_column(BigInteger)
    q_reference_microusd: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(20), default="CREATED", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class QWithdrawalRequest(Base):
    __tablename__ = "q_withdrawal_requests"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_code: Mapped[str] = mapped_column(String(48), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    requested_q_micros: Mapped[int] = mapped_column(BigInteger)
    fee_q_micros: Mapped[int] = mapped_column(BigInteger)
    net_q_micros: Mapped[int] = mapped_column(BigInteger)
    q_reference_microusd: Mapped[int] = mapped_column(BigInteger)
    payout_usdt_micros: Mapped[int] = mapped_column(BigInteger)
    network: Mapped[str] = mapped_column(String(16), index=True)
    destination_address: Mapped[str] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(20), default="PENDING", index=True)
    admin_note: Mapped[str] = mapped_column(String(300), default="")
    tx_hash: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RebuyCreateIn(BaseModel):
    target_package_code: str
    network: str
    q_amount: float = Field(gt=0, le=100_000_000)


class WithdrawalCreateIn(BaseModel):
    amount_q: float = Field(gt=0, le=100_000_000)
    network: str
    destination_address: str = Field(min_length=20, max_length=160)


class AdminWithdrawalToggleIn(BaseModel):
    enabled: bool


class AdminWithdrawalNoteIn(BaseModel):
    note: str = Field(default="", max_length=300)


class AdminWithdrawalPaidIn(BaseModel):
    tx_hash: str = Field(min_length=8, max_length=160)
    note: str = Field(default="", max_length=300)


class AdminEconomyControlsIn(BaseModel):
    rebuy_enabled: bool | None = None
    rebuy_same_max_percent: float | None = Field(default=None, ge=0, le=95)
    upgrade_max_percent: float | None = Field(default=None, ge=0, le=95)
    weekly_active_q: float | None = Field(default=None, ge=0, le=1_000_000)


def _cfg(db: Session) -> QEconomyV21074Config:
    row = db.get(QEconomyV21074Config, 1)
    if not row:
        row = QEconomyV21074Config(id=1)
        db.add(row)
        db.flush()
    return row


def _micros_q(value: float) -> int:
    return int(round(float(value) * Q_MICROS))


def _usd_from_q_micros(q_micros: int, q_price_microusd: int) -> int:
    return int((int(q_micros) * int(q_price_microusd)) // Q_MICROS)


def _q_from_usd_micros(usd_micros: int, q_price_microusd: int) -> int:
    return int((int(usd_micros) * Q_MICROS) // max(1, int(q_price_microusd)))


def _current_active_cap_lot(db: Session, user_id: int) -> QSubscriptionLot | None:
    return db.scalar(
        select(QSubscriptionLot)
        .where(QSubscriptionLot.user_id == user_id, QSubscriptionLot.status == "ACTIVE")
        .order_by(QSubscriptionLot.started_at.desc(), QSubscriptionLot.id.desc())
        .limit(1)
    )


def capture_qualifying_reward(
    db: Session,
    user_id: int,
    q_micros: int,
    ledger_kind: str,
    *,
    reference: str = "",
    note: str = "",
) -> QRewardCapEvent | None:
    """Count a qualifying LEMMIQ-generated reward toward the current 200% cycle.

    The full reward is always credited first by the caller. If it crosses the
    cap, the full reward still counts and the package becomes COMPLETED.
    When no package is active, the event remains unassigned and is attached to
    the next package cycle.
    """
    source = QUALIFYING_REWARD_KIND_TO_SOURCE.get((ledger_kind or "").upper())
    if not source or q_micros <= 0:
        return None
    economy = _config(db)
    usd_micros = _usd_from_q_micros(q_micros, economy.q_price_microusd)
    lot = _current_active_cap_lot(db, user_id)
    now = utcnow()
    event = QRewardCapEvent(
        user_id=user_id,
        subscription_lot_id=lot.id if lot else None,
        source=source,
        ledger_kind=(ledger_kind or "")[:60],
        q_micros=q_micros,
        usd_micros=usd_micros,
        reference=(reference or "")[:160],
        note=(note or "")[:240],
        assigned_at=now if lot else None,
    )
    db.add(event)
    if lot:
        lot.accrued_q_micros += q_micros
        lot.accrued_usd_micros += usd_micros
        if lot.accrued_usd_micros >= lot.cap_usd_micros:
            lot.status = "COMPLETED"
    return event


def record_package_accrual_event(
    db: Session,
    lot: QSubscriptionLot,
    q_micros: int,
    usd_micros: int,
    *,
    reference: str = "",
    note: str = "",
) -> None:
    """Log package accrual already added to the lot by the stable V2.8 engine."""
    if q_micros <= 0 and usd_micros <= 0:
        return
    db.add(QRewardCapEvent(
        user_id=lot.user_id,
        subscription_lot_id=lot.id,
        source="PACKAGE_ACCRUAL",
        ledger_kind="PACKAGE_ACCRUAL",
        q_micros=max(0, q_micros),
        usd_micros=max(0, usd_micros),
        reference=(reference or "")[:160],
        note=(note or "")[:240],
        assigned_at=utcnow(),
    ))


def attach_unassigned_rewards(db: Session, user_id: int, lot: QSubscriptionLot) -> int:
    """Attach rewards earned while no cycle was active to the newly activated cycle."""
    rows = db.scalars(
        select(QRewardCapEvent)
        .where(QRewardCapEvent.user_id == user_id, QRewardCapEvent.subscription_lot_id.is_(None))
        .order_by(QRewardCapEvent.id)
    ).all()
    if not rows:
        return 0
    now = utcnow()
    for event in rows:
        event.subscription_lot_id = lot.id
        event.assigned_at = now
        lot.accrued_q_micros += event.q_micros
        lot.accrued_usd_micros += event.usd_micros
    if lot.accrued_usd_micros >= lot.cap_usd_micros:
        lot.status = "COMPLETED"
    return len(rows)


def _cap_breakdown(db: Session, lot: QSubscriptionLot) -> dict:
    rows = db.scalars(select(QRewardCapEvent).where(QRewardCapEvent.subscription_lot_id == lot.id)).all()
    by_source: dict[str, dict[str, int]] = defaultdict(lambda: {"q_micros": 0, "usd_micros": 0})
    for row in rows:
        by_source[row.source]["q_micros"] += row.q_micros
        by_source[row.source]["usd_micros"] += row.usd_micros
    return {
        key: {
            "q": round(value["q_micros"] / Q_MICROS, 6),
            "usd_reference": round(value["usd_micros"] / USD_MICROS, 6),
        }
        for key, value in sorted(by_source.items())
    }


def _cycle_json(db: Session, lot: QSubscriptionLot) -> dict:
    cfg = _config(db)
    base = _subscription_json(lot, cfg, db)
    base["earning_cap_used_usd"] = round(lot.accrued_usd_micros / USD_MICROS, 6)
    base["earning_cap_usd"] = round(lot.cap_usd_micros / USD_MICROS, 6)
    base["earning_cap_remaining_usd"] = round(max(0, lot.cap_usd_micros - lot.accrued_usd_micros) / USD_MICROS, 6)
    base["earning_cap_breakdown"] = _cap_breakdown(db, lot)
    base["status"] = "COMPLETED" if lot.status == "CAP_REACHED" else lot.status
    return base


def _rebuy_json(db: Session, row: QPackageRebuyOrder) -> dict:
    payment = db.get(QPaymentOrder, row.payment_order_id)
    return {
        "id": row.id,
        "rebuy_code": row.rebuy_code,
        "action": row.action,
        "target_package_code": row.target_package_code,
        "target_package_name": PACKAGE_PLANS.get(row.target_package_code, {}).get("name", row.target_package_code),
        "source_lot_id": row.source_lot_id,
        "q_locked": round(row.q_locked_micros / Q_MICROS, 6),
        "q_value_usd": round(row.q_value_usd_micros / USD_MICROS, 6),
        "usdt_due": round(row.usdt_due_micros / USD_MICROS, 6),
        "q_reference_usd": row.q_reference_microusd / USD_MICROS,
        "status": row.status,
        "payment": _payment_order_json(db, payment) if payment else None,
        "created_at": row.created_at.isoformat(),
        "finalized_at": row.finalized_at.isoformat() if row.finalized_at else None,
    }


def rebuy_submit_allowed(db: Session, payment_order_id: int) -> bool:
    row = db.scalar(select(QPackageRebuyOrder).where(QPackageRebuyOrder.payment_order_id == payment_order_id))
    if not row:
        return True
    return row.status in {"CREATED", "PENDING"}


def finalize_rebuy_on_payment_approval(db: Session, payment: QPaymentOrder, new_lot: QSubscriptionLot) -> QPackageRebuyOrder | None:
    row = db.scalar(select(QPackageRebuyOrder).where(QPackageRebuyOrder.payment_order_id == payment.id))
    if row and row.status not in {"ACTIVATED", "CANCELLED", "REJECTED"}:
        _system_to_system(
            db, "REBUY_RESERVE", "PROFIT", row.q_locked_micros,
            "PACKAGE_REBUY_Q_DEBIT", reference=row.rebuy_code,
            note=f"{row.action} {row.target_package_code}; Q portion settled",
        )
        _ledger(
            db, "PACKAGE_REBUY_USDT", 0, to_user=row.user_id,
            reference=row.rebuy_code,
            note=f"{row.usdt_due_micros / USD_MICROS:.6f} USDT approved",
        )
        row.status = "ACTIVATED"
        row.finalized_at = utcnow()
    # Every new package cycle receives qualifying rewards that accumulated while
    # the user had no ACTIVE earning cycle.
    attach_unassigned_rewards(db, payment.user_id, new_lot)
    _ledger(
        db, "PACKAGE_ACTIVATED", 0, to_user=payment.user_id,
        reference=f"subscription:{new_lot.id}",
        note=f"{PACKAGE_PLANS.get(new_lot.package_code, {}).get('name', new_lot.package_code)} earning cycle activated",
    )
    return row


def finalize_rebuy_on_payment_reject(db: Session, payment: QPaymentOrder, reason: str = "") -> QPackageRebuyOrder | None:
    row = db.scalar(select(QPackageRebuyOrder).where(QPackageRebuyOrder.payment_order_id == payment.id))
    if not row or row.status in {"ACTIVATED", "CANCELLED", "REJECTED"}:
        return row
    _system_to_user(
        db, "REBUY_RESERVE", row.user_id, row.q_locked_micros,
        "PACKAGE_REBUY_Q_REFUND", reference=row.rebuy_code,
        note=reason or "Hybrid package payment rejected; locked Q released",
    )
    row.status = "REJECTED"
    row.finalized_at = utcnow()
    return row


def _withdrawal_json(db: Session, row: QWithdrawalRequest) -> dict:
    user = db.get(User, row.user_id)
    reviewer = db.get(User, row.reviewed_by) if row.reviewed_by else None
    return {
        "id": row.id,
        "request_id": row.request_code,
        "user": {"id": user.id, "username": user.username, "display_name": user.display_name} if user else None,
        "requested_q": round(row.requested_q_micros / Q_MICROS, 6),
        "fee_q": round(row.fee_q_micros / Q_MICROS, 6),
        "net_q": round(row.net_q_micros / Q_MICROS, 6),
        "q_reference_usd": row.q_reference_microusd / USD_MICROS,
        "payout_usdt": round(row.payout_usdt_micros / USD_MICROS, 6),
        "network": row.network,
        "destination_address": row.destination_address,
        "status": row.status,
        "requested_at": row.requested_at.isoformat(),
        "reviewed_at": row.reviewed_at.isoformat() if row.reviewed_at else None,
        "reviewer": {"id": reviewer.id, "username": reviewer.username, "display_name": reviewer.display_name} if reviewer else None,
        "paid_at": row.paid_at.isoformat() if row.paid_at else None,
        "tx_hash": row.tx_hash,
        "admin_note": row.admin_note,
    }


def _release_withdrawal(db: Session, row: QWithdrawalRequest, status: str, admin_id: int | None, note: str) -> None:
    if row.status in {"PAID", "REJECTED", "FAILED", "CANCELLED"}:
        raise HTTPException(409, "Withdrawal is already final")
    _system_to_user(
        db, "WITHDRAWAL_RESERVE", row.user_id, row.requested_q_micros,
        "Q_WITHDRAWAL_REFUND", reference=row.request_code,
        note=note or f"Withdrawal {status.lower()}; locked Q released",
    )
    row.status = status
    row.admin_note = note[:300]
    row.reviewed_at = utcnow()
    row.reviewed_by = admin_id


def _period_start(period: str) -> datetime | None:
    now = utcnow()
    p = (period or "ALL").upper()
    if p == "TODAY":
        return datetime.combine(now.date(), time.min, tzinfo=timezone.utc)
    if p == "WEEK":
        return now - timedelta(days=7)
    if p == "MONTH":
        return now - timedelta(days=30)
    if p == "YEAR":
        return now - timedelta(days=365)
    if p == "ALL":
        return None
    raise HTTPException(422, "Period must be TODAY, WEEK, MONTH, YEAR or ALL")


def register_v21074_q_economy(app, current_user, get_db):
    router = APIRouter(prefix="/v21074", tags=["LEMMIQ V2.10.7.4 Q Economy"])

    def require_section(section: str, required: str = "READ"):
        def dep(u: User = Depends(current_user), db: Session = Depends(get_db)):
            role = db.get(QAdminRole, u.id)
            if not role or not role.active:
                raise HTTPException(403, "Admin access required")
            require_admin_access(db, u.id, role.role, section, required)
            return u
        return dep

    @app.on_event("startup")
    def _v21074_startup():
        Base.metadata.create_all(bind=engine)
        db = SessionLocal()
        try:
            _cfg(db)
            for key, label in (
                ("WITHDRAWAL_RESERVE", "Withdrawal Reserve"),
                ("REBUY_RESERVE", "Package Rebuy Reserve"),
            ):
                if not db.get(QSystemWallet, key):
                    db.add(QSystemWallet(key=key, label=label, balance_micros=0))
            # Normalize the old cap label without changing any financial totals.
            for lot in db.scalars(select(QSubscriptionLot).where(QSubscriptionLot.status == "CAP_REACHED")).all():
                lot.status = "COMPLETED"
            # Preserve pre-update package accrual in the new breakdown.
            lots = db.scalars(select(QSubscriptionLot).where(QSubscriptionLot.accrued_usd_micros > 0)).all()
            for lot in lots:
                exists = db.scalar(
                    select(func.count()).select_from(QRewardCapEvent)
                    .where(QRewardCapEvent.subscription_lot_id == lot.id)
                ) or 0
                if not exists:
                    db.add(QRewardCapEvent(
                        user_id=lot.user_id, subscription_lot_id=lot.id,
                        source="PACKAGE_ACCRUAL", ledger_kind="LEGACY_PACKAGE_ACCRUAL",
                        q_micros=lot.accrued_q_micros, usd_micros=lot.accrued_usd_micros,
                        reference=f"subscription:{lot.id}",
                        note="Existing package accrual preserved at V2.10.7.4 upgrade",
                        assigned_at=utcnow(),
                    ))
            db.commit()
        finally:
            db.close()

    @router.get("/earning-cycles")
    def earning_cycles(u: User = Depends(current_user), db: Session = Depends(get_db)):
        from .v28 import _accrue_user_packages
        _accrue_user_packages(db, u.id)
        rows = db.scalars(
            select(QSubscriptionLot).where(QSubscriptionLot.user_id == u.id).order_by(QSubscriptionLot.id.desc())
        ).all()
        unassigned = db.scalars(
            select(QRewardCapEvent).where(
                QRewardCapEvent.user_id == u.id,
                QRewardCapEvent.subscription_lot_id.is_(None),
            ).order_by(QRewardCapEvent.id)
        ).all()
        db.commit()
        return {
            "cycles": [_cycle_json(db, x) for x in rows],
            "unassigned_rewards_q": round(sum(x.q_micros for x in unassigned) / Q_MICROS, 6),
            "unassigned_rewards_usd_reference": round(sum(x.usd_micros for x in unassigned) / USD_MICROS, 6),
            "qualifying_sources": sorted(set(QUALIFYING_REWARD_KIND_TO_SOURCE.values()) | {"PACKAGE_ACCRUAL"}),
        }

    @router.get("/weekly-active")
    def weekly_active_status(u: User = Depends(current_user), db: Session = Depends(get_db)):
        cfg = _cfg(db)
        iso = utcnow().date().isocalendar()
        week_key = f"{iso.year}-W{iso.week:02d}"
        claimed = bool(db.scalar(
            select(func.count()).select_from(QWeeklyActiveClaim)
            .where(QWeeklyActiveClaim.user_id == u.id, QWeeklyActiveClaim.week_key == week_key)
        ) or 0)
        return {
            "enabled": cfg.weekly_active_micros > 0,
            "weekly_q": round(cfg.weekly_active_micros / Q_MICROS, 6),
            "week_key": week_key,
            "claimed": claimed,
        }

    @router.post("/weekly-active/claim")
    def claim_weekly_active(u: User = Depends(current_user), db: Session = Depends(get_db)):
        cfg = _cfg(db)
        if cfg.weekly_active_micros <= 0:
            raise HTTPException(409, "Weekly active Q is not enabled")
        iso = utcnow().date().isocalendar()
        week_key = f"{iso.year}-W{iso.week:02d}"
        if db.scalar(select(func.count()).select_from(QWeeklyActiveClaim).where(
            QWeeklyActiveClaim.user_id == u.id, QWeeklyActiveClaim.week_key == week_key
        )):
            raise HTTPException(409, "Weekly active Q already claimed")
        _system_to_user(
            db, "USAGE_MINING", u.id, cfg.weekly_active_micros,
            "WEEKLY_ACTIVE", reference=week_key, note="Weekly LEMMIQ activity reward",
        )
        db.add(QWeeklyActiveClaim(user_id=u.id, week_key=week_key, amount_micros=cfg.weekly_active_micros))
        db.commit()
        return {"ok": True, "week_key": week_key, "amount_q": round(cfg.weekly_active_micros / Q_MICROS, 6)}

    @router.get("/packages/rebuy/options")
    def rebuy_options(u: User = Depends(current_user), db: Session = Depends(get_db)):
        cfg = _cfg(db)
        econ = _config(db)
        wallet = _raw_user_wallet(db, u.id)
        active = db.scalar(select(func.count()).select_from(QSubscriptionLot).where(
            QSubscriptionLot.user_id == u.id, QSubscriptionLot.status == "ACTIVE"
        )) or 0
        eligible = db.scalars(select(QSubscriptionLot).where(
            QSubscriptionLot.user_id == u.id,
            QSubscriptionLot.status.in_(["COMPLETED", "CAP_REACHED", "EXPIRED"])
        ).order_by(QSubscriptionLot.id.desc())).all()
        source = eligible[0] if eligible else None
        plans = []
        if source:
            source_price = PACKAGE_PLANS.get(source.package_code, {}).get("price_usd", 0)
            for code, plan in PACKAGE_PLANS.items():
                if plan["price_usd"] < source_price:
                    continue
                action = "REBUY" if code == source.package_code else "UPGRADE"
                pct = cfg.rebuy_same_max_bps if action == "REBUY" else cfg.upgrade_max_bps
                max_usd = plan["price_usd"] * pct / 10_000
                max_q = max_usd / max(econ.q_price_microusd / USD_MICROS, 0.000001)
                plans.append({
                    "package_code": code,
                    "name": plan["name"],
                    "price_usd": plan["price_usd"],
                    "action": action,
                    "max_q_percent": pct / 100,
                    "max_q_at_current_reference": round(max_q, 6),
                })
        return {
            "enabled": bool(cfg.rebuy_enabled),
            "can_rebuy": bool(cfg.rebuy_enabled and source and not active),
            "blocked_by_active_cycle": bool(active),
            "source_cycle": _cycle_json(db, source) if source else None,
            "wallet_balance_q": round(wallet.balance_micros / Q_MICROS, 6),
            "q_reference_usd": econ.q_price_microusd / USD_MICROS,
            "plans": plans,
            "networks": sorted(NETWORKS),
        }

    @router.post("/packages/rebuy/orders")
    def create_rebuy_order(body: RebuyCreateIn, u: User = Depends(current_user), db: Session = Depends(get_db)):
        cfg = _cfg(db)
        if not cfg.rebuy_enabled:
            raise HTTPException(409, "Q + USDT rebuy is currently disabled")
        active = db.scalar(select(func.count()).select_from(QSubscriptionLot).where(
            QSubscriptionLot.user_id == u.id, QSubscriptionLot.status == "ACTIVE"
        )) or 0
        if active:
            raise HTTPException(409, "Complete the current earning cycle before rebuying or upgrading")

        source = db.scalar(select(QSubscriptionLot).where(
            QSubscriptionLot.user_id == u.id,
            QSubscriptionLot.status.in_(["COMPLETED", "CAP_REACHED", "EXPIRED"])
        ).order_by(QSubscriptionLot.id.desc()).limit(1))
        if not source:
            raise HTTPException(409, "A completed or expired package is required before Q + USDT rebuy")

        code = body.target_package_code.strip().upper()
        network = body.network.strip().upper()
        if code not in PACKAGE_PLANS:
            raise HTTPException(422, "Unknown package")
        if network not in NETWORKS:
            raise HTTPException(422, "Network must be TRC20 or BEP20")
        source_price = PACKAGE_PLANS.get(source.package_code, {}).get("price_usd", 0)
        target_price = PACKAGE_PLANS[code]["price_usd"]
        if target_price < source_price:
            raise HTTPException(422, "Rebuy the same package or upgrade to a larger package")
        action = "REBUY" if code == source.package_code else "UPGRADE"
        max_bps = cfg.rebuy_same_max_bps if action == "REBUY" else cfg.upgrade_max_bps

        econ = _config(db)
        q_micros = _micros_q(body.q_amount)
        q_value_usd = _usd_from_q_micros(q_micros, econ.q_price_microusd)
        max_q_value_usd = int(target_price * USD_MICROS * max_bps / 10_000)
        if q_value_usd > max_q_value_usd:
            raise HTTPException(422, f"{action.title()} allows up to {max_bps / 100:.0f}% of the package price in Q")
        if q_value_usd <= 0:
            raise HTTPException(422, "Q amount is too small at the current reference rate")
        wallet = _raw_user_wallet(db, u.id)
        if wallet.balance_micros < q_micros:
            raise HTTPException(409, "Not enough Q in your wallet")

        payment_wallet = _shared_payment_wallet(db, network) or _legacy_payment_wallet(db, network, code)
        if not payment_wallet:
            raise HTTPException(409, f"No active {network} receiving wallet is configured")

        full_price_micros = target_price * USD_MICROS
        usdt_due = full_price_micros - q_value_usd
        if usdt_due <= 0:
            raise HTTPException(422, "A USDT portion is required for package rebuy")

        rebuy_code = f"QRB-{utcnow().strftime('%Y%m%d')}-{secrets.token_hex(4).upper()}"
        _user_to_system(
            db, u.id, "REBUY_RESERVE", q_micros,
            "PACKAGE_REBUY_Q_LOCK", reference=rebuy_code,
            note=f"{action} {code}; Q locked until USDT payment review",
        )
        payment = QPaymentOrder(
            order_code=f"LQ-{utcnow().strftime('%Y%m%d')}-{secrets.token_hex(4).upper()}",
            user_id=u.id, package_code=code, network=network, wallet_id=payment_wallet.id,
            expected_usdt_micros=usdt_due, status="CREATED",
            user_note=f"{action} with {q_micros / Q_MICROS:.6f} Q + USDT",
        )
        db.add(payment)
        db.flush()
        row = QPackageRebuyOrder(
            rebuy_code=rebuy_code, user_id=u.id, source_lot_id=source.id,
            payment_order_id=payment.id, target_package_code=code, action=action,
            q_locked_micros=q_micros, q_value_usd_micros=q_value_usd,
            usdt_due_micros=usdt_due, q_reference_microusd=econ.q_price_microusd,
            status="CREATED",
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return _rebuy_json(db, row)

    @router.get("/packages/rebuy/orders")
    def my_rebuy_orders(u: User = Depends(current_user), db: Session = Depends(get_db)):
        rows = db.scalars(select(QPackageRebuyOrder).where(
            QPackageRebuyOrder.user_id == u.id
        ).order_by(QPackageRebuyOrder.id.desc()).limit(100)).all()
        return [_rebuy_json(db, x) for x in rows]

    @router.post("/packages/rebuy/orders/{rebuy_id}/cancel")
    def cancel_rebuy_order(rebuy_id: int, u: User = Depends(current_user), db: Session = Depends(get_db)):
        row = db.get(QPackageRebuyOrder, rebuy_id)
        if not row or row.user_id != u.id:
            raise HTTPException(404, "Rebuy order not found")
        payment = db.get(QPaymentOrder, row.payment_order_id)
        if row.status not in {"CREATED", "PENDING"} or (payment and payment.status == "PENDING"):
            raise HTTPException(409, "Submitted payment orders must be reviewed by Admin")
        _system_to_user(
            db, "REBUY_RESERVE", u.id, row.q_locked_micros,
            "PACKAGE_REBUY_Q_REFUND", reference=row.rebuy_code,
            note="Hybrid package order cancelled; locked Q released",
        )
        row.status = "CANCELLED"
        row.finalized_at = utcnow()
        if payment:
            payment.status = "CANCELLED"
        db.commit()
        return {"ok": True}

    @router.get("/withdrawals/config")
    def withdrawal_config(u: User = Depends(current_user), db: Session = Depends(get_db)):
        cfg = _cfg(db)
        econ = _config(db)
        wallet = _raw_user_wallet(db, u.id)
        gross_min_q = _q_from_usd_micros(
            int(cfg.min_withdraw_usdt_micros * 10_000 / max(1, 10_000 - cfg.withdrawal_fee_bps)),
            econ.q_price_microusd,
        )
        return {
            "enabled": bool(cfg.withdrawal_enabled),
            "fee_percent": cfg.withdrawal_fee_bps / 100,
            "minimum_net_usdt": cfg.min_withdraw_usdt_micros / USD_MICROS,
            "minimum_gross_q_at_current_reference": round(gross_min_q / Q_MICROS, 6),
            "q_reference_usd": econ.q_price_microusd / USD_MICROS,
            "wallet_balance_q": round(wallet.balance_micros / Q_MICROS, 6),
            "networks": sorted(NETWORKS),
        }

    @router.post("/withdrawals")
    def create_withdrawal(body: WithdrawalCreateIn, u: User = Depends(current_user), db: Session = Depends(get_db)):
        cfg = _cfg(db)
        if not cfg.withdrawal_enabled:
            raise HTTPException(409, "Q withdrawal is currently turned off")
        network = body.network.strip().upper()
        address = body.destination_address.strip()
        _validate_payment_address(network, address)
        gross = _micros_q(body.amount_q)
        if gross <= 0:
            raise HTTPException(422, "Withdrawal amount must be greater than 0 Q")
        fee = (gross * cfg.withdrawal_fee_bps) // 10_000
        net = gross - fee
        econ = _config(db)
        payout = _usd_from_q_micros(net, econ.q_price_microusd)
        if payout < cfg.min_withdraw_usdt_micros:
            raise HTTPException(
                422,
                f"Minimum final withdrawal payout is {cfg.min_withdraw_usdt_micros / USD_MICROS:.2f} USDT",
            )
        wallet = _raw_user_wallet(db, u.id)
        if wallet.balance_micros < gross:
            raise HTTPException(409, "Not enough Q in your wallet")
        code = f"QW-{utcnow().strftime('%Y%m%d')}-{secrets.token_hex(4).upper()}"
        _user_to_system(
            db, u.id, "WITHDRAWAL_RESERVE", gross,
            "Q_WITHDRAWAL_LOCK", reference=code,
            note=f"{fee / Q_MICROS:.6f} Q fee; {payout / USD_MICROS:.6f} USDT quoted",
        )
        row = QWithdrawalRequest(
            request_code=code, user_id=u.id, requested_q_micros=gross,
            fee_q_micros=fee, net_q_micros=net,
            q_reference_microusd=econ.q_price_microusd,
            payout_usdt_micros=payout, network=network,
            destination_address=address, status="PENDING",
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return _withdrawal_json(db, row)

    @router.get("/withdrawals")
    def my_withdrawals(u: User = Depends(current_user), db: Session = Depends(get_db)):
        rows = db.scalars(select(QWithdrawalRequest).where(
            QWithdrawalRequest.user_id == u.id
        ).order_by(QWithdrawalRequest.id.desc()).limit(100)).all()
        return [_withdrawal_json(db, x) for x in rows]

    @router.post("/withdrawals/{withdrawal_id}/cancel")
    def cancel_withdrawal(withdrawal_id: int, u: User = Depends(current_user), db: Session = Depends(get_db)):
        row = db.get(QWithdrawalRequest, withdrawal_id)
        if not row or row.user_id != u.id:
            raise HTTPException(404, "Withdrawal request not found")
        if row.status != "PENDING":
            raise HTTPException(409, "Only a pending withdrawal can be cancelled")
        _release_withdrawal(db, row, "CANCELLED", None, "Cancelled by user")
        db.commit()
        return _withdrawal_json(db, row)

    @router.get("/admin/withdrawals/settings")
    def admin_withdrawal_settings(_u: User = Depends(require_section("PAYMENTS", "READ")), db: Session = Depends(get_db)):
        cfg = _cfg(db)
        return {
            "withdrawal_enabled": bool(cfg.withdrawal_enabled),
            "fee_percent": cfg.withdrawal_fee_bps / 100,
            "minimum_net_usdt": cfg.min_withdraw_usdt_micros / USD_MICROS,
        }

    @router.put("/admin/withdrawals/settings")
    def admin_withdrawal_toggle(body: AdminWithdrawalToggleIn, u: User = Depends(require_section("PAYMENTS", "FULL")), db: Session = Depends(get_db)):
        cfg = _cfg(db)
        before = {"withdrawal_enabled": bool(cfg.withdrawal_enabled)}
        cfg.withdrawal_enabled = bool(body.enabled)
        cfg.updated_at = utcnow()
        _audit(
            db, u.id, "Q_WITHDRAWAL_SWITCH",
            before=before, after={"withdrawal_enabled": cfg.withdrawal_enabled},
            reason="Global Q withdrawal switch",
        )
        db.commit()
        return {"withdrawal_enabled": cfg.withdrawal_enabled}

    @router.get("/admin/withdrawals")
    def admin_withdrawals(
        period: str = "ALL", status: str = "", network: str = "", username: str = "",
        _u: User = Depends(require_section("PAYMENTS", "READ")), db: Session = Depends(get_db),
    ):
        stmt = select(QWithdrawalRequest)
        start = _period_start(period)
        if start:
            stmt = stmt.where(QWithdrawalRequest.requested_at >= start)
        if status.strip():
            stmt = stmt.where(QWithdrawalRequest.status == status.strip().upper())
        if network.strip():
            stmt = stmt.where(QWithdrawalRequest.network == network.strip().upper())
        if username.strip():
            uname = username.strip().lstrip("@").lower()
            user = db.scalar(select(User).where(func.lower(User.username) == uname))
            if not user:
                return []
            stmt = stmt.where(QWithdrawalRequest.user_id == user.id)
        rows = db.scalars(stmt.order_by(QWithdrawalRequest.id.desc()).limit(500)).all()
        return [_withdrawal_json(db, x) for x in rows]

    def _admin_withdrawal_rows(db: Session, period: str = "ALL", status: str = "", network: str = "", username: str = ""):
        stmt = select(QWithdrawalRequest)
        start = _period_start(period)
        if start:
            stmt = stmt.where(QWithdrawalRequest.requested_at >= start)
        if status.strip():
            stmt = stmt.where(QWithdrawalRequest.status == status.strip().upper())
        if network.strip():
            stmt = stmt.where(QWithdrawalRequest.network == network.strip().upper())
        if username.strip():
            uname = username.strip().lstrip("@").lower()
            user = db.scalar(select(User).where(func.lower(User.username) == uname))
            if not user:
                return []
            stmt = stmt.where(QWithdrawalRequest.user_id == user.id)
        return db.scalars(stmt.order_by(QWithdrawalRequest.id.desc()).limit(5000)).all()

    @router.get("/admin/withdrawals/summary")
    def admin_withdrawal_summary(
        period: str = "ALL", status: str = "", network: str = "", username: str = "",
        _u: User = Depends(require_section("PAYMENTS", "READ")), db: Session = Depends(get_db),
    ):
        rows = _admin_withdrawal_rows(db, period, status, network, username)
        today_start = datetime.combine(utcnow().date(), time.min, tzinfo=timezone.utc)
        pending = [x for x in rows if x.status in {"PENDING", "APPROVED"}]
        paid = [x for x in rows if x.status == "PAID"]
        paid_today = [x for x in paid if _aware_dt(x.paid_at or x.reviewed_at or x.requested_at) >= today_start]
        return {
            "pending_requests": len(pending),
            "pending_usdt_value": round(sum(x.payout_usdt_micros for x in pending) / USD_MICROS, 6),
            "paid_today_usdt": round(sum(x.payout_usdt_micros for x in paid_today) / USD_MICROS, 6),
            "paid_today_count": len(paid_today),
            "fees_collected_q": round(sum(x.fee_q_micros for x in paid) / Q_MICROS, 6),
            "rejected_failed": sum(1 for x in rows if x.status in {"REJECTED", "FAILED", "CANCELLED"}),
            "gross_q_requested": round(sum(x.requested_q_micros for x in rows) / Q_MICROS, 6),
            "fee_q": round(sum(x.fee_q_micros for x in paid) / Q_MICROS, 6),
            "net_q_redeemed": round(sum(x.net_q_micros for x in paid) / Q_MICROS, 6),
            "usdt_sent": round(sum(x.payout_usdt_micros for x in paid) / USD_MICROS, 6),
        }

    @router.get("/admin/withdrawals/export.csv")
    def admin_withdrawal_export(
        period: str = "ALL", status: str = "", network: str = "", username: str = "",
        _u: User = Depends(require_section("PAYMENTS", "READ")), db: Session = Depends(get_db),
    ):
        rows = _admin_withdrawal_rows(db, period, status, network, username)
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow([
            "request_id", "username", "display_name", "requested_q", "fee_q", "net_q",
            "q_reference_usd", "payout_usdt", "network", "destination_wallet", "status",
            "requested_at", "reviewer", "reviewed_at", "paid_at", "transaction_hash", "admin_note",
        ])
        for row in rows:
            item = _withdrawal_json(db, row)
            user = item.get("user") or {}
            reviewer = item.get("reviewer") or {}
            writer.writerow([
                item["request_id"], user.get("username", ""), user.get("display_name", ""),
                item["requested_q"], item["fee_q"], item["net_q"], item["q_reference_usd"],
                item["payout_usdt"], item["network"], item["destination_address"], item["status"],
                item["requested_at"], reviewer.get("username", ""), item["reviewed_at"], item["paid_at"],
                item["tx_hash"] or "", item["admin_note"] or "",
            ])
        return StreamingResponse(
            iter([buf.getvalue()]), media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="lemmiq-outgoing-usdt.csv"'},
        )

    @router.post("/admin/withdrawals/{withdrawal_id}/approve")
    def admin_approve_withdrawal(withdrawal_id: int, u: User = Depends(require_section("PAYMENTS", "WRITE")), db: Session = Depends(get_db)):
        row = db.get(QWithdrawalRequest, withdrawal_id)
        if not row:
            raise HTTPException(404, "Withdrawal request not found")
        if row.status != "PENDING":
            raise HTTPException(409, "Only pending withdrawals can be approved")
        row.status = "APPROVED"
        row.reviewed_at = utcnow()
        row.reviewed_by = u.id
        _audit(db, u.id, "Q_WITHDRAWAL_APPROVE", target_user_id=row.user_id, before={"status": "PENDING"}, after={"status": "APPROVED"}, reason=row.request_code)
        db.commit()
        return _withdrawal_json(db, row)

    @router.post("/admin/withdrawals/{withdrawal_id}/reject")
    def admin_reject_withdrawal(withdrawal_id: int, body: AdminWithdrawalNoteIn, u: User = Depends(require_section("PAYMENTS", "WRITE")), db: Session = Depends(get_db)):
        row = db.get(QWithdrawalRequest, withdrawal_id)
        if not row:
            raise HTTPException(404, "Withdrawal request not found")
        previous = row.status
        _release_withdrawal(db, row, "REJECTED", u.id, body.note or "Rejected by Admin")
        _audit(db, u.id, "Q_WITHDRAWAL_REJECT", target_user_id=row.user_id, before={"status": previous}, after={"status": "REJECTED"}, reason=body.note)
        db.commit()
        return _withdrawal_json(db, row)

    @router.post("/admin/withdrawals/{withdrawal_id}/failed")
    def admin_fail_withdrawal(withdrawal_id: int, body: AdminWithdrawalNoteIn, u: User = Depends(require_section("PAYMENTS", "WRITE")), db: Session = Depends(get_db)):
        row = db.get(QWithdrawalRequest, withdrawal_id)
        if not row:
            raise HTTPException(404, "Withdrawal request not found")
        previous = row.status
        _release_withdrawal(db, row, "FAILED", u.id, body.note or "USDT payout failed; locked Q released")
        _audit(db, u.id, "Q_WITHDRAWAL_FAILED", target_user_id=row.user_id, before={"status": previous}, after={"status": "FAILED"}, reason=body.note)
        db.commit()
        return _withdrawal_json(db, row)

    @router.post("/admin/withdrawals/{withdrawal_id}/mark-paid")
    def admin_mark_withdrawal_paid(withdrawal_id: int, body: AdminWithdrawalPaidIn, u: User = Depends(require_section("PAYMENTS", "WRITE")), db: Session = Depends(get_db)):
        row = db.get(QWithdrawalRequest, withdrawal_id)
        if not row:
            raise HTTPException(404, "Withdrawal request not found")
        if row.status != "APPROVED":
            raise HTTPException(409, "Approve the withdrawal before marking it paid")
        if db.scalar(select(func.count()).select_from(QWithdrawalRequest).where(
            QWithdrawalRequest.tx_hash == body.tx_hash.strip(), QWithdrawalRequest.id != row.id
        )):
            raise HTTPException(409, "This withdrawal transaction hash is already recorded")
        if row.fee_q_micros:
            _system_to_system(
                db, "WITHDRAWAL_RESERVE", "PROFIT", row.fee_q_micros,
                "Q_WITHDRAWAL_FEE", reference=row.request_code,
                note="10% Q withdrawal fee",
            )
        if row.net_q_micros:
            _system_to_system(
                db, "WITHDRAWAL_RESERVE", "LOCKED_RESERVE", row.net_q_micros,
                "Q_WITHDRAWAL_REDEEMED", reference=row.request_code,
                note=f"{row.payout_usdt_micros / USD_MICROS:.6f} USDT paid",
            )
        row.status = "PAID"
        row.tx_hash = body.tx_hash.strip()
        row.admin_note = body.note.strip()
        row.reviewed_at = row.reviewed_at or utcnow()
        row.reviewed_by = u.id
        row.paid_at = utcnow()
        _audit(
            db, u.id, "Q_WITHDRAWAL_PAID", target_user_id=row.user_id,
            before={"status": "APPROVED"},
            after={"status": "PAID", "tx_hash": row.tx_hash, "usdt": row.payout_usdt_micros / USD_MICROS},
            reason=body.note,
        )
        db.commit()
        return _withdrawal_json(db, row)

    @router.get("/admin/economy-controls")
    def admin_economy_controls(_u: User = Depends(require_section("PACKAGES_REFERRALS", "READ")), db: Session = Depends(get_db)):
        cfg = _cfg(db)
        return {
            "rebuy_enabled": bool(cfg.rebuy_enabled),
            "rebuy_same_max_percent": cfg.rebuy_same_max_bps / 100,
            "upgrade_max_percent": cfg.upgrade_max_bps / 100,
            "weekly_active_q": round(cfg.weekly_active_micros / Q_MICROS, 6),
        }

    @router.put("/admin/economy-controls")
    def admin_update_economy_controls(body: AdminEconomyControlsIn, u: User = Depends(require_section("PACKAGES_REFERRALS", "FULL")), db: Session = Depends(get_db)):
        cfg = _cfg(db)
        before = {
            "rebuy_enabled": cfg.rebuy_enabled,
            "rebuy_same_max_percent": cfg.rebuy_same_max_bps / 100,
            "upgrade_max_percent": cfg.upgrade_max_bps / 100,
            "weekly_active_q": cfg.weekly_active_micros / Q_MICROS,
        }
        if body.rebuy_enabled is not None:
            cfg.rebuy_enabled = bool(body.rebuy_enabled)
        if body.rebuy_same_max_percent is not None:
            cfg.rebuy_same_max_bps = int(round(body.rebuy_same_max_percent * 100))
        if body.upgrade_max_percent is not None:
            cfg.upgrade_max_bps = int(round(body.upgrade_max_percent * 100))
        if body.weekly_active_q is not None:
            cfg.weekly_active_micros = _micros_q(body.weekly_active_q)
        cfg.updated_at = utcnow()
        after = {
            "rebuy_enabled": cfg.rebuy_enabled,
            "rebuy_same_max_percent": cfg.rebuy_same_max_bps / 100,
            "upgrade_max_percent": cfg.upgrade_max_bps / 100,
            "weekly_active_q": cfg.weekly_active_micros / Q_MICROS,
        }
        _audit(db, u.id, "Q_ECONOMY_21074_SETTINGS", before=before, after=after, reason="Earning/rebuy settings")
        db.commit()
        return after

    app.include_router(router)
