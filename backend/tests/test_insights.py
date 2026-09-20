from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app.database import Base
from app.models import User, InsightEvent
from app.insights import brief, list_events

def test_insight_scoped_aggregation():
    engine=create_engine("sqlite://",connect_args={"check_same_thread":False},poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add_all([User(id=1,username="one",display_name="One",password_hash="x",salt="x"),
                    User(id=2,username="two",display_name="Two",password_hash="x",salt="x")]);db.commit()
        for uid,amt in [(1,8540),(2,999999)]:
            db.add(InsightEvent(user_id=uid,client_event_id=str(uid)*10,category="MONEY",source="Test",
             title="Groceries",detail="",amount_cents=amt,direction="OUT",occurred_at=datetime.now(timezone.utc)))
        db.commit()
        assert brief(db,1)["spending_cents"]==8540
        assert len(list_events(db,1))==1
        assert brief(db,2)["spending_cents"]==999999
