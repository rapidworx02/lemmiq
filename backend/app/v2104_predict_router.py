"""Compatibility routes for V2.10.4 Android clients.

V2.10.5 makes /v29/predict the canonical Q-wallet implementation, but older
V2.10.4 APKs already post amount_q to /v2104/predict/.../stake. Keep that route
working against the same authoritative Q wallet and market transaction.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .models import User
from .v28 import _raw_user_wallet
from .v29 import PredictMarket, _market_json, _q, _q_micros, _stake_q


class StakeBody(BaseModel):
    outcome: str = Field(pattern="^(YES|NO|yes|no)$")
    amount_q: float = Field(gt=0)


def register_v2104_predict_compat(app, current_user, get_db):
    router = APIRouter(prefix="/v2104/predict", tags=["LEMMIQ V2.10.4 compatibility"])

    @router.get("/status")
    def status():
        return {"version": "2.10.5", "uses_q": True, "canonical_api": "/v29/predict"}

    @router.post("/markets/{market_id}/stake")
    def stake(market_id: int, body: StakeBody, u: User = Depends(current_user), db: Session = Depends(get_db)):
        m = db.get(PredictMarket, market_id)
        if not m:
            raise HTTPException(404, "Prediction market not found")
        _stake_q(db, u, m, body.outcome, _q_micros(body.amount_q))
        db.commit(); db.refresh(m)
        balance_q = _q(_raw_user_wallet(db, u.id).balance_micros)
        return {"market": _market_json(db, m, u.id), "wallet_balance_q": balance_q}

    app.include_router(router)
