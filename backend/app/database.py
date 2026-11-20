import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

DATABASE_URL = os.getenv("DATABASE_URL", "").strip() or "sqlite:///./lemmiq.db"
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = "postgresql+psycopg://" + DATABASE_URL[len("postgres://"):]
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = "postgresql+psycopg://" + DATABASE_URL[len("postgresql://"):]

# V21316: bounded PostgreSQL pool prevents uncontrolled connection growth.
# Tune only after reviewing lemmiq-db Max Connections and Render pool metrics.
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {"connect_timeout": 10}
kwargs = {"pool_pre_ping": True, "connect_args": connect_args}
if not DATABASE_URL.startswith("sqlite"):
    kwargs.update(pool_size=max(1,min(int(os.getenv("LEMMIQ_DB_POOL_SIZE","5")),10)),
                  max_overflow=max(0,min(int(os.getenv("LEMMIQ_DB_MAX_OVERFLOW","3")),10)),
                  pool_timeout=10, pool_recycle=1800)
engine = create_engine(DATABASE_URL, **kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

class Base(DeclarativeBase):
    pass
