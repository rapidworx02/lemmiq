"""Private Business AUTO decision history. No wallet or market changes."""
from datetime import datetime, timezone
from sqlalchemy import Integer, String, Text, DateTime, ForeignKey, select
from sqlalchemy.orm import Mapped, mapped_column
from .database import Base
from .models import BusinessChatSetting

class BusinessAutoDecision309(Base):
    __tablename__ = 'business_auto_decisions_309'
    trigger_id: Mapped[int] = mapped_column(ForeignKey('messages.id'), primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    chat_id: Mapped[int] = mapped_column(ForeignKey('chats.id'), index=True)
    status: Mapped[str] = mapped_column(String(32))
    reason: Mapped[str] = mapped_column(String(240), default='')
    confidence: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda:datetime.now(timezone.utc))

def selected309(db,uid,cid):
    row=db.get(BusinessChatSetting, {'user_id':uid,'chat_id':cid})
    return bool(row and row.enabled)

def decision309(db,mid,uid,cid,status,reason='',confidence=0):
    row=db.get(BusinessAutoDecision309,mid)
    if row is None:
        row=BusinessAutoDecision309(trigger_id=mid,owner_id=uid,chat_id=cid,status=status)
        db.add(row)
    row.status=status;row.reason=reason[:240];row.confidence=max(0,min(100,int(confidence or 0)));row.updated_at=datetime.now(timezone.utc)
    # Caller owns the transaction, including any outstanding feature-charge reversal.

def history309(db,uid,cid):
    rows=db.scalars(select(BusinessAutoDecision309).where(BusinessAutoDecision309.owner_id==uid,BusinessAutoDecision309.chat_id==cid).order_by(BusinessAutoDecision309.trigger_id.desc()).limit(20)).all()
    return [dict(message_id=r.trigger_id,status=r.status,reason=r.reason,confidence=r.confidence,updated_at=r.updated_at.isoformat()) for r in rows]
