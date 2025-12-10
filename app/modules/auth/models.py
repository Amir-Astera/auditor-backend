# app/auth/models.py
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, BigInteger
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    email: Mapped[str | None] = mapped_column(String, unique=True, index=True, nullable=True)
    full_name: Mapped[str | None] = mapped_column(String, nullable=True)

    password_hash: Mapped[str | None] = mapped_column(String, nullable=True)

    # Телефон, который админ указал для сотрудника (как в Telegram)
    telegram_phone: Mapped[str | None] = mapped_column(String, unique=True, index=True)

    # Telegram user id (как числовой ID, когда привяжем через бота)
    telegram_user_id: Mapped[int | None] = mapped_column(BigInteger, unique=True, index=True)

    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
