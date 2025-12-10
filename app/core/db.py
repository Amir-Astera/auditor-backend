"""Database setup for SQLAlchemy sessions and metadata.

This module centralizes the engine and session factory configuration so that
all models share the same Base. It is intentionally minimal to keep
initialization predictable for both admin and Telegram entry points.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    pass


engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
