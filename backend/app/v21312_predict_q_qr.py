"""LEMMIQ v2.13.12: authenticated Q Predict payment QR and admin reference images.

Buyer QR images are ALWAYS generated from the exact purchase-order receiving
address. Uploaded images are admin-only references and can never redirect a
buyer's payment. Q Economy wallet data is not touched.
"""
from __future__ import annotations

import base64
import io
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel
from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, Session, mapped_column

from .database import Base
from .models import User
from .v21310_predict_q import Order, Treasury, _admin, _team_ids

MAX_UPLOAD_BYTES = 500_000


class PredictQrReference(Base):
    __tablename__ = 'v21312_predict_q_qr_references'
    network: Mapped[str] = mapped_column(String(12), primary_key=True)
    receiving_address: Mapped[str] = mapped_column(String(100))
    png_b64: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


def _make_png(address: str) -> str:
    import qrcode
    qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_M,
                       box_size=9, border=4)
    qr.add_data(address)
    qr.make(fit=True)
    picture = qr.make_image(fill_color='black', back_color='white').convert('RGB')
    output = io.BytesIO()
    picture.save(output, format='PNG')
    return base64.b64encode(output.getvalue()).decode('ascii')


def _active_treasury(db: Session, network: str) -> Treasury:
    if network not in ('TRC20', 'BEP20'):
        raise HTTPException(422, 'Unsupported USDT network')
    row = db.get(Treasury, network)
    if row is None or not row.active:
        raise HTTPException(404, 'Active Q Predict receiving address not configured')
    return row


def register_v21312_predict_q_qr(app, current_user, get_db):
    router = APIRouter(prefix='/v21312/predict/qr', tags=['Q Predict payment QR'])

    @router.get('/order/{order_id}')
    def order_qr(order_id: int, u: User = Depends(current_user), db: Session = Depends(get_db)):
        if u.id not in _team_ids():
            raise HTTPException(403, 'Q Predict access not approved')
        order = db.get(Order, order_id)
        if order is None or order.user_id != u.id:
            raise HTTPException(404, 'Purchase order not found')
        if order.network not in ('TRC20', 'BEP20') or not order.receiving_address:
            raise HTTPException(409, 'Invalid purchase-order receiving address')
        # Crucially, do not read a current treasury address: orders snapshot their
        # original address so rotation cannot alter an existing payment instruction.
        return {
            'order_id': order.id,
            'network': order.network,
            'receiving_address': order.receiving_address,
            'qr_png_b64': _make_png(order.receiving_address),
            'custom_qr_used': False,
            'source': 'ORDER_RECEIVING_ADDRESS',
        }

    @router.get('/admin/{network}')
    def admin_get(network: str, u: User = Depends(current_user), db: Session = Depends(get_db)):
        _admin(db, u)
        treasury = _active_treasury(db, network)
        saved = db.get(PredictQrReference, network)
        matches = saved is not None and saved.receiving_address == treasury.address
        return {
            'network': network,
            'receiving_address': treasury.address,
            'checkout_qr_png_b64': _make_png(treasury.address),
            'custom_reference_png_b64': saved.png_b64 if matches else None,
            'custom_reference_matches_current_address': matches,
            'custom_qr_used_for_checkout': False,
        }

    @router.post('/admin/{network}')
    async def admin_upload(network: str, file: UploadFile = File(...),
                           u: User = Depends(current_user), db: Session = Depends(get_db)):
        _admin(db, u)
        treasury = _active_treasury(db, network)
        raw = await file.read(MAX_UPLOAD_BYTES + 1)
        if len(raw) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, 'Maximum QR reference image size is 500 KB')
        try:
            img = Image.open(io.BytesIO(raw))
            if img.format not in ('PNG', 'JPEG', 'WEBP'):
                raise ValueError('Please upload PNG, JPEG or WEBP')
            img.load()
            if not (150 <= img.width <= 2048 and 150 <= img.height <= 2048):
                raise ValueError('QR reference must be 150–2048 pixels in each dimension')
            out = io.BytesIO()
            img.convert('RGB').save(out, format='PNG', optimize=True)
            if out.tell() > 900_000:
                raise ValueError('Converted PNG is too large')
        except (UnidentifiedImageError, OSError, ValueError) as exc:
            raise HTTPException(422, str(exc)) from exc
        record = db.get(PredictQrReference, network)
        if record is None:
            record = PredictQrReference(network=network,
                                        receiving_address=treasury.address,
                                        png_b64=base64.b64encode(out.getvalue()).decode('ascii'))
            db.add(record)
        else:
            record.receiving_address = treasury.address
            record.png_b64 = base64.b64encode(out.getvalue()).decode('ascii')
            record.updated_at = datetime.now(timezone.utc)
        db.commit()
        return {'saved': True, 'network': network,
                'note': 'Admin reference saved. Checkout QR is generated from the actual receiving address for safety.'}

    @router.delete('/admin/{network}')
    def admin_delete(network: str, u: User = Depends(current_user), db: Session = Depends(get_db)):
        _admin(db, u)
        if network not in ('TRC20', 'BEP20'):
            raise HTTPException(422, 'Unsupported USDT network')
        saved = db.get(PredictQrReference, network)
        if saved:
            db.delete(saved)
            db.commit()
        return {'removed': True}

    app.include_router(router)
