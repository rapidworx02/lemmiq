"""LEMMIQ V2.10.4 Q Predict Q-wallet integration contract.

This file deliberately does NOT guess your existing Q wallet table names. Wire these callbacks to the
current V2.8 Q Economy service so Q Predict uses the SAME authoritative Q balance and q_ledger.

Legacy Predict Credits must not be converted 1:1 into Q. Keep old PC positions as historical test data.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Awaitable, Callable, Protocol


@dataclass
class QPredictControls:
    enabled: bool = False
    minimum_stake_q: Decimal = Decimal("1")
    maximum_stake_q: Decimal = Decimal("100")
    per_market_limit_q: Decimal = Decimal("250")
    daily_exposure_limit_q: Decimal = Decimal("500")
    weekly_exposure_limit_q: Decimal = Decimal("1500")
    fee_percent: Decimal = Decimal("5")


class QWalletPort(Protocol):
    async def balance(self, user_id: int) -> Decimal: ...
    async def debit(self, user_id: int, amount_q: Decimal, kind: str, reference: str, note: str) -> str: ...
    async def credit(self, user_id: int, amount_q: Decimal, kind: str, reference: str, note: str) -> str: ...


class QPredictRepositoryPort(Protocol):
    async def market(self, market_id: int): ...
    async def user_market_exposure(self, user_id: int, market_id: int) -> Decimal: ...
    async def user_daily_exposure(self, user_id: int) -> Decimal: ...
    async def user_weekly_exposure(self, user_id: int) -> Decimal: ...
    async def add_position(self, user_id: int, market_id: int, outcome: str, stake_q: Decimal): ...
    async def recalc_market_pools(self, market_id: int): ...


async def stake_q(
    *, user_id: int, market_id: int, outcome: str, amount_q: Decimal,
    wallet: QWalletPort, repo: QPredictRepositoryPort, controls: QPredictControls,
):
    if not controls.enabled:
        raise ValueError("Q Predict Q staking is disabled")
    side = outcome.strip().upper()
    if side not in {"YES", "NO"}:
        raise ValueError("Outcome must be YES or NO")
    if amount_q < controls.minimum_stake_q:
        raise ValueError(f"Minimum stake is {controls.minimum_stake_q} Q")
    if amount_q > controls.maximum_stake_q:
        raise ValueError(f"Maximum stake is {controls.maximum_stake_q} Q")
    market = await repo.market(market_id)
    if getattr(market, "status", "") != "LIVE":
        raise ValueError("Market is not live")
    if await repo.user_market_exposure(user_id, market_id) + amount_q > controls.per_market_limit_q:
        raise ValueError("Per-market Q limit exceeded")
    if await repo.user_daily_exposure(user_id) + amount_q > controls.daily_exposure_limit_q:
        raise ValueError("Daily Q Predict limit exceeded")
    if await repo.user_weekly_exposure(user_id) + amount_q > controls.weekly_exposure_limit_q:
        raise ValueError("Weekly Q Predict limit exceeded")
    if await wallet.balance(user_id) < amount_q:
        raise ValueError("Insufficient Q balance")

    ref = f"q_predict_market:{market_id}"
    # Debit and position insert should be inside ONE existing backend DB transaction when you wire this.
    await wallet.debit(user_id, amount_q, "Q_PREDICT_STAKE", ref, f"Q Predict {side} stake")
    try:
        await repo.add_position(user_id, market_id, side, amount_q)
        return await repo.recalc_market_pools(market_id)
    except Exception:
        await wallet.credit(user_id, amount_q, "Q_PREDICT_REFUND", ref, "Q Predict stake rollback")
        raise


async def settle_winner_q(
    *, market_id: int, user_id: int, original_stake_q: Decimal, gross_profit_q: Decimal,
    wallet: QWalletPort, fee_percent: Decimal,
):
    fee_q = (gross_profit_q * fee_percent / Decimal("100")).quantize(Decimal("0.000001"))
    payout_q = original_stake_q + gross_profit_q - fee_q
    ref = f"q_predict_market:{market_id}"
    await wallet.credit(user_id, payout_q, "Q_PREDICT_PAYOUT", ref, "Q Predict winning payout")
    return {"payout_q": payout_q, "fee_q": fee_q}


async def refund_void_q(*, market_id: int, user_id: int, stake_q: Decimal, wallet: QWalletPort):
    ref = f"q_predict_market:{market_id}"
    await wallet.credit(user_id, stake_q, "Q_PREDICT_REFUND", ref, "Q Predict VOID refund")
