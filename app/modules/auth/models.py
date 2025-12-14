from datetime import datetime
from uuid import uuid4
from sqlalchemy.dialects.postgresql import UUID

from sqlalchemy import BigInteger, Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class User(Base):
    __tablename__ = "users"

    # id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    id: Mapped[uuid4] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
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
