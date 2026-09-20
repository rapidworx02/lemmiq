from sqlalchemy import select
from .database import SessionLocal, Base, engine
from .models import User
from .main import hp

Base.metadata.create_all(bind=engine)
db=SessionLocal()
for username,name in [("eva","Eva"),("john","John"),("maya","Maya")]:
    if not db.scalar(select(User).where(User.username==username)):
        h,s=hp("password123")
        db.add(User(username=username,display_name=name,password_hash=h,salt=s))
db.commit();db.close()
print("Demo users ready: eva / john / maya — password123")
