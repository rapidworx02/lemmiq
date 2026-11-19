"""LEMMIQ v2.13.13 — auditable cancellation of unpaid Q Predict purchase orders.

Adds restricted cancellation endpoints; never credits Q or moves USDT and never
allows an order with a transaction hash, an already submitted order, or an
approved order to be cancelled through this route.
"""
from datetime import timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from .models import User
from .v21310_predict_q import Order, _admin, _audit, _order_json, now


class CancelUnpaidIn(BaseModel):
    reason: str = Field(min_length=8, max_length=240)


class CancelExpiredIn(BaseModel):
    reason: str = Field(default='Expired quote: no transaction hash submitted', min_length=8, max_length=240)


def _check_can_cancel(order: Order | None) -> None:
    if order is None:
        raise HTTPException(404, 'Purchase order not found')
    if order.status != 'CREATED' or (order.tx_hash or '').strip():
        raise HTTPException(409, 'Only CREATED unpaid orders without transaction proof can be cancelled. Submitted payments require separate review.')


def _cancel_order(db: Session, order: Order, actor_id: int, reason: str) -> None:
    _check_can_cancel(order)
    order.status = 'CANCELLED'
    order.notes = reason.strip()
    order.reviewer_id = actor_id
    order.updated_at = now()
    _audit(db, actor_id, 'CANCEL_UNPAID_BUY', {'order_id': order.id, 'order_code': order.code, 'reason': order.notes, 'unsubmitted': True})


def register_v21313_predict_orders(app, current_user, get_db):
    router = APIRouter(prefix='/v21313/predict', tags=['Q Predict unpaid order cancellation'])

    @router.post('/admin/orders/{order_id}/cancel')
    def cancel_unpaid(order_id: int, body: CancelUnpaidIn,
                      u: User = Depends(current_user), db: Session = Depends(get_db)):
        _admin(db, u)  # Master Admin only; checked on the server
        order = db.scalar(select(Order).where(Order.id == order_id).with_for_update())
        _check_can_cancel(order)
        _cancel_order(db, order, u.id, body.reason)
        db.commit()
        return {'cancelled': True, 'order': _order_json(order)}

    @router.post('/admin/orders/cancel-expired')
    def cancel_expired(body: CancelExpiredIn,
                       u: User = Depends(current_user), db: Session = Depends(get_db)):
        _admin(db, u)
        # Only unsubmitted, expired CREATED orders. PENDING and APPROVED remain untouched.
        expired = db.scalars(
            select(Order).where(
                Order.status == 'CREATED',
                Order.tx_hash.is_(None),
                Order.expires_at < now(),
            ).order_by(Order.id.asc()).limit(100).with_for_update(skip_locked=True)
        ).all()
        cancelled_ids = []
        for order in expired:
            _cancel_order(db, order, u.id, body.reason)
            cancelled_ids.append(order.id)
        db.commit()
        return {'cancelled_count': len(cancelled_ids), 'cancelled_order_ids': cancelled_ids,
                'note': 'Up to 100 expired orders per request; run again if more remain.'}

    app.include_router(router)
