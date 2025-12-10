# app/auth/models.py
from datetime import datetime
<<<<<<< HEAD

from sqlalchemy import Boolean, DateTime, String, BigInteger
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
=======
from uuid import uuid4

from sqlalchemy import BigInteger, Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
>>>>>>> e81b75286128c8454dcb0c6fa4879ac1da9358b2


class User(Base):
    __tablename__ = "users"

<<<<<<< HEAD
    id: Mapped[str] = mapped_column(String, primary_key=True)
=======
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
>>>>>>> e81b75286128c8454dcb0c6fa4879ac1da9358b2
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
