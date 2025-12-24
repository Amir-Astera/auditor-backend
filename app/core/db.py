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

import app.models

def _create_engine():
    """Create a SQLAlchemy engine with UTF-8 enforced.

    On some Windows setups with non-Latin usernames or system locales,
    ``psycopg2`` can raise ``UnicodeDecodeError`` when initializing the
    connection. Forcing UTF-8 client encoding prevents these crashes and
    keeps configuration deterministic across environments.
    """

    try:
        # Convert PostgresDsn to string for SQLAlchemy
        database_url = str(settings.DATABASE_URL)
        return create_engine(
            database_url,
            pool_pre_ping=True,
            connect_args={"client_encoding": "utf8"},
        )
    except UnicodeDecodeError as exc:  # pragma: no cover - defensive guard
        raise RuntimeError(
            "DATABASE_URL must be valid UTF-8. Please save your .env file "
            "in UTF-8 encoding and ensure credentials contain only UTF-8 "
            "characters."
        ) from exc


engine = _create_engine()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()