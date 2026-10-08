from __future__ import annotations

from decimal import Decimal
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from .v2104_q_predict_contract import QPredictControls, QWalletPort, QPredictRepositoryPort, stake_q

router = APIRouter(prefix="/v2104/predict", tags=["LEMMIQ V2.10.4 Q Predict"])

_wallet: Optional[QWalletPort] = None
_repo: Optional[QPredictRepositoryPort] = None
_controls = QPredictControls(enabled=False)
_get_user_id = None


def configure_q_predict(*, wallet: QWalletPort, repo: QPredictRepositoryPort, get_user_id, controls: QPredictControls | None = None):
    """Call once from your existing backend startup after adapting the current V2.8 Q wallet + V2.9 market repository."""
    global _wallet, _repo, _get_user_id, _controls
    _wallet = wallet
    _repo = repo
    _get_user_id = get_user_id
    if controls is not None:
        _controls = controls


class StakeBody(BaseModel):
    outcome: str = Field(pattern="^(YES|NO|yes|no)$")
    amount_q: Decimal = Field(gt=0)


@router.get("/status")
def status():
    return {
        "version": "2.10.4",
        "uses_q": True,
        "enabled": bool(_wallet and _repo and _get_user_id and _controls.enabled),
        "minimum_stake_q": str(_controls.minimum_stake_q),
        "maximum_stake_q": str(_controls.maximum_stake_q),
        "fee_percent": str(_controls.fee_percent),
        "legacy_pc_conversion": False,
    }


@router.post("/markets/{market_id}/stake")
async def stake(market_id: int, body: StakeBody, request: Request):
    if not (_wallet and _repo and _get_user_id):
        raise HTTPException(status_code=503, detail="Q Predict Q-wallet adapter is not wired on the backend yet")
    if not _controls.enabled:
        raise HTTPException(status_code=503, detail="Q Predict Q staking is disabled")
    user_id = await _get_user_id(request) if callable(_get_user_id) else None
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        market = await stake_q(
            user_id=int(user_id), market_id=market_id, outcome=body.outcome,
            amount_q=Decimal(body.amount_q), wallet=_wallet, repo=_repo, controls=_controls,
        )
        balance = await _wallet.balance(int(user_id))
        return {"market": market, "wallet_balance_q": float(balance)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
